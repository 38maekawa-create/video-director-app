from __future__ import annotations
"""C-3: 音声品質自動評価

BGMと会話音声のバランス + ノイズレベル検出 + SE適切性評価。

Phase 2実装:
- ffmpeg/実映像なしでもモック・スタブで動作する設計
- 文字起こしデータ・メタデータからの推定評価
- 評価ロジックの骨格とデータ構造を先行実装

Phase 3以降:
- ffmpegによる実際の音声解析
- RMS/LUFS測定、スペクトル分析
- BGM/音声分離と自動バランスチェック
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from ..integrations.ai_dev5_connector import VideoData, HighlightScene


# 音声品質の評価軸
AUDIO_AXES = [
    "voice_clarity",   # 音声の明瞭度
    "bgm_balance",     # BGMと会話のバランス
    "noise_level",     # ノイズレベル
    "se_quality",      # 効果音（SE）の適切性
    "volume_consistency",  # 音量の一貫性
]

AUDIO_AXIS_LABELS = {
    "voice_clarity": "音声明瞭度",
    "bgm_balance": "BGMバランス",
    "noise_level": "ノイズレベル",
    "se_quality": "効果音品質",
    "volume_consistency": "音量一貫性",
}

# 推奨値
RECOMMENDED_VOICE_DB = -14.0  # 会話音声の推奨レベル（LUFS）
RECOMMENDED_BGM_DB = -24.0    # BGMの推奨レベル（LUFS）
MAX_NOISE_FLOOR = -50.0       # ノイズフロアの許容上限（dB）


@dataclass
class AudioSegmentInfo:
    """音声セグメントの情報"""
    start_ts: str  # "MM:SS"
    end_ts: str  # "MM:SS"
    segment_type: str  # "speech" / "bgm" / "silence" / "se"
    speaker: str = ""
    estimated_volume: str = ""  # "normal" / "loud" / "quiet"
    is_stub: bool = True


@dataclass
class AudioAxisScore:
    """音声品質の1軸スコア"""
    axis: str
    label: str
    score: int  # 0-100
    notes: list = field(default_factory=list)
    measured_value: str = ""  # 実測値（Phase 3以降）
    is_estimated: bool = True


@dataclass
class AudioIssue:
    """音声の問題点"""
    timestamp: str  # 問題箇所のタイムスタンプ
    issue_type: str  # "balance" / "noise" / "volume" / "clarity" / "se"
    severity: str  # "error" / "warning" / "info"
    description: str
    suggestion: str = ""


@dataclass
class AudioEvaluationResult:
    """音声品質評価の全体結果"""
    axis_scores: list = field(default_factory=list)  # List[AudioAxisScore]
    overall_score: float = 0.0  # 総合スコア（0-100）
    grade: str = ""  # "S" / "A" / "B" / "C" / "D"
    issues: list = field(default_factory=list)  # List[AudioIssue]
    segments: list = field(default_factory=list)  # List[AudioSegmentInfo]
    error_count: int = 0
    warning_count: int = 0
    is_estimated: bool = True  # 推定値か実測値か
    analysis_method: str = "transcript_based"  # "transcript_based" / "ffmpeg_analysis"


def evaluate_audio(
    video_data: VideoData,
    audio_path: Optional[str] = None,
    use_ffmpeg: bool = False,
) -> AudioEvaluationResult:
    """音声品質の自動評価を実行する

    Phase 2: 文字起こしデータからの推定評価
    Phase 3: ffmpegによる実測評価

    Args:
        video_data: パース済みのVideoData
        audio_path: 音声/動画ファイルパス（Phase 3以降）
        use_ffmpeg: ffmpegを使った実解析を行うか

    Returns:
        AudioEvaluationResult: 音声品質評価結果
    """
    if use_ffmpeg and audio_path:
        # Phase 3: ffmpegによる実測（未実装）
        return _evaluate_with_ffmpeg(audio_path, video_data)
    else:
        # Phase 2: 文字起こしベースの推定
        return _evaluate_from_transcript(video_data)


def _evaluate_from_transcript(video_data: VideoData) -> AudioEvaluationResult:
    """文字起こしベースの推定評価"""
    axis_scores = []
    all_issues = []
    segments = []

    # Step 1: 音声セグメントの推定
    segments = _estimate_audio_segments(video_data)

    # Step 2: 各軸のスコア計算
    axis_scores.append(_score_voice_clarity(video_data, segments))
    axis_scores.append(_score_bgm_balance(video_data, segments))
    axis_scores.append(_score_noise_level(video_data, segments))
    axis_scores.append(_score_se_quality(video_data, segments))
    axis_scores.append(_score_volume_consistency(video_data, segments))

    # Step 3: 問題検出
    all_issues = _detect_audio_issues(video_data, segments)

    # Step 4: 集計
    overall = (
        sum(a.score for a in axis_scores) / len(axis_scores)
        if axis_scores else 0
    )
    overall = round(overall, 1)
    grade = _determine_audio_grade(overall)

    error_count = sum(1 for i in all_issues if i.severity == "error")
    warning_count = sum(1 for i in all_issues if i.severity == "warning")

    return AudioEvaluationResult(
        axis_scores=axis_scores,
        overall_score=overall,
        grade=grade,
        issues=all_issues,
        segments=segments,
        error_count=error_count,
        warning_count=warning_count,
        is_estimated=True,
        analysis_method="transcript_based",
    )


def _evaluate_with_ffmpeg(audio_path: str, video_data: VideoData) -> AudioEvaluationResult:
    """ffmpegによる実測評価（Phase 3で実装予定）

    現時点ではスタブで推定評価と同じ動作をする。
    """
    # Phase 3以降:
    # import subprocess
    # result = subprocess.run(["ffprobe", ...], capture_output=True)
    # ...
    return _evaluate_from_transcript(video_data)


def _estimate_audio_segments(video_data: VideoData) -> list:
    """文字起こしから音声セグメントを推定する"""
    segments = []

    # トランスクリプト全体から話者の発話セグメントを推定
    if video_data.full_transcript:
        # 話者ごとの発話ブロックを抽出
        speaker_pattern = re.compile(
            r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.+?)[:：]\s*(.+)"
        )
        for match in speaker_pattern.finditer(video_data.full_transcript):
            ts = match.group(1)
            speaker = match.group(2).strip()
            segments.append(AudioSegmentInfo(
                start_ts=ts,
                end_ts=ts,  # 終了時刻は推定困難
                segment_type="speech",
                speaker=speaker,
                estimated_volume="normal",
                is_stub=True,
            ))

    # ハイライトシーンからも推定
    for hl in video_data.highlights:
        # ハイライトシーンは発話が活発 → 音量が上がりやすい
        segments.append(AudioSegmentInfo(
            start_ts=hl.timestamp,
            end_ts=hl.timestamp,
            segment_type="speech",
            speaker=hl.speaker,
            estimated_volume="normal" if hl.category != "パンチライン" else "loud",
            is_stub=True,
        ))

    return segments


def _score_voice_clarity(video_data: VideoData, segments: list) -> AudioAxisScore:
    """音声明瞭度スコア"""
    score = 60  # ベースライン（推定のため控えめ）
    notes = ["Phase 2推定値: 実音声分析は未実施"]

    # 文字起こしの品質から推定
    if video_data.transcript_method:
        if "whisper" in video_data.transcript_method.lower():
            score += 10
            notes.append("Whisper文字起こし: 高精度のため音声品質良好と推定")

    # 話者が明確に分離されている → 音声品質が良い可能性
    if video_data.speakers:
        speaker_count = len(video_data.speakers.split(","))
        if speaker_count >= 2:
            score += 5
            notes.append("複数話者の分離成功: 音声品質が良好な可能性")

    # セグメント数（発話の活発さ）
    speech_segments = [s for s in segments if s.segment_type == "speech"]
    if len(speech_segments) >= 10:
        score += 5
        notes.append(f"発話セグメント{len(speech_segments)}件: 会話が活発")

    score = min(100, max(0, score))

    return AudioAxisScore(
        axis="voice_clarity",
        label=AUDIO_AXIS_LABELS["voice_clarity"],
        score=score,
        notes=notes,
        is_estimated=True,
    )


def _score_bgm_balance(video_data: VideoData, segments: list) -> AudioAxisScore:
    """BGMバランススコア"""
    score = 55  # ベースライン
    notes = ["Phase 2推定値: 実音声分析は未実施"]

    # インタビュー形式ではBGMは控えめが基本
    if video_data.video_type and "インタビュー" in video_data.video_type:
        score += 5
        notes.append("インタビュー形式: BGMは控えめ設定が標準")

    # 動画時間が長い場合、BGM変化が必要
    duration_min = _parse_duration_minutes(video_data.duration)
    if duration_min > 20:
        notes.append(f"動画時間{duration_min:.0f}分: BGM変化の確認推奨")
    elif duration_min > 0:
        score += 5

    score = min(100, max(0, score))

    return AudioAxisScore(
        axis="bgm_balance",
        label=AUDIO_AXIS_LABELS["bgm_balance"],
        score=score,
        notes=notes,
        is_estimated=True,
    )


def _score_noise_level(video_data: VideoData, segments: list) -> AudioAxisScore:
    """ノイズレベルスコア"""
    score = 60  # ベースライン
    notes = ["Phase 2推定値: 実音声分析は未実施"]

    # スタジオ収録のインタビューはノイズが少ない傾向
    if video_data.video_type and ("インタビュー" in video_data.video_type or "対談" in video_data.video_type):
        score += 10
        notes.append("スタジオ収録推定: ノイズレベルは低い可能性")

    score = min(100, max(0, score))

    return AudioAxisScore(
        axis="noise_level",
        label=AUDIO_AXIS_LABELS["noise_level"],
        score=score,
        notes=notes,
        is_estimated=True,
    )


def _score_se_quality(video_data: VideoData, segments: list) -> AudioAxisScore:
    """効果音品質スコア"""
    score = 55  # ベースライン
    notes = ["Phase 2推定値: SE使用状況は文字起こしから判定困難"]

    # ハイライトシーンが多い → SEが効果的に使われている可能性
    hl_count = len(video_data.highlights)
    if hl_count >= 8:
        score += 10
        notes.append(f"ハイライト{hl_count}件: SE活用の機会が豊富")
    elif hl_count >= 4:
        score += 5

    score = min(100, max(0, score))

    return AudioAxisScore(
        axis="se_quality",
        label=AUDIO_AXIS_LABELS["se_quality"],
        score=score,
        notes=notes,
        is_estimated=True,
    )


def _score_volume_consistency(video_data: VideoData, segments: list) -> AudioAxisScore:
    """音量一貫性スコア"""
    score = 60  # ベースライン
    notes = ["Phase 2推定値: 実音声分析は未実施"]

    # 音量変動の推定（パンチラインシーンが多い → 音量変動大）
    loud_segments = [s for s in segments if s.estimated_volume == "loud"]
    if loud_segments:
        if len(loud_segments) > 5:
            score -= 5
            notes.append(f"音量が大きいシーンが{len(loud_segments)}件: 音量変動が大きい可能性")
        else:
            notes.append(f"音量が大きいシーンが{len(loud_segments)}件: 適度な変動")

    # 話者が2名で安定した対話 → 音量が安定しやすい
    if video_data.speakers and "," in video_data.speakers:
        score += 5
        notes.append("2名対話: 音量が安定しやすい")

    score = min(100, max(0, score))

    return AudioAxisScore(
        axis="volume_consistency",
        label=AUDIO_AXIS_LABELS["volume_consistency"],
        score=score,
        notes=notes,
        is_estimated=True,
    )


def _detect_audio_issues(video_data: VideoData, segments: list) -> list:
    """音声の問題を検出"""
    issues = []

    # 長時間動画で話者切り替えが少ない → 音声バランスの確認推奨
    duration_min = _parse_duration_minutes(video_data.duration)
    speech_segments = [s for s in segments if s.segment_type == "speech"]
    unique_speakers = {s.speaker for s in speech_segments if s.speaker}

    if duration_min > 30 and len(unique_speakers) <= 1:
        issues.append(AudioIssue(
            timestamp="全体",
            issue_type="balance",
            severity="info",
            description="長時間動画で話者が1名のみ: 音声バランスの変化が少ない可能性",
            suggestion="BGMの変化やSEの追加を検討",
        ))

    # パンチラインが連続している → 音量の急変リスク
    loud_segments = [s for s in segments if s.estimated_volume == "loud"]
    if len(loud_segments) >= 2:
        # 近接するパンチライン（1分以内）をチェック
        loud_timestamps = sorted([_timestamp_to_seconds(s.start_ts) for s in loud_segments])
        for i in range(len(loud_timestamps) - 1):
            if loud_timestamps[i + 1] - loud_timestamps[i] < 60:
                issues.append(AudioIssue(
                    timestamp=_seconds_to_timestamp(loud_timestamps[i]),
                    issue_type="volume",
                    severity="warning",
                    description="音量が大きいシーンが近接: リミッター/コンプレッサーの確認推奨",
                    suggestion="音量のノーマライズ処理を推奨",
                ))
                break  # 1件のみ報告

    return issues


def _determine_audio_grade(overall_score: float) -> str:
    """スコアからグレードを判定"""
    if overall_score >= 90:
        return "S"
    elif overall_score >= 80:
        return "A"
    elif overall_score >= 65:
        return "B"
    elif overall_score >= 50:
        return "C"
    else:
        return "D"


def _parse_duration_minutes(duration_str: str) -> float:
    """動画時間文字列を分数に変換"""
    if not duration_str:
        return 0

    m = re.search(r"(\d+)\s*分", duration_str)
    if m:
        minutes = float(m.group(1))
        s = re.search(r"(\d+)\s*秒", duration_str)
        if s:
            minutes += float(s.group(1)) / 60
        return minutes

    m = re.match(r"(\d+):(\d+)(?::(\d+))?", duration_str)
    if m:
        if m.group(3):
            return float(m.group(1)) * 60 + float(m.group(2)) + float(m.group(3)) / 60
        else:
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


def _seconds_to_timestamp(seconds: int) -> str:
    """秒数をMM:SS形式に変換"""
    m = seconds // 60
    s = seconds % 60
    return f"{m:02d}:{s:02d}"


# === ffmpeg解析スタブ ===

def analyze_audio_with_ffmpeg(audio_path: str) -> dict:
    """ffmpegで音声を解析する（Phase 3で実装）

    Args:
        audio_path: 音声/動画ファイルパス

    Returns:
        dict: 音声解析結果（LUFS、RMS、スペクトル情報等）

    Note:
        Phase 2ではスタブ。ffmpegのインストールが必要。
    """
    # Phase 3以降:
    # import subprocess
    # result = subprocess.run(
    #     ["ffmpeg", "-i", audio_path, "-af", "loudnorm=print_format=json", ...],
    #     capture_output=True,
    # )
    return {}  # スタブ: 空辞書を返す
