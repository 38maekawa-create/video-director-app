"""Phase 3-4 で追加した新APIエンドポイントの統合テスト

テスト対象: api_server.py 内の以下のエンドポイント群
- 編集者管理 (/api/editors)
- 映像トラッキング (/api/tracking)
- インサイト (/api/tracking/insights)
- 巡回監査 (/api/audit)
- 通知設定 (/api/notifications)
- PDCA品質改善 (/api/pdca)
- フィードバック変換 (/api/feedback/convert)

各依存モジュール（EditorManager, VideoTracker, etc.）はモックで差し替え、
APIレイヤーの動作を独立してテストする。
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from fastapi.testclient import TestClient
from src.video_direction.integrations.api_server import app


# --- テスト用データクラス（実モジュールの構造を再現） ---

@dataclass
class MockEditorProfile:
    id: str = "editor_001"
    name: str = "テスト編集者"
    contact_info: str = "test@example.com"
    status: str = "active"
    contract_type: str = "freelance"
    specialties: list = field(default_factory=list)
    skills: dict = field(default_factory=dict)
    active_projects: list = field(default_factory=list)
    completed_count: int = 0
    avg_quality_score: float = 0.0
    capacity: int = 3
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class MockTrackedVideo:
    id: str = "video_001"
    url: str = "https://www.youtube.com/watch?v=test"
    title: str = "テスト動画"
    channel_name: str = "テストチャンネル"
    thumbnail_url: str = ""
    duration_seconds: float = 120.0
    analysis_status: str = "pending"
    analysis_result: Optional[dict] = None
    tags: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class MockVideoAnalysisResult:
    video_id: str = "video_001"
    overall_score: float = 75.0
    composition: str = "三分割構図"
    tempo: str = "標準テンポ"
    cutting_style: str = "カット割り：標準"
    color_grading: str = "暖色系"
    audio_balance: str = "良好"
    key_techniques: list = field(default_factory=list)
    summary: str = "テスト分析結果"
    frame_count: int = 100
    avg_scene_duration: float = 5.0


@dataclass
class MockVideoPattern:
    id: str = "pattern_001"
    category: str = "cutting"
    pattern: str = "テストパターン"
    source_count: int = 3
    source_video_ids: list = field(default_factory=list)
    confidence: float = 0.8
    example_urls: list = field(default_factory=list)
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class MockAuditReport:
    run_at: str = field(default_factory=lambda: datetime.now().isoformat())
    pipeline_status: str = "healthy"
    pending_videos: int = 0
    quality_anomalies: list = field(default_factory=list)
    stale_projects: list = field(default_factory=list)
    api_health: str = "healthy"
    db_health: str = "healthy"
    overall_health: str = "good"
    details: dict = field(default_factory=dict)


@dataclass
class MockPDCAState:
    project_id: str = "proj_001"
    guest_name: str = "テストゲスト"
    direction_generated: bool = False
    direction_url: str = ""
    editing_assigned: bool = False
    editor_id: str = ""
    editing_completed: bool = False
    quality_scored: bool = False
    quality_score: float = 0.0
    feedback_count: int = 0
    rules_updated: bool = False
    learning_applied: bool = False
    current_phase: str = "plan"
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


# --- ヘルパー ---

def _make_client():
    """TestClient を生成（startup イベントの DB初期化をスキップ）"""
    return TestClient(app, raise_server_exceptions=False)


# ============================================================
# 1. 編集者一覧 GET /api/editors
# ============================================================

class TestListEditors:
    """GET /api/editors — 編集者一覧"""

    @patch("src.video_direction.integrations.api_server._get_editor_manager")
    def test_空リスト_マネージャ未接続(self, mock_mgr):
        """EditorManager が無い場合は空リストを返す"""
        mock_mgr.return_value = None
        client = _make_client()
        resp = client.get("/api/editors")
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("src.video_direction.integrations.api_server._get_editor_manager")
    def test_編集者一覧を返す(self, mock_mgr):
        """編集者が登録済みの場合、一覧を返す"""
        mgr = MagicMock()
        editor = MockEditorProfile(id="e1", name="田中太郎")
        mgr.list_editors.return_value = [editor]
        mock_mgr.return_value = mgr
        client = _make_client()
        resp = client.get("/api/editors")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "e1"
        assert data[0]["name"] == "田中太郎"

    @patch("src.video_direction.integrations.api_server._get_editor_manager")
    def test_ステータスフィルタ(self, mock_mgr):
        """status クエリパラメータでフィルタリング"""
        mgr = MagicMock()
        mgr.list_editors.return_value = []
        mock_mgr.return_value = mgr
        client = _make_client()
        resp = client.get("/api/editors?status=active")
        assert resp.status_code == 200
        mgr.list_editors.assert_called_once_with(status="active")


# ============================================================
# 2. 編集者追加 POST /api/editors
# ============================================================

class TestCreateEditor:
    """POST /api/editors — 編集者追加"""

    @patch("src.video_direction.integrations.api_server._get_editor_manager")
    def test_編集者追加_正常(self, mock_mgr):
        """正常に編集者を追加し、プロフィール情報を返す"""
        mgr = MagicMock()
        created = MockEditorProfile(id="e_new", name="新規編集者", contact_info="new@example.com")
        mgr.add_editor.return_value = created
        mock_mgr.return_value = mgr
        client = _make_client()
        resp = client.post("/api/editors", json={
            "name": "新規編集者",
            "contact_info": "new@example.com",
            "contract_type": "freelance",
            "capacity": 5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "e_new"
        assert data["name"] == "新規編集者"
        assert "contact_info" in data

    @patch("src.video_direction.integrations.api_server._get_editor_manager")
    def test_編集者追加_マネージャ未接続で500(self, mock_mgr):
        """EditorManager が無い場合は 500 を返す"""
        mock_mgr.return_value = None
        client = _make_client()
        resp = client.post("/api/editors", json={"name": "テスト"})
        assert resp.status_code == 500


# ============================================================
# 3. 編集者詳細 GET /api/editors/{id}
# ============================================================

class TestGetEditor:
    """GET /api/editors/{id} — 編集者詳細"""

    @patch("src.video_direction.integrations.api_server._get_editor_manager")
    def test_編集者詳細_正常(self, mock_mgr):
        mgr = MagicMock()
        editor = MockEditorProfile(id="e1", name="田中太郎", skills={"cutting": 80})
        mgr.get_editor.return_value = editor
        mock_mgr.return_value = mgr
        client = _make_client()
        resp = client.get("/api/editors/e1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "e1"
        assert "skills" in data
        assert "capacity" in data

    @patch("src.video_direction.integrations.api_server._get_editor_manager")
    def test_編集者詳細_存在しない場合404(self, mock_mgr):
        mgr = MagicMock()
        mgr.get_editor.return_value = None
        mock_mgr.return_value = mgr
        client = _make_client()
        resp = client.get("/api/editors/nonexistent")
        assert resp.status_code == 404


# ============================================================
# 4. 編集者更新 PUT /api/editors/{id}
# ============================================================

class TestUpdateEditor:
    """PUT /api/editors/{id} — 編集者更新"""

    @patch("src.video_direction.integrations.api_server._get_editor_manager")
    def test_編集者更新_正常(self, mock_mgr):
        mgr = MagicMock()
        updated = MockEditorProfile(id="e1", name="更新済み太郎", status="inactive")
        mgr.update_editor.return_value = updated
        mock_mgr.return_value = mgr
        client = _make_client()
        resp = client.put("/api/editors/e1", json={"name": "更新済み太郎", "status": "inactive"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "更新済み太郎"

    @patch("src.video_direction.integrations.api_server._get_editor_manager")
    def test_編集者更新_存在しない場合404(self, mock_mgr):
        mgr = MagicMock()
        mgr.update_editor.return_value = None
        mock_mgr.return_value = mgr
        client = _make_client()
        resp = client.put("/api/editors/nonexistent", json={"name": "なし"})
        assert resp.status_code == 404


# ============================================================
# 5. 引き継ぎパッケージ GET /api/editors/{id}/handover
# ============================================================

class TestEditorHandover:
    """GET /api/editors/{id}/handover — 引き継ぎパッケージ"""

    @patch("src.video_direction.integrations.api_server._get_editor_manager")
    def test_引き継ぎパッケージ_正常(self, mock_mgr):
        mgr = MagicMock()
        mgr.generate_handover_package.return_value = {
            "editor_profile": {"id": "e1", "name": "テスト"},
            "skill_summary": {"strengths": ["cutting"], "weaknesses": [], "overall_avg": 75.0},
            "active_projects": [],
            "completed_count": 5,
            "avg_quality": 80.0,
            "generated_at": datetime.now().isoformat(),
            "notes": "",
        }
        mock_mgr.return_value = mgr
        client = _make_client()
        resp = client.get("/api/editors/e1/handover")
        assert resp.status_code == 200
        data = resp.json()
        assert "editor_profile" in data
        assert "skill_summary" in data
        assert "active_projects" in data
        assert "completed_count" in data

    @patch("src.video_direction.integrations.api_server._get_editor_manager")
    def test_引き継ぎパッケージ_存在しない場合(self, mock_mgr):
        """空辞書が返る（= 編集者なし）場合は404"""
        mgr = MagicMock()
        mgr.generate_handover_package.return_value = {}
        mock_mgr.return_value = mgr
        client = _make_client()
        # api_server の実装: if not package → 404
        # 空辞書は falsy なので 404 になる
        resp = client.get("/api/editors/nonexistent/handover")
        assert resp.status_code == 404


# ============================================================
# 6. トラッキング映像一覧 GET /api/tracking/videos
# ============================================================

class TestListTrackingVideos:
    """GET /api/tracking/videos — トラッキング映像一覧"""

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    def test_トラッカー未接続で空リスト(self, mock_tracker):
        mock_tracker.return_value = None
        client = _make_client()
        resp = client.get("/api/tracking/videos")
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    def test_映像一覧を返す(self, mock_tracker):
        tracker = MagicMock()
        video = MockTrackedVideo(id="v1", title="テスト動画A")
        tracker.list_videos.return_value = [video]
        mock_tracker.return_value = tracker
        client = _make_client()
        resp = client.get("/api/tracking/videos")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "v1"
        assert data[0]["title"] == "テスト動画A"
        assert "url" in data[0]
        assert "analysis_status" in data[0]


# ============================================================
# 7. 新規トラッキング登録 POST /api/tracking/videos
# ============================================================

class TestAddTrackingVideo:
    """POST /api/tracking/videos — 新規トラッキング登録"""

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    def test_トラッキング登録_正常(self, mock_tracker):
        tracker = MagicMock()
        video = MockTrackedVideo(id="v_new", url="https://youtube.com/watch?v=new", tags=["参考"])
        tracker.add_video.return_value = video
        mock_tracker.return_value = tracker
        client = _make_client()
        resp = client.post("/api/tracking/videos", json={
            "url": "https://youtube.com/watch?v=new",
            "tags": ["参考"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "v_new"
        assert data["url"] == "https://youtube.com/watch?v=new"

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    def test_トラッカー未接続で500(self, mock_tracker):
        mock_tracker.return_value = None
        client = _make_client()
        resp = client.post("/api/tracking/videos", json={"url": "https://example.com"})
        assert resp.status_code == 500


# ============================================================
# 8. トラッキング削除 DELETE /api/tracking/videos/{id}
# ============================================================

class TestRemoveTrackingVideo:
    """DELETE /api/tracking/videos/{id} — トラッキング削除"""

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    def test_トラッキング削除_正常(self, mock_tracker):
        tracker = MagicMock()
        tracker.remove_video.return_value = True
        mock_tracker.return_value = tracker
        client = _make_client()
        resp = client.delete("/api/tracking/videos/v1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "removed"

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    def test_トラッキング削除_存在しない場合404(self, mock_tracker):
        tracker = MagicMock()
        tracker.remove_video.return_value = False
        mock_tracker.return_value = tracker
        client = _make_client()
        resp = client.delete("/api/tracking/videos/nonexistent")
        assert resp.status_code == 404


# ============================================================
# 9. 映像分析 POST /api/tracking/videos/{id}/analyze
# ============================================================

class TestAnalyzeTrackingVideo:
    """POST /api/tracking/videos/{id}/analyze — 映像分析"""

    @patch("src.video_direction.integrations.api_server._get_video_analyzer")
    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    def test_映像分析_正常(self, mock_tracker, mock_analyzer):
        tracker = MagicMock()
        video = MockTrackedVideo(id="v1", url="https://youtube.com/test")
        tracker.get_video.return_value = video
        mock_tracker.return_value = tracker

        analyzer = MagicMock()
        result = MockVideoAnalysisResult(video_id="v1", overall_score=82.0)
        analyzer.analyze.return_value = result
        mock_analyzer.return_value = analyzer

        client = _make_client()
        resp = client.post("/api/tracking/videos/v1/analyze")
        assert resp.status_code == 200
        data = resp.json()
        assert data["video_id"] == "v1"
        assert data["overall_score"] == 82.0
        assert "composition" in data
        assert "tempo" in data

    @patch("src.video_direction.integrations.api_server._get_video_analyzer")
    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    def test_映像分析_映像が見つからない場合404(self, mock_tracker, mock_analyzer):
        tracker = MagicMock()
        tracker.get_video.return_value = None
        mock_tracker.return_value = tracker
        mock_analyzer.return_value = MagicMock()
        client = _make_client()
        resp = client.post("/api/tracking/videos/nonexistent/analyze")
        assert resp.status_code == 404

    @patch("src.video_direction.integrations.api_server._get_video_analyzer")
    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    def test_映像分析_システム未接続で500(self, mock_tracker, mock_analyzer):
        mock_tracker.return_value = None
        mock_analyzer.return_value = None
        client = _make_client()
        resp = client.post("/api/tracking/videos/v1/analyze")
        assert resp.status_code == 500


# ============================================================
# 10. インサイト一覧 GET /api/tracking/insights
# ============================================================

class TestListTrackingInsights:
    """GET /api/tracking/insights — インサイト一覧"""

    @patch("src.video_direction.integrations.api_server._get_video_learner")
    def test_インサイト一覧_正常(self, mock_learner):
        learner = MagicMock()
        pattern = MockVideoPattern(id="p1", category="cutting", confidence=0.9)
        learner.get_patterns.return_value = [pattern]
        mock_learner.return_value = learner
        client = _make_client()
        resp = client.get("/api/tracking/insights")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "p1"
        assert data[0]["category"] == "cutting"
        assert "confidence" in data[0]

    @patch("src.video_direction.integrations.api_server._get_video_learner")
    def test_インサイト一覧_ラーナー未接続で空リスト(self, mock_learner):
        mock_learner.return_value = None
        client = _make_client()
        resp = client.get("/api/tracking/insights")
        assert resp.status_code == 200
        assert resp.json() == []


# ============================================================
# 11. 最新監査 GET /api/audit/latest
# ============================================================

class TestGetLatestAudit:
    """GET /api/audit/latest — 最新監査"""

    @patch("src.video_direction.integrations.api_server._get_audit_runner")
    def test_最新監査_正常(self, mock_runner):
        runner = MagicMock()
        report = MockAuditReport(
            pipeline_status="healthy",
            overall_health="good",
            db_health="healthy",
        )
        runner.get_latest_report.return_value = report
        mock_runner.return_value = runner
        client = _make_client()
        resp = client.get("/api/audit/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pipeline_status"] == "healthy"
        assert data["overall_health"] == "good"
        assert "pending_videos" in data
        assert "quality_anomalies" in data

    @patch("src.video_direction.integrations.api_server._get_audit_runner")
    def test_最新監査_レポートなし(self, mock_runner):
        runner = MagicMock()
        runner.get_latest_report.return_value = None
        mock_runner.return_value = runner
        client = _make_client()
        resp = client.get("/api/audit/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data

    @patch("src.video_direction.integrations.api_server._get_audit_runner")
    def test_最新監査_ランナー未接続(self, mock_runner):
        mock_runner.return_value = None
        client = _make_client()
        resp = client.get("/api/audit/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data


# ============================================================
# 12. 監査実行 POST /api/audit/run
# ============================================================

class TestRunAudit:
    """POST /api/audit/run — 監査実行"""

    @patch("src.video_direction.integrations.api_server._get_audit_runner")
    def test_監査実行_正常(self, mock_runner):
        runner = MagicMock()
        report = MockAuditReport(overall_health="warning", pending_videos=3)
        runner.run_audit.return_value = report
        mock_runner.return_value = runner
        client = _make_client()
        resp = client.post("/api/audit/run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_health"] == "warning"
        assert data["pending_videos"] == 3
        assert "run_at" in data

    @patch("src.video_direction.integrations.api_server._get_audit_runner")
    def test_監査実行_ランナー未接続で500(self, mock_runner):
        mock_runner.return_value = None
        client = _make_client()
        resp = client.post("/api/audit/run")
        assert resp.status_code == 500


# ============================================================
# 13. 通知設定取得 GET /api/notifications/config
# ============================================================

class TestGetNotificationConfig:
    """GET /api/notifications/config — 通知設定取得"""

    @patch("src.video_direction.integrations.api_server._get_notifier")
    def test_通知設定取得_正常(self, mock_notifier):
        notifier = MagicMock()
        notifier.get_config.return_value = {
            "telegram_enabled": False,
            "telegram_configured": False,
            "line_enabled": False,
            "line_configured": False,
            "notify_on_report": True,
            "notify_on_quality_warning": True,
            "notify_on_feedback": True,
        }
        mock_notifier.return_value = notifier
        client = _make_client()
        resp = client.get("/api/notifications/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "telegram_enabled" in data
        assert "line_enabled" in data
        assert "notify_on_report" in data
        assert "notify_on_quality_warning" in data
        assert "notify_on_feedback" in data

    @patch("src.video_direction.integrations.api_server._get_notifier")
    def test_通知設定取得_ノーティファイア未接続(self, mock_notifier):
        mock_notifier.return_value = None
        client = _make_client()
        resp = client.get("/api/notifications/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data


# ============================================================
# 14. 通知設定更新 PUT /api/notifications/config
# ============================================================

class TestUpdateNotificationConfig:
    """PUT /api/notifications/config — 通知設定更新"""

    @patch("src.video_direction.integrations.api_server._get_notifier")
    def test_通知設定更新_正常(self, mock_notifier):
        """設定を更新して更新後の設定を返す"""
        notifier = MagicMock()
        # config 属性を設定（save_config 呼び出し時に属性を更新するため）
        config_mock = MagicMock()
        notifier.config = config_mock
        notifier.get_config.return_value = {
            "telegram_enabled": True,
            "telegram_configured": False,
            "line_enabled": False,
            "line_configured": False,
            "notify_on_report": False,
            "notify_on_quality_warning": True,
            "notify_on_feedback": True,
        }
        mock_notifier.return_value = notifier
        # NotificationConfig のインポートもモックする
        with patch("src.video_direction.integrations.api_server.NotificationConfig", create=True):
            client = _make_client()
            resp = client.put("/api/notifications/config", json={
                "telegram_enabled": True,
                "notify_on_report": False,
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "telegram_enabled" in data

    @patch("src.video_direction.integrations.api_server._get_notifier")
    def test_通知設定更新_未接続で500(self, mock_notifier):
        mock_notifier.return_value = None
        client = _make_client()
        resp = client.put("/api/notifications/config", json={"telegram_enabled": True})
        assert resp.status_code == 500


# ============================================================
# 15. PDCA状態一覧 GET /api/pdca/states
# ============================================================

class TestListPDCAStates:
    """GET /api/pdca/states — PDCA状態一覧"""

    @patch("src.video_direction.integrations.api_server._get_pdca_loop")
    def test_PDCA一覧_正常(self, mock_loop):
        loop = MagicMock()
        state = MockPDCAState(project_id="proj_001", current_phase="do")
        loop.list_states.return_value = [state]
        mock_loop.return_value = loop
        client = _make_client()
        resp = client.get("/api/pdca/states")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["project_id"] == "proj_001"
        assert data[0]["current_phase"] == "do"
        assert "quality_score" in data[0]
        assert "feedback_count" in data[0]

    @patch("src.video_direction.integrations.api_server._get_pdca_loop")
    def test_PDCA一覧_ループ未接続で空リスト(self, mock_loop):
        mock_loop.return_value = None
        client = _make_client()
        resp = client.get("/api/pdca/states")
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("src.video_direction.integrations.api_server._get_pdca_loop")
    def test_PDCA一覧_フェーズフィルタ(self, mock_loop):
        loop = MagicMock()
        loop.list_states.return_value = []
        mock_loop.return_value = loop
        client = _make_client()
        resp = client.get("/api/pdca/states?phase=check")
        assert resp.status_code == 200
        loop.list_states.assert_called_once_with(phase="check")


# ============================================================
# 16. PDCAサマリー GET /api/pdca/summary
# ============================================================

class TestPDCASummary:
    """GET /api/pdca/summary — PDCAサマリー"""

    @patch("src.video_direction.integrations.api_server._get_pdca_loop")
    def test_PDCAサマリー_正常(self, mock_loop):
        loop = MagicMock()
        loop.get_summary.return_value = {
            "total_cycles": 10,
            "phase_distribution": {"plan": 2, "do": 3, "check": 2, "act": 1, "completed": 2},
            "completed_cycles": 2,
            "active_cycles": 8,
            "avg_quality_score": 75.5,
        }
        mock_loop.return_value = loop
        client = _make_client()
        resp = client.get("/api/pdca/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_cycles" in data
        assert "phase_distribution" in data
        assert "completed_cycles" in data
        assert "active_cycles" in data
        assert "avg_quality_score" in data

    @patch("src.video_direction.integrations.api_server._get_pdca_loop")
    def test_PDCAサマリー_ループ未接続で空辞書(self, mock_loop):
        mock_loop.return_value = None
        client = _make_client()
        resp = client.get("/api/pdca/summary")
        assert resp.status_code == 200
        assert resp.json() == {}


# ============================================================
# 17. フィードバック変換 POST /api/feedback/convert
# ============================================================

class TestFeedbackConvert:
    """POST /api/feedback/convert — FB変換"""

    def test_フォールバック変換_正常(self):
        """Claude APIが使えない場合のフォールバック変換"""
        client = _make_client()
        resp = client.post("/api/feedback/convert", json={
            "raw_text": "ここのテロップもう少し大きくして",
            "project_id": "proj_001",
        })
        assert resp.status_code == 200
        data = resp.json()
        # フォールバック時のレスポンスキーを確認
        assert "converted_text" in data
        assert "structured_items" in data
        assert isinstance(data["structured_items"], list)
        assert len(data["structured_items"]) > 0
        # structured_items の各要素に必要なキーがあること
        item = data["structured_items"][0]
        assert "id" in item
        assert "timestamp" in item
        assert "element" in item
        assert "instruction" in item
        assert "priority" in item

    def test_フォールバック変換_入力テキストが含まれる(self):
        """変換結果に元のテキストが反映されていること"""
        client = _make_client()
        raw = "BGMの音量を下げてナレーションを聞き取りやすく"
        resp = client.post("/api/feedback/convert", json={
            "raw_text": raw,
            "project_id": "proj_002",
        })
        assert resp.status_code == 200
        data = resp.json()
        # フォールバックでは raw_text がそのまま含まれる
        assert raw in data["converted_text"] or raw[:50] in data["structured_items"][0]["instruction"]


# ============================================================
# CRUD一貫性テスト: POST → GET → PUT → GET
# ============================================================

class TestEditorCRUDFlow:
    """編集者の CRUD 一貫性テスト: 追加 → 取得 → 更新 → 取得"""

    @patch("src.video_direction.integrations.api_server._get_editor_manager")
    def test_編集者CRUDフロー(self, mock_mgr):
        """POST → GET → PUT → GET の一貫性を確認"""
        mgr = MagicMock()

        # ステップ1: POST（追加）
        created = MockEditorProfile(
            id="e_crud", name="CRUD太郎", contact_info="crud@test.com",
            contract_type="fulltime", capacity=4,
        )
        mgr.add_editor.return_value = created
        mock_mgr.return_value = mgr
        client = _make_client()

        resp1 = client.post("/api/editors", json={
            "name": "CRUD太郎", "contact_info": "crud@test.com",
            "contract_type": "fulltime", "capacity": 4,
        })
        assert resp1.status_code == 200
        created_id = resp1.json()["id"]
        assert created_id == "e_crud"

        # ステップ2: GET（取得して確認）
        mgr.get_editor.return_value = created
        resp2 = client.get(f"/api/editors/{created_id}")
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "CRUD太郎"
        assert resp2.json()["contract_type"] == "fulltime"

        # ステップ3: PUT（更新）
        updated = MockEditorProfile(
            id="e_crud", name="CRUD太郎（更新）", contact_info="crud@test.com",
            contract_type="fulltime", capacity=5, status="active",
        )
        mgr.update_editor.return_value = updated
        resp3 = client.put(f"/api/editors/{created_id}", json={
            "name": "CRUD太郎（更新）", "capacity": 5,
        })
        assert resp3.status_code == 200
        assert resp3.json()["name"] == "CRUD太郎（更新）"

        # ステップ4: GET（更新後の確認）
        mgr.get_editor.return_value = updated
        resp4 = client.get(f"/api/editors/{created_id}")
        assert resp4.status_code == 200
        assert resp4.json()["name"] == "CRUD太郎（更新）"
        assert resp4.json()["capacity"] == 5


class TestTrackingVideoCRUDFlow:
    """トラッキング映像の CRUD 一貫性テスト: 登録 → 一覧 → 削除 → 一覧"""

    @patch("src.video_direction.integrations.api_server._get_video_tracker")
    def test_トラッキングCRUDフロー(self, mock_tracker):
        """POST → GET(list) → DELETE → GET(list) の一貫性を確認"""
        tracker = MagicMock()
        mock_tracker.return_value = tracker

        # ステップ1: POST（登録）
        video = MockTrackedVideo(id="v_crud", url="https://youtube.com/crud", title="CRUD動画")
        tracker.add_video.return_value = video
        client = _make_client()

        resp1 = client.post("/api/tracking/videos", json={
            "url": "https://youtube.com/crud", "tags": ["テスト"],
        })
        assert resp1.status_code == 200
        assert resp1.json()["id"] == "v_crud"

        # ステップ2: GET（一覧で確認）
        tracker.list_videos.return_value = [video]
        resp2 = client.get("/api/tracking/videos")
        assert resp2.status_code == 200
        assert len(resp2.json()) == 1
        assert resp2.json()[0]["id"] == "v_crud"

        # ステップ3: DELETE（削除）
        tracker.remove_video.return_value = True
        resp3 = client.delete("/api/tracking/videos/v_crud")
        assert resp3.status_code == 200
        assert resp3.json()["status"] == "removed"

        # ステップ4: GET（削除後は空）
        tracker.list_videos.return_value = []
        resp4 = client.get("/api/tracking/videos")
        assert resp4.status_code == 200
        assert len(resp4.json()) == 0
