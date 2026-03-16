#!/usr/bin/env python3
"""タイトル再生成スクリプト（名前修正対応）

対象:
- p-20260125-ひ樹京ひろきょう: 「ひ樹京さん」→「ひろきょうさん」
- p-20260101-坂さん: 「坂さん」→「さくらさん」

mdファイル側は既に修正済み。このスクリプトはmdファイルを再パースし、
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

# 対象プロジェクトとmdファイルのマッピング
TARGETS = [
    {
        "project_id": "p-20260125-ひ樹京ひろきょう",
        "md_path": Path.home() / "TEKO" / "knowledge" / "01_teko" / "sources" / "video" / "2026.02.15_20260125撮影_ひろきょうさん.md",
    },
    {
        "project_id": "p-20260101-坂さん",
        "md_path": Path.home() / "TEKO" / "knowledge" / "01_teko" / "sources" / "video" / "2026.02.28_さくらさん_202512オフ会.md",
    },
]

DB_PATH = Path.home() / "AI開発10" / ".data" / "video_director.db"


def main():
    # ナレッジコンテキストの読み込み（全件共通）
    print("=" * 60)
    print("タイトル再生成スクリプト（名前修正対応）")
    print("=" * 60)

    print("\n📚 ナレッジコンテキスト読み込み中...")
    loader = KnowledgeLoader()
    knowledge_ctx = loader.load()
    print(f"  過去タイトル: {len(knowledge_ctx.past_title_patterns)}件")
    print(f"  マーケティング原則: {'あり' if knowledge_ctx.marketing_principles else 'なし'}")
    print(f"  Z理論: {'あり' if knowledge_ctx.z_theory_summary else 'なし'}")

    conn = sqlite3.connect(str(DB_PATH))

    for target in TARGETS:
        project_id = target["project_id"]
        md_path = target["md_path"]

        print(f"\n{'─' * 60}")
        print(f"📝 処理中: {project_id}")
        print(f"   mdファイル: {md_path}")

        if not md_path.exists():
            print(f"   ❌ mdファイルが見つかりません: {md_path}")
            continue

        # 1. mdファイルをパース
        print("   1/4 mdファイルをパース中...")
        video_data = parse_markdown_file(str(md_path))
        guest_name = video_data.profiles[0].name if video_data.profiles else "不明"
        print(f"       ゲスト名: {guest_name}")

        # 2. ゲスト分類
        print("   2/4 ゲスト分類中...")
        classification = classify_guest(video_data)
        print(f"       分類: {classification.tier_label} ({classification.reason})")

        # 3. 年収評価
        print("   3/4 年収評価中...")
        income_eval = evaluate_income(video_data)
        print(f"       年収: {income_eval.income_value}万円, 強調: {income_eval.emphasize}")

        # 4. タイトル生成（LLM呼び出し — 時間がかかる）
        print("   4/4 タイトル生成中（LLM呼び出し、30秒〜2分かかります）...")
        proposals = generate_title_proposals(
            video_data=video_data,
            classification=classification,
            income_eval=income_eval,
            knowledge_ctx=knowledge_ctx,
        )

        if not proposals.candidates:
            print(f"   ❌ タイトル生成に失敗しました")
            continue

        print(f"   ✅ {len(proposals.candidates)}件のタイトル案を生成")
        for i, c in enumerate(proposals.candidates):
            marker = "★" if i == proposals.recommended_index else " "
            print(f"      {marker}[{i}] {c.title[:70]}...")

        # 名前チェック: 誤表記が含まれていないか確認
        bad_names = ["ひ樹京", "坂さんが"]
        has_bad_name = False
        for c in proposals.candidates:
            for bad in bad_names:
                if bad in c.title:
                    print(f"   ⚠️  まだ誤表記が含まれています: 「{bad}」 in 「{c.title[:50]}...」")
                    has_bad_name = True

        if has_bad_name:
            print("   ⚠️  誤表記が残っていますが、mdファイル由来でなくLLMが再生成したものかもしれません。")
            print("      DB保存は続行します（手動確認推奨）。")

        # DBに保存
        proposals_json = json.dumps({
            "candidates": [
                {
                    "title": c.title,
                    "target_segment": c.target_segment,
                    "appeal_type": c.appeal_type,
                    "rationale": c.rationale,
                }
                for c in proposals.candidates
            ],
            "recommended_index": proposals.recommended_index,
            "llm_raw_response": proposals.llm_raw_response,
        }, ensure_ascii=False)

        cursor = conn.cursor()
        cursor.execute(
            """UPDATE youtube_assets
               SET title_proposals = ?,
                   updated_at = datetime('now')
               WHERE project_id = ?""",
            (proposals_json, project_id),
        )

        if cursor.rowcount == 0:
            print(f"   ⚠️  DB更新対象なし（project_id={project_id}が存在しない可能性）")
        else:
            print(f"   ✅ DB更新完了: {project_id}")

    conn.commit()
    conn.close()

    print(f"\n{'=' * 60}")
    print("全件処理完了")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
