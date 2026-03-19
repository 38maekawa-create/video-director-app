#!/usr/bin/env python3
"""
ディレクションレポート全員分バッチ生成スクリプト

全プロジェクトに対してE2Eパイプライン（FB分析→学習→ディレクション生成）を実行する。
テストプロジェクトは除外。

使い方:
  # dry-run（デフォルト）: 対象一覧を確認するだけ
  python3 scripts/batch_generate_directions.py

  # 実行: 全員分のディレクションレポートを生成
  python3 scripts/batch_generate_directions.py --execute

  # 特定のプロジェクトだけ実行
  python3 scripts/batch_generate_directions.py --execute --project-id p-20251123-陽介

  # 並列数を指定（デフォルト: 1件ずつ順次実行）
  python3 scripts/batch_generate_directions.py --execute --concurrency 3
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
import httpx


# APIサーバーのベースURL
API_BASE = "http://localhost:8210"


def get_all_projects() -> list[dict]:
    """DBから全プロジェクトを取得（テスト除外）"""
    db_path = Path(__file__).resolve().parent.parent / ".data" / "video_director.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, guest_name, title, category FROM projects ORDER BY guest_name"
    ).fetchall()
    conn.close()

    projects = []
    for r in rows:
        # テストプロジェクト除外
        if "テスト" in (r["guest_name"] or ""):
            continue
        if r["id"].startswith("test_"):
            continue
        projects.append(dict(r))
    return projects


async def generate_direction(
    client: httpx.AsyncClient,
    project_id: str,
    guest_name: str,
    timeout: float = 120,
) -> dict:
    """1プロジェクトのディレクションレポートを生成"""
    start = time.time()
    try:
        response = await client.post(
            f"{API_BASE}/api/v1/projects/{project_id}/e2e-pipeline",
            json={},
            timeout=timeout,
        )
        elapsed = time.time() - start

        if response.status_code == 200:
            data = response.json()
            return {
                "project_id": project_id,
                "guest_name": guest_name,
                "status": "success",
                "elapsed_seconds": round(elapsed, 1),
                "summary": data.get("summary", ""),
            }
        else:
            return {
                "project_id": project_id,
                "guest_name": guest_name,
                "status": "error",
                "elapsed_seconds": round(elapsed, 1),
                "error": f"HTTP {response.status_code}: {response.text[:200]}",
            }
    except httpx.TimeoutException:
        elapsed = time.time() - start
        return {
            "project_id": project_id,
            "guest_name": guest_name,
            "status": "timeout",
            "elapsed_seconds": round(elapsed, 1),
            "error": f"タイムアウト（{timeout}秒）",
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "project_id": project_id,
            "guest_name": guest_name,
            "status": "error",
            "elapsed_seconds": round(elapsed, 1),
            "error": str(e),
        }


async def run_batch(
    projects: list[dict],
    concurrency: int = 1,
) -> list[dict]:
    """バッチ実行（並列数制限付き）"""
    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async with httpx.AsyncClient() as client:
        async def process_one(proj: dict) -> dict:
            async with semaphore:
                print(f"  🔄 生成中: {proj['guest_name']} ({proj['id']})")
                result = await generate_direction(
                    client, proj["id"], proj["guest_name"]
                )
                status_icon = "✅" if result["status"] == "success" else "❌"
                print(
                    f"  {status_icon} {proj['guest_name']}: "
                    f"{result['status']} ({result['elapsed_seconds']}秒)"
                )
                return result

        tasks = [process_one(p) for p in projects]
        results = await asyncio.gather(*tasks)

    return list(results)


def main():
    parser = argparse.ArgumentParser(
        description="ディレクションレポート全員分バッチ生成"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="実際に生成を実行する（デフォルトはdry-run）",
    )
    parser.add_argument(
        "--project-id",
        type=str,
        help="特定のプロジェクトIDだけ実行",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="並列実行数（デフォルト: 1）",
    )
    parser.add_argument(
        "--category",
        type=str,
        choices=["teko_member", "teko_realestate"],
        help="特定カテゴリだけ実行",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="確認プロンプトをスキップ",
    )
    args = parser.parse_args()

    projects = get_all_projects()

    # フィルタリング
    if args.project_id:
        projects = [p for p in projects if p["id"] == args.project_id]
        if not projects:
            print(f"❌ プロジェクト '{args.project_id}' が見つかりません")
            sys.exit(1)

    if args.category:
        projects = [p for p in projects if p.get("category") == args.category]

    print(f"\n📋 ディレクションレポート バッチ生成")
    print(f"   対象: {len(projects)}件")
    print(f"   モード: {'🔴 実行' if args.execute else '🟢 dry-run（確認のみ）'}")
    if args.concurrency > 1:
        print(f"   並列数: {args.concurrency}")
    print()

    # 対象一覧を表示
    for i, p in enumerate(projects, 1):
        cat = p.get("category", "未分類") or "未分類"
        print(f"  {i:2d}. {p['guest_name']:15s} [{cat}] ({p['id']})")

    if not args.execute:
        print(f"\n💡 実行するには --execute を付けてください:")
        print(f"   python3 scripts/batch_generate_directions.py --execute")
        return

    # 確認プロンプト
    if not args.yes:
        print(f"\n⚠️  {len(projects)}件のディレクションレポートを生成します。")
        confirm = input("続行しますか？ (y/N): ").strip().lower()
        if confirm != "y":
            print("中止しました。")
            return

    print(f"\n🚀 バッチ生成開始...")
    start_time = time.time()

    results = asyncio.run(run_batch(projects, args.concurrency))

    total_time = time.time() - start_time

    # 結果サマリー
    success = [r for r in results if r["status"] == "success"]
    errors = [r for r in results if r["status"] != "success"]

    print(f"\n{'=' * 60}")
    print(f"📊 バッチ生成結果")
    print(f"   成功: {len(success)}件 / 失敗: {len(errors)}件")
    print(f"   総実行時間: {total_time:.1f}秒")

    if errors:
        print(f"\n❌ 失敗リスト:")
        for e in errors:
            print(f"   {e['guest_name']}: {e['error']}")

    # 結果をJSONファイルに保存
    output_path = (
        Path(__file__).resolve().parent.parent
        / ".data"
        / "batch_direction_results.json"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "total": len(results),
                "success": len(success),
                "errors": len(errors),
                "results": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\n📁 結果保存先: {output_path}")


if __name__ == "__main__":
    main()
