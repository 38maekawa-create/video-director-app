"""sheets_manager のヘルパー関数ユニットテスト（gspread不要）"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.integrations.sheets_manager import (
    _normalize_name,
    _to_hiragana,
    _to_katakana,
    _is_partial_match,
    _match_guest_name,
    _extract_names_from_title,
)


# ────────────────────────────────────────────────
# _normalize_name
# ────────────────────────────────────────────────

class TestNormalizeName:
    def test_空文字は空文字を返す(self):
        assert _normalize_name("") == ""

    def test_Noneは空文字を返す(self):
        assert _normalize_name(None) == ""

    def test_敬称さんを除去する(self):
        assert "さん" not in _normalize_name("田中さん")

    def test_敬称氏を除去する(self):
        assert "氏" not in _normalize_name("田中氏")

    def test_括弧内を除去する(self):
        result = _normalize_name("ゲスト氏（里芋、トーマス）")
        assert "里芋" not in result
        assert "トーマス" not in result

    def test_全角英数を半角に変換して小文字化(self):
        # NFKC正規化後に lower()
        result = _normalize_name("Ｉｚｕ")
        assert result == "izu"

    def test_スペースとアンダースコアを除去(self):
        result = _normalize_name("izu san")
        assert " " not in result

    def test_ゲスト接頭語を除去(self):
        result = _normalize_name("ゲストりょうすけ")
        assert "ゲスト" not in result

    def test_撮影接頭語を除去(self):
        result = _normalize_name("撮影_りょうすけ")
        assert "撮影" not in result


# ────────────────────────────────────────────────
# _to_hiragana / _to_katakana
# ────────────────────────────────────────────────

class TestKanaConversion:
    def test_カタカナをひらがなに変換(self):
        assert _to_hiragana("イズ") == "いず"

    def test_ひらがなをカタカナに変換(self):
        assert _to_katakana("いず") == "イズ"

    def test_往復変換が恒等写像(self):
        original = "テスト"
        assert _to_katakana(_to_hiragana(original)) == original

    def test_ASCII文字はそのまま(self):
        assert _to_hiragana("abc") == "abc"
        assert _to_katakana("abc") == "abc"

    def test_混合テキスト(self):
        # ひらがな部分のみ変換される
        result = _to_katakana("いzu")
        assert result[0] == "イ"
        assert result[1] == "z"


# ────────────────────────────────────────────────
# _is_partial_match
# ────────────────────────────────────────────────

class TestIsPartialMatch:
    def test_完全一致はTrue(self):
        assert _is_partial_match("izu", "izu") is True

    def test_包含関係はTrue(self):
        assert _is_partial_match("izu", "izuさん") is True

    def test_空文字はFalse(self):
        assert _is_partial_match("", "izu") is False
        assert _is_partial_match("izu", "") is False

    def test_全く異なるはFalse(self):
        assert _is_partial_match("izu", "ryosuke") is False

    def test_日本語2文字以上でマッチ(self):
        # ひらがな2文字以上は部分一致が許可される
        assert _is_partial_match("いず", "いずさんのタイトル") is True

    def test_英字3文字未満はFalse(self):
        # 英数字は3文字未満のmin_lenチェックが入る
        # 2文字のASCIIは min_len=3 なのでFalse
        assert _is_partial_match("ab", "abcdef") is False


# ────────────────────────────────────────────────
# _extract_names_from_title
# ────────────────────────────────────────────────

class TestExtractNamesFromTitle:
    def test_INT番号形式から名前を抽出(self):
        names = _extract_names_from_title("INT001_ブンさん：説明")
        normalized = [n.lower() for n in names]
        assert any("ブン" in n or "ぶん" in n.lower() or "ぶん" in n for n in names) or any("ぶん" in n for n in names) or any("ブン" in n for n in names)

    def test_番号ドット形式から名前を抽出(self):
        names = _extract_names_from_title("53.izuさん：30代...")
        assert any("izu" in n.lower() for n in names)

    def test_括弧内の別名も候補に含まれる(self):
        names = _extract_names_from_title("ゲスト氏（里芋、トーマス）")
        assert any("里芋" in n for n in names)
        assert any("トーマス" in n for n in names)

    def test_空文字は空リストを返す(self):
        names = _extract_names_from_title("")
        assert names == []


# ────────────────────────────────────────────────
# _match_guest_name
# ────────────────────────────────────────────────

class TestMatchGuestName:
    def test_完全一致でマッチする(self):
        assert _match_guest_name("izu", "INT015_Izuさん：説明") is True

    def test_ひらがなカタカナ変換後にマッチする(self):
        # "ハオ" vs "ハオさん" のように表記揺れがある場合
        assert _match_guest_name("ハオ", "INT020_ハオさん：30代") is True

    def test_全く異なる名前はFalseを返す(self):
        assert _match_guest_name("りょうすけ", "INT001_Izuさん") is False

    def test_空のゲスト名はFalseを返す(self):
        assert _match_guest_name("", "INT001_Izuさん") is False

    def test_空のタイトルはFalseを返す(self):
        assert _match_guest_name("izu", "") is False

    def test_番号ドット形式でマッチする(self):
        assert _match_guest_name("izu", "53.izuさん：30代...") is True

    def test_部分一致でマッチする(self):
        # "コテツ" という名前が "コテツさん：説明" にマッチ
        assert _match_guest_name("コテツ", "コテツさん：31歳製造業...") is True
