"""editing-feedback/convert APIエンドポイントのテスト

FastAPI TestClientを使用してAPIの入出力を検証する。
LLM呼び出しはモックで代替する。
"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient


class TestEditingFeedbackConvertAPI(unittest.TestCase):
    """POST /api/v1/editing-feedback/convert のテスト"""

    @classmethod
    def setUpClass(cls):
        """テスト用のFastAPIアプリを取得"""
        # google.oauth2のインポートエラーを回避
        sys.modules.setdefault("google.oauth2", MagicMock())
        sys.modules.setdefault("google.oauth2.service_account", MagicMock())
        sys.modules.setdefault("googleapiclient", MagicMock())
        sys.modules.setdefault("googleapiclient.discovery", MagicMock())
        from src.video_direction.integrations.api_server import app
        cls.client = TestClient(app)

    @patch("src.video_direction.tracker.editing_feedback_converter.ask")
    @patch("src.video_direction.tracker.editing_feedback_converter._get_guest_context")
    @patch("src.video_direction.tracker.editing_feedback_converter._get_quality_criteria")
    def test_basic_request(self, mock_criteria, mock_guest, mock_ask):
        """基本的なリクエストが正常にレスポンスを返す"""
        mock_criteria.return_value = ("品質基準テキスト", "ハイライト選定の品質基準")
        mock_guest.return_value = "ゲスト情報"
        mock_ask.return_value = json.dumps({
            "converted_instruction": "冒頭ハイライトを差し替え",
            "reason": "パンチライン不足",
            "suggestions": ["案1", "案2"],
            "confidence": 0.85,
        })

        response = self.client.post(
            "/api/v1/editing-feedback/convert",
            json={
                "feedback": "冒頭のハイライト、センスなさすぎ",
                "guest_name": "メンイチ",
                "category": "highlight",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("converted_instruction", data)
        self.assertIn("冒頭ハイライト", data["converted_instruction"])
        self.assertEqual(data["category"], "highlight")
        self.assertEqual(data["guest_name"], "メンイチ")
        self.assertIn("suggestions", data)
        self.assertIn("confidence", data)
        self.assertIn("quality_criteria_used", data)
        self.assertIn("original_feedback", data)

    @patch("src.video_direction.tracker.editing_feedback_converter.ask")
    @patch("src.video_direction.tracker.editing_feedback_converter._get_guest_context")
    @patch("src.video_direction.tracker.editing_feedback_converter._get_quality_criteria")
    def test_auto_category_detection(self, mock_criteria, mock_guest, mock_ask):
        """category未指定時に自動推定される"""
        mock_criteria.return_value = ("基準", "ハイライト選定の品質基準")
        mock_guest.return_value = ""
        mock_ask.return_value = json.dumps({
            "converted_instruction": "指示テキスト",
            "suggestions": [],
            "confidence": 0.7,
        })

        response = self.client.post(
            "/api/v1/editing-feedback/convert",
            json={
                "feedback": "冒頭のハイライトが弱い",
                "guest_name": "テスト",
                # categoryは未指定
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["category"], "highlight")

    @patch("src.video_direction.tracker.editing_feedback_converter._get_guest_context")
    @patch("src.video_direction.tracker.editing_feedback_converter._get_quality_criteria")
    def test_llm_failure_returns_fallback(self, mock_criteria, mock_guest):
        """LLM失敗時もフォールバックレスポンスが返る"""
        mock_criteria.return_value = ("基準", "ハイライト選定の品質基準")
        mock_guest.return_value = ""

        with patch(
            "src.video_direction.tracker.editing_feedback_converter.ask",
            side_effect=Exception("LLMエラー"),
        ):
            response = self.client.post(
                "/api/v1/editing-feedback/convert",
                json={
                    "feedback": "ダメ",
                    "guest_name": "テスト",
                    "category": "highlight",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("ハイライト修正指示", data["converted_instruction"])
        self.assertEqual(data["confidence"], 0.3)

    def test_missing_feedback_field(self):
        """feedbackフィールド未指定で422エラー"""
        response = self.client.post(
            "/api/v1/editing-feedback/convert",
            json={
                "guest_name": "テスト",
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_missing_guest_name_field(self):
        """guest_nameフィールド未指定で422エラー"""
        response = self.client.post(
            "/api/v1/editing-feedback/convert",
            json={
                "feedback": "テスト",
            },
        )
        self.assertEqual(response.status_code, 422)

    @patch("src.video_direction.tracker.editing_feedback_converter.ask")
    @patch("src.video_direction.tracker.editing_feedback_converter._get_guest_context")
    @patch("src.video_direction.tracker.editing_feedback_converter._get_quality_criteria")
    def test_with_project_id(self, mock_criteria, mock_guest, mock_ask):
        """project_id付きリクエスト"""
        mock_criteria.return_value = ("基準", "基準名")
        mock_guest.return_value = ""
        mock_ask.return_value = json.dumps({
            "converted_instruction": "指示",
            "suggestions": [],
            "confidence": 0.7,
        })

        response = self.client.post(
            "/api/v1/editing-feedback/convert",
            json={
                "feedback": "テスト",
                "guest_name": "テスト",
                "category": "direction",
                "project_id": "proj_20260320_001",
            },
        )

        self.assertEqual(response.status_code, 200)

    @patch("src.video_direction.tracker.editing_feedback_converter.ask")
    @patch("src.video_direction.tracker.editing_feedback_converter._get_guest_context")
    @patch("src.video_direction.tracker.editing_feedback_converter._get_quality_criteria")
    def test_response_has_all_fields(self, mock_criteria, mock_guest, mock_ask):
        """レスポンスに全必須フィールドが含まれる"""
        mock_criteria.return_value = ("基準", "基準名")
        mock_guest.return_value = "ゲスト情報"
        mock_ask.return_value = json.dumps({
            "converted_instruction": "指示テキスト",
            "suggestions": ["案A"],
            "confidence": 0.9,
        })

        response = self.client.post(
            "/api/v1/editing-feedback/convert",
            json={
                "feedback": "テストFB",
                "guest_name": "テストゲスト",
                "category": "highlight",
            },
        )

        data = response.json()
        required_fields = [
            "original_feedback",
            "category",
            "guest_name",
            "converted_instruction",
            "quality_criteria_used",
            "guest_context",
            "suggestions",
            "confidence",
        ]
        for field in required_fields:
            self.assertIn(field, data, f"レスポンスに{field}が含まれていない")


if __name__ == "__main__":
    unittest.main()
