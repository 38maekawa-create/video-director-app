#!/usr/bin/env python3
"""Vimeo編集済み動画の自動突合スクリプト

Vimeo APIから動画一覧を取得し、命名規則に基づいてDB上のメンバーと自動突合する。
launchdで1時間ごとに実行される想定。

命名規則（対談動画の検出パターン）:
  パターンA（坂野編集）: 番号_名前さん_対談_ステータス_坂野
  パターンB（大胡編集）: 名前さん_対談_ステータス_大胡
  共通: 「さん」+「対談/初稿/修正/完成/FB修正/ボイチャ」を含む

実行:
  python3 scripts/sync_vimeo_edited_videos.py          # 通常実行
  python3 scripts/sync_vimeo_edited_videos.py --dry-run # 変更なし確認のみ
"""

import json
import os
import sqlite3
import subprocess
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def load_vimeo_token() -> str:
    """VIMEO_ACCESS_TOKENを環境変数またはapi-keys.envから取得"""
    token = os.environ.get("VIMEO_ACCESS_TOKEN")
    if token:
        return token

    env_file = Path.home() / ".config" / "maekawa" / "api-keys.env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("VIMEO_ACCESS_TOKEN="):
                return line.split("=", 1)[1].strip()

    raise RuntimeError("VIMEO_ACCESS_TOKEN が見つかりません")


def fetch_vimeo_videos(token: str, max_pages: int = 4) -> list[dict]:
    """Vimeo APIから全動画を取得"""
    all_videos = []
    for page in range(1, max_pages + 1):
        result = subprocess.run(
            [
                "curl", "-s",
                "-H", f"Authorization: bearer {token}",
                f"https://api.vimeo.com/me/videos?per_page=100&sort=date&direction=desc&page={page}",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            break
        data = json.loads(result.stdout)
        vids = data.get("data", [])
        if not vids:
            break
        all_videos.extend(vids)
    return all_videos


def is_taidan_video(title: str) -> bool:
    """対談動画かどうかを命名規則で判定"""
    keywords = ["対談", "初稿", "完成", "FB修正", "ボイチャ", "修正", "インタビュー"]
    return any(k in title for k in keywords)


def build_search_map(projects: list) -> list[dict]:
    """メンバー名の表記揺れマップを構築"""
    # 追加の表記揺れ定義
    extras = {
        "Izu": ["lzu", "Izu", "Lzu", "luz"],
        "hirai": ["hirai"],
        "さるビール": ["さるビール"],
        "PAY": ["pay", "PAY", "Pay"],
        "ゆきもる": ["ゆきもる", "ゆきもり", "雪森"],
        "さといも・トーマス": ["トーマス", "さといも"],
        "kos": ["kos", "コスト"],
        "コテ": ["コテツ"],
        "メンイチ": ["メイジ", "メンイチ"],
        "ゆりか": ["ゆりか", "ユリカ"],
        "ハオ": ["ハオ", "羽生"],
        "くますけ": ["クマキ", "くますけ"],
    }

    search_map = []
    for p in projects:
        gn = p["guest_name"]
        base = gn.replace("さん", "").strip()
        keys = [base]
        if base in extras:
            keys.extend(extras[base])
        # NFKC正規化版も追加
        keys_norm = [unicodedata.normalize("NFKC", k) for k in keys]
        search_map.append({
            "project_id": p["id"],
            "guest_name": gn,
            "keys": list(set(keys + keys_norm)),
        })
    return search_map


def match_video_to_member(title_norm: str, search_map: list) -> dict | None:
    """NFKC正規化済みタイトルからメンバーを検索"""
    for entry in search_map:
        for key in entry["keys"]:
            key_norm = unicodedata.normalize("NFKC", key)
            if key_norm in title_norm:
                return entry
    return None


def run_sync(dry_run: bool = False):
    """メイン同期処理"""
    log_prefix = "[DRY-RUN] " if dry_run else ""
    now = datetime.now().isoformat()

    # トークン取得
    token = load_vimeo_token()

    # DB接続
    db_path = Path(__file__).parent.parent / ".data" / "video_director.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # メンバー取得
    projects = conn.execute(
        'SELECT id, guest_name, edited_video FROM projects WHERE id != "test_ef_project"'
    ).fetchall()
    projects = [dict(p) for p in projects]
    search_map = build_search_map(projects)

    # 既存のedited_video（更新不要なものをスキップ用）
    existing = {p["id"]: p["edited_video"] for p in projects}

    # Vimeo動画取得
    videos = fetch_vimeo_videos(token)
    print(f"{log_prefix}Vimeo動画取得: {len(videos)}本")

    # 対談動画フィルタ + 突合
    matched = []
    for v in videos:
        title = v["name"]
        title_norm = unicodedata.normalize("NFKC", title)
        vid = v["uri"].split("/")[-1]

        if not is_taidan_video(title_norm):
            continue

        member = match_video_to_member(title_norm, search_map)
        if not member:
            continue

        matched.append({
            "vimeo_id": vid,
            "vimeo_url": f"https://vimeo.com/{vid}",
            "title": title,
            "project_id": member["project_id"],
            "guest_name": member["guest_name"],
            "created": v["created_time"][:10],
            "status": v.get("status", ""),
        })

    # メンバーごとに最新版を特定
    by_member = defaultdict(list)
    for m in matched:
        by_member[m["guest_name"]].append(m)

    updated_count = 0
    skipped_count = 0
    for guest, vids in by_member.items():
        vids.sort(key=lambda x: x["created"], reverse=True)
        latest = vids[0]

        # available状態のもののみ
        if latest["status"] != "available":
            continue

        pid = latest["project_id"]
        new_url = latest["vimeo_url"]

        # 変更がなければスキップ
        if existing.get(pid) == new_url:
            skipped_count += 1
            continue

        old_url = existing.get(pid) or "null"
        print(f"{log_prefix}更新: {guest} | {old_url} → {new_url}")

        if not dry_run:
            conn.execute(
                'UPDATE projects SET edited_video = ?, updated_at = datetime("now") WHERE id = ?',
                (new_url, pid),
            )
        updated_count += 1

    if not dry_run:
        conn.commit()

    conn.close()

    # サマリー
    print(f"\n{log_prefix}同期完了 ({now})")
    print(f"  突合: {len(by_member)}名 / 更新: {updated_count}件 / スキップ: {skipped_count}件")

    # ログファイルに追記
    if not dry_run:
        log_path = Path(__file__).parent.parent / ".data" / "vimeo_sync.log"
        with open(log_path, "a") as f:
            f.write(f"{now} | matched={len(by_member)} updated={updated_count} skipped={skipped_count}\n")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run_sync(dry_run=dry)
