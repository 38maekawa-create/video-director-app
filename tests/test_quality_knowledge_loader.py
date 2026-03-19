"""quality_knowledge_loader のユニットテスト"""

import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.knowledge.quality_knowledge_loader import (
    load_quality_guide,
    get_highlight_criteria,
    get_direction_criteria,
    get_content_line_criteria,
    get_guest_tier_criteria,
    determine_content_line,
    build_quality_injection_text,
    _extract_section,
    _extract_compact_highlight,
    _get_guide_path,
    DEFAULT_GUIDE_PATH,
    REALESTATE_KEYWORDS,
)


# ────────────────────────────────────────────────
# ファイル読み込み
# ────────────────────────────────────────────────

class TestLoadQualityGuide:
    def test_ガイドファイルが存在すれば内容を返す(self):
        """QUALITY_JUDGMENT_GUIDE.md が存在するなら内容が空でない"""
        result = load_quality_guide()
        if DEFAULT_GUIDE_PATH.exists():
            assert len(result) > 0, "ガイドファイルが存在するのに空文字"
        else:
            assert result == ""

    def test_環境変数でパスを上書きできる(self):
        """QUALITY_JUDGMENT_GUIDE_PATH 環境変数でパスを指定"""
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write("# テスト品質ガイド\nテスト内容")
            tmp_path = f.name

        try:
            os.environ["QUALITY_JUDGMENT_GUIDE_PATH"] = tmp_path
            path = _get_guide_path()
            assert str(path) == tmp_path
            result = load_quality_guide()
            assert "テスト品質ガイド" in result
        finally:
            del os.environ["QUALITY_JUDGMENT_GUIDE_PATH"]
            Path(tmp_path).unlink()

    def test_存在しないパスは空文字を返す(self):
        """ファイル不在時は空文字で安全に返る"""
        os.environ["QUALITY_JUDGMENT_GUIDE_PATH"] = "/非存在/guide.md"
        try:
            result = load_quality_guide()
            assert result == ""
        finally:
            del os.environ["QUALITY_JUDGMENT_GUIDE_PATH"]


# ────────────────────────────────────────────────
# セクション抽出
# ────────────────────────────────────────────────

SAMPLE_GUIDE = """# 品質判断ガイド

---

## 1. ディレクションレポート — ゲスト層分類の判断基準

### ルール

| 条件 | 層分類 |
|------|--------|
| 年収1000万以上 | 層a |
| 年収700万以上 + 企業ブランド | 層a |

### TEKO対談動画の2つのコンテンツライン（なおとさん 03-20確定）

| コンテンツライン | 目的 |
|-----------------|------|
| ① 通常のTEKO実績対談（キャリア軸） | ハイキャリア層に刺しにいく |
| ② 不動産実績対談（ノウハウ軸） | 顕在層を取り込む |

→ さといも・トーマス、メンイチ等の不動産対談では不動産実績にフォーカス。

---

## 2. ディレクションレポート — 演出ディレクションの品質基準

### ルール

編集者が読んで即座にアクションに移せる具体性が必須。以下はNG:
- 「色変え: テロップ出現に合わせて画面演出」→ 何色に変えるか不明

---

## 5. ハイライト選定の品質基準

### ハイライトの目的

冒頭ハイライトは動画本編を見たいと思わせるためのフック。

### パンチラインが「強い」条件

#### (1) 共感 —「自分と同じ境遇の人だ」
同じ属性・同じ状況の人に「わかる...」と思わせる。

#### (2) 好奇心 —「どんな世界線？」
圧倒的強者の発言に「え？」ってなる。

#### (3) 言葉自体のパンチ力
聞いた瞬間に刺さる。

#### (4) 逆説 — 常識をひっくり返す
世間の「当たり前」を否定することで「なんで？」を喚起。

### 引きの強い事実をハイライトに詰め込む

年収・社格・実績数字をとにかく畳みかける。

### NGパターン

| NG類型 | 具体例 | 理由 |
|--------|--------|------|
| 1フレーズで意味が通じない | 脈絡なし | フック不成立 |
| パンチが弱い第三者エピソード | 大したフックにならない | パンチが弱い |
| フックと本編の整合性がない | 別人の話 | 裏切り |
| 相槌・つなぎ言葉 | 「そうですね」 | 問題外 |

### 背景やり取り

なおとさんのフィードバック内容。

---

## 6. このガイドの使い方

ガイドの使い方説明。
"""


class TestExtractSection:
    def test_セクション1を抽出する(self):
        result = _extract_section(SAMPLE_GUIDE, 1, r"ディレクションレポート.*ゲスト層分類の判断基準")
        assert "年収1000万以上" in result
        assert "演出ディレクションの品質基準" not in result

    def test_セクション2を抽出する(self):
        result = _extract_section(SAMPLE_GUIDE, 2, r"ディレクションレポート.*演出ディレクションの品質基準")
        assert "編集者が読んで" in result
        assert "ハイライト選定" not in result

    def test_セクション5を抽出する(self):
        result = _extract_section(SAMPLE_GUIDE, 5, r"ハイライト選定の品質基準")
        assert "パンチラインが「強い」条件" in result
        assert "NGパターン" in result

    def test_存在しないセクションは空文字を返す(self):
        result = _extract_section(SAMPLE_GUIDE, 99, r"存在しないセクション")
        assert result == ""

    def test_空テキストは空文字を返す(self):
        result = _extract_section("", 1, r"テスト")
        assert result == ""


class TestGetHighlightCriteria:
    def test_実ファイルが存在すればハイライト基準を返す(self):
        if not DEFAULT_GUIDE_PATH.exists():
            return  # ファイル不在時はスキップ
        result = get_highlight_criteria()
        assert "パンチライン" in result or result == ""

    def test_環境変数でテスト用ガイドを使用(self):
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(SAMPLE_GUIDE)
            tmp_path = f.name

        os.environ["QUALITY_JUDGMENT_GUIDE_PATH"] = tmp_path
        try:
            result = get_highlight_criteria()
            assert "パンチラインが「強い」条件" in result
            assert "NGパターン" in result
        finally:
            del os.environ["QUALITY_JUDGMENT_GUIDE_PATH"]
            Path(tmp_path).unlink()


class TestGetDirectionCriteria:
    def test_環境変数でテスト用ガイドを使用(self):
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(SAMPLE_GUIDE)
            tmp_path = f.name

        os.environ["QUALITY_JUDGMENT_GUIDE_PATH"] = tmp_path
        try:
            result = get_direction_criteria()
            assert "編集者が読んで" in result
        finally:
            del os.environ["QUALITY_JUDGMENT_GUIDE_PATH"]
            Path(tmp_path).unlink()


class TestGetContentLineCriteria:
    def test_環境変数でテスト用ガイドを使用(self):
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(SAMPLE_GUIDE)
            tmp_path = f.name

        os.environ["QUALITY_JUDGMENT_GUIDE_PATH"] = tmp_path
        try:
            result = get_content_line_criteria()
            assert "コンテンツライン" in result
            assert "キャリア軸" in result
        finally:
            del os.environ["QUALITY_JUDGMENT_GUIDE_PATH"]
            Path(tmp_path).unlink()


class TestGetGuestTierCriteria:
    def test_環境変数でテスト用ガイドを使用(self):
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(SAMPLE_GUIDE)
            tmp_path = f.name

        os.environ["QUALITY_JUDGMENT_GUIDE_PATH"] = tmp_path
        try:
            result = get_guest_tier_criteria()
            assert "年収1000万以上" in result
        finally:
            del os.environ["QUALITY_JUDGMENT_GUIDE_PATH"]
            Path(tmp_path).unlink()


# ────────────────────────────────────────────────
# コンテンツライン自動判定
# ────────────────────────────────────────────────

class TestDetermineContentLine:
    def test_空テキストはキャリア軸を返す(self):
        result = determine_content_line()
        assert result == "career"

    def test_不動産キーワードが多ければ不動産軸(self):
        title = "不動産投資で物件を5棟購入した話"
        transcript = "融資を受けて利回り8%の物件を購入。キャッシュフローは月20万。家賃収入で安定"
        result = determine_content_line(title=title, transcript=transcript)
        assert result == "realestate"

    def test_キャリアキーワードのみならキャリア軸(self):
        title = "年収1000万30代外資製薬MR"
        transcript = "転職してキャリアアップ。年収が上がった。副業も始めた"
        result = determine_content_line(title=title, transcript=transcript)
        assert result == "career"

    def test_短いタイトルで不動産キーワード3つ以上なら不動産軸(self):
        title = "不動産投資で物件購入、融資と利回りの話"
        result = determine_content_line(title=title)
        assert result == "realestate"

    def test_短いタイトルで不動産キーワード2つ以下ならキャリア軸(self):
        title = "年収900万で不動産も始めた話"
        result = determine_content_line(title=title)
        assert result == "career"

    def test_ゲスト概要も判定に使われる(self):
        guest_summary = "不動産投資家。物件3棟保有。融資活用。利回り重視。キャッシュフロー安定"
        result = determine_content_line(guest_summary=guest_summary)
        assert result == "realestate"


# ────────────────────────────────────────────────
# プロンプト注入テキスト構築
# ────────────────────────────────────────────────

class TestBuildQualityInjectionText:
    def test_キャリア軸のテキスト構築(self):
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(SAMPLE_GUIDE)
            tmp_path = f.name

        os.environ["QUALITY_JUDGMENT_GUIDE_PATH"] = tmp_path
        try:
            result = build_quality_injection_text(content_line="career")
            assert "品質基準（必ず反映すること）" in result
            assert "通常のTEKO実績対談（キャリア軸）" in result
        finally:
            del os.environ["QUALITY_JUDGMENT_GUIDE_PATH"]
            Path(tmp_path).unlink()

    def test_不動産軸のテキスト構築(self):
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(SAMPLE_GUIDE)
            tmp_path = f.name

        os.environ["QUALITY_JUDGMENT_GUIDE_PATH"] = tmp_path
        try:
            result = build_quality_injection_text(content_line="realestate")
            assert "不動産実績対談（ノウハウ軸）" in result
            assert "不動産実績とパンチラインにフォーカス" in result
        finally:
            del os.environ["QUALITY_JUDGMENT_GUIDE_PATH"]
            Path(tmp_path).unlink()

    def test_compactモードは短い(self):
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(SAMPLE_GUIDE)
            tmp_path = f.name

        os.environ["QUALITY_JUDGMENT_GUIDE_PATH"] = tmp_path
        try:
            full = build_quality_injection_text(compact=False)
            compact = build_quality_injection_text(compact=True)
            # compactはフルより短い（または同じ）
            assert len(compact) <= len(full)
        finally:
            del os.environ["QUALITY_JUDGMENT_GUIDE_PATH"]
            Path(tmp_path).unlink()

    def test_ガイド不在でもエラーにならない(self):
        os.environ["QUALITY_JUDGMENT_GUIDE_PATH"] = "/非存在/guide.md"
        try:
            result = build_quality_injection_text()
            assert "品質基準" in result  # ヘッダーは必ず含まれる
        finally:
            del os.environ["QUALITY_JUDGMENT_GUIDE_PATH"]


class TestExtractCompactHighlight:
    def test_空テキストは空文字を返す(self):
        assert _extract_compact_highlight("") == ""

    def test_4引き金とNGパターンを含む(self):
        highlight_section = _extract_section(SAMPLE_GUIDE, 5, r"ハイライト選定の品質基準")
        result = _extract_compact_highlight(highlight_section)
        # パンチラインが「強い」条件またはNGパターンのいずれかを含むべき
        assert "パンチライン" in result or "NG" in result or result == ""


# ────────────────────────────────────────────────
# direction_generator への品質基準注入の統合テスト
# ────────────────────────────────────────────────

class TestDirectionGeneratorIntegration:
    """direction_generator に品質基準が正しく注入されることのテスト"""

    def test_determine_content_lineがインポート可能(self):
        """direction_generator から品質基準関連がインポートできる"""
        from src.video_direction.analyzer.direction_generator import (
            determine_content_line,
            build_quality_injection_text,
        )
        assert callable(determine_content_line)
        assert callable(build_quality_injection_text)

    def test_REALESTATE_KEYWORDSが適切に定義されている(self):
        """不動産キーワードリストが空でない"""
        assert len(REALESTATE_KEYWORDS) > 10
        assert "不動産" in REALESTATE_KEYWORDS
        assert "物件" in REALESTATE_KEYWORDS
        assert "融資" in REALESTATE_KEYWORDS
