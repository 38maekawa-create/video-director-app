"""VideoAnalyzer / VideoAnalysisResult のユニットテスト（外部ツール不要）"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.tracker.video_analyzer import VideoAnalysisResult, VideoAnalyzer


# ────────────────────────────────────────────────
# VideoAnalysisResult データクラス
# ────────────────────────────────────────────────

class TestVideoAnalysisResult:
    def test_video_idだけで生成できる(self):
        r = VideoAnalysisResult(video_id="v001")
        assert r.video_id == "v001"
        assert r.overall_score == 0.0
        assert r.composition == ""
        assert r.tempo == ""
        assert r.cutting_style == ""
        assert r.color_grading == ""
        assert r.audio_balance == ""
        assert r.key_techniques == []
        assert r.summary == ""
        assert r.frame_count == 0
        assert r.avg_scene_duration == 0.0

    def test_全フィールドを指定して生成できる(self):
        r = VideoAnalysisResult(
            video_id="v002",
            overall_score=0.85,
            composition="ロングトーク構成",
            tempo="標準的なテンポ",
            cutting_style="高速カット",
            color_grading="暖色系",
            key_techniques=["テクA", "テクB"],
            frame_count=1000,
            avg_scene_duration=5.0,
        )
        assert r.overall_score == 0.85
        assert r.frame_count == 1000
        assert len(r.key_techniques) == 2


# ────────────────────────────────────────────────
# VideoAnalyzer — 初期化
# ────────────────────────────────────────────────

class TestVideoAnalyzerInit:
    def test_tmpディレクトリで初期化できる(self):
        tmp = Path(tempfile.mkdtemp())
        analyzer = VideoAnalyzer(cache_dir=tmp)
        assert analyzer.cache_dir == tmp


# ────────────────────────────────────────────────
# VideoAnalyzer — _analyze_from_transcript
# ────────────────────────────────────────────────

class TestAnalyzeFromTranscript:
    def setup_method(self):
        tmp = Path(tempfile.mkdtemp())
        self.analyzer = VideoAnalyzer(cache_dir=tmp)

    def _make_result(self):
        return VideoAnalysisResult(video_id="test_v")

    def test_話者切替が多いとテンポが速い判定(self):
        """30%超の行で話者切替があると「テンポが速い」"""
        # 10行中4行で話者切替 → 4/10 = 40% > 30%
        lines = []
        speakers = ["A", "B", "A", "B", "A", "B", "A", "B", "A", "B"]
        for s in speakers:
            lines.append(f"{s}: テスト発言内容")
        transcript = "\n".join(lines)
        result = self.analyzer._analyze_from_transcript(self._make_result(), transcript)
        assert "テンポが速い" in result.tempo

    def test_話者切替が少ないとゆったり判定(self):
        """15%未満の切替で「ゆったり」"""
        # 10行中1行のみ切替 → 1/10 = 10% < 15%
        lines = ["A: " + "長い発言内容。" * 3] * 9
        lines.append("B: 別の発言")
        transcript = "\n".join(lines)
        result = self.analyzer._analyze_from_transcript(self._make_result(), transcript)
        assert "ゆったり" in result.tempo

    def test_ロングトーク構成の判定(self):
        """50%超の行が100文字超 → ロングトーク構成"""
        lines = ["A: " + "あ" * 100 for _ in range(6)]
        lines += ["B: 短い" for _ in range(4)]
        transcript = "\n".join(lines)
        result = self.analyzer._analyze_from_transcript(self._make_result(), transcript)
        assert "ロングトーク" in result.composition

    def test_ショートカット構成の判定(self):
        """長い行が少ない → ショートカット構成"""
        lines = ["A: 短い発言" for _ in range(10)]
        transcript = "\n".join(lines)
        result = self.analyzer._analyze_from_transcript(self._make_result(), transcript)
        assert "ショートカット" in result.composition

    def test_frame_countが行数と一致する(self):
        transcript = "A: 発言1\nB: 発言2\nA: 発言3"
        result = self.analyzer._analyze_from_transcript(self._make_result(), transcript)
        assert result.frame_count == 3

    def test_summaryにサマリー情報が含まれる(self):
        transcript = "A: 発言1\nB: 発言2"
        result = self.analyzer._analyze_from_transcript(self._make_result(), transcript)
        assert result.summary != ""

    def test_空の文字起こしでもエラーにならない(self):
        result = self.analyzer._analyze_from_transcript(self._make_result(), "")
        assert result is not None


# ────────────────────────────────────────────────
# VideoAnalyzer — analyze（統合）
# ────────────────────────────────────────────────

class TestVideoAnalyzerAnalyze:
    def setup_method(self):
        tmp = Path(tempfile.mkdtemp())
        self.analyzer = VideoAnalyzer(cache_dir=tmp)

    def test_何も渡さなくても動作する(self):
        result = self.analyzer.analyze()
        assert result.video_id == "unknown"

    def test_transcriptを渡すと分析される(self):
        transcript = "A: 発言A\nB: 発言B\nA: 発言C"
        result = self.analyzer.analyze(transcript=transcript)
        assert result.tempo != ""
        assert result.composition != ""

    def test_video_urlを渡すとvideo_idに使われる(self):
        with patch.object(self.analyzer, "_analyze_from_metadata") as mock_meta:
            mock_meta.return_value = VideoAnalysisResult(video_id="https://example.com/v=abc")
            result = self.analyzer.analyze(video_url="https://example.com/v=abc")
        assert result.video_id == "https://example.com/v=abc"

    def test_存在しないvideo_pathは無視される(self):
        # _analyze_from_video は存在するファイルのみ実行
        result = self.analyzer.analyze(video_path="/no/such/file.mp4")
        # エラーにならず結果が返ること
        assert result is not None
