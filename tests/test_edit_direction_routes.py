"""edit_direction_routes のAPIテスト"""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# テスト用DBパスをパッチしてからインポートする
_test_db_path = Path(tempfile.mkdtemp()) / "test_direction.db"


def _get_test_db() -> sqlite3.Connection:
    """テスト用DB接続"""
    _test_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_test_db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _setup_test_db():
    """テスト用DBにprojectsテーブルとテストデータを作成"""
    conn = _get_test_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            guest_name TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'directed',
            knowledge TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS direction_edits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL REFERENCES projects(id),
            original_content TEXT,
            edited_content TEXT NOT NULL,
            edited_by TEXT NOT NULL,
            edit_notes TEXT,
            diff_summary TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.execute(
        "INSERT OR IGNORE INTO projects (id, guest_name, title, knowledge) VALUES (?, ?, ?, ?)",
        ("proj-001", "テストゲスト", "テスト動画", json.dumps({"direction_report": "元のディレクション内容"}, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()


# DBパスをパッチ
@pytest.fixture(autouse=True)
def patch_db(tmp_path):
    """各テストでクリーンなDBを使用する"""
    global _test_db_path
    _test_db_path = tmp_path / "test_direction.db"

    with patch("src.video_direction.integrations.edit_direction_routes.DB_PATH", _test_db_path), \
         patch("src.video_direction.integrations.edit_direction_routes._get_db", _get_test_db):
        _setup_test_db()
        yield


@pytest.fixture
def client():
    """FastAPIテストクライアント"""
    from fastapi import FastAPI
    from src.video_direction.integrations.edit_direction_routes import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestPutDirectionReport:
    """PUT /api/v1/projects/{project_id}/direction-report"""

    def test_create_edit(self, client):
        """手修正を保存できる"""
        resp = client.put(
            "/api/v1/projects/proj-001/direction-report",
            json={
                "edited_content": "修正後のディレクション",
                "edited_by": "naoto",
                "edit_notes": "テロップ指示を修正",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "proj-001"
        assert data["edited_by"] == "naoto"
        assert data["edit_notes"] == "テロップ指示を修正"

    def test_404_for_unknown_project(self, client):
        """存在しないプロジェクトは404"""
        resp = client.put(
            "/api/v1/projects/nonexistent/direction-report",
            json={
                "edited_content": "内容",
                "edited_by": "naoto",
            },
        )
        assert resp.status_code == 404

    def test_diff_summary_generated(self, client):
        """diff_summaryが自動生成される"""
        resp = client.put(
            "/api/v1/projects/proj-001/direction-report",
            json={
                "edited_content": "テロップを大きく表示する指示に変更",
                "edited_by": "naoto",
            },
        )
        data = resp.json()
        assert data["diff_summary"] is not None
        summary = json.loads(data["diff_summary"])
        assert "total_changes" in summary

    def test_multiple_edits(self, client):
        """複数回の手修正が保存できる"""
        client.put(
            "/api/v1/projects/proj-001/direction-report",
            json={"edited_content": "1回目", "edited_by": "naoto"},
        )
        resp = client.put(
            "/api/v1/projects/proj-001/direction-report",
            json={"edited_content": "2回目", "edited_by": "naoto"},
        )
        assert resp.status_code == 200


class TestGetDirectionHistory:
    """GET /api/v1/projects/{project_id}/direction-report/history"""

    def test_empty_history(self, client):
        """編集履歴がない場合は空リスト"""
        resp = client.get("/api/v1/projects/proj-001/direction-report/history")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_history_order(self, client):
        """編集履歴が新しい順で返される"""
        client.put(
            "/api/v1/projects/proj-001/direction-report",
            json={"edited_content": "1回目", "edited_by": "naoto"},
        )
        client.put(
            "/api/v1/projects/proj-001/direction-report",
            json={"edited_content": "2回目", "edited_by": "naoto"},
        )
        resp = client.get("/api/v1/projects/proj-001/direction-report/history")
        data = resp.json()
        assert len(data) == 2
        assert data[0]["edited_content"] == "2回目"
        assert data[1]["edited_content"] == "1回目"


class TestGetDirectionDiff:
    """GET /api/v1/projects/{project_id}/direction-report/diff"""

    def test_diff_not_found(self, client):
        """編集がない場合は404"""
        resp = client.get("/api/v1/projects/proj-001/direction-report/diff")
        assert resp.status_code == 404

    def test_diff_response(self, client):
        """diff結果が正しく返される"""
        client.put(
            "/api/v1/projects/proj-001/direction-report",
            json={"edited_content": "テロップを修正した内容", "edited_by": "naoto"},
        )
        resp = client.get("/api/v1/projects/proj-001/direction-report/diff")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "proj-001"
        assert "total_changes" in data
        assert "severity" in data
        assert "changes" in data
