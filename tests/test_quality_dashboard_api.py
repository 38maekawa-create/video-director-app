"""P2: 品質ダッシュボード実データ連動 APIエンドポイントのテスト

テスト対象:
- GET /api/v1/dashboard/quality
- _grade_from_score_100（0-100スケールグレード変換）
"""

import pytest
from fastapi.testclient import TestClient

from src.video_direction.integrations.api_server import app, _grade_from_score_100


# --- テストクライアント ---

client = TestClient(app)


# --- _grade_from_score_100 ユニットテスト ---

class TestGradeFromScore100:
    """0-100スケールのグレード変換テスト"""

    def test_aplus_boundary(self):
        assert _grade_from_score_100(90) == "A+"

    def test_aplus_max(self):
        assert _grade_from_score_100(100) == "A+"

    def test_a_lower(self):
        assert _grade_from_score_100(80) == "A"

    def test_a_upper(self):
        assert _grade_from_score_100(89) == "A"

    def test_bplus_lower(self):
        assert _grade_from_score_100(70) == "B+"

    def test_bplus_upper(self):
        assert _grade_from_score_100(79) == "B+"

    def test_b_lower(self):
        assert _grade_from_score_100(60) == "B"

    def test_b_upper(self):
        assert _grade_from_score_100(69) == "B"

    def test_c(self):
        assert _grade_from_score_100(55) == "C"

    def test_d(self):
        assert _grade_from_score_100(40) == "D"

    def test_e(self):
        assert _grade_from_score_100(0) == "E"

    def test_e_upper(self):
        assert _grade_from_score_100(39) == "E"


# --- /api/v1/dashboard/quality エンドポイントテスト ---

class TestQualityDashboardEndpoint:
    """GET /api/v1/dashboard/quality のレスポンス構造テスト"""

    def test_status_200(self):
        resp = client.get("/api/v1/dashboard/quality")
        assert resp.status_code == 200

    def test_response_has_required_fields(self):
        resp = client.get("/api/v1/dashboard/quality")
        data = resp.json()
        assert "total_scored" in data
        assert "total_unscored" in data
        assert "grade_distribution" in data
        assert "recent_trend" in data

    def test_grade_distribution_has_all_grades(self):
        resp = client.get("/api/v1/dashboard/quality")
        data = resp.json()
        dist = data["grade_distribution"]
        expected_grades = {"A+", "A", "B+", "B", "C", "D", "E"}
        assert expected_grades == set(dist.keys())

    def test_grade_distribution_counts_are_non_negative(self):
        resp = client.get("/api/v1/dashboard/quality")
        data = resp.json()
        for grade, count in data["grade_distribution"].items():
            assert count >= 0, f"グレード {grade} のカウントが負: {count}"

    def test_total_scored_matches_distribution_sum(self):
        resp = client.get("/api/v1/dashboard/quality")
        data = resp.json()
        dist_total = sum(data["grade_distribution"].values())
        assert dist_total == data["total_scored"]

    def test_recent_trend_is_list(self):
        resp = client.get("/api/v1/dashboard/quality")
        data = resp.json()
        assert isinstance(data["recent_trend"], list)

    def test_recent_trend_max_5_items(self):
        resp = client.get("/api/v1/dashboard/quality")
        data = resp.json()
        assert len(data["recent_trend"]) <= 5

    def test_recent_trend_items_have_required_fields(self):
        resp = client.get("/api/v1/dashboard/quality")
        data = resp.json()
        for item in data["recent_trend"]:
            assert "guest_name" in item
            assert "shoot_date" in item
            assert "quality_score" in item

    def test_average_score_is_numeric_or_null(self):
        resp = client.get("/api/v1/dashboard/quality")
        data = resp.json()
        avg = data.get("average_score")
        assert avg is None or isinstance(avg, (int, float))

    def test_improvement_delta_is_numeric_or_null(self):
        resp = client.get("/api/v1/dashboard/quality")
        data = resp.json()
        delta = data.get("improvement_delta")
        assert delta is None or isinstance(delta, (int, float))
