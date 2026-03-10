from __future__ import annotations
"""B-1: 7要素品質スコアリング

カット割り（20%）、色彩（20%）、テロップ（15%）、BGM（15%）、
カメラワーク（10%）、構図（10%）、テンポ（10%）を各0-100点で数値化する。

Phase 2の初期実装は文字起こし・ハイライトデータからの推定スコアリング。
映像フレーム解析（C-1）はPhase 3以降で追加する。
"""

from dataclasses import dataclass, field
from ..integrations.ai_dev5_connector import VideoData, HighlightScene
from .guest_classifier import ClassificationResult
from .direction_generator import DirectionTimeline


# 7要素の重み（合計100%）
QUALITY_WEIGHTS = {
    "cut": 0.20,       # カット割り
    "color": 0.20,     # 色彩
    "telop": 0.15,     # テロップ
    "bgm": 0.15,       # BGM
    "camera": 0.10,    # カメラワーク
    "composition": 0.10,  # 構図
    "tempo": 0.10,     # テンポ
}

QUALITY_LABELS = {
    "cut": "カット割り",
    "color": "色彩",
    "telop": "テロップ",
    "bgm": "BGM",
    "camera": "カメラワーク",
    "composition": "構図",
    "tempo": "テンポ",
}


@dataclass
class QualityDimension:
    """品質の1次元"""
    key: str  # "cut", "color", "telop", "bgm", "camera", "composition", "tempo"
    label: str
    score: int  # 0-100
    weight: float
    weighted_score: float  # score * weight
    notes: list = field(default_factory=list)  # 評価根拠・改善提案


@dataclass
class QualityScoreResult:
    """品質スコアリング結果"""
    dimensions: list = field(default_factory=list)  # List[QualityDimension]
    total_score: float = 0.0  # 加重平均（0-100）
    grade: str = ""  # "S" / "A" / "B" / "C" / "D"
    improvement_areas: list = field(default_factory=list)  # 改善すべき領域
    strengths: list = field(default_factory=list)  # 強みの領域
    is_estimated: bool = True  # 推定値か実測値か


def score_video_quality(
    video_data: VideoData,
    classification: ClassificationResult | None = None,
    direction_timeline: DirectionTimeline | None = None,
) -> QualityScoreResult:
    """動画の品質をスコアリングする

    Phase 2初期実装: 文字起こし・メタデータからの推定スコアリング
    Phase 3以降: 映像フレーム解析による実測スコアリングを追加

    Args:
        video_data: パース済みのVideoData
        classification: ゲスト分類結果（任意）
        direction_timeline: 演出ディレクション（任意）

    Returns:
        QualityScoreResult: 品質スコアリング結果
    """
    dimensions = []

    # 各次元のスコアを計算
    dimensions.append(_score_cut(video_data, direction_timeline))
    dimensions.append(_score_color(video_data, direction_timeline))
    dimensions.append(_score_telop(video_data, classification))
    dimensions.append(_score_bgm(video_data))
    dimensions.append(_score_camera(video_data, direction_timeline))
    dimensions.append(_score_composition(video_data))
    dimensions.append(_score_tempo(video_data))

    # 加重平均
    total = sum(d.weighted_score for d in dimensions)
    total = round(total, 1)

    # グレード判定
    grade = _determine_grade(total)

    # 改善領域と強み
    sorted_dims = sorted(dimensions, key=lambda d: d.score)
    improvement_areas = [
        f"{d.label}（{d.score}点）: {d.notes[0]}" if d.notes else f"{d.label}（{d.score}点）"
        for d in sorted_dims[:2]
    ]
    strengths = [
        f"{d.label}（{d.score}点）" for d in sorted_dims[-2:]
    ]

    return QualityScoreResult(
        dimensions=dimensions,
        total_score=total,
        grade=grade,
        improvement_areas=improvement_areas,
        strengths=strengths,
        is_estimated=True,
    )


def _score_cut(
    video_data: VideoData,
    direction_timeline: DirectionTimeline | None,
) -> QualityDimension:
    """カット割りスコア（推定）

    評価基準:
    - ハイライトシーンの分布（均等に散らばっているか）
    - 演出指示の画角変更数
    """
    score = 50  # ベースライン
    notes = []

    if video_data.highlights:
        hl_count = len(video_data.highlights)
        if hl_count >= 8:
            score += 20
            notes.append(f"ハイライト{hl_count}件: 素材が豊富")
        elif hl_count >= 4:
            score += 10
            notes.append(f"ハイライト{hl_count}件: 適度な密度")
        else:
            notes.append(f"ハイライト{hl_count}件: カットポイントが少ない可能性")

        # 時間的な分布をチェック
        spread_bonus = _check_temporal_spread(video_data.highlights)
        score += spread_bonus
        if spread_bonus > 0:
            notes.append("時間的に均等に分散")
        else:
            notes.append("特定の時間帯にシーンが集中")

    if direction_timeline:
        camera_entries = [
            e for e in direction_timeline.entries
            if e.direction_type == "camera"
        ]
        if len(camera_entries) >= 5:
            score += 10
        elif len(camera_entries) >= 3:
            score += 5

    score = min(100, max(0, score))
    weight = QUALITY_WEIGHTS["cut"]

    return QualityDimension(
        key="cut",
        label=QUALITY_LABELS["cut"],
        score=score,
        weight=weight,
        weighted_score=round(score * weight, 1),
        notes=notes,
    )


def _score_color(
    video_data: VideoData,
    direction_timeline: DirectionTimeline | None,
) -> QualityDimension:
    """色彩スコア（推定）

    Phase 2: 色変え演出指示の数で推定
    Phase 3: 実際のフレーム画像から色彩分析
    """
    score = 50  # ベースライン（実映像分析なしのため）
    notes = ["Phase 2推定値: 実映像分析は未実施"]

    if direction_timeline:
        color_entries = [
            e for e in direction_timeline.entries
            if e.direction_type == "color"
        ]
        if len(color_entries) >= 3:
            score += 15
            notes.append(f"色変え演出{len(color_entries)}件: 視覚的変化が豊富")
        elif len(color_entries) >= 1:
            score += 5
            notes.append(f"色変え演出{len(color_entries)}件: 基本的な色変えあり")

    score = min(100, max(0, score))
    weight = QUALITY_WEIGHTS["color"]

    return QualityDimension(
        key="color",
        label=QUALITY_LABELS["color"],
        score=score,
        weight=weight,
        weighted_score=round(score * weight, 1),
        notes=notes,
    )


def _score_telop(
    video_data: VideoData,
    classification: ClassificationResult | None,
) -> QualityDimension:
    """テロップスコア（推定）

    評価基準:
    - テロップが必要なシーン（実績数字、パンチライン）の数
    - ゲスト分類に応じた適切なテロップ量
    """
    score = 50
    notes = []

    telop_candidates = [
        h for h in video_data.highlights
        if h.category in ("実績数字", "パンチライン", "属性紹介")
    ]

    if len(telop_candidates) >= 6:
        score += 25
        notes.append(f"テロップ候補{len(telop_candidates)}件: 豊富な強調ポイント")
    elif len(telop_candidates) >= 3:
        score += 15
        notes.append(f"テロップ候補{len(telop_candidates)}件: 適度な量")
    elif len(telop_candidates) >= 1:
        score += 5
        notes.append(f"テロップ候補{len(telop_candidates)}件: テロップが少なめ")
    else:
        notes.append("テロップ候補なし: 強調すべきシーンが不足")

    # 層aのゲストは数字テロップが重要
    if classification and classification.tier == "a":
        number_scenes = [h for h in telop_candidates if h.category == "実績数字"]
        if number_scenes:
            score += 10
            notes.append("層a向け数字テロップ素材あり")

    score = min(100, max(0, score))
    weight = QUALITY_WEIGHTS["telop"]

    return QualityDimension(
        key="telop",
        label=QUALITY_LABELS["telop"],
        score=score,
        weight=weight,
        weighted_score=round(score * weight, 1),
        notes=notes,
    )


def _score_bgm(video_data: VideoData) -> QualityDimension:
    """BGMスコア（推定）

    Phase 2: 動画時間と構造から推定
    Phase 3: 実際の音声解析で評価
    """
    score = 50
    notes = ["Phase 2推定値: 実音声分析は未実施"]

    # 動画時間が取得できている → 基本的な構造が把握可能
    if video_data.duration:
        score += 5
        notes.append("動画時間情報あり")

    score = min(100, max(0, score))
    weight = QUALITY_WEIGHTS["bgm"]

    return QualityDimension(
        key="bgm",
        label=QUALITY_LABELS["bgm"],
        score=score,
        weight=weight,
        weighted_score=round(score * weight, 1),
        notes=notes,
    )


def _score_camera(
    video_data: VideoData,
    direction_timeline: DirectionTimeline | None,
) -> QualityDimension:
    """カメラワークスコア（推定）

    評価基準:
    - 画角変更指示の数
    - 寄り/引きのバランス
    """
    score = 50
    notes = []

    if direction_timeline:
        camera_entries = [
            e for e in direction_timeline.entries
            if e.direction_type == "camera"
        ]
        if len(camera_entries) >= 5:
            score += 20
            notes.append(f"画角変更{len(camera_entries)}件: カメラワークの変化が豊富")
        elif len(camera_entries) >= 2:
            score += 10
            notes.append(f"画角変更{len(camera_entries)}件: 基本的な画角変更あり")
        else:
            notes.append("画角変更が少ない: 単調になる可能性")
    else:
        notes.append("演出指示なし: カメラワーク評価不可")

    score = min(100, max(0, score))
    weight = QUALITY_WEIGHTS["camera"]

    return QualityDimension(
        key="camera",
        label=QUALITY_LABELS["camera"],
        score=score,
        weight=weight,
        weighted_score=round(score * weight, 1),
        notes=notes,
    )


def _score_composition(video_data: VideoData) -> QualityDimension:
    """構図スコア（推定）

    Phase 2: メタ情報からの推定
    Phase 3: 実際のフレーム画像から構図分析
    """
    score = 50
    notes = ["Phase 2推定値: 実映像分析は未実施"]

    # 話者が2名（ホスト+ゲスト） → インタビュー構図
    if video_data.speakers:
        speaker_count = len(video_data.speakers.split(",")) if "," in video_data.speakers else 1
        if speaker_count == 2:
            score += 10
            notes.append("2名対談: インタビュー構図の活用が可能")

    score = min(100, max(0, score))
    weight = QUALITY_WEIGHTS["composition"]

    return QualityDimension(
        key="composition",
        label=QUALITY_LABELS["composition"],
        score=score,
        weight=weight,
        weighted_score=round(score * weight, 1),
        notes=notes,
    )


def _score_tempo(video_data: VideoData) -> QualityDimension:
    """テンポスコア（推定）

    評価基準:
    - ハイライトシーンの密度（動画時間あたりのハイライト数）
    - トピックの多様性
    """
    score = 50
    notes = []

    # ハイライト密度
    duration_min = _parse_duration_minutes(video_data.duration)
    hl_count = len(video_data.highlights)

    if duration_min > 0 and hl_count > 0:
        density = hl_count / duration_min  # ハイライト/分
        if density >= 0.5:
            score += 20
            notes.append(f"ハイライト密度: {density:.1f}/分（高密度・テンポ良好）")
        elif density >= 0.2:
            score += 10
            notes.append(f"ハイライト密度: {density:.1f}/分（適度なテンポ）")
        else:
            notes.append(f"ハイライト密度: {density:.1f}/分（テンポが遅い可能性）")

    # トピックの多様性
    topic_count = len(video_data.main_topics)
    if topic_count >= 4:
        score += 10
        notes.append(f"トピック{topic_count}件: 話題が豊富")
    elif topic_count >= 2:
        score += 5

    score = min(100, max(0, score))
    weight = QUALITY_WEIGHTS["tempo"]

    return QualityDimension(
        key="tempo",
        label=QUALITY_LABELS["tempo"],
        score=score,
        weight=weight,
        weighted_score=round(score * weight, 1),
        notes=notes,
    )


def _check_temporal_spread(highlights: list[HighlightScene]) -> int:
    """ハイライトの時間的分散度をチェック（ボーナスポイントを返す）"""
    if len(highlights) < 2:
        return 0

    timestamps = sorted([_timestamp_to_seconds(h.timestamp) for h in highlights])
    total_range = timestamps[-1] - timestamps[0]
    if total_range == 0:
        return 0

    # 各ハイライト間の間隔を計算
    intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
    avg_interval = sum(intervals) / len(intervals)

    # 間隔のばらつき（変動係数）
    if avg_interval > 0:
        variance = sum((iv - avg_interval)**2 for iv in intervals) / len(intervals)
        cv = (variance ** 0.5) / avg_interval  # 変動係数
        # CV が小さい（均等に分散）ほど高スコア
        if cv < 0.5:
            return 15
        elif cv < 1.0:
            return 10
        else:
            return 0
    return 0


def _determine_grade(total_score: float) -> str:
    """スコアからグレードを判定"""
    if total_score >= 90:
        return "S"
    elif total_score >= 80:
        return "A"
    elif total_score >= 65:
        return "B"
    elif total_score >= 50:
        return "C"
    else:
        return "D"


def _parse_duration_minutes(duration_str: str) -> float:
    """動画時間文字列を分数に変換"""
    if not duration_str:
        return 0

    import re
    # "XX分" パターン
    m = re.search(r"(\d+)\s*分", duration_str)
    if m:
        minutes = float(m.group(1))
        # 秒の追加
        s = re.search(r"(\d+)\s*秒", duration_str)
        if s:
            minutes += float(s.group(1)) / 60
        return minutes

    # "HH:MM:SS" or "MM:SS" パターン
    m = re.match(r"(\d+):(\d+)(?::(\d+))?", duration_str)
    if m:
        if m.group(3):  # HH:MM:SS
            return float(m.group(1)) * 60 + float(m.group(2)) + float(m.group(3)) / 60
        else:  # MM:SS
            return float(m.group(1)) + float(m.group(2)) / 60

    return 0


def _timestamp_to_seconds(ts: str) -> int:
    """タイムスタンプを秒数に変換"""
    parts = ts.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0
