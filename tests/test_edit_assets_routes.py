"""edit_assets_routes のAPIテスト"""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

_test_db_path = Path(tempfile.mkdtemp()) / "test_assets.db"


def _get_test_db() -> sqlite3.Connection:
    """テスト用DB接続"""
    _test_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_test_db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _setup_test_db():
    """テスト用DBにテーブルとテストデータを作成"""
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

        CREATE TABLE IF NOT EXISTS youtube_assets (
            project_id TEXT PRIMARY KEY REFERENCES projects(id),
            thumbnail_design TEXT,
            title_proposals TEXT,
            description_original TEXT,
            description_edited TEXT,
            description_finalized_at TEXT,
            description_finalized_by TEXT,
            selected_title_index INTEGER,
            edited_title TEXT,
            last_edited_by TEXT,
            generated_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS asset_edits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL REFERENCES projects(id),
            asset_type TEXT NOT NULL CHECK(asset_type IN ('title', 'description', 'thumbnail')),
            original_content TEXT,
            edited_content TEXT NOT NULL,
            edited_by TEXT NOT NULL,
            diff_summary TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.execute(
        "INSERT OR IGNORE INTO projects (id, guest_name, title) VALUES (?, ?, ?)",
        ("proj-001", "テストゲスト", "テスト動画"),
    )
    conn.execute(
        """INSERT OR IGNORE INTO youtube_assets
           (project_id, title_proposals, selected_title_index, edited_title,
            description_original, thumbnail_design)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            "proj-001",
            json.dumps([{"title": "元のタイトル案1"}, {"title": "元のタイトル案2"}], ensure_ascii=False),
            0,
            "選択済みタイトル",
            "元の概要欄テキスト",
            json.dumps({"layout": "左寄せ", "text": "サムネテキスト"}, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()


@pytest.fixture(autouse=True)
def patch_db(tmp_path):
    """各テストでクリーンなDBを使用する"""
    global _test_db_path
    _test_db_path = tmp_path / "test_assets.db"

    with patch("src.video_direction.integrations.edit_assets_routes.DB_PATH", _test_db_path), \
         patch("src.video_direction.integrations.edit_assets_routes._get_db", _get_test_db):
        _setup_test_db()
        yield


@pytest.fixture
def client():
    """FastAPIテストクライアント"""
    from fastapi import FastAPI
    from src.video_direction.integrations.edit_assets_routes import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestTitleEndpoints:
    """タイトル手修正API"""

    def test_put_title(self, client):
        resp = client.put(
            "/api/v1/projects/proj-001/title",
            json={"edited_content": "新しいタイトル", "edited_by": "naoto"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_type"] == "title"
        assert data["edited_by"] == "naoto"

    def test_title_history(self, client):
        client.put(
            "/api/v1/projects/proj-001/title",
            json={"edited_content": "タイトル1", "edited_by": "naoto"},
        )
        client.put(
            "/api/v1/projects/proj-001/title",
            json={"edited_content": "タイトル2", "edited_by": "naoto"},
        )
        resp = client.get("/api/v1/projects/proj-001/title/history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["edited_content"] == "タイトル2"

    def test_title_diff(self, client):
        client.put(
            "/api/v1/projects/proj-001/title",
            json={"edited_content": "変更タイトル", "edited_by": "naoto"},
        )
        resp = client.get("/api/v1/projects/proj-001/title/diff")
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_type"] == "title"
        assert "severity" in data

    def test_title_404(self, client):
        resp = client.put(
            "/api/v1/projects/nonexistent/title",
            json={"edited_content": "x", "edited_by": "y"},
        )
        assert resp.status_code == 404


class TestDescriptionEndpoints:
    """概要欄手修正API"""

    def test_put_description(self, client):
        resp = client.put(
            "/api/v1/projects/proj-001/description",
            json={"edited_content": "新しい概要欄", "edited_by": "naoto"},
        )
        assert resp.status_code == 200
        assert resp.json()["asset_type"] == "description"

    def test_description_history(self, client):
        client.put(
            "/api/v1/projects/proj-001/description",
            json={"edited_content": "概要1", "edited_by": "naoto"},
        )
        resp = client.get("/api/v1/projects/proj-001/description/history")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_description_diff(self, client):
        client.put(
            "/api/v1/projects/proj-001/description",
            json={"edited_content": "変更概要", "edited_by": "naoto"},
        )
        resp = client.get("/api/v1/projects/proj-001/description/diff")
        assert resp.status_code == 200

    def test_description_diff_404(self, client):
        resp = client.get("/api/v1/projects/proj-001/description/diff")
        assert resp.status_code == 404


class TestThumbnailEndpoints:
    """サムネイル指示手修正API"""

    def test_put_thumbnail(self, client):
        resp = client.put(
            "/api/v1/projects/proj-001/thumbnail-instruction",
            json={"edited_content": "新しいサムネ指示", "edited_by": "naoto"},
        )
        assert resp.status_code == 200
        assert resp.json()["asset_type"] == "thumbnail"

    def test_thumbnail_history(self, client):
        client.put(
            "/api/v1/projects/proj-001/thumbnail-instruction",
            json={"edited_content": "サムネ1", "edited_by": "naoto"},
        )
        client.put(
            "/api/v1/projects/proj-001/thumbnail-instruction",
            json={"edited_content": "サムネ2", "edited_by": "naoto"},
        )
        resp = client.get("/api/v1/projects/proj-001/thumbnail-instruction/history")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_thumbnail_diff(self, client):
        client.put(
            "/api/v1/projects/proj-001/thumbnail-instruction",
            json={"edited_content": "変更サムネ", "edited_by": "naoto"},
        )
        resp = client.get("/api/v1/projects/proj-001/thumbnail-instruction/diff")
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_type"] == "thumbnail"


class TestCrossAssetIsolation:
    """異なるアセットタイプ間の分離確認"""

    def test_different_asset_types_isolated(self, client):
        """タイトル・概要欄・サムネの履歴は混ざらない"""
        client.put(
            "/api/v1/projects/proj-001/title",
            json={"edited_content": "タイトル", "edited_by": "naoto"},
        )
        client.put(
            "/api/v1/projects/proj-001/description",
            json={"edited_content": "概要", "edited_by": "naoto"},
        )
        client.put(
            "/api/v1/projects/proj-001/thumbnail-instruction",
            json={"edited_content": "サムネ", "edited_by": "naoto"},
        )

        title_history = client.get("/api/v1/projects/proj-001/title/history").json()
        desc_history = client.get("/api/v1/projects/proj-001/description/history").json()
        thumb_history = client.get("/api/v1/projects/proj-001/thumbnail-instruction/history").json()

        assert len(title_history) == 1
        assert len(desc_history) == 1
        assert len(thumb_history) == 1
        assert title_history[0]["asset_type"] == "title"
        assert desc_history[0]["asset_type"] == "description"
        assert thumb_history[0]["asset_type"] == "thumbnail"
