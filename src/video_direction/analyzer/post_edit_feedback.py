from __future__ import annotations
"""NEW-3: 編集後動画フィードバック

編集済み動画に対して以下を生成:
1. 映像品質管理（B-1基準でのスコアリング）
2. 取捨選択された内容へのフィードバック（含めるべきシーンが含まれているか等）
3. テロップ誤字チェック

Phase 2: 編集前の文字起こしデータと編集後のメタデータを比較する形で
フィードバックを生成する。実映像の解析はPhase 3以降。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..integrations.ai_dev5_connector import VideoData, HighlightScene
from .quality_scorer import QualityScoreResult, score_video_quality
from .guest_classifier import ClassificationResult, classify_guest
from .direction_generator import DirectionTimeline, generate_directions
from .income_evaluator import evaluate_income
from .telop_checker import TelopCheckResult, check_telops


@dataclass
class ContentFeedbackItem:
    """コンテンツに関するフィードバック1件"""
    category: str  # "included" / "missing" / "order" / "emphasis"
    severity: str  # "good" / "warning" / "suggestion"
    description: str
    timestamp: str = ""  # 関連するタイムスタンプ
    highlight_text: str = ""  # 対象のハイライトテキスト


@dataclass
class EditFeedbackResult:
    """編集後フィードバックの全体結果"""
    # 品質スコア
    quality_score: Optional[QualityScoreResult] = None

    # コンテンツフィードバック
    content_feedback: list = field(default_factory=list)  # List[ContentFeedbackItem]

    # テロップチェック
    telop_check: Optional[TelopCheckResult] = None

    # サマリー
    total_issues: int = 0
    good_points: int = 0
    warnings: int = 0
    suggestions: int = 0

    # メタ情報
    video_id: str = ""
    guest_name: str = ""
    editor: str = ""
    stage: str = ""  # "draft" / "revision_1" / "revision_2" / "final"
    feedback_timestamp: str = ""
    is_estimated: bool = True


def generate_post_edit_feedback(
    original_video_data: VideoData,
    edited_video_data: Optional[VideoData] = None,
    included_timestamps: list = None,
    excluded_timestamps: list = None,
    editor: str = "",
    stage: str = "draft",
) -> EditFeedbackResult:
    """編集後動画のフィードバックを生成する

    Args:
        original_video_data: 編集前の元動画データ
        edited_video_data: 編集後の動画データ（Phase 3以降）
        included_timestamps: 編集で残されたシーンのタイムスタンプリスト
        excluded_timestamps: 編集で除外されたシーンのタイムスタンプリスト
        editor: 担当編集者
        stage: 編集段階

    Returns:
        EditFeedbackResult: フィードバック結果
    """
    now = datetime.now().isoformat()
    guest_name = (
        original_video_data.profiles[0].name
        if original_video_data.profiles else "不明"
    )

    # Step 1: 品質スコアリング（B-1基準）
    classification = classify_guest(original_video_data)
    income_eval = evaluate_income(original_video_data)
    direction_timeline = generate_directions(
        original_video_data, classification, income_eval
    )
    quality_score = score_video_quality(
        original_video_data, classification, direction_timeline
    )

    # Step 2: コンテンツフィードバック
    content_feedback = _generate_content_feedback(
        original_video_data,
        classification,
        included_timestamps or [],
        excluded_timestamps or [],
    )

    # Step 3: テロップチェック
    telop_check = check_telops(original_video_data, direction_timeline)

    # Step 4: サマリー集計
    good_count = sum(1 for f in content_feedback if f.severity == "good")
    warning_count = sum(1 for f in content_feedback if f.severity == "warning")
    suggestion_count = sum(1 for f in content_feedback if f.severity == "suggestion")
    total_issues = warning_count + suggestion_count + telop_check.error_count + telop_check.warning_count

    return EditFeedbackResult(
        quality_score=quality_score,
        content_feedback=content_feedback,
        telop_check=telop_check,
        total_issues=total_issues,
        good_points=good_count,
        warnings=warning_count + telop_check.error_count,
        suggestions=suggestion_count + telop_check.warning_count,
        video_id=f"{guest_name}_{stage}",
        guest_name=guest_name,
        editor=editor,
        stage=stage,
        feedback_timestamp=now,
        is_estimated=True,
    )


def _generate_content_feedback(
    video_data: VideoData,
    classification: ClassificationResult,
    included_ts: list,
    excluded_ts: list,
) -> list:
    """コンテンツに関するフィードバックを生成"""
    feedback = []

    # ハイライトシーンの取捨選択チェック
    if video_data.highlights:
        feedback.extend(_check_highlight_inclusion(
            video_data.highlights, included_ts, excluded_ts
        ))

    # ゲスト分類に基づくコンテンツチェック
    feedback.extend(_check_classification_alignment(
        video_data, classification
    ))

    # 全体的なバランスチェック
    feedback.extend(_check_content_balance(video_data))

    return feedback


def _check_highlight_inclusion(
    highlights: list,
    included_ts: list,
    excluded_ts: list,
) -> list:
    """ハイライトシーンの取捨選択をチェック"""
    feedback = []

    if not included_ts and not excluded_ts:
        # タイムスタンプ指定なし → 全ハイライトの確認を推奨
        critical_highlights = [
            h for h in highlights
            if h.category in ("実績数字", "パンチライン")
        ]
        if critical_highlights:
            feedback.append(ContentFeedbackItem(
                category="emphasis",
                severity="suggestion",
                description=f"重要なハイライト{len(critical_highlights)}件の確認を推奨（実績数字・パンチライン）",
            ))
        return feedback

    included_set = set(included_ts)
    excluded_set = set(excluded_ts)

    for hl in highlights:
        if hl.timestamp in excluded_set:
            # 除外されたシーンのチェック
            if hl.category in ("実績数字", "パンチライン"):
                feedback.append(ContentFeedbackItem(
                    category="missing",
                    severity="warning",
                    description=f"重要シーン（{hl.category}）が除外されています",
                    timestamp=hl.timestamp,
                    highlight_text=hl.text,
                ))
            else:
                feedback.append(ContentFeedbackItem(
                    category="missing",
                    severity="suggestion",
                    description=f"シーン（{hl.category}）が除外されています。意図的であれば問題ありません",
                    timestamp=hl.timestamp,
                    highlight_text=hl.text,
                ))
        elif hl.timestamp in included_set:
            # 含まれているシーン → 良い点
            if hl.category in ("実績数字", "パンチライン"):
                feedback.append(ContentFeedbackItem(
                    category="included",
                    severity="good",
                    description=f"重要シーン（{hl.category}）が適切に含まれています",
                    timestamp=hl.timestamp,
                    highlight_text=hl.text,
                ))

    return feedback


def _check_classification_alignment(
    video_data: VideoData,
    classification: ClassificationResult,
) -> list:
    """ゲスト分類に基づくコンテンツチェック"""
    feedback = []

    if classification.tier == "a":
        # 層a: 強さ・ハイキャリアが前面に出ているか
        number_highlights = [
            h for h in video_data.highlights if h.category == "実績数字"
        ]
        if len(number_highlights) < 2:
            feedback.append(ContentFeedbackItem(
                category="emphasis",
                severity="suggestion",
                description="層aゲスト: 実績数字のシーンが少ない。強さの強調を検討してください",
            ))
        else:
            feedback.append(ContentFeedbackItem(
                category="emphasis",
                severity="good",
                description=f"層aゲスト: 実績数字{len(number_highlights)}件で強さが適切に表現されています",
            ))

    elif classification.tier == "b":
        # 層b: 年収以外の強さが言語化されているか
        alternative_highlights = [
            h for h in video_data.highlights
            if h.category in ("属性紹介", "TEKO価値")
        ]
        if not alternative_highlights:
            feedback.append(ContentFeedbackItem(
                category="emphasis",
                severity="warning",
                description="層bゲスト: 年収以外の強み（属性・TEKO価値）のシーンがありません",
            ))

    return feedback


def _check_content_balance(video_data: VideoData) -> list:
    """全体的なコンテンツバランスをチェック"""
    feedback = []

    if not video_data.highlights:
        feedback.append(ContentFeedbackItem(
            category="emphasis",
            severity="warning",
            description="ハイライトシーンが検出されていません",
        ))
        return feedback

    # カテゴリ分布
    categories = [h.category for h in video_data.highlights]
    unique_categories = set(categories)

    if len(unique_categories) == 1:
        feedback.append(ContentFeedbackItem(
            category="order",
            severity="suggestion",
            description=f"ハイライトが1カテゴリ（{list(unique_categories)[0]}）に偏っています。多様性の検討を推奨",
        ))
    elif len(unique_categories) >= 4:
        feedback.append(ContentFeedbackItem(
            category="order",
            severity="good",
            description=f"ハイライトが{len(unique_categories)}カテゴリに分散。良いバランスです",
        ))

    return feedback
