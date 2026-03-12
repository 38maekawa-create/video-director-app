#!/usr/bin/env python3
"""プロジェクトにdirection_report_urlを紐付けるスクリプト

GitHub Pagesに公開済みのレポートファイル名から、
DBプロジェクトとマッチングしてURLを設定する。

使い方:
    cd ~/AI開発10
    source venv/bin/activate
    python scripts/update_report_urls.py
"""

import json
import re
import urllib.request
import urllib.parse

API_BASE = "http://localhost:8210"
PAGES_BASE = "https://38maekawa-create.github.io/direction-pages"

# GitHub Pagesのレポートファイル一覧
REPORT_FILES = [
    "20251123_Izu_direction.html",
    "20251123_hirai_direction.html",
    "20251123_こも_direction.html",
    "20251123_てぃーひろ_direction.html",
    "20251123_りょうすけ_direction.html",
    "20251130_さるビール_direction.html",
    "20251130_みんてぃあ_direction.html",
    "20251130_真生_direction.html",
    "20251213_PAY_direction.html",
    "20251213_しお_direction.html",
    "20251213_ゆきもる_direction.html",
    "20251213_スリマン_direction.html",
    "20260124_RYO_direction.html",
    "20260124_やーまん_direction.html",
    "20260124_ろく_direction.html",
    "20260125_ひろきょう_direction.html",
    "20260125_松本_direction.html",
    "20260215_あさかつ_direction.html",
    "20260215_くますけ_direction.html",
    "20260215_アンディ_direction.html",
    "20260215_ロキ_direction.html",
    "20260310_kos_direction.html",
    "20260310_けー_direction.html",
    "20260310_さくら_direction.html",
    "20260310_さといも・トーマス_direction.html",
    "20260310_ゆりか_direction.html",
    "20260310_コテ_direction.html",
    "20260310_ハオ_direction.html",
    "20260310_メンイチ_direction.html",
]


def get_projects():
    """APIからプロジェクト一覧を取得"""
    req = urllib.request.Request(f"{API_BASE}/api/projects")
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read().decode("utf-8"))


def update_project_url(project_id, url):
    """プロジェクトのdirection_report_urlを更新"""
    # まずプロジェクトデータを取得
    pid = urllib.parse.quote(project_id, safe="")
    req = urllib.request.Request(f"{API_BASE}/api/projects/{pid}")
    resp = urllib.request.urlopen(req, timeout=10)
    project = json.loads(resp.read().decode("utf-8"))

    # direction_report_urlを設定してPUT
    project["direction_report_url"] = url
    # JSON系フィールドはそのまま渡す
    body = json.dumps(project, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}/api/projects/{pid}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read().decode("utf-8"))


def normalize(s):
    """マッチング用に文字列を正規化"""
    s = s.lower()
    s = re.sub(r"[_\-・（）\(\)\s]", "", s)
    s = re.sub(r"さん$", "", s)
    return s


def main():
    projects = get_projects()
    print(f"プロジェクト数: {len(projects)}件")
    print(f"レポートファイル数: {len(REPORT_FILES)}件\n")

    matched = 0
    unmatched_reports = []

    for filename in REPORT_FILES:
        # ファイル名からゲスト名を抽出（例: 20251123_Izu_direction.html → Izu）
        m = re.match(r"\d{8}_(.+)_direction\.html", filename)
        if not m:
            continue
        report_guest = m.group(1)
        report_norm = normalize(report_guest)
        url = f"{PAGES_BASE}/{urllib.parse.quote(filename)}"

        # プロジェクトとマッチング
        best_match = None
        best_score = 0

        for p in projects:
            guest_norm = normalize(p["guest_name"])
            # 完全一致
            if report_norm == guest_norm:
                best_match = p
                best_score = 100
                break
            # 部分一致
            if report_norm in guest_norm or guest_norm in report_norm:
                score = len(report_norm) + len(guest_norm)
                if score > best_score:
                    best_match = p
                    best_score = score

        if best_match and best_score > 0:
            # 既にURLが設定されていればスキップ
            if best_match.get("direction_report_url"):
                print(f"  ⏭️ スキップ（設定済み）: {report_guest} → {best_match['id']}")
            else:
                result = update_project_url(best_match["id"], url)
                print(f"  ✅ 紐付け: {report_guest} → {best_match['id']}")
            matched += 1
        else:
            unmatched_reports.append(f"{report_guest} ({filename})")

    print(f"\n📊 結果: {matched}件マッチ / {len(unmatched_reports)}件未マッチ")
    if unmatched_reports:
        print("未マッチ:")
        for r in unmatched_reports:
            print(f"  - {r}")


if __name__ == "__main__":
    main()
