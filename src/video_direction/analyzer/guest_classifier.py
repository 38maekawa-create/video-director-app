from __future__ import annotations
"""A-1: ゲスト層自動分類

分類ロジック:
- 層c: 自営業家系・2代目・3代目
- 層a: 年収1000万以上 OR 有名企業管理職 OR 士業（監査法人等）
- 層b: それ以外（相対的強さの言語化が必要）
"""

import re
from dataclasses import dataclass
from ..integrations.ai_dev5_connector import VideoData, PersonProfile


# 層aに該当する有名企業・士業キーワード
TIER_A_KEYWORDS = [
    "アクセンチュア", "マッキンゼー", "BCG", "ベイン", "デロイト",
    "PwC", "EY", "KPMG", "監査法人", "BIG4",
    "GAFA", "Google", "Amazon", "Apple", "Meta", "Microsoft",
    "AWS", "外資",
    "VP", "執行役員", "取締役", "弁護士", "公認会計士",
    "医師", "パイロット",
]

# 層cに該当するキーワード（「実家」だけでは不十分。自営業の文脈が必要）
TIER_C_KEYWORDS_STRONG = [
    "自営業家系", "2代目", "3代目", "二代目", "三代目",
    "家業", "跡継ぎ", "家族経営",
]
# 「実家」は自営業との共起で初めて層cとする
TIER_C_KEYWORDS_WEAK = ["実家"]
TIER_C_CONTEXT_REQUIRED = ["自営", "家業", "継ぐ", "跡継ぎ", "家業を経営", "実家の経営"]

# 見せ方テンプレート
PRESENTATION_TEMPLATES = {
    "a": "強さ・ハイキャリアさを前面に押し出す。その人のキャリアの中で最も強い部分にフォーカスした演出。",
    "b": "年収以外の文脈で強さを言語化する。在籍企業のブランド力、キャリアパスの希少性、勤務形態の自由度、転職先の年収見込み等を活用。",
    "c": "強さに加えて、自営業家系の背景やご本人の葛藤や経歴、そこからTEKOを通じてどう変化したかというストーリーにも重きを置く。",
}


@dataclass
class ClassificationResult:
    """ゲスト分類結果"""
    tier: str  # "a", "b", "c"
    tier_label: str  # "層a", "層b", "層c"
    reason: str  # 分類理由
    presentation_template: str  # 見せ方テンプレート
    confidence: str  # "high", "medium", "low"


def classify_guest(video_data: VideoData) -> ClassificationResult:
    """ゲストを層a/b/cに分類する"""
    profile = _get_primary_profile(video_data)
    if not profile:
        return ClassificationResult(
            tier="b",
            tier_label="層b",
            reason="プロファイル情報が不足のためデフォルト分類",
            presentation_template=PRESENTATION_TEMPLATES["b"],
            confidence="low",
        )

    # プロファイルベースのテキスト（現在の属性のみ。将来の希望は含めない）
    profile_text = " ".join([
        profile.occupation or "",
        profile.income or "",
        profile.teko_info or "",
        video_data.guest_summary or "",
    ])
    # 詳細要約も参照するが、分類判定はプロファイルベースを優先
    full_text = profile_text + " " + (video_data.detailed_summary or "")

    # 層c判定: 自営業家系・2代目・3代目
    for keyword in TIER_C_KEYWORDS_STRONG:
        if keyword in full_text:
            return ClassificationResult(
                tier="c",
                tier_label="層c（自営業家系）",
                reason=f"「{keyword}」に該当",
                presentation_template=PRESENTATION_TEMPLATES["c"],
                confidence="high",
            )
    # 弱いキーワード（「実家」等）は自営業文脈との共起で判定
    for keyword in TIER_C_KEYWORDS_WEAK:
        if keyword in full_text:
            if any(ctx in full_text for ctx in TIER_C_CONTEXT_REQUIRED):
                return ClassificationResult(
                    tier="c",
                    tier_label="層c（自営業家系）",
                    reason=f"「{keyword}」+ 自営業文脈に該当",
                    presentation_template=PRESENTATION_TEMPLATES["c"],
                    confidence="medium",
                )

    # 年収抽出: プロファイルのincomeフィールドのみから取得（目標値の誤検出防止）
    income = _extract_income(profile.income or "", "")

    # 層a判定: 年収1000万以上
    if income and income >= 1000:
        return ClassificationResult(
            tier="a",
            tier_label="層a（圧倒的に強い）",
            reason=f"年収{income}万円（1000万以上）",
            presentation_template=PRESENTATION_TEMPLATES["a"],
            confidence="high",
        )

    # 層a判定: 有名企業管理職・士業
    # profile_textのみで判定（detailed_summaryに「将来外資に転職したい」等の文脈での誤判定防止）
    # さらに仮定文脈（「転職すれば」「の場合」等）でのキーワードは除外
    for keyword in TIER_A_KEYWORDS:
        if keyword.lower() in profile_text.lower():
            # 仮定・条件文脈での言及は除外（例: 「外資系の場合」「転職すれば外資」）
            if _is_hypothetical_context(profile_text, keyword):
                continue
            # 「医師と」「医師に」等、本人が医師ではないケースを除外
            if not _is_subject_attribute(profile_text, keyword):
                continue
            return ClassificationResult(
                tier="a",
                tier_label="層a（圧倒的に強い）",
                reason=f"「{keyword}」に該当",
                presentation_template=PRESENTATION_TEMPLATES["a"],
                confidence="high" if income and income >= 700 else "medium",
            )

    # 層b: それ以外
    reason = "年収1000万未満かつ層a/cの特徴キーワードなし"
    if income:
        reason = f"年収{income}万円（1000万未満、相対的強さの言語化が必要）"
    return ClassificationResult(
        tier="b",
        tier_label="層b（相対的強さの言語化が必要）",
        reason=reason,
        presentation_template=PRESENTATION_TEMPLATES["b"],
        confidence="medium" if income else "low",
    )


def _get_primary_profile(video_data: VideoData) -> PersonProfile | None:
    """メインゲストのプロファイルを取得"""
    if video_data.profiles:
        return video_data.profiles[0]
    return None


def _is_hypothetical_context(text: str, keyword: str) -> bool:
    """キーワードが仮定・条件文脈で使われているか判定

    キーワードの直近（前後20文字）に仮定表現があるかで判断。
    離れた位置の仮定表現（例: 別フィールドの「転職後」）は無視する。
    """
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return False
    # キーワード前後20文字のみ（狭い窓で誤検出防止）
    start = max(0, idx - 20)
    end = min(len(text), idx + len(keyword) + 20)
    context = text[start:end]
    # 仮定文脈のパターン（キーワードに直接かかる表現のみ）
    hypothetical_patterns = [
        r"転職すれば.*" + re.escape(keyword),
        re.escape(keyword) + r".*の場合",
        re.escape(keyword) + r".*したら",
        r"すれば.*" + re.escape(keyword),
        re.escape(keyword) + r".*昇進予定",
        re.escape(keyword) + r".*予定",
        re.escape(keyword) + r".*想定",
        re.escape(keyword) + r".*検討",
        re.escape(keyword) + r".*目指",
        re.escape(keyword) + r".*見込み",
    ]
    for pattern in hypothetical_patterns:
        if re.search(pattern, context):
            return True
    return False


def _is_subject_attribute(text: str, keyword: str) -> bool:
    """キーワードが主語（本人）の属性として使われているか判定

    「医師と対話する」→ False（本人は医師ではない）
    「医師」（単体、または「医師として」）→ True
    企業名・外資等は常にTrue（属性チェック不要）
    """
    # 職種キーワード（本人の職業か確認が必要なもの）のみチェック
    subject_check_keywords = {"医師", "弁護士", "公認会計士", "パイロット"}
    if keyword not in subject_check_keywords:
        return True  # 企業名等はチェック不要

    idx = text.find(keyword)
    if idx == -1:
        return True

    # キーワード直後の文字を確認
    end_idx = idx + len(keyword)
    if end_idx < len(text):
        next_char = text[end_idx]
        # 「医師と」「医師に」「医師へ」「医師から」→ 本人ではない
        if next_char in "とにへからの":
            return False
    return True


def _extract_income(income_str: str, full_text: str = "") -> int | None:
    """年収の数値（万円単位）を抽出する（本業年収のみ）

    注意: 目標値・トータル値・副業込み合計は除外する
    """
    # カンマ入り数値を正規化（1,500万 → 1500万）
    income_str = re.sub(r"(\d),(\d)", r"\1\2", income_str)

    # 目標・トータル・合計を除去
    cleaned = re.sub(r"目標[^。\n]*", "", income_str)
    cleaned = re.sub(r"トータル[^。\n]*", "", cleaned)
    cleaned = re.sub(r"合計[^。\n]*", "", cleaned)

    # 優先度1: 「本業年収」パターン
    m = re.search(r"本業[年収：:\s]*(\d{3,4})\s*万", cleaned)
    if m:
        return int(m.group(1))

    # 優先度2: 一般的な年収パターン
    patterns = [
        r"年収[約：:\s]*(\d{3,4})\s*[万〜]",
        r"年間利益[約：:\s]*(\d{3,4})\s*[万〜]",
    ]
    values = []
    for pattern in patterns:
        for match in re.finditer(pattern, cleaned):
            values.append(int(match.group(1)))

    if values:
        return max(values)

    # 優先度3: 先頭の「数字+万円」（"1400万円（35歳時見込み...）"のようなケース）
    m = re.match(r"[約]?(\d{3,4})\s*万", cleaned.strip())
    if m:
        return int(m.group(1))

    return None
