"""edit_diff_analyzer のユニットテスト"""

import pytest

from src.video_direction.analyzer.edit_diff_analyzer import (
    EditChange,
    EditDiffResult,
    analyze_description_diff,
    analyze_direction_diff,
    analyze_thumbnail_diff,
    analyze_title_diff,
)


class TestAnalyzeDirectionDiff:
    """ディレクションレポートのdiff分析テスト"""

    def test_no_changes(self):
        """同一テキストなら変更なし"""
        result = analyze_direction_diff("テスト内容", "テスト内容")
        assert result.total_changes == 0
        assert result.severity == "minor"
        assert result.categories_affected == []

    def test_simple_modification(self):
        """単純な変更を検出する"""
        original = "冒頭のテロップは大きめに表示"
        edited = "冒頭のテロップは小さめに表示"
        result = analyze_direction_diff(original, edited)
        assert result.total_changes >= 1
        assert any(c.change_type == "modified" for c in result.changes)

    def test_addition(self):
        """行の追加を検出する"""
        original = "セクション1\nセクション2"
        edited = "セクション1\nセクション2\nセクション3を追加"
        result = analyze_direction_diff(original, edited)
        assert result.total_changes >= 1
        assert any(c.change_type == "added" for c in result.changes)

    def test_deletion(self):
        """行の削除を検出する"""
        original = "セクション1\nセクション2\nセクション3"
        edited = "セクション1\nセクション3"
        result = analyze_direction_diff(original, edited)
        assert result.total_changes >= 1
        assert any(c.change_type == "removed" for c in result.changes)

    def test_telop_category(self):
        """テロップ関連のキーワードでカテゴリ分類される"""
        original = "ここにテキスト"
        edited = "ここにテロップを追加する"
        result = analyze_direction_diff(original, edited)
        assert "telop" in result.categories_affected

    def test_bgm_category(self):
        """BGM関連のキーワードでカテゴリ分類される"""
        original = "このシーンは静かに"
        edited = "このシーンはBGMを追加して盛り上げる"
        result = analyze_direction_diff(original, edited)
        assert "bgm" in result.categories_affected

    def test_structure_category_triggers_major(self):
        """構成変更はmajor severityになる"""
        original = "冒頭パートの構成\n中盤の流れ"
        edited = "冒頭パートの構成を全面変更\n中盤の流れも再編"
        result = analyze_direction_diff(original, edited)
        assert result.severity == "major"

    def test_multiple_changes(self):
        """複数の変更を正しくカウントする"""
        original = "行1\n行2\n行3\n行4\n行5"
        edited = "行1変更\n行2\n新行\n行4変更\n行5"
        result = analyze_direction_diff(original, edited)
        assert result.total_changes >= 2

    def test_learning_signal_generated(self):
        """learning_signalが生成される"""
        result = analyze_direction_diff("元", "変更後")
        assert result.learning_signal
        assert "変更なし" not in result.learning_signal

    def test_empty_original(self):
        """空のオリジナルからの変更"""
        result = analyze_direction_diff("", "新しいコンテンツ")
        assert result.total_changes >= 1

    def test_empty_edited(self):
        """空への変更（全削除）"""
        result = analyze_direction_diff("元のコンテンツ", "")
        assert result.total_changes >= 1
        assert any(c.change_type == "removed" for c in result.changes)


class TestAnalyzeTitleDiff:
    """タイトルのdiff分析テスト"""

    def test_no_changes(self):
        """同一タイトルなら変更なし"""
        result = analyze_title_diff("テストタイトル", "テストタイトル")
        assert result.total_changes == 0
        assert result.severity == "minor"

    def test_title_change(self):
        """タイトル変更を検出する"""
        result = analyze_title_diff("元のタイトル", "新しいタイトル")
        assert result.total_changes == 1
        assert result.changes[0].category == "hook"
        assert result.changes[0].change_type == "modified"

    def test_whitespace_only(self):
        """空白のみの違いは変更なしとする"""
        result = analyze_title_diff("タイトル ", "タイトル")
        assert result.total_changes == 0


class TestAnalyzeDescriptionDiff:
    """概要欄のdiff分析テスト"""

    def test_no_changes(self):
        result = analyze_description_diff("概要テキスト", "概要テキスト")
        assert result.total_changes == 0

    def test_description_modification(self):
        original = "チャンネル登録お願いします\nリンクはこちら"
        edited = "チャンネル登録よろしく！\nリンクはこちら\n概要欄にも情報追加"
        result = analyze_description_diff(original, edited)
        assert result.total_changes >= 1


class TestAnalyzeThumbnailDiff:
    """サムネイル指示のdiff分析テスト"""

    def test_no_changes(self):
        result = analyze_thumbnail_diff("サムネ指示", "サムネ指示")
        assert result.total_changes == 0

    def test_thumbnail_change_is_hook(self):
        """サムネイル変更はhookカテゴリになる"""
        result = analyze_thumbnail_diff("元の指示", "新しい指示に変更")
        # direction（デフォルト）はhookに上書きされる
        for c in result.changes:
            assert c.category == "hook"

    def test_thumbnail_with_color_keyword(self):
        """カラー関連キーワードがあればcolorカテゴリ"""
        result = analyze_thumbnail_diff(
            "背景を白に",
            "背景のカラーを青に変更、彩度を上げる"
        )
        assert "color" in result.categories_affected


class TestSeverityLogic:
    """severity判定のテスト"""

    def test_minor_severity(self):
        """1件の軽微な変更はminor"""
        result = analyze_description_diff("テスト", "テスト変更")
        assert result.severity == "minor"

    def test_major_with_many_changes(self):
        """5件以上の変更はmajor"""
        # 変更が複数ブロックに分かれるようにする
        original = "行0\n固定1\n行2\n固定3\n行4\n固定5\n行6\n固定7\n行8\n固定9"
        edited = "変更0\n固定1\n変更2\n固定3\n変更4\n固定5\n変更6\n固定7\n変更8\n固定9"
        result = analyze_direction_diff(original, edited)
        assert result.severity == "major"


class TestEditDiffResultStructure:
    """EditDiffResultの構造テスト"""

    def test_dataclass_fields(self):
        """全フィールドが存在する"""
        result = analyze_direction_diff("a", "b")
        assert hasattr(result, "total_changes")
        assert hasattr(result, "changes")
        assert hasattr(result, "categories_affected")
        assert hasattr(result, "severity")
        assert hasattr(result, "learning_signal")

    def test_changes_are_edit_change(self):
        """changesの各要素がEditChangeである"""
        result = analyze_direction_diff("元", "変更")
        for c in result.changes:
            assert isinstance(c, EditChange)
            assert c.change_type in ("added", "removed", "modified")
            assert c.category in (
                "direction", "telop", "bgm", "color",
                "structure", "tone", "hook", "attribute",
            )
