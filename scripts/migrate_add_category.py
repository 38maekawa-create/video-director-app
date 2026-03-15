#!/usr/bin/env python3
"""DBマイグレーション: projectsテーブルにcategoryカラムを追加し、既存データを自動分類する

カテゴリ:
- teko_member: TEKOメンバー対談
- teko_realestate: TEKO不動産対談
- NULL: 未分類

自動分類ロジック:
- タイトル・ゲスト名に不動産関連キーワードがあれば teko_realestate
- それ以外は teko_member
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / "AI開発10" / ".data" / "video_director.db"

# 不動産関連キーワード（タイトルまたはゲスト名に含まれる場合 teko_realestate）
REALESTATE_KEYWORDS = [
    "物件", "不動産", "楽街", "PAY", "pay", "投資",
    "CF", "キャッシュフロー", "融資", "利回り",
    "区分", "一棟", "大家", "賃貸", "eBay",
    "海運", "PIVOT", "pivot",
]

# 既知の不動産関連ゲスト名（ハオさん: 不動産+eBay投資家、PAYさん等）
REALESTATE_GUESTS = [
    "ハオさん",
    "PAYさん",
]

# テストデータのIDパターン（分類対象外）
TEST_ID_PATTERNS = ["test_"]


def migrate():
    """categoryカラムを追加し、既存データを自動分類する"""
    if not DB_PATH.exists():
        print(f"[ERROR] DBが見つかりません: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # カラム存在チェック
    columns = [row[1] for row in conn.execute("PRAGMA table_info(projects)").fetchall()]
    if "category" in columns:
        print("[INFO] categoryカラムは既に存在します。自動分類のみ実行します。")
    else:
        print("[MIGRATE] categoryカラムを追加します...")
        conn.execute("ALTER TABLE projects ADD COLUMN category TEXT")
        conn.commit()
        print("[MIGRATE] categoryカラム追加完了")

    # 既存データの自動分類
    rows = conn.execute("SELECT id, title, guest_name FROM projects WHERE category IS NULL").fetchall()
    if not rows:
        print("[INFO] 未分類のプロジェクトはありません。")
        conn.close()
        return

    print(f"[CLASSIFY] {len(rows)}件の未分類プロジェクトを自動分類します...")

    classified = {"teko_member": [], "teko_realestate": [], "skipped": []}

    for row in rows:
        pid = row["id"]
        title = row["title"] or ""
        guest = row["guest_name"] or ""

        # テストデータはスキップ
        if any(pid.startswith(pat) for pat in TEST_ID_PATTERNS):
            classified["skipped"].append(pid)
            continue

        # 不動産判定
        is_realestate = False

        # ゲスト名ベース判定
        if any(g in guest for g in REALESTATE_GUESTS):
            is_realestate = True

        # タイトル・ゲスト名のキーワードベース判定
        combined = title + " " + guest
        if any(kw.lower() in combined.lower() for kw in REALESTATE_KEYWORDS):
            is_realestate = True

        category = "teko_realestate" if is_realestate else "teko_member"
        classified[category].append(f"{pid} ({guest})")

        conn.execute(
            "UPDATE projects SET category = ? WHERE id = ?",
            (category, pid),
        )

    conn.commit()
    conn.close()

    # レポート出力
    print(f"\n[RESULT] 自動分類結果:")
    print(f"  TEKOメンバー対談:   {len(classified['teko_member'])}件")
    for item in classified['teko_member']:
        print(f"    - {item}")
    print(f"  TEKO不動産対談:     {len(classified['teko_realestate'])}件")
    for item in classified['teko_realestate']:
        print(f"    - {item}")
    if classified['skipped']:
        print(f"  スキップ（テスト）: {len(classified['skipped'])}件")
        for item in classified['skipped']:
            print(f"    - {item}")


if __name__ == "__main__":
    migrate()
