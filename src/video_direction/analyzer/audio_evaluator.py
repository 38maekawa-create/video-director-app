from __future__ import annotations
"""C-3: 音声品質自動評価

BGMと会話音声のバランス + ノイズレベル検出 + SE適切性評価。

Phase 2実装:
- ffmpeg/実映像なしでもモック・スタブで動作する設計
- 文字起こしデータ・メタデータからの推定評価
- 評価ロジックの骨格とデータ構造を先行実装

Phase 3実装:
- ffmpegによる実際の音声解析（LUFS/RMS/ピーク/ダイナミックレンジ）
- ffprobe による音声トラック情報取得
- ffmpeg が無い環境では推定評価にフォールバック
"""

import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Optional
from ..integrations.ai_dev5_connector import VideoData, HighlightScene

logger = logging.getLogger(__name__)

# ffmpeg/ffprobe の利用可否を起動時に判定
HAS_FFMPEG = shutil.which("ffmpeg") is not None
HAS_FFPROBE = shutil.which("ffprobe") is not None


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
    """ffmpegによる実測評価

    ffmpeg/ffprobe を使って音声の実測値を取得し、5軸評価を行う。
    ffmpeg が利用できない場合や解析に失敗した場合は推定評価にフォールバックする。
    """
    # ffmpeg が無い、またはファイルが存在しない場合はフォールバック
    if not HAS_FFMPEG or not os.path.isfile(audio_path):
        logger.warning(
            "ffmpeg解析不可（HAS_FFMPEG=%s, file_exists=%s）: 推定評価にフォールバック",
            HAS_FFMPEG, os.path.isfile(audio_path),
        )
        return _evaluate_from_transcript(video_data)

    # ffmpeg で実測値を取得
    ffmpeg_data = analyze_audio_with_ffmpeg(audio_path)
    if not ffmpeg_data:
        logger.warning("ffmpeg解析結果が空: 推定評価にフォールバック")
        return _evaluate_from_transcript(video_data)

    # 実測値に基づく5軸評価
    axis_scores = []
    all_issues = []

    # セグメント情報は文字起こしベースのものを併用
    segments = _estimate_audio_segments(video_data)

    # 1. volume_balance（会話音声とBGMのバランス）
    axis_scores.append(_score_volume_balance_ffmpeg(ffmpeg_data, video_data))

    # 2. noise_level（ノイズレベル）
    axis_scores.append(_score_noise_level_ffmpeg(ffmpeg_data))

    # 3. dynamic_range（ダイナミックレンジ）
    axis_scores.append(_score_dynamic_range_ffmpeg(ffmpeg_data))

    # 4. se_quality（SE適切性 — ffmpegだけでは判定困難、推定値と併用）
    axis_scores.append(_score_se_quality(video_data, segments))

    # 5. overall（総合音声品質）
    axis_scores.append(_score_overall_audio_ffmpeg(ffmpeg_data))

    # 問題検出（ffmpeg実測値ベース）
    all_issues = _detect_ffmpeg_issues(ffmpeg_data)
    # 推定ベースの問題も追加
    all_issues.extend(_detect_audio_issues(video_data, segments))

    # 集計
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
        is_estimated=False,
        analysis_method="ffmpeg_analysis",
    )


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


# === ffmpeg解析 ===

def analyze_audio_with_ffmpeg(audio_path: str) -> dict:
    """ffmpegで音声を解析する

    ffprobe で音声トラック情報を取得し、ffmpeg で LUFS/RMS/ピーク値を測定する。
    ffmpeg が利用できない場合やファイルが存在しない場合は空辞書を返す。

    Args:
        audio_path: 音声/動画ファイルパス

    Returns:
        dict: 音声解析結果。キー:
            - sample_rate (int): サンプルレート (Hz)
            - bit_rate (int): ビットレート (bps)
            - channels (int): チャンネル数
            - codec_name (str): コーデック名
            - duration (float): 音声の長さ（秒）
            - loudness_lufs (float): 統合ラウドネス（LUFS）
            - loudness_range (float): ラウドネスレンジ（LU）
            - true_peak (float): トゥルーピーク（dBTP）
            - rms_level (float): RMS平均レベル（dB）
            - rms_peak (float): RMSピーク（dB）
            - dynamic_range (float): ダイナミックレンジ（dB） = rms_peak - noise_floor推定
            - noise_floor_estimate (float): ノイズフロア推定値（dB）

        ffmpegが無い/ファイルが無い/エラー発生時は空辞書 {} を返す。
    """
    if not HAS_FFMPEG or not os.path.isfile(audio_path):
        return {}

    result = {}

    # Step 1: ffprobe で音声トラック情報を取得
    try:
        probe_data = _run_ffprobe(audio_path)
        if probe_data:
            result.update(probe_data)
    except Exception as e:
        logger.warning("ffprobe 実行エラー: %s", e)

    # Step 2: loudnorm フィルタで LUFS 測定
    try:
        loudness_data = _run_loudnorm(audio_path)
        if loudness_data:
            result.update(loudness_data)
    except Exception as e:
        logger.warning("loudnorm 測定エラー: %s", e)

    # Step 3: astats フィルタで RMS/ピーク測定
    try:
        stats_data = _run_astats(audio_path)
        if stats_data:
            result.update(stats_data)
    except Exception as e:
        logger.warning("astats 測定エラー: %s", e)

    # Step 4: ダイナミックレンジ計算
    if "rms_peak" in result and "rms_level" in result:
        # ダイナミックレンジ = ピーク - 平均RMS の近似
        result["dynamic_range"] = round(
            result["rms_peak"] - result["rms_level"], 2
        )
    if "rms_level" in result:
        # ノイズフロアの推定: 平均RMSの-20dB以下をノイズフロアとみなす
        result["noise_floor_estimate"] = round(result["rms_level"] - 20.0, 2)

    return result


def _run_ffprobe(audio_path: str) -> dict:
    """ffprobe で音声ストリーム情報を取得する"""
    if not HAS_FFPROBE:
        return {}

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-select_streams", "a:0",  # 最初の音声ストリーム
        audio_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        logger.warning("ffprobe 失敗 (returncode=%d): %s", proc.returncode, proc.stderr[:200])
        return {}

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}

    streams = data.get("streams", [])
    if not streams:
        return {}

    stream = streams[0]
    result = {}

    # サンプルレート
    if "sample_rate" in stream:
        try:
            result["sample_rate"] = int(stream["sample_rate"])
        except (ValueError, TypeError):
            pass

    # ビットレート
    if "bit_rate" in stream:
        try:
            result["bit_rate"] = int(stream["bit_rate"])
        except (ValueError, TypeError):
            pass

    # チャンネル数
    if "channels" in stream:
        try:
            result["channels"] = int(stream["channels"])
        except (ValueError, TypeError):
            pass

    # コーデック名
    if "codec_name" in stream:
        result["codec_name"] = stream["codec_name"]

    # 音声の長さ
    if "duration" in stream:
        try:
            result["duration"] = float(stream["duration"])
        except (ValueError, TypeError):
            pass

    return result


def _run_loudnorm(audio_path: str) -> dict:
    """ffmpeg loudnorm フィルタで LUFS/ラウドネスレンジ/トゥルーピークを測定する"""
    cmd = [
        "ffmpeg",
        "-i", audio_path,
        "-af", "loudnorm=print_format=json",
        "-f", "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        logger.warning("loudnorm 失敗 (returncode=%d)", proc.returncode)
        return {}

    # loudnorm の JSON 出力は stderr に含まれる
    stderr = proc.stderr
    # JSON ブロックを抽出（最後の {...} を探す）
    json_match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr, re.DOTALL)
    if not json_match:
        logger.warning("loudnorm: JSON出力が見つからない")
        return {}

    try:
        loudnorm_data = json.loads(json_match.group())
    except json.JSONDecodeError:
        logger.warning("loudnorm: JSONパースエラー")
        return {}

    result = {}

    # 統合ラウドネス (LUFS)
    if "input_i" in loudnorm_data:
        try:
            result["loudness_lufs"] = float(loudnorm_data["input_i"])
        except (ValueError, TypeError):
            pass

    # ラウドネスレンジ (LU)
    if "input_lra" in loudnorm_data:
        try:
            result["loudness_range"] = float(loudnorm_data["input_lra"])
        except (ValueError, TypeError):
            pass

    # トゥルーピーク (dBTP)
    if "input_tp" in loudnorm_data:
        try:
            result["true_peak"] = float(loudnorm_data["input_tp"])
        except (ValueError, TypeError):
            pass

    return result


def _run_astats(audio_path: str) -> dict:
    """ffmpeg astats フィルタで RMS/ピーク値を測定する"""
    cmd = [
        "ffmpeg",
        "-i", audio_path,
        "-af", "astats=metadata=1:reset=1,ametadata=mode=print",
        "-f", "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        logger.warning("astats 失敗 (returncode=%d)", proc.returncode)
        return {}

    stderr = proc.stderr

    # astats の出力から RMS レベルとピークを抽出
    # 出力形式: lavfi.astats.Overall.RMS_level=-XX.XX
    rms_levels = []
    rms_peaks = []

    for line in stderr.split("\n"):
        # Overall RMS レベル
        m = re.search(r"lavfi\.astats\.Overall\.RMS_level=([-\d.]+)", line)
        if m:
            try:
                rms_levels.append(float(m.group(1)))
            except ValueError:
                pass
        # Overall RMS ピーク
        m = re.search(r"lavfi\.astats\.Overall\.RMS_peak=([-\d.]+)", line)
        if m:
            try:
                rms_peaks.append(float(m.group(1)))
            except ValueError:
                pass

    result = {}

    # RMS 平均レベル: 全フレームの平均
    if rms_levels:
        # -inf を除外してから平均を取る
        valid_levels = [v for v in rms_levels if v > -150.0]
        if valid_levels:
            result["rms_level"] = round(sum(valid_levels) / len(valid_levels), 2)

    # RMS ピーク: 全フレームの最大値
    if rms_peaks:
        valid_peaks = [v for v in rms_peaks if v > -150.0]
        if valid_peaks:
            result["rms_peak"] = round(max(valid_peaks), 2)

    return result


# === ffmpeg 実測値ベースのスコアリング ===

def _score_volume_balance_ffmpeg(ffmpeg_data: dict, video_data: VideoData) -> AudioAxisScore:
    """会話音声とBGMのバランス（ffmpeg実測値ベース）"""
    score = 70  # ベースライン
    notes = []
    measured = ""

    lufs = ffmpeg_data.get("loudness_lufs")
    if lufs is not None:
        measured = f"LUFS: {lufs:.1f}"
        notes.append(f"統合ラウドネス: {lufs:.1f} LUFS")

        # 推奨値 -14 LUFS（会話音声）との乖離を評価
        deviation = abs(lufs - RECOMMENDED_VOICE_DB)
        if deviation <= 2:
            score += 20
            notes.append("推奨レベル(-14 LUFS)にほぼ一致: 優秀")
        elif deviation <= 5:
            score += 10
            notes.append("推奨レベルとの差は許容範囲内")
        elif deviation <= 10:
            notes.append("推奨レベルとやや乖離: 調整推奨")
            score -= 5
        else:
            notes.append("推奨レベルと大きく乖離: 要調整")
            score -= 15

    # ラウドネスレンジで変動幅を評価
    lra = ffmpeg_data.get("loudness_range")
    if lra is not None:
        notes.append(f"ラウドネスレンジ: {lra:.1f} LU")
        if 5 <= lra <= 15:
            score += 5
            notes.append("音量変動幅は適切")
        elif lra > 20:
            score -= 10
            notes.append("音量変動が大きすぎる: コンプレッサー推奨")
        elif lra < 3:
            score -= 5
            notes.append("音量変動が小さすぎる: ダイナミクスが不足")

    score = min(100, max(0, score))
    return AudioAxisScore(
        axis="volume_balance",
        label="音量バランス",
        score=score,
        notes=notes,
        measured_value=measured,
        is_estimated=False,
    )


def _score_noise_level_ffmpeg(ffmpeg_data: dict) -> AudioAxisScore:
    """ノイズレベル（ffmpeg実測値ベース）"""
    score = 70  # ベースライン
    notes = []
    measured = ""

    noise_floor = ffmpeg_data.get("noise_floor_estimate")
    rms_level = ffmpeg_data.get("rms_level")

    if rms_level is not None:
        measured = f"RMS平均: {rms_level:.1f} dB"
        notes.append(f"RMS平均レベル: {rms_level:.1f} dB")

    if noise_floor is not None:
        notes.append(f"ノイズフロア推定: {noise_floor:.1f} dB")
        if noise_floor < MAX_NOISE_FLOOR:
            score += 20
            notes.append("ノイズフロアが十分低い: 優秀")
        elif noise_floor < MAX_NOISE_FLOOR + 10:
            score += 10
            notes.append("ノイズフロアは許容範囲内")
        elif noise_floor < MAX_NOISE_FLOOR + 20:
            notes.append("ノイズが目立つ可能性: ノイズリダクション推奨")
            score -= 10
        else:
            notes.append("ノイズレベルが高い: 要改善")
            score -= 20

    score = min(100, max(0, score))
    return AudioAxisScore(
        axis="noise_level",
        label=AUDIO_AXIS_LABELS["noise_level"],
        score=score,
        notes=notes,
        measured_value=measured,
        is_estimated=False,
    )


def _score_dynamic_range_ffmpeg(ffmpeg_data: dict) -> AudioAxisScore:
    """ダイナミックレンジ（ffmpeg実測値ベース）"""
    score = 70  # ベースライン
    notes = []
    measured = ""

    dr = ffmpeg_data.get("dynamic_range")
    true_peak = ffmpeg_data.get("true_peak")

    if dr is not None:
        measured = f"DR: {dr:.1f} dB"
        notes.append(f"ダイナミックレンジ: {dr:.1f} dB")
        # 対談動画の推奨ダイナミックレンジ: 8-20 dB
        if 8 <= dr <= 20:
            score += 20
            notes.append("ダイナミックレンジが適切: 聴きやすい")
        elif 5 <= dr < 8:
            score += 10
            notes.append("ダイナミックレンジがやや狭い: 平坦な印象")
        elif 20 < dr <= 30:
            score += 5
            notes.append("ダイナミックレンジが広め: コンプレッサー検討")
        elif dr > 30:
            notes.append("ダイナミックレンジが広すぎる: リミッター推奨")
            score -= 10
        else:
            notes.append("ダイナミックレンジが極端に狭い: 過度な圧縮")
            score -= 10

    if true_peak is not None:
        notes.append(f"トゥルーピーク: {true_peak:.1f} dBTP")
        if true_peak > -1.0:
            score -= 15
            notes.append("トゥルーピークが高すぎる: クリッピング危険")
        elif true_peak > -3.0:
            score -= 5
            notes.append("トゥルーピークがやや高い: マージン不足")
        else:
            score += 5
            notes.append("トゥルーピークは安全範囲内")

    score = min(100, max(0, score))
    return AudioAxisScore(
        axis="dynamic_range",
        label="ダイナミックレンジ",
        score=score,
        notes=notes,
        measured_value=measured,
        is_estimated=False,
    )


def _score_overall_audio_ffmpeg(ffmpeg_data: dict) -> AudioAxisScore:
    """総合音声品質（ffmpeg実測値ベース）"""
    score = 65  # ベースライン
    notes = []
    measured_parts = []

    # サンプルレート評価
    sr = ffmpeg_data.get("sample_rate")
    if sr is not None:
        measured_parts.append(f"{sr}Hz")
        if sr >= 48000:
            score += 10
            notes.append(f"サンプルレート{sr}Hz: プロフェッショナル品質")
        elif sr >= 44100:
            score += 5
            notes.append(f"サンプルレート{sr}Hz: CD品質")
        else:
            notes.append(f"サンプルレート{sr}Hz: 低品質")
            score -= 5

    # ビットレート評価
    br = ffmpeg_data.get("bit_rate")
    if br is not None:
        br_kbps = br / 1000
        measured_parts.append(f"{br_kbps:.0f}kbps")
        if br_kbps >= 256:
            score += 5
            notes.append(f"ビットレート{br_kbps:.0f}kbps: 高品質")
        elif br_kbps >= 128:
            score += 2
        else:
            notes.append(f"ビットレート{br_kbps:.0f}kbps: 低品質")
            score -= 5

    # チャンネル数
    ch = ffmpeg_data.get("channels")
    if ch is not None:
        measured_parts.append(f"{ch}ch")
        if ch >= 2:
            score += 3
            notes.append(f"{ch}チャンネル: ステレオ以上")
        else:
            notes.append("モノラル: ステレオ推奨")

    measured = ", ".join(measured_parts) if measured_parts else ""

    score = min(100, max(0, score))
    return AudioAxisScore(
        axis="overall",
        label="総合音声品質",
        score=score,
        notes=notes,
        measured_value=measured,
        is_estimated=False,
    )


def _detect_ffmpeg_issues(ffmpeg_data: dict) -> list:
    """ffmpeg実測値ベースの問題検出"""
    issues = []

    # トゥルーピークが0 dBTP超過 → クリッピング
    true_peak = ffmpeg_data.get("true_peak")
    if true_peak is not None and true_peak > 0.0:
        issues.append(AudioIssue(
            timestamp="全体",
            issue_type="volume",
            severity="error",
            description=f"トゥルーピーク {true_peak:.1f} dBTP: クリッピングが発生",
            suggestion="リミッターを適用し、トゥルーピークを -1.0 dBTP 以下に抑える",
        ))
    elif true_peak is not None and true_peak > -1.0:
        issues.append(AudioIssue(
            timestamp="全体",
            issue_type="volume",
            severity="warning",
            description=f"トゥルーピーク {true_peak:.1f} dBTP: クリッピングの危険",
            suggestion="トゥルーピークを -1.0 dBTP 以下に調整推奨",
        ))

    # ラウドネスが極端に低い/高い
    lufs = ffmpeg_data.get("loudness_lufs")
    if lufs is not None:
        if lufs < -30:
            issues.append(AudioIssue(
                timestamp="全体",
                issue_type="volume",
                severity="warning",
                description=f"統合ラウドネス {lufs:.1f} LUFS: 音量が非常に小さい",
                suggestion="ノーマライズ処理で -14 LUFS 前後に調整推奨",
            ))
        elif lufs > -5:
            issues.append(AudioIssue(
                timestamp="全体",
                issue_type="volume",
                severity="error",
                description=f"統合ラウドネス {lufs:.1f} LUFS: 音量が大きすぎる",
                suggestion="音量を -14 LUFS 前後に下げることを推奨",
            ))

    # ノイズフロアが高い
    noise_floor = ffmpeg_data.get("noise_floor_estimate")
    if noise_floor is not None and noise_floor > MAX_NOISE_FLOOR + 15:
        issues.append(AudioIssue(
            timestamp="全体",
            issue_type="noise",
            severity="warning",
            description=f"ノイズフロア推定 {noise_floor:.1f} dB: バックグラウンドノイズが顕著",
            suggestion="ノイズリダクション処理を推奨",
        ))

    return issues
