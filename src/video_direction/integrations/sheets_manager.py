from __future__ import annotations
"""J-2: スプシ統合 — 【インタビュー対談動画】管理タブとの連携"""

import re
from pathlib import Path
from google.oauth2.service_account import Credentials
import gspread


SPREADSHEET_ID = "1bW_qb13p747xoa2yf7RHaccNVTFCMxV8a5CjGdNqI6I"
TAB_NAME = "【インタビュー対談動画】管理"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ヘッダー行はRow 2
HEADER_ROW = 2
# B列（タイトル）のインデックス（1-based）
TITLE_COL = 2


class SheetsManager:
    """スプレッドシート連携マネージャー"""

    def __init__(self, credentials_path: str | Path = None):
        if credentials_path is None:
            credentials_path = Path.home() / ".config" / "maekawa" / "google-credentials.json"
        self.credentials_path = Path(credentials_path)
        self._client = None
        self._worksheet = None

    def _connect(self):
        """スプレッドシートに接続（lazy）"""
        if self._worksheet is not None:
            return

        credentials = Credentials.from_service_account_file(
            str(self.credentials_path),
            scopes=SCOPES,
        )
        self._client = gspread.authorize(credentials)
        spreadsheet = self._client.open_by_key(SPREADSHEET_ID)
        self._worksheet = spreadsheet.worksheet(TAB_NAME)

    def find_direction_url_column(self) -> int:
        """ディレクションURL列のインデックス（1-based）を取得。なければ新規作成"""
        self._connect()
        header_row = self._worksheet.row_values(HEADER_ROW)

        # 既存のディレクションURL列を探す
        for i, cell in enumerate(header_row, start=1):
            if "ディレクション" in cell and "URL" in cell:
                return i

        # なければ末尾に新規作成
        new_col = len(header_row) + 1
        self._worksheet.update_cell(HEADER_ROW, new_col, "ディレクションURL")
        return new_col

    def write_direction_url(self, guest_name: str, url: str) -> bool:
        """ゲスト名でマッチングし、対応する行にディレクションURLを書き込む"""
        self._connect()
        url_col = self.find_direction_url_column()

        # B列（タイトル）の全データを取得
        title_cells = self._worksheet.col_values(TITLE_COL)

        # ゲスト名でマッチング
        matched_row = None
        for row_idx, title in enumerate(title_cells, start=1):
            if row_idx <= HEADER_ROW:
                continue
            if _match_guest_name(guest_name, title):
                matched_row = row_idx
                break

        if matched_row is None:
            return False

        # URLを書き込み（既存データは上書きしない → 空セルの場合のみ書き込み）
        existing = self._worksheet.cell(matched_row, url_col).value
        if existing and existing.strip():
            return True  # 既に書き込み済み

        self._worksheet.update_cell(matched_row, url_col, url)
        return True

    def get_all_titles(self) -> list[tuple[int, str]]:
        """全タイトルと行番号のリストを返す"""
        self._connect()
        title_cells = self._worksheet.col_values(TITLE_COL)
        return [
            (row_idx, title)
            for row_idx, title in enumerate(title_cells, start=1)
            if row_idx > HEADER_ROW and title.strip()
        ]


def _match_guest_name(guest_name: str, sheet_title: str) -> bool:
    """ゲスト名がスプシのタイトル（B列）とマッチするか判定

    B列の例: "INT001_ブンさん", "INT015_Izuさん"
    guest_name: "Izu", "ブン", etc.
    """
    if not sheet_title or not guest_name:
        return False

    # 「さん」を除去して比較
    name_clean = guest_name.rstrip("さん").strip()
    title_clean = sheet_title.strip()

    # INT番号の後のゲスト名を抽出
    match = re.search(r"INT\d+[_\s]+(.+?)(?:さん)?$", title_clean)
    if match:
        title_name = match.group(1).strip()
        if name_clean.lower() == title_name.lower():
            return True

    # 番号+名前形式（例: "53.izuさん"）
    num_match = re.search(r"\d+[._]\s*(.+?)(?:さん)?$", title_clean)
    if num_match:
        title_name = num_match.group(1).strip()
        if name_clean.lower() == title_name.lower():
            return True

    # 部分一致（ゲスト名がタイトルに含まれる、大文字小文字無視）
    # 1文字の場合は誤マッチ防止のためスキップ
    if name_clean and len(name_clean) >= 2 and name_clean.lower() in title_clean.lower():
        return True

    return False
