"""NEW-2: ハイライトカットポイントディレクションのテスト"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.analyzer.highlight_cutter import (
    suggest_highlight_cuts,
    HighlightCutResult,
    HighlightCutScene,
    _score_highlights,
    _select_diverse_highlights,
)
from src.video_direction.analyzer.guest_classifier import ClassificationResult
from src.video_direction.integrations.ai_dev5_connector import (
    VideoData,
    HighlightScene,
    PersonProfile,
    parse_markdown_file,
)


def _make_video_data(highlights=None, guest_name="テストゲスト"):
    return VideoData(
        title=f"{guest_name}さんインタビュー",
        profiles=[PersonProfile(name=guest_name, age="30代", income="年収800万")],
        highlights=highlights or [],
        duration="30分",
        main_topics=["トピック1", "トピック2"],
    )


def _make_highlight(ts="5:00", category="パンチライン", text="テスト発言", speaker="ゲスト"):
    return HighlightScene(timestamp=ts, speaker=speaker, text=text, category=category)


def _make_classification(tier="b"):
    return ClassificationResult(
        tier=tier,
        tier_label=f"層{tier}",
        reason="テスト",
        presentation_template="テスト",
        confidence="high",
    )


class TestSuggestHighlightCuts:
    """ハイライトカットポイント提案の基本テスト"""

    def test_empty_highlights(self):
        """ハイライトなしでは空の結果"""
        data = _make_video_data(highlights=[])
        result = suggest_highlight_cuts(data)
        assert isinstance(result, HighlightCutResult)
        assert result.scene_count == 0

    def test_single_highlight(self):
        """ハイライト1件でもシーンが生成される"""
        data = _make_video_data(highlights=[
            _make_highlight(ts="5:00", category="パンチライン"),
        ])
        result = suggest_highlight_cuts(data)
        assert result.scene_count == 1

    def test_multiple_highlights(self):
        """複数ハイライトから複数シーンが選定される"""
        data = _make_video_data(highlights=[
            _make_highlight(ts="2:00", category="属性紹介", text="30代ITエンジニア"),
            _make_highlight(ts="5:00", category="実績数字", text="年収1400万達成"),
            _make_highlight(ts="10:00", category="パンチライン", text="人生変わった"),
            _make_highlight(ts="15:00", category="TEKO価値", text="TEKOで成長できた"),
            _make_highlight(ts="25:00", category="メッセージ", text="挑戦してほしい"),
        ])
        result = suggest_highlight_cuts(data)
        assert result.scene_count == 5
        # 時系列順
        for i in range(len(result.scenes) - 1):
            assert result.scenes[i].order < result.scenes[i+1].order

    def test_scene_has_required_fields(self):
        """シーンに必須フィールドがある"""
        data = _make_video_data(highlights=[
            _make_highlight(ts="10:00", category="実績数字", text="月利100万"),
        ])
        result = suggest_highlight_cuts(data)
        scene = result.scenes[0]
        assert scene.start_ts != ""
        assert scene.end_ts != ""
        assert scene.duration_seconds > 0
        assert scene.category != ""
        assert scene.speaker != ""
        assert scene.text != ""

    def test_has_structure_note(self):
        """構成メモが生成される"""
        data = _make_video_data(highlights=[
            _make_highlight(ts="2:00", category="属性紹介"),
            _make_highlight(ts="10:00", category="パンチライン"),
        ])
        result = suggest_highlight_cuts(data)
        assert result.structure_note != ""

    def test_has_opening_closing(self):
        """オープニング・クロージング提案がある"""
        data = _make_video_data(highlights=[
            _make_highlight(ts="2:00", category="属性紹介"),
            _make_highlight(ts="25:00", category="メッセージ"),
        ])
        result = suggest_highlight_cuts(data)
        assert result.opening_suggestion != ""
        assert result.closing_suggestion != ""

    def test_with_classification(self):
        """分類結果を渡しても正常動作する"""
        data = _make_video_data(highlights=[
            _make_highlight(ts="5:00", category="実績数字", text="年収1500万"),
        ])
        classification = _make_classification(tier="a")
        result = suggest_highlight_cuts(data, classification=classification)
        assert result.scene_count == 1

    def test_total_duration(self):
        """合計時間が計算される"""
        data = _make_video_data(highlights=[
            _make_highlight(ts="5:00"),
            _make_highlight(ts="15:00"),
        ])
        result = suggest_highlight_cuts(data)
        assert result.total_duration_seconds > 0

    def test_max_duration_limit(self):
        """合計時間が上限（180秒）を超えない"""
        # 大量のハイライトを入れても上限内に収まる
        highlights = [
            _make_highlight(ts=f"{i*3}:00", category="パンチライン", text="長い発言" * 20)
            for i in range(10)
        ]
        data = _make_video_data(highlights=highlights)
        result = suggest_highlight_cuts(data)
        assert result.total_duration_seconds <= 180


class TestScoreHighlights:
    """ハイライトスコアリングのテスト"""

    def test_achievement_higher_than_general(self):
        """実績数字は一般カテゴリより高スコア"""
        highlights = [
            _make_highlight(category="実績数字", text="年収1400万を達成した瞬間のこと"),
            _make_highlight(category="属性紹介", text="30代のエンジニアです"),
        ]
        scored = _score_highlights(highlights)
        # 実績数字のスコアが属性紹介より高い
        achievement_score = next(s for h, s in scored if h.category == "実績数字")
        intro_score = next(s for h, s in scored if h.category == "属性紹介")
        assert achievement_score >= intro_score

    def test_number_bonus(self):
        """数字を含むハイライトにはボーナス"""
        with_number = _make_highlight(text="年収1400万を達成")
        without_number = _make_highlight(text="成長を実感した瞬間だった")
        scored = _score_highlights([with_number, without_number])
        # スコア順（降順）で数字入りが先
        assert scored[0][0].text == with_number.text


class TestSelectDiverse:
    """多様性を考慮した選定のテスト"""

    def test_selects_different_categories(self):
        """異なるカテゴリのハイライトが優先的に選ばれる"""
        scored = [
            (_make_highlight(category="実績数字"), 0.8),
            (_make_highlight(category="実績数字"), 0.7),
            (_make_highlight(category="パンチライン"), 0.6),
            (_make_highlight(category="TEKO価値"), 0.5),
        ]
        selected = _select_diverse_highlights(scored, 3)
        categories = [h.category for h, s in selected]
        # 3件中、少なくとも2カテゴリは含まれるはず
        assert len(set(categories)) >= 2


class TestRealData:
    """実データでのテスト"""

    REAL_FILE = Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_Izuさん：30代中盤元アクセンチュア年収1000万円台.md"

    def test_izu_highlight_cuts(self):
        """Izuさんの実データでハイライトカットが生成される"""
        if not self.REAL_FILE.exists():
            return
        data = parse_markdown_file(self.REAL_FILE)
        result = suggest_highlight_cuts(data)
        assert result.scene_count >= 1
        assert result.total_duration_seconds > 0
        assert result.structure_note != ""
        # 全シーンが有効
        for scene in result.scenes:
            assert scene.duration_seconds > 0
