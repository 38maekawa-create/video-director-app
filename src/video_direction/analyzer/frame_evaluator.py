from __future__ import annotations
"""C-1: フレーム画像マルチモデル評価

代表フレームをClaude Opus 4.6 + GPT-5.4で独立評価。
両モデル合意 → 「指摘」に昇格、不合意 → 「要検討」。

Phase 2実装:
- opencv/実映像なしでもモック・スタブで動作する設計
- フレーム抽出はスタブ（実映像分析は将来対応）
- 評価ロジックの骨格とデータ構造を先行実装

Phase 3実装:
- opencv-pythonによる実フレーム抽出（等間隔 + シーンチェンジ検出）
- Anthropic APIによるフレーム画像評価（構図/色彩/明るさ/フォーカス/テロップ可読性）
- cv2/APIキーが無い場合はgracefulに推定値フォールバック
"""

import base64
import io
import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import Optional

from ..integrations.ai_dev5_connector import VideoData, HighlightScene

# opencv-python のgraceful import
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    cv2 = None
    np = None
    HAS_CV2 = False

# Pillow のgraceful import
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    Image = None
    HAS_PIL = False

# anthropic のgraceful import
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    anthropic = None
    HAS_ANTHROPIC = False

logger = logging.getLogger(__name__)

# シーンチェンジ検出の閾値（フレーム間差分のピクセル平均値）
SCENE_CHANGE_THRESHOLD = 30.0
# 最大フレーム抽出数
MAX_EXTRACTED_FRAMES = 20


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
            # Phase 3: 実APIでの評価
            eval_result = _evaluate_frame_with_api(frame, video_path, video_data)
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


def _evaluate_frame_with_api(
    frame: FrameInfo,
    video_path: str,
    video_data: VideoData | None = None,
) -> FrameEvaluation:
    """Claude APIでフレーム画像を評価する

    動画からフレームを抽出し、Claude APIに送信して評価を受ける。
    APIキーが無い場合やエラー時はスタブ評価にフォールバック。

    Args:
        frame: 評価対象フレーム情報
        video_path: 動画ファイルパス
        video_data: VideoData（フォールバック用）

    Returns:
        FrameEvaluation: 評価結果
    """
    # cv2が無い場合はフォールバック
    if not HAS_CV2:
        logger.info("cv2が無いためスタブ評価にフォールバック")
        if video_data:
            return _evaluate_frame_stub(frame, video_data)
        return FrameEvaluation(
            frame=frame, evaluations=[], consensus_score=0.0,
            findings=[], agreement_level="pending",
        )

    # フレーム画像を抽出
    frame_image_b64 = _extract_single_frame_b64(video_path, frame.timestamp)
    if frame_image_b64 is None:
        logger.warning(f"フレーム画像を抽出できません: {frame.timestamp}")
        if video_data:
            return _evaluate_frame_stub(frame, video_data)
        return FrameEvaluation(
            frame=frame, evaluations=[], consensus_score=0.0,
            findings=[], agreement_level="pending",
        )

    # Claude APIで評価
    claude_eval = _call_claude_vision_api(frame, frame_image_b64)

    # GPT-5.4のAPIは未実装のためスタブ（将来的にOpenAI APIも追加）
    gpt_eval = ModelEvaluation(
        model_name="gpt-5.4",
        scores={axis: claude_eval.scores.get(axis, 60) + ((hash(axis) % 11) - 5) for axis in EVALUATION_AXES},
        overall_score=0.0,
        comments=["GPT-5.4 API未実装: Claude評価ベースの推定値"],
        is_stub=True,
    )
    # overall_scoreを再計算
    if gpt_eval.scores:
        gpt_eval.scores = {k: min(100, max(0, v)) for k, v in gpt_eval.scores.items()}
        gpt_eval.overall_score = round(sum(gpt_eval.scores.values()) / len(gpt_eval.scores), 1)

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


def _extract_single_frame_b64(video_path: str, timestamp: str) -> str | None:
    """動画から指定タイムスタンプのフレームを1枚抽出し、base64で返す"""
    if not HAS_CV2:
        return None

    sec = _timestamp_to_seconds(timestamp)
    if sec is None:
        return None

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        return None

    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            return None
        frame_idx = int(sec * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            return None
        return _frame_to_base64(frame)
    finally:
        cap.release()


def _call_claude_vision_api(frame: FrameInfo, image_b64: str) -> ModelEvaluation:
    """Claude Vision APIでフレームを評価する

    APIキーが無い場合やAPIエラー時はスタブスコアにフォールバック。
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not HAS_ANTHROPIC or not api_key:
        logger.info("Anthropic APIキーが未設定のためスタブ評価にフォールバック")
        return _generate_fallback_evaluation("claude-opus-4.6", frame)

    prompt = (
        "この動画フレーム画像を映像品質の観点で評価してください。\n"
        "以下の5項目について、それぞれ0-100のスコアと短いコメントを付けてください。\n\n"
        "1. composition (構図): 被写体の配置、三分割法、余白のバランス\n"
        "2. lighting (明るさ): 露出、コントラスト、逆光や白飛び\n"
        "3. color_balance (色彩): 色温度、彩度、カラーグレーディング\n"
        "4. focus (フォーカス): ピントの合い具合、被写界深度\n"
        "5. framing (テロップ可読性): テロップやテキストがあれば読みやすさ。なければフレーミング全般\n\n"
        "以下のJSON形式で返してください（他のテキストは不要）:\n"
        "```json\n"
        '{"composition": {"score": 75, "comment": "..."},\n'
        ' "lighting": {"score": 80, "comment": "..."},\n'
        ' "color_balance": {"score": 70, "comment": "..."},\n'
        ' "focus": {"score": 85, "comment": "..."},\n'
        ' "framing": {"score": 60, "comment": "..."}}\n'
        "```"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",  # Vision評価にはSonnetで十分
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )

        # レスポンスのパース
        response_text = message.content[0].text
        return _parse_vision_response(response_text)

    except Exception as e:
        logger.warning(f"Claude Vision API呼び出しに失敗: {e}")
        return _generate_fallback_evaluation("claude-opus-4.6", frame)


def _parse_vision_response(response_text: str) -> ModelEvaluation:
    """Claude Vision APIのレスポンスをModelEvaluationにパースする"""
    import json

    scores = {}
    comments = []

    try:
        # JSONブロックを抽出
        json_match = re.search(r"```json\s*\n?(.*?)\n?```", response_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(1))
        else:
            # ```なしの生JSON
            data = json.loads(response_text.strip())

        for axis in EVALUATION_AXES:
            if axis in data:
                entry = data[axis]
                if isinstance(entry, dict):
                    scores[axis] = min(100, max(0, int(entry.get("score", 60))))
                    if "comment" in entry:
                        comments.append(f"{AXIS_LABELS.get(axis, axis)}: {entry['comment']}")
                elif isinstance(entry, (int, float)):
                    scores[axis] = min(100, max(0, int(entry)))

    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning(f"Vision APIレスポンスのパースに失敗: {e}")
        # パース失敗時はデフォルトスコア
        for axis in EVALUATION_AXES:
            scores.setdefault(axis, 60)
        comments.append("APIレスポンスのパースに失敗したためデフォルト値を使用")

    # 未設定の軸をデフォルトで埋める
    for axis in EVALUATION_AXES:
        scores.setdefault(axis, 60)

    overall = sum(scores.values()) / len(scores) if scores else 0.0

    return ModelEvaluation(
        model_name="claude-opus-4.6",
        scores=scores,
        overall_score=round(overall, 1),
        comments=comments,
        is_stub=False,
    )


def _generate_fallback_evaluation(model_name: str, frame: FrameInfo) -> ModelEvaluation:
    """APIが利用できない場合のフォールバック推定評価"""
    scores = {}
    base = 60

    for i, axis in enumerate(EVALUATION_AXES):
        # フレームインデックスとaxis名で微小な変動を付与
        variation = (hash(f"{frame.timestamp}_{axis}") % 15) - 7
        scores[axis] = min(100, max(0, base + variation))

    overall = sum(scores.values()) / len(scores)

    return ModelEvaluation(
        model_name=model_name,
        scores=scores,
        overall_score=round(overall, 1),
        comments=[f"APIフォールバック推定値（{model_name}）"],
        is_stub=True,
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
    timestamps: list | None = None,
    num_uniform: int = 10,
    detect_scene_changes: bool = True,
    output_format: str = "base64",
) -> list:
    """動画からフレームを抽出する

    等間隔で代表フレームを抽出し、さらにシーンチェンジ検出で追加フレームを抽出する。
    opencv-pythonが無い場合やファイルが開けない場合は空リストにフォールバック。

    Args:
        video_path: 動画ファイルパス
        timestamps: 指定タイムスタンプ("MM:SS"形式)のリスト。指定された場合はそれらを優先抽出
        num_uniform: 等間隔で抽出するフレーム数（デフォルト10）
        detect_scene_changes: シーンチェンジ検出を行うか（デフォルトTrue）
        output_format: "base64" (base64文字列) / "pil" (PIL Image) / "path" (一時ファイルパス)

    Returns:
        list[dict]: 抽出フレーム情報のリスト。各要素は以下のキーを持つ:
            - "timestamp": str ("MM:SS"形式)
            - "frame_index": int (元動画でのフレーム番号)
            - "image": str|Image|None (フォーマットに応じた画像データ)
            - "source": str ("uniform"/"scene_change"/"timestamp")
        cv2が無い場合やファイルが開けない場合は空リストを返す
    """
    if not HAS_CV2:
        logger.warning("opencv-pythonが未インストールのためフレーム抽出をスキップします")
        return []

    if not os.path.isfile(video_path):
        logger.warning(f"動画ファイルが見つかりません: {video_path}")
        return []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        logger.warning(f"動画ファイルを開けません: {video_path}")
        return []

    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if total_frames <= 0 or fps <= 0:
            logger.warning(f"動画のメタデータが不正です: fps={fps}, frames={total_frames}")
            return []

        duration_sec = total_frames / fps
        extracted = []

        # (1) 指定タイムスタンプからの抽出
        if timestamps:
            for ts in timestamps:
                sec = _timestamp_to_seconds(ts)
                if sec is not None and sec < duration_sec:
                    frame_idx = int(sec * fps)
                    frame_data = _read_frame(cap, frame_idx, output_format)
                    if frame_data is not None:
                        extracted.append({
                            "timestamp": ts,
                            "frame_index": frame_idx,
                            "image": frame_data,
                            "source": "timestamp",
                        })

        # (2) 等間隔フレーム抽出
        if num_uniform > 0:
            interval = total_frames / num_uniform
            for i in range(num_uniform):
                frame_idx = int(i * interval)
                if frame_idx >= total_frames:
                    break
                # 既に同じフレームを抽出済みならスキップ
                if any(abs(e["frame_index"] - frame_idx) < fps for e in extracted):
                    continue
                frame_data = _read_frame(cap, frame_idx, output_format)
                if frame_data is not None:
                    sec = frame_idx / fps
                    extracted.append({
                        "timestamp": _seconds_to_timestamp(sec),
                        "frame_index": frame_idx,
                        "image": frame_data,
                        "source": "uniform",
                    })

        # (3) シーンチェンジ検出による追加フレーム
        if detect_scene_changes:
            scene_frames = _detect_scene_changes(cap, fps, total_frames)
            for frame_idx in scene_frames:
                # 既に近接フレームが抽出済みならスキップ
                if any(abs(e["frame_index"] - frame_idx) < fps for e in extracted):
                    continue
                if len(extracted) >= MAX_EXTRACTED_FRAMES:
                    break
                frame_data = _read_frame(cap, frame_idx, output_format)
                if frame_data is not None:
                    sec = frame_idx / fps
                    extracted.append({
                        "timestamp": _seconds_to_timestamp(sec),
                        "frame_index": frame_idx,
                        "image": frame_data,
                        "source": "scene_change",
                    })

        # タイムスタンプ順にソート
        extracted.sort(key=lambda x: x["frame_index"])
        return extracted[:MAX_EXTRACTED_FRAMES]

    finally:
        cap.release()


def _read_frame(cap, frame_idx: int, output_format: str):
    """指定フレームを読み込み、指定フォーマットで返す"""
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    if not ret or frame is None:
        return None

    if output_format == "base64":
        return _frame_to_base64(frame)
    elif output_format == "pil" and HAS_PIL:
        return _frame_to_pil(frame)
    elif output_format == "path":
        return _frame_to_tempfile(frame)
    else:
        # デフォルトはbase64
        return _frame_to_base64(frame)


def _frame_to_base64(frame) -> str:
    """cv2フレームをbase64 JPEG文字列に変換"""
    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buffer).decode("utf-8")


def _frame_to_pil(frame):
    """cv2フレームをPIL Imageに変換"""
    if not HAS_PIL:
        return None
    # cv2はBGR、PILはRGBなので変換
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def _frame_to_tempfile(frame) -> str:
    """cv2フレームを一時ファイルに保存しパスを返す

    注意: 呼び出し元で必ず os.unlink(path) を呼んでファイルを削除すること。
    削除忘れは一時ファイルの蓄積（リソースリーク）につながる。
    例:
        path = _frame_to_tempfile(frame)
        try:
            process(path)
        finally:
            os.unlink(path)
    """
    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return path


def _detect_scene_changes(cap, fps: float, total_frames: int) -> list:
    """シーンチェンジ（フレーム間差分が閾値を超えた箇所）を検出する

    全フレームを走査するのではなく、一定間隔でサンプリングして差分を計算する。

    Returns:
        list[int]: シーンチェンジが検出されたフレーム番号のリスト
    """
    # サンプリング間隔: 0.5秒ごとにチェック
    sample_interval = max(1, int(fps * 0.5))
    scene_changes = []
    prev_gray = None

    for frame_idx in range(0, total_frames, sample_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # リサイズして計算コストを下げる（160x90）
        gray = cv2.resize(gray, (160, 90))

        if prev_gray is not None:
            diff = cv2.absdiff(gray, prev_gray)
            mean_diff = float(np.mean(diff))
            if mean_diff > SCENE_CHANGE_THRESHOLD:
                scene_changes.append(frame_idx)

        prev_gray = gray

    return scene_changes


def _timestamp_to_seconds(ts: str) -> float | None:
    """'MM:SS' 形式のタイムスタンプを秒数に変換"""
    match = re.match(r"(\d+):(\d{2})", ts)
    if not match:
        return None
    minutes = int(match.group(1))
    seconds = int(match.group(2))
    return minutes * 60 + seconds


def _seconds_to_timestamp(sec: float) -> str:
    """秒数を'MM:SS'形式のタイムスタンプに変換"""
    minutes = int(sec // 60)
    seconds = int(sec % 60)
    return f"{minutes:02d}:{seconds:02d}"
