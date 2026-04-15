from __future__ import annotations
"""品質判断ガイドローダー — QUALITY_JUDGMENT_GUIDE.md を読み込んでプロンプト注入用テキストを返す

ディレクションレポート生成時に、ハイライト選定・演出判断・層分類の品質基準を
LLMプロンプトに注入するためのモジュール。
"""

import os
import re
from pathlib import Path


# デフォルトのガイドファイルパス（環境変数で上書き可能）
# .claude/rules/ に一元化。symlinkで docs/QUALITY_JUDGMENT_GUIDE.md を参照する
DEFAULT_GUIDE_PATH = Path.home() / "AI開発10" / ".claude" / "rules" / "quality-judgment-guide.md"

# コンテンツライン判定用キーワード（不動産軸）
REALESTATE_KEYWORDS = [
    "不動産", "物件", "融資", "棟", "利回り", "家賃",
    "キャッシュフロー", "CF", "賃貸", "築年", "区分",
    "一棟", "ローン", "金利", "返済", "管理会社",
    "入居率", "空室", "リフォーム", "修繕", "売却",
]


def _get_guide_path() -> Path:
    """品質判断ガイドのファイルパスを取得する（環境変数で上書き可能）"""
    env_path = os.environ.get("QUALITY_JUDGMENT_GUIDE_PATH")
    if env_path:
        return Path(env_path)
    return DEFAULT_GUIDE_PATH


def load_quality_guide() -> str:
    """品質判断ガイドの全文を読み込む

    Returns:
        ガイド全文。ファイル不在時は空文字（安全な失敗）
    """
    path = _get_guide_path()
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""


def _extract_section(full_text: str, section_number: int, section_title_pattern: str) -> str:
    """ガイドから指定セクションを抽出する

    Args:
        full_text: ガイド全文
        section_number: セクション番号（例: 5）
        section_title_pattern: セクションタイトルの正規表現パターン

    Returns:
        セクションテキスト。見つからない場合は空文字
    """
    if not full_text:
        return ""

    # セクション開始パターン: ## N. タイトル
    start_pattern = rf"^## {section_number}\.\s+{section_title_pattern}"
    start_match = re.search(start_pattern, full_text, re.MULTILINE)
    if not start_match:
        return ""

    start_pos = start_match.start()

    # 次の ## セクションまたは --- で終了
    rest = full_text[start_pos + len(start_match.group()):]
    end_match = re.search(r"^---$|^## \d+\.", rest, re.MULTILINE)
    if end_match:
        end_pos = start_pos + len(start_match.group()) + end_match.start()
        return full_text[start_pos:end_pos].strip()
    else:
        return full_text[start_pos:].strip()


def get_highlight_criteria() -> str:
    """セクション5（ハイライト選定品質基準）を抽出して返す

    含まれる内容:
    - パンチラインの4つの引き金（共感・好奇心・パンチ力・逆説）
    - 引きの強い事実の畳みかけパターン
    - NGパターン4種
    - 全42本のタイトルパンチライン一覧
    """
    full_text = load_quality_guide()
    return _extract_section(full_text, 5, r"ハイライト選定の品質基準")


def get_direction_criteria() -> str:
    """セクション2（演出ディレクション品質基準）を抽出して返す"""
    full_text = load_quality_guide()
    return _extract_section(full_text, 2, r"ディレクションレポート.*演出ディレクションの品質基準")


def get_content_line_criteria() -> str:
    """セクション1の「2つのコンテンツライン」を抽出して返す

    キャリア軸 vs 不動産ノウハウ軸の判定基準を含む。
    """
    full_text = load_quality_guide()
    if not full_text:
        return ""

    # 「2つのコンテンツライン」サブセクションを抽出
    pattern = r"### TEKO対談動画の2つのコンテンツライン"
    match = re.search(pattern, full_text)
    if not match:
        return ""

    start_pos = match.start()
    rest = full_text[start_pos:]
    # 次の --- または ## セクションで終了
    end_match = re.search(r"^---$|^## \d+\.", rest, re.MULTILINE)
    if end_match:
        return rest[:end_match.start()].strip()
    return rest.strip()


def get_guest_tier_criteria() -> str:
    """セクション1の層分類ルールを抽出して返す"""
    full_text = load_quality_guide()
    return _extract_section(full_text, 1, r"ディレクションレポート.*ゲスト層分類の判断基準")


def determine_content_line(title: str = "", transcript: str = "", guest_summary: str = "") -> str:
    """コンテンツライン（キャリア軸/不動産軸）を自動判定する

    タイトル・文字起こし・ゲスト概要から不動産キーワードの出現頻度を分析し、
    不動産軸かキャリア軸かを判定する。

    Args:
        title: 動画タイトル
        transcript: 文字起こしテキスト（全文または要約）
        guest_summary: ゲスト概要テキスト

    Returns:
        "realestate" (不動産軸) または "career" (キャリア軸)
    """
    # 全テキストを結合して分析
    combined = f"{title} {guest_summary} {transcript}".lower()

    if not combined.strip():
        return "career"  # デフォルトはキャリア軸

    # 不動産キーワードの出現回数をカウント
    realestate_count = 0
    for kw in REALESTATE_KEYWORDS:
        realestate_count += len(re.findall(re.escape(kw.lower()), combined))

    # テキスト長に対する不動産キーワード密度で判定
    # 短いテキスト（タイトルのみ等）の場合は出現回数で判定
    text_len = len(combined)

    if text_len < 200:
        # 短いテキスト: 3回以上で不動産軸
        threshold = 3
    else:
        # 長いテキスト: 密度ベース（1000文字あたり5回以上）
        threshold = max(5, text_len // 200)

    if realestate_count >= threshold:
        return "realestate"

    return "career"


def build_quality_injection_text(
    content_line: str = "career",
    include_highlight: bool = True,
    include_direction: bool = True,
    include_content_line: bool = True,
    include_tier: bool = True,
    compact: bool = False,
) -> str:
    """プロンプト注入用の品質基準テキストを構築する

    Args:
        content_line: コンテンツライン（"career" or "realestate"）
        include_highlight: ハイライト選定基準を含めるか
        include_direction: 演出ディレクション基準を含めるか
        include_content_line: コンテンツライン判定基準を含めるか
        include_tier: 層分類基準を含めるか
        compact: trueの場合、最も重要な部分のみに絞る

    Returns:
        プロンプト注入用テキスト
    """
    sections = []
    sections.append("## 品質基準（必ず反映すること）")
    sections.append("")

    if compact:
        # コンパクトモード: ハイライト4引き金 + NGパターン + コンテンツライン判定のみ
        highlight_text = get_highlight_criteria()
        if highlight_text:
            # 4つの引き金とNGパターンだけ抽出
            compact_parts = _extract_compact_highlight(highlight_text)
            if compact_parts:
                sections.append("### ハイライト選定基準")
                sections.append(compact_parts)
                sections.append("")

        if include_content_line:
            cl_text = get_content_line_criteria()
            if cl_text:
                sections.append("### コンテンツライン判定")
                sections.append(f"この動画のコンテンツライン: **{'不動産実績対談（ノウハウ軸）' if content_line == 'realestate' else '通常のTEKO実績対談（キャリア軸）'}**")
                sections.append(cl_text)
                sections.append("")

        return "\n".join(sections)

    # フルモード
    if include_highlight:
        highlight_text = get_highlight_criteria()
        if highlight_text:
            sections.append("### ハイライト選定基準")
            sections.append(highlight_text)
            sections.append("")

    if include_direction:
        direction_text = get_direction_criteria()
        if direction_text:
            sections.append("### 演出ディレクション基準")
            sections.append(direction_text)
            sections.append("")

    if include_content_line:
        cl_text = get_content_line_criteria()
        if cl_text:
            sections.append("### コンテンツライン判定")
            sections.append(f"この動画のコンテンツライン: **{'不動産実績対談（ノウハウ軸）' if content_line == 'realestate' else '通常のTEKO実績対談（キャリア軸）'}**")
            if content_line == "realestate":
                sections.append("→ 層分類より不動産の実績・内容がパンチライン。マニュアルの層分類を厳密に適用するよりも不動産実績とパンチラインにフォーカスすること。")
            else:
                sections.append("→ マニュアルの層分類・社格・年収の見せ方を厳密に適用すること。")
            sections.append(cl_text)
            sections.append("")

    if include_tier:
        tier_text = get_guest_tier_criteria()
        if tier_text:
            sections.append("### ゲスト層分類基準")
            sections.append(tier_text)
            sections.append("")

    return "\n".join(sections)


def _extract_compact_highlight(highlight_text: str) -> str:
    """ハイライト基準からコンパクト版を抽出（4引き金 + NGパターン）"""
    if not highlight_text:
        return ""

    parts = []

    # パンチラインが「強い」条件セクション
    punchline_match = re.search(
        r"### パンチラインが「強い」条件(.*?)### (?:引きの強い事実|NGパターン)",
        highlight_text,
        re.DOTALL,
    )
    if punchline_match:
        parts.append(punchline_match.group(0).rsplit("###", 1)[0].strip())

    # NGパターンセクション
    ng_match = re.search(
        r"### NGパターン(.*?)(?:### |$)",
        highlight_text,
        re.DOTALL,
    )
    if ng_match:
        parts.append("### NGパターン" + ng_match.group(1).strip())

    return "\n\n".join(parts)
