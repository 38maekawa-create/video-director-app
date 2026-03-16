from __future__ import annotations
"""タイトル考案モジュール

過去タイトルパターン + マーケティング原則をもとに、
TEKO対談動画のYouTubeタイトル案を3-5個提案する。
"""

import json
import re
from dataclasses import dataclass, field
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
    """タイトル案を生成する（teko_core.llm経由 — MAX定額内）"""

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
        from teko_core.llm import ask
        raw = ask(prompt, model="sonnet", max_tokens=2000, timeout=120)
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
    raw_age = profile.age if profile else "30代"
    # 数字のみの場合は「歳」を付与、「代」「歳」が付いていればそのまま
    age = raw_age
    if raw_age and raw_age.isdigit():
        age = f"{raw_age}歳"
    elif raw_age and not any(s in raw_age for s in ("代", "歳")):
        age = f"{raw_age}歳"
    raw_occupation = profile.occupation if profile else "会社員"
    # 職業テキストが長すぎる場合は最初の句点・括弧閉じまでで切り詰め
    occupation = re.split(r'[。（]', raw_occupation)[0][:30] if raw_occupation else "会社員"
    income = profile.income if profile else ""

    # 年収テキスト
    income_text = f"年収{income}" if income else ""

    # パンチライン抽出（ハイライトから最もインパクトのあるフレーズを選ぶ）
    punchline = ""
    for h in video_data.highlights:
        if h.category in ("パンチライン", "実績数字"):
            # 文の区切りの良いところで切る（句読点・助詞の後）
            text = h.text
            if len(text) > 50:
                # 最初の句読点・「」・助詞で切る
                for sep_pos in range(35, min(60, len(text))):
                    if text[sep_pos] in "。、」！？":
                        text = text[:sep_pos + 1]
                        break
                else:
                    text = text[:40]
            punchline = text
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


