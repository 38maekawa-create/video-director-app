"""FB登録APIの学習連携テスト"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from src.video_direction.integrations import api_server


def test_create_feedback_triggers_feedback_learning(tmp_path):
    test_db = tmp_path / "video_director_test.db"
    learner = MagicMock()
    learner.ingest_feedback.return_value = [MagicMock()]

    with patch.object(api_server, "DB_PATH", Path(test_db)):
        api_server.init_db()
        with patch.object(api_server, "_get_feedback_learner", return_value=learner):
            client = TestClient(api_server.app, raise_server_exceptions=False)

            # FK制約のため先にprojectを作る
            resp_project = client.post(
                "/api/projects",
                json={
                    "id": "proj_001",
                    "guest_name": "テストさん",
                    "title": "テスト動画",
                },
            )
            assert resp_project.status_code == 200

            resp = client.post(
                "/api/projects/proj_001/feedbacks",
                json={
                    "timestamp_mark": "00:12",
                    "raw_voice_text": "テロップ改善したい",
                    "converted_text": "テロップを太くして視認性を上げる",
                    "category": "telop",
                    "priority": "high",
                    "created_by": "qa",
                },
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload["status"] == "created"
            assert isinstance(payload["feedback_id"], int)
            assert payload["feedback_id"] > 0
            assert payload["learning_applied"] is True
            assert payload["learned_patterns"] == 1
            learner.ingest_feedback.assert_called_once()
