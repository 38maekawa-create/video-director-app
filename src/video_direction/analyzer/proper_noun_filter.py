from __future__ import annotations
"""A-4: 固有名詞規制

1. 文字起こし全文から企業名・サービス名を抽出
2. 各固有名詞について伏せるか判定
3. 伏せる場合のテロップテンプレート自動生成
"""

import re
from dataclasses import dataclass
from pathlib import Path
from ..integrations.ai_dev5_connector import VideoData


# 伏せないことが多い業界トップ企業（有名すぎて伏せる意味がない or 本人が開示済み）
# ※ 最終判断は文脈による。迷ったら伏せる。
WELL_KNOWN_COMPANIES = {
    "TEKO", "テコ",
}

# 業界カテゴリマッピング（テロップ生成用）
INDUSTRY_CATEGORIES = {
    "アクセンチュア": ("コンサルティング", "コンサルティングファーム"),
    "マッキンゼー": ("コンサルティング", "コンサルティングファーム"),
    "BCG": ("コンサルティング", "コンサルティングファーム"),
    "デロイト": ("コンサルティング", "監査法人/コンサルティングファーム"),
    "PwC": ("監査・コンサルティング", "監査法人"),
    "EY": ("監査・コンサルティング", "監査法人"),
    "KPMG": ("監査・コンサルティング", "監査法人"),
    "Google": ("IT", "テック企業"),
    "Amazon": ("IT", "テック企業"),
    "Apple": ("IT", "テック企業"),
    "Meta": ("IT", "テック企業"),
    "Microsoft": ("IT", "テック企業"),
    "AWS": ("クラウド", "テック企業"),
    "LINE": ("IT", "テック企業"),
    "Yahoo": ("IT", "テック企業"),
    "LINEヤフー": ("IT", "テック企業"),
    "凸版": ("印刷", "印刷業界最大手企業"),
    "凸版ホールディングス": ("印刷", "印刷業界最大手企業"),
    "大日本印刷": ("印刷", "印刷業界大手企業"),
    "キリン": ("飲料", "飲料メーカー"),
    "キリンビール": ("飲料", "ビールメーカー"),
    "サントリー": ("飲料", "飲料メーカー"),
    "サービスナウ": ("IT", "SaaS企業"),
    "ServiceNow": ("IT", "SaaS企業"),
}

# 固有名詞抽出用パターン
COMPANY_PATTERNS = [
    # 英字企業名
    r"\b[A-Z][A-Za-z]{2,}(?:\s+[A-Z][A-Za-z]+)*\b",
    # 日本語企業名（カタカナ3文字以上）
    r"[ァ-ヶー]{3,}",
    # 〇〇株式会社、〇〇ホールディングス等
    r"[\w]{2,}(?:株式会社|ホールディングス|グループ|コーポレーション)",
]


@dataclass
class ProperNounEntry:
    """固有名詞エントリ"""
    name: str
    category: str  # 企業名 / サービス名
    action: str  # "show" / "hide"
    reason: str
    telop_template: str  # 伏せる場合のテロップ提案
    occurrences: list  # 出現箇所（タイムスタンプ等）


def detect_proper_nouns(video_data: VideoData, guest_name: str = None) -> list[ProperNounEntry]:
    """固有名詞を検出し、判定・テロップ提案を生成する

    Args:
        video_data: 動画データ
        guest_name: ゲスト名（指定時、このゲストに関連する固有名詞のみを返す）
    """
    # ハイライトシーンと全文から固有名詞を抽出
    all_text = video_data.detailed_summary or ""
    if video_data.profiles:
        all_text += " " + (video_data.profiles[0].occupation or "")
    all_text += " " + (video_data.guest_summary or "")

    # ハイライトからの抽出（タイムスタンプ付き）
    noun_occurrences: dict[str, list[str]] = {}
    for highlight in video_data.highlights:
        for noun in _extract_nouns_from_text(highlight.text):
            if noun not in noun_occurrences:
                noun_occurrences[noun] = []
            noun_occurrences[noun].append(highlight.timestamp)

    # 詳細テキストからの追加抽出
    for noun in _extract_nouns_from_text(all_text):
        if noun not in noun_occurrences:
            noun_occurrences[noun] = []

    # ゲスト名が指定されている場合、そのゲストに関連する固有名詞のみをフィルタ
    if guest_name and noun_occurrences:
        guest_related = _get_guest_related_nouns(guest_name, video_data)
        if guest_related is not None:
            # ゲストのプロファイルに関連する固有名詞のみを残す
            filtered = {}
            for noun, timestamps in noun_occurrences.items():
                if noun in guest_related:
                    filtered[noun] = timestamps
            noun_occurrences = filtered

    # 各固有名詞を判定
    results = []
    for noun, timestamps in noun_occurrences.items():
        entry = _judge_noun(noun, timestamps, video_data)
        if entry:
            results.append(entry)

    return results


def _get_guest_related_nouns(guest_name: str, video_data: VideoData) -> set[str] | None:
    """ゲストに関連する固有名詞のセットを返す

    MEMBER_MASTER.jsonのプロファイルと、video_dataのゲスト固有テキスト
    （profiles[0].occupation, guest_summary）のみから固有名詞を抽出し、
    そのゲストに関連する企業名のセットを返す。

    ゲスト情報が見つからない場合はNoneを返し、フィルタリングをスキップする。
    """
    # ゲスト固有のテキストのみから固有名詞を抽出
    guest_text = ""
    if video_data.profiles:
        profile = video_data.profiles[0]
        guest_text += (profile.occupation or "") + " "
        guest_text += (profile.name or "") + " "
    guest_text += (video_data.guest_summary or "") + " "

    # MEMBER_MASTER.jsonからゲストのプロファイル情報も取得
    try:
        from ..integrations.member_master import MemberMaster
        mm = MemberMaster()
        member = mm.find_member(guest_name)
        if member and member.has_people_file:
            profile_text = mm.get_people_profile(member)
            if profile_text:
                guest_text += profile_text + " "
    except Exception:
        pass

    if not guest_text.strip():
        return None  # ゲスト情報なし → フィルタリングしない

    # ゲスト固有テキストから企業名を抽出
    related = set()
    for company in INDUSTRY_CATEGORIES:
        if _is_standalone_match(company, guest_text):
            related.add(company)

    # ハイライトシーンのテキストからも抽出
    # （ハイライトはそのゲストの動画に紐づいているため、関連性が高い）
    for highlight in video_data.highlights:
        for company in INDUSTRY_CATEGORIES:
            if _is_standalone_match(company, highlight.text):
                related.add(company)

    return related


def _is_standalone_match(word: str, text: str) -> bool:
    """単語が独立して出現しているか（部分文字列でないか）

    カタカナ単語の場合、前後にカタカナが続いていれば
    より長い単語の一部とみなし、マッチしない。
    例: 「くますけ」の中の「キリン」は不一致（前後がカタカナ）。
    """
    def _is_katakana(ch: str) -> bool:
        return '\u30A0' <= ch <= '\u30FF'

    idx = text.find(word)
    while idx != -1:
        before_ok = (idx == 0 or not _is_katakana(text[idx - 1]))
        after_ok = (idx + len(word) >= len(text)
                    or not _is_katakana(text[idx + len(word)]))
        if before_ok and after_ok:
            return True
        idx = text.find(word, idx + 1)
    return False


def _extract_nouns_from_text(text: str) -> list[str]:
    """テキストから企業名・サービス名を抽出"""
    found = set()

    # 既知の企業名を検出（部分文字列マッチを防止）
    for company in INDUSTRY_CATEGORIES:
        if _is_standalone_match(company, text):
            found.add(company)

    # パターンマッチングで追加抽出
    for pattern in COMPANY_PATTERNS:
        for match in re.finditer(pattern, text):
            candidate = match.group(0).strip()
            # フィルタリング: 一般的すぎる単語を除外
            if len(candidate) >= 3 and candidate not in _COMMON_WORDS:
                # 既知企業名と完全一致するかチェック（部分文字列マッチ防止）
                for known in INDUSTRY_CATEGORIES:
                    if candidate == known or _is_standalone_match(known, candidate):
                        found.add(known)

    return sorted(found)


def _judge_noun(noun: str, timestamps: list, video_data: VideoData) -> ProperNounEntry | None:
    """固有名詞の出す/伏せる判定"""
    # TEKOは常に出す
    if noun in WELL_KNOWN_COMPANIES:
        return None  # レポートに含めない（判定不要）

    # 文脈から開示判断
    combined_text = (video_data.detailed_summary or "") + " " + (video_data.guest_summary or "")

    # 本人が開示OKとしている場合のチェック
    # 「前置きで開示不能と言っている」パターン
    hide_indicators = [
        f"{noun}.*伏せ", f"{noun}.*言えない", f"{noun}.*出せない",
        f"開示.*不可", "ピー音", "企業名.*伏せ",
    ]
    for indicator in hide_indicators:
        if re.search(indicator, combined_text):
            return _create_hidden_entry(noun, timestamps, "本人または文脈から開示不可と判断")

    # 既知企業なら業界カテゴリで処理
    if noun in INDUSTRY_CATEGORIES:
        industry, company_type = INDUSTRY_CATEGORIES[noun]
        # 判断基準: 本人が動画内で明示的に言及していれば出す
        # → ハイライトシーンに含まれていれば言及済みとみなす
        if timestamps:
            return ProperNounEntry(
                name=noun,
                category="企業名",
                action="show",
                reason=f"本人が動画内で言及（{', '.join(timestamps[:3])}）",
                telop_template="",
                occurrences=timestamps,
            )
        else:
            # タイムスタンプなし = 要約から推定された情報 → 安全側に倒す
            return _create_hidden_entry(noun, timestamps,
                                        "要約から推定された情報のため安全側に伏せる")

    return None


def _create_hidden_entry(noun: str, timestamps: list, reason: str) -> ProperNounEntry:
    """伏せる判定のエントリを作成"""
    industry_info = INDUSTRY_CATEGORIES.get(noun)
    if industry_info:
        industry, company_type = industry_info
        templates = [
            f"誰もが知る{industry}業界の超大手企業",
            f"{industry}トップクラスの{company_type}",
        ]
    else:
        templates = [
            "誰もが知る業界の超大手企業",
            "業界トップクラスの企業",
        ]

    return ProperNounEntry(
        name=noun,
        category="企業名",
        action="hide",
        reason=reason,
        telop_template=" / ".join(templates),
        occurrences=timestamps,
    )


# 一般的すぎる単語（誤検出防止）
_COMMON_WORDS = {
    "YouTube", "eBay", "PSA", "LINE", "Note", "THE",
    "AND", "FOR", "NOT", "THE", "WITH", "FROM",
    "インタビュー", "マネジメント", "プロジェクト", "コンテンツ",
    "メンバー", "コミュニティ", "サポート", "リサーチ",
    "コンサル", "ビジネス", "キャリア", "トレカ",
    "ライバー", "エージェント", "パラレル", "フリーランス",
}
