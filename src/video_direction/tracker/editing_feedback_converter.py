"""編集FB変換: 抽象的な音声FBを品質基準に基づいて具体的な編集指示に変換する

タイミング1: FB変換の具体化
なおとさん/パグさんの抽象的な音声FB（例:「冒頭のハイライト、センスなさすぎ」）を、
QUALITY_JUDGMENT_GUIDE.mdの品質基準を参照して、編集者が即アクションできる具体的な指示に変換する。
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# DBパス（プロジェクト情報取得用）
_DB_PATH = Path.home() / "AI開発10" / ".data" / "video_director.db"


@dataclass
class ConvertedEditingFeedback:
    """変換済み編集FB"""
    original_feedback: str       # 元のFBテキスト
    category: str                # FBカテゴリ
    guest_name: str              # ゲスト名
    converted_instruction: str   # 変換後の具体的な編集指示
    quality_criteria_used: str   # 参照した品質基準のセクション名
    guest_context: str           # 参照したゲスト情報の要約
    suggestions: list[str] = field(default_factory=list)  # 代替案（複数提示）
    confidence: float = 0.0      # 変換の確度（0.0-1.0）


# カテゴリとQUALITY_JUDGMENT_GUIDE.mdのセクションの対応
CATEGORY_SECTION_MAP = {
    "highlight": {
        "section_name": "ハイライト選定の品質基準",
        "loader_func": "get_highlight_criteria",
        "description": "ハイライト選定（パンチライン・引きの強さ・冒頭構成）",
    },
    "direction": {
        "section_name": "演出ディレクションの品質基準",
        "loader_func": "get_direction_criteria",
        "description": "演出ディレクション（構成・テンポ・見せ方）",
    },
    "telop": {
        "section_name": "テロップ品質基準",
        "loader_func": "get_direction_criteria",  # テロップは演出の一部として扱う
        "description": "テロップ（フォント・サイズ・表示タイミング・内容）",
    },
    "general": {
        "section_name": "品質判断ガイド全般",
        "loader_func": "load_quality_guide",
        "description": "全般的な品質基準",
    },
}

# カテゴリ推定用キーワード
CATEGORY_KEYWORDS = {
    "highlight": [
        "ハイライト", "冒頭", "パンチライン", "引き", "サムネ",
        "タイトル", "掴み", "フック", "アイキャッチ", "オープニング",
        "最初", "頭", "先頭", "出だし", "センス",
    ],
    "direction": [
        "演出", "構成", "テンポ", "流れ", "展開",
        "カット", "繋ぎ", "場面転換", "リズム", "尺",
        "シーン", "間", "盛り上がり", "クライマックス",
        "bgm", "音楽", "se", "効果音",
    ],
    "telop": [
        "テロップ", "字幕", "フォント", "テキスト", "文字",
        "サイズ", "色", "見にくい", "読みにくい", "表示",
    ],
}


def classify_editing_feedback(feedback: str) -> str:
    """FBテキストからカテゴリを推定する

    Args:
        feedback: 生のFBテキスト

    Returns:
        "highlight" | "direction" | "telop" | "general"
    """
    feedback_lower = feedback.lower()
    scores: dict[str, int] = {}

    for cat, keywords in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in keywords if kw in feedback_lower)

    if max(scores.values(), default=0) > 0:
        return max(scores, key=scores.get)
    return "general"


def _get_quality_criteria(category: str) -> tuple[str, str]:
    """カテゴリに応じた品質基準テキストを取得する

    Args:
        category: FBカテゴリ

    Returns:
        (品質基準テキスト, セクション名)
    """
    from ..knowledge.quality_knowledge_loader import (
        get_highlight_criteria,
        get_direction_criteria,
        load_quality_guide,
    )

    section_info = CATEGORY_SECTION_MAP.get(category, CATEGORY_SECTION_MAP["general"])
    section_name = section_info["section_name"]
    loader_name = section_info["loader_func"]

    # 対応する関数を呼び出す
    loaders = {
        "get_highlight_criteria": get_highlight_criteria,
        "get_direction_criteria": get_direction_criteria,
        "load_quality_guide": load_quality_guide,
    }

    loader = loaders.get(loader_name, load_quality_guide)
    criteria_text = loader()

    # Opusのコンテキスト長は1Mトークンのため切り詰め不要
    # セクション5（ハイライト選定品質基準）は10,698文字あり、
    # NGパターン・完成品ハイライト構成・パンチライン一覧を全て注入する

    return criteria_text, section_name


def _get_guest_context(guest_name: str) -> str:
    """ゲストのプロファイル情報を取得する

    MEMBER_MASTER.jsonとpeopleファイルから、ゲストの年収・企業・実績等を取得。

    Args:
        guest_name: ゲスト名（正式名またはエイリアス）

    Returns:
        ゲスト情報のテキスト要約。見つからない場合は空文字
    """
    try:
        from ..integrations.member_master import MemberMaster

        master = MemberMaster()
        member = master.find_member(guest_name)
        if not member:
            return ""

        # プロファイルファイルから詳細情報を取得
        # Opusのコンテキスト長は1Mトークンのため切り詰め不要
        profile_text = master.get_people_profile(member)
        if profile_text:
            return f"【ゲスト: {member.canonical_name}】\n{profile_text}"

        # プロファイルファイルがない場合はMEMBER_MASTER.jsonの情報だけ返す
        return f"【ゲスト: {member.canonical_name}】（詳細プロファイルなし）"

    except Exception:
        return ""


def _get_content_line_context(project_id: str | None) -> str:
    """project_idからDBのcategoryを取得し、コンテンツライン情報テキストを返す

    不動産軸（teko_realestate）の場合は層分類よりも不動産実績がパンチラインになる旨を注入。
    キャリア軸（teko_member）の場合はマニュアルの層分類・社格・年収の見せ方を厳密に適用する旨を注入。

    Args:
        project_id: 動画プロジェクトID（Noneの場合は空文字を返す）

    Returns:
        コンテンツライン情報テキスト。取得できない場合は空文字
    """
    if not project_id:
        return ""

    try:
        from ..knowledge.quality_knowledge_loader import (
            get_content_line_criteria,
        )

        # DBからcategoryを取得
        if not _DB_PATH.exists():
            return ""
        conn = sqlite3.connect(str(_DB_PATH), timeout=5)
        try:
            row = conn.execute(
                "SELECT category, title FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        finally:
            conn.close()

        if not row:
            return ""

        category = row[0] or "teko_member"
        title = row[1] or ""

        # コンテンツライン判定
        if category == "teko_realestate":
            content_line = "realestate"
        else:
            content_line = "career"

        # コンテンツライン基準テキストの取得
        cl_criteria = get_content_line_criteria()

        parts = []
        parts.append("## コンテンツライン判定")
        if content_line == "realestate":
            parts.append(f"この動画のコンテンツライン: **不動産実績対談（ノウハウ軸）**")
            parts.append("→ 層分類より不動産の実績・内容がパンチライン。マニュアルの層分類を厳密に適用するよりも不動産実績とパンチラインにフォーカスすること。")
        else:
            parts.append(f"この動画のコンテンツライン: **通常のTEKO実績対談（キャリア軸）**")
            parts.append("→ マニュアルの層分類・社格・年収の見せ方を厳密に適用すること。")

        if cl_criteria:
            parts.append("")
            parts.append(cl_criteria)

        return "\n".join(parts)

    except Exception:
        return ""


def _build_conversion_prompt(
    raw_feedback: str,
    category: str,
    quality_criteria: str,
    guest_context: str,
    content_line_context: str = "",
) -> tuple[str, str]:
    """LLM用のプロンプトを構築する

    Returns:
        (system_prompt, user_prompt)
    """
    system_prompt = (
        "あなたは映像編集のディレクターです。"
        "プロデューサーから以下のフィードバックを受けました。"
        "これを編集者が即座にアクションに移せる具体的な指示に変換してください。"
        "TEKOの対談動画（不動産投資家の実績紹介コンテンツ）の文脈を理解しています。"
    )

    # コンテンツライン情報があればプロンプトに注入
    content_line_section = ""
    if content_line_context:
        content_line_section = f"\n\n{content_line_context}"

    user_prompt = f"""以下の音声フィードバックを、編集者が即座にアクションに移せる具体的な指示に変換してください。

## プロデューサーのFB
{raw_feedback}

## 対象ゲスト情報
{guest_context if guest_context else "（ゲスト情報なし）"}

## 品質基準（この基準に基づいて具体化すること）
{quality_criteria if quality_criteria else "（品質基準未設定）"}{content_line_section}

## 出力形式（JSON）
必ず以下のJSON形式で出力してください。他のテキストは含めないでください。
{{
    "converted_instruction": "具体的な編集指示テキスト（編集者がこれだけ読んで作業できるレベル）",
    "reason": "なぜこの修正が必要か（品質基準のどこに抵触しているか）",
    "suggestions": ["代替案1", "代替案2", "代替案3"],
    "confidence": 0.8
}}"""

    return system_prompt, user_prompt


def convert_editing_feedback(
    raw_feedback: str,
    guest_name: str,
    feedback_category: str | None = None,
    project_id: str | None = None,
) -> ConvertedEditingFeedback:
    """抽象的な音声FBを品質基準に基づいて具体的な編集指示に変換する

    1. feedback_categoryに応じてQUALITY_JUDGMENT_GUIDE.mdの該当セクションを取得
    2. ゲストのプロファイル情報をMEMBER_MASTER.jsonやナレッジファイルから取得
    3. LLMに「抽象FB + 品質基準 + ゲスト情報」を渡して、具体的な編集指示に変換
    4. 変換結果を返す

    Args:
        raw_feedback: なおとさんの抽象的なFB（音声→STT後のテキスト）
        guest_name: 対象ゲスト名
        feedback_category: "highlight" | "direction" | "telop" | "general" (Noneなら自動推定)
        project_id: 動画プロジェクトID（オプション）

    Returns:
        ConvertedEditingFeedback: 変換結果
    """
    # カテゴリ自動推定
    if not feedback_category:
        feedback_category = classify_editing_feedback(raw_feedback)

    # 品質基準の取得
    quality_criteria, section_name = _get_quality_criteria(feedback_category)

    # ゲスト情報の取得
    guest_context = _get_guest_context(guest_name)

    # コンテンツライン情報の取得（project_idからDBのcategoryを参照）
    content_line_context = _get_content_line_context(project_id)

    # LLMプロンプトの構築
    system_prompt, user_prompt = _build_conversion_prompt(
        raw_feedback, feedback_category, quality_criteria, guest_context,
        content_line_context=content_line_context,
    )

    # LLM呼び出し
    converted_instruction = ""
    suggestions: list[str] = []
    confidence = 0.0

    try:
        from teko_core.llm import ask

        response_text = ask(
            user_prompt,
            system=system_prompt,
            model="opus",
            max_tokens=1024,
            timeout=120,
        )

        # JSONパース
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            result = json.loads(json_match.group())
            converted_instruction = result.get("converted_instruction", "")
            suggestions = result.get("suggestions", [])
            confidence = float(result.get("confidence", 0.7))
            # reasonがあればinstructionに付加
            reason = result.get("reason", "")
            if reason and converted_instruction:
                converted_instruction += f"\n\n【修正理由】{reason}"
        else:
            # JSONパース失敗時はレスポンス全文を指示として使用
            converted_instruction = response_text
            confidence = 0.5

    except Exception as e:
        # LLM呼び出し失敗時のフォールバック
        converted_instruction = _fallback_conversion(raw_feedback, feedback_category)
        confidence = 0.3

    return ConvertedEditingFeedback(
        original_feedback=raw_feedback,
        category=feedback_category,
        guest_name=guest_name,
        converted_instruction=converted_instruction,
        quality_criteria_used=section_name,
        guest_context=guest_context[:200] if guest_context else "",
        suggestions=suggestions,
        confidence=confidence,
    )


def _fallback_conversion(raw_feedback: str, category: str) -> str:
    """LLM呼び出し失敗時のフォールバック変換

    カテゴリに応じた定型文+元のFBを結合して返す。
    """
    category_templates = {
        "highlight": (
            "【ハイライト修正指示】\n"
            "冒頭のハイライトシーンを見直してください。\n"
            f"プロデューサーからのFB: {raw_feedback}\n\n"
            "確認ポイント:\n"
            "- パンチラインの引きは十分か（共感・好奇心・パンチ力・逆説の4引き金）\n"
            "- 引きの強い事実の畳みかけができているか\n"
            "- NGパターン（前置き長い・抽象的すぎ・結論先出し・無関係シーン）に該当していないか"
        ),
        "direction": (
            "【演出修正指示】\n"
            f"プロデューサーからのFB: {raw_feedback}\n\n"
            "確認ポイント:\n"
            "- テンポ・リズムは適切か\n"
            "- 場面転換がスムーズか\n"
            "- 盛り上がりのメリハリがあるか"
        ),
        "telop": (
            "【テロップ修正指示】\n"
            f"プロデューサーからのFB: {raw_feedback}\n\n"
            "確認ポイント:\n"
            "- フォントサイズ・色は見やすいか\n"
            "- 表示タイミングは適切か\n"
            "- テロップ内容は発言の要点を正確に表しているか"
        ),
        "general": (
            "【品質修正指示】\n"
            f"プロデューサーからのFB: {raw_feedback}\n\n"
            "品質基準に照らして該当箇所を見直してください。"
        ),
    }

    return category_templates.get(category, category_templates["general"])
