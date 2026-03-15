"""P1: 編集後フィードバック APIエンドポイントのテスト

テスト対象:
- POST /api/v1/projects/{project_id}/edit-feedback
- _compute_edit_feedback（インライン計算関数）
- _grade_from_score（グレード変換）
"""

import json
import pytest
from fastapi.testclient import TestClient

from src.video_direction.integrations.api_server import app, _grade_from_score, _compute_edit_feedback


# --- テストクライアント ---

client = TestClient(app)


# --- _grade_from_score ユニットテスト ---

class TestGradeFromScore:
    def test_aplus(self):
        assert _grade_from_score(9.5) == "A+"

    def test_a(self):
        assert _grade_from_score(8.5) == "A"

    def test_bplus(self):
        assert _grade_from_score(7.5) == "B+"

    def test_b(self):
        assert _grade_from_score(6.5) == "B"

    def test_c(self):
        assert _grade_from_score(5.0) == "C"

    def test_d(self):
        assert _grade_from_score(4.0) == "D"

    def test_e(self):
        assert _grade_from_score(2.0) == "E"

    def test_boundary_a(self):
        """境界値: 8.0 は "A"（9.0未満）"""
        assert _grade_from_score(8.0) == "A"

    def test_boundary_bplus(self):
        """境界値: 7.0 は "B+"（8.0未満）"""
        assert _grade_from_score(7.0) == "B+"


# --- _compute_edit_feedback ユニットテスト ---

class TestComputeEditFeedback:

    def _make_row(self, project_id="test_p1", title="テスト動画"):
        """SQLite Row を dict で代替"""
        return {"id": project_id, "title": title}

    def _make_request(self, **kwargs):
        """EditFeedbackRequest 相当の dict をオブジェクト化"""
        from src.video_direction.integrations.api_server import EditFeedbackRequest
        return EditFeedbackRequest(**kwargs)

    def test_empty_request_returns_default(self):
        """メタデータなしでもデフォルトスコアが返る"""
        row = self._make_row()
        req = self._make_request()
        result = _compute_edit_feedback(row, req)
        assert result["quality_score"] == 5.0
        assert result["grade"] == "C"
        assert len(result["content_feedback"]) >= 1

    def test_good_compression_ratio(self):
        """圧縮率40%（理想範囲）→ 高スコア"""
        row = self._make_row()
        req = self._make_request(
            duration_seconds=1200,          # 20分
            original_duration_seconds=3000, # 50分
        )
        result = _compute_edit_feedback(row, req)
        assert result["quality_score"] >= 8.0
        # 良好フィードバックが含まれる
        categories = [f["category"] for f in result["content_feedback"]]
        assert "positive" in categories

    def test_too_little_editing(self):
        """圧縮率90%（ほぼ無編集）→ 低スコア"""
        row = self._make_row()
        req = self._make_request(
            duration_seconds=2700,          # 45分
            original_duration_seconds=3000, # 50分
        )
        result = _compute_edit_feedback(row, req)
        assert result["quality_score"] <= 5.0
        categories = [f["category"] for f in result["content_feedback"]]
        assert "critical" in categories

    def test_high_highlight_rate(self):
        """ハイライト採用率80%→ 高密度フィードバック"""
        row = self._make_row()
        req = self._make_request(
            included_timestamps=["02:00", "05:00", "08:00", "10:00"],
            excluded_timestamps=["15:00"],
        )
        result = _compute_edit_feedback(row, req)
        hl = result["highlight_check"]
        assert hl["included"] == 4
        assert hl["excluded"] == 1
        assert hl["inclusion_rate"] == pytest.approx(0.8, abs=0.01)

    def test_low_highlight_rate(self):
        """ハイライト採用率20%→ 要改善フィードバック"""
        row = self._make_row()
        req = self._make_request(
            included_timestamps=["02:00"],
            excluded_timestamps=["05:00", "08:00", "10:00", "15:00"],
        )
        result = _compute_edit_feedback(row, req)
        cats = [f["category"] for f in result["content_feedback"]]
        assert "critical" in cats

    def test_chronological_scene_order(self):
        """時系列順シーン→ 構成力ポジティブ評価"""
        row = self._make_row()
        req = self._make_request(
            scene_order=["01:00", "03:00", "06:00", "10:00"]
        )
        result = _compute_edit_feedback(row, req)
        comp_items = [f for f in result["content_feedback"] if f["area"] == "構成力"]
        assert len(comp_items) > 0
        assert comp_items[0]["category"] == "positive"

    def test_response_structure(self):
        """レスポンスの全必須フィールドが含まれる"""
        row = self._make_row()
        req = self._make_request(editor_name="テスト編集者", stage="revision_1")
        result = _compute_edit_feedback(row, req)

        required_keys = [
            "project_id", "quality_score", "grade", "content_feedback",
            "telop_check", "highlight_check", "direction_adherence",
            "summary", "editor_name", "stage", "generated_at",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

        # テロップチェック構造
        assert "error_count" in result["telop_check"]
        assert "warning_count" in result["telop_check"]

        # ハイライトチェック構造
        hl = result["highlight_check"]
        assert "total" in hl
        assert "included" in hl
        assert "excluded" in hl
        assert "inclusion_rate" in hl

    def test_editor_name_and_stage_propagated(self):
        """editor_name と stage がレスポンスに反映される"""
        row = self._make_row()
        req = self._make_request(editor_name="山田太郎", stage="final")
        result = _compute_edit_feedback(row, req)
        assert result["editor_name"] == "山田太郎"
        assert result["stage"] == "final"


# --- APIエンドポイント 統合テスト ---

class TestEditFeedbackEndpoint:

    def setup_method(self):
        """各テスト前にプロジェクトをDBに登録"""
        client.post("/api/projects", json={
            "id": "test_ef_project",
            "guest_name": "テストゲスト",
            "title": "テスト対談動画",
            "status": "review_pending",
        })

    def teardown_method(self):
        """テスト後の後片付けは不要（テストDBは揮発性）"""
        pass

    def test_endpoint_returns_200(self):
        """正常リクエストで200が返る"""
        response = client.post(
            "/api/v1/projects/test_ef_project/edit-feedback",
            json={}
        )
        assert response.status_code == 200

    def test_endpoint_response_has_required_fields(self):
        """レスポンスに必須フィールドが含まれる"""
        response = client.post(
            "/api/v1/projects/test_ef_project/edit-feedback",
            json={
                "duration_seconds": 600,
                "original_duration_seconds": 2700,
                "included_timestamps": ["02:00", "05:00"],
                "excluded_timestamps": ["10:00"],
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "test_ef_project"
        assert "quality_score" in data
        assert "grade" in data
        assert isinstance(data["content_feedback"], list)
        assert "telop_check" in data
        assert "highlight_check" in data
        assert "summary" in data

    def test_endpoint_404_for_unknown_project(self):
        """存在しないプロジェクトで404が返る"""
        response = client.post(
            "/api/v1/projects/nonexistent_project_id/edit-feedback",
            json={}
        )
        assert response.status_code == 404

    def test_endpoint_with_full_metadata(self):
        """全フィールド指定でのリクエスト"""
        response = client.post(
            "/api/v1/projects/test_ef_project/edit-feedback",
            json={
                "duration_seconds": 900,
                "original_duration_seconds": 2700,
                "included_timestamps": ["02:00", "05:00", "08:00"],
                "excluded_timestamps": ["12:00"],
                "telop_texts": ["年収1200万", "TEKOで変わった"],
                "scene_order": ["02:00", "05:00", "08:00"],
                "editor_name": "山田太郎",
                "stage": "revision_1",
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["editor_name"] == "山田太郎"
        assert data["stage"] == "revision_1"
        # 圧縮率33% → 適切なテンポ → positiveまたはimprovement
        score = data["quality_score"]
        assert 0.0 <= score <= 10.0

    def test_grade_is_valid_string(self):
        """gradeフィールドが有効な文字列"""
        valid_grades = {"A+", "A", "B+", "B", "C", "D", "E"}
        response = client.post(
            "/api/v1/projects/test_ef_project/edit-feedback",
            json={"duration_seconds": 600, "original_duration_seconds": 1500}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["grade"] in valid_grades
