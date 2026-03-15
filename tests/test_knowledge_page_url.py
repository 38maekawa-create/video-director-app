"""ナレッジページURL マッチングのテスト

プロジェクトのゲスト名+撮影日からナレッジページHTMLのURLを正しくマッチングできることを検証する。
"""

import tempfile
from pathlib import Path
from unittest import mock

import pytest


def _make_html_files(tmpdir: Path, filenames: list[str]):
    """テスト用にHTMLファイルを作成する"""
    for name in filenames:
        (tmpdir / name).write_text("<html></html>", encoding="utf-8")


class TestNormalizeName:
    """_normalize_name関数のテスト"""

    def test_remove_san(self):
        from src.video_direction.integrations.api_server import _normalize_name
        assert _normalize_name("hiraiさん") == "hirai"

    def test_remove_shi(self):
        from src.video_direction.integrations.api_server import _normalize_name
        assert _normalize_name("田中氏") == "田中"

    def test_lowercase(self):
        from src.video_direction.integrations.api_server import _normalize_name
        assert _normalize_name("Pay") == "pay"

    def test_fullwidth_to_halfwidth(self):
        from src.video_direction.integrations.api_server import _normalize_name
        # 全角英数字→半角
        assert _normalize_name("ＡＢＣ") == "abc"

    def test_empty(self):
        from src.video_direction.integrations.api_server import _normalize_name
        assert _normalize_name("") == ""

    def test_strip_whitespace(self):
        from src.video_direction.integrations.api_server import _normalize_name
        assert _normalize_name("  hirai  ") == "hirai"


class TestFindKnowledgePageUrl:
    """find_knowledge_page_url関数のテスト"""

    def test_match_by_guest_name(self, tmp_path):
        """ゲスト名でマッチできること"""
        from src.video_direction.integrations import api_server

        _make_html_files(tmp_path, [
            "20260215_20251123撮影_hiraiさん30代中盤内資系生保マーケ年収850万円.html",
            "20260215_20251213撮影_payさん30代中盤LINEyahoo年収850万.html",
        ])

        with mock.patch.object(api_server, "KNOWLEDGE_PAGES_DIR", tmp_path):
            url = api_server.find_knowledge_page_url("hiraiさん")
            assert url is not None
            assert "hirai" in url
            assert url.startswith(api_server.KNOWLEDGE_PAGES_BASE_URL)

    def test_match_by_guest_name_and_date(self, tmp_path):
        """ゲスト名+撮影日で最優先マッチすること"""
        from src.video_direction.integrations import api_server

        _make_html_files(tmp_path, [
            "20260215_20251123撮影_hiraiさん30代中盤内資系生保マーケ年収850万円.html",
            "20260301_20260201撮影_hiraiさん別動画.html",
        ])

        with mock.patch.object(api_server, "KNOWLEDGE_PAGES_DIR", tmp_path):
            url = api_server.find_knowledge_page_url("hirai", "2025-11-23")
            assert url is not None
            assert "20251123" in url

    def test_no_match(self, tmp_path):
        """マッチしない場合はNoneを返すこと"""
        from src.video_direction.integrations import api_server

        _make_html_files(tmp_path, [
            "20260215_20251213撮影_payさん30代中盤LINEyahoo年収850万.html",
        ])

        with mock.patch.object(api_server, "KNOWLEDGE_PAGES_DIR", tmp_path):
            url = api_server.find_knowledge_page_url("存在しないゲスト")
            assert url is None

    def test_empty_guest_name(self, tmp_path):
        """空文字ゲスト名はNoneを返すこと"""
        from src.video_direction.integrations import api_server

        _make_html_files(tmp_path, [
            "20260215_20251123撮影_hiraiさん.html",
        ])

        with mock.patch.object(api_server, "KNOWLEDGE_PAGES_DIR", tmp_path):
            url = api_server.find_knowledge_page_url("")
            assert url is None

    def test_missing_directory(self):
        """ナレッジページディレクトリが存在しない場合はNoneを返すこと"""
        from src.video_direction.integrations import api_server

        with mock.patch.object(api_server, "KNOWLEDGE_PAGES_DIR", Path("/nonexistent/path")):
            url = api_server.find_knowledge_page_url("hirai")
            assert url is None

    def test_honorific_stripping(self, tmp_path):
        """敬称付きゲスト名でもマッチすること"""
        from src.video_direction.integrations import api_server

        _make_html_files(tmp_path, [
            "20260216_20251130撮影_みんてぃあさん40代前半AWS管理職年収2200万.html",
        ])

        with mock.patch.object(api_server, "KNOWLEDGE_PAGES_DIR", tmp_path):
            # 敬称なしでマッチ
            url = api_server.find_knowledge_page_url("みんてぃあ")
            assert url is not None
            assert "みんてぃあ" in url

    def test_date_format_conversion(self, tmp_path):
        """撮影日のYYYY-MM-DD形式がYYYYMMDDに変換されてマッチすること"""
        from src.video_direction.integrations import api_server

        _make_html_files(tmp_path, [
            "20260216_20251213撮影_しおさん30代前半外資製薬MR年収1050万.html",
        ])

        with mock.patch.object(api_server, "KNOWLEDGE_PAGES_DIR", tmp_path):
            url = api_server.find_knowledge_page_url("しお", "2025-12-13")
            assert url is not None
            assert "20251213" in url


class TestEnrichProjectWithKnowledgeUrl:
    """_enrich_project_with_knowledge_url関数のテスト"""

    def test_adds_field(self, tmp_path):
        """プロジェクト辞書にknowledge_page_urlフィールドが追加されること"""
        from src.video_direction.integrations import api_server

        _make_html_files(tmp_path, [
            "20260216_20251130撮影_さるビールさん30代前半キリンビール年収700万.html",
        ])

        project = {
            "guest_name": "さるビール",
            "shoot_date": "2025-11-30",
        }

        with mock.patch.object(api_server, "KNOWLEDGE_PAGES_DIR", tmp_path):
            result = api_server._enrich_project_with_knowledge_url(project)
            assert "knowledge_page_url" in result
            assert result["knowledge_page_url"] is not None
            assert "さるビール" in result["knowledge_page_url"]

    def test_none_when_no_match(self, tmp_path):
        """マッチしない場合はknowledge_page_urlがNoneであること"""
        from src.video_direction.integrations import api_server

        _make_html_files(tmp_path, [])

        project = {
            "guest_name": "未知のゲスト",
            "shoot_date": "2026-01-01",
        }

        with mock.patch.object(api_server, "KNOWLEDGE_PAGES_DIR", tmp_path):
            result = api_server._enrich_project_with_knowledge_url(project)
            assert result["knowledge_page_url"] is None
