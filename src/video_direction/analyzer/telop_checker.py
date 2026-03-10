from __future__ import annotations
"""C-2: テロップ自動チェック

フォント統一性・サイズ適正・配置の一貫性をOCR+LLMで検証し、
誤字脱字検出も行う。

Phase 2初期実装:
- 文字起こし・ハイライトデータからの推定チェック（OCRなし）
- テロップ候補テキストの誤字脱字検出
- テロップ配置ルールの一貫性チェック

Phase 3以降（C-1実装後）:
- 実際の映像フレームからOCRでテロップ読み取り
- フォント・サイズ・配置の実測検証
"""

import re
from dataclasses import dataclass, field
from ..integrations.ai_dev5_connector import VideoData, HighlightScene
from .direction_generator import DirectionTimeline


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


def _create_telop_candidate_from_direction(entry) -> TelopCandidate:
    """演出ディレクションエントリーからテロップ候補を生成"""
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


def _check_single_telop(candidate: TelopCandidate) -> list:
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


def _check_brackets(candidate: TelopCandidate) -> list:
    """括弧の対応をチェック"""
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


def _check_consistency(candidates: list) -> list:
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


def _check_typos_in_transcript(video_data: VideoData) -> list:
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


def _calculate_consistency_score(candidates: list, issues: list) -> float:
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
