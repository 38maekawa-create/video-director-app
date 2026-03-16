from __future__ import annotations
"""タイトル考案モジュール

過去タイトルパターン + マーケティング原則をもとに、
TEKO対談動画のYouTubeタイトル案を3-5個提案する。
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
from ..knowledge.prompts import TITLE_GENERATION_PROMPT


@dataclass
class TitleCandidate:
    """タイトル案の1候補"""
    title: str = ""
    target_segment: str = ""   # このタイトルが刺さるターゲット層
    appeal_type: str = ""      # 訴求タイプ（数字系/ストーリー系/問いかけ系/権威系）
    rationale: str = ""        # 選定理由


@dataclass
class TitleProposals:
    """タイトル提案の全体"""
    candidates: list[TitleCandidate] = field(default_factory=list)
    recommended_index: int = 0  # 推奨案のインデックス
    llm_raw_response: str = ""  # デバッグ・監査用


def generate_title_proposals(
    video_data: VideoData,
    classification: ClassificationResult,
    income_eval: IncomeEvaluation,
    knowledge_ctx: KnowledgeContext,
) -> TitleProposals:
    """タイトル案を生成する"""

    api_key = _get_api_key()
    if not api_key:
        return _fallback_titles(video_data, classification, income_eval)

    profile = video_data.profiles[0] if video_data.profiles else None

    # 過去タイトル一覧（最新30件に制限）
    past_titles_text = "\n".join([
        f"- {t}" for t in knowledge_ctx.past_title_patterns[:30]
    ]) if knowledge_ctx.past_title_patterns else "（過去タイトルデータなし）"

    # パンチライン・実績数字のハイライトを抽出
    key_highlights = [
        h for h in video_data.highlights
        if h.category in ("パンチライン", "実績数字", "属性紹介")
    ]
    highlights_text = "\n".join([
        f"[{h.timestamp}] {h.speaker}: {h.text[:80]} ({h.category})"
        for h in key_highlights[:8]
    ]) or "なし"

    prompt = TITLE_GENERATION_PROMPT.format(
        marketing_principles=knowledge_ctx.marketing_principles,
        z_theory_summary=knowledge_ctx.z_theory_summary,
        past_titles_text=past_titles_text,
        video_title=video_data.title or "不明",
        guest_name=profile.name if profile else "不明",
        guest_age=profile.age if profile else "不明",
        guest_occupation=profile.occupation if profile else "不明",
        guest_income=profile.income if profile else "不明",
        guest_tier=classification.tier,
        tier_label=classification.tier_label,
        income_emphasis="強調ON" if income_eval.emphasize else "強調OFF",
        three_line_summary="\n".join(video_data.three_line_summary) if video_data.three_line_summary else "なし",
        main_topics="\n".join(video_data.main_topics) if video_data.main_topics else "なし",
        side_business=profile.side_business if profile and profile.side_business else "なし",
        highlights_text=highlights_text,
    )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        return _parse_title_response(raw)

    except Exception as e:
        print(f"  ⚠️ タイトル考案LLM生成失敗: {e}")
        return _fallback_titles(video_data, classification, income_eval)


def _parse_title_response(raw: str) -> TitleProposals:
    """LLMレスポンスからTitleProposalsを構築"""
    json_match = re.search(r"\{[\s\S]*\}", raw)
    if not json_match:
        return TitleProposals(llm_raw_response=raw)

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        return TitleProposals(llm_raw_response=raw)

    candidates = []
    for item in data.get("candidates", []):
        candidates.append(TitleCandidate(
            title=item.get("title", ""),
            target_segment=item.get("target_segment", ""),
            appeal_type=item.get("appeal_type", ""),
            rationale=item.get("rationale", ""),
        ))

    return TitleProposals(
        candidates=candidates,
        recommended_index=data.get("recommended_index", 0),
        llm_raw_response=raw,
    )


def _fallback_titles(
    video_data: VideoData,
    classification: ClassificationResult,
    income_eval: IncomeEvaluation,
) -> TitleProposals:
    """フォールバック（ルールベース — TEKO実投稿済みフォーマット準拠）

    パターンA（パンチライン先頭型・最近の主流）:
    「[パンチライン]」[年代]年収[金額][職業]の[名前]さんが語る[テーマ]とは？【TEKO独占インタビュー】
    """
    profile = video_data.profiles[0] if video_data.profiles else None

    # ゲスト属性から基本要素を抽出（「さん」二重付与防止）
    raw_name = profile.name if profile else "ゲスト"
    name = raw_name.rstrip("さん")
    age = profile.age if profile else "30代"
    occupation = profile.occupation if profile else "会社員"
    income = profile.income if profile else ""

    # 年収テキスト
    income_text = f"年収{income}" if income else ""

    # パンチライン抽出（ハイライトから最もインパクトのあるフレーズを選ぶ）
    punchline = ""
    for h in video_data.highlights:
        if h.category in ("パンチライン", "実績数字"):
            # 発言者がゲスト本人のものを優先
            punchline = h.text[:40]
            break
    if not punchline:
        # デフォルトのパンチラインは使わない。具体的な動画内容がないと意味がない
        punchline = ""

    # テーマのバリエーション
    themes = [
        "キャリア戦略",
        "『本業×複業』で得た真の安定",
        "キャリアプラン",
    ]

    candidates = []
    for i, theme in enumerate(themes):
        if punchline:
            # パターンA: パンチライン先頭型（最近のTEKOで主流）
            title = f"「{punchline}」{age}{income_text}{occupation}の{name}さんが語る{theme}とは？【TEKO独占インタビュー】"
        else:
            # パンチラインがない場合はパターンB: 年収先頭型
            title = f"{income_text}{age}{occupation}{name}さんが語る{theme}とは【TEKO独占インタビュー】"

        candidates.append(TitleCandidate(
            title=title,
            target_segment="同世代・同属性のハイキャリア層",
            appeal_type=["数字系", "ストーリー系", "問いかけ系"][i],
            rationale=f"TEKO実投稿済みフォーマット準拠: テーマ={theme}",
        ))

    return TitleProposals(
        candidates=candidates,
        recommended_index=0,
        llm_raw_response="[フォールバック: TEKO実投稿済みフォーマット準拠]",
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
