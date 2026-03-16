from __future__ import annotations
"""概要欄文章生成モジュール

そのままYouTubeに貼れる概要欄テキストを生成する。
構成: チャンネル登録CTA → ブランド紹介 → ゲスト紹介フック → トークサマリー → LINE CTA
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
    """YouTube概要欄テキストを生成する（teko_core.llm経由 — MAX定額内）"""

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
        from teko_core.llm import ask
        raw = ask(prompt, model="sonnet", max_tokens=3000, timeout=120)
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
    """フォールバック（テンプレートベース — TEKO実投稿済みフォーマット完全準拠）"""
    profile = video_data.profiles[0] if video_data.profiles else None

    # ゲスト名（「さん」の二重付与を防止）
    raw_name = profile.name if profile and profile.name else "ゲスト"
    guest_name = raw_name.rstrip("さん") + "さん"

    # ハッシュタグ生成（動画内容に合わせて）
    hashtag_parts = []
    if profile and profile.occupation:
        # 職業からハッシュタグ候補を生成（長い場合は最初の区切りまで）
        occ = re.split(r'[。（]', profile.occupation)[0][:20]
        hashtag_parts.append(f"#{occ.replace(' ', '')}")
    if profile and profile.income:
        hashtag_parts.append(f"#年収{profile.income}")
    hashtag_parts.extend(["#プロパー八重洲", "#年収1000万", "#年収", "#副業", "#ハイキャリ", "#TEKO", "#転職"])

    hashtags_text = "　".join(hashtag_parts[:10])

    # タイムスタンプ（ハイライト情報がある場合）
    timestamps_text = ""
    if video_data.highlights:
        for h in video_data.highlights[:8]:
            ts = h.timestamp if h.timestamp else "0:00"
            timestamps_text += f"{ts} {h.text[:40]}\n"

    # 概要欄全文（実際のTEKO投稿済み動画と完全同一のテンプレート）
    full_text = f"""チャンネル登録はこちらから▼
    @TEKO-公式

【TEKO公式メディア】
ハイキャリアパーソンの裏側とキャリア、資産形成について発信
https://levaraging.daive-teko.com/

【運営者：プロパー八重洲とLINEで繋がりませんか？】
▼パラレルキャリア戦略やTEKOについてはLINEから▼
https://leverage.daive-teko.com/p/lp_youtube_tekoofficial?openExternalBrowser=1

【プロパー八重洲公式チャンネルはこちらから】
     @プロパー八重洲キャリア戦略室

ハイキャリアのキャリアの裏側と挑戦に迫ったキャリア密着ドキュメンタリー番組・"ハイキャリアの裏側"はこちら▼
   @ハイキャリアの裏側-TEKO

▼タイムスタンプ▼
{timestamps_text}

━━━━━━━━━━━
{hashtags_text}
━━━━━━━━━━━


【運営者情報】　プロパー八重洲 / 藤田光貴

1993年、愛媛県生まれ。
TEKO合同会社 代表社員 / Yohack合同会社 代表社員。

小野薬品工業（株） → (株) ストライク → アレクシオンファーマ（同）を経て独立。

アレクシオンファーマ在籍時、30歳時点で年収約1,100万円と500万円相当のRSUを受け取る。

サラリーマン時代に副業・不動産投資を並行して実践し、アレクシオンファーマ（同）在籍時に純資産1億円超えに至る。

Xフォロワー2.2万人。Instagramフォロワー1万人。（2025.9時点）

医師、GAFAM、5大総合商社、外資系戦略コンサルなどハイクラスのビジネスパーソンも数多く在籍する会員制ビジネスパーソン向けプラットフォーム"TEKO"を運営。

2025年9月時点で、300名ほどのビジネスパーソンがTEKOに在籍中。

海外輸出物販事業を運営する法人と不動産賃貸業及びハイキャリア中心にビジネスパーソンのキャリア支援・経済支援を行うTEKO事業を運営する法人の2法人を所有。

海外輸出物販法人の前期決算では年商1.3億円。

2016年 小野薬品工業株式会社  入社
2021年 株式会社ストライク 入社
2022年 アレクシオンファーマ合同会社  入社
2024年 TEKO設立


▪️他SNSでもキャリアや資産形成に関する戦略・戦術を発信中
X（旧Twitter）
https://x.com/yaesu_pro

Instagram
https://www.instagram.com/yaesu.pro/"""

    return VideoDescription(
        full_text=full_text,
        hook=f"{guest_name}のキャリアと資産形成のリアルに迫る",
        summary="",
        timestamps=timestamps_text,
        cta="",
        hashtags=hashtags_text,
        llm_raw_response="[フォールバック: TEKO実投稿済みテンプレート準拠]",
    )


