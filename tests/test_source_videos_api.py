"""素材動画（source_videos）API のユニットテスト

source_videosテーブルのCRUD + ナレッジファイル連携のテスト。
"""

import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from src.video_direction.integrations.api_server import app, init_db, _get_db, DB_PATH


@pytest.fixture
def test_db(tmp_path):
    """テスト用の一時DBを使用する"""
    test_db_path = tmp_path / "test_video_director.db"

    # DB_PATHをモンキーパッチ
    import src.video_direction.integrations.api_server as api_module
    original_db_path = api_module.DB_PATH
    api_module.DB_PATH = test_db_path

    # DB初期化
    init_db()

    yield test_db_path

    # 元に戻す
    api_module.DB_PATH = original_db_path


@pytest.fixture
def client(test_db):
    """テスト用のFastAPIクライアント"""
    return TestClient(app)


@pytest.fixture
def sample_project(test_db):
    """テスト用プロジェクトをDBに追加"""
    import src.video_direction.integrations.api_server as api_module
    conn = sqlite3.connect(str(api_module.DB_PATH))
    conn.execute(
        """INSERT INTO projects (id, guest_name, title, status, shoot_date)
           VALUES (?, ?, ?, ?, ?)""",
        ("test-proj-1", "テストゲスト", "テスト対談動画", "directed", "2026/01/15"),
    )
    conn.commit()
    conn.close()
    return "test-proj-1"


@pytest.fixture
def sample_project_with_legacy_source(test_db):
    """レガシーsource_video JSONが設定されたプロジェクト"""
    import src.video_direction.integrations.api_server as api_module
    source_video = json.dumps({
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "source": "ai_dev5",
        "quality": "youtube_subtitle",
        "knowledge_file": "2026.02.15_test.md",
        "linked_at": "2026-02-15T10:00:00",
    })
    conn = sqlite3.connect(str(api_module.DB_PATH))
    conn.execute(
        """INSERT INTO projects (id, guest_name, title, status, shoot_date, source_video)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("test-proj-legacy", "レガシーゲスト", "レガシー対談", "directed", "2026/02/15", source_video),
    )
    conn.commit()
    conn.close()
    return "test-proj-legacy"


class TestExtractVideoId:
    """_extract_video_id のテスト"""

    def test_standard_url(self):
        from src.video_direction.integrations.api_server import _extract_video_id
        assert _extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_url(self):
        from src.video_direction.integrations.api_server import _extract_video_id
        assert _extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_embed_url(self):
        from src.video_direction.integrations.api_server import _extract_video_id
        assert _extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_url_with_params(self):
        from src.video_direction.integrations.api_server import _extract_video_id
        assert _extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s") == "dQw4w9WgXcQ"

    def test_invalid_url(self):
        from src.video_direction.integrations.api_server import _extract_video_id
        assert _extract_video_id("https://example.com/not-youtube") == ""

    def test_empty_url(self):
        from src.video_direction.integrations.api_server import _extract_video_id
        assert _extract_video_id("") == ""


class TestListProjectSourceVideos:
    """GET /api/v1/projects/{project_id}/source-videos のテスト"""

    def test_empty_list(self, client, sample_project):
        """素材動画がないプロジェクトは空リストを返す"""
        r = client.get(f"/api/v1/projects/{sample_project}/source-videos")
        assert r.status_code == 200
        data = r.json()
        assert data["project_id"] == sample_project
        assert data["total"] == 0
        assert data["videos"] == []

    def test_project_not_found(self, client, test_db):
        """存在しないプロジェクトは404"""
        r = client.get("/api/v1/projects/nonexistent/source-videos")
        assert r.status_code == 404

    def test_legacy_source_video(self, client, sample_project_with_legacy_source):
        """レガシーsource_video JSONが正しく変換されて返る"""
        r = client.get(f"/api/v1/projects/{sample_project_with_legacy_source}/source-videos")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        video = data["videos"][0]
        assert video["video_id"] == "dQw4w9WgXcQ"
        assert video["youtube_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert video["source"] == "ai_dev5"

    def test_registered_and_legacy_dedup(self, client, sample_project_with_legacy_source):
        """同じvideo_idがテーブルにもレガシーにもある場合は重複排除"""
        # まず手動登録
        client.post(
            f"/api/v1/projects/{sample_project_with_legacy_source}/source-videos",
            json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
        r = client.get(f"/api/v1/projects/{sample_project_with_legacy_source}/source-videos")
        assert r.status_code == 200
        data = r.json()
        # 重複排除で1件のみ
        assert data["total"] == 1


class TestAddProjectSourceVideo:
    """POST /api/v1/projects/{project_id}/source-videos のテスト"""

    def test_add_source_video(self, client, sample_project):
        """正常に素材動画を登録できる"""
        r = client.post(
            f"/api/v1/projects/{sample_project}/source-videos",
            json={
                "youtube_url": "https://www.youtube.com/watch?v=abc123XYZ",
                "title": "テスト動画タイトル",
                "quality_status": "good_audio",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["video_id"] == "abc123XYZ"
        assert data["title"] == "テスト動画タイトル"
        assert data["quality_status"] == "good_audio"
        assert data["source"] == "manual"
        assert data["project_id"] == sample_project

    def test_add_short_url(self, client, sample_project):
        """youtu.be短縮URLでも登録できる"""
        r = client.post(
            f"/api/v1/projects/{sample_project}/source-videos",
            json={"youtube_url": "https://youtu.be/shortID123"},
        )
        assert r.status_code == 200
        assert r.json()["video_id"] == "shortID123"

    def test_invalid_url(self, client, sample_project):
        """不正なURLは400エラー"""
        r = client.post(
            f"/api/v1/projects/{sample_project}/source-videos",
            json={"youtube_url": "https://example.com/not-youtube"},
        )
        assert r.status_code == 400

    def test_duplicate_registration(self, client, sample_project):
        """同じ動画の重複登録は409エラー"""
        payload = {"youtube_url": "https://www.youtube.com/watch?v=dupVid"}
        r1 = client.post(f"/api/v1/projects/{sample_project}/source-videos", json=payload)
        assert r1.status_code == 200

        r2 = client.post(f"/api/v1/projects/{sample_project}/source-videos", json=payload)
        assert r2.status_code == 409

    def test_project_not_found(self, client, test_db):
        """存在しないプロジェクトへの登録は404"""
        r = client.post(
            "/api/v1/projects/nonexistent/source-videos",
            json={"youtube_url": "https://www.youtube.com/watch?v=test"},
        )
        assert r.status_code == 404

    def test_add_then_list(self, client, sample_project):
        """登録後にGETで取得できる"""
        client.post(
            f"/api/v1/projects/{sample_project}/source-videos",
            json={"youtube_url": "https://www.youtube.com/watch?v=listed1"},
        )
        client.post(
            f"/api/v1/projects/{sample_project}/source-videos",
            json={"youtube_url": "https://www.youtube.com/watch?v=listed2", "title": "2番目の動画"},
        )

        r = client.get(f"/api/v1/projects/{sample_project}/source-videos")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        video_ids = [v["video_id"] for v in data["videos"]]
        assert "listed1" in video_ids
        assert "listed2" in video_ids

    def test_default_quality_status(self, client, sample_project):
        """quality_statusを省略するとpendingがデフォルト"""
        r = client.post(
            f"/api/v1/projects/{sample_project}/source-videos",
            json={"youtube_url": "https://www.youtube.com/watch?v=defaultQ"},
        )
        assert r.status_code == 200
        assert r.json()["quality_status"] == "pending"


class TestSourceVideoScanEndpoint:
    """POST /api/v1/source-videos/scan のテスト（既存エンドポイント）"""

    def test_scan_dry_run(self, client, test_db):
        """dry_runでスキャンが実行できる（ナレッジファイル依存だがエラーにならない）"""
        r = client.post(
            "/api/v1/source-videos/scan",
            json={"dry_run": True},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["dry_run"] is True
        assert "summary" in data

    def test_status_endpoint(self, client, test_db):
        """素材動画連携の状況サマリーが取得できる"""
        r = client.get("/api/v1/source-videos/status")
        assert r.status_code == 200
        data = r.json()
        assert "linked_count" in data
        assert "total_projects" in data
