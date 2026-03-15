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


# === 永続化エッジケーステスト ===

class TestPersistenceEdgeCases:
    """品質スコア永続化のエッジケーステスト"""

    def test_jsonファイル破損時は空で初期化(self, tmp_dir):
        """JSONが壊れているファイルがあっても空dictで正常起動する"""
        data_file = Path(tmp_dir) / "quality_dashboard.json"
        # 破損したJSONを書き込む
        data_file.write_text("{ broken json <<<", encoding="utf-8")
        db = QualityDashboard(data_dir=tmp_dir)
        assert len(db.records) == 0

    def test_空ファイル時は空で初期化(self, tmp_dir):
        """0バイトのファイルがあっても空dictで正常起動する"""
        data_file = Path(tmp_dir) / "quality_dashboard.json"
        data_file.write_text("", encoding="utf-8")
        db = QualityDashboard(data_dir=tmp_dir)
        assert len(db.records) == 0

    def test_必須キー欠損JSONは空で初期化(self, tmp_dir):
        """video_id等の必須キーが欠けたレコードがあっても空で初期化"""
        data_file = Path(tmp_dir) / "quality_dashboard.json"
        # video_idキーが欠けた不正データ
        corrupt = {
            "version": "1.0",
            "records": {
                "v1": {"guest_name": "テスト"}  # video_id等が欠損
            }
        }
        data_file.write_text(json.dumps(corrupt), encoding="utf-8")
        db = QualityDashboard(data_dir=tmp_dir)
        assert len(db.records) == 0

    def test_初稿スコアゼロの改善率はゼロ(self, tmp_dir):
        """初稿スコアが0のとき改善率計算でゼロ除算しない"""
        db = QualityDashboard(data_dir=tmp_dir)
        db.record_quality(
            video_id="zero_start", guest_name="テスト", video_title="テスト",
            stage="draft", total_score=0.0, grade="D",
        )
        db.record_quality(
            video_id="zero_start", guest_name="テスト", video_title="テスト",
            stage="final", total_score=80.0, grade="A",
        )
        record = db.get_record("zero_start")
        # ゼロ除算を回避し improvement_rate=0 で返る
        assert record.improvement_rate == 0.0

    def test_スコア境界値0のラウンドトリップ(self, tmp_dir):
        """スコア0.0が保存・読み込み後も正確に保持される"""
        db1 = QualityDashboard(data_dir=tmp_dir)
        db1.record_quality(
            video_id="score_zero", guest_name="テスト", video_title="テスト",
            stage="draft", total_score=0.0, grade="D",
        )
        db2 = QualityDashboard(data_dir=tmp_dir)
        record = db2.get_record("score_zero")
        assert record.snapshots[0].total_score == 0.0

    def test_スコア境界値100のラウンドトリップ(self, tmp_dir):
        """スコア100.0が保存・読み込み後も正確に保持される"""
        db1 = QualityDashboard(data_dir=tmp_dir)
        db1.record_quality(
            video_id="score_max", guest_name="テスト", video_title="テスト",
            stage="final", total_score=100.0, grade="S",
        )
        db2 = QualityDashboard(data_dir=tmp_dir)
        record = db2.get_record("score_max")
        assert record.snapshots[0].total_score == 100.0

    def test_日本語video_idのラウンドトリップ(self, tmp_dir):
        """日本語を含むvideo_idが保存・読み込み後も正確に保持される"""
        db1 = QualityDashboard(data_dir=tmp_dir)
        jp_id = "2026年3月_田中さん_対談動画"
        db1.record_quality(
            video_id=jp_id, guest_name="田中さん", video_title="対談動画",
            stage="draft", total_score=72.5, grade="B",
        )
        db2 = QualityDashboard(data_dir=tmp_dir)
        record = db2.get_record(jp_id)
        assert record is not None
        assert record.guest_name == "田中さん"
        assert record.snapshots[0].total_score == 72.5

    def test_スコア悪化でマイナス改善率(self, tmp_dir):
        """修正後にスコアが下がった場合、改善率がマイナスになる"""
        db = QualityDashboard(data_dir=tmp_dir)
        db.record_quality(
            video_id="regress_test", guest_name="テスト", video_title="テスト",
            stage="draft", total_score=80.0, grade="A",
        )
        db.record_quality(
            video_id="regress_test", guest_name="テスト", video_title="テスト",
            stage="final", total_score=60.0, grade="C",
        )
        record = db.get_record("regress_test")
        assert record.improvement_rate < 0.0  # (60-80)/80*100 = -25%

    def test_未知ステージ名はそのままラベルになる(self, tmp_dir):
        """stage_labelsにないステージ名は stage 自体がラベルとして使われる"""
        db = QualityDashboard(data_dir=tmp_dir)
        db.record_quality(
            video_id="custom_stage", guest_name="テスト", video_title="テスト",
            stage="special_review", total_score=75.0, grade="B",
        )
        record = db.get_record("custom_stage")
        assert record.snapshots[0].stage_label == "special_review"

    def test_clear_all後に新規登録できる(self, tmp_dir):
        """clear_all後でも正常に新しいレコードを登録できる"""
        db = QualityDashboard(data_dir=tmp_dir)
        db.record_quality(
            video_id="before_clear", guest_name="テスト", video_title="テスト",
            stage="draft", total_score=70.0, grade="B",
        )
        db.clear_all()
        assert db.get_record("before_clear") is None
        db.record_quality(
            video_id="after_clear", guest_name="新テスト", video_title="新テスト",
            stage="draft", total_score=80.0, grade="A",
        )
        assert db.get_record("after_clear") is not None

    def test_複数回save_load繰り返しでデータ整合性(self, tmp_dir):
        """save→load→save→loadを繰り返してもデータが壊れない"""
        db = QualityDashboard(data_dir=tmp_dir)
        for i in range(3):
            db.record_quality(
                video_id=f"multi_{i}", guest_name=f"ゲスト{i}", video_title=f"動画{i}",
                stage="draft", total_score=float(60 + i * 10), grade="B",
            )
        # 2回ロードして同じデータを得る
        db2 = QualityDashboard(data_dir=tmp_dir)
        db3 = QualityDashboard(data_dir=tmp_dir)
        assert len(db2.records) == 3
        assert len(db3.records) == 3
        for i in range(3):
            r2 = db2.get_record(f"multi_{i}")
            r3 = db3.get_record(f"multi_{i}")
            assert r2.snapshots[0].total_score == r3.snapshots[0].total_score

    def test_dimension_scoresのラウンドトリップ(self, tmp_dir):
        """dimension_scoresが保存・読み込み後も正確に保持される"""
        dims = {"cut": 85, "color": 70, "telop": 90, "bgm": 65, "camera": 75, "composition": 80, "tempo": 78}
        db1 = QualityDashboard(data_dir=tmp_dir)
        db1.record_quality(
            video_id="dims_test", guest_name="テスト", video_title="テスト",
            stage="draft", total_score=77.6, grade="B",
            dimension_scores=dims,
        )
        db2 = QualityDashboard(data_dir=tmp_dir)
        record = db2.get_record("dims_test")
        assert record.snapshots[0].dimension_scores == dims

    def test_空のrecordsキーを持つJSONは正常ロード(self, tmp_dir):
        """recordsキーが空dictのJSONファイルは0件として正常ロードされる"""
        data_file = Path(tmp_dir) / "quality_dashboard.json"
        data_file.write_text(json.dumps({"version": "1.0", "records": {}}), encoding="utf-8")
        db = QualityDashboard(data_dir=tmp_dir)
        assert len(db.records) == 0

    def test_notesフィールドのラウンドトリップ(self, tmp_dir):
        """notesフィールドが保存・読み込み後も正確に保持される"""
        db1 = QualityDashboard(data_dir=tmp_dir)
        db1.record_quality(
            video_id="notes_test", guest_name="テスト", video_title="テスト",
            stage="draft", total_score=65.0, grade="B",
            notes="テロップの色が明るすぎる。修正依頼済み。",
        )
        db2 = QualityDashboard(data_dir=tmp_dir)
        record = db2.get_record("notes_test")
        assert record.snapshots[0].notes == "テロップの色が明るすぎる。修正依頼済み。"
