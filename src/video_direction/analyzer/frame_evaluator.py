from __future__ import annotations
"""C-1: フレーム画像マルチモデル評価

代表フレームをClaude Opus 4.6 + GPT-5.4で独立評価。
両モデル合意 → 「指摘」に昇格、不合意 → 「要検討」。

Phase 2実装:
- opencv/実映像なしでもモック・スタブで動作する設計
- フレーム抽出はスタブ（実映像分析は将来対応）
- 評価ロジックの骨格とデータ構造を先行実装

Phase 3以降:
- opencv-pythonによる実フレーム抽出
- Anthropic/OpenAI APIによるマルチモデル評価
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from ..integrations.ai_dev5_connector import VideoData, HighlightScene


# 評価の軸
EVALUATION_AXES = [
    "composition",    # 構図
    "lighting",       # 照明
    "color_balance",  # 色バランス
    "focus",          # フォーカス
    "framing",        # フレーミング（被写体の配置）
]

AXIS_LABELS = {
    "composition": "構図",
    "lighting": "照明",
    "color_balance": "色バランス",
    "focus": "フォーカス",
    "framing": "フレーミング",
}

# 合意レベル
AGREEMENT_THRESHOLD = 15  # 両モデルのスコア差がこの範囲内なら「合意」


@dataclass
class FrameInfo:
    """フレーム情報"""
    timestamp: str  # "MM:SS" 形式
    frame_index: int = 0  # フレーム番号
    scene_description: str = ""  # シーンの説明
    image_path: str = ""  # フレーム画像パス（将来用）
    is_stub: bool = True  # スタブデータかどうか


@dataclass
class ModelEvaluation:
    """単一モデルの評価結果"""
    model_name: str  # "claude-opus-4.6" / "gpt-5.4"
    scores: dict = field(default_factory=dict)  # {axis: score(0-100)}
    overall_score: float = 0.0
    comments: list = field(default_factory=list)  # モデルのコメント
    is_stub: bool = True  # スタブ評価かどうか


@dataclass
class FrameEvaluation:
    """フレーム評価結果（マルチモデル）"""
    frame: FrameInfo
    evaluations: list = field(default_factory=list)  # List[ModelEvaluation]
    consensus_score: float = 0.0  # 合意スコア（両モデルの平均）
    findings: list = field(default_factory=list)  # List[Finding]
    agreement_level: str = ""  # "agreed" / "partial" / "disagreed"


@dataclass
class Finding:
    """指摘事項"""
    axis: str  # 評価軸
    axis_label: str  # 評価軸の日本語名
    level: str  # "issue"（指摘: 両モデル合意） / "review"（要検討: 不合意）
    description: str
    model_scores: dict = field(default_factory=dict)  # {model_name: score}
    suggestion: str = ""  # 改善提案


@dataclass
class FrameEvaluationResult:
    """フレーム評価全体の結果"""
    evaluations: list = field(default_factory=list)  # List[FrameEvaluation]
    total_frames: int = 0
    issue_count: int = 0  # 両モデル合意の指摘数
    review_count: int = 0  # 要検討数
    average_score: float = 0.0
    is_stub: bool = True  # 全てスタブ評価か


def evaluate_frames(
    video_data: VideoData,
    video_path: Optional[str] = None,
    use_api: bool = False,
) -> FrameEvaluationResult:
    """フレーム画像のマルチモデル評価を実行する

    Phase 2: 文字起こしデータから代表フレームを推定し、
    スタブ評価を生成する。実APIは呼ばない。

    Args:
        video_data: パース済みのVideoData
        video_path: 動画ファイルパス（Phase 3以降で使用）
        use_api: APIを使った実評価を行うか（Phase 3以降）

    Returns:
        FrameEvaluationResult: フレーム評価結果
    """
    # Step 1: 代表フレームの選定（ハイライトシーンから）
    frames = _select_representative_frames(video_data)

    if not frames:
        return FrameEvaluationResult(is_stub=True)

    # Step 2: 各フレームの評価
    evaluations = []
    for frame in frames:
        if use_api and video_path:
            # Phase 3: 実APIでの評価（未実装）
            eval_result = _evaluate_frame_with_api(frame, video_path)
        else:
            # Phase 2: スタブ評価（文字起こしベース）
            eval_result = _evaluate_frame_stub(frame, video_data)
        evaluations.append(eval_result)

    # Step 3: 集計
    total_frames = len(evaluations)
    issue_count = sum(
        sum(1 for f in e.findings if f.level == "issue")
        for e in evaluations
    )
    review_count = sum(
        sum(1 for f in e.findings if f.level == "review")
        for e in evaluations
    )
    avg_score = (
        sum(e.consensus_score for e in evaluations) / total_frames
        if total_frames > 0 else 0.0
    )

    return FrameEvaluationResult(
        evaluations=evaluations,
        total_frames=total_frames,
        issue_count=issue_count,
        review_count=review_count,
        average_score=round(avg_score, 1),
        is_stub=not use_api,
    )


def _select_representative_frames(video_data: VideoData) -> list:
    """代表フレームを選定する

    ハイライトシーンのタイムスタンプから代表フレームを選ぶ。
    最大10フレームまで。
    """
    frames = []

    if not video_data.highlights:
        return frames

    # ハイライトからカテゴリ別に代表を選定
    category_priority = ["実績数字", "パンチライン", "属性紹介", "TEKO価値", "メッセージ"]
    selected_timestamps = set()

    for category in category_priority:
        for hl in video_data.highlights:
            if hl.category == category and hl.timestamp not in selected_timestamps:
                frames.append(FrameInfo(
                    timestamp=hl.timestamp,
                    frame_index=len(frames),
                    scene_description=f"[{hl.category}] {hl.speaker}: {hl.text[:50]}",
                    is_stub=True,
                ))
                selected_timestamps.add(hl.timestamp)

                if len(frames) >= 10:
                    return frames

    return frames


def _evaluate_frame_stub(frame: FrameInfo, video_data: VideoData) -> FrameEvaluation:
    """スタブ評価（文字起こしベースの推定）

    実映像なしでの推定評価。ハイライト情報から映像品質を推定する。
    """
    # Claude モデルのスタブ評価
    claude_eval = _generate_stub_evaluation(
        model_name="claude-opus-4.6",
        frame=frame,
        video_data=video_data,
        bias_seed=1,
    )

    # GPT モデルのスタブ評価
    gpt_eval = _generate_stub_evaluation(
        model_name="gpt-5.4",
        frame=frame,
        video_data=video_data,
        bias_seed=2,
    )

    # 合意分析
    findings = _analyze_agreement(claude_eval, gpt_eval)
    consensus_score = _calculate_consensus_score(claude_eval, gpt_eval)
    agreement_level = _determine_agreement_level(claude_eval, gpt_eval)

    return FrameEvaluation(
        frame=frame,
        evaluations=[claude_eval, gpt_eval],
        consensus_score=consensus_score,
        findings=findings,
        agreement_level=agreement_level,
    )


def _evaluate_frame_with_api(frame: FrameInfo, video_path: str) -> FrameEvaluation:
    """API評価（Phase 3で実装予定）

    現時点ではスタブと同じ動作をする。
    """
    # Phase 3以降: opencv でフレーム抽出 → API送信
    # 現時点ではスタブ
    return FrameEvaluation(
        frame=frame,
        evaluations=[],
        consensus_score=0.0,
        findings=[],
        agreement_level="pending",
    )


def _generate_stub_evaluation(
    model_name: str,
    frame: FrameInfo,
    video_data: VideoData,
    bias_seed: int = 0,
) -> ModelEvaluation:
    """スタブ評価を生成

    文字起こしの情報量・構造から映像品質を推定する。
    モデルごとに微妙に異なるスコアを付与（bias_seedで制御）。
    """
    scores = {}
    comments = []

    # 基本スコア（文字起こしベースの推定）
    base_score = 55  # ベースライン

    # ハイライト数による加算
    hl_count = len(video_data.highlights)
    if hl_count >= 8:
        base_score += 10
    elif hl_count >= 4:
        base_score += 5

    # 話者数による構図推定
    speaker_count = 1
    if video_data.speakers and "," in video_data.speakers:
        speaker_count = len(video_data.speakers.split(","))

    for axis in EVALUATION_AXES:
        axis_score = base_score

        # 軸ごとの調整
        if axis == "composition":
            if speaker_count == 2:
                axis_score += 8  # 2名対談は構図が安定しやすい
            axis_score += (bias_seed * 3) % 7  # モデルによる微小差

        elif axis == "lighting":
            axis_score += (bias_seed * 5) % 10  # 推定困難のためランダム寄り

        elif axis == "color_balance":
            axis_score += (bias_seed * 7) % 8

        elif axis == "focus":
            # インタビュー形式はフォーカスが安定しやすい
            if video_data.video_type and "インタビュー" in video_data.video_type:
                axis_score += 10
            axis_score += (bias_seed * 2) % 5

        elif axis == "framing":
            if speaker_count == 2:
                axis_score += 5
            axis_score += (bias_seed * 4) % 6

        scores[axis] = min(100, max(0, axis_score))

    overall = sum(scores.values()) / len(scores) if scores else 0
    comments.append(f"Phase 2推定値（{model_name}）: 文字起こしベースの推定評価")

    if frame.scene_description:
        comments.append(f"シーン: {frame.scene_description[:80]}")

    return ModelEvaluation(
        model_name=model_name,
        scores=scores,
        overall_score=round(overall, 1),
        comments=comments,
        is_stub=True,
    )


def _analyze_agreement(eval_a: ModelEvaluation, eval_b: ModelEvaluation) -> list:
    """2つのモデル評価の合意分析"""
    findings = []

    for axis in EVALUATION_AXES:
        score_a = eval_a.scores.get(axis, 0)
        score_b = eval_b.scores.get(axis, 0)
        diff = abs(score_a - score_b)
        avg = (score_a + score_b) / 2

        # 低スコア（60未満）の場合に指摘を生成
        if avg < 60:
            if diff <= AGREEMENT_THRESHOLD:
                # 両モデル合意 → 指摘
                findings.append(Finding(
                    axis=axis,
                    axis_label=AXIS_LABELS.get(axis, axis),
                    level="issue",
                    description=f"{AXIS_LABELS.get(axis, axis)}のスコアが低い（平均{avg:.0f}点）",
                    model_scores={eval_a.model_name: score_a, eval_b.model_name: score_b},
                    suggestion=f"{AXIS_LABELS.get(axis, axis)}の改善を推奨",
                ))
            else:
                # 不合意 → 要検討
                findings.append(Finding(
                    axis=axis,
                    axis_label=AXIS_LABELS.get(axis, axis),
                    level="review",
                    description=f"{AXIS_LABELS.get(axis, axis)}の評価がモデル間で分かれている（差{diff}点）",
                    model_scores={eval_a.model_name: score_a, eval_b.model_name: score_b},
                ))

    return findings


def _calculate_consensus_score(eval_a: ModelEvaluation, eval_b: ModelEvaluation) -> float:
    """合意スコアを計算（両モデルの平均）"""
    if not eval_a.scores or not eval_b.scores:
        return 0.0
    avg = (eval_a.overall_score + eval_b.overall_score) / 2
    return round(avg, 1)


def _determine_agreement_level(eval_a: ModelEvaluation, eval_b: ModelEvaluation) -> str:
    """合意レベルを判定"""
    if not eval_a.scores or not eval_b.scores:
        return "pending"

    diffs = []
    for axis in EVALUATION_AXES:
        score_a = eval_a.scores.get(axis, 0)
        score_b = eval_b.scores.get(axis, 0)
        diffs.append(abs(score_a - score_b))

    avg_diff = sum(diffs) / len(diffs) if diffs else 0

    if avg_diff <= 10:
        return "agreed"
    elif avg_diff <= 20:
        return "partial"
    else:
        return "disagreed"


# === ユーティリティ: フレーム抽出スタブ ===

def extract_frames_from_video(
    video_path: str,
    timestamps: list,
) -> list:
    """動画からフレームを抽出する（Phase 3で実装）

    Args:
        video_path: 動画ファイルパス
        timestamps: 抽出するタイムスタンプのリスト

    Returns:
        list[str]: 保存されたフレーム画像のパスリスト

    Note:
        Phase 2ではスタブ。opencv-pythonが必要。
    """
    # Phase 3以降: opencv-pythonを使ってフレーム抽出
    # import cv2
    # cap = cv2.VideoCapture(video_path)
    # ...
    return []  # スタブ: 空リストを返す
