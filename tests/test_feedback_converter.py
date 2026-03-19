"""FB変換プロンプトのユニットテスト

カテゴリ分類、プロンプト構築、サンプル変換の品質検証。
LLM呼び出しは行わず、プロンプト構築ロジックとカテゴリ推定を検証する。
"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.analyzer.feedback_converter import (
    CATEGORY_TEMPLATES,
    CATEGORY_KEYWORDS,
    SAMPLE_CONVERSIONS,
    classify_feedback_category,
    build_system_prompt,
    build_conversion_prompt,
)


class TestCategoryClassification(unittest.TestCase):
    """カテゴリ自動分類のテスト"""

    def test_color_category(self):
        """色・明るさ系のFBがcolorに分類される"""
        self.assertEqual(classify_feedback_category("ここもうちょっと明るくして"), "color")

    def test_color_category_dark(self):
        """暗い系のFBがcolorに分類される"""
        self.assertEqual(classify_feedback_category("顔が暗いからもっと明るくして"), "color")

    def test_cutting_category(self):
        """カット系のFBがcuttingに分類される"""
        self.assertEqual(classify_feedback_category("ここの繋ぎがおかしい"), "cutting")

    def test_cutting_category_delete(self):
        """削除系のFBがcuttingに分類される"""
        self.assertEqual(classify_feedback_category("このシーンいらないからカットして"), "cutting")

    def test_telop_category(self):
        """テロップ系のFBがtelopに分類される"""
        self.assertEqual(classify_feedback_category("テロップ読みにくいわ"), "telop")

    def test_telop_category_font(self):
        """フォント系のFBがtelopに分類される"""
        self.assertEqual(classify_feedback_category("フォント変えて、もっとデカく"), "telop")

    def test_bgm_category(self):
        """BGM系のFBがbgmに分類される"""
        self.assertEqual(classify_feedback_category("BGMうるさくて声が聞こえない"), "bgm")

    def test_bgm_category_sound(self):
        """効果音系のFBがbgmに分類される"""
        self.assertEqual(classify_feedback_category("効果音つけてほしい"), "bgm")

    def test_camera_category(self):
        """カメラ系のFBがcameraに分類される"""
        self.assertEqual(classify_feedback_category("手ブレひどいなこのカット"), "camera")

    def test_camera_category_zoom(self):
        """ズーム系のFBがcameraに分類される"""
        self.assertEqual(classify_feedback_category("もっとズームしてアップにして"), "camera")

    def test_composition_category(self):
        """構図系のFBがcompositionに分類される"""
        self.assertEqual(classify_feedback_category("構図のバランスが悪い"), "composition")

    def test_tempo_category(self):
        """テンポ系のFBがtempoに分類される"""
        self.assertEqual(classify_feedback_category("テンポが悪い、だるい"), "tempo")

    def test_tempo_category_hook(self):
        """冒頭の掴み系のFBがtempoに分類される"""
        self.assertEqual(classify_feedback_category("冒頭の掴みが弱い"), "tempo")

    def test_general_category(self):
        """カテゴリ不明のFBがgeneralに分類される"""
        self.assertEqual(classify_feedback_category("いい感じにして"), "general")

    def test_empty_text(self):
        """空文字がgeneralに分類される"""
        self.assertEqual(classify_feedback_category(""), "general")


class TestSampleConversions(unittest.TestCase):
    """サンプル変換データのカテゴリ分類精度テスト"""

    def test_all_samples_correct_category(self):
        """全サンプルが期待されるカテゴリに分類される"""
        for sample in SAMPLE_CONVERSIONS:
            with self.subTest(input=sample["input"]):
                result = classify_feedback_category(sample["input"])
                self.assertEqual(
                    result,
                    sample["expected_category"],
                    f"入力: '{sample['input']}' → 期待: {sample['expected_category']}, 実際: {result}",
                )


class TestBuildSystemPrompt(unittest.TestCase):
    """システムプロンプト構築のテスト"""

    def test_system_prompt_with_category(self):
        """カテゴリ指定時に専門用語が含まれる"""
        prompt = build_system_prompt("color")
        self.assertIn("色温度", prompt)
        self.assertIn("露出補正", prompt)
        self.assertIn("スキントーン", prompt)
        self.assertIn("カラー・色調", prompt)

    def test_system_prompt_cutting(self):
        """cuttingカテゴリの専門用語が含まれる"""
        prompt = build_system_prompt("cutting")
        self.assertIn("Jカット", prompt)
        self.assertIn("ディゾルブ", prompt)
        self.assertIn("ジャンプカット", prompt)

    def test_system_prompt_telop(self):
        """telopカテゴリの専門用語が含まれる"""
        prompt = build_system_prompt("telop")
        self.assertIn("セーフエリア", prompt)
        self.assertIn("カーニング", prompt)
        self.assertIn("ドロップシャドウ", prompt)

    def test_system_prompt_bgm(self):
        """bgmカテゴリの専門用語が含まれる"""
        prompt = build_system_prompt("bgm")
        self.assertIn("ダッキング", prompt)
        self.assertIn("ラウドネス", prompt)
        self.assertIn("LUFS", prompt)

    def test_system_prompt_camera(self):
        """cameraカテゴリの専門用語が含まれる"""
        prompt = build_system_prompt("camera")
        self.assertIn("パン", prompt)
        self.assertIn("ワープスタビライザー", prompt)

    def test_system_prompt_composition(self):
        """compositionカテゴリの専門用語が含まれる"""
        prompt = build_system_prompt("composition")
        self.assertIn("三分割法", prompt)
        self.assertIn("ヘッドルーム", prompt)

    def test_system_prompt_tempo(self):
        """tempoカテゴリの専門用語が含まれる"""
        prompt = build_system_prompt("tempo")
        self.assertIn("フック", prompt)
        self.assertIn("ブリーザー", prompt)

    def test_system_prompt_without_category(self):
        """カテゴリなしの場合は全カテゴリ概要が含まれる"""
        prompt = build_system_prompt(None)
        self.assertIn("カット・編集", prompt)
        self.assertIn("カラー・色調", prompt)
        self.assertIn("テロップ・字幕", prompt)
        self.assertIn("BGM・音響", prompt)
        # カテゴリ固有の詳細用語は含まれない
        self.assertNotIn("Jカット", prompt)

    def test_system_prompt_general_category(self):
        """generalカテゴリの場合も全カテゴリ概要になる"""
        prompt = build_system_prompt("general")
        self.assertIn("カット・編集", prompt)
        self.assertIn("映像ディレクター", prompt)

    def test_system_prompt_base_content(self):
        """全プロンプトに基本原則が含まれる"""
        for cat in list(CATEGORY_TEMPLATES.keys()) + [None, "general"]:
            prompt = build_system_prompt(cat)
            self.assertIn("具体的な数値・技術用語を使う", prompt)
            self.assertIn("理由と意図を添える", prompt)
            self.assertIn("ポジティブなトーン", prompt)


class TestBuildConversionPrompt(unittest.TestCase):
    """ユーザープロンプト構築のテスト"""

    def test_prompt_contains_raw_text(self):
        """元のFBテキストがプロンプトに含まれる"""
        prompt = build_conversion_prompt("テロップ読みにくい")
        self.assertIn("テロップ読みにくい", prompt)

    def test_prompt_contains_json_format(self):
        """出力JSON形式の指定が含まれる"""
        prompt = build_conversion_prompt("テスト")
        self.assertIn("converted_text", prompt)
        self.assertIn("structured_items", prompt)
        self.assertIn("priority", prompt)
        self.assertIn("reason", prompt)

    def test_prompt_with_category_hint(self):
        """カテゴリ指定時にカテゴリ名がプロンプトに含まれる"""
        prompt = build_conversion_prompt("テスト", category="color")
        self.assertIn("カラー・色調", prompt)

    def test_prompt_auto_category_detection(self):
        """カテゴリ未指定時に自動検出される"""
        prompt = build_conversion_prompt("BGMの音量を調整して")
        self.assertIn("BGM・音響", prompt)

    def test_prompt_with_learning_rules(self):
        """学習ルールテキストがプロンプトに含まれる"""
        rules = "\n## 学習ルール:\n- テロップは常に白縁取り"
        prompt = build_conversion_prompt("テスト", learned_rules_text=rules)
        self.assertIn("学習ルール", prompt)
        self.assertIn("白縁取り", prompt)

    def test_prompt_with_tracking_refs(self):
        """トラッキング参照テキストがプロンプトに含まれる"""
        refs = "\n## 参考映像:\n- https://example.com/video1"
        prompt = build_conversion_prompt("テスト", tracking_refs_text=refs)
        self.assertIn("参考映像", prompt)
        self.assertIn("example.com", prompt)

    def test_prompt_conversion_guidelines(self):
        """変換注意事項が含まれる"""
        prompt = build_conversion_prompt("テスト")
        self.assertIn("口語表現をそのまま残さず", prompt)
        self.assertIn("曖昧表現", prompt)


class TestCategoryTemplatesCompleteness(unittest.TestCase):
    """カテゴリテンプレートの網羅性テスト"""

    REQUIRED_CATEGORIES = ["cutting", "color", "telop", "bgm", "camera", "composition", "tempo"]

    def test_all_categories_defined(self):
        """7カテゴリ全てがテンプレートに定義されている"""
        for cat in self.REQUIRED_CATEGORIES:
            self.assertIn(cat, CATEGORY_TEMPLATES, f"カテゴリ '{cat}' がテンプレートに未定義")

    def test_all_categories_have_keywords(self):
        """7カテゴリ全てがキーワードマッピングに定義されている"""
        for cat in self.REQUIRED_CATEGORIES:
            self.assertIn(cat, CATEGORY_KEYWORDS, f"カテゴリ '{cat}' がキーワードに未定義")

    def test_template_structure(self):
        """各テンプレートに必須フィールドが存在する"""
        for cat, tmpl in CATEGORY_TEMPLATES.items():
            with self.subTest(category=cat):
                self.assertIn("display_name", tmpl)
                self.assertIn("description", tmpl)
                self.assertIn("technical_terms", tmpl)
                self.assertIn("conversion_guide", tmpl)
                self.assertIsInstance(tmpl["technical_terms"], list)
                self.assertGreater(len(tmpl["technical_terms"]), 3, f"{cat}の専門用語が少なすぎる")

    def test_keywords_not_empty(self):
        """各カテゴリのキーワードが空でない"""
        for cat, words in CATEGORY_KEYWORDS.items():
            self.assertGreater(len(words), 3, f"{cat}のキーワードが少なすぎる")


class TestAPIEndpointConvertFeedback(unittest.TestCase):
    """/api/feedback/convert エンドポイントのテスト（LLMモック使用）"""

    def _get_test_client(self):
        """テスト用FastAPIクライアントを取得"""
        from fastapi.testclient import TestClient
        from src.video_direction.integrations.api_server import app
        return TestClient(app)

    def test_convert_fallback_no_llm(self):
        """LLM不使用時のフォールバックが正常に動作する"""
        client = self._get_test_client()
        # anthropic モジュールのインポートを失敗させる
        with patch.dict("sys.modules", {"anthropic": None}):
            resp = client.post("/api/feedback/convert", json={
                "raw_text": "BGMうるさい",
                "project_id": "test-project",
            })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("converted_text", data)
        self.assertIn("structured_items", data)
        self.assertIn("detected_category", data)
        self.assertEqual(data["detected_category"], "bgm")

    def test_convert_fallback_structured_items(self):
        """フォールバック時にstructured_itemsにreasonフィールドがある"""
        client = self._get_test_client()
        with patch.dict("sys.modules", {"anthropic": None}):
            resp = client.post("/api/feedback/convert", json={
                "raw_text": "テロップ読めない",
                "project_id": "test-project",
            })
        data = resp.json()
        self.assertGreaterEqual(len(data["structured_items"]), 1)
        item = data["structured_items"][0]
        self.assertIn("reason", item)
        self.assertIn("reference_url", item)

    def test_convert_enhanced_fallback(self):
        """強化版のフォールバックが正常に動作する"""
        client = self._get_test_client()
        with patch.dict("sys.modules", {"anthropic": None}):
            resp = client.post("/api/v1/feedback/convert-enhanced", json={
                "raw_text": "色がバラバラ",
                "project_id": "test-project",
                "use_learning_rules": False,
                "include_tracking_references": False,
            })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("detected_category", data)
        self.assertEqual(data["detected_category"], "color")
        self.assertIn("tracking_references", data)
        self.assertIn("learning_rules_applied", data)


class TestSampleConversionQuality(unittest.TestCase):
    """サンプルFBの変換品質テスト（プロンプト内容の検証）"""

    def test_color_prompt_contains_technical_terms(self):
        """色系FBのプロンプトに色の専門用語が含まれる"""
        prompt = build_conversion_prompt("ここもうちょっと明るくして")
        system = build_system_prompt("color")
        combined = system + prompt
        # 色系の専門用語が少なくとも3つ含まれるべき
        terms_found = [t for t in ["露出", "EV", "リフト", "スキントーン", "色温度", "LUT"]
                       if t in combined]
        self.assertGreaterEqual(len(terms_found), 3, f"専門用語が不足: {terms_found}")

    def test_tempo_prompt_contains_technical_terms(self):
        """テンポ系FBのプロンプトにテンポの専門用語が含まれる"""
        system = build_system_prompt("tempo")
        terms_found = [t for t in ["ジャンプカット", "ブリーザー", "フック", "BPM", "尺調整"]
                       if t in system]
        self.assertGreaterEqual(len(terms_found), 3, f"専門用語が不足: {terms_found}")

    def test_bgm_prompt_contains_technical_terms(self):
        """BGM系FBのプロンプトに音響の専門用語が含まれる"""
        system = build_system_prompt("bgm")
        terms_found = [t for t in ["ダッキング", "dB", "ラウドネス", "LUFS", "コンプレッサー"]
                       if t in system]
        self.assertGreaterEqual(len(terms_found), 3, f"専門用語が不足: {terms_found}")


if __name__ == "__main__":
    unittest.main()
