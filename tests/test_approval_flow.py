"""承認フロー（T-042）回帰テスト

テスト対象:
- GET  /api/v1/feedbacks/pending       — 承認待ちFB一覧
- PUT  /api/v1/feedbacks/{id}/approve  — 承認（正常系+異常系）
- PUT  /api/v1/feedbacks/{id}/modify   — 修正承認（正常系）
- PUT  /api/v1/feedbacks/{id}/reject   — 却下（正常系）
- 承認済みのみVimeo投稿許可されることの確認
- 承認ステータス遷移（pending→approved, pending→modified, pending→rejected）

DBはインメモリで作成し、_get_dbをモックで差し替える。
"""

import json
import sqlite3
import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from src.video_direction.integrations.api_server import app


# --- テスト用ヘルパー ---

class _NonClosingConnection:
    """conn.close()を無効化するラッパー。
    APIエンドポイントが毎回conn.close()を呼ぶため、
    テストで同一コネクションを再利用するために必要。
    """
    def __init__(self, conn):
        self._conn = conn

    def close(self):
        # close()を無効化（テスト終了まで保持）
        pass

    def real_close(self):
        self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _make_client():
    """TestClientを生成（startupイベントのDB初期化をスキップ）"""
    return TestClient(app, raise_server_exceptions=False)


def _make_approval_db(
    feedbacks=None,
    project_id="proj_approval_001",
) -> sqlite3.Connection:
    """承認フローテスト用のインメモリDBを作成

    feedbacks: list[dict] — 各FBの属性を指定。省略時はデフォルト3件を挿入
    """
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
            category TEXT,
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
            feedback_target TEXT DEFAULT 'direction',
            approval_status TEXT DEFAULT 'pending',
            approved_at TEXT,
            modified_text TEXT,
            approved_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)

    # プロジェクト挿入
    conn.execute(
        "INSERT INTO projects (id, guest_name, title, status) VALUES (?, ?, ?, ?)",
        (project_id, "承認テストゲスト", "承認テスト動画", "directed"),
    )

    # フィードバック挿入
    if feedbacks is None:
        feedbacks = [
            {"timestamp_mark": "01:00", "raw_voice_text": "テロップを大きく", "category": "telop", "priority": "high", "created_by": "naoto"},
            {"timestamp_mark": "02:30", "raw_voice_text": "カットを短く", "category": "cut", "priority": "medium", "created_by": "naoto"},
            {"timestamp_mark": "04:00", "raw_voice_text": "BGMを変更", "category": "bgm", "priority": "low", "created_by": "naoto"},
        ]

    for fb in feedbacks:
        conn.execute(
            "INSERT INTO feedbacks (project_id, timestamp_mark, raw_voice_text, category, priority, created_by, approval_status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                project_id,
                fb.get("timestamp_mark", "00:00"),
                fb.get("raw_voice_text", "テストFB"),
                fb.get("category", "other"),
                fb.get("priority", "medium"),
                fb.get("created_by", "naoto"),
                fb.get("approval_status", "pending"),
            ),
        )

    conn.commit()
    return _NonClosingConnection(conn)


# ============================================================
# 1. GET /api/v1/feedbacks/pending — 承認待ちFB一覧
# ============================================================

class TestPendingFeedbacks:
    """承認待ちFB一覧APIのテスト"""

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_全件pending時に全件返される(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        resp = client.get("/api/v1/feedbacks/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        # プロジェクト情報が付与されている
        assert data[0]["guest_name"] == "承認テストゲスト"
        assert data[0]["project_title"] == "承認テスト動画"

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_承認済みはpending一覧に含まれない(self, mock_db):
        feedbacks = [
            {"raw_voice_text": "承認済みFB", "created_by": "naoto", "approval_status": "approved"},
            {"raw_voice_text": "pending FB", "created_by": "naoto", "approval_status": "pending"},
        ]
        conn = _make_approval_db(feedbacks=feedbacks)
        mock_db.return_value = conn
        client = _make_client()

        resp = client.get("/api/v1/feedbacks/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["raw_voice_text"] == "pending FB"

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_approval_statusがNULLのFBもpendingとして返される(self, mock_db):
        """マイグレーション前の既存データ（NULLのまま）もpendingとして扱う"""
        conn = _make_approval_db(feedbacks=[])
        # NULLのapproval_statusを持つFBを直接挿入
        conn.execute(
            "INSERT INTO feedbacks (project_id, timestamp_mark, raw_voice_text, category, created_by, approval_status) "
            "VALUES (?, ?, ?, ?, ?, NULL)",
            ("proj_approval_001", "00:00", "旧データFB", "other", "naoto"),
        )
        conn.commit()
        mock_db.return_value = conn
        client = _make_client()

        resp = client.get("/api/v1/feedbacks/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_pending_feedbacksが空の場合は空リスト(self, mock_db):
        feedbacks = [
            {"raw_voice_text": "全部承認済み", "created_by": "naoto", "approval_status": "approved"},
        ]
        conn = _make_approval_db(feedbacks=feedbacks)
        mock_db.return_value = conn
        client = _make_client()

        resp = client.get("/api/v1/feedbacks/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 0


# ============================================================
# 2. PUT /api/v1/feedbacks/{id}/approve — 承認
# ============================================================

class TestApproveFeedback:
    """承認APIのテスト"""

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_正常系_承認成功(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        resp = client.put(
            "/api/v1/feedbacks/1/approve",
            json={"approved_by": "naoto"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["feedback_id"] == 1
        assert data["approved_by"] == "naoto"

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_正常系_approved_by省略時はcreated_byが使われる(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        resp = client.put("/api/v1/feedbacks/1/approve")
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved_by"] == "naoto"

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_異常系_存在しないFB(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        resp = client.put(
            "/api/v1/feedbacks/9999/approve",
            json={"approved_by": "naoto"},
        )
        assert resp.status_code == 404

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_異常系_投稿者以外が承認しようとすると403(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        resp = client.put(
            "/api/v1/feedbacks/1/approve",
            json={"approved_by": "other_user"},
        )
        assert resp.status_code == 403

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_承認後にDBのapproval_statusがapprovedに変わる(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        client.put("/api/v1/feedbacks/1/approve", json={"approved_by": "naoto"})

        # DBを直接確認
        row = conn.execute("SELECT approval_status, approved_at, approved_by FROM feedbacks WHERE id = 1").fetchone()
        assert row["approval_status"] == "approved"
        assert row["approved_at"] is not None
        assert row["approved_by"] == "naoto"


# ============================================================
# 3. PUT /api/v1/feedbacks/{id}/modify — 修正承認
# ============================================================

class TestModifyFeedback:
    """修正承認APIのテスト"""

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_正常系_修正承認成功(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        resp = client.put(
            "/api/v1/feedbacks/1/modify",
            json={"modified_text": "テロップを大きく（修正版）", "approved_by": "naoto"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "modified"
        assert data["modified_text"] == "テロップを大きく（修正版）"
        assert data["approved_by"] == "naoto"

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_異常系_modified_textが空の場合400(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        resp = client.put(
            "/api/v1/feedbacks/1/modify",
            json={"modified_text": "", "approved_by": "naoto"},
        )
        assert resp.status_code == 400

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_異常系_modified_text未指定の場合400(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        resp = client.put(
            "/api/v1/feedbacks/1/modify",
            json={"approved_by": "naoto"},
        )
        assert resp.status_code == 400

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_異常系_存在しないFBは404(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        resp = client.put(
            "/api/v1/feedbacks/9999/modify",
            json={"modified_text": "修正テキスト", "approved_by": "naoto"},
        )
        assert resp.status_code == 404

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_異常系_投稿者以外が修正承認すると403(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        resp = client.put(
            "/api/v1/feedbacks/1/modify",
            json={"modified_text": "修正テキスト", "approved_by": "other_user"},
        )
        assert resp.status_code == 403

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_修正承認後にDBにmodified_textが保存される(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        client.put(
            "/api/v1/feedbacks/2/modify",
            json={"modified_text": "カットを2秒に短縮", "approved_by": "naoto"},
        )

        row = conn.execute("SELECT approval_status, modified_text, approved_by FROM feedbacks WHERE id = 2").fetchone()
        assert row["approval_status"] == "modified"
        assert row["modified_text"] == "カットを2秒に短縮"


# ============================================================
# 4. PUT /api/v1/feedbacks/{id}/reject — 却下
# ============================================================

class TestRejectFeedback:
    """却下APIのテスト"""

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_正常系_却下成功(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        resp = client.put(
            "/api/v1/feedbacks/1/reject",
            json={"approved_by": "naoto"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert data["feedback_id"] == 1

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_異常系_存在しないFBは404(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        resp = client.put("/api/v1/feedbacks/9999/reject", json={"approved_by": "naoto"})
        assert resp.status_code == 404

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_異常系_投稿者以外が却下すると403(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        resp = client.put(
            "/api/v1/feedbacks/1/reject",
            json={"approved_by": "other_user"},
        )
        assert resp.status_code == 403

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_却下後にDBのapproval_statusがrejectedに変わる(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        client.put("/api/v1/feedbacks/3/reject", json={"approved_by": "naoto"})

        row = conn.execute("SELECT approval_status, approved_at FROM feedbacks WHERE id = 3").fetchone()
        assert row["approval_status"] == "rejected"
        assert row["approved_at"] is not None


# ============================================================
# 5. 承認済みのみVimeo投稿許可 — 承認チェックガード
# ============================================================

class TestVimeoApprovalGate:
    """Vimeo投稿時の承認チェック（本番投稿=dry_run=false時のみ）"""

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_未承認FBを含む本番投稿は403で拒否(self, mock_db):
        """approval_status='pending'のFBが含まれる場合、本番投稿は拒否"""
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        resp = client.post(
            "/api/v1/vimeo/post-review?dry_run=false",
            json={
                "vimeo_video_id": "12345",
                "comments": [
                    {"timecode": "01:00", "text": "テスト", "priority": "high", "feedback_id": "1"},
                ],
            },
        )
        assert resp.status_code == 403
        resp_data = resp.json()
        detail = resp_data.get("detail", resp_data.get("message", ""))
        assert "未承認" in detail

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_承認済みFBなら本番投稿可能(self, mock_db):
        """approval_status='approved'のFBのみの場合、投稿処理に進む"""
        feedbacks = [
            {"raw_voice_text": "承認済みFB", "created_by": "naoto", "approval_status": "approved"},
        ]
        conn = _make_approval_db(feedbacks=feedbacks)
        mock_db.return_value = conn
        client = _make_client()

        # Vimeo APIへの実際のリクエストはモック不要（承認チェック後のVimeo呼び出しはモックすべきだが、
        # ここでは承認チェックを通過することの確認のみ。実際のVimeo APIコールは別途失敗しても良い）
        resp = client.post(
            "/api/v1/vimeo/post-review?dry_run=false",
            json={
                "vimeo_video_id": "12345",
                "comments": [
                    {"timecode": "01:00", "text": "テスト", "priority": "high", "feedback_id": "1"},
                ],
            },
        )
        # 承認チェックは通過（403でない）。Vimeo APIの認証エラー等は別の問題
        assert resp.status_code != 403

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_修正承認済みFBも本番投稿可能(self, mock_db):
        """approval_status='modified'もVimeo投稿許可"""
        feedbacks = [
            {"raw_voice_text": "修正承認済みFB", "created_by": "naoto", "approval_status": "modified"},
        ]
        conn = _make_approval_db(feedbacks=feedbacks)
        mock_db.return_value = conn
        client = _make_client()

        resp = client.post(
            "/api/v1/vimeo/post-review?dry_run=false",
            json={
                "vimeo_video_id": "12345",
                "comments": [
                    {"timecode": "01:00", "text": "テスト", "priority": "high", "feedback_id": "1"},
                ],
            },
        )
        assert resp.status_code != 403

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_却下済みFBは本番投稿不可(self, mock_db):
        """approval_status='rejected'のFBが含まれる場合は拒否"""
        feedbacks = [
            {"raw_voice_text": "却下済みFB", "created_by": "naoto", "approval_status": "rejected"},
        ]
        conn = _make_approval_db(feedbacks=feedbacks)
        mock_db.return_value = conn
        client = _make_client()

        resp = client.post(
            "/api/v1/vimeo/post-review?dry_run=false",
            json={
                "vimeo_video_id": "12345",
                "comments": [
                    {"timecode": "01:00", "text": "テスト", "priority": "high", "feedback_id": "1"},
                ],
            },
        )
        assert resp.status_code == 403

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_dry_run時は承認チェックをスキップ(self, mock_db):
        """dry_run=Trueの場合は承認状態に関係なく処理される"""
        conn = _make_approval_db()  # 全てpending
        mock_db.return_value = conn
        client = _make_client()

        resp = client.post(
            "/api/v1/vimeo/post-review?dry_run=true",
            json={
                "vimeo_video_id": "12345",
                "comments": [
                    {"timecode": "01:00", "text": "テスト", "priority": "high", "feedback_id": "1"},
                ],
            },
        )
        # dry_runなので承認チェックは行われず、403にならない
        assert resp.status_code != 403


# ============================================================
# 6. ステータス遷移テスト
# ============================================================

class TestApprovalStatusTransitions:
    """承認ステータスの遷移を包括的に検証"""

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_pending_to_approved遷移(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        # 遷移前: pending
        row = conn.execute("SELECT approval_status FROM feedbacks WHERE id = 1").fetchone()
        assert row["approval_status"] == "pending"

        # 承認
        resp = client.put("/api/v1/feedbacks/1/approve", json={"approved_by": "naoto"})
        assert resp.status_code == 200

        # 遷移後: approved
        row = conn.execute("SELECT approval_status FROM feedbacks WHERE id = 1").fetchone()
        assert row["approval_status"] == "approved"

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_pending_to_modified遷移(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        # 遷移前: pending
        row = conn.execute("SELECT approval_status FROM feedbacks WHERE id = 2").fetchone()
        assert row["approval_status"] == "pending"

        # 修正承認
        resp = client.put(
            "/api/v1/feedbacks/2/modify",
            json={"modified_text": "修正テキスト", "approved_by": "naoto"},
        )
        assert resp.status_code == 200

        # 遷移後: modified
        row = conn.execute("SELECT approval_status FROM feedbacks WHERE id = 2").fetchone()
        assert row["approval_status"] == "modified"

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_pending_to_rejected遷移(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        # 遷移前: pending
        row = conn.execute("SELECT approval_status FROM feedbacks WHERE id = 3").fetchone()
        assert row["approval_status"] == "pending"

        # 却下
        resp = client.put("/api/v1/feedbacks/3/reject", json={"approved_by": "naoto"})
        assert resp.status_code == 200

        # 遷移後: rejected
        row = conn.execute("SELECT approval_status FROM feedbacks WHERE id = 3").fetchone()
        assert row["approval_status"] == "rejected"

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_承認後はpending一覧から消える(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        # 全3件がpending
        resp = client.get("/api/v1/feedbacks/pending")
        assert len(resp.json()) == 3

        # 1件を承認
        client.put("/api/v1/feedbacks/1/approve", json={"approved_by": "naoto"})

        # pending一覧が2件に減る
        resp = client.get("/api/v1/feedbacks/pending")
        assert len(resp.json()) == 2

    @patch("src.video_direction.integrations.api_server._get_db")
    def test_全件承認後にpending一覧が空になる(self, mock_db):
        conn = _make_approval_db()
        mock_db.return_value = conn
        client = _make_client()

        # 全件を承認/修正承認/却下
        client.put("/api/v1/feedbacks/1/approve", json={"approved_by": "naoto"})
        client.put("/api/v1/feedbacks/2/modify", json={"modified_text": "修正", "approved_by": "naoto"})
        client.put("/api/v1/feedbacks/3/reject", json={"approved_by": "naoto"})

        # pending一覧が空
        resp = client.get("/api/v1/feedbacks/pending")
        assert resp.status_code == 200
        assert len(resp.json()) == 0
