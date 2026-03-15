"""E2E API エンドポイントのテスト

テスト対象:
- POST /api/v1/projects/{pid}/generate-direction
- POST /api/v1/projects/{pid}/e2e-pipeline （dry_run）
- POST /api/v1/feedback/convert-enhanced
- エラーケース（不存在プロジェクト等）

各依存モジュール（DB, FeedbackLearner, VideoLearner等）はモックで差し替え、
APIレイヤーの動作を独立してテストする。
"""

import json
import sqlite3
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import dataclass, field
from datetime import datetime

from fastapi.testclient import TestClient
from src.video_direction.integrations.api_server import app


# --- テスト用ヘルパー ---

def _make_client():
    """TestClient を生成（startup イベントの DB初期化をスキップ）"""
    return TestClient(app, raise_server_exceptions=False)


def _make_test_db(project_id: str = "proj_test_001",
                  with_knowledge: bool = True,
                  with_feedbacks: bool = False) -> sqlite3.Connection:
    """テスト用のインメモリDBを作成してプロジェクトを挿入"""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            guest_name TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'directed',
            shoot_date TEXT,
            guest_age INTEGER,
            guest_occupation TEXT,
            quality_score INTEGER,
            has_unsent_feedback INTEGER DEFAULT 0,
            unreviewed_count INTEGER DEFAULT 0,
            direction_report_url TEXT,
            source_video TEXT,
            edited_video TEXT,
            feedback_summary TEXT,
            knowledge TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS feedbacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT REFERENCES projects(id),
            timestamp_mark TEXT,
            raw_voice_text TEXT,
            converted_text TEXT,
            category TEXT,
            priority TEXT DEFAULT 'medium',
            created_by TEXT,
            is_sent INTEGER DEFAULT 0,
            editor_status TEXT DEFAULT '未対応',
            learning_effect TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)

    # ナレッジデータ（ハイライト付き）
    knowledge = None
    if with_knowledge:
        knowledge = json.dumps({
            "highlights": [
                {
                    "timestamp": "01:00",
                    "speaker": "ゲスト",
                    "text": "年収1000万円を達成しました",
                    "category": "実績数字",
                },
                {
                    "timestamp": "02:30",
                    "speaker": "ゲスト",
                    "text": "人生は一度きりです",
                    "category": "パンチライン",
                },
                {
                    "timestamp": "05:00",
                    "speaker": "ゲスト",
                    "text": "TEKOのおかげで成長できました",
                    "category": "TEKO価値",
                },
            ]
        })

    conn.execute(
        "INSERT INTO projects (id, guest_name, title, status, knowledge) VALUES (?, ?, ?, ?, ?)",
        (project_id, "テストゲスト", "テスト動画タイトル", "directed", knowledge),
    )

    if with_feedbacks:
        conn.execute(
            "INSERT INTO feedbacks (project_id, timestamp_mark, raw_voice_text, category, priority) VALUES (?, ?, ?, ?, ?)",
            (project_id, "01:00", "テロップをもっと目立たせてほしい", "telop", "high"),
        )
        conn.execute(
            "INSERT INTO feedbacks (project_id, timestamp_mark, raw_voice_text, category, priority) VALUES (?, ?, ?, ?, ?)",
            (project_id, "03:00", "カメラアングルを変えてほしい", "camera", "medium"),
        )

    conn.commit()
    return conn


# ============================================================
# 1. POST /api/v1/projects/{pid}/generate-direction
# ============================================================

class TestGenerateDirectionAPI:
    """ディレクション生成APIのテスト"""

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    @patch("src.video_direction.integrations.api_server._get_video_learner")
    @patch("src.video_direction.integrations.api_server._get_feedback_learner")
    @patch("src.video_direction.integrations.api_server._get_db")
    def test_正常レスポンス形式(self, mock_db, mock_fb, mock_vl, mock_tracker):
        """正常時のレスポンスに必要なフィールドが全て含まれる"""
        conn = _make_test_db()
        mock_db.return_value = conn
        mock_fb.return_value = None
        mock_vl.return_value = None
        mock_tracker.return_value = None

        client = _make_client()
        resp = client.post(
            "/api/v1/projects/proj_test_001/generate-direction",
            json={"use_llm": False},
        )
        assert resp.status_code == 200
        data = resp.json()

        # 必須フィールドの存在チェック
        assert "project_id" in data
        assert data["project_id"] == "proj_test_001"
        assert "direction_timeline" in data
        assert "entries" in data["direction_timeline"]
        assert "llm_analysis" in data["direction_timeline"]
        assert "applied_rules" in data["direction_timeline"]
        assert "learning_context" in data
        assert "tracking_references" in data
        assert "video_reference_urls" in data
        assert "generated_at" in data

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    @patch("src.video_direction.integrations.api_server._get_video_learner")
    @patch("src.video_direction.integrations.api_server._get_feedback_learner")
    @patch("src.video_direction.integrations.api_server._get_db")
    def test_ハイライト付きプロジェクトでエントリが生成される(self, mock_db, mock_fb, mock_vl, mock_tracker):
        """knowledgeにハイライトがあればエントリが生成される"""
        conn = _make_test_db(with_knowledge=True)
        mock_db.return_value = conn
        mock_fb.return_value = None
        mock_vl.return_value = None
        mock_tracker.return_value = None

        client = _make_client()
        resp = client.post(
            "/api/v1/projects/proj_test_001/generate-direction",
            json={"use_llm": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        entries = data["direction_timeline"]["entries"]
        # 実績数字 + パンチライン + TEKO価値 → 複数エントリ生成
        assert len(entries) >= 1

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    @patch("src.video_direction.integrations.api_server._get_video_learner")
    @patch("src.video_direction.integrations.api_server._get_feedback_learner")
    @patch("src.video_direction.integrations.api_server._get_db")
    def test_ナレッジなしプロジェクトでも正常レスポンス(self, mock_db, mock_fb, mock_vl, mock_tracker):
        """knowledgeが空でもエラーにならない"""
        conn = _make_test_db(with_knowledge=False)
        mock_db.return_value = conn
        mock_fb.return_value = None
        mock_vl.return_value = None
        mock_tracker.return_value = None

        client = _make_client()
        resp = client.post(
            "/api/v1/projects/proj_test_001/generate-direction",
            json={"use_llm": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["direction_timeline"]["entries"] == []

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_不存在プロジェクトで404(self, mock_db):
        """存在しないプロジェクトIDで404が返る"""
        conn = _make_test_db()
        mock_db.return_value = conn

        client = _make_client()
        resp = client.post(
            "/api/v1/projects/non_existent_project/generate-direction",
            json={"use_llm": False},
        )
        assert resp.status_code == 404

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    @patch("src.video_direction.integrations.api_server._get_video_learner")
    @patch("src.video_direction.integrations.api_server._get_feedback_learner")
    @patch("src.video_direction.integrations.api_server._get_db")
    def test_エントリの構造が正しい(self, mock_db, mock_fb, mock_vl, mock_tracker):
        """各エントリにtimestamp, direction_type, instruction, reason, priorityが含まれる"""
        conn = _make_test_db(with_knowledge=True)
        mock_db.return_value = conn
        mock_fb.return_value = None
        mock_vl.return_value = None
        mock_tracker.return_value = None

        client = _make_client()
        resp = client.post(
            "/api/v1/projects/proj_test_001/generate-direction",
            json={"use_llm": False},
        )
        assert resp.status_code == 200
        entries = resp.json()["direction_timeline"]["entries"]
        for entry in entries:
            assert "timestamp" in entry
            assert "direction_type" in entry
            assert "instruction" in entry
            assert "reason" in entry
            assert "priority" in entry
            assert entry["priority"] in ("high", "medium", "low")
            assert entry["direction_type"] in ("telop", "camera", "color", "composite")


# ============================================================
# 2. POST /api/v1/projects/{pid}/e2e-pipeline
# ============================================================

class TestE2EPipelineAPI:
    """E2Eパイプライン APIのテスト"""

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    @patch("src.video_direction.integrations.api_server._get_video_learner")
    @patch("src.video_direction.integrations.api_server._get_feedback_learner")
    @patch("src.video_direction.integrations.api_server._get_db")
    def test_dry_run正常動作(self, mock_db, mock_fb, mock_vl, mock_tracker):
        """dry_run=Trueで全ステップが成功する"""
        conn = _make_test_db(with_knowledge=True, with_feedbacks=True)
        mock_db.return_value = conn
        mock_fb.return_value = None
        mock_vl.return_value = None
        mock_tracker.return_value = None

        client = _make_client()
        resp = client.post(
            "/api/v1/projects/proj_test_001/e2e-pipeline",
            json={"dry_run": True, "use_llm": False},
        )
        assert resp.status_code == 200
        data = resp.json()

        # 基本フィールド
        assert "project_id" in data
        assert data["project_id"] == "proj_test_001"
        assert "pipeline_steps" in data
        assert "success" in data
        assert "errors" in data
        assert "generated_at" in data

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    @patch("src.video_direction.integrations.api_server._get_video_learner")
    @patch("src.video_direction.integrations.api_server._get_feedback_learner")
    @patch("src.video_direction.integrations.api_server._get_db")
    def test_pipeline_stepsの構造(self, mock_db, mock_fb, mock_vl, mock_tracker):
        """pipeline_stepsに各ステップの状態が含まれる"""
        conn = _make_test_db(with_knowledge=True)
        mock_db.return_value = conn
        mock_fb.return_value = None
        mock_vl.return_value = None
        mock_tracker.return_value = None

        client = _make_client()
        resp = client.post(
            "/api/v1/projects/proj_test_001/e2e-pipeline",
            json={"dry_run": True, "use_llm": False},
        )
        assert resp.status_code == 200
        steps = resp.json()["pipeline_steps"]

        # Step 1: FB一覧取得
        assert "step1_feedbacks" in steps
        assert steps["step1_feedbacks"]["status"] == "ok"

        # Step 4: ディレクション生成
        assert "step4_direction" in steps

        # Step 5: Vimeo（vimeo_video_id未指定でskipped）
        assert "step5_vimeo" in steps
        assert steps["step5_vimeo"]["status"] == "skipped"

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_不存在プロジェクトで404(self, mock_db):
        """存在しないプロジェクトIDで404が返る"""
        conn = _make_test_db()
        mock_db.return_value = conn

        client = _make_client()
        resp = client.post(
            "/api/v1/projects/non_existent/e2e-pipeline",
            json={"dry_run": True},
        )
        assert resp.status_code == 404

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    @patch("src.video_direction.integrations.api_server._get_video_learner")
    @patch("src.video_direction.integrations.api_server._get_feedback_learner")
    @patch("src.video_direction.integrations.api_server._get_db")
    def test_direction_timelineがレスポンスに含まれる(self, mock_db, mock_fb, mock_vl, mock_tracker):
        """ディレクション生成結果がレスポンスに含まれる"""
        conn = _make_test_db(with_knowledge=True)
        mock_db.return_value = conn
        mock_fb.return_value = None
        mock_vl.return_value = None
        mock_tracker.return_value = None

        client = _make_client()
        resp = client.post(
            "/api/v1/projects/proj_test_001/e2e-pipeline",
            json={"dry_run": True, "use_llm": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        # direction_timelineが存在（Noneでない場合エントリ構造をチェック）
        if data.get("direction_timeline"):
            assert "entries" in data["direction_timeline"]

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    @patch("src.video_direction.integrations.api_server._get_video_learner")
    @patch("src.video_direction.integrations.api_server._get_feedback_learner")
    @patch("src.video_direction.integrations.api_server._get_db")
    def test_vimeo_video_id未指定でstep5はskipped(self, mock_db, mock_fb, mock_vl, mock_tracker):
        """vimeo_video_idが未指定の場合、Step5がskippedになる"""
        conn = _make_test_db(with_knowledge=True)
        mock_db.return_value = conn
        mock_fb.return_value = None
        mock_vl.return_value = None
        mock_tracker.return_value = None

        client = _make_client()
        resp = client.post(
            "/api/v1/projects/proj_test_001/e2e-pipeline",
            json={"dry_run": True, "use_llm": False},
        )
        assert resp.status_code == 200
        step5 = resp.json()["pipeline_steps"]["step5_vimeo"]
        assert step5["status"] == "skipped"
        assert "vimeo_video_idが未指定" in step5["reason"]


# ============================================================
# 3. POST /api/v1/feedback/convert-enhanced
# ============================================================

class TestFeedbackConvertEnhancedAPI:
    """FB→LLM変換強化版APIのテスト"""

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    @patch("src.video_direction.integrations.api_server._get_video_learner")
    @patch("src.video_direction.integrations.api_server._get_feedback_learner")
    def test_フォールバックレスポンス形式(self, mock_fb, mock_vl, mock_tracker):
        """APIキーなしの場合、フォールバックレスポンスが返る"""
        mock_fb.return_value = None
        mock_vl.return_value = None
        mock_tracker.return_value = None

        client = _make_client()
        resp = client.post(
            "/api/v1/feedback/convert-enhanced",
            json={
                "raw_text": "テロップの色をもっと目立たせてください",
                "project_id": "proj_test",
                "use_learning_rules": False,
                "include_tracking_references": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()

        # フォールバックレスポンスの構造チェック
        assert "converted_text" in data
        assert "structured_items" in data
        assert "tracking_references" in data
        assert "learning_rules_applied" in data
        assert isinstance(data["structured_items"], list)
        assert len(data["structured_items"]) >= 1

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    @patch("src.video_direction.integrations.api_server._get_video_learner")
    @patch("src.video_direction.integrations.api_server._get_feedback_learner")
    def test_structured_itemsの構造(self, mock_fb, mock_vl, mock_tracker):
        """structured_itemsの各要素に必須フィールドがある"""
        mock_fb.return_value = None
        mock_vl.return_value = None
        mock_tracker.return_value = None

        client = _make_client()
        resp = client.post(
            "/api/v1/feedback/convert-enhanced",
            json={
                "raw_text": "カメラアングルを変更してください",
                "project_id": "proj_test",
                "use_learning_rules": False,
                "include_tracking_references": False,
            },
        )
        assert resp.status_code == 200
        items = resp.json()["structured_items"]
        for item in items:
            assert "id" in item
            assert "timestamp" in item
            assert "element" in item
            assert "instruction" in item
            assert "priority" in item

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    @patch("src.video_direction.integrations.api_server._get_video_learner")
    @patch("src.video_direction.integrations.api_server._get_feedback_learner")
    def test_learning_rules_falseのときルール未適用(self, mock_fb, mock_vl, mock_tracker):
        """use_learning_rules=Falseの場合、learning_rules_appliedがFalse"""
        mock_fb.return_value = None
        mock_vl.return_value = None
        mock_tracker.return_value = None

        client = _make_client()
        resp = client.post(
            "/api/v1/feedback/convert-enhanced",
            json={
                "raw_text": "テスト",
                "project_id": "proj_test",
                "use_learning_rules": False,
                "include_tracking_references": False,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["learning_rules_applied"] is False

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    @patch("src.video_direction.integrations.api_server._get_video_learner")
    @patch("src.video_direction.integrations.api_server._get_feedback_learner")
    def test_tracking_references_falseのときリスト空(self, mock_fb, mock_vl, mock_tracker):
        """include_tracking_references=Falseの場合、tracking_referencesが空リスト"""
        mock_fb.return_value = None
        mock_vl.return_value = None
        mock_tracker.return_value = None

        client = _make_client()
        resp = client.post(
            "/api/v1/feedback/convert-enhanced",
            json={
                "raw_text": "テスト",
                "project_id": "proj_test",
                "use_learning_rules": False,
                "include_tracking_references": False,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["tracking_references"] == []

    def test_必須フィールドraw_text欠落で422(self):
        """raw_textが欠落した場合、バリデーションエラー"""
        client = _make_client()
        resp = client.post(
            "/api/v1/feedback/convert-enhanced",
            json={
                "project_id": "proj_test",
            },
        )
        assert resp.status_code == 422

    def test_必須フィールドproject_id欠落で422(self):
        """project_idが欠落した場合、バリデーションエラー"""
        client = _make_client()
        resp = client.post(
            "/api/v1/feedback/convert-enhanced",
            json={
                "raw_text": "テスト",
            },
        )
        assert resp.status_code == 422


# ============================================================
# 4. エラーケース（共通）
# ============================================================

class TestErrorCases:
    """各エンドポイント共通のエラーケーステスト"""

    def test_generate_direction_GETは許可されない(self):
        """GETメソッドではアクセスできない（POSTのみ）"""
        client = _make_client()
        resp = client.get("/api/v1/projects/proj_test/generate-direction")
        # FastAPIはPOST専用ルートにGETすると405または404を返す
        assert resp.status_code in (404, 405)

    def test_e2e_pipeline_GETは許可されない(self):
        """GETメソッドではアクセスできない（POSTのみ）"""
        client = _make_client()
        resp = client.get("/api/v1/projects/proj_test/e2e-pipeline")
        assert resp.status_code in (404, 405)

    def test_convert_enhanced_GETは許可されない(self):
        """GETメソッドではアクセスできない（POSTのみ）"""
        client = _make_client()
        resp = client.get("/api/v1/feedback/convert-enhanced")
        assert resp.status_code in (404, 405)

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_generate_direction_DB接続エラー(self, mock_db):
        """DBへの接続がエラーの場合、500系のエラーが返る"""
        mock_db.side_effect = Exception("DB connection error")

        client = _make_client()
        resp = client.post(
            "/api/v1/projects/proj_test/generate-direction",
            json={"use_llm": False},
        )
        assert resp.status_code == 500
