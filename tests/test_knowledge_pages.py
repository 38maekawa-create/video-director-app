"""テスト — ナレッジページ連携モジュール（KP-1）

~/video-knowledge-pages/ の実データを使ったテストと、
テスト用一時ディレクトリを使った単体テストの両方を含む。
"""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.integrations.knowledge_pages import (
    KnowledgePageIntegration,
    _extract_html_text,
    _extract_meta,
    _parse_filename,
)


# --- ユニットテスト: ヘルパー関数 ---


class TestParseFilename:
    """ファイル名パース"""

    def test_standard_format(self):
        result = _parse_filename("20260215_テスト動画.html")
        assert result["date"] == "2026-02-15"
        assert result["filename_title"] == "テスト動画"

    def test_complex_filename(self):
        result = _parse_filename("20260307_2月28日_大阪_ハオさん34歳.html")
        assert result["date"] == "2026-03-07"
        assert "ハオ" in result["filename_title"]

    def test_no_date_prefix(self):
        result = _parse_filename("index.html")
        assert result["date"] == ""
        assert result["filename_title"] == "index"


class TestExtractHtmlText:
    """HTML→テキスト抽出"""

    def test_basic(self):
        html = "<html><body><p>テスト文章です</p></body></html>"
        text = _extract_html_text(html)
        assert "テスト文章" in text

    def test_skip_style(self):
        html = "<html><style>.foo { color: red; }</style><body><p>本文</p></body></html>"
        text = _extract_html_text(html)
        assert "本文" in text
        assert "color" not in text

    def test_skip_script(self):
        html = "<html><script>var x = 1;</script><body><p>内容</p></body></html>"
        text = _extract_html_text(html)
        assert "内容" in text
        assert "var" not in text


class TestExtractMeta:
    """HTMLメタ情報抽出"""

    SAMPLE_HTML = """<!DOCTYPE html>
<html lang="ja">
<head><title>テストタイトル</title></head>
<body>
<h1>テストタイトル</h1>
<div class="meta-grid">
  <div class="meta-item"><span class="meta-label">話者</span><span class="meta-value">hirai</span></div>
  <div class="meta-item"><span class="meta-label">カテゴリ</span><span class="meta-value">TEKO事業</span></div>
  <div class="meta-item"><span class="meta-label">動画時間</span><span class="meta-value">44分0秒</span></div>
</div>
<div class="tags">
  <span class="tag">TEKOメンバー</span>
  <span class="tag">インタビュー</span>
</div>
<section>
  <h2>3行要約</h2>
  <ul class="summary-list">
    <li>要約1行目</li>
    <li>要約2行目</li>
  </ul>
</section>
</body></html>"""

    def test_title(self):
        meta = _extract_meta(self.SAMPLE_HTML)
        assert meta["title"] == "テストタイトル"

    def test_tags(self):
        meta = _extract_meta(self.SAMPLE_HTML)
        assert "TEKOメンバー" in meta["tags"]
        assert "インタビュー" in meta["tags"]

    def test_meta_items(self):
        meta = _extract_meta(self.SAMPLE_HTML)
        assert meta["meta"]["話者"] == "hirai"
        assert meta["meta"]["カテゴリ"] == "TEKO事業"
        assert meta["meta"]["動画時間"] == "44分0秒"

    def test_summary(self):
        meta = _extract_meta(self.SAMPLE_HTML)
        assert len(meta["summary"]) == 2
        assert "要約1行目" in meta["summary"][0]


# --- 単体テスト: KnowledgePageIntegration ---


@pytest.fixture
def temp_pages_dir():
    """テスト用の一時ナレッジページディレクトリ"""
    with tempfile.TemporaryDirectory() as tmpdir:
        pages_dir = Path(tmpdir)

        # テスト用HTMLファイル作成
        page1 = pages_dir / "20260215_テストゲストAさん.html"
        page1.write_text("""<!DOCTYPE html>
<html><head><title>テストゲストA</title></head><body>
<h1>テストゲストA</h1>
<div class="meta-grid">
  <div class="meta-item"><span class="meta-label">話者</span><span class="meta-value">ゲストA</span></div>
  <div class="meta-item"><span class="meta-label">カテゴリ</span><span class="meta-value">TEKO事業</span></div>
</div>
<div class="tags"><span class="tag">不動産</span><span class="tag">投資</span></div>
<section><h2>3行要約</h2>
<ul class="summary-list"><li>ゲストAは不動産投資を行っている</li></ul>
</section>
<section><h2>内容整理</h2>
<div class="content-block"><p>ゲストAは30代前半で不動産投資を始めた。</p></div>
</section>
</body></html>""", encoding="utf-8")

        page2 = pages_dir / "20260216_テストゲストBさん株式投資.html"
        page2.write_text("""<!DOCTYPE html>
<html><head><title>テストゲストB：株式投資</title></head><body>
<h1>テストゲストB：株式投資</h1>
<div class="meta-grid">
  <div class="meta-item"><span class="meta-label">話者</span><span class="meta-value">ゲストB</span></div>
  <div class="meta-item"><span class="meta-label">カテゴリ</span><span class="meta-value">外部動画</span></div>
</div>
<div class="tags"><span class="tag">株式</span><span class="tag">投資</span></div>
<section><h2>3行要約</h2>
<ul class="summary-list"><li>ゲストBは株式投資の専門家</li></ul>
</section>
</body></html>""", encoding="utf-8")

        page3 = pages_dir / "20260217_ゲストAさん追加インタビュー.html"
        page3.write_text("""<!DOCTYPE html>
<html><head><title>ゲストA追加インタビュー</title></head><body>
<h1>ゲストA追加インタビュー</h1>
<div class="meta-grid">
  <div class="meta-item"><span class="meta-label">話者</span><span class="meta-value">ゲストA</span></div>
</div>
<div class="tags"><span class="tag">不動産</span></div>
<section><h2>内容整理</h2>
<div class="content-block"><p>追加のインタビュー内容。マーケティング戦略について。</p></div>
</section>
</body></html>""", encoding="utf-8")

        # index.htmlも作成（一覧から除外されるべき）
        (pages_dir / "index.html").write_text("<html><body>index</body></html>", encoding="utf-8")

        yield pages_dir


class TestKnowledgePageIntegration:
    """KnowledgePageIntegration単体テスト"""

    def test_list_pages(self, temp_pages_dir):
        kp = KnowledgePageIntegration(pages_dir=temp_pages_dir)
        pages = kp.list_pages()
        assert len(pages) == 3
        # index.htmlが含まれないことを確認
        ids = [p["id"] for p in pages]
        assert "index" not in ids

    def test_list_pages_sorted_reverse(self, temp_pages_dir):
        kp = KnowledgePageIntegration(pages_dir=temp_pages_dir)
        pages = kp.list_pages()
        # 日付降順（新しい順）
        dates = [p["date"] for p in pages]
        assert dates == sorted(dates, reverse=True)

    def test_list_pages_metadata(self, temp_pages_dir):
        kp = KnowledgePageIntegration(pages_dir=temp_pages_dir)
        pages = kp.list_pages()
        # 最新ページ（20260217）のメタ情報確認
        latest = pages[0]
        assert latest["date"] == "2026-02-17"
        assert "ゲストA" in latest["speakers"]

    def test_get_page_content(self, temp_pages_dir):
        kp = KnowledgePageIntegration(pages_dir=temp_pages_dir)
        html = kp.get_page_content("20260215_テストゲストAさん")
        assert html is not None
        assert "<title>テストゲストA</title>" in html

    def test_get_page_content_not_found(self, temp_pages_dir):
        kp = KnowledgePageIntegration(pages_dir=temp_pages_dir)
        assert kp.get_page_content("nonexistent_page") is None

    def test_get_page_text(self, temp_pages_dir):
        kp = KnowledgePageIntegration(pages_dir=temp_pages_dir)
        text = kp.get_page_text("20260215_テストゲストAさん")
        assert text is not None
        assert "不動産投資" in text

    def test_get_page_meta(self, temp_pages_dir):
        kp = KnowledgePageIntegration(pages_dir=temp_pages_dir)
        meta = kp.get_page_meta("20260215_テストゲストAさん")
        assert meta is not None
        assert meta["title"] == "テストゲストA"
        assert meta["date"] == "2026-02-15"
        assert "不動産" in meta["tags"]
        assert meta["meta"]["話者"] == "ゲストA"

    def test_search_knowledge(self, temp_pages_dir):
        kp = KnowledgePageIntegration(pages_dir=temp_pages_dir)
        results = kp.search_knowledge("不動産")
        assert len(results) >= 1
        # ページ1（不動産投資）がヒット
        ids = [r["id"] for r in results]
        assert "20260215_テストゲストAさん" in ids

    def test_search_knowledge_no_results(self, temp_pages_dir):
        kp = KnowledgePageIntegration(pages_dir=temp_pages_dir)
        results = kp.search_knowledge("存在しないキーワード12345")
        assert len(results) == 0

    def test_search_knowledge_snippet(self, temp_pages_dir):
        kp = KnowledgePageIntegration(pages_dir=temp_pages_dir)
        results = kp.search_knowledge("マーケティング")
        assert len(results) >= 1
        # スニペットにマーケティングが含まれる
        assert "マーケティング" in results[0]["snippet"].lower() or "マーケティング" in results[0]["snippet"]

    def test_get_guest_knowledge_by_filename(self, temp_pages_dir):
        kp = KnowledgePageIntegration(pages_dir=temp_pages_dir)
        results = kp.get_guest_knowledge("ゲストA")
        # ファイル名に「ゲストA」を含む2ページがヒット
        assert len(results) >= 2
        ids = [r["id"] for r in results]
        assert "20260215_テストゲストAさん" in ids
        assert "20260217_ゲストAさん追加インタビュー" in ids

    def test_get_guest_knowledge_by_speaker(self, temp_pages_dir):
        kp = KnowledgePageIntegration(pages_dir=temp_pages_dir)
        results = kp.get_guest_knowledge("ゲストB")
        assert len(results) >= 1
        assert results[0]["speakers"] == "ゲストB"

    def test_get_guest_knowledge_no_results(self, temp_pages_dir):
        kp = KnowledgePageIntegration(pages_dir=temp_pages_dir)
        results = kp.get_guest_knowledge("存在しない人物")
        assert len(results) == 0

    def test_empty_directory(self):
        """存在しないディレクトリで空リストを返す"""
        kp = KnowledgePageIntegration(pages_dir=Path("/tmp/nonexistent_dir_12345"))
        assert kp.list_pages() == []
        assert kp.search_knowledge("test") == []
        assert kp.get_guest_knowledge("test") == []


# --- 実データテスト（~/video-knowledge-pages/ が存在する場合のみ） ---


REAL_PAGES_DIR = Path.home() / "video-knowledge-pages"


@pytest.mark.skipif(not REAL_PAGES_DIR.exists(), reason="実データディレクトリが存在しない")
class TestKnowledgePageIntegrationReal:
    """実データを使ったテスト"""

    def test_list_pages_real(self):
        kp = KnowledgePageIntegration()
        pages = kp.list_pages()
        assert len(pages) > 100  # 166ページ以上存在するはず
        # 各ページにIDと日付がある
        for page in pages[:5]:
            assert page["id"]
            assert page["date"]

    def test_get_page_content_hirai(self):
        kp = KnowledgePageIntegration()
        html = kp.get_page_content("20260215_20251123撮影_hiraiさん30代中盤内資系生保マーケ年収850万円")
        assert html is not None
        assert "hirai" in html

    def test_search_knowledge_teko(self):
        kp = KnowledgePageIntegration()
        results = kp.search_knowledge("TEKO")
        assert len(results) > 0

    def test_get_guest_knowledge_hirai(self):
        kp = KnowledgePageIntegration()
        results = kp.get_guest_knowledge("hirai")
        assert len(results) >= 1
