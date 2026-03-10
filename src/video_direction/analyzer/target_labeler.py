from __future__ import annotations
"""A-5: ターゲット別チェックリスト

各シーンを1層/2層にラベリング:
- 1層（ハイキャリア・エリート向け）: 焦燥感・所属欲求の喚起
- 2層（2代目3代目向け）: 共感・安心感の喚起
"""

import re
from dataclasses import dataclass, field
from ..integrations.ai_dev5_connector import VideoData, HighlightScene


# 1層向けキーワード（焦燥感・所属欲求）
TIER1_KEYWORDS = [
    "年収", "万円", "高収入", "ハイキャリア", "管理職", "マネージャー",
    "外資", "大手", "コンサル", "エリート", "凄い", "強い",
    "実績", "成果", "達成", "目標", "戦略", "投資",
    "独立", "起業", "フリーランス", "稼ぐ", "稼ぎ",
    "スキル", "能力", "専門", "希少", "転職",
    "仲間に入りたい", "基準", "当たり前",
]

# 2層向けキーワード（共感・安心感）
TIER2_KEYWORDS = [
    "家業", "実家", "2代目", "3代目", "自営",
    "悩み", "不安", "葛藤", "変化", "成長",
    "同じ", "共感", "安心", "仲間", "つながり",
    "始めた", "きっかけ", "最初は", "初めて",
    "続けられ", "諦め", "継続", "コツコツ",
    "バランス", "両立", "家庭", "プライベート",
    "コミュニティ", "サポート", "環境",
    "解決策", "ここで",
]

# ハイライトカテゴリ → ターゲット層の傾向マッピング
CATEGORY_TENDENCY = {
    "実績数字": "tier1",
    "属性紹介": "tier1",
    "パンチライン": "both",
    "TEKO価値": "both",
    "メッセージ": "tier2",
}


@dataclass
class SceneLabel:
    """シーンのターゲットラベル"""
    timestamp: str
    speaker: str
    text: str
    target_tier: str  # "tier1", "tier2", "both"
    tier_label: str  # "1層向け", "2層向け", "両層向け"
    reason: str
    emotional_hook: str  # 感情フック（焦燥感/所属欲求/共感/安心感）


@dataclass
class TargetBalance:
    """ターゲットバランスチェック結果"""
    tier1_count: int
    tier2_count: int
    both_count: int
    total: int
    tier1_ratio: float
    tier2_ratio: float
    balance_assessment: str  # "良好" / "1層偏重" / "2層偏重"
    recommendation: str


@dataclass
class TargetLabelResult:
    """ターゲットラベリング結果"""
    scenes: list  # List[SceneLabel]
    balance: TargetBalance


def label_targets(video_data: VideoData) -> TargetLabelResult:
    """各ハイライトシーンをターゲット層にラベリングし、バランスチェックする"""
    scenes = []

    for highlight in video_data.highlights:
        label = _label_scene(highlight)
        scenes.append(label)

    balance = _check_balance(scenes)
    return TargetLabelResult(scenes=scenes, balance=balance)


def _label_scene(highlight: HighlightScene) -> SceneLabel:
    """単一シーンのラベリング"""
    text = highlight.text
    category = highlight.category

    # カテゴリベースの初期判定
    base_tendency = CATEGORY_TENDENCY.get(category, "both")

    # キーワードスコアリング
    tier1_score = sum(1 for kw in TIER1_KEYWORDS if kw in text)
    tier2_score = sum(1 for kw in TIER2_KEYWORDS if kw in text)

    # 判定
    if base_tendency == "tier1" or tier1_score > tier2_score + 1:
        target = "tier1"
        label = "1層向け"
        hook = "焦燥感・所属欲求"
    elif base_tendency == "tier2" or tier2_score > tier1_score + 1:
        target = "tier2"
        label = "2層向け"
        hook = "共感・安心感"
    else:
        target = "both"
        label = "両層向け"
        hook = "焦燥感+共感"

    # 理由生成
    reasons = []
    if category in CATEGORY_TENDENCY:
        reasons.append(f"カテゴリ「{category}」")
    if tier1_score > 0:
        reasons.append(f"1層キーワード{tier1_score}件")
    if tier2_score > 0:
        reasons.append(f"2層キーワード{tier2_score}件")

    return SceneLabel(
        timestamp=highlight.timestamp,
        speaker=highlight.speaker,
        text=text,
        target_tier=target,
        tier_label=label,
        reason=" / ".join(reasons) if reasons else "文脈判定",
        emotional_hook=hook,
    )


def _check_balance(scenes: list[SceneLabel]) -> TargetBalance:
    """バランスチェック"""
    tier1 = sum(1 for s in scenes if s.target_tier == "tier1")
    tier2 = sum(1 for s in scenes if s.target_tier == "tier2")
    both = sum(1 for s in scenes if s.target_tier == "both")
    total = len(scenes) or 1

    tier1_ratio = (tier1 + both * 0.5) / total
    tier2_ratio = (tier2 + both * 0.5) / total

    if 0.3 <= tier1_ratio <= 0.7:
        assessment = "良好"
        recommendation = "1層・2層のバランスが取れています。"
    elif tier1_ratio > 0.7:
        assessment = "1層偏重"
        recommendation = "2層（共感・安心感）向けのシーンを追加検討してください。"
    else:
        assessment = "2層偏重"
        recommendation = "1層（焦燥感・所属欲求）向けのシーンを追加検討してください。"

    return TargetBalance(
        tier1_count=tier1,
        tier2_count=tier2,
        both_count=both,
        total=len(scenes),
        tier1_ratio=round(tier1_ratio, 2),
        tier2_ratio=round(tier2_ratio, 2),
        balance_assessment=assessment,
        recommendation=recommendation,
    )
