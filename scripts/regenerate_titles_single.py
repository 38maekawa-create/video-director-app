#!/usr/bin/env python3
"""ひろきょうさん1件だけ再生成"""

import sys
import json
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from video_direction.integrations.ai_dev5_connector import parse_markdown_file
from video_direction.analyzer.guest_classifier import classify_guest
from video_direction.analyzer.income_evaluator import evaluate_income
from video_direction.analyzer.title_generator import generate_title_proposals, _parse_title_response
from video_direction.knowledge.loader import KnowledgeLoader

DB_PATH = Path.home() / "AI開発10" / ".data" / "video_director.db"
MD_PATH = Path.home() / "TEKO" / "knowledge" / "01_teko" / "sources" / "video" / "2026.02.15_20260125撮影_ひろきょうさん.md"
PROJECT_ID = "p-20260125-ひ樹京ひろきょう"

print("📚 ナレッジ読み込み中...")
loader = KnowledgeLoader()
knowledge_ctx = loader.load()

print("📝 mdパース中...")
video_data = parse_markdown_file(str(MD_PATH))
classification = classify_guest(video_data)
income_eval = evaluate_income(video_data)

print(f"   ゲスト名: {video_data.profiles[0].name if video_data.profiles else '不明'}")

# LLM直接呼び出し（デバッグ用にraw responseを表示）
from video_direction.knowledge.prompts import TITLE_GENERATION_PROMPT
import re

profile = video_data.profiles[0]
raw_guest_name = profile.name
paren_match = re.search(r'[（(]([^）)]+)[）)]', raw_guest_name)
if paren_match:
    inner = paren_match.group(1)
    inner = re.sub(r'^(ニックネーム|NN|通称)[：:]?\s*', '', inner)
    clean_guest_name = inner
else:
    clean_guest_name = raw_guest_name

key_highlights = [h for h in video_data.highlights if h.category in ("パンチライン", "実績数字", "属性紹介")]
highlights_text = "\n".join([
    f"[{h.timestamp}] {h.speaker}: {h.text[:80]} ({h.category})"
    for h in key_highlights[:8]
]) or "なし"

past_titles_text = "\n".join([f"- {t}" for t in knowledge_ctx.past_title_patterns[:30]])

prompt = TITLE_GENERATION_PROMPT.format(
    marketing_principles=knowledge_ctx.marketing_principles,
    z_theory_summary=knowledge_ctx.z_theory_summary,
    past_titles_text=past_titles_text,
    video_title=video_data.title or "不明",
    guest_name=clean_guest_name,
    guest_age=profile.age,
    guest_occupation=profile.occupation,
    guest_income=profile.income,
    guest_tier=classification.tier,
    tier_label=classification.tier_label,
    income_emphasis="強調ON" if income_eval.emphasize else "強調OFF",
    three_line_summary="\n".join(video_data.three_line_summary),
    main_topics="\n".join(video_data.main_topics),
    side_business=profile.side_business or "なし",
    highlights_text=highlights_text,
)

print("🤖 LLM呼び出し中...")
from teko_core.llm import ask
raw = ask(prompt, model="sonnet", max_tokens=2000, timeout=120)
print(f"🤖 LLM応答: {len(raw)}文字")
print("--- raw response start ---")
print(raw[:500])
print("--- raw response end (first 500 chars) ---")

# パース
result = _parse_title_response(raw)
print(f"\nパース結果: {len(result.candidates)}件")

if result.candidates:
    for i, c in enumerate(result.candidates):
        marker = "★" if i == result.recommended_index else " "
        print(f"  {marker}[{i}] {c.title}")

    # DB保存
    proposals_json = json.dumps({
        "candidates": [
            {"title": c.title, "target_segment": c.target_segment, "appeal_type": c.appeal_type, "rationale": c.rationale}
            for c in result.candidates
        ],
        "recommended_index": result.recommended_index,
        "llm_raw_response": result.llm_raw_response,
    }, ensure_ascii=False)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("UPDATE youtube_assets SET title_proposals = ?, updated_at = datetime('now') WHERE project_id = ?",
                   (proposals_json, PROJECT_ID))
    conn.commit()
    conn.close()
    print(f"\n✅ DB更新完了: {PROJECT_ID}")
else:
    print("\n❌ パース失敗。JSONの手動パースを試みます...")
    # コードブロック除去して再パース
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    result2 = _parse_title_response(cleaned)
    print(f"  再パース結果: {len(result2.candidates)}件")

    if result2.candidates:
        for i, c in enumerate(result2.candidates):
            marker = "★" if i == result2.recommended_index else " "
            print(f"  {marker}[{i}] {c.title}")

        proposals_json = json.dumps({
            "candidates": [
                {"title": c.title, "target_segment": c.target_segment, "appeal_type": c.appeal_type, "rationale": c.rationale}
                for c in result2.candidates
            ],
            "recommended_index": result2.recommended_index,
            "llm_raw_response": result2.llm_raw_response,
        }, ensure_ascii=False)

        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("UPDATE youtube_assets SET title_proposals = ?, updated_at = datetime('now') WHERE project_id = ?",
                       (proposals_json, PROJECT_ID))
        conn.commit()
        conn.close()
        print(f"\n✅ DB更新完了: {PROJECT_ID}")
    else:
        print("  再パースも失敗。手動確認が必要です。")
