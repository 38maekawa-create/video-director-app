from __future__ import annotations
"""NEW-3: 編集後動画FB（フィードバック）生成

ディレクションレポート（期待）vs 編集結果（実際）の差分分析を行い、
テキストベースでの品質フィードバックを生成する。

ロジック:
- ディレクションレポートの演出指示（期待）を読み込む
- 編集結果データ（実際）を受け取る
- 期待 vs 実際の差分を分析
- 品質スコアリング（B-1基礎版）を内包
- フィードバックテキストを生成
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from ..integrations.ai_dev5_connector import VideoData
from ..analyzer.direction_generator import DirectionTimeline, DirectionEntry
from ..analyzer.target_labeler import TargetLabelResult
from ..analyzer.clip_cutter import ClipCutterResult


# 品質評価の7要素（テキストベースで評価可能な3要素を先行実装）
QUALITY_DIMENSIONS = {
    "tempo": {"name": "テンポ", "weight": 0.10, "text_evaluable": True},
    "composition": {"name": "構成力", "weight": 0.15, "text_evaluable": True},
    "content_density": {"name": "内容密度", "weight": 0.15, "text_evaluable": True},
    "cut_rhythm": {"name": "カット割り", "weight": 0.20, "text_evaluable": False},
    "color": {"name": "色彩", "weight": 0.20, "text_evaluable": False},
    "camera_work": {"name": "カメラワーク", "weight": 0.10, "text_evaluable": False},
    "framing": {"name": "構図", "weight": 0.10, "text_evaluable": False},
}


@dataclass
class EditedVideoData:
    """編集済み動画のメタ情報"""
    title: str = ""
    duration_seconds: int = 0  # 編集後の動画長さ
    original_duration_seconds: int = 0  # 元動画の長さ
    included_timestamps: list = field(default_factory=list)  # 採用されたタイムスタンプ ["MM:SS", ...]
    excluded_timestamps: list = field(default_factory=list)  # カットされたタイムスタンプ
    telop_texts: list = field(default_factory=list)  # 実際に使われたテロップテキスト
    scene_order: list = field(default_factory=list)  # シーンの並び順 ["MM:SS", ...]
    editor_name: str = ""  # 編集者名
    edit_date: str = ""  # 編集日


@dataclass
class QualityScore:
    """品質スコア"""
    dimension: str  # 評価次元名
    score: float  # 0.0〜10.0
    max_score: float = 10.0
    evaluable: bool = True  # テキストベースで評価可能か
    comment: str = ""  # スコアに対するコメント


@dataclass
class DirectionAdherence:
    """ディレクション準拠度"""
    total_directions: int = 0  # 指示総数
    followed_count: int = 0  # 準拠した指示数
    partially_followed: int = 0  # 部分準拠
    not_followed: int = 0  # 未準拠
    adherence_rate: float = 0.0  # 準拠率
    details: list = field(default_factory=list)  # 各指示の準拠詳細


@dataclass
class DirectionDetail:
    """各ディレクション指示の準拠詳細"""
    timestamp: str
    instruction: str
    status: str  # "followed", "partial", "not_followed", "unknown"
    comment: str = ""


@dataclass
class SceneSelectionAnalysis:
    """シーン取捨選択分析"""
    total_highlights: int = 0
    included_highlights: int = 0
    excluded_highlights: int = 0
    inclusion_rate: float = 0.0
    key_included: list = field(default_factory=list)  # 重要な採用シーン
    key_excluded: list = field(default_factory=list)  # 重要なカットシーン
    analysis_comment: str = ""


@dataclass
class FeedbackItem:
    """フィードバック項目"""
    category: str  # "positive", "improvement", "critical"
    area: str  # フィードバック対象領域
    message: str  # フィードバック内容
    priority: str = "medium"  # "high", "medium", "low"


@dataclass
class PostEditFeedback:
    """編集後フィードバック結果"""
    # 品質スコア
    quality_scores: list = field(default_factory=list)  # List[QualityScore]
    overall_score: float = 0.0  # 総合スコア
    overall_grade: str = ""  # A/B/C/D/E

    # ディレクション準拠度
    direction_adherence: DirectionAdherence = field(default_factory=DirectionAdherence)

    # シーン取捨選択
    scene_selection: SceneSelectionAnalysis = field(default_factory=SceneSelectionAnalysis)

    # フィードバック
    feedback_items: list = field(default_factory=list)  # List[FeedbackItem]

    # サマリー
    summary: str = ""
    generated_at: str = ""


def generate_feedback(
    video_data: VideoData,
    direction_timeline: DirectionTimeline,
    target_result: TargetLabelResult,
    edited_data: EditedVideoData,
    clip_result: ClipCutterResult | None = None,
) -> PostEditFeedback:
    """編集後フィードバックを生成する"""

    # 品質スコアリング
    quality_scores = _evaluate_quality(video_data, edited_data)
    overall_score = _calc_overall_score(quality_scores)
    overall_grade = _score_to_grade(overall_score)

    # ディレクション準拠度
    adherence = _evaluate_direction_adherence(
        direction_timeline, edited_data
    )

    # シーン取捨選択分析
    scene_selection = _analyze_scene_selection(
        video_data, target_result, edited_data
    )

    # フィードバック生成
    feedback_items = _generate_feedback_items(
        quality_scores, adherence, scene_selection, edited_data
    )

    # サマリー
    summary = _generate_summary(
        overall_score, overall_grade, adherence, scene_selection, feedback_items
    )

    return PostEditFeedback(
        quality_scores=quality_scores,
        overall_score=round(overall_score, 1),
        overall_grade=overall_grade,
        direction_adherence=adherence,
        scene_selection=scene_selection,
        feedback_items=feedback_items,
        summary=summary,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def _evaluate_quality(
    video_data: VideoData,
    edited_data: EditedVideoData,
) -> list[QualityScore]:
    """品質スコアリング（テキストベースで評価可能な3要素）"""
    scores = []

    # テンポ: 編集前後の比率で評価
    tempo_score = _evaluate_tempo(video_data, edited_data)
    scores.append(tempo_score)

    # 構成力: シーン順序の論理性
    composition_score = _evaluate_composition(video_data, edited_data)
    scores.append(composition_score)

    # 内容密度: ハイライトの採用率
    density_score = _evaluate_content_density(video_data, edited_data)
    scores.append(density_score)

    # テキストベース評価不可の4要素（プレースホルダ）
    for key, dim in QUALITY_DIMENSIONS.items():
        if not dim["text_evaluable"]:
            scores.append(QualityScore(
                dimension=dim["name"],
                score=0.0,
                evaluable=False,
                comment="映像フレーム分析（Phase 2 Tier 3）で評価予定",
            ))

    return scores


def _evaluate_tempo(
    video_data: VideoData,
    edited_data: EditedVideoData,
) -> QualityScore:
    """テンポ評価"""
    if edited_data.original_duration_seconds == 0 or edited_data.duration_seconds == 0:
        return QualityScore(
            dimension="テンポ",
            score=5.0,
            comment="動画長さの情報不足のためデフォルトスコア",
        )

    # 圧縮率: 理想は40-60%
    compression = edited_data.duration_seconds / edited_data.original_duration_seconds
    if 0.3 <= compression <= 0.6:
        score = 8.0 + (0.5 - abs(compression - 0.5)) * 4
        comment = f"圧縮率{compression:.0%}（適切な編集テンポ）"
    elif compression < 0.3:
        score = 5.0
        comment = f"圧縮率{compression:.0%}（カットしすぎの可能性。重要シーンが含まれているか確認）"
    elif compression > 0.8:
        score = 4.0
        comment = f"圧縮率{compression:.0%}（編集が少ない。冗長部分のカットを検討）"
    else:
        score = 6.0
        comment = f"圧縮率{compression:.0%}"

    return QualityScore(
        dimension="テンポ",
        score=min(score, 10.0),
        comment=comment,
    )


def _evaluate_composition(
    video_data: VideoData,
    edited_data: EditedVideoData,
) -> QualityScore:
    """構成力評価"""
    if not edited_data.scene_order:
        return QualityScore(
            dimension="構成力",
            score=5.0,
            comment="シーン順序情報なしのためデフォルトスコア",
        )

    # シーン順序が時系列に沿っているか
    scene_seconds = [_ts_to_seconds(ts) for ts in edited_data.scene_order]
    is_chronological = all(
        scene_seconds[i] <= scene_seconds[i + 1]
        for i in range(len(scene_seconds) - 1)
    )

    score = 6.0
    comments = []

    if is_chronological:
        score += 2.0
        comments.append("時系列順の構成")
    else:
        # 並び替えがある場合、意図的な再構成の可能性
        score += 1.0
        comments.append("非時系列の構成（意図的な再構成の可能性）")

    # シーン数の適切さ（多すぎず少なすぎず）
    scene_count = len(edited_data.scene_order)
    duration_min = edited_data.duration_seconds / 60 if edited_data.duration_seconds else 5
    scenes_per_min = scene_count / max(duration_min, 1)

    if 1 <= scenes_per_min <= 4:
        score += 1.0
        comments.append(f"シーン密度{scenes_per_min:.1f}/分（適切）")
    elif scenes_per_min > 4:
        comments.append(f"シーン密度{scenes_per_min:.1f}/分（やや多い）")
    else:
        comments.append(f"シーン密度{scenes_per_min:.1f}/分（やや少ない）")

    return QualityScore(
        dimension="構成力",
        score=min(score, 10.0),
        comment="。".join(comments),
    )


def _evaluate_content_density(
    video_data: VideoData,
    edited_data: EditedVideoData,
) -> QualityScore:
    """内容密度評価"""
    total_highlights = len(video_data.highlights)
    if total_highlights == 0:
        return QualityScore(
            dimension="内容密度",
            score=5.0,
            comment="ハイライト情報なしのためデフォルトスコア",
        )

    # ハイライトの採用率
    included = _count_included_highlights(
        video_data.highlights, edited_data.included_timestamps
    )
    rate = included / total_highlights

    if rate >= 0.7:
        score = 8.0 + rate * 2
        comment = f"ハイライト採用率{rate:.0%}（高密度）"
    elif rate >= 0.4:
        score = 6.0 + rate * 4
        comment = f"ハイライト採用率{rate:.0%}（適切）"
    else:
        score = 4.0 + rate * 4
        comment = f"ハイライト採用率{rate:.0%}（重要シーンの見落としの可能性）"

    return QualityScore(
        dimension="内容密度",
        score=min(score, 10.0),
        comment=comment,
    )


def _calc_overall_score(scores: list[QualityScore]) -> float:
    """総合スコア計算（評価可能な要素のみで加重平均）"""
    evaluable = [s for s in scores if s.evaluable]
    if not evaluable:
        return 5.0

    total_weight = 0
    weighted_sum = 0
    for s in evaluable:
        for key, dim in QUALITY_DIMENSIONS.items():
            if dim["name"] == s.dimension:
                weighted_sum += s.score * dim["weight"]
                total_weight += dim["weight"]
                break

    if total_weight == 0:
        return 5.0

    # 評価可能な要素のウェイトで正規化
    return weighted_sum / total_weight


def _score_to_grade(score: float) -> str:
    """スコアをグレードに変換"""
    if score >= 9.0:
        return "A+"
    elif score >= 8.0:
        return "A"
    elif score >= 7.0:
        return "B+"
    elif score >= 6.0:
        return "B"
    elif score >= 5.0:
        return "C"
    elif score >= 4.0:
        return "D"
    else:
        return "E"


def _evaluate_direction_adherence(
    timeline: DirectionTimeline,
    edited_data: EditedVideoData,
) -> DirectionAdherence:
    """ディレクション準拠度を評価"""
    if not timeline.entries:
        return DirectionAdherence()

    included_seconds = set()
    for ts in edited_data.included_timestamps:
        included_seconds.add(_ts_to_seconds(ts))

    details = []
    followed = 0
    partial = 0
    not_followed = 0

    for entry in timeline.entries:
        entry_seconds = _ts_to_seconds(entry.timestamp)

        # そのタイムスタンプのシーンが採用されているか
        is_included = any(
            abs(entry_seconds - inc_sec) <= 10
            for inc_sec in included_seconds
        )

        if is_included:
            if edited_data.telop_texts and entry.direction_type == "telop":
                # テロップ指示がある場合、テロップが実装されているか
                telop_match = any(
                    _text_similarity(entry.instruction, telop) > 0.3
                    for telop in edited_data.telop_texts
                )
                if telop_match:
                    status = "followed"
                    followed += 1
                else:
                    status = "partial"
                    partial += 1
            else:
                status = "followed"
                followed += 1
        else:
            # シーン自体がカットされている
            if entry.priority == "high":
                status = "not_followed"
                not_followed += 1
            else:
                status = "partial"  # 低優先度はpartialとして扱う
                partial += 1

        details.append(DirectionDetail(
            timestamp=entry.timestamp,
            instruction=entry.instruction[:80],
            status=status,
            comment=f"シーン{'採用' if is_included else '未採用'}",
        ))

    total = len(timeline.entries)
    adherence_rate = (followed + partial * 0.5) / total if total > 0 else 0

    return DirectionAdherence(
        total_directions=total,
        followed_count=followed,
        partially_followed=partial,
        not_followed=not_followed,
        adherence_rate=round(adherence_rate, 2),
        details=details,
    )


def _analyze_scene_selection(
    video_data: VideoData,
    target_result: TargetLabelResult,
    edited_data: EditedVideoData,
) -> SceneSelectionAnalysis:
    """シーン取捨選択を分析"""
    total = len(video_data.highlights)
    if total == 0:
        return SceneSelectionAnalysis()

    included_seconds = set()
    for ts in edited_data.included_timestamps:
        included_seconds.add(_ts_to_seconds(ts))

    included_count = 0
    excluded_count = 0
    key_included = []
    key_excluded = []

    for i, highlight in enumerate(video_data.highlights):
        h_seconds = _ts_to_seconds(highlight.timestamp)
        is_included = any(
            abs(h_seconds - inc_sec) <= 10
            for inc_sec in included_seconds
        )

        if is_included:
            included_count += 1
            if highlight.category in ("実績数字", "パンチライン"):
                key_included.append(
                    f"[{highlight.timestamp}] {highlight.category}: {highlight.text[:50]}"
                )
        else:
            excluded_count += 1
            if highlight.category in ("実績数字", "パンチライン"):
                key_excluded.append(
                    f"[{highlight.timestamp}] {highlight.category}: {highlight.text[:50]}"
                )

    rate = included_count / total if total > 0 else 0

    # 分析コメント
    if key_excluded:
        comment = (
            f"重要シーン（実績数字・パンチライン）のうち{len(key_excluded)}件がカットされています。"
            "意図的なカットか確認してください。"
        )
    elif rate >= 0.7:
        comment = "主要なハイライトシーンが網羅されています。"
    else:
        comment = f"ハイライト採用率{rate:.0%}。追加で採用を検討すべきシーンがあります。"

    return SceneSelectionAnalysis(
        total_highlights=total,
        included_highlights=included_count,
        excluded_highlights=excluded_count,
        inclusion_rate=round(rate, 2),
        key_included=key_included,
        key_excluded=key_excluded,
        analysis_comment=comment,
    )


def _generate_feedback_items(
    quality_scores: list[QualityScore],
    adherence: DirectionAdherence,
    scene_selection: SceneSelectionAnalysis,
    edited_data: EditedVideoData,
) -> list[FeedbackItem]:
    """フィードバック項目を生成"""
    items = []

    # 品質スコアベースのフィードバック
    for qs in quality_scores:
        if not qs.evaluable:
            continue
        if qs.score >= 8.0:
            items.append(FeedbackItem(
                category="positive",
                area=qs.dimension,
                message=f"{qs.dimension}: {qs.comment}",
                priority="low",
            ))
        elif qs.score < 5.0:
            items.append(FeedbackItem(
                category="critical",
                area=qs.dimension,
                message=f"{qs.dimension}: {qs.comment}（改善推奨）",
                priority="high",
            ))
        elif qs.score < 7.0:
            items.append(FeedbackItem(
                category="improvement",
                area=qs.dimension,
                message=f"{qs.dimension}: {qs.comment}",
                priority="medium",
            ))

    # ディレクション準拠度フィードバック
    if adherence.adherence_rate >= 0.8:
        items.append(FeedbackItem(
            category="positive",
            area="ディレクション準拠",
            message=f"ディレクション準拠率{adherence.adherence_rate:.0%}（高い準拠度）",
            priority="low",
        ))
    elif adherence.not_followed > 0:
        items.append(FeedbackItem(
            category="improvement",
            area="ディレクション準拠",
            message=f"未準拠のディレクション指示が{adherence.not_followed}件あります（高優先度シーンを確認）",
            priority="high",
        ))

    # シーン取捨選択フィードバック
    if scene_selection.key_excluded:
        items.append(FeedbackItem(
            category="improvement",
            area="シーン選択",
            message=f"重要シーン{len(scene_selection.key_excluded)}件がカットされています。意図確認推奨。",
            priority="high",
        ))
    elif scene_selection.inclusion_rate >= 0.7:
        items.append(FeedbackItem(
            category="positive",
            area="シーン選択",
            message="主要ハイライトが適切に網羅されています。",
            priority="low",
        ))

    return items


def _generate_summary(
    overall_score: float,
    grade: str,
    adherence: DirectionAdherence,
    scene_selection: SceneSelectionAnalysis,
    feedback_items: list[FeedbackItem],
) -> str:
    """サマリーテキストを生成"""
    critical_count = sum(1 for f in feedback_items if f.category == "critical")
    improvement_count = sum(1 for f in feedback_items if f.category == "improvement")
    positive_count = sum(1 for f in feedback_items if f.category == "positive")

    summary = f"総合評価: {grade}（{overall_score}/10.0）。"

    if critical_count:
        summary += f" 要改善{critical_count}件。"
    if improvement_count:
        summary += f" 改善推奨{improvement_count}件。"
    if positive_count:
        summary += f" 良好{positive_count}件。"

    summary += f" ディレクション準拠率: {adherence.adherence_rate:.0%}。"
    summary += f" ハイライト採用率: {scene_selection.inclusion_rate:.0%}。"

    return summary


def _count_included_highlights(highlights, included_timestamps):
    """ハイライトのうち含まれるものをカウント"""
    included_seconds = set()
    for ts in included_timestamps:
        included_seconds.add(_ts_to_seconds(ts))

    count = 0
    for h in highlights:
        h_sec = _ts_to_seconds(h.timestamp)
        if any(abs(h_sec - inc) <= 10 for inc in included_seconds):
            count += 1
    return count


def _text_similarity(text1: str, text2: str) -> float:
    """簡易的なテキスト類似度（共通文字の割合）"""
    if not text1 or not text2:
        return 0.0
    set1 = set(text1)
    set2 = set(text2)
    intersection = set1 & set2
    union = set1 | set2
    return len(intersection) / len(union) if union else 0.0


def _ts_to_seconds(ts: str) -> int:
    """タイムスタンプを秒数に変換"""
    try:
        parts = ts.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except (ValueError, AttributeError):
        pass
    return 0
