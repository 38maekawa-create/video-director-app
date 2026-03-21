"""タイミング3: 自動QCパイプライン Phase1 テスト

Whisper / GPT-4o / ffmpeg 等の外部依存はモックして、
ロジック部分（突合・フィルタリング・データ構造）を網羅的にテスト。
"""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from video_direction.qc.whisper_transcriber import (
    TranscriptSegment,
    TranscriptResult,
)
from video_direction.qc.frame_extractor import (
    ExtractedFrame,
    detect_telop_frames,
)
from video_direction.qc.telop_reader import (
    TelopReading,
    TelopReadResult,
)
from video_direction.qc.qc_comparator import (
    QCIssue,
    QCResult,
    _normalize_text,
    _compute_similarity,
    _find_differences,
    compare_single,
    run_qc_comparison,
)


# ===================================================================
# TranscriptSegment / TranscriptResult テスト
# ===================================================================

class TestTranscriptSegment:
    def test_timecode_format(self):
        seg = TranscriptSegment(start=125.0, end=130.0, text="テスト")
        assert seg.start_timecode == "02:05"
        assert seg.end_timecode == "02:10"

    def test_timecode_zero(self):
        seg = TranscriptSegment(start=0.0, end=5.0, text="開始")
        assert seg.start_timecode == "00:00"
        assert seg.end_timecode == "00:05"

    def test_timecode_long_video(self):
        seg = TranscriptSegment(start=3661.0, end=3665.0, text="長い動画")
        assert seg.start_timecode == "61:01"


class TestTranscriptResult:
    def _make_result(self):
        return TranscriptResult(
            segments=[
                TranscriptSegment(start=0.0, end=3.0, text="最初のセグメント"),
                TranscriptSegment(start=3.0, end=6.0, text="2番目のセグメント"),
                TranscriptSegment(start=10.0, end=15.0, text="離れたセグメント"),
                TranscriptSegment(start=30.0, end=35.0, text="キャッシュフローが重要です"),
            ],
            full_text="最初のセグメント 2番目のセグメント 離れたセグメント キャッシュフローが重要です",
            language="ja",
            duration=35.0,
        )

    def test_get_text_at_exact_match(self):
        result = self._make_result()
        segs = result.get_text_at(1.0, window_sec=1.0)
        assert len(segs) == 1
        assert segs[0].text == "最初のセグメント"

    def test_get_text_at_overlap(self):
        result = self._make_result()
        segs = result.get_text_at(2.5, window_sec=2.0)
        assert len(segs) == 2  # 最初と2番目の両方にかかる

    def test_get_text_at_no_match(self):
        result = self._make_result()
        segs = result.get_text_at(20.0, window_sec=1.0)
        assert len(segs) == 0

    def test_get_text_at_wide_window(self):
        result = self._make_result()
        segs = result.get_text_at(5.0, window_sec=10.0)
        assert len(segs) == 3  # 最初3つ

    def test_to_dict_from_dict_roundtrip(self):
        result = self._make_result()
        data = result.to_dict()
        restored = TranscriptResult.from_dict(data)
        assert len(restored.segments) == 4
        assert restored.segments[0].text == "最初のセグメント"
        assert restored.full_text == result.full_text
        assert restored.language == "ja"
        assert restored.duration == 35.0


# ===================================================================
# ExtractedFrame / テロップフィルタリング テスト
# ===================================================================

class TestExtractedFrame:
    def test_timecode(self):
        f = ExtractedFrame(path=Path("/tmp/f.jpg"), timestamp_sec=125.0)
        assert f.timecode == "02:05"

    def test_to_dict(self):
        f = ExtractedFrame(path=Path("/tmp/f.jpg"), timestamp_sec=10.0, has_telop=True)
        d = f.to_dict()
        assert d["timestamp_sec"] == 10.0
        assert d["has_telop"] is True
        assert d["timecode"] == "00:10"


class TestDetectTelopFrames:
    """OpenCVが無い場合のフォールバック動作をテスト"""

    def test_no_cv2_returns_all_frames(self):
        """OpenCV未インストール時は全フレームをテロップありとして返す"""
        frames = [
            ExtractedFrame(path=Path("/tmp/f1.jpg"), timestamp_sec=0.0),
            ExtractedFrame(path=Path("/tmp/f2.jpg"), timestamp_sec=2.0),
        ]
        with patch("video_direction.qc.frame_extractor.HAS_CV2", False):
            result = detect_telop_frames(frames)
        assert len(result) == 2
        assert all(f.has_telop for f in result)


# ===================================================================
# TelopReading / TelopReadResult テスト
# ===================================================================

class TestTelopReading:
    def test_to_dict(self):
        r = TelopReading(
            timestamp_sec=10.0,
            timecode="00:10",
            telop_texts=["テロップ1"],
            has_telop=True,
            confidence="high",
        )
        d = r.to_dict()
        assert d["timecode"] == "00:10"
        assert d["telop_texts"] == ["テロップ1"]

    def test_from_dict(self):
        data = {
            "timestamp_sec": 5.0,
            "timecode": "00:05",
            "telop_texts": ["テスト"],
            "has_telop": True,
            "confidence": "medium",
        }
        r = TelopReading.from_dict(data)
        assert r.timestamp_sec == 5.0
        assert r.confidence == "medium"


class TestTelopReadResult:
    def test_roundtrip(self):
        result = TelopReadResult(
            readings=[
                TelopReading(timestamp_sec=0.0, timecode="00:00", telop_texts=["a"]),
                TelopReading(timestamp_sec=2.0, timecode="00:02", telop_texts=["b"], has_telop=False),
            ],
            total_frames=5,
            telop_frames=1,
        )
        d = result.to_dict()
        restored = TelopReadResult.from_dict(d)
        assert restored.total_frames == 5
        assert restored.telop_frames == 1
        assert len(restored.readings) == 2


# ===================================================================
# QCComparator テスト（コア突合ロジック）
# ===================================================================

class TestNormalizeText:
    def test_basic_normalization(self):
        assert _normalize_text("キャッシュフロー") == _normalize_text("キャッシュフロー")

    def test_removes_punctuation(self):
        assert _normalize_text("これは、テスト。です！") == "これはテストです"

    def test_fullwidth_halfwidth(self):
        # NFKC正規化で全角→半角
        assert _normalize_text("ＡＢＣ") == "abc"

    def test_removes_spaces(self):
        assert _normalize_text("テスト テキスト") == "テストテキスト"

    def test_removes_brackets(self):
        assert _normalize_text("「テスト」") == "テスト"


class TestComputeSimilarity:
    def test_identical(self):
        assert _compute_similarity("同じテキスト", "同じテキスト") == 1.0

    def test_identical_after_normalization(self):
        sim = _compute_similarity("テスト！", "テスト")
        assert sim == 1.0

    def test_empty_strings(self):
        assert _compute_similarity("", "") == 1.0

    def test_one_empty(self):
        assert _compute_similarity("テスト", "") == 0.0
        assert _compute_similarity("", "テスト") == 0.0

    def test_similar(self):
        sim = _compute_similarity("キャッシュフロー", "キャシュフロー")
        assert 0.5 < sim < 1.0  # 高いが完全一致ではない

    def test_very_different(self):
        sim = _compute_similarity("こんにちは", "さようなら")
        assert sim < 0.5


class TestFindDifferences:
    def test_single_char_typo(self):
        diff = _find_differences("キャッシュフロー", "キャシュフロー")
        # 「ッ」が脱落として検出される
        assert "脱落" in diff or "キャッシュ" in diff or "キャシュ" in diff

    def test_missing_text(self):
        diff = _find_differences("重要なポイント", "重要なポイ")
        assert "脱落" in diff

    def test_extra_text(self):
        diff = _find_differences("テスト", "テストです")
        assert "余分" in diff

    def test_normalized_identical(self):
        diff = _find_differences("テスト！", "テスト")
        assert "正規化後は一致" in diff


class TestCompareSingle:
    def _make_transcript(self):
        return TranscriptResult(
            segments=[
                TranscriptSegment(start=28.0, end=33.0, text="キャッシュフローが重要です"),
                TranscriptSegment(start=33.0, end=38.0, text="特に不動産投資においては"),
            ],
            full_text="キャッシュフローが重要です 特に不動産投資においては",
        )

    def test_no_telop_no_issues(self):
        reading = TelopReading(
            timestamp_sec=30.0, timecode="00:30",
            telop_texts=[], has_telop=False,
        )
        transcript = self._make_transcript()
        issues = compare_single(reading, transcript)
        assert len(issues) == 0

    def test_exact_match_no_issues(self):
        reading = TelopReading(
            timestamp_sec=30.0, timecode="00:30",
            telop_texts=["キャッシュフローが重要です"], has_telop=True,
        )
        transcript = self._make_transcript()
        issues = compare_single(reading, transcript)
        assert len(issues) == 0

    def test_typo_detected(self):
        reading = TelopReading(
            timestamp_sec=30.0, timecode="00:30",
            telop_texts=["キャシュフローが重要です"],  # キャッシュ→キャシュ
            has_telop=True,
        )
        transcript = self._make_transcript()
        issues = compare_single(reading, transcript, similarity_threshold=0.7)
        assert len(issues) >= 1
        assert issues[0].issue_type in ("typo", "mismatch")

    def test_no_matching_segment_warning(self):
        reading = TelopReading(
            timestamp_sec=100.0, timecode="01:40",  # 該当セグメントなし
            telop_texts=["何かのテロップ"], has_telop=True,
        )
        transcript = self._make_transcript()
        issues = compare_single(reading, transcript, time_window_sec=3.0)
        assert len(issues) == 1
        assert issues[0].issue_type == "extra_text"
        assert issues[0].severity == "warning"

    def test_large_mismatch(self):
        reading = TelopReading(
            timestamp_sec=30.0, timecode="00:30",
            telop_texts=["全く関係ないテキスト"], has_telop=True,
        )
        transcript = self._make_transcript()
        issues = compare_single(reading, transcript, similarity_threshold=0.7)
        assert len(issues) >= 1
        assert issues[0].issue_type == "mismatch"
        assert issues[0].severity == "error"


class TestRunQCComparison:
    def test_all_correct_passes(self):
        transcript = TranscriptResult(
            segments=[
                TranscriptSegment(start=0.0, end=5.0, text="正しいテキスト"),
            ],
        )
        telop_result = TelopReadResult(
            readings=[
                TelopReading(
                    timestamp_sec=2.0, timecode="00:02",
                    telop_texts=["正しいテキスト"], has_telop=True,
                ),
            ],
            total_frames=1,
            telop_frames=1,
        )
        result = run_qc_comparison(transcript, telop_result, project_id="TEST001")
        assert result.status == "passed"
        assert result.error_count == 0
        assert result.checked_frames == 1

    def test_typo_fails(self):
        transcript = TranscriptResult(
            segments=[
                TranscriptSegment(start=0.0, end=5.0, text="キャッシュフロー"),
            ],
        )
        telop_result = TelopReadResult(
            readings=[
                TelopReading(
                    timestamp_sec=2.0, timecode="00:02",
                    telop_texts=["キャシュフロー"], has_telop=True,
                ),
            ],
            total_frames=1,
            telop_frames=1,
        )
        result = run_qc_comparison(transcript, telop_result, project_id="TEST002")
        assert result.status == "failed"
        assert result.error_count >= 1

    def test_empty_telop_passes(self):
        transcript = TranscriptResult(
            segments=[
                TranscriptSegment(start=0.0, end=5.0, text="テスト"),
            ],
        )
        telop_result = TelopReadResult(
            readings=[
                TelopReading(
                    timestamp_sec=2.0, timecode="00:02",
                    telop_texts=[], has_telop=False,
                ),
            ],
            total_frames=1,
            telop_frames=0,
        )
        result = run_qc_comparison(transcript, telop_result)
        assert result.status == "passed"
        assert result.checked_frames == 0

    def test_multiple_frames(self):
        transcript = TranscriptResult(
            segments=[
                TranscriptSegment(start=0.0, end=5.0, text="セグメント1"),
                TranscriptSegment(start=10.0, end=15.0, text="セグメント2"),
                TranscriptSegment(start=20.0, end=25.0, text="セグメント3"),
            ],
        )
        telop_result = TelopReadResult(
            readings=[
                TelopReading(
                    timestamp_sec=2.0, timecode="00:02",
                    telop_texts=["セグメント1"], has_telop=True,
                ),
                TelopReading(
                    timestamp_sec=12.0, timecode="00:12",
                    telop_texts=["セグメント2"], has_telop=True,
                ),
                TelopReading(
                    timestamp_sec=22.0, timecode="00:22",
                    telop_texts=["セグメント3の誤字"], has_telop=True,
                ),
            ],
            total_frames=3,
            telop_frames=3,
        )
        result = run_qc_comparison(transcript, telop_result)
        assert result.checked_frames == 3
        # 最後のフレームで不一致が出るはず
        assert result.error_count >= 1


# ===================================================================
# QCResult データ構造テスト
# ===================================================================

class TestQCResult:
    def test_to_dict_from_dict_roundtrip(self):
        result = QCResult(
            project_id="PRJ001",
            video_path="/tmp/test.mp4",
            issues=[
                QCIssue(
                    timestamp_sec=30.0, timecode="00:30",
                    issue_type="typo", severity="error",
                    spoken_text="正解", telop_text="誤字",
                    description="テスト", similarity=0.8,
                ),
            ],
            total_telop_frames=10,
            checked_frames=5,
            error_count=1,
            warning_count=0,
            status="failed",
        )
        d = result.to_dict()
        restored = QCResult.from_dict(d)
        assert restored.project_id == "PRJ001"
        assert restored.status == "failed"
        assert restored.error_count == 1
        assert len(restored.issues) == 1
        assert restored.issues[0].issue_type == "typo"

    def test_has_errors(self):
        r1 = QCResult(error_count=0)
        assert r1.has_errors is False
        r2 = QCResult(error_count=3)
        assert r2.has_errors is True


# ===================================================================
# QCIssue テスト
# ===================================================================

class TestQCIssue:
    def test_to_dict(self):
        issue = QCIssue(
            timestamp_sec=10.0, timecode="00:10",
            issue_type="typo", severity="error",
            spoken_text="キャッシュフロー",
            telop_text="キャシュフロー",
            description="誤字検出",
            similarity=0.85,
        )
        d = issue.to_dict()
        assert d["timecode"] == "00:10"
        assert d["similarity"] == 0.85
        assert d["issue_type"] == "typo"

    def test_from_dict(self):
        data = {
            "timestamp_sec": 5.0,
            "timecode": "00:05",
            "issue_type": "mismatch",
            "severity": "warning",
            "spoken_text": "a",
            "telop_text": "b",
            "description": "テスト",
            "similarity": 0.3,
        }
        issue = QCIssue.from_dict(data)
        assert issue.issue_type == "mismatch"
        assert issue.severity == "warning"


# ===================================================================
# Whisper キャッシュ / シリアライゼーション テスト
# ===================================================================

class TestTranscriptCache:
    def test_cache_write_read(self, tmp_path):
        """キャッシュ書き込み→読み込みのラウンドトリップ"""
        result = TranscriptResult(
            segments=[
                TranscriptSegment(start=0.0, end=3.0, text="テスト"),
            ],
            full_text="テスト",
            language="ja",
            duration=3.0,
        )
        cache_file = tmp_path / "test_whisper.json"
        cache_file.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        data = json.loads(cache_file.read_text(encoding="utf-8"))
        restored = TranscriptResult.from_dict(data)
        assert len(restored.segments) == 1
        assert restored.segments[0].text == "テスト"
        assert restored.duration == 3.0
