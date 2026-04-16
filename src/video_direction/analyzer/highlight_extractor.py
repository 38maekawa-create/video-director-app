from __future__ import annotations
"""NEW-2: ハイライトカットポイント提案

target_labelerのシーン分類を活用し、各層の代表シーンを抽出する。
ハイライト使用シーンの最適カットポイントを提案する。

ロジック:
- target_labelerのtier1/tier2/both分類結果を受け取る
- 各層から代表シーン（インパクト最大）を抽出
- カットイン/カットアウトのタイミングを前後の文脈から推定
- ハイライト動画（リール等）用の最適シーン順序を提案
"""

import re
from dataclasses import dataclass, field
from ..integrations.ai_dev5_connector import VideoData, HighlightScene
from .target_labeler import TargetLabelResult, SceneLabel


# カテゴリ別の重要度（ハイライト動画での優先度）
CATEGORY_PRIORITY = {
    "実績数字": 5,
    "パンチライン": 4,
    "属性紹介": 3,
    "TEKO価値": 3,
    "メッセージ": 2,
}

# シーン前後のバッファ秒数
CUT_IN_BUFFER_SECONDS = 3  # カットイン前のバッファ
CUT_OUT_BUFFER_SECONDS = 5  # カットアウト後のバッファ

# ハイライト1シーンの推奨長さ
HIGHLIGHT_MIN_SECONDS = 10
HIGHLIGHT_MAX_SECONDS = 45
HIGHLIGHT_IDEAL_SECONDS = 20


@dataclass
class HighlightCutPoint:
    """ハイライトの最適カットポイント"""
    scene_index: int  # 元のハイライトシーンのインデックス
    timestamp: str  # 元のタイムスタンプ
    cut_in: str  # カットイン推奨タイムスタンプ "MM:SS"
    cut_out: str  # カットアウト推奨タイムスタンプ "MM:SS"
    estimated_duration: int  # 推定秒数
    speaker: str
    text_preview: str  # テキストプレビュー
    category: str  # ハイライトカテゴリ
    target_tier: str  # "tier1", "tier2", "both"
    tier_label: str  # "1層向け", "2層向け", "両層向け"
    priority_score: float  # 優先度スコア
    cut_reason: str  # カットポイント選定理由


@dataclass
class TierRepresentatives:
    """各層の代表シーン"""
    tier1_scenes: list = field(default_factory=list)  # List[HighlightCutPoint]
    tier2_scenes: list = field(default_factory=list)
    both_scenes: list = field(default_factory=list)


@dataclass
class HighlightSequence:
    """ハイライト動画用のシーン順序提案"""
    scenes: list = field(default_factory=list)  # List[HighlightCutPoint]
    total_duration: int = 0  # 推定合計秒数
    sequence_rationale: str = ""  # 順序選定の理由


@dataclass
class HighlightExtractorResult:
    """ハイライト抽出結果"""
    cut_points: list = field(default_factory=list)  # List[HighlightCutPoint]
    tier_representatives: TierRepresentatives = field(default_factory=TierRepresentatives)
    recommended_sequence: HighlightSequence = field(default_factory=HighlightSequence)
    analysis_summary: str = ""


def extract_highlights(
    video_data: VideoData,
    target_result: TargetLabelResult,
) -> HighlightExtractorResult:
    """ハイライトシーンの最適カットポイントを抽出する"""
    if not target_result.scenes:
        return HighlightExtractorResult(
            analysis_summary="ターゲットラベリング結果が空のため分析不可"
        )

    # トランスクリプトの行データ（カット前後の文脈推定用）
    transcript_timestamps = _extract_timestamps_from_transcript(
        video_data.full_transcript
    )

    # 各シーンのカットポイントを計算
    cut_points = []
    for i, scene in enumerate(target_result.scenes):
        # 対応するハイライトシーンを探す
        highlight = _find_matching_highlight(scene, video_data.highlights)
        cut_point = _calculate_cut_point(
            i, scene, highlight, transcript_timestamps
        )
        cut_points.append(cut_point)

    # 層別代表シーン抽出
    tier_reps = _extract_tier_representatives(cut_points)

    # 推奨シーン順序
    recommended = _build_recommended_sequence(cut_points, target_result)

    # サマリー
    summary = _generate_summary(cut_points, tier_reps, recommended)

    return HighlightExtractorResult(
        cut_points=cut_points,
        tier_representatives=tier_reps,
        recommended_sequence=recommended,
        analysis_summary=summary,
    )


def _extract_timestamps_from_transcript(transcript: str) -> list[int]:
    """トランスクリプトからタイムスタンプ一覧を抽出（秒数リスト）"""
    if not transcript:
        return []
    timestamps = []
    for match in re.finditer(r"\[?(\d{1,3}:\d{2})\]?", transcript):
        ts = match.group(1)
        seconds = _ts_to_seconds(ts)
        timestamps.append(seconds)
    return sorted(set(timestamps))


def _find_matching_highlight(
    scene: SceneLabel, highlights: list[HighlightScene]
) -> HighlightScene | None:
    """SceneLabelに対応するHighlightSceneを探す"""
    for h in highlights:
        if h.timestamp == scene.timestamp and h.speaker == scene.speaker:
            return h
    # タイムスタンプのみで再検索
    for h in highlights:
        if h.timestamp == scene.timestamp:
            return h
    return None


def _calculate_cut_point(
    index: int,
    scene: SceneLabel,
    highlight: HighlightScene | None,
    transcript_timestamps: list[int],
) -> HighlightCutPoint:
    """シーンの最適カットポイントを計算"""
    scene_seconds = _ts_to_seconds(scene.timestamp)
    category = highlight.category if highlight else ""

    # カットイン: シーンの少し前（文の開始を含む）
    cut_in_sec = max(0, scene_seconds - CUT_IN_BUFFER_SECONDS)

    # 前のタイムスタンプを探して、文の開始にスナップ
    prev_ts = _find_nearest_timestamp(
        transcript_timestamps, scene_seconds, direction="before"
    )
    if prev_ts is not None and (scene_seconds - prev_ts) <= 10:
        # 前のタイムスタンプが10秒以内なら、そこからカットイン
        cut_in_sec = prev_ts

    # カットアウト: シーンの後
    cut_out_sec = scene_seconds + HIGHLIGHT_IDEAL_SECONDS

    # 次のタイムスタンプを探して、文の終了にスナップ
    next_ts = _find_nearest_timestamp(
        transcript_timestamps, scene_seconds + HIGHLIGHT_IDEAL_SECONDS, direction="after"
    )
    if next_ts is not None and abs(next_ts - (scene_seconds + HIGHLIGHT_IDEAL_SECONDS)) <= 10:
        cut_out_sec = next_ts + CUT_OUT_BUFFER_SECONDS

    # 長すぎる場合は制限
    duration = cut_out_sec - cut_in_sec
    if duration > HIGHLIGHT_MAX_SECONDS:
        cut_out_sec = cut_in_sec + HIGHLIGHT_MAX_SECONDS

    # 短すぎる場合は延長
    duration = cut_out_sec - cut_in_sec
    if duration < HIGHLIGHT_MIN_SECONDS:
        cut_out_sec = cut_in_sec + HIGHLIGHT_MIN_SECONDS

    duration = cut_out_sec - cut_in_sec

    # 優先度スコア計算
    priority = _calc_priority_score(scene, category)

    # カットポイント選定理由
    cut_reason = _generate_cut_reason(scene, category, duration)

    return HighlightCutPoint(
        scene_index=index,
        timestamp=scene.timestamp,
        cut_in=_seconds_to_ts(cut_in_sec),
        cut_out=_seconds_to_ts(cut_out_sec),
        estimated_duration=duration,
        speaker=scene.speaker,
        text_preview=scene.text[:80] + ("..." if len(scene.text) > 80 else ""),
        category=category,
        target_tier=scene.target_tier,
        tier_label=scene.tier_label,
        priority_score=round(priority, 2),
        cut_reason=cut_reason,
    )


def _find_nearest_timestamp(
    timestamps: list[int], target: int, direction: str
) -> int | None:
    """指定方向で最も近いタイムスタンプを探す"""
    if not timestamps:
        return None

    if direction == "before":
        candidates = [ts for ts in timestamps if ts < target]
        return max(candidates) if candidates else None
    else:  # after
        candidates = [ts for ts in timestamps if ts > target]
        return min(candidates) if candidates else None


def _calc_priority_score(scene: SceneLabel, category: str) -> float:
    """優先度スコアを計算（0.0〜1.0）"""
    score = 0.0

    # カテゴリベースの優先度
    cat_priority = CATEGORY_PRIORITY.get(category, 1)
    score += cat_priority / 5.0 * 0.5  # 最大0.5

    # ターゲット層: bothは両方に使えるため優先度高
    if scene.target_tier == "both":
        score += 0.3
    elif scene.target_tier == "tier1":
        score += 0.2
    else:
        score += 0.15

    # テキストの長さ（短すぎず長すぎずが理想）
    text_len = len(scene.text)
    if 30 <= text_len <= 100:
        score += 0.2
    elif text_len > 100:
        score += 0.1

    return min(score, 1.0)


def _generate_cut_reason(scene: SceneLabel, category: str, duration: int) -> str:
    """カットポイント選定理由を生成"""
    reasons = []

    if category == "実績数字":
        reasons.append("実績数字の強調シーン")
    elif category == "パンチライン":
        reasons.append("インパクトのある発言")
    elif category == "属性紹介":
        reasons.append("ゲスト属性の紹介")
    elif category == "TEKO価値":
        reasons.append("TEKO価値の証言")
    elif category == "メッセージ":
        reasons.append("視聴者へのメッセージ")

    reasons.append(f"{scene.tier_label}（{scene.emotional_hook}）")
    reasons.append(f"推定{duration}秒")

    return "、".join(reasons)


def _extract_tier_representatives(
    cut_points: list[HighlightCutPoint],
) -> TierRepresentatives:
    """各層の代表シーンを抽出"""
    tier1 = sorted(
        [cp for cp in cut_points if cp.target_tier == "tier1"],
        key=lambda cp: cp.priority_score,
        reverse=True,
    )
    tier2 = sorted(
        [cp for cp in cut_points if cp.target_tier == "tier2"],
        key=lambda cp: cp.priority_score,
        reverse=True,
    )
    both = sorted(
        [cp for cp in cut_points if cp.target_tier == "both"],
        key=lambda cp: cp.priority_score,
        reverse=True,
    )

    return TierRepresentatives(
        tier1_scenes=tier1[:3],  # 上位3件
        tier2_scenes=tier2[:3],
        both_scenes=both[:3],
    )


def _build_recommended_sequence(
    cut_points: list[HighlightCutPoint],
    target_result: TargetLabelResult,
) -> HighlightSequence:
    """推奨シーン順序を構築"""
    if not cut_points:
        return HighlightSequence(sequence_rationale="カットポイントなし")

    # 優先度スコア順にソート
    sorted_points = sorted(
        cut_points,
        key=lambda cp: cp.priority_score,
        reverse=True,
    )

    # 上位シーンを選択（合計2分以内を目安）
    selected = []
    total_duration = 0
    MAX_TOTAL_SECONDS = 120  # ハイライト動画は2分以内

    for cp in sorted_points:
        if total_duration + cp.estimated_duration > MAX_TOTAL_SECONDS:
            continue
        selected.append(cp)
        total_duration += cp.estimated_duration
        if len(selected) >= 6:  # 最大6シーン
            break

    # タイムスタンプ順に並び替え（動画の流れに沿う）
    selected.sort(key=lambda cp: _ts_to_seconds(cp.timestamp))

    # 順序の理由
    tier1_count = sum(1 for s in selected if s.target_tier == "tier1")
    tier2_count = sum(1 for s in selected if s.target_tier == "tier2")
    both_count = sum(1 for s in selected if s.target_tier == "both")

    rationale = (
        f"{len(selected)}シーン選出（合計{total_duration}秒）。"
        f"1層向け{tier1_count}件、2層向け{tier2_count}件、両層{both_count}件。"
        f"タイムスタンプ順で動画の流れに沿った配列。"
    )

    return HighlightSequence(
        scenes=selected,
        total_duration=total_duration,
        sequence_rationale=rationale,
    )


def _generate_summary(
    cut_points: list[HighlightCutPoint],
    tier_reps: TierRepresentatives,
    recommended: HighlightSequence,
) -> str:
    """分析サマリーを生成"""
    total = len(cut_points)
    tier1 = sum(1 for cp in cut_points if cp.target_tier == "tier1")
    tier2 = sum(1 for cp in cut_points if cp.target_tier == "tier2")
    both = sum(1 for cp in cut_points if cp.target_tier == "both")

    summary = (
        f"全{total}シーンのカットポイントを分析。"
        f"1層向け{tier1}件、2層向け{tier2}件、両層向け{both}件。"
        f"推奨ハイライト構成: {len(recommended.scenes)}シーン（{recommended.total_duration}秒）。"
    )

    if tier_reps.tier1_scenes:
        top = tier_reps.tier1_scenes[0]
        summary += f" 1層代表シーン: [{top.timestamp}] {top.text_preview[:30]}。"

    if tier_reps.tier2_scenes:
        top = tier_reps.tier2_scenes[0]
        summary += f" 2層代表シーン: [{top.timestamp}] {top.text_preview[:30]}。"

    return summary


def _ts_to_seconds(ts: str) -> int:
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


def _seconds_to_ts(seconds: int) -> str:
    """秒数をMM:SS形式に変換"""
    m = seconds // 60
    s = seconds % 60
    return f"{m:02d}:{s:02d}"
