from __future__ import annotations
"""C-2: テロップ自動チェック

フォント統一性・サイズ適正・配置の一貫性をOCR+LLMで検証し、
誤字脱字検出も行う。

Phase 2実装:
- 文字起こし・ハイライトデータからの推定チェック（OCRなし）
- テロップ候補テキストの誤字脱字検出
- テロップ配置ルールの一貫性チェック

Phase 3実装:
- 実際の映像フレームからOCR（pytesseract）でテロップ読み取り
- pytesseract未インストール時はClaude Vision APIにフォールバック
- フォント・色・位置の一貫性チェック（フレーム間比較）
- テロップ表示タイミングの評価
"""

import base64
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from ..integrations.ai_dev5_connector import VideoData, HighlightScene
from .direction_generator import DirectionTimeline, DirectionEntry

# opencv-python のgraceful import
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    cv2 = None
    np = None
    HAS_CV2 = False

# pytesseract のgraceful import
try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    pytesseract = None
    HAS_TESSERACT = False

# anthropic のgraceful import
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    anthropic = None
    HAS_ANTHROPIC = False

logger = logging.getLogger(__name__)


# テロップチェックの閾値設定
MAX_TELOP_CHARS = 20  # テロップ1行の最大文字数
MIN_TELOP_CHARS = 2   # テロップの最小文字数
IDEAL_TELOP_CHARS = 12  # テロップの理想文字数

# よくある誤字パターン（テロップ特有）
COMMON_TYPO_PATTERNS = [
    (r"(\d),(\d{3})", None),  # カンマ区切り数字は正常 — チェック除外
    (r"[0-9０-９]+万[0-9０-９]+", "数字と「万」の間にスペースまたは区切りがありません"),
    (r"([ぁ-ん])\1{3,}", "同じひらがなが4回以上連続しています"),
    (r"([ァ-ヶ])\1{3,}", "同じカタカナが4回以上連続しています"),
]

# テロップに不適切な表現（長すぎる、冗長等）
VERBOSE_INDICATORS = [
    "ということで",
    "みたいな感じ",
    "っていうか",
    "なんですけど",
    "なんですが",
    "というわけで",
]


@dataclass
class TelopIssue:
    """テロップの問題点"""
    timestamp: str  # 問題が検出された箇所のタイムスタンプ
    issue_type: str  # "typo" / "length" / "consistency" / "readability" / "placement"
    severity: str  # "error" / "warning" / "info"
    description: str  # 問題の説明
    original_text: str = ""  # 元のテキスト
    suggestion: str = ""  # 修正提案


@dataclass
class TelopCandidate:
    """テロップ候補"""
    timestamp: str
    text: str  # テロップ表示テキスト
    category: str  # テロップの種類（強調/補足/数字/企業名伏せ）
    char_count: int = 0
    is_valid: bool = True
    issues: list = field(default_factory=list)  # List[TelopIssue]


@dataclass
class TelopCheckResult:
    """テロップチェック結果"""
    candidates: list = field(default_factory=list)  # List[TelopCandidate]
    issues: list = field(default_factory=list)  # List[TelopIssue] 全問題点
    total_telops: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    consistency_score: float = 0.0  # 一貫性スコア（0-100）
    is_estimated: bool = True  # OCR実測ではなく推定


def check_telops(
    video_data: VideoData,
    direction_timeline: DirectionTimeline | None = None,
) -> TelopCheckResult:
    """テロップの自動チェックを実行する

    Phase 2: 文字起こし・演出指示からテロップ候補を抽出し、
    テキストレベルのチェックを実施する。

    Args:
        video_data: パース済みのVideoData
        direction_timeline: 演出ディレクション結果（任意）

    Returns:
        TelopCheckResult: テロップチェック結果
    """
    candidates = []
    all_issues = []

    # Step 1: ハイライトからテロップ候補を抽出
    for hl in video_data.highlights:
        candidate = _create_telop_candidate_from_highlight(hl)
        candidates.append(candidate)

    # Step 2: 演出指示からテロップ候補を追加
    if direction_timeline:
        for entry in direction_timeline.entries:
            if entry.direction_type == "telop":
                candidate = _create_telop_candidate_from_direction(entry)
                # 重複チェック（同じタイムスタンプで既にあれば追加しない）
                existing_ts = {c.timestamp for c in candidates}
                if candidate.timestamp not in existing_ts:
                    candidates.append(candidate)

    # Step 3: 各テロップ候補をチェック
    for candidate in candidates:
        issues = _check_single_telop(candidate)
        candidate.issues = issues
        candidate.is_valid = not any(i.severity == "error" for i in issues)
        all_issues.extend(issues)

    # Step 4: テロップ間の一貫性チェック
    consistency_issues = _check_consistency(candidates)
    all_issues.extend(consistency_issues)

    # Step 5: 誤字脱字チェック（トランスクリプトベース）
    typo_issues = _check_typos_in_transcript(video_data)
    all_issues.extend(typo_issues)

    # 集計
    error_count = sum(1 for i in all_issues if i.severity == "error")
    warning_count = sum(1 for i in all_issues if i.severity == "warning")
    info_count = sum(1 for i in all_issues if i.severity == "info")

    # 一貫性スコア計算
    consistency_score = _calculate_consistency_score(candidates, all_issues)

    return TelopCheckResult(
        candidates=candidates,
        issues=all_issues,
        total_telops=len(candidates),
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
        consistency_score=consistency_score,
        is_estimated=True,
    )


def _create_telop_candidate_from_highlight(hl: HighlightScene) -> TelopCandidate:
    """ハイライトシーンからテロップ候補を生成"""
    # カテゴリに応じたテロップテキスト生成
    text = hl.text
    if hl.category == "実績数字":
        # 数字を含むテロップ — 強調テロップとして
        category = "数字強調"
        text = _extract_number_telop(hl.text)
    elif hl.category == "パンチライン":
        category = "キー発言強調"
        text = _extract_punchline_telop(hl.text)
    elif hl.category == "属性紹介":
        category = "属性テロップ"
        text = _extract_attribute_telop(hl.text)
    else:
        category = "一般テロップ"
        text = _truncate_for_telop(hl.text)

    char_count = len(text)

    return TelopCandidate(
        timestamp=hl.timestamp,
        text=text,
        category=category,
        char_count=char_count,
    )


def _create_telop_candidate_from_direction(entry: DirectionEntry) -> TelopCandidate:
    """演出ディレクションエントリーからテロップ候補を生成

    Args:
        entry: 演出ディレクションエントリー（direction_type == "telop" のもの）

    Returns:
        テロップ候補オブジェクト
    """
    text = entry.description if hasattr(entry, "description") else str(entry)
    # テロップ指示からテキスト部分を抽出
    telop_match = re.search(r"[「『](.*?)[」』]", text)
    if telop_match:
        text = telop_match.group(1)

    char_count = len(text)
    timestamp = entry.timestamp if hasattr(entry, "timestamp") else "00:00"

    return TelopCandidate(
        timestamp=timestamp,
        text=text,
        category="演出指示テロップ",
        char_count=char_count,
    )


def _check_single_telop(candidate: TelopCandidate) -> list[TelopIssue]:
    """単一テロップの品質チェック"""
    issues = []

    # 文字数チェック
    if candidate.char_count > MAX_TELOP_CHARS:
        issues.append(TelopIssue(
            timestamp=candidate.timestamp,
            issue_type="length",
            severity="warning",
            description=f"テロップが長すぎます（{candidate.char_count}文字、推奨{IDEAL_TELOP_CHARS}文字以下）",
            original_text=candidate.text,
            suggestion=_truncate_for_telop(candidate.text),
        ))
    elif candidate.char_count < MIN_TELOP_CHARS:
        issues.append(TelopIssue(
            timestamp=candidate.timestamp,
            issue_type="length",
            severity="info",
            description=f"テロップが短すぎます（{candidate.char_count}文字）",
            original_text=candidate.text,
        ))

    # 冗長表現チェック
    for verbose in VERBOSE_INDICATORS:
        if verbose in candidate.text:
            issues.append(TelopIssue(
                timestamp=candidate.timestamp,
                issue_type="readability",
                severity="warning",
                description=f"冗長表現「{verbose}」が含まれています",
                original_text=candidate.text,
                suggestion=candidate.text.replace(verbose, ""),
            ))

    # 括弧の対応チェック
    bracket_issues = _check_brackets(candidate)
    issues.extend(bracket_issues)

    return issues


def _check_brackets(candidate: TelopCandidate) -> list[TelopIssue]:
    """括弧の対応をチェック

    Args:
        candidate: チェック対象のテロップ候補

    Returns:
        括弧不一致が検出された場合の問題リスト（正常時は空リスト）
    """
    issues = []
    bracket_pairs = [("「", "」"), ("（", "）"), ("(", ")"), ("『", "』")]

    for open_b, close_b in bracket_pairs:
        open_count = candidate.text.count(open_b)
        close_count = candidate.text.count(close_b)
        if open_count != close_count:
            issues.append(TelopIssue(
                timestamp=candidate.timestamp,
                issue_type="typo",
                severity="error",
                description=f"括弧{open_b}{close_b}の対応が不一致です（開{open_count}個/閉{close_count}個）",
                original_text=candidate.text,
            ))

    return issues


def _check_consistency(candidates: list[TelopCandidate]) -> list[TelopIssue]:
    """テロップ間の一貫性チェック"""
    issues = []
    if len(candidates) < 2:
        return issues

    # 数字テロップの書式統一チェック
    number_telops = [c for c in candidates if c.category == "数字強調"]
    if len(number_telops) >= 2:
        # 万/億の表記ゆれチェック
        has_kanji_unit = any("万" in c.text or "億" in c.text for c in number_telops)
        has_plain_number = any(
            re.search(r"\d{4,}", c.text) and "万" not in c.text and "億" not in c.text
            for c in number_telops
        )
        if has_kanji_unit and has_plain_number:
            issues.append(TelopIssue(
                timestamp="全体",
                issue_type="consistency",
                severity="warning",
                description="数字テロップの表記が統一されていません（「万」表記と数値のみが混在）",
            ))

    # テロップ長の統一性チェック
    char_counts = [c.char_count for c in candidates if c.char_count > 0]
    if char_counts:
        avg_len = sum(char_counts) / len(char_counts)
        for c in candidates:
            if c.char_count > 0 and abs(c.char_count - avg_len) > avg_len * 0.8:
                issues.append(TelopIssue(
                    timestamp=c.timestamp,
                    issue_type="consistency",
                    severity="info",
                    description=f"テロップ長が平均（{avg_len:.0f}文字）から大きく乖離しています（{c.char_count}文字）",
                    original_text=c.text,
                ))

    return issues


def _check_typos_in_transcript(video_data: VideoData) -> list[TelopIssue]:
    """トランスクリプト内のテロップ向け誤字脱字チェック"""
    issues = []

    # ハイライト発言の誤字チェック
    for hl in video_data.highlights:
        for pattern, msg in COMMON_TYPO_PATTERNS:
            if msg is None:
                continue  # 正常パターンはスキップ
            if re.search(pattern, hl.text):
                issues.append(TelopIssue(
                    timestamp=hl.timestamp,
                    issue_type="typo",
                    severity="warning",
                    description=msg,
                    original_text=hl.text,
                ))

    return issues


def _calculate_consistency_score(candidates: list[TelopCandidate], issues: list[TelopIssue]) -> float:
    """一貫性スコアを計算（0-100）"""
    if not candidates:
        return 100.0

    score = 100.0

    # エラー1件あたり-15点、警告1件あたり-5点、info1件あたり-1点
    for issue in issues:
        if issue.severity == "error":
            score -= 15
        elif issue.severity == "warning":
            score -= 5
        elif issue.severity == "info":
            score -= 1

    return max(0.0, min(100.0, round(score, 1)))


def _extract_number_telop(text: str) -> str:
    """数字テロップ用のテキスト抽出"""
    # 年収・金額のパターン
    patterns = [
        r"年収[\s　]*(\d[\d,]*万?\d*円?)",
        r"(\d[\d,]*万?\d*円?)[\s　]*(?:稼|超|以上)",
        r"月収[\s　]*(\d[\d,]*万?\d*円?)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(0).strip()

    # 金額を含むテキストをそのまま短縮
    return _truncate_for_telop(text)


def _extract_punchline_telop(text: str) -> str:
    """パンチライン用テロップテキスト抽出"""
    # 引用符内のテキストがあればそれを使う
    quote_match = re.search(r"[「『](.*?)[」』]", text)
    if quote_match:
        return quote_match.group(1)
    return _truncate_for_telop(text)


def _extract_attribute_telop(text: str) -> str:
    """属性テロップ用テキスト抽出"""
    return _truncate_for_telop(text)


def _truncate_for_telop(text: str, max_chars: int = IDEAL_TELOP_CHARS) -> str:
    """テロップ用にテキストを短縮"""
    # 引用符を除去
    text = text.strip("「」『』")

    if len(text) <= max_chars:
        return text

    # 句読点で区切って最初の部分を使う
    for sep in ["。", "、", "！", "？", "…"]:
        if sep in text[:max_chars + 5]:
            idx = text.index(sep)
            if idx <= max_chars:
                return text[:idx]

    # 強制短縮
    return text[:max_chars]


# =====================================================================
# Phase 3: フレーム画像ベースのテロップ抽出・チェック
# =====================================================================

@dataclass
class ExtractedTelop:
    """フレーム画像から抽出されたテロップ情報"""
    timestamp: str  # "MM:SS" 形式
    text: str  # OCR/LLMで読み取ったテキスト
    confidence: float = 0.0  # 抽出信頼度（0-1）
    position: str = ""  # "top" / "center" / "bottom" / "unknown"
    font_info: str = ""  # フォント情報（LLMによる推定）
    color_info: str = ""  # 色情報（LLMによる推定）
    source: str = "unknown"  # "ocr" / "llm" / "estimated"


@dataclass
class TelopTimingIssue:
    """テロップ表示タイミングの問題"""
    timestamp: str
    issue_type: str  # "too_short" / "too_long" / "overlap" / "gap"
    severity: str  # "error" / "warning" / "info"
    description: str
    duration_sec: float = 0.0


@dataclass
class FrameTelopCheckResult:
    """フレーム画像ベースのテロップチェック結果"""
    extracted_telops: list = field(default_factory=list)  # List[ExtractedTelop]
    spelling_issues: list = field(default_factory=list)  # List[TelopIssue]
    consistency_issues: list = field(default_factory=list)  # List[TelopIssue]
    timing_issues: list = field(default_factory=list)  # List[TelopTimingIssue]
    total_frames_checked: int = 0
    total_telops_found: int = 0
    error_count: int = 0
    warning_count: int = 0
    overall_score: float = 100.0  # 総合スコア（0-100）
    extraction_method: str = "none"  # "ocr" / "llm" / "estimated"


def extract_telop_from_frame(frame_image_b64: str, timestamp: str = "00:00") -> list[ExtractedTelop]:
    """フレーム画像からテロップテキストを抽出する

    pytesseractが利用可能ならOCR、なければClaude Vision APIで代替。
    どちらも利用不可の場合は空リストを返す。

    Args:
        frame_image_b64: base64エンコードされたフレーム画像（JPEG）
        timestamp: フレームのタイムスタンプ（"MM:SS"形式）

    Returns:
        抽出されたテロップのリスト
    """
    # pytesseract（OCR）で抽出を試みる
    if HAS_TESSERACT and HAS_CV2:
        telops = _extract_with_ocr(frame_image_b64, timestamp)
        if telops:
            return telops

    # OCRが利用不可またはテロップ検出できなかった場合、LLMにフォールバック
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if HAS_ANTHROPIC and api_key:
        telops = _extract_with_llm(frame_image_b64, timestamp, api_key)
        if telops:
            return telops

    logger.info("OCR/LLMともに利用不可: テロップ抽出をスキップ")
    return []


def _extract_with_ocr(frame_image_b64: str, timestamp: str) -> list[ExtractedTelop]:
    """pytesseract OCRでテロップを抽出する

    画像を前処理（グレースケール化、二値化、テロップ領域推定）してからOCRを実行する。
    日本語テロップに対応。
    """
    try:
        # base64をcv2画像にデコード
        img_bytes = base64.b64decode(frame_image_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return []

        height, width = img.shape[:2]
        telops = []

        # テロップは画面の上部20%と下部30%に集中する傾向がある
        regions = [
            ("top", img[0:int(height * 0.2), :]),
            ("bottom", img[int(height * 0.7):, :]),
            ("center", img[int(height * 0.3):int(height * 0.7), :]),
        ]

        for region_name, region_img in regions:
            if region_img.size == 0:
                continue

            # 前処理: グレースケール → コントラスト強調 → 二値化
            gray = cv2.cvtColor(region_img, cv2.COLOR_BGR2GRAY)
            # CLAHE（適応的ヒストグラム均等化）でコントラスト強調
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            # 大津の二値化
            _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            # 反転版もOCRにかける（白文字on黒背景用）
            binary_inv = cv2.bitwise_not(binary)

            for img_variant in [binary, binary_inv]:
                text = pytesseract.image_to_string(
                    img_variant,
                    lang="jpn+eng",
                    config="--psm 6",  # ブロック単位のテキスト検出
                ).strip()

                if text and len(text) >= MIN_TELOP_CHARS:
                    # OCR結果をクリーニング（改行、余分な空白を除去）
                    cleaned = _clean_ocr_text(text)
                    if cleaned:
                        telops.append(ExtractedTelop(
                            timestamp=timestamp,
                            text=cleaned,
                            confidence=0.7,  # OCRの基本信頼度
                            position=region_name,
                            source="ocr",
                        ))

        # 重複除去（同じテキストの重複を排除）
        seen = set()
        unique_telops = []
        for t in telops:
            if t.text not in seen:
                seen.add(t.text)
                unique_telops.append(t)

        return unique_telops

    except Exception as e:
        logger.warning(f"OCRテロップ抽出に失敗: {e}")
        return []


def _clean_ocr_text(text: str) -> str:
    """OCR結果のテキストをクリーニングする"""
    # 改行を除去
    text = text.replace("\n", " ").replace("\r", "")
    # 連続する空白を1つに
    text = re.sub(r"\s+", " ", text).strip()
    # 1文字以下の場合は無効
    if len(text) < MIN_TELOP_CHARS:
        return ""
    # 記号のみの場合は無効
    if re.match(r"^[\s\W]+$", text):
        return ""
    return text


def _extract_with_llm(
    frame_image_b64: str,
    timestamp: str,
    api_key: str,
) -> list[ExtractedTelop]:
    """Claude Vision APIでテロップを抽出する

    画像内のテロップ/字幕テキストを読み取り、位置・フォント・色情報も推定する。
    """
    prompt = (
        "この動画フレーム画像に表示されているテロップ（字幕・テキスト）を全て読み取ってください。\n"
        "テロップが存在しない場合は空の配列を返してください。\n\n"
        "各テロップについて以下の情報をJSON形式で返してください（他のテキストは不要）:\n"
        "```json\n"
        "[\n"
        '  {"text": "テロップのテキスト", "position": "bottom", "font_info": "ゴシック体・白・大", "color_info": "白文字に黒縁取り"},\n'
        '  {"text": "別のテロップ", "position": "top", "font_info": "明朝体・黄色・中", "color_info": "黄色文字"}\n'
        "]\n"
        "```\n\n"
        "positionは top/center/bottom のいずれか。\n"
        "font_infoはフォントの種類・色・サイズの推定。\n"
        "color_infoは文字色と装飾（縁取り・影等）の推定。"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": frame_image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )

        response_text = message.content[0].text
        return _parse_llm_telop_response(response_text, timestamp)

    except Exception as e:
        logger.warning(f"Claude Vision APIでのテロップ抽出に失敗: {e}")
        return []


def _parse_llm_telop_response(response_text: str, timestamp: str) -> list[ExtractedTelop]:
    """LLMのテロップ抽出レスポンスをパースする"""
    telops = []

    try:
        # JSONブロックを抽出
        json_match = re.search(r"```json\s*\n?(.*?)\n?```", response_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(1))
        else:
            data = json.loads(response_text.strip())

        if not isinstance(data, list):
            data = [data]

        for item in data:
            if not isinstance(item, dict):
                continue
            text = item.get("text", "").strip()
            if text and len(text) >= MIN_TELOP_CHARS:
                telops.append(ExtractedTelop(
                    timestamp=timestamp,
                    text=text,
                    confidence=0.85,  # LLMの信頼度はOCRより高め
                    position=item.get("position", "unknown"),
                    font_info=item.get("font_info", ""),
                    color_info=item.get("color_info", ""),
                    source="llm",
                ))

    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning(f"LLMテロップレスポンスのパースに失敗: {e}")

    return telops


def check_spelling(text: str) -> list[TelopIssue]:
    """テロップテキストの誤字脱字チェック（日本語対応）

    OCR/LLM抽出されたテロップテキストに対して、
    パターンベースの誤字脱字チェックを実施する。

    Args:
        text: チェック対象テキスト

    Returns:
        検出された問題のリスト
    """
    issues = []

    # 既存の誤字パターンチェック
    for pattern, msg in COMMON_TYPO_PATTERNS:
        if msg is None:
            continue
        if re.search(pattern, text):
            issues.append(TelopIssue(
                timestamp="",
                issue_type="typo",
                severity="warning",
                description=msg,
                original_text=text,
            ))

    # 括弧の対応チェック（TelopCandidateを構築して再利用）
    temp_candidate = TelopCandidate(timestamp="", text=text, category="", char_count=len(text))
    bracket_issues = _check_brackets(temp_candidate)
    issues.extend(bracket_issues)

    # 全角半角の混在チェック
    has_fullwidth_num = bool(re.search(r"[０-９]", text))
    has_halfwidth_num = bool(re.search(r"[0-9]", text))
    if has_fullwidth_num and has_halfwidth_num:
        issues.append(TelopIssue(
            timestamp="",
            issue_type="typo",
            severity="warning",
            description="全角数字と半角数字が混在しています",
            original_text=text,
            suggestion="半角数字に統一することを推奨",
        ))

    # 全角半角アルファベットの混在チェック
    has_fullwidth_alpha = bool(re.search(r"[Ａ-Ｚａ-ｚ]", text))
    has_halfwidth_alpha = bool(re.search(r"[A-Za-z]", text))
    if has_fullwidth_alpha and has_halfwidth_alpha:
        issues.append(TelopIssue(
            timestamp="",
            issue_type="typo",
            severity="info",
            description="全角英字と半角英字が混在しています",
            original_text=text,
        ))

    return issues


def check_font_consistency(telops: list[ExtractedTelop]) -> list[TelopIssue]:
    """テロップ間のフォント・色・位置の一貫性チェック

    複数フレームから抽出されたテロップの視覚的な一貫性を検証する。

    Args:
        telops: 抽出されたテロップリスト

    Returns:
        検出された一貫性の問題リスト
    """
    issues = []
    if len(telops) < 2:
        return issues

    # フォント情報がある場合のみチェック
    font_infos = [t.font_info for t in telops if t.font_info]
    if len(font_infos) >= 2:
        # フォント情報の一意値を取得
        unique_fonts = set(font_infos)
        if len(unique_fonts) > 2:
            issues.append(TelopIssue(
                timestamp="全体",
                issue_type="consistency",
                severity="warning",
                description=f"テロップのフォントが{len(unique_fonts)}種類検出されました。統一を推奨します",
            ))

    # 色情報がある場合のみチェック
    color_infos = [t.color_info for t in telops if t.color_info]
    if len(color_infos) >= 2:
        unique_colors = set(color_infos)
        if len(unique_colors) > 3:
            issues.append(TelopIssue(
                timestamp="全体",
                issue_type="consistency",
                severity="info",
                description=f"テロップの色パターンが{len(unique_colors)}種類検出されました",
            ))

    # 位置の一貫性チェック
    positions = [t.position for t in telops if t.position and t.position != "unknown"]
    if positions:
        from collections import Counter
        pos_counts = Counter(positions)
        dominant_pos = pos_counts.most_common(1)[0]
        # 支配的な位置が50%未満なら一貫性に問題
        if dominant_pos[1] / len(positions) < 0.5 and len(positions) >= 3:
            issues.append(TelopIssue(
                timestamp="全体",
                issue_type="placement",
                severity="info",
                description="テロップの表示位置がバラバラです。統一的な配置を推奨します",
            ))

    return issues


def analyze_telop_timing(
    telops_with_timestamps: list[dict],
    min_display_sec: float = 1.5,
    max_display_sec: float = 8.0,
) -> list[TelopTimingIssue]:
    """テロップ表示タイミングの評価

    テロップの表示時間・間隔を評価し、視聴者の読みやすさを検証する。

    Args:
        telops_with_timestamps: テロップリスト。各要素は以下のキーを持つ:
            - "text": str
            - "start_sec": float (表示開始時刻・秒)
            - "end_sec": float (表示終了時刻・秒)
        min_display_sec: テロップの最低表示時間（秒）
        max_display_sec: テロップの最大表示時間（秒）

    Returns:
        タイミング問題のリスト
    """
    issues = []
    if not telops_with_timestamps:
        return issues

    for i, telop in enumerate(telops_with_timestamps):
        start = telop.get("start_sec", 0)
        end = telop.get("end_sec", 0)
        text = telop.get("text", "")
        duration = end - start

        if duration <= 0:
            continue

        ts = _seconds_to_timestamp(start)

        # 表示時間が短すぎる
        if duration < min_display_sec:
            issues.append(TelopTimingIssue(
                timestamp=ts,
                issue_type="too_short",
                severity="warning",
                description=f"テロップ「{text[:15]}...」の表示時間が短すぎます（{duration:.1f}秒、最低{min_display_sec}秒推奨）",
                duration_sec=duration,
            ))

        # 表示時間が長すぎる
        if duration > max_display_sec:
            issues.append(TelopTimingIssue(
                timestamp=ts,
                issue_type="too_long",
                severity="info",
                description=f"テロップ「{text[:15]}...」の表示時間が長すぎます（{duration:.1f}秒）",
                duration_sec=duration,
            ))

        # 文字数に対して表示時間が不適切（日本語は1文字あたり0.3秒が目安）
        char_count = len(text)
        ideal_duration = max(min_display_sec, char_count * 0.3)
        if duration < ideal_duration * 0.5:
            issues.append(TelopTimingIssue(
                timestamp=ts,
                issue_type="too_short",
                severity="error",
                description=f"テロップ（{char_count}文字）に対して表示時間（{duration:.1f}秒）が不足しています（推奨: {ideal_duration:.1f}秒以上）",
                duration_sec=duration,
            ))

        # 前のテロップとの重複チェック
        if i > 0:
            prev_end = telops_with_timestamps[i - 1].get("end_sec", 0)
            if start < prev_end:
                overlap = prev_end - start
                issues.append(TelopTimingIssue(
                    timestamp=ts,
                    issue_type="overlap",
                    severity="warning",
                    description=f"テロップが前のテロップと{overlap:.1f}秒重複しています",
                    duration_sec=overlap,
                ))

    return issues


def check_telops_from_frames(
    video_path: Optional[str] = None,
    frame_images_b64: Optional[list[dict]] = None,
    video_data: Optional[VideoData] = None,
    telops_with_timestamps: Optional[list[dict]] = None,
) -> FrameTelopCheckResult:
    """フレーム画像ベースのテロップ総合チェックを実行する

    動画ファイルまたはbase64フレーム画像のリストからテロップを抽出し、
    誤字脱字・フォント一貫性・タイミングをチェックする。

    Args:
        video_path: 動画ファイルパス（cv2で自動フレーム抽出）
        frame_images_b64: base64フレーム画像のリスト
            各要素は {"image": "base64...", "timestamp": "MM:SS"} の形式
        video_data: VideoData（テキストベースチェックとの統合用）
        telops_with_timestamps: タイミング評価用のテロップデータ

    Returns:
        FrameTelopCheckResult: テロップチェック結果
    """
    all_telops: list[ExtractedTelop] = []
    all_spelling_issues: list[TelopIssue] = []
    frames_checked = 0
    extraction_method = "none"

    # フレーム画像の準備
    frames = []
    if frame_images_b64:
        frames = frame_images_b64
    elif video_path and HAS_CV2:
        frames = _sample_frames_from_video(video_path)

    # 各フレームからテロップを抽出
    for frame_data in frames:
        image_b64 = frame_data.get("image", "")
        timestamp = frame_data.get("timestamp", "00:00")

        if not image_b64:
            continue

        telops = extract_telop_from_frame(image_b64, timestamp)
        all_telops.extend(telops)
        frames_checked += 1

        if telops:
            extraction_method = telops[0].source

    # 各テロップの誤字脱字チェック
    for telop in all_telops:
        spelling_issues = check_spelling(telop.text)
        for issue in spelling_issues:
            issue.timestamp = telop.timestamp
        all_spelling_issues.extend(spelling_issues)

    # テロップ間の一貫性チェック
    consistency_issues = check_font_consistency(all_telops)

    # タイミングチェック
    timing_issues = []
    if telops_with_timestamps:
        timing_issues = analyze_telop_timing(telops_with_timestamps)

    # 総合スコア計算
    all_issues_count = len(all_spelling_issues) + len(consistency_issues) + len(timing_issues)
    error_count = (
        sum(1 for i in all_spelling_issues if i.severity == "error")
        + sum(1 for i in consistency_issues if i.severity == "error")
        + sum(1 for i in timing_issues if i.severity == "error")
    )
    warning_count = (
        sum(1 for i in all_spelling_issues if i.severity == "warning")
        + sum(1 for i in consistency_issues if i.severity == "warning")
        + sum(1 for i in timing_issues if i.severity == "warning")
    )

    score = 100.0
    score -= error_count * 15
    score -= warning_count * 5
    score -= (all_issues_count - error_count - warning_count) * 1
    overall_score = max(0.0, min(100.0, round(score, 1)))

    return FrameTelopCheckResult(
        extracted_telops=all_telops,
        spelling_issues=all_spelling_issues,
        consistency_issues=consistency_issues,
        timing_issues=timing_issues,
        total_frames_checked=frames_checked,
        total_telops_found=len(all_telops),
        error_count=error_count,
        warning_count=warning_count,
        overall_score=overall_score,
        extraction_method=extraction_method if all_telops else "none",
    )


def _sample_frames_from_video(
    video_path: str,
    num_samples: int = 10,
) -> list[dict]:
    """動画からフレームを等間隔サンプリングしてbase64で返す"""
    if not HAS_CV2:
        return []

    if not os.path.isfile(video_path):
        logger.warning(f"動画ファイルが見つかりません: {video_path}")
        return []

    if num_samples <= 0:
        return []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        return []

    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0 or fps <= 0:
            return []

        interval = total_frames / num_samples
        frames = []

        for i in range(num_samples):
            frame_idx = int(i * interval)
            if frame_idx >= total_frames:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue
            _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            b64 = base64.b64encode(buffer).decode("utf-8")
            sec = frame_idx / fps
            frames.append({
                "image": b64,
                "timestamp": _seconds_to_timestamp(sec),
            })

        return frames
    finally:
        cap.release()


def _seconds_to_timestamp(sec: float) -> str:
    """秒数を'MM:SS'形式のタイムスタンプに変換"""
    minutes = int(sec // 60)
    seconds = int(sec % 60)
    return f"{minutes:02d}:{seconds:02d}"
