from __future__ import annotations
"""Z型サムネイル指示書生成

青木さんのZ理論に基づく4ゾーン構成のサムネイル設計指示を生成する。
LLM（Claude Sonnet）を使ってナレッジ + ゲスト情報から最適なサムネ設計を提案。
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
from ..knowledge.prompts import THUMBNAIL_DESIGN_PROMPT


@dataclass
class ThumbnailZone:
    """サムネイルの1ゾーン"""
    role: str = ""              # ゾーンの役割
    content: str = ""           # 具体的な内容
    color_suggestion: str = ""  # 色の提案
    notes: str = ""             # 配置・サイズの注意点


@dataclass
class ThumbnailDesign:
    """Z型サムネイル指示書"""
    overall_concept: str = ""
    font_suggestion: str = ""
    background_suggestion: str = ""
    top_left: ThumbnailZone = field(default_factory=ThumbnailZone)      # フック
    top_right: ThumbnailZone = field(default_factory=ThumbnailZone)     # 人物シルエット＋属性
    diagonal: ThumbnailZone = field(default_factory=ThumbnailZone)      # コンテンツ要素
    bottom_right: ThumbnailZone = field(default_factory=ThumbnailZone)  # ベネフィット
    llm_raw_response: str = ""  # デバッグ・監査用


def generate_thumbnail_design(
    video_data: VideoData,
    classification: ClassificationResult,
    income_eval: IncomeEvaluation,
    knowledge_ctx: KnowledgeContext,
) -> ThumbnailDesign:
    """Z型サムネイル指示書を生成する（teko_core.llm経由 — MAX定額内）"""

    # プロンプト構築
    profile = video_data.profiles[0] if video_data.profiles else None
    highlights_text = "\n".join([
        f"[{h.timestamp}] {h.speaker}: {h.text[:80]} ({h.category})"
        for h in video_data.highlights[:5]
    ])

    # ゲスト名クリーニング（括弧内ニックネーム優先）
    import re as _re
    raw_guest_name = profile.name if profile else "不明"
    paren_match = _re.search(r'[（(]([^）)]+)[）)]', raw_guest_name)
    if paren_match:
        inner = paren_match.group(1)
        inner = _re.sub(r'^(ニックネーム|NN|通称)[：:]?\s*', '', inner)
        clean_guest_name = inner
    else:
        clean_guest_name = raw_guest_name

    prompt = THUMBNAIL_DESIGN_PROMPT.format(
        z_theory_summary=knowledge_ctx.z_theory_summary,
        z_theory_detailed=knowledge_ctx.z_theory_detailed,
        marketing_principles=knowledge_ctx.marketing_principles,
        video_title=video_data.title or "不明",
        guest_name=clean_guest_name,
        guest_age=profile.age if profile else "不明",
        guest_occupation=profile.occupation if profile else "不明",
        guest_income=profile.income if profile else "不明",
        guest_tier=classification.tier,
        tier_label=classification.tier_label,
        income_emphasis="強調ON" if income_eval.emphasize else "強調OFF",
        three_line_summary="\n".join(video_data.three_line_summary) if video_data.three_line_summary else "なし",
        main_topics="\n".join(video_data.main_topics) if video_data.main_topics else "なし",
        highlights_text=highlights_text or "なし",
    )

    # LLM呼び出し（teko_core.llm経由 — MAX定額内）
    try:
        from teko_core.llm import ask
        raw = ask(prompt, model="sonnet", max_tokens=2000, timeout=120)

        # JSONパース
        return _parse_thumbnail_response(raw)

    except Exception as e:
        print(f"  ⚠️ サムネ指示書LLM生成失敗: {e}")
        return _fallback_thumbnail(video_data, classification, income_eval)


def _parse_thumbnail_response(raw: str) -> ThumbnailDesign:
    """LLMレスポンスからThumbnailDesignを構築"""
    # JSON部分を抽出
    json_match = re.search(r"\{[\s\S]*\}", raw)
    if not json_match:
        return ThumbnailDesign(llm_raw_response=raw)

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        return ThumbnailDesign(llm_raw_response=raw)

    zones = data.get("zones", {})

    def _parse_zone(zone_data: dict) -> ThumbnailZone:
        return ThumbnailZone(
            role=zone_data.get("role", ""),
            content=zone_data.get("content", ""),
            color_suggestion=zone_data.get("color_suggestion", ""),
            notes=zone_data.get("notes", ""),
        )

    return ThumbnailDesign(
        overall_concept=data.get("overall_concept", ""),
        font_suggestion=data.get("font_suggestion", ""),
        background_suggestion=data.get("background_suggestion", ""),
        top_left=_parse_zone(zones.get("top_left", {})),
        top_right=_parse_zone(zones.get("top_right", {})),
        diagonal=_parse_zone(zones.get("diagonal", {})),
        bottom_right=_parse_zone(zones.get("bottom_right", {})),
        llm_raw_response=raw,
    )


def _fallback_thumbnail(
    video_data: VideoData,
    classification: ClassificationResult,
    income_eval: IncomeEvaluation,
) -> ThumbnailDesign:
    """APIキーなし・LLM失敗時のフォールバック（ルールベース・層別フック戦略対応）"""
    profile = video_data.profiles[0] if video_data.profiles else None

    # 層別フック戦略に基づくフック文言の決定
    tier = classification.tier
    if tier == "a":
        # tier a（年収2000万〜）: 数字+権威性でフック
        hook_text = "年収" + (profile.income if profile and profile.income else "???万円")
        hook_notes = "0.2秒で目に入る最大フォント。数字+権威性で停止させる。企業ロゴ・役職アイコン等の非言語要素も活用"
    elif tier == "b":
        # tier b（年収1000-2000万）: ストーリー+共感でフック
        hook_text = "年収" + (profile.income if profile and profile.income else "???万円")
        hook_notes = "0.2秒で目に入る最大フォント。ストーリー性を感じさせる。転職・キャリアチェンジを示すアイコン等の非言語要素も活用"
    else:
        # tier c（年収〜1000万）: 行動のきっかけ+等身大感でフック
        if income_eval.emphasize and profile and profile.income:
            hook_text = "年収" + profile.income
        else:
            hook_text = profile.occupation if profile and profile.occupation else "会社員"
        hook_notes = "0.2秒で目に入る最大フォント。「自分でもできそう」感を演出。等身大を示すアイコン等の非言語要素も活用"

    return ThumbnailDesign(
        overall_concept=f"Z型レイアウト（0.2秒視認設計）— {classification.tier_label}のゲスト対談",
        font_suggestion="ゴシック体・太字（視認性重視）。文字は最小限に抑え、非言語要素で情報伝達",
        background_suggestion="ダークグレー or ネイビー系（高級感）",
        top_left=ThumbnailZone(
            role="フック（0.2秒で勝負を決める最重要ゾーン）",
            content=hook_text,
            color_suggestion="白テキスト on 赤/オレンジ背景",
            notes=hook_notes,
        ),
        top_right=ThumbnailZone(
            role="人物シルエット＋属性",
            content=f"モザイクシルエット + 「{profile.age if profile else ''}・{profile.occupation if profile else ''}」",
            color_suggestion="シルエットは白 or グレー、属性テキストは黄色",
            notes="顔はモザイク。シルエットの横に属性テキストを配置。業界ロゴ・企業アイコンで職業を非言語的に伝える",
        ),
        diagonal=ThumbnailZone(
            role="コンテンツ要素（非言語優先）",
            content="業界アイコン・ロゴ・映像カットで視線誘導",
            color_suggestion="アクセントカラー",
            notes="文字ではなくアイコン・ロゴで情報を伝える。左上→右下への視線誘導を意識した斜め配置",
        ),
        bottom_right=ThumbnailZone(
            role="ベネフィット",
            content="視聴者が得られる学び・気づきを1行で",
            color_suggestion="黄色 or ゴールド",
            notes="CTA的な要素、クリック動機に直結。テキストは最小限",
        ),
        llm_raw_response="[フォールバック: ルールベース生成（層別フック戦略・0.2秒視認設計対応）]",
    )


