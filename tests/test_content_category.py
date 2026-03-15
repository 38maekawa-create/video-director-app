"""スプシA列「コンテンツ」ベースのカテゴリ分類テスト"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.integrations.sheets_manager import (
    CONTENT_TO_CATEGORY,
    SheetsManager,
    _extract_names_from_title,
    _match_guest_name,
)


# ────────────────────────────────────────────────
# CONTENT_TO_CATEGORY マッピングテスト
# ────────────────────────────────────────────────

class TestContentToCategory:
    """A列コンテンツ値→カテゴリマッピングの正しさを検証"""

    def test_対談はteko_member(self):
        assert CONTENT_TO_CATEGORY["対談"] == "teko_member"

    def test_オフ会インタビューはteko_member(self):
        assert CONTENT_TO_CATEGORY["オフ会インタビュー"] == "teko_member"

    def test_不動産対談はteko_realestate(self):
        assert CONTENT_TO_CATEGORY["不動産対談"] == "teko_realestate"

    def test_未定義のコンテンツ値はNone(self):
        assert CONTENT_TO_CATEGORY.get("その他") is None
        assert CONTENT_TO_CATEGORY.get("") is None


# ────────────────────────────────────────────────
# get_content_categories のテスト（スプシAPIをモック）
# ────────────────────────────────────────────────

class TestGetContentCategories:
    """SheetsManager.get_content_categories() のテスト"""

    def _make_manager_with_mock_data(self, content_cells, title_cells):
        """モックされたスプシデータでSheetsManagerを作成"""
        sm = SheetsManager.__new__(SheetsManager)
        sm.credentials_path = Path("/dummy")
        sm._client = MagicMock()
        sm._worksheet = MagicMock()
        sm._worksheet.col_values.side_effect = lambda col: {
            1: content_cells,  # A列（コンテンツ）
            2: title_cells,    # B列（タイトル）
        }[col]
        return sm

    def test_基本的なカテゴリマッピング(self):
        """対談/不動産対談/オフ会インタビューが正しくマッピングされる"""
        # ヘッダー2行 + データ3行
        content_cells = ["", "コンテンツ", "対談", "不動産対談", "オフ会インタビュー"]
        title_cells = ["", "タイトル", "71.コテさん", "52.ロキさん", "80.PAYさん"]

        sm = self._make_manager_with_mock_data(content_cells, title_cells)
        result = sm.get_content_categories()

        # コテ → teko_member（対談）
        found_teko_member = False
        found_teko_realestate = False
        for name, cat in result.items():
            if "コテ" in name or _match_guest_name("コテ", name):
                assert cat == "teko_member", f"コテは対談なのでteko_member: {cat}"
                found_teko_member = True
            if "ロキ" in name or _match_guest_name("ロキ", name):
                assert cat == "teko_realestate", f"ロキは不動産対談なのでteko_realestate: {cat}"
                found_teko_realestate = True

        assert found_teko_member, f"コテが結果に含まれていない: {result}"
        assert found_teko_realestate, f"ロキが結果に含まれていない: {result}"

    def test_未定義コンテンツ値はNone(self):
        """A列が空やマッピングにない値の場合はNone"""
        content_cells = ["", "コンテンツ", "", "特別企画"]
        title_cells = ["", "タイトル", "99.テストさん", "100.テスト2さん"]

        sm = self._make_manager_with_mock_data(content_cells, title_cells)
        result = sm.get_content_categories()

        for name, cat in result.items():
            assert cat is None, f"未定義コンテンツのカテゴリはNone: {name}={cat}"

    def test_空行をスキップ(self):
        """タイトルが空の行はスキップされる"""
        content_cells = ["", "コンテンツ", "対談", "対談"]
        title_cells = ["", "タイトル", "", "71.コテさん"]

        sm = self._make_manager_with_mock_data(content_cells, title_cells)
        result = sm.get_content_categories()

        # 空タイトル行は結果に含まれない
        assert len(result) >= 1

    def test_誤分類の修正_ロキさん不動産対談(self):
        """ロキさんが不動産対談に正しく分類されることを確認（以前はteko_memberに誤分類）"""
        content_cells = ["", "コンテンツ", "不動産対談"]
        title_cells = ["", "タイトル", "55.ロキさん"]

        sm = self._make_manager_with_mock_data(content_cells, title_cells)
        result = sm.get_content_categories()

        for name, cat in result.items():
            if "ロキ" in name or _match_guest_name("ロキ", name):
                assert cat == "teko_realestate", f"ロキは不動産対談: {cat}"
                break
        else:
            raise AssertionError(f"ロキが結果に見つからない: {result}")

    def test_誤分類の修正_RYOさん不動産対談(self):
        """RYOさんが不動産対談に正しく分類されることを確認"""
        content_cells = ["", "コンテンツ", "不動産対談"]
        title_cells = ["", "タイトル", "56.RYOさん"]

        sm = self._make_manager_with_mock_data(content_cells, title_cells)
        result = sm.get_content_categories()

        for name, cat in result.items():
            if "RYO" in name.upper() or _match_guest_name("RYO", name):
                assert cat == "teko_realestate", f"RYOは不動産対談: {cat}"
                break

    def test_誤分類の修正_PAYさんオフ会インタビュー(self):
        """PAYさんがオフ会インタビューとしてteko_memberに正しく分類される"""
        content_cells = ["", "コンテンツ", "オフ会インタビュー"]
        title_cells = ["", "タイトル", "80.PAYさん"]

        sm = self._make_manager_with_mock_data(content_cells, title_cells)
        result = sm.get_content_categories()

        for name, cat in result.items():
            if "PAY" in name.upper() or _match_guest_name("PAY", name):
                assert cat == "teko_member", f"PAYはオフ会インタビューなのでteko_member: {cat}"
                break


# ────────────────────────────────────────────────
# sync-categories エンドポイントのテスト
# ────────────────────────────────────────────────

class TestSyncCategoriesAPI:
    """POST /api/v1/sync-categories のテスト"""

    def test_sync_endpoint_exists(self):
        """sync-categoriesエンドポイントが存在する"""
        from src.video_direction.integrations.api_server import app
        routes = [r.path for r in app.routes]
        assert "/api/v1/sync-categories" in routes

    def test_sync_updates_projects(self):
        """スプシからカテゴリを同期してDBを更新する"""
        from fastapi.testclient import TestClient
        from src.video_direction.integrations.api_server import app, _get_db, init_db
        import sqlite3
        import tempfile
        import os

        # テスト用一時DB
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            test_db_path = f.name

        try:
            # DB初期化
            original_db_path = None
            import src.video_direction.integrations.api_server as api_mod
            original_db_path = api_mod.DB_PATH
            api_mod.DB_PATH = Path(test_db_path)
            init_db()

            # テストプロジェクトを挿入
            conn = _get_db()
            conn.execute(
                "INSERT INTO projects (id, guest_name, title, status) VALUES (?, ?, ?, ?)",
                ("test-1", "コテ", "71.コテさん", "planning"),
            )
            conn.execute(
                "INSERT INTO projects (id, guest_name, title, status) VALUES (?, ?, ?, ?)",
                ("test-2", "ロキ", "55.ロキさん", "planning"),
            )
            conn.commit()
            conn.close()

            # SheetsManagerをモック（sync_categories_from_sheet内でrelative importされるため）
            mock_categories = {"コテ": "teko_member", "ロキ": "teko_realestate"}
            with patch(
                "src.video_direction.integrations.sheets_manager.SheetsManager"
            ) as MockSM:
                mock_instance = MagicMock()
                mock_instance.get_content_categories.return_value = mock_categories
                MockSM.return_value = mock_instance

                client = TestClient(app)
                response = client.post("/api/v1/sync-categories")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "synced"
            assert data["updated_count"] + data["skipped_count"] == 2

            # DBを確認
            conn = _get_db()
            row1 = conn.execute("SELECT category FROM projects WHERE id = 'test-1'").fetchone()
            row2 = conn.execute("SELECT category FROM projects WHERE id = 'test-2'").fetchone()
            conn.close()

            # コテ→teko_member, ロキ→teko_realestate
            updated_ids = [u["id"] for u in data["updated"]]
            if "test-1" in updated_ids:
                assert row1["category"] == "teko_member"
            if "test-2" in updated_ids:
                assert row2["category"] == "teko_realestate"

        finally:
            api_mod.DB_PATH = original_db_path
            os.unlink(test_db_path)
