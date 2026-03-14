from __future__ import annotations
"""NEW-1: 演出ディレクション生成

テロップ強調・色変え・画角変更のタイミング指示をタイムライン形式で生成する。
LLM（Claude Sonnet）を使って文脈分析 → タイムライン形式の指示を生成。
FB学習ループ: FeedbackLearnerのルールを自動反映してディレクション品質を向上させる。
"""

import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from ..integrations.ai_dev5_connector import VideoData, HighlightScene
from .guest_classifier import ClassificationResult
from .income_evaluator import IncomeEvaluation


@dataclass
class DirectionEntry:
    """演出ディレクションの1エントリ"""
    timestamp: str  # "MM:SS"
    direction_type: str  # "telop" / "camera" / "color" / "composite"
    instruction: str  # 具体的な演出指示
    reason: str  # この演出をする理由
    priority: str  # "high" / "medium" / "low"


@dataclass
class DirectionTimeline:
    """演出ディレクション全体"""
    entries: list = field(default_factory=list)  # List[DirectionEntry]
    llm_analysis: str = ""  # LLMによる追加分析（あれば）
    applied_rules: list = field(default_factory=list)  # 適用されたFB学習ルール


def generate_directions(
    video_data: VideoData,
    classification: ClassificationResult,
    income_eval: IncomeEvaluation,
    feedback_learner=None,
) -> DirectionTimeline:
    """ルールベースで演出ディレクションを生成する

    Args:
        video_data: 動画データ
        classification: ゲスト分類結果
        income_eval: 年収演出判断結果
        feedback_learner: FeedbackLearnerインスタンス（FB学習ルール反映用、Noneなら無視）
    """
    entries = []

    for highlight in video_data.highlights:
        highlight_entries = _generate_for_highlight(
            highlight, classification, income_eval
        )
        entries.extend(highlight_entries)

    # FB学習ルールの適用
    applied_rules = []
    if feedback_learner is not None:
        fb_entries, applied_rules = _apply_learned_rules(
            video_data, classification, income_eval, feedback_learner
        )
        entries.extend(fb_entries)

    # タイムスタンプ順にソート
    entries.sort(key=lambda e: _timestamp_to_seconds(e.timestamp))

    # LLM分析を試行（APIキーがなければスキップ）
    llm_analysis = ""
    try:
        llm_analysis = _llm_analyze(video_data, classification, income_eval)
    except Exception:
        pass

    return DirectionTimeline(entries=entries, llm_analysis=llm_analysis, applied_rules=applied_rules)


def _generate_for_highlight(
    highlight: HighlightScene,
    classification: ClassificationResult,
    income_eval: IncomeEvaluation,
) -> list[DirectionEntry]:
    """ハイライトシーンから演出指示を生成"""
    entries = []
    ts = highlight.timestamp
    text = highlight.text
    category = highlight.category

    # テロップ強調タイミング
    if category == "実績数字":
        # 年収・実績の数字が出た瞬間 → テロップ強調
        numbers = re.findall(r"\d+万|年収\d+|月利?\d+万|月収?\d+万", text)
        if numbers:
            entries.append(DirectionEntry(
                timestamp=ts,
                direction_type="telop",
                instruction=f"テロップ強調: 「{numbers[0]}」を大きく表示、色変え（赤orゴールド）",
                reason=f"実績数字の出現（{', '.join(numbers)}）",
                priority="high",
            ))
            # 色変えも同時
            entries.append(DirectionEntry(
                timestamp=ts,
                direction_type="color",
                instruction="色変え: テロップ出現に合わせて画面演出（フラッシュ or 背景色変更）",
                reason="強調テロップ出現時の色変え",
                priority="medium",
            ))

    if category == "パンチライン":
        # キー発言 → テロップ強調 + 寄り
        # テキストから短いパンチラインを抽出
        punch = _extract_punchline(text)
        entries.append(DirectionEntry(
            timestamp=ts,
            direction_type="telop",
            instruction=f"テロップ強調: 「{punch}」（パンチライン）",
            reason="キー発言の強調",
            priority="high",
        ))
        entries.append(DirectionEntry(
            timestamp=ts,
            direction_type="camera",
            instruction="画角変更: ワイド → 寄り（アップ）でキー発言を際立たせる",
            reason="パンチライン発言時の寄り",
            priority="high",
        ))

    if category == "属性紹介":
        # 属性紹介 → テロップで属性情報表示
        entries.append(DirectionEntry(
            timestamp=ts,
            direction_type="telop",
            instruction=f"属性テロップ: ゲストの肩書き・属性情報を表示",
            reason="ゲスト属性の視覚的提示",
            priority="medium",
        ))

    if category == "TEKO価値":
        # TEKO価値の証言 → 2ショットで信頼感演出
        entries.append(DirectionEntry(
            timestamp=ts,
            direction_type="camera",
            instruction="画角: 2ショット（ワイド）で対話の空気感を見せる",
            reason="TEKO価値の証言は対話の雰囲気が重要",
            priority="medium",
        ))

    if category == "メッセージ":
        # 締めメッセージ → 寄りで説得力
        entries.append(DirectionEntry(
            timestamp=ts,
            direction_type="camera",
            instruction="画角変更: 寄り（アップ）で視聴者への直接メッセージ感",
            reason="視聴者への直接メッセージ",
            priority="medium",
        ))

    # 層a/bの強さ強調シーン → 色変え
    if classification.tier in ("a", "b") and category in ("実績数字", "パンチライン"):
        if not any(e.direction_type == "color" for e in entries):
            entries.append(DirectionEntry(
                timestamp=ts,
                direction_type="color",
                instruction=f"色変え: {classification.tier_label}の強さ強調シーン",
                reason=f"ゲスト{classification.tier_label}の強さ演出",
                priority="medium",
            ))

    return entries


def _extract_punchline(text: str) -> str:
    """長いテキストからパンチラインを抽出（50文字以内に短縮）"""
    if len(text) <= 50:
        return text
    # 。で分割して最初の文を取得
    sentences = text.split("。")
    if sentences and len(sentences[0]) <= 50:
        return sentences[0]
    # 先頭50文字 + ...
    return text[:47] + "..."


def _timestamp_to_seconds(ts: str) -> int:
    """タイムスタンプを秒数に変換"""
    parts = ts.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0


def _apply_learned_rules(
    video_data: VideoData,
    classification: ClassificationResult,
    income_eval: IncomeEvaluation,
    feedback_learner,
) -> tuple[list[DirectionEntry], list]:
    """FB学習ルールに基づく追加ディレクションを生成

    FeedbackLearnerから有効なルールを取得し、各ハイライトシーンに
    該当するルールがあれば追加の演出指示を生成する。

    Returns:
        (追加エントリ一覧, 適用されたルールのリスト)
    """
    entries = []
    applied_rules = []

    active_rules = feedback_learner.get_active_rules()
    if not active_rules:
        return entries, applied_rules

    # カテゴリ → ディレクションタイプのマッピング
    category_to_direction = {
        "cutting": "composite",
        "color": "color",
        "telop": "telop",
        "bgm": "composite",
        "camera": "camera",
        "composition": "camera",
        "tempo": "composite",
        "general": "composite",
    }

    for rule in active_rules:
        rule_applied = False
        direction_type = category_to_direction.get(rule.category, "composite")

        for highlight in video_data.highlights:
            # ルールのカテゴリとハイライトの内容を照合
            if _rule_matches_highlight(rule, highlight):
                entries.append(DirectionEntry(
                    timestamp=highlight.timestamp,
                    direction_type=direction_type,
                    instruction=f"[FB学習] {rule.rule_text}",
                    reason=f"FB学習ルール適用（{rule.id}、優先度: {rule.priority}）",
                    priority=rule.priority,
                ))
                rule_applied = True

        if rule_applied:
            applied_rules.append({
                "rule_id": rule.id,
                "rule_text": rule.rule_text,
                "category": rule.category,
                "priority": rule.priority,
            })
            # ルールの適用回数を更新
            rule.applied_count += 1

    # ルール適用回数を永続化
    if applied_rules:
        try:
            feedback_learner._save()
        except Exception:
            pass

    return entries, applied_rules


def _rule_matches_highlight(rule, highlight) -> bool:
    """ルールがハイライトシーンに適用可能か判定

    ルールのカテゴリとハイライトのカテゴリ・テキスト内容を照合する。
    """
    rule_text_lower = rule.rule_text.lower()
    highlight_text_lower = (highlight.text or "").lower()
    highlight_category_lower = (highlight.category or "").lower()

    # ルールのカテゴリに関連するキーワードがハイライトに含まれるか
    category_keywords = {
        "cutting": ["カット", "切り", "繋ぎ", "トランジション"],
        "color": ["色", "カラー", "明る", "暗"],
        "telop": ["テロップ", "字幕", "テキスト", "文字"],
        "bgm": ["bgm", "音楽", "se", "効果音"],
        "camera": ["カメラ", "アングル", "画角", "ズーム"],
        "composition": ["構図", "レイアウト", "配置"],
        "tempo": ["テンポ", "リズム", "スピード", "間"],
    }

    # カテゴリマッチ: ルールのカテゴリに関連するハイライトカテゴリ
    category_map = {
        "cutting": ["パンチライン", "実績数字"],
        "color": ["実績数字", "パンチライン"],
        "telop": ["実績数字", "パンチライン", "属性紹介"],
        "bgm": ["メッセージ", "TEKO価値"],
        "camera": ["パンチライン", "TEKO価値", "メッセージ"],
        "composition": ["属性紹介", "TEKO価値"],
        "tempo": ["パンチライン", "メッセージ"],
    }

    matching_categories = category_map.get(rule.category, [])
    if highlight.category in matching_categories:
        return True

    # テキストベースのマッチング: ルールテキスト内のキーワードがハイライトに含まれるか
    keywords = category_keywords.get(rule.category, [])
    for kw in keywords:
        if kw.lower() in highlight_text_lower:
            return True

    return False


def _llm_analyze(
    video_data: VideoData,
    classification: ClassificationResult,
    income_eval: IncomeEvaluation,
) -> str:
    """LLM（Claude Sonnet）による追加分析"""
    # APIキー読み込み
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        env_file = Path.home() / ".config" / "maekawa" / "api-keys.env"
        if env_file.exists():
            for line in env_file.read_text().split("\n"):
                if line.startswith("ANTHROPIC_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        return ""

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    # ハイライトシーンのサマリー
    highlights_text = "\n".join([
        f"[{h.timestamp}] {h.speaker}: {h.text} ({h.category})"
        for h in video_data.highlights[:15]
    ])

    prompt = f"""以下はTEKO対談インタビュー動画のハイライトシーンです。
動画編集者向けに、追加の演出ディレクション提案を3〜5個生成してください。

ゲスト情報:
- 分類: {classification.tier_label}
- 年収演出: {income_eval.emphasis_reason}
- タイトル: {video_data.title}

ハイライトシーン:
{highlights_text}

以下のフォーマットで、具体的なタイムスタンプと演出指示を出してください:
[MM:SS] 演出タイプ（テロップ/画角/色変え）: 具体的な指示内容

注意:
- ディレクションマニュアルの原則に従うこと
- 年収以外の強さ（企業ブランド・勤務形態等）も活用すること
- 固有名詞の扱いに注意（迷ったら伏せる）
"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
