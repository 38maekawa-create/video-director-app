"""E-1改: 切り抜きカットポイント提案のテスト"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.analyzer.clip_cutter import (
    suggest_clip_cuts,
    ClipSegment,
    ClipCutResult,
    _group_nearby_highlights,
    _timestamp_to_seconds,
    _seconds_to_timestamp,
)
from src.video_direction.integrations.ai_dev5_connector import (
    VideoData,
    HighlightScene,
    PersonProfile,
    parse_markdown_file,
)


# テスト用ヘルパー: ハイライト付きVideoDataを生成
def _make_video_data(highlights=None, guest_name="テストゲスト"):
    return VideoData(
        title=f"{guest_name}さんインタビュー",
        profiles=[PersonProfile(name=guest_name, age="30代", income="年収800万", occupation="IT企業勤務")],
        highlights=highlights or [],
        duration="30分",
    )


def _make_highlight(ts="5:00", category="パンチライン", text="これはテスト発言です", speaker="ゲスト"):
    return HighlightScene(timestamp=ts, speaker=speaker, text=text, category=category)


class TestSuggestClipCuts:
    """切り抜きカットポイント提案の基本テスト"""

    def test_empty_highlights(self):
        """ハイライトなしの場合は空のClipCutResultを返す"""
        data = _make_video_data(highlights=[])
        result = suggest_clip_cuts(data)
        assert isinstance(result, ClipCutResult)
        assert result.clip_count == 0
        assert result.clips == []

    def test_single_highlight(self):
        """ハイライト1件でもクリップが生成される"""
        data = _make_video_data(highlights=[
            _make_highlight(ts="5:00", category="パンチライン", text="衝撃の発言がここに入る"),
        ])
        result = suggest_clip_cuts(data)
        assert result.clip_count >= 1
        assert result.clips[0].clip_type == "punchline"

    def test_multiple_highlights(self):
        """複数のハイライトから複数のクリップが生成される"""
        data = _make_video_data(highlights=[
            _make_highlight(ts="2:00", category="属性紹介", text="30代ITエンジニア"),
            _make_highlight(ts="5:00", category="実績数字", text="年収1400万"),
            _make_highlight(ts="15:00", category="パンチライン", text="人生を変えた瞬間だった"),
            _make_highlight(ts="25:00", category="メッセージ", text="これから挑戦する人に伝えたい"),
        ])
        result = suggest_clip_cuts(data)
        assert result.clip_count >= 2
        assert result.total_highlights == 4

    def test_clip_has_required_fields(self):
        """生成されたクリップに必須フィールドが含まれる"""
        data = _make_video_data(highlights=[
            _make_highlight(ts="10:00", category="実績数字", text="月利100万達成"),
        ])
        result = suggest_clip_cuts(data)
        clip = result.clips[0]
        assert clip.start_ts != ""
        assert clip.end_ts != ""
        assert clip.duration_seconds > 0
        assert clip.title_suggestion != ""
        assert clip.hook_text != ""
        assert clip.clip_type != ""
        assert clip.priority in ("high", "medium", "low")
        assert 0.0 <= clip.standalone_score <= 1.0

    def test_priority_ordering(self):
        """パンチライン/実績数字はhigh優先度"""
        data = _make_video_data(highlights=[
            _make_highlight(ts="5:00", category="パンチライン"),
            _make_highlight(ts="15:00", category="TEKO価値"),
        ])
        result = suggest_clip_cuts(data)
        # 最初のクリップはhigh優先度のはず
        assert result.clips[0].priority == "high"


class TestGroupNearbyHighlights:
    """近接ハイライトグループ化のテスト"""

    def test_no_highlights(self):
        """空リストに対しては空を返す"""
        result = _group_nearby_highlights([])
        assert result == []

    def test_single_highlight(self):
        """1件のハイライトは1グループ"""
        highlights = [_make_highlight(ts="5:00")]
        groups = _group_nearby_highlights(highlights)
        assert len(groups) == 1
        assert len(groups[0]) == 1

    def test_nearby_grouped(self):
        """60秒以内のハイライトは同一グループ"""
        highlights = [
            _make_highlight(ts="5:00"),
            _make_highlight(ts="5:30"),
            _make_highlight(ts="5:50"),
        ]
        groups = _group_nearby_highlights(highlights, proximity_seconds=60)
        assert len(groups) == 1
        assert len(groups[0]) == 3

    def test_far_apart_separate(self):
        """60秒以上離れたハイライトは別グループ"""
        highlights = [
            _make_highlight(ts="2:00"),
            _make_highlight(ts="10:00"),
        ]
        groups = _group_nearby_highlights(highlights, proximity_seconds=60)
        assert len(groups) == 2


class TestTimestampConversion:
    """タイムスタンプ変換のテスト"""

    def test_mm_ss(self):
        assert _timestamp_to_seconds("5:30") == 330

    def test_hh_mm_ss(self):
        assert _timestamp_to_seconds("1:05:30") == 3930

    def test_zero(self):
        assert _timestamp_to_seconds("0:00") == 0

    def test_seconds_to_ts(self):
        assert _seconds_to_timestamp(330) == "5:30"

    def test_seconds_to_ts_zero(self):
        assert _seconds_to_timestamp(0) == "0:00"


class TestRealData:
    """実データでのテスト"""

    REAL_FILE = Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_Izuさん：30代中盤元アクセンチュア年収1000万円台.md"

    def test_izu_clip_cuts(self):
        """Izuさんの実データで切り抜きが生成される"""
        if not self.REAL_FILE.exists():
            return
        data = parse_markdown_file(self.REAL_FILE)
        result = suggest_clip_cuts(data)
        assert result.clip_count >= 1
        # 全クリップが有効な構造を持つ
        for clip in result.clips:
            assert clip.duration_seconds >= 15
            assert clip.start_ts != ""
            assert clip.end_ts != ""
