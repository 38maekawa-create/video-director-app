"""C-3: 音声品質自動評価のテスト"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from video_direction.analyzer.audio_evaluator import (
    evaluate_audio,
    AudioEvaluationResult,
    AudioAxisScore,
    AudioIssue,
    AudioSegmentInfo,
    AudioEvaluator,
    _evaluate_from_transcript,
    _estimate_audio_segments,
    _score_voice_clarity,
    _score_bgm_balance,
    _score_noise_level,
    _score_se_quality,
    _score_volume_consistency,
    _detect_audio_issues,
    _detect_ffmpeg_issues,
    _determine_audio_grade,
    _parse_duration_minutes,
    _timestamp_to_seconds,
    _seconds_to_timestamp,
    _run_silencedetect,
    _run_volumedetect,
    analyze_audio_with_ffmpeg,
    AUDIO_AXES,
    AUDIO_AXIS_LABELS,
    SUDDEN_VOLUME_CHANGE_THRESHOLD,
)
from video_direction.integrations.ai_dev5_connector import VideoData, HighlightScene


# === テストデータ ===

def _make_video_data(
    highlights=None,
    duration="30分",
    speakers="ホスト, ゲスト",
    video_type="対談インタビュー",
    transcript_method="whisper",
    full_transcript="",
):
    """テスト用VideoDataを生成"""
    return VideoData(
        title="テスト動画",
        duration=duration,
        speakers=speakers,
        video_type=video_type,
        highlights=highlights or [],
        main_topics=["トピック1"],
        transcript_method=transcript_method,
        full_transcript=full_transcript,
    )


def _make_highlights(count=5, with_punchline=True):
    """テスト用ハイライトリストを生成"""
    categories = ["実績数字", "パンチライン", "属性紹介", "TEKO価値", "メッセージ"]
    if not with_punchline:
        categories = ["実績数字", "属性紹介", "TEKO価値", "メッセージ", "属性紹介"]
    return [
        HighlightScene(
            timestamp=f"{i*5:02d}:00",
            speaker="ゲスト",
            text=f"テスト発言{i+1}",
            category=categories[i % len(categories)],
        )
        for i in range(count)
    ]


# === evaluate_audio メインテスト ===

class TestEvaluateAudio:
    """メインのevaluate_audio関数テスト"""

    def test_基本的な評価結果が返る(self):
        video = _make_video_data(highlights=_make_highlights(5))
        result = evaluate_audio(video)
        assert isinstance(result, AudioEvaluationResult)
        assert result.is_estimated is True
        assert result.analysis_method == "transcript_based"

    def test_5軸のスコアが生成される(self):
        video = _make_video_data(highlights=_make_highlights(5))
        result = evaluate_audio(video)
        assert len(result.axis_scores) == 5
        for axis_score in result.axis_scores:
            assert 0 <= axis_score.score <= 100

    def test_総合スコアが計算される(self):
        video = _make_video_data(highlights=_make_highlights(5))
        result = evaluate_audio(video)
        assert result.overall_score > 0

    def test_グレードが判定される(self):
        video = _make_video_data(highlights=_make_highlights(5))
        result = evaluate_audio(video)
        assert result.grade in ("S", "A", "B", "C", "D")

    def test_空のハイライトでも動作する(self):
        video = _make_video_data(highlights=[])
        result = evaluate_audio(video)
        assert isinstance(result, AudioEvaluationResult)
        assert len(result.axis_scores) == 5

    def test_ffmpeg無しでは推定フラグTrue(self):
        video = _make_video_data()
        result = evaluate_audio(video, use_ffmpeg=False)
        assert result.is_estimated is True


# === 音声セグメント推定テスト ===

class TestEstimateAudioSegments:
    """音声セグメント推定のテスト"""

    def test_ハイライトからセグメント生成(self):
        video = _make_video_data(highlights=_make_highlights(3))
        segments = _estimate_audio_segments(video)
        assert len(segments) >= 3  # 最低でもハイライト数分

    def test_パンチラインシーンはloud(self):
        highlights = [
            HighlightScene("05:00", "ゲスト", "すごい発言", "パンチライン"),
        ]
        video = _make_video_data(highlights=highlights)
        segments = _estimate_audio_segments(video)
        loud_segments = [s for s in segments if s.estimated_volume == "loud"]
        assert len(loud_segments) >= 1

    def test_トランスクリプトからもセグメント生成(self):
        transcript = "[01:00] ホスト: はい、こんにちは\n[01:30] ゲスト: よろしくお願いします"
        video = _make_video_data(full_transcript=transcript)
        segments = _estimate_audio_segments(video)
        speech = [s for s in segments if s.segment_type == "speech"]
        assert len(speech) >= 2

    def test_セグメントはスタブフラグTrue(self):
        video = _make_video_data(highlights=_make_highlights(1))
        segments = _estimate_audio_segments(video)
        assert all(s.is_stub for s in segments)


# === 各軸スコアテスト ===

class TestAxisScores:
    """各軸のスコア計算テスト"""

    def test_voice_clarity_whisperで加点(self):
        video = _make_video_data(transcript_method="whisper large-v3")
        segments = _estimate_audio_segments(video)
        score = _score_voice_clarity(video, segments)
        assert score.score >= 70  # whisper加算あり

    def test_voice_clarity_推定フラグ(self):
        video = _make_video_data()
        segments = _estimate_audio_segments(video)
        score = _score_voice_clarity(video, segments)
        assert score.is_estimated is True

    def test_bgm_balance_インタビュー形式で加点(self):
        video = _make_video_data(video_type="対談インタビュー")
        segments = _estimate_audio_segments(video)
        score = _score_bgm_balance(video, segments)
        assert score.score >= 60

    def test_noise_level_スタジオ収録で加点(self):
        video = _make_video_data(video_type="対談インタビュー")
        segments = _estimate_audio_segments(video)
        score = _score_noise_level(video, segments)
        assert score.score >= 70  # スタジオ加算

    def test_se_quality_ハイライト多で加点(self):
        video = _make_video_data(highlights=_make_highlights(10))
        segments = _estimate_audio_segments(video)
        score = _score_se_quality(video, segments)
        assert score.score >= 65  # 多数ハイライト加算

    def test_volume_consistency_2名対話で加点(self):
        video = _make_video_data(speakers="ホスト, ゲスト")
        segments = _estimate_audio_segments(video)
        score = _score_volume_consistency(video, segments)
        assert score.score >= 65  # 2名対話加算


# === 問題検出テスト ===

class TestAudioIssueDetection:
    """音声問題検出のテスト"""

    def test_長時間単独話者で情報提供(self):
        video = _make_video_data(
            duration="40分",
            speakers="ゲスト",
            highlights=_make_highlights(2, with_punchline=False),
        )
        segments = _estimate_audio_segments(video)
        issues = _detect_audio_issues(video, segments)
        balance_issues = [i for i in issues if i.issue_type == "balance"]
        assert len(balance_issues) >= 1

    def test_近接パンチラインで音量警告(self):
        # 1分以内にパンチラインが2つ
        highlights = [
            HighlightScene("05:00", "ゲスト", "発言1", "パンチライン"),
            HighlightScene("05:30", "ゲスト", "発言2", "パンチライン"),
        ]
        video = _make_video_data(highlights=highlights)
        segments = _estimate_audio_segments(video)
        issues = _detect_audio_issues(video, segments)
        volume_issues = [i for i in issues if i.issue_type == "volume"]
        assert len(volume_issues) >= 1


# === ユーティリティテスト ===

class TestUtilities:
    """ユーティリティ関数のテスト"""

    def test_グレード判定_S(self):
        assert _determine_audio_grade(95) == "S"

    def test_グレード判定_A(self):
        assert _determine_audio_grade(85) == "A"

    def test_グレード判定_B(self):
        assert _determine_audio_grade(70) == "B"

    def test_グレード判定_C(self):
        assert _determine_audio_grade(55) == "C"

    def test_グレード判定_D(self):
        assert _determine_audio_grade(40) == "D"

    def test_duration_parse_分(self):
        assert _parse_duration_minutes("30分") == 30.0

    def test_duration_parse_分秒(self):
        assert _parse_duration_minutes("30分30秒") == 30.5

    def test_duration_parse_MMSS(self):
        assert _parse_duration_minutes("30:30") == 30.5

    def test_duration_parse_空(self):
        assert _parse_duration_minutes("") == 0

    def test_timestamp_to_seconds(self):
        assert _timestamp_to_seconds("05:30") == 330

    def test_seconds_to_timestamp(self):
        assert _seconds_to_timestamp(330) == "05:30"

    def test_ffmpegスタブ(self):
        result = analyze_audio_with_ffmpeg("/dummy/path.mp4")
        assert result == {}


# === 定数テスト ===

class TestConstants:
    """定数のテスト"""

    def test_全軸にラベルがある(self):
        for axis in AUDIO_AXES:
            assert axis in AUDIO_AXIS_LABELS


# === AudioEvaluatorクラステスト ===

class TestAudioEvaluatorClass:
    """AudioEvaluatorクラスのテスト"""

    def test_初期化(self):
        evaluator = AudioEvaluator()
        assert isinstance(evaluator.has_ffmpeg, bool)
        assert isinstance(evaluator.has_ffprobe, bool)

    def test_extract_audio_stats_存在しないファイル(self):
        evaluator = AudioEvaluator()
        result = evaluator.extract_audio_stats("/nonexistent/path.mp4")
        assert result == {}

    def test_detect_audio_issues_空データ(self):
        evaluator = AudioEvaluator()
        issues = evaluator.detect_audio_issues({})
        assert isinstance(issues, list)

    def test_detect_audio_issues_クリッピング検出(self):
        evaluator = AudioEvaluator()
        stats = {"true_peak": 1.0}  # 0dBTP超過
        issues = evaluator.detect_audio_issues(stats)
        assert len(issues) >= 1
        assert issues[0]["issue_type"] == "volume"
        assert issues[0]["severity"] == "error"

    def test_detect_audio_issues_音量低すぎ(self):
        evaluator = AudioEvaluator()
        stats = {"loudness_lufs": -35.0}
        issues = evaluator.detect_audio_issues(stats)
        volume_issues = [i for i in issues if "小さい" in i["description"]]
        assert len(volume_issues) >= 1

    def test_detect_audio_issues_ノイズフロア高い(self):
        evaluator = AudioEvaluator()
        stats = {"noise_floor_estimate": -30.0}
        issues = evaluator.detect_audio_issues(stats)
        noise_issues = [i for i in issues if i["issue_type"] == "noise"]
        assert len(noise_issues) >= 1

    def test_detect_audio_issues_無音区間検出(self):
        evaluator = AudioEvaluator()
        stats = {
            "silence_ranges": [
                {"start": 10.0, "end": 22.0, "duration": 12.0},
            ],
        }
        issues = evaluator.detect_audio_issues(stats)
        silence_issues = [i for i in issues if i["issue_type"] == "clarity"]
        assert len(silence_issues) >= 1

    def test_detect_audio_issues_急激な音量変化(self):
        evaluator = AudioEvaluator()
        stats = {
            "sudden_volume_changes": [
                {"time": 30.0, "change_db": 20.0, "direction": "up"},
            ],
        }
        issues = evaluator.detect_audio_issues(stats)
        volume_issues = [i for i in issues if "急激" in i["description"]]
        assert len(volume_issues) >= 1

    def test_evaluate_overall_存在しないファイル(self):
        evaluator = AudioEvaluator()
        # ファイルが存在しない場合は推定評価にフォールバック
        result = evaluator.evaluate_overall("/nonexistent/path.mp4")
        assert isinstance(result, dict)
        assert "overall_score" in result
        assert "grade" in result
        assert "axis_scores" in result
        assert "issues" in result
        assert result["is_estimated"] is True

    def test_evaluate_overall_VideoData付き(self):
        evaluator = AudioEvaluator()
        video = _make_video_data(highlights=_make_highlights(5))
        result = evaluator.evaluate_overall("/nonexistent/path.mp4", video)
        assert isinstance(result, dict)
        assert result["overall_score"] > 0

    def test_detect_audio_issues_返り値の形式(self):
        evaluator = AudioEvaluator()
        stats = {"true_peak": 1.0, "loudness_lufs": -35.0}
        issues = evaluator.detect_audio_issues(stats)
        for issue in issues:
            assert "timestamp" in issue
            assert "issue_type" in issue
            assert "severity" in issue
            assert "description" in issue
            assert "suggestion" in issue


# === silencedetect / volumedetect テスト ===

class TestSilenceAndVolumeDetect:
    """無音検出・音量変化検出のテスト"""

    def test_silencedetect_ファイルなし(self):
        result = _run_silencedetect("/nonexistent/path.mp4")
        assert result == {}

    def test_volumedetect_ファイルなし(self):
        result = _run_volumedetect("/nonexistent/path.mp4")
        assert result == {}

    def test_閾値定数が定義されている(self):
        assert SUDDEN_VOLUME_CHANGE_THRESHOLD > 0


# === ffmpeg問題検出の拡張テスト ===

class TestFfmpegIssueDetectionExtended:
    """ffmpeg問題検出の拡張テスト（無音・音量変化）"""

    def test_無音区間5秒以上でwarning(self):
        ffmpeg_data = {
            "silence_ranges": [
                {"start": 5.0, "end": 11.0, "duration": 6.0},
            ],
        }
        issues = _detect_ffmpeg_issues(ffmpeg_data)
        silence_issues = [i for i in issues if i.issue_type == "clarity"]
        assert len(silence_issues) >= 1
        assert silence_issues[0].severity == "warning"

    def test_無音区間10秒以上でerror(self):
        ffmpeg_data = {
            "silence_ranges": [
                {"start": 5.0, "end": 18.0, "duration": 13.0},
            ],
        }
        issues = _detect_ffmpeg_issues(ffmpeg_data)
        silence_issues = [i for i in issues if i.issue_type == "clarity" and i.severity == "error"]
        assert len(silence_issues) >= 1

    def test_急激な音量変化でwarning(self):
        ffmpeg_data = {
            "sudden_volume_changes": [
                {"time": 45.0, "change_db": 18.5, "direction": "up"},
            ],
        }
        issues = _detect_ffmpeg_issues(ffmpeg_data)
        volume_issues = [i for i in issues if "急激" in i.description]
        assert len(volume_issues) >= 1

    def test_無音なしで問題なし(self):
        ffmpeg_data = {
            "silence_ranges": [],
            "sudden_volume_changes": [],
        }
        issues = _detect_ffmpeg_issues(ffmpeg_data)
        # 無音・音量変化関連のissueがないこと
        silence_volume_issues = [
            i for i in issues
            if i.issue_type == "clarity" or "急激" in i.description
        ]
        assert len(silence_volume_issues) == 0
