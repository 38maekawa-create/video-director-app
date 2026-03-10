"""B-2: 品質トラッキングダッシュボードのテスト"""
import pytest
import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from video_direction.tracker.quality_dashboard import (
    QualityDashboard,
    QualitySnapshot,
    VideoQualityRecord,
    DashboardSummary,
)


@pytest.fixture
def tmp_dir():
    """テスト用一時ディレクトリ"""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def dashboard(tmp_dir):
    """テスト用ダッシュボードインスタンス"""
    return QualityDashboard(data_dir=tmp_dir)


# === 基本テスト ===

class TestQualityDashboardBasic:
    """ダッシュボードの基本テスト"""

    def test_初期化(self, dashboard):
        assert isinstance(dashboard, QualityDashboard)
        assert len(dashboard.records) == 0

    def test_品質記録の登録(self, dashboard):
        record = dashboard.record_quality(
            video_id="test_001",
            guest_name="テストさん",
            video_title="テスト動画",
            stage="draft",
            total_score=65.0,
            grade="B",
        )
        assert record.video_id == "test_001"
        assert record.guest_name == "テストさん"
        assert len(record.snapshots) == 1
        assert record.snapshots[0].stage == "draft"
        assert record.snapshots[0].total_score == 65.0

    def test_同一動画に複数スナップショット(self, dashboard):
        dashboard.record_quality(
            video_id="test_001", guest_name="テスト", video_title="テスト",
            stage="draft", total_score=60.0, grade="C",
        )
        dashboard.record_quality(
            video_id="test_001", guest_name="テスト", video_title="テスト",
            stage="revision_1", total_score=75.0, grade="B",
        )
        record = dashboard.get_record("test_001")
        assert len(record.snapshots) == 2
        assert record.snapshots[0].stage_label == "初稿"
        assert record.snapshots[1].stage_label == "修正1"

    def test_dimension_scoresの保存(self, dashboard):
        dims = {"cut": 70, "color": 65, "telop": 80}
        dashboard.record_quality(
            video_id="test_001", guest_name="テスト", video_title="テスト",
            stage="draft", total_score=71.7, grade="B",
            dimension_scores=dims,
        )
        record = dashboard.get_record("test_001")
        assert record.snapshots[0].dimension_scores == dims

    def test_編集者情報の保存(self, dashboard):
        dashboard.record_quality(
            video_id="test_001", guest_name="テスト", video_title="テスト",
            stage="draft", total_score=70.0, grade="B",
            editor="パグさん",
        )
        record = dashboard.get_record("test_001")
        assert record.editor == "パグさん"


# === 永続化テスト ===

class TestPersistence:
    """データ永続化のテスト"""

    def test_保存と読み込み(self, tmp_dir):
        # 保存
        db1 = QualityDashboard(data_dir=tmp_dir)
        db1.record_quality(
            video_id="persist_test", guest_name="テスト", video_title="テスト",
            stage="draft", total_score=70.0, grade="B",
        )

        # 新しいインスタンスで読み込み
        db2 = QualityDashboard(data_dir=tmp_dir)
        record = db2.get_record("persist_test")
        assert record is not None
        assert record.guest_name == "テスト"
        assert record.snapshots[0].total_score == 70.0

    def test_データファイルがJSONで保存される(self, tmp_dir):
        db = QualityDashboard(data_dir=tmp_dir)
        db.record_quality(
            video_id="json_test", guest_name="テスト", video_title="テスト",
            stage="draft", total_score=70.0, grade="B",
        )
        data_file = Path(tmp_dir) / "quality_dashboard.json"
        assert data_file.exists()
        data = json.loads(data_file.read_text())
        assert "records" in data
        assert "json_test" in data["records"]

    def test_clear_allでデータ消去(self, dashboard):
        dashboard.record_quality(
            video_id="clear_test", guest_name="テスト", video_title="テスト",
            stage="draft", total_score=70.0, grade="B",
        )
        dashboard.clear_all()
        assert len(dashboard.records) == 0


# === 改善率テスト ===

class TestImprovementRate:
    """改善率計算のテスト"""

    def test_改善率の計算(self, dashboard):
        dashboard.record_quality(
            video_id="improve_test", guest_name="テスト", video_title="テスト",
            stage="draft", total_score=60.0, grade="C",
        )
        dashboard.record_quality(
            video_id="improve_test", guest_name="テスト", video_title="テスト",
            stage="final", total_score=90.0, grade="S",
        )
        record = dashboard.get_record("improve_test")
        assert record.improvement_rate == 50.0  # (90-60)/60*100

    def test_スナップショット1つでは改善率0(self, dashboard):
        dashboard.record_quality(
            video_id="single_test", guest_name="テスト", video_title="テスト",
            stage="draft", total_score=70.0, grade="B",
        )
        record = dashboard.get_record("single_test")
        assert record.improvement_rate == 0.0


# === サマリーテスト ===

class TestDashboardSummary:
    """ダッシュボードサマリーのテスト"""

    def test_空のサマリー(self, dashboard):
        summary = dashboard.get_summary()
        assert isinstance(summary, DashboardSummary)
        assert summary.total_videos == 0

    def test_サマリーの集計(self, dashboard):
        dashboard.record_quality(
            video_id="v1", guest_name="A", video_title="動画A",
            stage="draft", total_score=80.0, grade="A", editor="編集者X",
        )
        dashboard.record_quality(
            video_id="v2", guest_name="B", video_title="動画B",
            stage="draft", total_score=60.0, grade="C", editor="編集者Y",
        )
        summary = dashboard.get_summary()
        assert summary.total_videos == 2
        assert summary.average_score == 70.0
        assert "A" in summary.grade_distribution
        assert "C" in summary.grade_distribution

    def test_top_performersとneeds_improvement(self, dashboard):
        for i, score in enumerate([90, 80, 70, 60, 50]):
            grade = "S" if score >= 90 else "A" if score >= 80 else "B" if score >= 65 else "C"
            dashboard.record_quality(
                video_id=f"v{i}", guest_name=f"ゲスト{i}", video_title=f"動画{i}",
                stage="draft", total_score=float(score), grade=grade,
            )
        summary = dashboard.get_summary()
        assert summary.top_performers[0]["score"] == 90
        assert summary.needs_improvement[-1]["score"] == 50

    def test_editor_stats(self, dashboard):
        dashboard.record_quality(
            video_id="v1", guest_name="A", video_title="1",
            stage="draft", total_score=80.0, grade="A", editor="パグ",
        )
        dashboard.record_quality(
            video_id="v2", guest_name="B", video_title="2",
            stage="draft", total_score=70.0, grade="B", editor="パグ",
        )
        summary = dashboard.get_summary()
        assert "パグ" in summary.editor_stats
        assert summary.editor_stats["パグ"]["avg_score"] == 75.0
        assert summary.editor_stats["パグ"]["count"] == 2


# === タイムラインテスト ===

class TestTimeline:
    """品質スコア時系列のテスト"""

    def test_タイムライン取得(self, dashboard):
        dashboard.record_quality(
            video_id="tl_test", guest_name="テスト", video_title="テスト",
            stage="draft", total_score=60.0, grade="C",
        )
        dashboard.record_quality(
            video_id="tl_test", guest_name="テスト", video_title="テスト",
            stage="revision_1", total_score=75.0, grade="B",
        )
        dashboard.record_quality(
            video_id="tl_test", guest_name="テスト", video_title="テスト",
            stage="final", total_score=85.0, grade="A",
        )
        timeline = dashboard.get_timeline("tl_test")
        assert len(timeline) == 3
        assert timeline[0]["stage"] == "初稿"
        assert timeline[1]["stage"] == "修正1"
        assert timeline[2]["stage"] == "完成版"
        assert timeline[2]["score"] == 85.0

    def test_存在しない動画のタイムライン(self, dashboard):
        timeline = dashboard.get_timeline("nonexistent")
        assert timeline == []


# === 編集者ランキングテスト ===

class TestEditorRanking:
    """編集者ランキングのテスト"""

    def test_ランキング生成(self, dashboard):
        dashboard.record_quality(
            video_id="v1", guest_name="A", video_title="1",
            stage="draft", total_score=90.0, grade="S", editor="編集者A",
        )
        dashboard.record_quality(
            video_id="v2", guest_name="B", video_title="2",
            stage="draft", total_score=70.0, grade="B", editor="編集者B",
        )
        ranking = dashboard.get_editor_ranking()
        assert len(ranking) == 2
        assert ranking[0]["editor"] == "編集者A"  # スコア高い方が上位
        assert ranking[0]["avg_score"] == 90.0

    def test_編集者なしの動画はランキングに含まれない(self, dashboard):
        dashboard.record_quality(
            video_id="v1", guest_name="A", video_title="1",
            stage="draft", total_score=70.0, grade="B",
        )
        ranking = dashboard.get_editor_ranking()
        assert len(ranking) == 0


# === VideoQualityRecord メソッドテスト ===

class TestVideoQualityRecord:
    """VideoQualityRecordのメソッドテスト"""

    def test_latest_snapshot(self):
        record = VideoQualityRecord(
            video_id="test", guest_name="テスト", video_title="テスト",
            created_at="2026-01-01", updated_at="2026-01-02",
            snapshots=[
                QualitySnapshot("2026-01-01", "draft", "初稿", 60.0, "C"),
                QualitySnapshot("2026-01-02", "final", "完成版", 85.0, "A"),
            ],
        )
        latest = record.latest_snapshot()
        assert latest.stage == "final"
        assert latest.total_score == 85.0

    def test_latest_snapshot_空(self):
        record = VideoQualityRecord(
            video_id="test", guest_name="テスト", video_title="テスト",
            created_at="2026-01-01", updated_at="2026-01-01",
        )
        assert record.latest_snapshot() is None

    def test_calculate_improvement_rate(self):
        record = VideoQualityRecord(
            video_id="test", guest_name="テスト", video_title="テスト",
            created_at="2026-01-01", updated_at="2026-01-02",
            snapshots=[
                QualitySnapshot("2026-01-01", "draft", "初稿", 50.0, "C"),
                QualitySnapshot("2026-01-02", "final", "完成版", 75.0, "B"),
            ],
        )
        rate = record.calculate_improvement_rate()
        assert rate == 50.0  # (75-50)/50*100
