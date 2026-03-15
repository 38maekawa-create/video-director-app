"""動画ナレッジページとの連携モジュール

AI開発5（動画ナレッジシステム）で生成されたHTMLナレッジページを
映像エージェントから参照・検索できるようにする。

ナレッジページは ~/video-knowledge-pages/ に保存されている。
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional


# ナレッジページの保存先
PAGES_DIR = Path.home() / "video-knowledge-pages"


class _HTMLTextExtractor(HTMLParser):
    """HTMLからテキストを抽出する簡易パーサー"""

    def __init__(self):
        super().__init__()
        self._text_parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]):
        if tag in ("style", "script"):
            self._skip = True

    def handle_endtag(self, tag: str):
        if tag in ("style", "script"):
            self._skip = False

    def handle_data(self, data: str):
        if not self._skip:
            self._text_parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._text_parts)


class _HTMLMetaExtractor(HTMLParser):
    """HTMLからメタ情報を抽出するパーサー"""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.tags: list[str] = []
        self.meta_items: dict[str, str] = {}
        self.summary_lines: list[str] = []
        # 内部状態
        self._in_title = False
        self._in_tag = False
        self._in_meta_label = False
        self._in_meta_value = False
        self._in_summary_li = False
        self._in_h1 = False
        self._current_label = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]):
        attr_dict = dict(attrs)
        cls = attr_dict.get("class", "")

        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self._in_h1 = True
        elif tag == "span" and "tag" in cls:
            self._in_tag = True
        elif tag == "span" and "meta-label" in cls:
            self._in_meta_label = True
        elif tag == "span" and "meta-value" in cls:
            self._in_meta_value = True
        elif tag == "li":
            self._in_summary_li = True

    def handle_endtag(self, tag: str):
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        elif tag == "span":
            self._in_tag = False
            self._in_meta_label = False
            self._in_meta_value = False
        elif tag == "li":
            self._in_summary_li = False

    def handle_data(self, data: str):
        text = data.strip()
        if not text:
            return

        if self._in_title:
            self.title = text
        elif self._in_h1 and not self.title:
            self.title = text
        elif self._in_tag:
            self.tags.append(text)
        elif self._in_meta_label:
            self._current_label = text
        elif self._in_meta_value and self._current_label:
            self.meta_items[self._current_label] = text
            self._current_label = ""
        elif self._in_summary_li:
            self.summary_lines.append(text)


def _extract_html_text(html_content: str) -> str:
    """HTMLからプレーンテキストを抽出"""
    extractor = _HTMLTextExtractor()
    extractor.feed(html_content)
    return extractor.get_text()


def _extract_meta(html_content: str) -> dict:
    """HTMLからメタ情報を抽出"""
    extractor = _HTMLMetaExtractor()
    extractor.feed(html_content)
    return {
        "title": extractor.title,
        "tags": extractor.tags,
        "meta": extractor.meta_items,
        "summary": extractor.summary_lines,
    }


def _parse_filename(filename: str) -> dict:
    """ファイル名からメタ情報を抽出

    形式: YYYYMMDD_タイトル.html
    """
    stem = Path(filename).stem
    # 日付部分を抽出
    match = re.match(r"^(\d{8})_(.+)$", stem)
    if match:
        date_str = match.group(1)
        title_part = match.group(2)
        return {
            "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
            "filename_title": title_part,
        }
    return {"date": "", "filename_title": stem}


class KnowledgePageIntegration:
    """動画ナレッジページとの連携"""

    def __init__(self, pages_dir: Optional[Path] = None):
        self.pages_dir = pages_dir or PAGES_DIR

    def list_pages(self) -> list[dict]:
        """利用可能なナレッジページ一覧を返す

        Returns:
            各ページの基本情報（id, title, date, tags, speakers等）のリスト
        """
        if not self.pages_dir.exists():
            return []

        pages = []
        for html_file in sorted(self.pages_dir.glob("*.html"), reverse=True):
            if html_file.name == "index.html":
                continue

            file_info = _parse_filename(html_file.name)
            page_id = html_file.stem

            # メタ情報をHTMLから抽出
            try:
                content = html_file.read_text(encoding="utf-8")
                meta = _extract_meta(content)
            except Exception:
                meta = {"title": "", "tags": [], "meta": {}, "summary": []}

            pages.append({
                "id": page_id,
                "filename": html_file.name,
                "title": meta["title"] or file_info["filename_title"],
                "date": file_info["date"],
                "tags": meta["tags"],
                "speakers": meta["meta"].get("話者", ""),
                "category": meta["meta"].get("カテゴリ", ""),
                "source_type": meta["meta"].get("種別", ""),
                "duration": meta["meta"].get("動画時間", ""),
                "summary": meta["summary"],
            })

        return pages

    def get_page_content(self, page_id: str) -> Optional[str]:
        """特定のナレッジページのHTML全文を返す

        Args:
            page_id: ページID（拡張子なしのファイル名）

        Returns:
            HTMLコンテンツ。見つからない場合はNone
        """
        html_path = self.pages_dir / f"{page_id}.html"
        if not html_path.exists():
            return None

        try:
            return html_path.read_text(encoding="utf-8")
        except Exception:
            return None

    def get_page_text(self, page_id: str) -> Optional[str]:
        """特定のナレッジページのテキスト（HTMLタグ除去済み）を返す

        Args:
            page_id: ページID

        Returns:
            プレーンテキスト。見つからない場合はNone
        """
        html = self.get_page_content(page_id)
        if html is None:
            return None
        return _extract_html_text(html)

    def get_page_meta(self, page_id: str) -> Optional[dict]:
        """特定のナレッジページのメタ情報を返す

        Args:
            page_id: ページID

        Returns:
            メタ情報dict。見つからない場合はNone
        """
        html = self.get_page_content(page_id)
        if html is None:
            return None

        file_info = _parse_filename(f"{page_id}.html")
        meta = _extract_meta(html)

        return {
            "id": page_id,
            "title": meta["title"] or file_info["filename_title"],
            "date": file_info["date"],
            "tags": meta["tags"],
            "meta": meta["meta"],
            "summary": meta["summary"],
        }

    def search_knowledge(self, query: str) -> list[dict]:
        """ナレッジ内を全文検索

        タイトル、タグ、要約、本文テキストをすべて検索対象とする。

        Args:
            query: 検索クエリ（部分一致）

        Returns:
            マッチしたページのリスト（スニペット付き）
        """
        if not self.pages_dir.exists():
            return []

        query_lower = query.lower()
        results = []

        for html_file in sorted(self.pages_dir.glob("*.html"), reverse=True):
            if html_file.name == "index.html":
                continue

            try:
                content = html_file.read_text(encoding="utf-8")
            except Exception:
                continue

            # テキスト抽出
            text = _extract_html_text(content).lower()
            if query_lower not in text:
                continue

            # メタ情報抽出
            meta = _extract_meta(content)
            file_info = _parse_filename(html_file.name)
            page_id = html_file.stem

            # スニペット生成（マッチ箇所の前後を抽出）
            snippet = self._make_snippet(text, query_lower)

            results.append({
                "id": page_id,
                "filename": html_file.name,
                "title": meta["title"] or file_info["filename_title"],
                "date": file_info["date"],
                "tags": meta["tags"],
                "speakers": meta["meta"].get("話者", ""),
                "snippet": snippet,
            })

        return results

    def get_guest_knowledge(self, guest_name: str) -> list[dict]:
        """特定ゲストに関連するナレッジ一覧

        ファイル名、タイトル、話者メタデータ、タグからゲスト名を検索する。

        Args:
            guest_name: ゲスト名（部分一致）

        Returns:
            関連ページのリスト
        """
        if not self.pages_dir.exists():
            return []

        guest_lower = guest_name.lower()
        results = []

        for html_file in sorted(self.pages_dir.glob("*.html"), reverse=True):
            if html_file.name == "index.html":
                continue

            file_info = _parse_filename(html_file.name)
            filename_lower = html_file.name.lower()

            # ファイル名マッチ
            if guest_lower in filename_lower:
                try:
                    content = html_file.read_text(encoding="utf-8")
                    meta = _extract_meta(content)
                except Exception:
                    meta = {"title": "", "tags": [], "meta": {}, "summary": []}

                results.append({
                    "id": html_file.stem,
                    "filename": html_file.name,
                    "title": meta["title"] or file_info["filename_title"],
                    "date": file_info["date"],
                    "tags": meta["tags"],
                    "speakers": meta["meta"].get("話者", ""),
                    "summary": meta["summary"],
                    "match_source": "filename",
                })
                continue

            # HTMLメタ情報マッチ
            try:
                content = html_file.read_text(encoding="utf-8")
                meta = _extract_meta(content)
            except Exception:
                continue

            # 話者、タイトル、タグでマッチ
            speakers = meta["meta"].get("話者", "").lower()
            title = meta["title"].lower()
            tags_text = " ".join(meta["tags"]).lower()

            if guest_lower in speakers or guest_lower in title or guest_lower in tags_text:
                results.append({
                    "id": html_file.stem,
                    "filename": html_file.name,
                    "title": meta["title"] or file_info["filename_title"],
                    "date": file_info["date"],
                    "tags": meta["tags"],
                    "speakers": meta["meta"].get("話者", ""),
                    "summary": meta["summary"],
                    "match_source": "meta",
                })

        return results

    def _make_snippet(self, text: str, query: str, context_len: int = 100) -> str:
        """検索クエリ周辺のスニペットを生成"""
        idx = text.find(query)
        if idx == -1:
            return text[:200]

        start = max(0, idx - context_len)
        end = min(len(text), idx + len(query) + context_len)
        snippet = text[start:end].strip()

        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."

        return snippet
