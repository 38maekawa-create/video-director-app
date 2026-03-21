#!/usr/bin/env python3
"""
概要欄のみ再生成スクリプト

T-043: 概要欄バグ修正後の全件再生成
- 修正A（パース後バリデーション）適用済み
- 修正B（プロンプト矛盾解消）適用済み
- 修正C（DB上書き防止）適用済み

使い方:
  # dry-run: 対象一覧確認のみ
  python3 scripts/regenerate_descriptions.py

  # 実行: 全件の概要欄を再生成
  python3 scripts/regenerate_descriptions.py --execute

  # 空の概要欄のみ再生成
  python3 scripts/regenerate_descriptions.py --execute --empty-only

  # 特定プロジェクトのみ
  python3 scripts/regenerate_descriptions.py --execute --project-id p-20260101-けーさん
"""

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

# プロジェクトルートをパスに追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / ".data" / "video_director.db"
LOG_PATH = PROJECT_ROOT / ".data" / f"description_regen_{time.strftime('%Y%m%d_%H%M%S')}.log"


def get_projects(empty_only: bool = False, project_id: str = None) -> list[dict]:
    """対象プロジェクトを取得"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    query = """
        SELECT p.id, p.guest_name, p.title, p.category, p.knowledge,
               p.guest_age, p.guest_occupation,
               ya.description_original, length(ya.description_original) as desc_len
        FROM projects p
        LEFT JOIN youtube_assets ya ON p.id = ya.project_id
        WHERE p.guest_name NOT LIKE '%テスト%'
          AND p.id NOT LIKE 'test_%'
    """
    params = []

    if project_id:
        query += " AND p.id = ?"
        params.append(project_id)

    if empty_only:
        query += " AND (ya.description_original IS NULL OR length(ya.description_original) < 50)"

    query += " ORDER BY p.guest_name"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def regenerate_description_for_project(project_data: dict) -> dict:
    """1プロジェクトの概要欄を再生成（LLM呼び出し含む）"""
    from src.video_direction.integrations.ai_dev5_connector import VideoData, PersonProfile
    from src.video_direction.analyzer.guest_classifier import ClassificationResult
    from src.video_direction.analyzer.income_evaluator import IncomeEvaluation
    from src.video_direction.analyzer.description_writer import generate_description
    from src.video_direction.knowledge.loader import KnowledgeLoader
    from src.video_direction.analyzer.proper_noun_filter import detect_proper_nouns

    project_id = project_data["id"]
    guest_name = project_data["guest_name"]

    start = time.time()

    try:
        # VideoDataの構築
        video_data = VideoData(
            title=project_data.get("title", ""),
            speakers=guest_name or "",
        )

        # カテゴリ設定
        video_data.category = project_data.get("category", "")

        # knowledgeからプロフィール補完
        knowledge_json = project_data.get("knowledge")
        if knowledge_json:
            try:
                kd = json.loads(knowledge_json) if isinstance(knowledge_json, str) else knowledge_json
                profiles_data = kd.get("profiles", [])
                if profiles_data:
                    p = profiles_data[0]
                    video_data.profiles = [PersonProfile(
                        name=p.get("name", guest_name or ""),
                        age=p.get("age", str(project_data.get("guest_age", "")) if project_data.get("guest_age") else ""),
                        occupation=p.get("occupation", project_data.get("guest_occupation", "")),
                        income=p.get("income", ""),
                        side_business=p.get("side_business", ""),
                    )]
                # ハイライト・サマリー等の取得
                if kd.get("highlights"):
                    from src.video_direction.integrations.ai_dev5_connector import HighlightScene
                    video_data.highlights = []
                    for h in kd["highlights"]:
                        video_data.highlights.append(HighlightScene(
                            timestamp=h.get("timestamp", ""),
                            speaker=h.get("speaker", ""),
                            text=h.get("text", ""),
                            category=h.get("category", ""),
                        ))
                if kd.get("three_line_summary"):
                    video_data.three_line_summary = kd["three_line_summary"]
                if kd.get("main_topics"):
                    video_data.main_topics = kd["main_topics"]
                if kd.get("duration"):
                    video_data.duration = kd["duration"]
            except (json.JSONDecodeError, TypeError):
                pass

        if not video_data.profiles and guest_name:
            video_data.profiles = [PersonProfile(
                name=guest_name,
                age=str(project_data.get("guest_age", "")) if project_data.get("guest_age") else "",
                occupation=project_data.get("guest_occupation", ""),
                income="",
                side_business="",
            )]

        # 分類結果
        classification = ClassificationResult(
            tier="c", tier_label="層c",
            reason="再生成デフォルト", presentation_template="標準テンプレート",
            confidence="low",
        )

        # 年収評価
        income_eval = IncomeEvaluation(
            income_value=None, age_bracket="不明", threshold=0,
            emphasize=False, emphasis_reason="デフォルト", telop_suggestion="",
        )
        if video_data.profiles and video_data.profiles[0].income:
            income_eval = IncomeEvaluation(
                income_value=None, age_bracket="不明", threshold=0,
                emphasize=True, emphasis_reason="年収情報あり", telop_suggestion="",
            )

        # ナレッジロード
        knowledge_ctx = KnowledgeLoader().load()

        # EditLearner
        edit_learner = None
        try:
            from src.video_direction.tracker.edit_learner import EditLearner
            edit_learner = EditLearner()
        except Exception:
            pass

        # 固有名詞フィルタ
        _guest_name_for_filter = video_data.profiles[0].name if video_data.profiles else None
        proper_nouns = detect_proper_nouns(video_data, guest_name=_guest_name_for_filter)

        # 概要欄生成（LLM呼び出し）
        desc = generate_description(
            video_data, classification, income_eval, knowledge_ctx,
            edit_learner=edit_learner, proper_nouns=proper_nouns,
        )

        elapsed = time.time() - start

        if not desc.full_text or not desc.full_text.strip():
            return {
                "project_id": project_id,
                "guest_name": guest_name,
                "status": "empty_result",
                "elapsed": round(elapsed, 1),
                "desc_len": 0,
                "error": "生成結果が空（フォールバックも失敗）",
            }

        # DBに書き込み
        conn = sqlite3.connect(str(DB_PATH))
        # 既存レコードがあるか確認
        existing = conn.execute(
            "SELECT description_original FROM youtube_assets WHERE project_id = ?",
            (project_id,)
        ).fetchone()

        if existing is not None:
            # 既存レコードがある → UPDATE（空でない場合のみ）
            conn.execute(
                "UPDATE youtube_assets SET description_original = ?, updated_at = ? WHERE project_id = ?",
                (desc.full_text, time.strftime("%Y-%m-%dT%H:%M:%S"), project_id)
            )
        else:
            # 既存レコードがない → INSERT
            conn.execute(
                """INSERT INTO youtube_assets (project_id, description_original, updated_at)
                   VALUES (?, ?, ?)""",
                (project_id, desc.full_text, time.strftime("%Y-%m-%dT%H:%M:%S"))
            )
        conn.commit()
        conn.close()

        return {
            "project_id": project_id,
            "guest_name": guest_name,
            "status": "success",
            "elapsed": round(elapsed, 1),
            "desc_len": len(desc.full_text),
            "is_fallback": "[フォールバック" in (desc.llm_raw_response or ""),
        }

    except Exception as e:
        elapsed = time.time() - start
        return {
            "project_id": project_id,
            "guest_name": guest_name,
            "status": "error",
            "elapsed": round(elapsed, 1),
            "desc_len": 0,
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(description="概要欄のみ再生成（T-043）")
    parser.add_argument("--execute", action="store_true", help="実行する（デフォルトはdry-run）")
    parser.add_argument("--empty-only", action="store_true", help="概要欄が空のプロジェクトのみ対象")
    parser.add_argument("--project-id", type=str, help="特定のプロジェクトIDのみ")
    parser.add_argument("--yes", "-y", action="store_true", help="確認スキップ")
    args = parser.parse_args()

    projects = get_projects(empty_only=args.empty_only, project_id=args.project_id)

    print(f"\n=== 概要欄再生成（T-043） ===")
    print(f"対象: {len(projects)}件")
    print(f"モード: {'実行' if args.execute else 'dry-run'}")
    if args.empty_only:
        print(f"フィルタ: 空の概要欄のみ")
    print()

    for i, p in enumerate(projects, 1):
        desc_status = f"len={p['desc_len']}" if p['desc_len'] and p['desc_len'] > 0 else "空"
        cat = p.get("category", "未分類") or "未分類"
        print(f"  {i:2d}. {p['guest_name']:15s} [{cat}] ({desc_status}) — {p['id']}")

    if not args.execute:
        print(f"\n実行するには --execute を付けてください")
        return

    if not args.yes:
        confirm = input(f"\n{len(projects)}件の概要欄を再生成します。続行？ (y/N): ").strip().lower()
        if confirm != "y":
            print("中止しました。")
            return

    print(f"\n概要欄再生成開始...")
    total_start = time.time()
    results = []

    for i, p in enumerate(projects, 1):
        print(f"\n[{i}/{len(projects)}] {p['guest_name']} ({p['id']})")
        result = regenerate_description_for_project(p)
        results.append(result)

        icon = "OK" if result["status"] == "success" else "NG"
        fb = " (フォールバック)" if result.get("is_fallback") else ""
        print(f"  {icon}: {result['status']} | {result['desc_len']}文字 | {result['elapsed']}秒{fb}")
        if result.get("error"):
            print(f"  エラー: {result['error']}")

    total_elapsed = time.time() - total_start
    success = [r for r in results if r["status"] == "success"]
    errors = [r for r in results if r["status"] != "success"]

    print(f"\n{'=' * 50}")
    print(f"結果サマリー")
    print(f"  成功: {len(success)}/{len(results)}")
    print(f"  失敗: {len(errors)}/{len(results)}")
    print(f"  総時間: {total_elapsed:.1f}秒")

    if errors:
        print(f"\n失敗リスト:")
        for e in errors:
            print(f"  - {e['guest_name']}: {e.get('error', 'unknown')}")

    # ログ保存
    log_data = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total": len(results),
        "success": len(success),
        "errors": len(errors),
        "total_elapsed": round(total_elapsed, 1),
        "results": results,
    }
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)
    print(f"\nログ保存先: {LOG_PATH}")


if __name__ == "__main__":
    main()
