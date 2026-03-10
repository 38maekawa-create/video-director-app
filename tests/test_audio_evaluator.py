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
    _evaluate_from_transcript,
    _estimate_audio_segments,
    _score_voice_clarity,
    _score_bgm_balance,
    _score_noise_level,
    _score_se_quality,
    _score_volume_consistency,
    _detect_audio_issues,
    _determine_audio_grade,
    _parse_duration_minutes,
    _timestamp_to_seconds,
    _seconds_to_timestamp,
    analyze_audio_with_ffmpeg,
    AUDIO_AXES,
    AUDIO_AXIS_LABELS,
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
