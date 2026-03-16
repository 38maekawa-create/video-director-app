#!/usr/bin/env python3
"""Vimeo編集済み動画の自動突合スクリプト

Vimeo APIから動画一覧を取得し、命名規則に基づいてDB上のメンバーと自動突合する。
launchdで1時間ごとに実行される想定。

命名規則（対談動画の検出パターン）:
  パターンA（坂野編集）: 番号_名前さん_対談_ステータス_坂野
  パターンB（大胡編集）: 名前さん_対談_ステータス_大胡
  共通: 「さん」+「対談/初稿/修正/完成/FB修正/ボイチャ」を含む

実行:
  python3 scripts/sync_vimeo_edited_videos.py              # 通常実行
  python3 scripts/sync_vimeo_edited_videos.py --dry-run     # 変更なし確認のみ
  python3 scripts/sync_vimeo_edited_videos.py --list-all    # Vimeo全動画タイトルをダンプ
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


# ひらがな↔カタカナ変換用オフセット
_HIRA_START = 0x3041  # ぁ
_HIRA_END = 0x3096    # ゖ
_KATA_START = 0x30A1  # ァ
_KATA_END = 0x30F6    # ヶ
_OFFSET = _KATA_START - _HIRA_START


def _to_hiragana(text: str) -> str:
    """カタカナをひらがなに変換"""
    result = []
    for ch in text:
        cp = ord(ch)
        if _KATA_START <= cp <= _KATA_END:
            result.append(chr(cp - _OFFSET))
        else:
            result.append(ch)
    return "".join(result)


def _to_katakana(text: str) -> str:
    """ひらがなをカタカナに変換"""
    result = []
    for ch in text:
        cp = ord(ch)
        if _HIRA_START <= cp <= _HIRA_END:
            result.append(chr(cp + _OFFSET))
        else:
            result.append(ch)
    return "".join(result)


def _has_hiragana(text: str) -> bool:
    return any(_HIRA_START <= ord(ch) <= _HIRA_END for ch in text)


def _has_katakana(text: str) -> bool:
    return any(_KATA_START <= ord(ch) <= _KATA_END for ch in text)


def _split_compound_name(name: str) -> list[str]:
    """複合名を中黒・スペース・ハイフンで分割して個別名リストを返す"""
    import re
    parts = re.split(r"[・\s\-/／]", name)
    # 空文字除去、元の名前と同じなら分割不要
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) <= 1:
        return []
    return parts


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
    """メンバー名の表記揺れマップを構築（ひらがな/カタカナ相互変換対応）"""
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

        # extras辞書から追加キーを取得
        if base in extras:
            keys.extend(extras[base])

        # 複合名の分割対応（中黒・スペース・ハイフン等）
        compound_parts = _split_compound_name(base)
        if compound_parts:
            keys.extend(compound_parts)
            # extras辞書にない複合名でも自動分割
            for part in compound_parts:
                if part in extras:
                    keys.extend(extras[part])

        # ひらがな/カタカナ相互変換を全キーに適用
        kana_variants = []
        for k in keys:
            if _has_katakana(k):
                kana_variants.append(_to_hiragana(k))
            if _has_hiragana(k):
                kana_variants.append(_to_katakana(k))
        keys.extend(kana_variants)

        # NFKC正規化版も追加
        keys_norm = [unicodedata.normalize("NFKC", k) for k in keys]
        all_keys = list(set(keys + keys_norm))

        # 空文字キーを除去
        all_keys = [k for k in all_keys if k]

        search_map.append({
            "project_id": p["id"],
            "guest_name": gn,
            "keys": all_keys,
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


def find_partial_candidates(title_norm: str, keys: list[str], threshold: int = 2) -> list[str]:
    """部分一致で近い候補を探す（未マッチ時のデバッグ用）"""
    candidates = []
    for key in keys:
        key_norm = unicodedata.normalize("NFKC", key)
        # キーの文字がタイトルに何文字含まれるか
        if len(key_norm) >= threshold:
            common = sum(1 for ch in key_norm if ch in title_norm)
            if common >= threshold and common >= len(key_norm) * 0.5:
                candidates.append(key)
    return candidates


def generate_match_report(
    search_map: list,
    matched_members: dict,
    taidan_videos: list[dict],
    all_videos: list[dict],
    data_dir: Path,
):
    """マッチング結果の詳細レポートをJSON出力"""
    report = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_members": len(search_map),
            "matched": len(matched_members),
            "unmatched": len(search_map) - len(matched_members),
            "total_vimeo_videos": len(all_videos),
            "taidan_videos": len(taidan_videos),
        },
        "matched": [],
        "unmatched": [],
    }

    matched_ids = set(matched_members.keys())

    for entry in search_map:
        pid = entry["project_id"]
        if pid in matched_ids:
            vids = matched_members[pid]
            report["matched"].append({
                "guest_name": entry["guest_name"],
                "videos": [
                    {
                        "title": v["title"],
                        "vimeo_url": v["vimeo_url"],
                        "status": v["status"],
                        "created": v["created"],
                    }
                    for v in vids
                ],
            })
        else:
            # 未マッチ: 候補動画を探す
            near_candidates = []
            for v in taidan_videos:
                title_norm = unicodedata.normalize("NFKC", v["name"])
                matches = find_partial_candidates(title_norm, entry["keys"])
                if matches:
                    near_candidates.append({
                        "title": v["name"],
                        "matched_keys": matches,
                        "status": v.get("status", ""),
                    })

            report["unmatched"].append({
                "guest_name": entry["guest_name"],
                "search_keys": entry["keys"],
                "near_candidates": near_candidates[:5],  # 上位5件まで
            })

    report_path = data_dir / "vimeo_match_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"マッチングレポート出力: {report_path}")


def list_all_videos(token: str):
    """Vimeo上の全動画タイトルをダンプ（--list-all用）"""
    videos = fetch_vimeo_videos(token)
    print(f"Vimeo動画一覧（{len(videos)}本）:\n")
    for i, v in enumerate(videos, 1):
        vid = v["uri"].split("/")[-1]
        status = v.get("status", "unknown")
        created = v.get("created_time", "")[:10]
        is_taidan = "◯" if is_taidan_video(unicodedata.normalize("NFKC", v["name"])) else "　"
        print(f"  {i:3d}. [{status:12s}] {is_taidan} {v['name']}")
        print(f"       https://vimeo.com/{vid}  ({created})")
    print(f"\n合計: {len(videos)}本 / うち対談動画: {sum(1 for v in videos if is_taidan_video(unicodedata.normalize('NFKC', v['name'])))}本")


def run_sync(dry_run: bool = False):
    """メイン同期処理"""
    log_prefix = "[DRY-RUN] " if dry_run else ""
    now = datetime.now().isoformat()

    # トークン取得
    token = load_vimeo_token()

    # DB接続
    data_dir = Path(__file__).parent.parent / ".data"
    db_path = data_dir / "video_director.db"
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

    # 対談動画フィルタ
    taidan_videos = [v for v in videos if is_taidan_video(unicodedata.normalize("NFKC", v["name"]))]
    print(f"{log_prefix}対談動画: {len(taidan_videos)}本")

    # 突合
    matched = []
    non_available = []  # available以外のステータスの動画
    for v in taidan_videos:
        title = v["name"]
        title_norm = unicodedata.normalize("NFKC", title)
        vid = v["uri"].split("/")[-1]
        status = v.get("status", "")

        member = match_video_to_member(title_norm, search_map)
        if not member:
            continue

        entry = {
            "vimeo_id": vid,
            "vimeo_url": f"https://vimeo.com/{vid}",
            "title": title,
            "project_id": member["project_id"],
            "guest_name": member["guest_name"],
            "created": v["created_time"][:10],
            "status": status,
        }

        if status != "available":
            non_available.append(entry)
        matched.append(entry)

    # ステータスフィルタの可視化（available以外の動画を報告）
    if non_available:
        print(f"\n{log_prefix}⚠ available以外のステータスの対談動画:")
        for na in non_available:
            print(f"  [{na['status']:12s}] {na['guest_name']} | {na['title']}")
        print(f"  → これらは存在するがまだ利用不可の動画です\n")

    # メンバーごとに最新版を特定
    by_member = defaultdict(list)
    for m in matched:
        by_member[m["guest_name"]].append(m)

    # レポート用: project_id → 動画リスト
    matched_by_pid = defaultdict(list)
    for m in matched:
        matched_by_pid[m["project_id"]].append(m)

    updated_count = 0
    skipped_count = 0
    for guest, vids in by_member.items():
        vids.sort(key=lambda x: x["created"], reverse=True)
        latest = vids[0]

        # available状態のもののみDB更新
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

    # マッチングレポート出力
    generate_match_report(search_map, matched_by_pid, taidan_videos, videos, data_dir)

    # サマリー
    unmatched_count = len(search_map) - len(by_member)
    print(f"\n{log_prefix}同期完了 ({now})")
    print(f"  突合: {len(by_member)}名 / 未マッチ: {unmatched_count}名 / 更新: {updated_count}件 / スキップ: {skipped_count}件")

    # ログファイルに追記
    if not dry_run:
        log_path = data_dir / "vimeo_sync.log"
        with open(log_path, "a") as f:
            f.write(f"{now} | matched={len(by_member)} unmatched={unmatched_count} updated={updated_count} skipped={skipped_count}\n")


if __name__ == "__main__":
    if "--list-all" in sys.argv:
        t = load_vimeo_token()
        list_all_videos(t)
    else:
        dry = "--dry-run" in sys.argv
        run_sync(dry_run=dry)
