"""B-1: 7要素品質スコアリングのテスト"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.analyzer.quality_scorer import (
    score_video_quality,
    QualityScoreResult,
    QualityDimension,
    QUALITY_WEIGHTS,
    _determine_grade,
    _parse_duration_minutes,
)
from src.video_direction.analyzer.guest_classifier import ClassificationResult
from src.video_direction.analyzer.direction_generator import DirectionTimeline, DirectionEntry
from src.video_direction.integrations.ai_dev5_connector import (
    VideoData,
    HighlightScene,
    PersonProfile,
    parse_markdown_file,
)


def _make_video_data(highlights=None, guest_name="テストゲスト", duration="30分"):
    return VideoData(
        title=f"{guest_name}さんインタビュー",
        profiles=[PersonProfile(name=guest_name, age="30代", income="年収800万")],
        highlights=highlights or [],
        duration=duration,
        main_topics=["トピック1", "トピック2", "トピック3"],
        speakers="ホスト, ゲスト",
    )


def _make_highlight(ts="5:00", category="パンチライン", text="テスト発言", speaker="ゲスト"):
    return HighlightScene(timestamp=ts, speaker=speaker, text=text, category=category)


def _make_classification(tier="a"):
    return ClassificationResult(
        tier=tier, tier_label=f"層{tier}", reason="テスト",
        presentation_template="テスト", confidence="high",
    )


def _make_direction_timeline(entries=None):
    return DirectionTimeline(entries=entries or [])


def _make_direction_entry(ts="5:00", dtype="telop", priority="high"):
    return DirectionEntry(
        timestamp=ts, direction_type=dtype,
        instruction="テスト指示", reason="テスト理由", priority=priority,
    )


class TestScoreVideoQuality:
    """品質スコアリングの基本テスト"""

    def test_returns_result(self):
        """スコアリング結果が正しい型で返る"""
        data = _make_video_data()
        result = score_video_quality(data)
        assert isinstance(result, QualityScoreResult)

    def test_has_seven_dimensions(self):
        """7つの品質次元が含まれる"""
        data = _make_video_data()
        result = score_video_quality(data)
        assert len(result.dimensions) == 7

    def test_dimension_keys(self):
        """全次元が正しいキーを持つ"""
        data = _make_video_data()
        result = score_video_quality(data)
        keys = {d.key for d in result.dimensions}
        expected = {"cut", "color", "telop", "bgm", "camera", "composition", "tempo"}
        assert keys == expected

    def test_scores_in_range(self):
        """各スコアが0-100の範囲内"""
        data = _make_video_data(highlights=[
            _make_highlight(ts="5:00", category="実績数字"),
            _make_highlight(ts="10:00", category="パンチライン"),
        ])
        result = score_video_quality(data)
        for dim in result.dimensions:
            assert 0 <= dim.score <= 100, f"{dim.key}: {dim.score}"

    def test_total_score_in_range(self):
        """合計スコアが0-100の範囲内"""
        data = _make_video_data()
        result = score_video_quality(data)
        assert 0 <= result.total_score <= 100

    def test_weights_sum_to_one(self):
        """重みの合計が1.0"""
        assert abs(sum(QUALITY_WEIGHTS.values()) - 1.0) < 0.01

    def test_weighted_score_calculation(self):
        """加重スコアが正しく計算される"""
        data = _make_video_data()
        result = score_video_quality(data)
        for dim in result.dimensions:
            expected = round(dim.score * dim.weight, 1)
            assert abs(dim.weighted_score - expected) < 0.2, f"{dim.key}: {dim.weighted_score} != {expected}"

    def test_grade_assigned(self):
        """グレードが割り当てられる"""
        data = _make_video_data()
        result = score_video_quality(data)
        assert result.grade in ("S", "A", "B", "C", "D")

    def test_is_estimated(self):
        """Phase 2では推定値フラグがTrue"""
        data = _make_video_data()
        result = score_video_quality(data)
        assert result.is_estimated is True

    def test_with_rich_data(self):
        """豊富なデータがあるとスコアが上がる"""
        # 最小データ
        minimal = _make_video_data(highlights=[])
        result_minimal = score_video_quality(minimal)

        # 豊富なデータ
        rich = _make_video_data(highlights=[
            _make_highlight(ts="2:00", category="属性紹介"),
            _make_highlight(ts="5:00", category="実績数字", text="年収1400万達成"),
            _make_highlight(ts="8:00", category="パンチライン"),
            _make_highlight(ts="12:00", category="TEKO価値"),
            _make_highlight(ts="15:00", category="実績数字", text="月利200万"),
            _make_highlight(ts="20:00", category="パンチライン"),
            _make_highlight(ts="24:00", category="メッセージ"),
            _make_highlight(ts="28:00", category="パンチライン"),
        ])
        timeline = _make_direction_timeline(entries=[
            _make_direction_entry(ts="5:00", dtype="telop"),
            _make_direction_entry(ts="5:00", dtype="color"),
            _make_direction_entry(ts="8:00", dtype="camera"),
            _make_direction_entry(ts="12:00", dtype="camera"),
            _make_direction_entry(ts="15:00", dtype="telop"),
            _make_direction_entry(ts="20:00", dtype="camera"),
        ])
        result_rich = score_video_quality(rich, direction_timeline=timeline)

        assert result_rich.total_score > result_minimal.total_score

    def test_with_classification(self):
        """分類結果を渡しても正常動作"""
        data = _make_video_data(highlights=[
            _make_highlight(category="実績数字", text="年収1500万"),
        ])
        classification = _make_classification(tier="a")
        result = score_video_quality(data, classification=classification)
        assert result.total_score > 0

    def test_improvement_areas(self):
        """改善領域が提示される"""
        data = _make_video_data(highlights=[_make_highlight()])
        result = score_video_quality(data)
        assert len(result.improvement_areas) >= 1

    def test_strengths(self):
        """強み領域が提示される"""
        data = _make_video_data(highlights=[_make_highlight()])
        result = score_video_quality(data)
        assert len(result.strengths) >= 1


class TestDetermineGrade:
    """グレード判定のテスト"""

    def test_grade_s(self):
        assert _determine_grade(95) == "S"

    def test_grade_a(self):
        assert _determine_grade(85) == "A"

    def test_grade_b(self):
        assert _determine_grade(70) == "B"

    def test_grade_c(self):
        assert _determine_grade(55) == "C"

    def test_grade_d(self):
        assert _determine_grade(30) == "D"


class TestParseDuration:
    """動画時間パースのテスト"""

    def test_minutes(self):
        assert _parse_duration_minutes("30分") == 30

    def test_minutes_seconds(self):
        assert abs(_parse_duration_minutes("30分45秒") - 30.75) < 0.01

    def test_mm_ss(self):
        assert abs(_parse_duration_minutes("30:45") - 30.75) < 0.01

    def test_hh_mm_ss(self):
        assert abs(_parse_duration_minutes("1:30:00") - 90.0) < 0.01

    def test_empty(self):
        assert _parse_duration_minutes("") == 0

    def test_none(self):
        assert _parse_duration_minutes(None) == 0


class TestRealData:
    """実データでのテスト"""

    REAL_FILE = Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_Izuさん：30代中盤元アクセンチュア年収1000万円台.md"

    def test_izu_quality_score(self):
        """Izuさんの実データで品質スコアリングが正常動作"""
        if not self.REAL_FILE.exists():
            return
        data = parse_markdown_file(self.REAL_FILE)
        result = score_video_quality(data)
        assert result.total_score > 0
        assert len(result.dimensions) == 7
        assert result.grade in ("S", "A", "B", "C", "D")
        # 各次元が有効
        for dim in result.dimensions:
            assert dim.label != ""
            assert 0 <= dim.score <= 100
