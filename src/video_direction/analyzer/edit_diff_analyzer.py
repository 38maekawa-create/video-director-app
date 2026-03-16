"""手修正のdiff分析エンジン

ディレクションレポート・タイトル・概要欄・サムネイル指示の
手修正内容をルールベースで分析し、変更カテゴリ・重要度を判定する。
LLMは使用せず、difflibによる差分検出とキーワードマッチングで分類する。
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class EditChange:
    """個別の変更"""
    change_type: str  # "added", "removed", "modified"
    original_text: Optional[str]
    edited_text: Optional[str]
    category: str  # "direction", "telop", "bgm", "color", "structure", "tone", "hook", "attribute"


@dataclass
class EditDiffResult:
    """diff分析結果"""
    total_changes: int
    changes: List[EditChange]
    categories_affected: List[str]
    severity: str  # "minor", "moderate", "major"
    learning_signal: str  # 学習に使える要約


# --- カテゴリ分類用キーワード ---

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "telop": [
        "テロップ", "字幕", "テキスト", "フォント", "文字",
        "キャプション", "表示", "テロ", "タイトルテロップ",
    ],
    "bgm": [
        "BGM", "bgm", "音楽", "SE", "効果音", "サウンド",
        "音量", "音", "ミュージック", "ジングル",
    ],
    "color": [
        "カラー", "色", "グレーディング", "LUT", "彩度",
        "コントラスト", "明るさ", "トーンカーブ", "ホワイトバランス",
    ],
    "structure": [
        "構成", "順番", "カット", "シーン", "セクション",
        "パート", "流れ", "展開", "尺", "タイムライン",
        "冒頭", "中盤", "終盤", "エンディング", "オープニング",
    ],
    "tone": [
        "トーン", "雰囲気", "テンション", "テンポ", "空気感",
        "世界観", "ムード", "印象",
    ],
    "hook": [
        "フック", "サムネ", "サムネイル", "つかみ", "冒頭",
        "アテンション", "興味", "クリック", "CTR",
    ],
    "attribute": [
        "属性", "ターゲット", "年齢", "職業", "年収",
        "ペルソナ", "視聴者", "層",
    ],
}


def _classify_text(text: str) -> str:
    """テキストからカテゴリを推定する。マッチしなければ "direction" を返す。"""
    scores: dict[str, int] = {}
    for category, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[category] = score
    if not scores:
        return "direction"
    return max(scores, key=scores.get)  # type: ignore[arg-type]


def _compute_severity(changes: List[EditChange]) -> str:
    """変更量からseverityを判定する。"""
    n = len(changes)
    if n == 0:
        return "minor"
    # 大幅な変更（5個以上）またはstructure/hook変更を含む場合は major
    high_impact = {"structure", "hook", "tone"}
    if n >= 5 or any(c.category in high_impact for c in changes):
        return "major"
    if n >= 2:
        return "moderate"
    return "minor"


def _generate_learning_signal(changes: List[EditChange], categories: List[str]) -> str:
    """学習に使える要約テキストを生成する。"""
    if not changes:
        return "変更なし"

    parts: list[str] = []
    cat_counts: dict[str, int] = {}
    for c in changes:
        cat_counts[c.category] = cat_counts.get(c.category, 0) + 1

    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        parts.append(f"{cat}: {count}件")

    type_counts: dict[str, int] = {}
    for c in changes:
        type_counts[c.change_type] = type_counts.get(c.change_type, 0) + 1

    type_desc = ", ".join(f"{t}{n}件" for t, n in type_counts.items())
    return f"カテゴリ別: {', '.join(parts)} / 変更種別: {type_desc}"


def _extract_changes(original: str, edited: str) -> List[EditChange]:
    """difflibでテキストの差分を抽出し、EditChangeリストを返す。"""
    original_lines = original.splitlines()
    edited_lines = edited.splitlines()

    changes: List[EditChange] = []
    matcher = difflib.SequenceMatcher(None, original_lines, edited_lines)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        orig_block = "\n".join(original_lines[i1:i2]) if i1 < i2 else None
        edit_block = "\n".join(edited_lines[j1:j2]) if j1 < j2 else None

        # カテゴリ分類用のテキスト
        classify_target = edit_block or orig_block or ""

        if tag == "replace":
            change_type = "modified"
        elif tag == "insert":
            change_type = "added"
        elif tag == "delete":
            change_type = "removed"
        else:
            continue

        changes.append(EditChange(
            change_type=change_type,
            original_text=orig_block,
            edited_text=edit_block,
            category=_classify_text(classify_target),
        ))

    return changes


def _build_result(original: str, edited: str, changes: List[EditChange]) -> EditDiffResult:
    """EditChangeリストからEditDiffResultを構築する。"""
    categories = sorted(set(c.category for c in changes))
    severity = _compute_severity(changes)
    learning_signal = _generate_learning_signal(changes, categories)

    return EditDiffResult(
        total_changes=len(changes),
        changes=changes,
        categories_affected=categories,
        severity=severity,
        learning_signal=learning_signal,
    )


def analyze_direction_diff(original: str, edited: str) -> EditDiffResult:
    """ディレクションレポートのdiffを分析する。"""
    changes = _extract_changes(original, edited)
    return _build_result(original, edited, changes)


def analyze_title_diff(original: str, edited: str) -> EditDiffResult:
    """タイトルのdiffを分析する。タイトルは短文なので行単位ではなく全体比較。"""
    if original.strip() == edited.strip():
        return EditDiffResult(
            total_changes=0, changes=[], categories_affected=[],
            severity="minor", learning_signal="変更なし",
        )

    # タイトル全体を1つの変更として扱う
    change = EditChange(
        change_type="modified",
        original_text=original.strip(),
        edited_text=edited.strip(),
        category="hook",  # タイトルはフック要素
    )
    return _build_result(original, edited, [change])


def analyze_description_diff(original: str, edited: str) -> EditDiffResult:
    """概要欄のdiffを分析する。"""
    changes = _extract_changes(original, edited)
    return _build_result(original, edited, changes)


def analyze_thumbnail_diff(original: str, edited: str) -> EditDiffResult:
    """サムネイル指示のdiffを分析する。"""
    changes = _extract_changes(original, edited)
    # サムネイル変更は基本的にhookカテゴリに上書き
    for c in changes:
        if c.category == "direction":
            c.category = "hook"
    return _build_result(original, edited, changes)
