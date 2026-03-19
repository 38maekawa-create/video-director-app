"""editing_feedback_converter のユニットテスト

ハイライト系FB変換、演出系FB変換、ゲスト情報の取得、
カテゴリに応じた品質基準セクション選択を検証する。
LLM呼び出しはモックで代替する。
"""
import json
import sys
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch, MagicMock

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.tracker.editing_feedback_converter import (
    classify_editing_feedback,
    _get_quality_criteria,
    _get_guest_context,
    _build_conversion_prompt,
    _fallback_conversion,
    convert_editing_feedback,
    ConvertedEditingFeedback,
    CATEGORY_SECTION_MAP,
    CATEGORY_KEYWORDS,
)

# モック対象のモジュールパス
_LOADER_MOD = "src.video_direction.knowledge.quality_knowledge_loader"
_MEMBER_MOD = "src.video_direction.integrations.member_master.MemberMaster"
_LLM_MOD = "teko_core.llm.ask"


class TestClassifyEditingFeedback(unittest.TestCase):
    """カテゴリ自動分類のテスト"""

    def test_highlight_category_basic(self):
        """ハイライト系のFBがhighlightに分類される"""
        self.assertEqual(
            classify_editing_feedback("冒頭のハイライト、センスなさすぎ"),
            "highlight",
        )

    def test_highlight_category_punchline(self):
        """パンチライン系のFBがhighlightに分類される"""
        self.assertEqual(
            classify_editing_feedback("パンチラインが弱い、もっと引きのある場面を選んで"),
            "highlight",
        )

    def test_highlight_opening(self):
        """冒頭・オープニング系のFBがhighlightに分類される"""
        self.assertEqual(
            classify_editing_feedback("最初の掴みが弱い、もっとインパクトある出だしにして"),
            "highlight",
        )

    def test_direction_category_tempo(self):
        """テンポ・演出系のFBがdirectionに分類される"""
        self.assertEqual(
            classify_editing_feedback("テンポが悪い、もっとリズムよくカットして"),
            "direction",
        )

    def test_direction_category_cut(self):
        """カット系のFBがdirectionに分類される"""
        self.assertEqual(
            classify_editing_feedback("ここの繋ぎがおかしい、場面転換がぎこちない"),
            "direction",
        )

    def test_direction_category_bgm(self):
        """BGM系のFBがdirectionに分類される"""
        result = classify_editing_feedback("BGMの音量でかすぎ、もっと下げて")
        self.assertEqual(result, "direction")

    def test_telop_category(self):
        """テロップ系のFBがtelopに分類される"""
        self.assertEqual(
            classify_editing_feedback("テロップが読みにくい、フォントもっとデカくして"),
            "telop",
        )

    def test_telop_category_color(self):
        """テロップ色系のFBがtelopに分類される"""
        self.assertEqual(
            classify_editing_feedback("字幕の文字色が見にくい、もっと目立つ色にして"),
            "telop",
        )

    def test_general_category(self):
        """特定カテゴリに該当しないFBがgeneralに分類される"""
        self.assertEqual(
            classify_editing_feedback("なんか違う、やり直し"),
            "general",
        )

    def test_empty_feedback(self):
        """空のFBがgeneralに分類される"""
        self.assertEqual(classify_editing_feedback(""), "general")


class TestGetQualityCriteria(unittest.TestCase):
    """品質基準セクション選択のテスト"""

    @patch(f"{_LOADER_MOD}.get_highlight_criteria")
    def test_highlight_criteria(self, mock_loader):
        """highlightカテゴリでハイライト基準が取得される"""
        mock_loader.return_value = "ハイライト選定テスト基準テキスト"
        criteria, section_name = _get_quality_criteria("highlight")
        self.assertEqual(section_name, "ハイライト選定の品質基準")
        self.assertIn("ハイライト選定テスト基準テキスト", criteria)
        mock_loader.assert_called_once()

    @patch(f"{_LOADER_MOD}.get_direction_criteria")
    def test_direction_criteria(self, mock_loader):
        """directionカテゴリで演出基準が取得される"""
        mock_loader.return_value = "演出ディレクションテスト基準テキスト"
        criteria, section_name = _get_quality_criteria("direction")
        self.assertEqual(section_name, "演出ディレクションの品質基準")
        self.assertIn("演出ディレクションテスト基準テキスト", criteria)
        mock_loader.assert_called_once()

    @patch(f"{_LOADER_MOD}.get_direction_criteria")
    def test_telop_uses_direction_criteria(self, mock_loader):
        """telopカテゴリでも演出基準が取得される（テロップは演出の一部）"""
        mock_loader.return_value = "テロップ含む演出基準"
        criteria, section_name = _get_quality_criteria("telop")
        self.assertEqual(section_name, "テロップ品質基準")
        mock_loader.assert_called_once()

    @patch(f"{_LOADER_MOD}.load_quality_guide")
    def test_general_loads_full_guide(self, mock_loader):
        """generalカテゴリでガイド全文が取得される"""
        mock_loader.return_value = "品質判断ガイド全文"
        criteria, section_name = _get_quality_criteria("general")
        self.assertEqual(section_name, "品質判断ガイド全般")
        mock_loader.assert_called_once()

    @patch(f"{_LOADER_MOD}.load_quality_guide")
    def test_unknown_category_fallback(self, mock_loader):
        """不明なカテゴリはgeneralにフォールバック"""
        mock_loader.return_value = "ガイド全文"
        criteria, section_name = _get_quality_criteria("unknown_category")
        self.assertEqual(section_name, "品質判断ガイド全般")

    @patch(f"{_LOADER_MOD}.get_highlight_criteria")
    def test_long_criteria_truncated(self, mock_loader):
        """3000文字を超える品質基準は切り詰められる"""
        mock_loader.return_value = "あ" * 5000
        criteria, _ = _get_quality_criteria("highlight")
        self.assertTrue(len(criteria) < 5000)
        self.assertIn("以下省略", criteria)


class TestGetGuestContext(unittest.TestCase):
    """ゲスト情報取得のテスト"""

    @patch(_MEMBER_MOD)
    def test_guest_found_with_profile(self, MockMaster):
        """ゲストが見つかりプロファイルファイルがある場合"""
        mock_instance = MockMaster.return_value
        mock_member = MagicMock()
        mock_member.canonical_name = "メンイチ"
        mock_instance.find_member.return_value = mock_member
        mock_instance.get_people_profile.return_value = "年収2000万、不動産3棟保有"

        context = _get_guest_context("メンイチ")
        self.assertIn("メンイチ", context)
        self.assertIn("年収2000万", context)

    @patch(_MEMBER_MOD)
    def test_guest_found_no_profile(self, MockMaster):
        """ゲストが見つかるがプロファイルファイルがない場合"""
        mock_instance = MockMaster.return_value
        mock_member = MagicMock()
        mock_member.canonical_name = "テストゲスト"
        mock_instance.find_member.return_value = mock_member
        mock_instance.get_people_profile.return_value = ""

        context = _get_guest_context("テストゲスト")
        self.assertIn("テストゲスト", context)
        self.assertIn("詳細プロファイルなし", context)

    @patch(_MEMBER_MOD)
    def test_guest_not_found(self, MockMaster):
        """ゲストが見つからない場合"""
        mock_instance = MockMaster.return_value
        mock_instance.find_member.return_value = None

        context = _get_guest_context("存在しないゲスト")
        self.assertEqual(context, "")

    @patch(_MEMBER_MOD, side_effect=Exception("ファイルが見つかりません"))
    def test_guest_context_exception_handling(self, _):
        """MemberMasterの読み込み失敗時は空文字を返す"""
        context = _get_guest_context("エラーゲスト")
        self.assertEqual(context, "")

    @patch(_MEMBER_MOD)
    def test_long_profile_truncated(self, MockMaster):
        """長すぎるプロファイルは切り詰められる"""
        mock_instance = MockMaster.return_value
        mock_member = MagicMock()
        mock_member.canonical_name = "長文ゲスト"
        mock_instance.find_member.return_value = mock_member
        mock_instance.get_people_profile.return_value = "テスト" * 1000

        context = _get_guest_context("長文ゲスト")
        self.assertIn("以下省略", context)
        self.assertTrue(len(context) < 3000)


class TestBuildConversionPrompt(unittest.TestCase):
    """プロンプト構築のテスト"""

    def test_prompt_contains_feedback(self):
        """プロンプトに元のFBが含まれる"""
        system, user = _build_conversion_prompt(
            "ハイライトがダサい", "highlight", "品質基準テキスト", "ゲスト情報"
        )
        self.assertIn("ハイライトがダサい", user)
        self.assertIn("映像編集のディレクター", system)

    def test_prompt_contains_criteria(self):
        """プロンプトに品質基準が含まれる"""
        _, user = _build_conversion_prompt(
            "テンポ悪い", "direction", "演出ディレクション基準テキスト", ""
        )
        self.assertIn("演出ディレクション基準テキスト", user)

    def test_prompt_contains_guest_context(self):
        """プロンプトにゲスト情報が含まれる"""
        _, user = _build_conversion_prompt(
            "FB", "highlight", "基準", "メンイチ: 年収2000万"
        )
        self.assertIn("メンイチ: 年収2000万", user)

    def test_prompt_handles_empty_guest(self):
        """ゲスト情報が空の場合も正常にプロンプトが生成される"""
        _, user = _build_conversion_prompt(
            "FB", "highlight", "基準", ""
        )
        self.assertIn("ゲスト情報なし", user)

    def test_prompt_json_output_format(self):
        """プロンプトにJSON出力形式の指示が含まれる"""
        _, user = _build_conversion_prompt("FB", "highlight", "基準", "")
        self.assertIn("converted_instruction", user)
        self.assertIn("suggestions", user)
        self.assertIn("confidence", user)


class TestFallbackConversion(unittest.TestCase):
    """フォールバック変換のテスト"""

    def test_highlight_fallback(self):
        """ハイライト系フォールバック"""
        result = _fallback_conversion("ハイライトダサい", "highlight")
        self.assertIn("ハイライト修正指示", result)
        self.assertIn("ハイライトダサい", result)
        self.assertIn("パンチライン", result)

    def test_direction_fallback(self):
        """演出系フォールバック"""
        result = _fallback_conversion("テンポ悪い", "direction")
        self.assertIn("演出修正指示", result)
        self.assertIn("テンポ悪い", result)

    def test_telop_fallback(self):
        """テロップ系フォールバック"""
        result = _fallback_conversion("文字が見にくい", "telop")
        self.assertIn("テロップ修正指示", result)
        self.assertIn("文字が見にくい", result)

    def test_general_fallback(self):
        """一般フォールバック"""
        result = _fallback_conversion("なんか違う", "general")
        self.assertIn("品質修正指示", result)

    def test_unknown_category_fallback(self):
        """不明カテゴリはgeneralにフォールバック"""
        result = _fallback_conversion("不明", "unknown")
        self.assertIn("品質修正指示", result)


class TestConvertEditingFeedback(unittest.TestCase):
    """convert_editing_feedback 統合テスト（LLMモック）"""

    @patch(_LLM_MOD)
    @patch("src.video_direction.tracker.editing_feedback_converter._get_guest_context")
    @patch("src.video_direction.tracker.editing_feedback_converter._get_quality_criteria")
    def test_highlight_conversion_with_menichi(self, mock_criteria, mock_guest, mock_ask):
        """メンイチのハイライト系FB変換（LLMモック）"""
        mock_criteria.return_value = ("ハイライト品質基準テキスト", "ハイライト選定の品質基準")
        mock_guest.return_value = "【ゲスト: メンイチ】年収2000万、不動産3棟保有"
        mock_ask.return_value = json.dumps({
            "converted_instruction": "冒頭0:00-0:15のハイライトを差し替え。メンイチの年収2000万→3棟保有の実績を畳みかけるカットに変更。",
            "reason": "現在のハイライトはパンチラインの「引きの強い事実の畳みかけ」が不足している",
            "suggestions": [
                "年収実績→物件規模→キャッシュフローの3段階で畳みかける",
                "「サラリーマンから年収2000万」のギャップを冒頭に持ってくる",
                "メンイチの具体的な数字（3棟、CF月50万等）を冒頭テロップで一気に見せる",
            ],
            "confidence": 0.85,
        })

        result = convert_editing_feedback(
            raw_feedback="冒頭のハイライト、センスなさすぎ",
            guest_name="メンイチ",
            feedback_category="highlight",
        )

        self.assertIsInstance(result, ConvertedEditingFeedback)
        self.assertEqual(result.category, "highlight")
        self.assertEqual(result.guest_name, "メンイチ")
        self.assertIn("冒頭0:00-0:15", result.converted_instruction)
        self.assertEqual(result.quality_criteria_used, "ハイライト選定の品質基準")
        self.assertIn("メンイチ", result.guest_context)
        self.assertEqual(len(result.suggestions), 3)
        self.assertAlmostEqual(result.confidence, 0.85, places=2)
        self.assertEqual(result.original_feedback, "冒頭のハイライト、センスなさすぎ")

    @patch(_LLM_MOD)
    @patch("src.video_direction.tracker.editing_feedback_converter._get_guest_context")
    @patch("src.video_direction.tracker.editing_feedback_converter._get_quality_criteria")
    def test_direction_conversion(self, mock_criteria, mock_guest, mock_ask):
        """演出系FB変換（LLMモック）"""
        mock_criteria.return_value = ("演出基準テキスト", "演出ディレクションの品質基準")
        mock_guest.return_value = ""
        mock_ask.return_value = json.dumps({
            "converted_instruction": "中盤のインタビューパート（5:00-10:00）のテンポを改善。回答が長い箇所をカットして間を詰める。",
            "reason": "テンポが遅い部分が視聴離脱を招いている",
            "suggestions": [
                "5:30-6:00の回答を30秒にカット",
                "7:00-8:00の同じ話題の繰り返しを削除",
            ],
            "confidence": 0.75,
        })

        result = convert_editing_feedback(
            raw_feedback="中盤のテンポが悪い、もっとサクサク進めて",
            guest_name="テストゲスト",
            feedback_category="direction",
        )

        self.assertEqual(result.category, "direction")
        self.assertIn("テンポを改善", result.converted_instruction)
        self.assertEqual(result.quality_criteria_used, "演出ディレクションの品質基準")

    @patch(_LLM_MOD)
    @patch("src.video_direction.tracker.editing_feedback_converter._get_guest_context")
    @patch("src.video_direction.tracker.editing_feedback_converter._get_quality_criteria")
    def test_auto_category_detection(self, mock_criteria, mock_guest, mock_ask):
        """カテゴリ未指定時の自動推定"""
        mock_criteria.return_value = ("基準", "ハイライト選定の品質基準")
        mock_guest.return_value = ""
        mock_ask.return_value = json.dumps({
            "converted_instruction": "ハイライト修正指示",
            "suggestions": [],
            "confidence": 0.7,
        })

        result = convert_editing_feedback(
            raw_feedback="冒頭のパンチラインが弱い",
            guest_name="テスト",
            feedback_category=None,  # 自動推定
        )

        self.assertEqual(result.category, "highlight")

    @patch("src.video_direction.tracker.editing_feedback_converter._get_guest_context")
    @patch("src.video_direction.tracker.editing_feedback_converter._get_quality_criteria")
    def test_llm_failure_fallback(self, mock_criteria, mock_guest):
        """LLM呼び出し失敗時のフォールバック"""
        mock_criteria.return_value = ("基準", "ハイライト選定の品質基準")
        mock_guest.return_value = ""

        with patch(
            _LLM_MOD,
            side_effect=Exception("LLM呼び出しエラー"),
        ):
            result = convert_editing_feedback(
                raw_feedback="ハイライトダサい",
                guest_name="テスト",
                feedback_category="highlight",
            )

        self.assertIn("ハイライト修正指示", result.converted_instruction)
        self.assertIn("ハイライトダサい", result.converted_instruction)
        self.assertEqual(result.confidence, 0.3)

    @patch(_LLM_MOD)
    @patch("src.video_direction.tracker.editing_feedback_converter._get_guest_context")
    @patch("src.video_direction.tracker.editing_feedback_converter._get_quality_criteria")
    def test_llm_returns_non_json(self, mock_criteria, mock_guest, mock_ask):
        """LLMがJSON以外を返した場合"""
        mock_criteria.return_value = ("基準", "ハイライト選定の品質基準")
        mock_guest.return_value = ""
        mock_ask.return_value = "JSONではないただのテキストレスポンス"

        result = convert_editing_feedback(
            raw_feedback="テスト",
            guest_name="テスト",
            feedback_category="highlight",
        )

        # レスポンス全文が指示として使用される
        self.assertIn("JSONではないただのテキストレスポンス", result.converted_instruction)
        self.assertEqual(result.confidence, 0.5)

    def test_dataclass_serialization(self):
        """ConvertedEditingFeedbackのシリアライゼーション"""
        fb = ConvertedEditingFeedback(
            original_feedback="テストFB",
            category="highlight",
            guest_name="テストゲスト",
            converted_instruction="具体的な指示",
            quality_criteria_used="ハイライト選定の品質基準",
            guest_context="ゲスト情報",
            suggestions=["案1", "案2"],
            confidence=0.8,
        )
        d = asdict(fb)
        self.assertEqual(d["original_feedback"], "テストFB")
        self.assertEqual(d["category"], "highlight")
        self.assertEqual(len(d["suggestions"]), 2)
        self.assertAlmostEqual(d["confidence"], 0.8)

    @patch(_LLM_MOD)
    @patch("src.video_direction.tracker.editing_feedback_converter._get_guest_context")
    @patch("src.video_direction.tracker.editing_feedback_converter._get_quality_criteria")
    def test_reason_appended_to_instruction(self, mock_criteria, mock_guest, mock_ask):
        """reasonフィールドがinstructionに付加される"""
        mock_criteria.return_value = ("基準", "基準名")
        mock_guest.return_value = ""
        mock_ask.return_value = json.dumps({
            "converted_instruction": "具体的な編集指示",
            "reason": "NGパターンに該当している",
            "suggestions": [],
            "confidence": 0.8,
        })

        result = convert_editing_feedback(
            raw_feedback="テスト",
            guest_name="テスト",
            feedback_category="highlight",
        )

        self.assertIn("修正理由", result.converted_instruction)
        self.assertIn("NGパターンに該当", result.converted_instruction)


class TestCategorySectionMap(unittest.TestCase):
    """カテゴリとセクションマッピングのテスト"""

    def test_all_categories_have_mapping(self):
        """全カテゴリにマッピングが定義されている"""
        for cat in ["highlight", "direction", "telop", "general"]:
            self.assertIn(cat, CATEGORY_SECTION_MAP)
            self.assertIn("section_name", CATEGORY_SECTION_MAP[cat])
            self.assertIn("loader_func", CATEGORY_SECTION_MAP[cat])
            self.assertIn("description", CATEGORY_SECTION_MAP[cat])

    def test_all_categories_have_keywords(self):
        """highlight/direction/telopにキーワードが定義されている"""
        for cat in ["highlight", "direction", "telop"]:
            self.assertIn(cat, CATEGORY_KEYWORDS)
            self.assertTrue(len(CATEGORY_KEYWORDS[cat]) > 0)


if __name__ == "__main__":
    unittest.main()
