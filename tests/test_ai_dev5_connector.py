"""ai_dev5_connector のユニットテスト"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.integrations.ai_dev5_connector import (
    parse_markdown_file,
    list_video_markdown_files,
    VideoData,
    HighlightScene,
    PersonProfile,
)


# テスト用の実データパス
SAMPLE_FILES = [
    Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_Izuさん：30代中盤元アクセンチュア年収1000万円台.md",
    Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_りょうすけさん：20代後半内資IT勤務年収600万.md",
    Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.28_ゆりかさん.md",
]


class TestParseMarkdownFile:
    """Markdownファイルパースのテスト"""

    def test_parse_izu(self):
        """Izuさんのファイルをパースできる"""
        filepath = SAMPLE_FILES[0]
        if not filepath.exists():
            return  # ファイルがなければスキップ
        data = parse_markdown_file(filepath)
        assert data.title is not None
        assert "Izu" in data.title or "アクセンチュア" in data.title
        assert data.duration != ""
        assert len(data.highlights) > 0
        assert len(data.profiles) > 0
        assert data.profiles[0].name == "Izu"
        assert "1500" in data.profiles[0].income or "3000" in data.profiles[0].income

    def test_parse_ryosuke(self):
        """りょうすけさんのファイルをパースできる"""
        filepath = SAMPLE_FILES[1]
        if not filepath.exists():
            return
        data = parse_markdown_file(filepath)
        assert len(data.profiles) > 0
        # りょうすけさんのプロファイル名は「陽介」
        assert "600" in data.profiles[0].income
        assert len(data.highlights) > 0
        assert len(data.three_line_summary) == 3

    def test_parse_yurika(self):
        """ゆりかさんのファイルをパースできる"""
        filepath = SAMPLE_FILES[2]
        if not filepath.exists():
            return
        data = parse_markdown_file(filepath)
        assert len(data.profiles) > 0
        assert "理学療法士" in (data.profiles[0].occupation or "")
        assert len(data.highlights) > 0

    def test_parse_meta_info(self):
        """メタ情報が正しくパースされる"""
        filepath = SAMPLE_FILES[0]
        if not filepath.exists():
            return
        data = parse_markdown_file(filepath)
        assert data.date != ""
        assert data.video_type != ""
        assert data.category != ""
        assert len(data.tags) > 0

    def test_parse_highlights_structure(self):
        """ハイライトシーンの構造が正しい"""
        filepath = SAMPLE_FILES[0]
        if not filepath.exists():
            return
        data = parse_markdown_file(filepath)
        for h in data.highlights:
            assert isinstance(h, HighlightScene)
            assert ":" in h.timestamp
            assert h.speaker != ""
            assert h.text != ""
            assert h.category in ("属性紹介", "実績数字", "パンチライン", "TEKO価値", "メッセージ")


class TestListFiles:
    """ファイル一覧取得のテスト"""

    def test_list_files(self):
        """ファイル一覧を取得できる"""
        files = list_video_markdown_files()
        assert len(files) > 0
        for f in files:
            assert f.name.endswith(".md")
            assert not f.name.startswith("_")
            assert "DUPLICATE" not in f.name

    def test_excludes_archive(self):
        """_archive, _backup ディレクトリのファイルが除外される"""
        files = list_video_markdown_files()
        for f in files:
            assert "_archive" not in str(f)
            assert "_backup" not in str(f)
