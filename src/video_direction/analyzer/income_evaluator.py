from __future__ import annotations
"""A-2: 年収演出判断 + A-3: 年収以外の強さ発掘

年齢別早見表:
- 20代前半〜中盤: 500万
- 20代後半: 600万
- 30代前半: 700万

演出判断:
- 700万以上 → 無条件で強調ON
- 早見表基準+100万以上 → 強調ON（文脈付きテロップ推奨）
- 早見表基準以下 → 強調OFF → 代替の強みを検出
"""

import re
from dataclasses import dataclass, field
from ..integrations.ai_dev5_connector import VideoData, PersonProfile


# 年齢別年収早見表（TEKO独自基準）
INCOME_THRESHOLD = {
    "20代前半": 500,
    "20代中盤": 500,
    "20代後半": 600,
    "30代前半": 700,
    "30代中盤": 700,
    "30代後半": 700,
    "40代": 700,
}


@dataclass
class IncomeEvaluation:
    """年収演出判断結果"""
    income_value: int | None  # 万円単位
    age_bracket: str  # 年齢帯
    threshold: int  # 早見表基準値
    emphasize: bool  # 強調するか
    emphasis_reason: str  # 強調理由
    telop_suggestion: str  # テロップ提案
    alternative_strengths: list = field(default_factory=list)  # A-3: 代替の強み


@dataclass
class AlternativeStrength:
    """代替の強み"""
    category: str  # 企業ブランド / キャリアパス / 勤務形態 / 転職見込み
    description: str
    source_text: str  # 根拠テキスト


def evaluate_income(video_data: VideoData) -> IncomeEvaluation:
    """年収演出判断を行う"""
    profile = video_data.profiles[0] if video_data.profiles else None
    if profile is None:
        return IncomeEvaluation(
            income_value=None, age_bracket="不明",
            threshold=700, emphasize=False,
            emphasis_reason="プロファイル情報不足",
            telop_suggestion="",
        )

    income = _extract_income_value(profile.income or "")
    age_bracket = _extract_age_bracket(profile.age or "")
    threshold = INCOME_THRESHOLD.get(age_bracket, 700)

    # 700万以上 → 無条件で強調ON
    if income and income >= 700:
        telop = _generate_emphasis_telop(income, age_bracket, profile)
        return IncomeEvaluation(
            income_value=income, age_bracket=age_bracket,
            threshold=threshold, emphasize=True,
            emphasis_reason=f"年収{income}万円（700万以上で無条件強調）",
            telop_suggestion=telop,
        )

    # 早見表基準+100万以上 → 強調ON
    if income and income >= threshold + 100:
        telop = _generate_emphasis_telop(income, age_bracket, profile)
        return IncomeEvaluation(
            income_value=income, age_bracket=age_bracket,
            threshold=threshold, emphasize=True,
            emphasis_reason=f"年収{income}万円（{age_bracket}基準{threshold}万+100万以上）",
            telop_suggestion=telop,
        )

    # 強調OFF → 代替の強みを検出
    alt_strengths = _find_alternative_strengths(video_data, profile)
    reason = f"年収{income}万円（{age_bracket}基準{threshold}万以下）" if income else "年収情報なし"
    return IncomeEvaluation(
        income_value=income, age_bracket=age_bracket,
        threshold=threshold, emphasize=False,
        emphasis_reason=reason + " → 年収以外の強さにフォーカス",
        telop_suggestion="",
        alternative_strengths=alt_strengths,
    )


def _extract_income_value(income_str: str) -> int | None:
    """年収文字列から万円単位の数値を抽出

    注意: 「目標」「見込み」等の将来値は除外し、現在の実績値のみを取得する
    """
    # カンマ入り数値を正規化（1,500万 → 1500万）
    income_str = re.sub(r"(\d),(\d)", r"\1\2", income_str)

    # 見込み・目標・トータル・合計・上司の情報を除去
    cleaned = re.sub(r"目標[^。\n]*", "", income_str)
    cleaned = re.sub(r"見込み[^。\n]*", "", cleaned)
    cleaned = re.sub(r"トータル[^。\n]*", "", cleaned)
    cleaned = re.sub(r"合計[^。\n]*", "", cleaned)
    # 「上司（40歳）で約1000万円、さらに上で1500万円」のような他人の年収を除去
    cleaned = re.sub(r"上司[^。\n]*", "", cleaned)
    cleaned = re.sub(r"さらに上[^。\n]*", "", cleaned)
    # 「あと10年で〜」のような将来予測を除去
    cleaned = re.sub(r"あと\d+年[^。\n]*", "", cleaned)

    # 優先度1: 「本業年収」or 「本業：」のパターン
    main_income_patterns = [
        r"本業[年収：:\s]*(\d{3,4})\s*万",
        r"本業[：:\s]*(\d{3,4})\s*[万〜]",
    ]
    for pattern in main_income_patterns:
        m = re.search(pattern, cleaned)
        if m:
            return int(m.group(1))

    # 優先度2: 一般的な年収パターン
    patterns = [
        r"年収[約：:\s]*(\d{3,4})\s*万",
        r"年間利益[約：:\s]*(\d{3,4})\s*万",
    ]
    values = []
    for pattern in patterns:
        for m in re.finditer(pattern, cleaned):
            values.append(int(m.group(1)))

    if values:
        return max(values)

    # 優先度3: 先頭の「約数字万円」パターン
    m = re.match(r"[約]?(\d{3,4})\s*万", cleaned.strip())
    if m:
        return int(m.group(1))

    # 優先度4: cleanedの中から最初の数字+万円
    m = re.search(r"(\d{3,4})\s*万[円〜]", cleaned)
    if m:
        return int(m.group(1))

    return None


def _extract_age_bracket(age_str: str) -> str:
    """年齢文字列から年齢帯を抽出"""
    # "28歳" → "20代後半"
    age_match = re.search(r"(\d{2})歳", age_str)
    if age_match:
        age = int(age_match.group(1))
        if age <= 24:
            return "20代前半"
        elif age <= 26:
            return "20代中盤"
        elif age <= 29:
            return "20代後半"
        elif age <= 34:
            return "30代前半"
        elif age <= 39:
            return "30代後半"
        else:
            return "40代"

    # "20代後半" などのパターン
    bracket_patterns = [
        (r"20代前半", "20代前半"),
        (r"20代中盤", "20代中盤"),
        (r"20代後半", "20代後半"),
        (r"30代前半", "30代前半"),
        (r"30代中盤", "30代中盤"),
        (r"30代後半", "30代後半"),
        (r"30代半ば", "30代中盤"),
        (r"40代", "40代"),
        (r"20代", "20代中盤"),  # 細分化不明
        (r"30代", "30代前半"),  # デフォルト
    ]
    for pattern, bracket in bracket_patterns:
        if re.search(pattern, age_str):
            return bracket

    return "不明"


def _generate_emphasis_telop(income: int, age_bracket: str, profile: PersonProfile) -> str:
    """年収強調テロップの提案文を生成"""
    parts = []

    # 20代で700万以上 → 年次補足
    if "20代" in age_bracket and income >= 700:
        age_text = profile.age or age_bracket
        parts.append(f"テロップ: 「{age_text}で年収{income}万円」（年齢の若さを際立たせる補足推奨）")
    else:
        parts.append(f"テロップ: 「年収{income}万円」を強調表示")

    # 特殊ケース: 新卒2年目等
    if profile.occupation:
        if "新卒" in profile.occupation or "1年目" in profile.occupation or "2年目" in profile.occupation:
            parts.append(f"補足テロップ: 「（{profile.occupation}で）」を追加")

    return " / ".join(parts)


def _find_alternative_strengths(video_data: VideoData, profile: PersonProfile) -> list:
    """A-3: 年収以外の強さを検出する"""
    strengths = []
    combined_text = " ".join([
        profile.occupation or "",
        profile.income or "",
        video_data.detailed_summary or "",
        video_data.guest_summary or "",
    ])

    # 在籍企業のブランド力
    brand_keywords = [
        "凸版", "トッパン", "大手", "最大手", "有名", "一部上場",
        "プライム", "Fortune", "外資", "グローバル",
    ]
    for kw in brand_keywords:
        if kw in combined_text:
            match_context = _find_context(combined_text, kw)
            strengths.append(AlternativeStrength(
                category="企業ブランド力",
                description=f"「{kw}」関連企業への在籍経験",
                source_text=match_context,
            ))
            break

    # キャリアパスの希少性
    career_keywords = ["転職", "キャリアチェンジ", "異業種", "独立", "起業", "フリーランス"]
    for kw in career_keywords:
        if kw in combined_text:
            match_context = _find_context(combined_text, kw)
            strengths.append(AlternativeStrength(
                category="キャリアパスの希少性",
                description=f"「{kw}」に関連する独自のキャリアパス",
                source_text=match_context,
            ))
            break

    # 勤務形態の自由度（ゆりかさんパターン）
    work_style_keywords = ["週4", "週3", "リモート", "在宅", "フレックス", "自由"]
    for kw in work_style_keywords:
        if kw in combined_text:
            match_context = _find_context(combined_text, kw)
            strengths.append(AlternativeStrength(
                category="勤務形態の自由度",
                description=f"「{kw}」のワークスタイルが強み",
                source_text=match_context,
            ))
            break

    # 転職先の年収見込み（りょうすけさんパターン）
    future_keywords = ["転職で", "転職先", "次の", "見込み", "狙える", "目標"]
    for kw in future_keywords:
        if kw in combined_text:
            # 転職後の年収数値を探す
            future_match = re.search(r"(?:転職|次の|見込み|狙え).*?(\d{3,4})万", combined_text)
            if future_match:
                strengths.append(AlternativeStrength(
                    category="転職先の年収見込み",
                    description=f"転職後の年収{future_match.group(1)}万円の見込み",
                    source_text=_find_context(combined_text, kw),
                ))
                break

    # 副業実績
    if profile.side_business:
        side_income_match = re.search(r"月(\d+)万", profile.side_business)
        if side_income_match:
            strengths.append(AlternativeStrength(
                category="副業実績",
                description=f"副業で月{side_income_match.group(1)}万円の実績",
                source_text=profile.side_business,
            ))

    return strengths


def _find_context(text: str, keyword: str, window: int = 50) -> str:
    """キーワード周辺のコンテキストを取得"""
    idx = text.find(keyword)
    if idx == -1:
        return ""
    start = max(0, idx - window)
    end = min(len(text), idx + len(keyword) + window)
    return text[start:end].strip()
