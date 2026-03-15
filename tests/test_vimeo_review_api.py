"""Vimeoレビューコメント投稿APIエンドポイントのテスト

テスト対象:
- /api/v1/vimeo/post-review エンドポイント（dry-runモード）
- タイムコードマッピング（_timecode_to_seconds）
- 優先度変換（_priority_to_japanese）
- Vimeoペイロード構築（_build_vimeo_comment_payload）
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# api_serverモジュールをインポート
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestTimecodeToSeconds:
    """タイムコードから秒への変換テスト"""

    def test_mm_ss_format(self):
        from video_direction.integrations.api_server import _timecode_to_seconds
        assert _timecode_to_seconds("02:18") == 138.0

    def test_hh_mm_ss_format(self):
        from video_direction.integrations.api_server import _timecode_to_seconds
        assert _timecode_to_seconds("01:02:18") == 3738.0

    def test_seconds_only(self):
        from video_direction.integrations.api_server import _timecode_to_seconds
        assert _timecode_to_seconds("90") == 90.0

    def test_zero(self):
        from video_direction.integrations.api_server import _timecode_to_seconds
        assert _timecode_to_seconds("00:00") == 0.0

    def test_invalid_returns_zero(self):
        from video_direction.integrations.api_server import _timecode_to_seconds
        assert _timecode_to_seconds("abc") == 0.0

    def test_empty_returns_zero(self):
        from video_direction.integrations.api_server import _timecode_to_seconds
        assert _timecode_to_seconds("") == 0.0

    def test_whitespace_stripped(self):
        from video_direction.integrations.api_server import _timecode_to_seconds
        assert _timecode_to_seconds("  02:18  ") == 138.0


class TestPriorityToJapanese:
    """英語→日本語の優先度変換テスト"""

    def test_high(self):
        from video_direction.integrations.api_server import _priority_to_japanese
        assert _priority_to_japanese("high") == "高"

    def test_medium(self):
        from video_direction.integrations.api_server import _priority_to_japanese
        assert _priority_to_japanese("medium") == "中"

    def test_low(self):
        from video_direction.integrations.api_server import _priority_to_japanese
        assert _priority_to_japanese("low") == "低"

    def test_case_insensitive(self):
        from video_direction.integrations.api_server import _priority_to_japanese
        assert _priority_to_japanese("HIGH") == "高"
        assert _priority_to_japanese("Medium") == "中"

    def test_unknown_defaults_to_medium(self):
        from video_direction.integrations.api_server import _priority_to_japanese
        assert _priority_to_japanese("unknown") == "中"


class TestBuildVimeoCommentPayload:
    """Vimeoコメントペイロード構築テスト"""

    def test_embed_text_mode_default(self):
        from video_direction.integrations.api_server import (
            VimeoCommentItem,
            _build_vimeo_comment_payload,
        )
        comment = VimeoCommentItem(
            timecode="02:18",
            text="ここのカットを短くしてください",
            priority="high",
        )
        with patch.dict(os.environ, {"VIMEO_TIMECODE_MODE": "embed_text"}):
            payload = _build_vimeo_comment_payload(comment)
        assert "text" in payload
        assert "[02:18]" in payload["text"]
        assert "🔴【優先度: 高】" in payload["text"]
        assert "ここのカットを短くしてください" in payload["text"]

    def test_medium_priority_prefix(self):
        from video_direction.integrations.api_server import (
            VimeoCommentItem,
            _build_vimeo_comment_payload,
        )
        comment = VimeoCommentItem(
            timecode="01:00",
            text="テロップのフォントを変えてください",
            priority="medium",
        )
        with patch.dict(os.environ, {"VIMEO_TIMECODE_MODE": "embed_text"}):
            payload = _build_vimeo_comment_payload(comment)
        assert "🟡【優先度: 中】" in payload["text"]

    def test_low_priority_prefix(self):
        from video_direction.integrations.api_server import (
            VimeoCommentItem,
            _build_vimeo_comment_payload,
        )
        comment = VimeoCommentItem(
            timecode="05:30",
            text="可能であればBGMを少し下げてください",
            priority="low",
        )
        with patch.dict(os.environ, {"VIMEO_TIMECODE_MODE": "embed_text"}):
            payload = _build_vimeo_comment_payload(comment)
        assert "🟢【優先度: 低】" in payload["text"]

    def test_body_field_mode(self):
        from video_direction.integrations.api_server import (
            VimeoCommentItem,
            _build_vimeo_comment_payload,
        )
        comment = VimeoCommentItem(
            timecode="02:18",
            text="テスト",
            priority="medium",
        )
        with patch.dict(os.environ, {
            "VIMEO_TIMECODE_MODE": "body_field",
            "VIMEO_TIMECODE_FIELD": "timecode",
        }):
            payload = _build_vimeo_comment_payload(comment)
        assert "text" in payload
        assert "timecode" in payload
        assert payload["timecode"] == 138.0

    def test_skip_mode(self):
        from video_direction.integrations.api_server import (
            VimeoCommentItem,
            _build_vimeo_comment_payload,
        )
        comment = VimeoCommentItem(
            timecode="02:18",
            text="テスト",
            priority="medium",
        )
        with patch.dict(os.environ, {"VIMEO_TIMECODE_MODE": "skip"}):
            payload = _build_vimeo_comment_payload(comment)
        assert "text" in payload
        assert "[02:18]" not in payload["text"]


class TestVimeoPostReviewEndpoint:
    """/api/v1/vimeo/post-review エンドポイントのテスト"""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from video_direction.integrations.api_server import app
        return TestClient(app)

    def test_dry_run_mode(self, client):
        """dry-runモードで投稿計画が返る"""
        response = client.post(
            "/api/v1/vimeo/post-review?dry_run=true",
            json={
                "vimeo_video_id": "123456789",
                "comments": [
                    {
                        "timecode": "02:18",
                        "text": "ここのカットを短くしてください",
                        "priority": "high",
                    },
                    {
                        "timecode": "05:30",
                        "text": "BGMを調整してください",
                        "priority": "medium",
                    },
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "dry_run"
        assert data["targetVideoId"] == "123456789"
        assert data["commentCount"] == 2
        assert len(data["plan"]) == 2
        # 1つ目のコメント
        assert data["plan"][0]["timecode"] == "02:18"
        assert data["plan"][0]["timestampSeconds"] == 138.0
        assert data["plan"][0]["priority"] == "high"

    def test_dry_run_is_default(self, client):
        """dry_runパラメータ省略時はdry-runモード"""
        response = client.post(
            "/api/v1/vimeo/post-review",
            json={
                "vimeo_video_id": "123456789",
                "comments": [
                    {"timecode": "00:00", "text": "テスト", "priority": "medium"},
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "dry_run"

    def test_empty_video_id_rejected(self, client):
        """空のvideo_idはバリデーションエラー"""
        response = client.post(
            "/api/v1/vimeo/post-review",
            json={
                "vimeo_video_id": "",
                "comments": [
                    {"timecode": "00:00", "text": "テスト", "priority": "medium"},
                ],
            },
        )
        assert response.status_code == 400

    def test_empty_comments_rejected(self, client):
        """空のcommentsリストはバリデーションエラー"""
        response = client.post(
            "/api/v1/vimeo/post-review",
            json={
                "vimeo_video_id": "123456789",
                "comments": [],
            },
        )
        assert response.status_code == 400

    def test_multiple_timecode_formats(self, client):
        """異なるタイムコードフォーマットが正しく変換される"""
        response = client.post(
            "/api/v1/vimeo/post-review?dry_run=true",
            json={
                "vimeo_video_id": "123456789",
                "comments": [
                    {"timecode": "01:02:18", "text": "HH:MM:SS形式", "priority": "medium"},
                    {"timecode": "02:18", "text": "MM:SS形式", "priority": "medium"},
                    {"timecode": "90", "text": "秒数形式", "priority": "medium"},
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["plan"][0]["timestampSeconds"] == 3738.0  # 1*3600 + 2*60 + 18
        assert data["plan"][1]["timestampSeconds"] == 138.0    # 2*60 + 18
        assert data["plan"][2]["timestampSeconds"] == 90.0

    def test_feedback_id_optional(self, client):
        """feedback_idは省略可能（自動生成される）"""
        response = client.post(
            "/api/v1/vimeo/post-review?dry_run=true",
            json={
                "vimeo_video_id": "123456789",
                "comments": [
                    {"timecode": "00:30", "text": "テスト", "priority": "medium"},
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["plan"][0]["feedbackId"] == "comment_0"

    def test_feedback_id_provided(self, client):
        """feedback_idが指定されればそれを使う"""
        response = client.post(
            "/api/v1/vimeo/post-review?dry_run=true",
            json={
                "vimeo_video_id": "123456789",
                "comments": [
                    {
                        "timecode": "00:30",
                        "text": "テスト",
                        "priority": "medium",
                        "feedback_id": "fb_42",
                    },
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["plan"][0]["feedbackId"] == "fb_42"
