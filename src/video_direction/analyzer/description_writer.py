from __future__ import annotations
"""概要欄文章生成モジュール

そのままYouTubeに貼れる概要欄テキストを生成する。
構成: 冒頭フック → トークサマリー → タイムスタンプ → CTA → ハッシュタグ
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from ..integrations.ai_dev5_connector import VideoData
from ..analyzer.guest_classifier import ClassificationResult
from ..analyzer.income_evaluator import IncomeEvaluation
from ..knowledge.loader import KnowledgeContext
from ..knowledge.prompts import DESCRIPTION_GENERATION_PROMPT


@dataclass
class VideoDescription:
    """YouTube概要欄テキスト"""
    full_text: str = ""          # そのまま貼れる完成版
    hook: str = ""               # 冒頭フック
    summary: str = ""            # トークサマリー
    timestamps: str = ""         # タイムスタンプ
    cta: str = ""                # CTA
    hashtags: str = ""           # ハッシュタグ
    llm_raw_response: str = ""   # デバッグ・監査用


def generate_description(
    video_data: VideoData,
    classification: ClassificationResult,
    income_eval: IncomeEvaluation,
    knowledge_ctx: KnowledgeContext,
) -> VideoDescription:
    """YouTube概要欄テキストを生成する"""

    api_key = _get_api_key()
    if not api_key:
        return _fallback_description(video_data, classification, income_eval)

    profile = video_data.profiles[0] if video_data.profiles else None

    # 過去概要欄テキスト（few-shot examples）
    past_descriptions_text = ""
    if knowledge_ctx.past_descriptions:
        for i, desc in enumerate(knowledge_ctx.past_descriptions[:3], 1):
            # 先頭300文字に制限（プロンプトサイズ管理）
            truncated = desc[:300] + ("..." if len(desc) > 300 else "")
            past_descriptions_text += f"\n--- 過去例{i} ---\n{truncated}\n"
    else:
        past_descriptions_text = "（過去概要欄データなし — 初回生成のため独自に構成）"

    # タイムスタンプ付きハイライト
    highlights_with_timestamps = "\n".join([
        f"{h.timestamp} - {h.category}: {h.text[:60]}"
        for h in video_data.highlights[:10]
    ]) or "なし"

    prompt = DESCRIPTION_GENERATION_PROMPT.format(
        marketing_principles=knowledge_ctx.marketing_principles,
        past_descriptions_text=past_descriptions_text,
        video_title=video_data.title or "不明",
        guest_age=profile.age if profile else "不明",
        guest_occupation=profile.occupation if profile else "不明",
        guest_income=profile.income if profile else "不明",
        three_line_summary="\n".join(video_data.three_line_summary) if video_data.three_line_summary else "なし",
        main_topics="\n".join(video_data.main_topics) if video_data.main_topics else "なし",
        duration=video_data.duration or "不明",
        highlights_with_timestamps=highlights_with_timestamps,
    )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        return _parse_description_response(raw)

    except Exception as e:
        print(f"  ⚠️ 概要欄文章LLM生成失敗: {e}")
        return _fallback_description(video_data, classification, income_eval)


def _parse_description_response(raw: str) -> VideoDescription:
    """LLMレスポンスからVideoDescriptionを構築"""
    json_match = re.search(r"\{[\s\S]*\}", raw)
    if not json_match:
        return VideoDescription(llm_raw_response=raw)

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        return VideoDescription(llm_raw_response=raw)

    sections = data.get("sections", {})
    return VideoDescription(
        full_text=data.get("full_text", ""),
        hook=sections.get("hook", ""),
        summary=sections.get("summary", ""),
        timestamps=sections.get("timestamps", ""),
        cta=sections.get("cta", ""),
        hashtags=sections.get("hashtags", ""),
        llm_raw_response=raw,
    )


def _fallback_description(
    video_data: VideoData,
    classification: ClassificationResult,
    income_eval: IncomeEvaluation,
) -> VideoDescription:
    """フォールバック（テンプレートベース）"""
    profile = video_data.profiles[0] if video_data.profiles else None

    # ゲスト属性テキスト（名前は出さない）
    attr_parts = []
    if profile:
        if profile.age:
            attr_parts.append(profile.age)
        if profile.occupation:
            attr_parts.append(profile.occupation)
        if profile.income and income_eval.emphasize:
            attr_parts.append(f"年収{profile.income}")
    guest_attr = "・".join(attr_parts) if attr_parts else "会社員ゲスト"

    # 冒頭フック
    hook = f"{guest_attr}が語る、不動産投資のリアルな体験談。"

    # トークサマリー
    topics = video_data.main_topics[:5] if video_data.main_topics else ["不動産投資について"]
    summary_lines = "\n".join([f"・{t}" for t in topics])
    summary = f"▼ 今回のトーク内容\n{summary_lines}"

    # タイムスタンプ
    ts_lines = []
    for h in video_data.highlights[:8]:
        ts_lines.append(f"{h.timestamp} {h.category}: {h.text[:40]}")
    timestamps = "\n".join(ts_lines) if ts_lines else "0:00 オープニング"

    # CTA
    cta = """▼ TEKO（テコ）について詳しくはこちら
https://teko-lp.com/

▼ LINE公式アカウント
[LINE公式リンク]

▼ チャンネル登録お願いします！
[チャンネル登録リンク]

▼ SNS
Instagram: [Instagramリンク]
X (Twitter): [Xリンク]
TikTok: [TikTokリンク]"""

    # ハッシュタグ
    hashtags = "#不動産投資 #TEKO #テコ #資産形成 #サラリーマン投資 #対談"

    # full_text組み立て
    full_text = f"""{hook}

{summary}

▼ タイムスタンプ
{timestamps}

{cta}

{hashtags}"""

    return VideoDescription(
        full_text=full_text,
        hook=hook,
        summary=summary,
        timestamps=timestamps,
        cta=cta,
        hashtags=hashtags,
        llm_raw_response="[フォールバック: テンプレート生成]",
    )


def _get_api_key() -> str:
    """Anthropic APIキーを取得"""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        env_file = Path.home() / ".config" / "maekawa" / "api-keys.env"
        if env_file.exists():
            for line in env_file.read_text().split("\n"):
                if line.startswith("ANTHROPIC_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    return api_key
