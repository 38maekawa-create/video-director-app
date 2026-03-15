"""品質メトリクス統計計算モジュール (quality_stats.py) のテスト

テスト対象:
- QualityStatsCalculator の各メソッド
- キャッシュ動作
- エッジケース（空DB、データなし等）
- APIエンドポイント（強化版）
"""

import json
import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from video_direction.analyzer.quality_stats import (
    QualityStatsCalculator,
    _grade_from_score,
)


# --- ヘルパー ---

def _create_test_db(db_path: Path) -> sqlite3.Connection:
    """テスト用DBを作成してテーブルを初期化"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            guest_name TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'directed',
            shoot_date TEXT,
            quality_score INTEGER,
            has_unsent_feedback INTEGER DEFAULT 0,
            unreviewed_count INTEGER DEFAULT 0,
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
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    return conn


def _insert_project(conn, pid, guest, title, score, shoot_date=None, created_at=None):
    """テスト用プロジェクトを挿入"""
    conn.execute(
        "INSERT INTO projects (id, guest_name, title, quality_score, shoot_date, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (pid, guest, title, score, shoot_date or "2026-03-01",
         created_at or datetime.now().isoformat()),
    )
    conn.commit()


def _insert_feedback(conn, project_id, category, text="テストFB", created_by=None):
    """テスト用フィードバックを挿入"""
    conn.execute(
        "INSERT INTO feedbacks (project_id, category, converted_text, created_by) "
        "VALUES (?, ?, ?, ?)",
        (project_id, category, text, created_by),
    )
    conn.commit()


# --- フィクスチャ ---

@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def db_path(tmp_dir):
    return tmp_dir / "test.db"


@pytest.fixture
def empty_calculator(tmp_dir, db_path):
    """空のDBで初期化したCalculator"""
    _create_test_db(db_path)
    learning_dir = tmp_dir / "learning"
    learning_dir.mkdir()
    return QualityStatsCalculator(db_path=db_path, learning_data_dir=learning_dir)


@pytest.fixture
def populated_calculator(tmp_dir, db_path):
    """テストデータ入りのCalculator"""
    conn = _create_test_db(db_path)

    # プロジェクト10件を異なるスコア・日付で挿入
    base_date = datetime(2026, 1, 1)
    for i in range(10):
        date = (base_date + timedelta(days=i * 15)).strftime("%Y-%m-%d")
        score = 50 + i * 5  # 50, 55, 60, ..., 95
        created = (base_date + timedelta(days=i * 15)).isoformat()
        _insert_project(conn, f"p{i:02d}", f"ゲスト{i}", f"動画{i}", score, date, created)

    # フィードバック（カテゴリ別に挿入）
    categories = ["cutting", "cutting", "cutting", "color", "color",
                   "telop", "telop", "bgm", "camera", "tempo"]
    for i, cat in enumerate(categories):
        _insert_feedback(conn, f"p{i:02d}", cat, f"FB_{cat}_{i}", created_by="編集者A" if i < 5 else "編集者B")

    conn.close()

    learning_dir = tmp_dir / "learning"
    learning_dir.mkdir()

    # テスト用学習ルールを作成
    rules = {
        "rules": [
            {
                "id": "rule_001",
                "rule_text": "カット割りは5秒以内に",
                "category": "cutting",
                "source_pattern_ids": ["pat_001"],
                "priority": "high",
                "applied_count": 15,
                "is_active": True,
                "created_at": (base_date + timedelta(days=60)).isoformat(),
            },
            {
                "id": "rule_002",
                "rule_text": "テロップは3秒以上表示",
                "category": "telop",
                "source_pattern_ids": ["pat_002"],
                "priority": "medium",
                "applied_count": 8,
                "is_active": True,
                "created_at": (base_date + timedelta(days=90)).isoformat(),
            },
            {
                "id": "rule_003",
                "rule_text": "非アクティブルール",
                "category": "bgm",
                "source_pattern_ids": [],
                "priority": "low",
                "applied_count": 0,
                "is_active": False,
                "created_at": (base_date + timedelta(days=30)).isoformat(),
            },
        ],
        "updated_at": datetime.now().isoformat(),
    }
    (learning_dir / "learning_rules.json").write_text(
        json.dumps(rules, ensure_ascii=False), encoding="utf-8"
    )

    return QualityStatsCalculator(db_path=db_path, learning_data_dir=learning_dir)


# === _grade_from_score テスト ===

class TestGradeFromScore:
    """グレード変換のテスト"""

    def test_aplus(self):
        assert _grade_from_score(90) == "A+"
        assert _grade_from_score(100) == "A+"

    def test_a(self):
        assert _grade_from_score(80) == "A"
        assert _grade_from_score(89) == "A"

    def test_bplus(self):
        assert _grade_from_score(70) == "B+"
        assert _grade_from_score(79) == "B+"

    def test_b(self):
        assert _grade_from_score(60) == "B"
        assert _grade_from_score(69) == "B"

    def test_c(self):
        assert _grade_from_score(50) == "C"
        assert _grade_from_score(59) == "C"

    def test_d(self):
        assert _grade_from_score(40) == "D"
        assert _grade_from_score(49) == "D"

    def test_e(self):
        assert _grade_from_score(0) == "E"
        assert _grade_from_score(39) == "E"


# === 空DBテスト ===

class TestEmptyDatabase:
    """データなし時の動作テスト"""

    def test_空DBでproject_trends(self, empty_calculator):
        result = empty_calculator.get_project_trends()
        assert result == []

    def test_空DBでcategory_ranking(self, empty_calculator):
        result = empty_calculator.get_category_problem_ranking()
        assert result == []

    def test_空DBでeditor_profiles(self, empty_calculator):
        result = empty_calculator.get_editor_quality_profiles()
        assert result == []

    def test_空DBでlearning_effects(self, empty_calculator):
        result = empty_calculator.get_learning_rule_effects()
        assert result == []

    def test_空DBでimprovement_stats(self, empty_calculator):
        result = empty_calculator.get_improvement_stats()
        assert result["total_projects"] == 0
        assert result["overall_trend"] == "no_data"

    def test_空DBでmonthly_averages(self, empty_calculator):
        result = empty_calculator.get_monthly_averages()
        assert result == []

    def test_空DBでfull_stats(self, empty_calculator):
        result = empty_calculator.get_full_stats()
        assert result["total_projects"] == 0
        assert result["scored_projects"] == 0
        assert result["average_score"] is None


# === プロジェクト別トレンドテスト ===

class TestProjectTrends:
    """プロジェクト別品質スコアトレンドのテスト"""

    def test_トレンド取得(self, populated_calculator):
        result = populated_calculator.get_project_trends()
        assert len(result) == 10

    def test_日付昇順でソート(self, populated_calculator):
        result = populated_calculator.get_project_trends()
        dates = [r["shoot_date"] for r in result if r["shoot_date"]]
        assert dates == sorted(dates)

    def test_limit制限(self, populated_calculator):
        result = populated_calculator.get_project_trends(limit=3)
        assert len(result) == 3

    def test_レスポンス構造(self, populated_calculator):
        result = populated_calculator.get_project_trends(limit=1)
        item = result[0]
        assert "project_id" in item
        assert "guest_name" in item
        assert "quality_score" in item
        assert "grade" in item
        assert "shoot_date" in item

    def test_グレードが正しく計算される(self, populated_calculator):
        result = populated_calculator.get_project_trends()
        # スコア95のプロジェクト → A+
        high_score = [r for r in result if r["quality_score"] == 95]
        assert high_score[0]["grade"] == "A+"


# === カテゴリ別問題頻度テスト ===

class TestCategoryRanking:
    """カテゴリ別問題頻度ランキングのテスト"""

    def test_ランキング取得(self, populated_calculator):
        result = populated_calculator.get_category_problem_ranking()
        assert len(result) > 0

    def test_頻度降順(self, populated_calculator):
        result = populated_calculator.get_category_problem_ranking()
        counts = [r["count"] for r in result]
        assert counts == sorted(counts, reverse=True)

    def test_cuttingが最多(self, populated_calculator):
        """テストデータではcuttingが3件で最多"""
        result = populated_calculator.get_category_problem_ranking()
        assert result[0]["category"] == "cutting"
        assert result[0]["count"] == 3

    def test_パーセンテージ計算(self, populated_calculator):
        result = populated_calculator.get_category_problem_ranking()
        # 合計パーセンテージは100前後であるべき
        total_pct = sum(r["percentage"] for r in result)
        assert 99.0 <= total_pct <= 101.0

    def test_recent_examplesが含まれる(self, populated_calculator):
        result = populated_calculator.get_category_problem_ranking()
        for item in result:
            assert "recent_examples" in item
            for ex in item["recent_examples"]:
                assert "text" in ex
                assert "project_id" in ex

    def test_limit制限(self, populated_calculator):
        result = populated_calculator.get_category_problem_ranking(limit=2)
        assert len(result) <= 2


# === 編集者別品質テスト ===

class TestEditorProfiles:
    """編集者別品質傾向のテスト"""

    def test_プロファイル取得(self, populated_calculator):
        result = populated_calculator.get_editor_quality_profiles()
        assert len(result) > 0

    def test_レスポンス構造(self, populated_calculator):
        result = populated_calculator.get_editor_quality_profiles()
        for p in result:
            assert "editor_name" in p
            assert "project_count" in p
            assert "average_score" in p
            assert "grade_distribution" in p
            assert "trend" in p
            assert "recent_scores" in p

    def test_平均スコア降順(self, populated_calculator):
        result = populated_calculator.get_editor_quality_profiles()
        avgs = [p["average_score"] for p in result]
        assert avgs == sorted(avgs, reverse=True)

    def test_トレンド値は有効な文字列(self, populated_calculator):
        result = populated_calculator.get_editor_quality_profiles()
        valid_trends = {"improving", "stable", "declining"}
        for p in result:
            assert p["trend"] in valid_trends


# === FB学習ルール効果テスト ===

class TestLearningRuleEffects:
    """FB学習ルールの適用効果測定テスト"""

    def test_効果取得(self, populated_calculator):
        result = populated_calculator.get_learning_rule_effects()
        assert len(result) > 0

    def test_非アクティブルールは除外(self, populated_calculator):
        result = populated_calculator.get_learning_rule_effects()
        rule_ids = [r["rule_id"] for r in result]
        assert "rule_003" not in rule_ids  # is_active=False

    def test_適用回数降順(self, populated_calculator):
        result = populated_calculator.get_learning_rule_effects()
        counts = [r["applied_count"] for r in result]
        assert counts == sorted(counts, reverse=True)

    def test_レスポンス構造(self, populated_calculator):
        result = populated_calculator.get_learning_rule_effects()
        for r in result:
            assert "rule_id" in r
            assert "rule_text" in r
            assert "category" in r
            assert "applied_count" in r
            assert "avg_score_before" in r
            assert "avg_score_after" in r
            assert "effect_delta" in r

    def test_学習ルールファイルなし(self, empty_calculator):
        """learning_rules.jsonが存在しない場合は空リスト"""
        result = empty_calculator.get_learning_rule_effects()
        assert result == []


# === 改善率統計テスト ===

class TestImprovementStats:
    """改善率統計のテスト"""

    def test_統計取得(self, populated_calculator):
        result = populated_calculator.get_improvement_stats()
        assert result["total_projects"] == 10

    def test_前半後半の平均(self, populated_calculator):
        result = populated_calculator.get_improvement_stats()
        assert result["first_half_avg"] is not None
        assert result["second_half_avg"] is not None
        # テストデータはスコアが上昇するので後半の方が高い
        assert result["second_half_avg"] > result["first_half_avg"]

    def test_ベストワースト(self, populated_calculator):
        result = populated_calculator.get_improvement_stats()
        assert result["best_score"] == 95  # 50 + 9*5
        assert result["worst_score"] == 50

    def test_トレンド判定(self, populated_calculator):
        result = populated_calculator.get_improvement_stats()
        # スコアが50→95と上昇しているのでimproving
        assert result["overall_trend"] == "improving"


# === 月別平均テスト ===

class TestMonthlyAverages:
    """月別平均スコアのテスト"""

    def test_月別取得(self, populated_calculator):
        result = populated_calculator.get_monthly_averages()
        assert len(result) > 0

    def test_月順にソート(self, populated_calculator):
        result = populated_calculator.get_monthly_averages()
        months = [r["month"] for r in result]
        assert months == sorted(months)

    def test_レスポンス構造(self, populated_calculator):
        result = populated_calculator.get_monthly_averages()
        for m in result:
            assert "month" in m
            assert "average_score" in m
            assert "count" in m
            assert "min_score" in m
            assert "max_score" in m


# === 総合統計テスト ===

class TestFullStats:
    """総合統計のテスト"""

    def test_全体統計取得(self, populated_calculator):
        result = populated_calculator.get_full_stats()
        assert result["total_projects"] == 10
        assert result["scored_projects"] == 10

    def test_平均スコア(self, populated_calculator):
        result = populated_calculator.get_full_stats()
        # 50+55+60+65+70+75+80+85+90+95 = 725 / 10 = 72.5
        assert result["average_score"] == 72.5

    def test_中央値(self, populated_calculator):
        result = populated_calculator.get_full_stats()
        # 偶数個なので(70+75)/2 = 72.5
        assert result["median_score"] == 72.5

    def test_標準偏差が正の数(self, populated_calculator):
        result = populated_calculator.get_full_stats()
        assert result["score_std_dev"] > 0

    def test_グレード分布の合計(self, populated_calculator):
        result = populated_calculator.get_full_stats()
        total = sum(result["grade_distribution"].values())
        assert total == 10

    def test_サブ統計が含まれる(self, populated_calculator):
        result = populated_calculator.get_full_stats()
        assert "project_trends" in result
        assert "category_ranking" in result
        assert "editor_profiles" in result
        assert "learning_rule_effects" in result
        assert "improvement_stats" in result
        assert "monthly_averages" in result
        assert "generated_at" in result


# === キャッシュテスト ===

class TestCache:
    """キャッシュ動作のテスト"""

    def test_同じ結果がキャッシュされる(self, populated_calculator):
        r1 = populated_calculator.get_project_trends()
        r2 = populated_calculator.get_project_trends()
        assert r1 is r2  # 同一オブジェクト（キャッシュヒット）

    def test_キャッシュ無効化(self, populated_calculator):
        r1 = populated_calculator.get_project_trends()
        populated_calculator.invalidate_cache()
        r2 = populated_calculator.get_project_trends()
        assert r1 is not r2  # 異なるオブジェクト（キャッシュミス）
        assert r1 == r2  # 内容は同じ

    def test_異なるメソッドは独立キャッシュ(self, populated_calculator):
        t = populated_calculator.get_project_trends()
        c = populated_calculator.get_category_problem_ranking()
        assert t is not c


# === エッジケーステスト ===

class TestEdgeCases:
    """エッジケースのテスト"""

    def test_スコアなしプロジェクトのみ(self, tmp_dir, db_path):
        """quality_scoreがNULLのプロジェクトのみの場合"""
        conn = _create_test_db(db_path)
        conn.execute(
            "INSERT INTO projects (id, guest_name, title) VALUES (?, ?, ?)",
            ("p_null", "テスト", "タイトル"),
        )
        conn.commit()
        conn.close()

        calc = QualityStatsCalculator(db_path=db_path, learning_data_dir=tmp_dir / "learning")
        result = calc.get_full_stats()
        assert result["total_projects"] == 1
        assert result["scored_projects"] == 0
        assert result["average_score"] is None

    def test_スコア全件同じ(self, tmp_dir, db_path):
        """全プロジェクトが同じスコアの場合"""
        conn = _create_test_db(db_path)
        for i in range(5):
            _insert_project(conn, f"same_{i}", f"ゲスト{i}", f"動画{i}", 70, f"2026-0{i+1}-01")
        conn.close()

        calc = QualityStatsCalculator(db_path=db_path, learning_data_dir=tmp_dir / "learning")
        result = calc.get_full_stats()
        assert result["average_score"] == 70.0
        assert result["score_std_dev"] == 0.0
        stats = calc.get_improvement_stats()
        assert stats["overall_trend"] == "stable"

    def test_プロジェクト1件のみ(self, tmp_dir, db_path):
        """プロジェクトが1件だけの場合"""
        conn = _create_test_db(db_path)
        _insert_project(conn, "solo", "テスト", "テスト動画", 85)
        conn.close()

        calc = QualityStatsCalculator(db_path=db_path, learning_data_dir=tmp_dir / "learning")
        result = calc.get_full_stats()
        assert result["scored_projects"] == 1
        assert result["average_score"] == 85.0
        assert result["median_score"] == 85.0

    def test_学習ルールJSON破損(self, tmp_dir, db_path):
        """learning_rules.jsonが壊れている場合"""
        conn = _create_test_db(db_path)
        _insert_project(conn, "p1", "テスト", "テスト動画", 70)
        conn.close()

        learning_dir = tmp_dir / "learning"
        learning_dir.mkdir()
        (learning_dir / "learning_rules.json").write_text("{ broken <<<")

        calc = QualityStatsCalculator(db_path=db_path, learning_data_dir=learning_dir)
        result = calc.get_learning_rule_effects()
        assert result == []

    def test_shoot_dateなしプロジェクト(self, tmp_dir, db_path):
        """shoot_dateがNULLのプロジェクトは月別集計から除外"""
        conn = _create_test_db(db_path)
        conn.execute(
            "INSERT INTO projects (id, guest_name, title, quality_score) "
            "VALUES (?, ?, ?, ?)",
            ("no_date", "テスト", "日付なし", 80),
        )
        conn.commit()
        conn.close()

        calc = QualityStatsCalculator(db_path=db_path, learning_data_dir=tmp_dir / "learning")
        monthly = calc.get_monthly_averages()
        assert len(monthly) == 0  # shoot_dateがないので月別には出ない

    def test_カテゴリ空文字のFBは除外(self, tmp_dir, db_path):
        """categoryが空文字のフィードバックはランキングから除外"""
        conn = _create_test_db(db_path)
        _insert_project(conn, "p1", "テスト", "テスト動画", 70)
        conn.execute(
            "INSERT INTO feedbacks (project_id, category, converted_text) VALUES (?, ?, ?)",
            ("p1", "", "空カテゴリFB"),
        )
        conn.execute(
            "INSERT INTO feedbacks (project_id, category, converted_text) VALUES (?, ?, ?)",
            ("p1", None, "NULLカテゴリFB"),
        )
        conn.execute(
            "INSERT INTO feedbacks (project_id, category, converted_text) VALUES (?, ?, ?)",
            ("p1", "cutting", "有効なFB"),
        )
        conn.commit()
        conn.close()

        calc = QualityStatsCalculator(db_path=db_path, learning_data_dir=tmp_dir / "learning")
        ranking = calc.get_category_problem_ranking()
        assert len(ranking) == 1
        assert ranking[0]["category"] == "cutting"


# === APIエンドポイントテスト ===

class TestQualityStatsAPI:
    """APIエンドポイント（強化版）の疎通テスト"""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from fastapi.testclient import TestClient
        from src.video_direction.integrations.api_server import app
        self.client = TestClient(app)

    def test_full_stats_endpoint(self):
        resp = self.client.get("/api/v1/dashboard/quality/full")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_projects" in data
        assert "scored_projects" in data
        assert "grade_distribution" in data

    def test_project_trends_endpoint(self):
        resp = self.client.get("/api/v1/dashboard/quality/project-trends")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_project_trends_with_limit(self):
        resp = self.client.get("/api/v1/dashboard/quality/project-trends?limit=5")
        assert resp.status_code == 200
        assert len(resp.json()) <= 5

    def test_category_ranking_endpoint(self):
        resp = self.client.get("/api/v1/dashboard/quality/category-ranking")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_editor_profiles_endpoint(self):
        resp = self.client.get("/api/v1/dashboard/quality/editor-profiles")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_learning_effects_endpoint(self):
        resp = self.client.get("/api/v1/dashboard/quality/learning-effects")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_improvement_endpoint(self):
        resp = self.client.get("/api/v1/dashboard/quality/improvement")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_projects" in data
        assert "overall_trend" in data

    def test_monthly_endpoint(self):
        resp = self.client.get("/api/v1/dashboard/quality/monthly")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_既存エンドポイントが壊れていない(self):
        """既存の /api/v1/dashboard/quality が正常に動作する"""
        resp = self.client.get("/api/v1/dashboard/quality")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_scored" in data
        assert "grade_distribution" in data

    def test_既存summaryが壊れていない(self):
        """既存の /api/dashboard/summary が正常に動作する"""
        resp = self.client.get("/api/dashboard/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_projects" in data

    def test_既存quality_trendが壊れていない(self):
        """既存の /api/dashboard/quality-trend が正常に動作する"""
        resp = self.client.get("/api/dashboard/quality-trend")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
