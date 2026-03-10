from __future__ import annotations
"""E-1改: 切り抜きカットポイント提案

切り抜き動画（ショート・リール等）作成のための最適カットポイントを提案する。
文字起こしのハイライトシーンとトランスクリプトから、
単体で成立するセグメントを検出し、開始・終了タイムスタンプを指示する。
"""

import re
from dataclasses import dataclass, field
from ..integrations.ai_dev5_connector import VideoData, HighlightScene


# 切り抜きに適したカテゴリ（優先度順）
CLIP_WORTHY_CATEGORIES = [
    "パンチライン",
    "実績数字",
    "メッセージ",
    "TEKO価値",
    "属性紹介",
]

# 切り抜き動画の推奨時間範囲（秒）
MIN_CLIP_DURATION = 15
MAX_CLIP_DURATION = 90
IDEAL_CLIP_DURATION = 45

# 前後バッファ（秒）— 文脈を持たせるための余白
PRE_BUFFER = 5
POST_BUFFER = 3


@dataclass
class ClipSegment:
    """切り抜きセグメント"""
    start_ts: str  # "MM:SS" 開始タイムスタンプ
    end_ts: str  # "MM:SS" 終了タイムスタンプ
    duration_seconds: int  # 推定秒数
    title_suggestion: str  # 切り抜きのタイトル案
    hook_text: str  # 冒頭フック（最初に出す文言）
    highlights: list = field(default_factory=list)  # 含まれるハイライト
    clip_type: str = ""  # "punchline" / "achievement" / "message" / "story"
    priority: str = "medium"  # "high" / "medium" / "low"
    standalone_score: float = 0.0  # 単体成立度（0.0-1.0）


@dataclass
class ClipCutResult:
    """切り抜きカットポイント提案の全体結果"""
    clips: list = field(default_factory=list)  # List[ClipSegment]
    total_highlights: int = 0
    clip_count: int = 0


def suggest_clip_cuts(video_data: VideoData) -> ClipCutResult:
    """切り抜きカットポイントを提案する

    Args:
        video_data: パース済みのVideoData

    Returns:
        ClipCutResult: カットポイント提案一覧
    """
    if not video_data.highlights:
        return ClipCutResult(total_highlights=0, clip_count=0)

    # ハイライトシーンをタイムスタンプ順にソート
    sorted_highlights = sorted(
        video_data.highlights,
        key=lambda h: _timestamp_to_seconds(h.timestamp)
    )

    # 近接するハイライトをグループ化（同一セグメントとして切り出す）
    groups = _group_nearby_highlights(sorted_highlights)

    # 各グループからクリップセグメントを生成
    clips = []
    for group in groups:
        clip = _create_clip_segment(group, video_data)
        if clip and clip.duration_seconds >= MIN_CLIP_DURATION:
            clips.append(clip)

    # 優先度でソート（high → medium → low）
    priority_order = {"high": 0, "medium": 1, "low": 2}
    clips.sort(key=lambda c: priority_order.get(c.priority, 99))

    return ClipCutResult(
        clips=clips,
        total_highlights=len(video_data.highlights),
        clip_count=len(clips),
    )


def _group_nearby_highlights(
    highlights: list[HighlightScene],
    proximity_seconds: int = 60,
) -> list[list[HighlightScene]]:
    """近接するハイライトをグループ化する

    proximity_seconds秒以内のハイライトは同一グループとする。
    """
    if not highlights:
        return []

    groups = []
    current_group = [highlights[0]]

    for i in range(1, len(highlights)):
        prev_ts = _timestamp_to_seconds(current_group[-1].timestamp)
        curr_ts = _timestamp_to_seconds(highlights[i].timestamp)

        if curr_ts - prev_ts <= proximity_seconds:
            current_group.append(highlights[i])
        else:
            groups.append(current_group)
            current_group = [highlights[i]]

    groups.append(current_group)
    return groups


def _create_clip_segment(
    highlight_group: list[HighlightScene],
    video_data: VideoData,
) -> ClipSegment | None:
    """ハイライトグループからクリップセグメントを生成する"""
    if not highlight_group:
        return None

    # グループ内の時間範囲
    start_sec = _timestamp_to_seconds(highlight_group[0].timestamp) - PRE_BUFFER
    # 最後のハイライトの推定発言時間を考慮（1秒あたり約4文字）
    last_hl = highlight_group[-1]
    estimated_speech = max(5, len(last_hl.text) // 4)
    end_sec = _timestamp_to_seconds(last_hl.timestamp) + estimated_speech + POST_BUFFER
    start_sec = max(0, start_sec)

    # 最大長を超える場合は制限
    duration = end_sec - start_sec
    if duration > MAX_CLIP_DURATION:
        # 最も重要なハイライトを中心に切り出す
        best = _find_best_highlight(highlight_group)
        best_sec = _timestamp_to_seconds(best.timestamp)
        start_sec = max(0, best_sec - PRE_BUFFER)
        end_sec = start_sec + IDEAL_CLIP_DURATION
        duration = end_sec - start_sec
        # グループを再フィルタリング
        highlight_group = [
            h for h in highlight_group
            if start_sec <= _timestamp_to_seconds(h.timestamp) <= end_sec
        ]

    # 短すぎる場合はバッファを拡大
    if duration < MIN_CLIP_DURATION:
        extra = (MIN_CLIP_DURATION - duration) // 2
        start_sec = max(0, start_sec - extra)
        end_sec = end_sec + extra
        duration = end_sec - start_sec

    # クリップタイプの判定
    categories = [h.category for h in highlight_group]
    clip_type = _determine_clip_type(categories)

    # 優先度の判定
    priority = _determine_priority(highlight_group, clip_type)

    # タイトル案の生成
    title = _generate_clip_title(highlight_group, video_data)

    # フックテキスト（冒頭に出す文言）
    hook = _generate_hook_text(highlight_group)

    # 単体成立度スコア
    standalone_score = _calculate_standalone_score(
        highlight_group, duration, clip_type
    )

    return ClipSegment(
        start_ts=_seconds_to_timestamp(start_sec),
        end_ts=_seconds_to_timestamp(end_sec),
        duration_seconds=duration,
        title_suggestion=title,
        hook_text=hook,
        highlights=[h.timestamp for h in highlight_group],
        clip_type=clip_type,
        priority=priority,
        standalone_score=standalone_score,
    )


def _find_best_highlight(highlights: list[HighlightScene]) -> HighlightScene:
    """グループ内で最も重要なハイライトを選定"""
    priority_map = {cat: i for i, cat in enumerate(CLIP_WORTHY_CATEGORIES)}
    return min(
        highlights,
        key=lambda h: priority_map.get(h.category, 99)
    )


def _determine_clip_type(categories: list[str]) -> str:
    """カテゴリ群からクリップタイプを判定"""
    if "パンチライン" in categories:
        return "punchline"
    if "実績数字" in categories:
        return "achievement"
    if "メッセージ" in categories:
        return "message"
    if "TEKO価値" in categories:
        return "story"
    return "general"


def _determine_priority(
    highlights: list[HighlightScene],
    clip_type: str,
) -> str:
    """クリップの優先度を判定"""
    # パンチライン or 実績数字 が含まれる → high
    high_categories = {"パンチライン", "実績数字"}
    if any(h.category in high_categories for h in highlights):
        return "high"

    # 複数ハイライトが含まれる → medium
    if len(highlights) >= 2:
        return "medium"

    # メッセージ系 → medium
    if clip_type == "message":
        return "medium"

    return "low"


def _generate_clip_title(
    highlights: list[HighlightScene],
    video_data: VideoData,
) -> str:
    """切り抜きのタイトル案を生成"""
    guest_name = ""
    if video_data.profiles:
        guest_name = video_data.profiles[0].name

    # 最も重要なハイライトからタイトルを生成
    best = _find_best_highlight(highlights)

    # パンチラインはそのまま使える
    if best.category == "パンチライン":
        text = best.text.strip("「」")
        if len(text) > 30:
            text = text[:27] + "..."
        return f"【{guest_name}】{text}" if guest_name else text

    # 実績数字は数字をフック
    if best.category == "実績数字":
        numbers = re.findall(r"\d+万|年収\d+", best.text)
        if numbers:
            return f"【{guest_name}】{numbers[0]}の裏側" if guest_name else f"{numbers[0]}の裏側"

    # その他
    text = best.text[:20] if len(best.text) > 20 else best.text
    return f"【{guest_name}】{text}" if guest_name else text


def _generate_hook_text(highlights: list[HighlightScene]) -> str:
    """冒頭フック文言を生成（視聴者の注意を引く一言）"""
    best = _find_best_highlight(highlights)

    if best.category == "実績数字":
        numbers = re.findall(r"\d+万|年収\d+|月利?\d+万|月収?\d+万", best.text)
        if numbers:
            return f"衝撃の{numbers[0]}..."

    if best.category == "パンチライン":
        text = best.text.strip("「」")
        if len(text) > 40:
            text = text[:37] + "..."
        return f"「{text}」"

    if best.category == "メッセージ":
        return "ゲストが語る本音..."

    return best.text[:30] + "..." if len(best.text) > 30 else best.text


def _calculate_standalone_score(
    highlights: list[HighlightScene],
    duration: int,
    clip_type: str,
) -> float:
    """単体成立度スコア（0.0-1.0）を計算

    高スコアの条件:
    - 切り抜き向きカテゴリのハイライトが多い
    - 適切な長さ（30-60秒が最適）
    - パンチラインや実績数字が含まれる
    """
    score = 0.0

    # ハイライト数ボーナス（最大0.3）
    hl_count = min(len(highlights), 3)
    score += hl_count * 0.1

    # 長さの適切さ（最大0.3）
    if MIN_CLIP_DURATION <= duration <= MAX_CLIP_DURATION:
        # 30-60秒が最高スコア
        if 30 <= duration <= 60:
            score += 0.3
        else:
            score += 0.2
    else:
        score += 0.1

    # クリップタイプボーナス（最大0.4）
    type_scores = {
        "punchline": 0.4,
        "achievement": 0.35,
        "message": 0.25,
        "story": 0.2,
        "general": 0.1,
    }
    score += type_scores.get(clip_type, 0.1)

    return min(1.0, round(score, 2))


def _timestamp_to_seconds(ts: str) -> int:
    """タイムスタンプを秒数に変換"""
    parts = ts.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0


def _seconds_to_timestamp(seconds: int) -> str:
    """秒数をMM:SS形式に変換"""
    if seconds < 0:
        seconds = 0
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"
