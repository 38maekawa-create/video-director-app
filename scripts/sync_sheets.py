#!/usr/bin/env python3
"""DBのedited_video URLをスプレッドシートに反映するスクリプト

DBに登録済みのVimeo編集済みURLを、スプシの「Vimeo編集済URL」列に書き込む。
sheets_manager.pyのマッチング機能を活用してゲスト名を突合する。

使い方:
  python3 scripts/sync_sheets.py              # dry-run（デフォルト）
  python3 scripts/sync_sheets.py --execute    # 実際に書き込み

注意:
  - デフォルトはdry-run。--executeを付けないと書き込みは行われない
  - 空セルのみ書き込み（既存データは上書きしない）
  - NFKC正規化を使用（Vimeo突合の教訓）
"""

import sqlite3
import sys
import time
import unicodedata
from pathlib import Path

# プロジェクトルートをsys.pathに追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from video_direction.integrations.sheets_manager import (
    SheetsManager,
    _match_guest_name,
    _normalize_name,
    HEADER_ROW,
    TITLE_COL,
)

# スプシに書き込む列のヘッダー名
VIMEO_URL_COLUMN_HEADER = "Vimeo編集済URL"


def get_db_projects_with_edited_video() -> list[dict]:
    """DBからedited_videoが設定済みのプロジェクトを取得"""
    db_path = PROJECT_ROOT / ".data" / "video_director.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, guest_name, edited_video FROM projects "
        "WHERE edited_video IS NOT NULL AND edited_video != '' "
        "AND id != 'test_ef_project' "
        "ORDER BY guest_name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def find_vimeo_url_column(manager: SheetsManager) -> int:
    """「Vimeo」列のインデックス（1-based）を取得

    スプシの14列目に既存の「Vimeo」ヘッダーがある。
    Vimeo/vimeo を含むヘッダーを検索し、見つからなければエラー。
    """
    manager._connect()
    header_row = manager._worksheet.row_values(HEADER_ROW)

    # 既存の列を探す（NFKC正規化で比較）
    for i, cell in enumerate(header_row, start=1):
        cell_norm = unicodedata.normalize("NFKC", cell.strip().lower())
        if "vimeo" in cell_norm:
            return i

    raise ValueError(
        "スプシに「Vimeo」列が見つかりません。"
        f"ヘッダー行（Row {HEADER_ROW}）を確認してください。"
    )


def run_sync(dry_run: bool = True):
    """メイン同期処理"""
    log_prefix = "[DRY-RUN] " if dry_run else ""

    # 1. DBからedited_video設定済みプロジェクトを取得
    projects = get_db_projects_with_edited_video()
    print(f"{log_prefix}DB: edited_video設定済み {len(projects)}件")
    for p in projects:
        print(f"  {p['guest_name']:20s} | {p['edited_video']}")

    if not projects:
        print(f"\n{log_prefix}書き込み対象なし。終了。")
        return

    # 2. スプレッドシート接続
    print(f"\n{log_prefix}スプレッドシートに接続中...")
    manager = SheetsManager()
    manager._connect()

    # 3. Vimeo編集済URL列を取得/作成
    url_col = find_vimeo_url_column(manager)
    print(f"{log_prefix}Vimeo編集済URL列: {url_col}列目")

    # 4. スプシの全タイトルを取得
    title_cells = manager._worksheet.col_values(TITLE_COL)
    sheet_rows = [
        (row_idx, title)
        for row_idx, title in enumerate(title_cells, start=1)
        if row_idx > HEADER_ROW and title.strip()
    ]
    print(f"{log_prefix}スプシ: {len(sheet_rows)}行のデータ")

    # 5. 突合
    print(f"\n{'='*60}")
    print(f"{log_prefix}突合結果:")
    print(f"{'='*60}")

    matched_count = 0
    written_count = 0
    skipped_existing = 0
    unmatched = []

    for p in projects:
        guest_name = p["guest_name"]
        url = p["edited_video"]

        # スプシの各行と突合
        matched_row = None
        matched_title = None
        for row_idx, title in sheet_rows:
            if _match_guest_name(guest_name, title):
                matched_row = row_idx
                matched_title = title
                break

        if matched_row is None:
            unmatched.append(guest_name)
            print(f"  ❌ {guest_name:20s} → マッチなし")
            continue

        matched_count += 1

        # 既存データ確認（空セルのみ書き込み）
        existing_value = manager._worksheet.cell(matched_row, url_col).value
        if existing_value and existing_value.strip():
            skipped_existing += 1
            # 表示は30文字まで
            existing_short = existing_value[:50] + "..." if len(existing_value) > 50 else existing_value
            print(f"  ⏭  {guest_name:20s} → 行{matched_row:3d} | 既存値あり: {existing_short}")
            continue

        # 書き込み
        title_short = matched_title[:40] + "..." if len(matched_title) > 40 else matched_title
        print(f"  ✅ {guest_name:20s} → 行{matched_row:3d} | {title_short}")
        print(f"     URL: {url}")

        if not dry_run:
            manager._worksheet.update_cell(matched_row, url_col, url)
            written_count += 1
            # Google APIレート制限対策（1リクエスト/秒）
            time.sleep(1.2)
        else:
            written_count += 1  # dry-runでも書き込み予定数をカウント

    # 6. サマリー
    print(f"\n{'='*60}")
    print(f"{log_prefix}サマリー:")
    print(f"  DB件数:       {len(projects)}件（edited_video設定済み）")
    print(f"  マッチ成功:   {matched_count}件")
    print(f"  書き込み:     {written_count}件{'（予定）' if dry_run else ''}")
    print(f"  既存スキップ: {skipped_existing}件")
    print(f"  マッチなし:   {len(unmatched)}件")
    if unmatched:
        print(f"  未マッチ一覧: {', '.join(unmatched)}")
    print(f"{'='*60}")

    if dry_run and written_count > 0:
        print(f"\n💡 実際に書き込むには --execute オプションを付けて実行してください:")
        print(f"   python3 scripts/sync_sheets.py --execute")


if __name__ == "__main__":
    execute = "--execute" in sys.argv
    run_sync(dry_run=not execute)
