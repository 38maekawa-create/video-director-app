from __future__ import annotations
"""NEW-2: ハイライトカットポイントディレクション

ハイライト動画（ダイジェスト版）作成のための最適カットポイントを提案する。
切り抜き（E-1改）が短い単体動画を生成するのに対し、
ハイライトは複数のベストシーンを繋ぎ合わせたダイジェスト版を想定する。
"""

import re
from dataclasses import dataclass, field
from ..integrations.ai_dev5_connector import VideoData, HighlightScene
from .guest_classifier import ClassificationResult


# ハイライト使用に適したカテゴリ（優先度順）
HIGHLIGHT_PRIORITY = {
    "実績数字": 1,
    "パンチライン": 2,
    "属性紹介": 3,
    "TEKO価値": 4,
    "メッセージ": 5,
}

# ハイライト動画の推奨設定
TARGET_HIGHLIGHT_COUNT = 5  # ハイライト動画に含む理想的なシーン数
MAX_HIGHLIGHT_DURATION = 180  # ハイライト動画全体の最大長（秒）
SCENE_BUFFER_BEFORE = 3  # 各シーン前のバッファ（秒）
SCENE_BUFFER_AFTER = 2  # 各シーン後のバッファ（秒）
MIN_SCENE_DURATION = 8  # 最小シーン長（秒）
MAX_SCENE_DURATION = 45  # 最大シーン長（秒）


@dataclass
class HighlightCutScene:
    """ハイライトカットのシーン"""
    order: int  # 使用順序（1から）
    start_ts: str  # "MM:SS" 開始
    end_ts: str  # "MM:SS" 終了
    duration_seconds: int
    category: str  # ハイライトカテゴリ
    speaker: str
    text: str  # シーンの発言内容
    transition_note: str = ""  # 前シーンからのつなぎ方メモ
    telop_suggestion: str = ""  # このシーン用テロップ提案


@dataclass
class HighlightCutResult:
    """ハイライトカットポイント提案の全体結果"""
    scenes: list = field(default_factory=list)  # List[HighlightCutScene]
    total_duration_seconds: int = 0
    scene_count: int = 0
    structure_note: str = ""  # 構成メモ（オープニング→中盤→クライマックス等）
    opening_suggestion: str = ""  # オープニングの提案
    closing_suggestion: str = ""  # クロージングの提案


def suggest_highlight_cuts(
    video_data: VideoData,
    classification: ClassificationResult | None = None,
) -> HighlightCutResult:
    """ハイライトカットポイントを提案する

    Args:
        video_data: パース済みのVideoData
        classification: ゲスト分類結果（任意）

    Returns:
        HighlightCutResult: ハイライトカット提案
    """
    if not video_data.highlights:
        return HighlightCutResult()

    # 全ハイライトをスコアリング
    scored = _score_highlights(video_data.highlights)

    # 上位N件を選定（多様性を考慮）
    selected = _select_diverse_highlights(scored, TARGET_HIGHLIGHT_COUNT)

    # タイムスタンプ順にソート（ダイジェスト版は時系列順）
    selected.sort(key=lambda item: _timestamp_to_seconds(item[0].timestamp))

    # シーンを生成
    scenes = []
    total_duration = 0
    for i, (highlight, score) in enumerate(selected):
        scene = _create_highlight_scene(
            highlight=highlight,
            order=i + 1,
            prev_scene=scenes[-1] if scenes else None,
            classification=classification,
        )
        if total_duration + scene.duration_seconds <= MAX_HIGHLIGHT_DURATION:
            scenes.append(scene)
            total_duration += scene.duration_seconds

    # 構成メモの生成
    structure = _generate_structure_note(scenes, video_data)
    opening = _suggest_opening(scenes, video_data)
    closing = _suggest_closing(scenes, video_data)

    return HighlightCutResult(
        scenes=scenes,
        total_duration_seconds=total_duration,
        scene_count=len(scenes),
        structure_note=structure,
        opening_suggestion=opening,
        closing_suggestion=closing,
    )


def _score_highlights(
    highlights: list[HighlightScene],
) -> list[tuple[HighlightScene, float]]:
    """ハイライトシーンをスコアリングする

    スコアリング基準:
    - カテゴリ優先度（実績数字 > パンチライン > 属性紹介 > TEKO価値 > メッセージ）
    - テキストの長さ（短すぎず長すぎないものが高スコア）
    - 数字の有無（数字入りは注目度が高い）
    """
    scored = []
    for h in highlights:
        score = 0.0

        # カテゴリスコア（最大0.4）
        cat_priority = HIGHLIGHT_PRIORITY.get(h.category, 6)
        score += max(0, (6 - cat_priority) * 0.08)

        # テキスト長スコア（最大0.3）— 20-80文字が最適
        text_len = len(h.text)
        if 20 <= text_len <= 80:
            score += 0.3
        elif 10 <= text_len <= 120:
            score += 0.2
        else:
            score += 0.1

        # 数字ボーナス（最大0.2）
        if re.search(r"\d+万|\d+円|\d+%", h.text):
            score += 0.2

        # 引用テキストボーナス（最大0.1）— 「」で囲まれた印象的な発言
        if "「" in h.text or "」" in h.text:
            score += 0.1

        scored.append((h, round(score, 2)))

    # スコア降順でソート
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def _select_diverse_highlights(
    scored: list[tuple[HighlightScene, float]],
    count: int,
) -> list[tuple[HighlightScene, float]]:
    """多様性を考慮してハイライトを選定する

    同じカテゴリのシーンが連続しないよう、カテゴリの分散を優先する。
    """
    if len(scored) <= count:
        return scored

    selected = []
    used_categories = set()
    remaining = list(scored)

    # 第1ラウンド: 各カテゴリから最高スコアのものを1つずつ
    for item in remaining[:]:
        h, score = item
        if h.category not in used_categories and len(selected) < count:
            selected.append(item)
            used_categories.add(h.category)
            remaining.remove(item)

    # 第2ラウンド: 残り枠をスコア順で埋める
    for item in remaining:
        if len(selected) >= count:
            break
        selected.append(item)

    return selected[:count]


def _create_highlight_scene(
    highlight: HighlightScene,
    order: int,
    prev_scene: HighlightCutScene | None,
    classification: ClassificationResult | None,
) -> HighlightCutScene:
    """HighlightSceneからHighlightCutSceneを生成"""
    hl_sec = _timestamp_to_seconds(highlight.timestamp)

    # 開始・終了タイムスタンプ
    start_sec = max(0, hl_sec - SCENE_BUFFER_BEFORE)
    # テキスト長から推定表示時間を計算（1秒あたり約4文字）
    estimated_speech_sec = max(MIN_SCENE_DURATION, len(highlight.text) // 4)
    estimated_speech_sec = min(estimated_speech_sec, MAX_SCENE_DURATION)
    end_sec = hl_sec + estimated_speech_sec + SCENE_BUFFER_AFTER

    duration = end_sec - start_sec

    # トランジションメモ
    transition = ""
    if prev_scene:
        transition = _suggest_transition(prev_scene, highlight)
    else:
        transition = "オープニングから入り"

    # テロップ提案
    telop = _suggest_scene_telop(highlight, classification)

    return HighlightCutScene(
        order=order,
        start_ts=_seconds_to_timestamp(start_sec),
        end_ts=_seconds_to_timestamp(end_sec),
        duration_seconds=duration,
        category=highlight.category,
        speaker=highlight.speaker,
        text=highlight.text,
        transition_note=transition,
        telop_suggestion=telop,
    )


def _suggest_transition(
    prev_scene: HighlightCutScene,
    current_highlight: HighlightScene,
) -> str:
    """前シーンとのトランジション提案"""
    prev_cat = prev_scene.category
    curr_cat = current_highlight.category

    # カテゴリの変化に応じた提案
    if prev_cat == "属性紹介" and curr_cat == "実績数字":
        return "属性紹介から実績へ — 自然に繋がるカット"
    if prev_cat == "実績数字" and curr_cat == "パンチライン":
        return "数字のインパクトからパンチラインへ — テンポよく繋ぐ"
    if curr_cat == "TEKO価値":
        return "TEKOでの変化を語るシーンへ — 少し間を持たせてカット"
    if curr_cat == "メッセージ":
        return "締めメッセージへ — フェードまたはクロスカット"

    return "ストレートカットで繋ぐ"


def _suggest_scene_telop(
    highlight: HighlightScene,
    classification: ClassificationResult | None,
) -> str:
    """シーン用テロップの提案"""
    if highlight.category == "実績数字":
        numbers = re.findall(r"\d+万|\d+円|年収\d+", highlight.text)
        if numbers:
            return f"強調テロップ: {numbers[0]}（大きく、色変え）"

    if highlight.category == "パンチライン":
        text = highlight.text.strip("「」")
        if len(text) > 25:
            text = text[:22] + "..."
        return f"パンチラインテロップ: 「{text}」"

    if highlight.category == "属性紹介":
        return f"属性テロップ: {highlight.speaker}のプロフィール表示"

    if highlight.category == "メッセージ":
        return "サブタイトルテロップ: ゲストからのメッセージ"

    return ""


def _generate_structure_note(
    scenes: list[HighlightCutScene],
    video_data: VideoData,
) -> str:
    """ハイライト動画の構成メモを生成"""
    if not scenes:
        return "シーンが選定されませんでした。"

    parts = []

    # カテゴリの分布
    categories = [s.category for s in scenes]
    cat_set = set(categories)

    if len(scenes) <= 2:
        parts.append(f"コンパクト構成: {len(scenes)}シーン")
    elif "属性紹介" in cat_set and "メッセージ" in cat_set:
        parts.append("完全構成: 導入（属性紹介）→ 展開（実績・パンチライン）→ 締め（メッセージ）")
    elif "属性紹介" in cat_set:
        parts.append("導入付き構成: 属性紹介 → ハイライトシーン")
    else:
        parts.append("ハイライト集中構成: 印象的なシーンを時系列で繋ぐ")

    guest_name = video_data.profiles[0].name if video_data.profiles else "ゲスト"
    parts.append(f"ゲスト: {guest_name}")

    return " / ".join(parts)


def _suggest_opening(
    scenes: list[HighlightCutScene],
    video_data: VideoData,
) -> str:
    """オープニング提案"""
    guest_name = video_data.profiles[0].name if video_data.profiles else "ゲスト"

    if scenes and scenes[0].category == "属性紹介":
        return f"{guest_name}の属性紹介シーンでスタート。視聴者に人物像を提示。"

    # 最も印象的なシーンのフラッシュカット → 属性紹介 の構成
    return f"最初に最もインパクトのあるシーンをフラッシュ表示 → {guest_name}の属性紹介"


def _suggest_closing(
    scenes: list[HighlightCutScene],
    video_data: VideoData,
) -> str:
    """クロージング提案"""
    if scenes and scenes[-1].category == "メッセージ":
        return "ゲストからのメッセージで自然に締め。チャンネル登録誘導テロップを重ねる。"

    return "最後のシーン後にフェードアウト → 「フルバージョンはこちら」の誘導テロップ。"


def _timestamp_to_seconds(ts: str) -> int:
    """タイムスタンプを秒数に変換"""
    try:
        parts = ts.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0
    except (ValueError, AttributeError):
        return 0


def _seconds_to_timestamp(seconds: int) -> str:
    """秒数をMM:SS形式に変換"""
    if seconds < 0:
        seconds = 0
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"
