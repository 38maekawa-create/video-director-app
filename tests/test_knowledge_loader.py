"""KnowledgeLoader のユニットテスト（外部API・ファイル不要）"""

import sys
import json
import time
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.knowledge.loader import KnowledgeLoader, KnowledgeContext


# ────────────────────────────────────────────────
# KnowledgeLoader._read_file
# ────────────────────────────────────────────────

class TestReadFile:
    def setup_method(self):
        self.loader = KnowledgeLoader()

    def test_存在するファイルを読み込む(self):
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write("テストコンテンツ")
            tmp_path = Path(f.name)
        result = self.loader._read_file(tmp_path)
        assert "テストコンテンツ" in result
        tmp_path.unlink()

    def test_存在しないファイルは空文字を返す(self):
        result = self.loader._read_file(Path("/非存在パス/test.md"))
        assert result == ""

    def test_パーミッションエラー時は空文字を返す(self):
        # 不正なパスで例外が起きても空文字で安全に終了
        result = self.loader._read_file(Path("/root/secret.md"))
        assert isinstance(result, str)


# ────────────────────────────────────────────────
# KnowledgeLoader._extract_z_theory_key_points
# ────────────────────────────────────────────────

class TestExtractZTheoryKeyPoints:
    def setup_method(self):
        self.loader = KnowledgeLoader()

    def test_空文字は空文字を返す(self):
        assert self.loader._extract_z_theory_key_points("") == ""

    def test_Z理論セクションを抽出する(self):
        text = "## はじめに\n本文\n## Z理論について\n内容が入ります\n## 関係ない話\n削除"
        result = self.loader._extract_z_theory_key_points(text)
        assert "Z理論" in result
        assert "関係ない話" not in result

    def test_サムネセクションを抽出する(self):
        text = "## 前置き\nテキスト\n## サムネの設計\nサムネについての内容\n"
        result = self.loader._extract_z_theory_key_points(text)
        assert "サムネ" in result

    def test_抽出結果が200文字未満なら先頭200行を返す(self):
        # キーワードがないテキストは先頭200行フォールバック
        lines = [f"行{i}" for i in range(300)]
        text = "\n".join(lines)
        result = self.loader._extract_z_theory_key_points(text)
        # 先頭部分が含まれること
        assert "行0" in result


# ────────────────────────────────────────────────
# KnowledgeLoader._extract_past_titles
# ────────────────────────────────────────────────

class TestExtractPastTitles:
    def test_存在しないディレクトリは空リストを返す(self):
        loader = KnowledgeLoader()
        # VIDEO_TRANSCRIPTS_DIR を一時的に上書き
        loader.__class__.VIDEO_TRANSCRIPTS_DIR = Path("/非存在ディレクトリ/video_transcripts")
        result = loader._extract_past_titles()
        assert result == []

    def test_撮影を含むJSONからタイトルを抽出する(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # 撮影を含むJSONファイルを作成
            data = {"title": "テストタイトル", "_metadata": {"source_type": "interview"}}
            json_file = tmp_path / "2026.02.01_20251201撮影_テストさん.json"
            json_file.write_text(json.dumps(data), encoding="utf-8")

            # 撮影を含まないJSONファイル（除外されるはず）
            other_file = tmp_path / "2026.02.01_別の動画.json"
            other_file.write_text(json.dumps({"title": "除外タイトル"}), encoding="utf-8")

            loader = KnowledgeLoader()
            loader.__class__.VIDEO_TRANSCRIPTS_DIR = tmp_path
            titles = loader._extract_past_titles()

            assert "テストタイトル" in titles
            assert "除外タイトル" not in titles

    def test_source_typeがinterviewでないJSONは除外(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data = {"title": "除外タイトル", "_metadata": {"source_type": "other"}}
            json_file = tmp_path / "2026.02.01_20251201撮影_テストさん.json"
            json_file.write_text(json.dumps(data), encoding="utf-8")

            loader = KnowledgeLoader()
            loader.__class__.VIDEO_TRANSCRIPTS_DIR = tmp_path
            titles = loader._extract_past_titles()

            assert "除外タイトル" not in titles


# ────────────────────────────────────────────────
# KnowledgeLoader._load_cached_descriptions
# ────────────────────────────────────────────────

class TestLoadCachedDescriptions:
    def setup_method(self):
        self.loader = KnowledgeLoader()

    def test_存在しないキャッシュは空リストを返す(self):
        result = self.loader._load_cached_descriptions(Path("/非存在/cache.json"))
        assert result == []

    def test_有効なキャッシュを読み込む(self):
        with tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", encoding="utf-8", delete=False
        ) as f:
            data = {
                "cached_at": time.time(),
                "descriptions": ["概要欄テキスト1", "概要欄テキスト2"],
            }
            json.dump(data, f)
            tmp_path = Path(f.name)

        result = self.loader._load_cached_descriptions(tmp_path)
        assert len(result) == 2
        tmp_path.unlink()

    def test_24時間超過したキャッシュは空リストを返す(self):
        with tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", encoding="utf-8", delete=False
        ) as f:
            data = {
                "cached_at": time.time() - 86401,  # 24時間+1秒超過
                "descriptions": ["古い概要欄"],
            }
            json.dump(data, f)
            tmp_path = Path(f.name)

        result = self.loader._load_cached_descriptions(tmp_path)
        assert result == []
        tmp_path.unlink()


# ────────────────────────────────────────────────
# KnowledgeLoader.load のキャッシュ動作
# ────────────────────────────────────────────────

class TestLoad:
    def test_ロードはKnowledgeContextを返す(self):
        loader = KnowledgeLoader()
        ctx = loader.load()
        assert isinstance(ctx, KnowledgeContext)

    def test_2回ロードしても同一インスタンスを返す（キャッシュ）(self):
        loader = KnowledgeLoader()
        ctx1 = loader.load()
        ctx2 = loader.load()
        assert ctx1 is ctx2

    def test_ファイル不在でもエラーにならない(self):
        """ナレッジファイルが存在しなくても空文字で安全に返る"""
        loader = KnowledgeLoader()
        # クラス変数を存在しないパスで上書き
        original = loader.__class__.KNOWLEDGE_FILES.copy()
        loader.__class__.KNOWLEDGE_FILES = {
            "z_theory_summary": Path("/非存在/z_theory.md"),
            "z_theory_detailed": Path("/非存在/z_detailed.md"),
            "marketing_principles": Path("/非存在/marketing.md"),
        }
        loader._cache = None
        try:
            ctx = loader.load()
            assert isinstance(ctx, KnowledgeContext)
            assert ctx.z_theory_summary == ""
        finally:
            loader.__class__.KNOWLEDGE_FILES = original
