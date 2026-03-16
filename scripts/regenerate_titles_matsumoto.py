#!/usr/bin/env python3
"""松本さんタイトル再生成スクリプト（月商→月利修正対応）

修正内容: 月商→月利に修正済みのmdファイルを再パースし、
title_generator経由でLLMにタイトル案を再生成させ、DBに保存する。
"""

import sys
import json
import sqlite3
from pathlib import Path

# AI開発10のsrcをパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from video_direction.integrations.ai_dev5_connector import parse_markdown_file
from video_direction.analyzer.guest_classifier import classify_guest
from video_direction.analyzer.income_evaluator import evaluate_income
from video_direction.analyzer.title_generator import generate_title_proposals
from video_direction.knowledge.loader import KnowledgeLoader

TARGETS = [
    {
        "project_id": "p-20260125-松本",
        "md_path": Path.home() / "TEKO" / "knowledge" / "01_teko" / "sources" / "video" / "2026.02.15_20260125撮影_松本さん30代前半化学メーカー年収1050万円.md",
    },
]

DB_PATH = Path.home() / "AI開発10" / ".data" / "video_director.db"


def main():
    print("=" * 60)
    print("タイトル再生成スクリプト（松本さん: 月商→月利修正）")
    print("=" * 60)

    print("\n📚 ナレッジコンテキスト読み込み中...")
    loader = KnowledgeLoader()
    knowledge_ctx = loader.load()
    print(f"  過去タイトル: {len(knowledge_ctx.past_title_patterns)}件")

    conn = sqlite3.connect(str(DB_PATH))

    for target in TARGETS:
        project_id = target["project_id"]
        md_path = target["md_path"]

        print(f"\n{'─' * 60}")
        print(f"🎯 対象: {project_id}")
        print(f"  MDファイル: {md_path.name}")

        if not md_path.exists():
            print(f"  ❌ MDファイルが見つかりません: {md_path}")
            continue

        # MDファイルをパース
        print("  📄 MDファイルパース中...")
        parsed = parse_markdown_file(str(md_path))
        if not parsed:
            print(f"  ❌ パース失敗")
            continue

        # ゲスト分類
        print("  🏷️ ゲスト分類中...")
        classification = classify_guest(parsed)
        nickname = getattr(classification, 'nickname', None) or classification.__dict__.get('nickname', '不明')
        print(f"    ニックネーム: {nickname}")

        # 収入評価
        print("  💰 収入評価中...")
        income = evaluate_income(parsed)
        annual = getattr(income, 'annual_income', None) or income.__dict__.get('annual_income', '不明')
        print(f"    年収: {annual}")

        # タイトル生成
        print("  🎬 タイトル候補生成中（LLM呼び出し）...")
        proposals = generate_title_proposals(
            video_data=parsed,
            classification=classification,
            income_eval=income,
            knowledge_ctx=knowledge_ctx,
        )

        if not proposals or not proposals.candidates:
            print(f"  ❌ タイトル生成失敗")
            continue

        candidates = proposals.candidates
        print(f"  ✅ {len(candidates)}件のタイトル候補を生成:")
        for i, c in enumerate(candidates):
            title = c.title if hasattr(c, 'title') else str(c)
            print(f"    [{i}] {title[:80]}...")

        # 月商が含まれていないことを確認
        has_geshou = False
        for c in candidates:
            t = c.title if hasattr(c, 'title') else str(c)
            if "月商" in t:
                has_geshou = True
                print(f"    ⚠️ 警告: 月商が含まれています: {t[:60]}")
        if not has_geshou:
            print(f"    ✅ 月商なし（月利に正しく修正済み）")

        # DBに保存（dataclass → dict変換）
        from dataclasses import asdict
        proposals_json = json.dumps(asdict(proposals), ensure_ascii=False)
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE youtube_assets
               SET title_proposals = ?, updated_at = datetime('now')
               WHERE project_id = ?""",
            (proposals_json, project_id),
        )
        if cursor.rowcount == 0:
            print(f"  ⚠️ DB更新対象なし（project_id={project_id}）")
        else:
            print(f"  ✅ DB更新完了（youtube_assets.title_proposals）")

        conn.commit()

    conn.close()
    print(f"\n{'=' * 60}")
    print("完了！")


if __name__ == "__main__":
    main()
