"""E2Eパイプライン統合テスト — 新規追加エンドポイントの実動検証

テスト対象:
1. POST /api/v1/projects/{pid}/generate-direction
2. POST /api/v1/projects/{pid}/e2e-pipeline
3. POST /api/v1/feedback/convert-enhanced
4. 存在しないプロジェクトIDで404返却確認
5. direction_generator, feedback_learner, video_learnerの連携確認
"""

import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from src.video_direction.integrations.api_server import app

client = TestClient(app)


# --- テスト用プロジェクトIDの取得 ---

def _get_existing_project_id():
    """DB内の既存プロジェクトIDを1件返す（テスト環境非依存）"""
    import sqlite3
    DB_PATH = Path.home() / "AI開発10" / ".data" / "video_director.db"
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(str(DB_PATH))
    row = conn.execute("SELECT id FROM projects LIMIT 1").fetchone()
    conn.close()
    return row[0] if row else None


EXISTING_PID = _get_existing_project_id()
NONEXISTENT_PID = "p-99999999-nonexistent"


# =================================================================
# 1. POST /api/v1/projects/{pid}/generate-direction
# =================================================================

class TestGenerateDirection:
    """ディレクション生成APIのテスト"""

    @pytest.mark.skipif(EXISTING_PID is None, reason="DBにプロジェクトなし")
    def test_generate_direction_success(self):
        """既存プロジェクトIDでディレクション生成が成功する"""
        resp = client.post(f"/api/v1/projects/{EXISTING_PID}/generate-direction")
        assert resp.status_code == 200
        data = resp.json()

        # レスポンス構造の検証
        assert "project_id" in data
        assert data["project_id"] == EXISTING_PID
        assert "direction_timeline" in data
        assert "entries" in data["direction_timeline"]
        assert "llm_analysis" in data["direction_timeline"]
        assert "applied_rules" in data["direction_timeline"]
        assert "learning_context" in data
        assert "tracking_references" in data
        assert "video_reference_urls" in data
        assert "generated_at" in data

    @pytest.mark.skipif(EXISTING_PID is None, reason="DBにプロジェクトなし")
    def test_generate_direction_entries_format(self):
        """ディレクションエントリがDirectionTimeline形式であること"""
        resp = client.post(f"/api/v1/projects/{EXISTING_PID}/generate-direction")
        assert resp.status_code == 200
        data = resp.json()

        entries = data["direction_timeline"]["entries"]
        assert isinstance(entries, list)
        # エントリが存在すれば形式チェック
        if entries:
            entry = entries[0]
            # DirectionEntryの必須フィールド確認
            assert "timestamp" in entry
            assert "instruction" in entry

    def test_generate_direction_404(self):
        """存在しないプロジェクトIDで404が返る"""
        resp = client.post(f"/api/v1/projects/{NONEXISTENT_PID}/generate-direction")
        assert resp.status_code == 404

    @pytest.mark.skipif(EXISTING_PID is None, reason="DBにプロジェクトなし")
    def test_generate_direction_with_body(self):
        """use_llm=Falseで呼び出し可能"""
        resp = client.post(
            f"/api/v1/projects/{EXISTING_PID}/generate-direction",
            json={"use_llm": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "direction_timeline" in data


# =================================================================
# 2. POST /api/v1/projects/{pid}/e2e-pipeline
# =================================================================

class TestE2EPipeline:
    """E2E統合フローAPIのテスト"""

    @pytest.mark.skipif(EXISTING_PID is None, reason="DBにプロジェクトなし")
    def test_e2e_pipeline_dry_run(self):
        """dry_run=Trueで5段階の結果を確認"""
        resp = client.post(
            f"/api/v1/projects/{EXISTING_PID}/e2e-pipeline",
            json={"dry_run": True},
        )
        assert resp.status_code == 200
        data = resp.json()

        # レスポンス構造の検証
        assert "project_id" in data
        assert data["project_id"] == EXISTING_PID
        assert "pipeline_steps" in data
        assert "errors" in data
        assert "success" in data
        assert "generated_at" in data

        # 5段階のステップが存在する
        steps = data["pipeline_steps"]
        assert "step1_feedbacks" in steps
        assert "step2_fb_learning" in steps
        assert "step3_video_learning" in steps
        assert "step4_direction" in steps
        assert "step5_vimeo" in steps

    @pytest.mark.skipif(EXISTING_PID is None, reason="DBにプロジェクトなし")
    def test_e2e_pipeline_step1_feedbacks(self):
        """Step1: プロジェクトとFB一覧が正常取得される"""
        resp = client.post(
            f"/api/v1/projects/{EXISTING_PID}/e2e-pipeline",
            json={"dry_run": True},
        )
        assert resp.status_code == 200
        data = resp.json()

        step1 = data["pipeline_steps"]["step1_feedbacks"]
        assert step1["status"] == "ok"
        assert "feedback_count" in step1
        assert "project_title" in step1
        assert "guest_name" in step1

    @pytest.mark.skipif(EXISTING_PID is None, reason="DBにプロジェクトなし")
    def test_e2e_pipeline_step4_direction(self):
        """Step4: ディレクション生成がok/errorのいずれかで完了する"""
        resp = client.post(
            f"/api/v1/projects/{EXISTING_PID}/e2e-pipeline",
            json={"dry_run": True},
        )
        assert resp.status_code == 200
        data = resp.json()

        step4 = data["pipeline_steps"]["step4_direction"]
        assert step4["status"] in ("ok", "error")
        if step4["status"] == "ok":
            assert "entry_count" in step4
            assert "has_llm_analysis" in step4
            assert "applied_rule_count" in step4

    @pytest.mark.skipif(EXISTING_PID is None, reason="DBにプロジェクトなし")
    def test_e2e_pipeline_step5_vimeo_skipped(self):
        """Step5: vimeo_video_id未指定ならskippedになる"""
        resp = client.post(
            f"/api/v1/projects/{EXISTING_PID}/e2e-pipeline",
            json={"dry_run": True},
        )
        assert resp.status_code == 200
        data = resp.json()

        step5 = data["pipeline_steps"]["step5_vimeo"]
        assert step5["status"] == "skipped"
        assert "vimeo_video_idが未指定" in step5.get("reason", "")

    def test_e2e_pipeline_404(self):
        """存在しないプロジェクトIDで404が返る"""
        resp = client.post(
            f"/api/v1/projects/{NONEXISTENT_PID}/e2e-pipeline",
            json={"dry_run": True},
        )
        assert resp.status_code == 404

    @pytest.mark.skipif(EXISTING_PID is None, reason="DBにプロジェクトなし")
    def test_e2e_pipeline_default_dry_run(self):
        """デフォルトはdry_run=Trueであること"""
        resp = client.post(f"/api/v1/projects/{EXISTING_PID}/e2e-pipeline")
        assert resp.status_code == 200
        data = resp.json()
        # Vimeo投稿はスキップされる（vimeo_video_id未指定）
        assert data["pipeline_steps"]["step5_vimeo"]["status"] == "skipped"

    @pytest.mark.skipif(EXISTING_PID is None, reason="DBにプロジェクトなし")
    def test_e2e_pipeline_tracking_references(self):
        """トラッキング参照リストが返される"""
        resp = client.post(
            f"/api/v1/projects/{EXISTING_PID}/e2e-pipeline",
            json={"dry_run": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "tracking_references" in data
        assert isinstance(data["tracking_references"], list)
        assert "video_reference_urls" in data
        assert isinstance(data["video_reference_urls"], list)


# =================================================================
# 3. POST /api/v1/feedback/convert-enhanced
# =================================================================

class TestFeedbackConvertEnhanced:
    """FB変換強化版APIのテスト"""

    def test_convert_enhanced_basic(self):
        """基本的なFBテキスト変換が成功する"""
        resp = client.post(
            "/api/v1/feedback/convert-enhanced",
            json={
                "raw_text": "もっとテンポを速くして。イントロが長すぎる。3秒以内に収めて。",
                "project_id": EXISTING_PID or "test-project",
            },
        )
        assert resp.status_code == 200
        data = resp.json()

        # レスポンス構造の検証（LLMフォールバック含む）
        assert "detected_category" in data
        assert "tracking_references" in data
        assert "learning_rules_applied" in data

    def test_convert_enhanced_with_options(self):
        """学習ルール・トラッキング参照の有効/無効切り替え"""
        resp = client.post(
            "/api/v1/feedback/convert-enhanced",
            json={
                "raw_text": "BGMをもう少し小さくしてほしい",
                "project_id": EXISTING_PID or "test-project",
                "use_learning_rules": False,
                "include_tracking_references": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["learning_rules_applied"] is False

    def test_convert_enhanced_empty_text(self):
        """空テキストでもエラーにならない"""
        resp = client.post(
            "/api/v1/feedback/convert-enhanced",
            json={
                "raw_text": "",
                "project_id": EXISTING_PID or "test-project",
            },
        )
        # 空テキストでも処理は通る（フォールバック）
        assert resp.status_code == 200

    def test_convert_enhanced_fallback_response(self):
        """LLM不使用時のフォールバックレスポンス構造"""
        # ANTHROPIC_API_KEYが未設定の場合、フォールバックが返る
        resp = client.post(
            "/api/v1/feedback/convert-enhanced",
            json={
                "raw_text": "カット割りをもっと細かくしてください。各シーン5秒以内。",
                "project_id": EXISTING_PID or "test-project",
            },
        )
        assert resp.status_code == 200
        data = resp.json()

        # フォールバックまたはLLMどちらでもこれらのフィールドは存在する
        assert "detected_category" in data
        assert "tracking_references" in data
        assert isinstance(data["tracking_references"], list)

    def test_convert_enhanced_missing_raw_text(self):
        """raw_textが欠如した場合422エラー"""
        resp = client.post(
            "/api/v1/feedback/convert-enhanced",
            json={
                "project_id": "test-project",
            },
        )
        assert resp.status_code == 422

    def test_convert_enhanced_missing_project_id(self):
        """project_idが欠如した場合422エラー"""
        resp = client.post(
            "/api/v1/feedback/convert-enhanced",
            json={
                "raw_text": "テスト",
            },
        )
        assert resp.status_code == 422


# =================================================================
# 4. 404エラー系の追加テスト
# =================================================================

class TestNotFound:
    """存在しないプロジェクトIDで404が返ることを確認"""

    def test_generate_direction_nonexistent(self):
        resp = client.post(f"/api/v1/projects/{NONEXISTENT_PID}/generate-direction")
        assert resp.status_code == 404

    def test_e2e_pipeline_nonexistent(self):
        resp = client.post(
            f"/api/v1/projects/{NONEXISTENT_PID}/e2e-pipeline",
            json={"dry_run": True},
        )
        assert resp.status_code == 404


# =================================================================
# 5. learner連携テスト（direction_generator, feedback_learner, video_learner）
# =================================================================

class TestLearnerIntegration:
    """direction_generator + feedback_learner + video_learner の連携確認"""

    @pytest.mark.skipif(EXISTING_PID is None, reason="DBにプロジェクトなし")
    def test_generate_direction_includes_learning_context(self):
        """ディレクション生成にlearning_contextが含まれる"""
        resp = client.post(f"/api/v1/projects/{EXISTING_PID}/generate-direction")
        assert resp.status_code == 200
        data = resp.json()
        assert "learning_context" in data
        # learning_contextは辞書型
        assert isinstance(data["learning_context"], dict)

    @pytest.mark.skipif(EXISTING_PID is None, reason="DBにプロジェクトなし")
    def test_e2e_pipeline_fb_learning_status(self):
        """E2Eパイプラインでstep2_fb_learningのstatusが正しい"""
        resp = client.post(
            f"/api/v1/projects/{EXISTING_PID}/e2e-pipeline",
            json={"dry_run": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        step2 = data["pipeline_steps"]["step2_fb_learning"]
        # FeedbackLearnerが利用可能ならok、不可ならunavailable
        assert step2["status"] in ("ok", "unavailable", "error")

    @pytest.mark.skipif(EXISTING_PID is None, reason="DBにプロジェクトなし")
    def test_e2e_pipeline_video_learning_status(self):
        """E2Eパイプラインでstep3_video_learningのstatusが正しい"""
        resp = client.post(
            f"/api/v1/projects/{EXISTING_PID}/e2e-pipeline",
            json={"dry_run": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        step3 = data["pipeline_steps"]["step3_video_learning"]
        assert step3["status"] in ("ok", "unavailable", "error")

    @pytest.mark.skipif(EXISTING_PID is None, reason="DBにプロジェクトなし")
    def test_direction_timeline_applied_rules(self):
        """ディレクションのapplied_rulesがリスト形式"""
        resp = client.post(f"/api/v1/projects/{EXISTING_PID}/generate-direction")
        assert resp.status_code == 200
        data = resp.json()
        rules = data["direction_timeline"]["applied_rules"]
        assert isinstance(rules, list)

    def test_convert_enhanced_uses_feedback_learner(self):
        """FB変換強化版でuse_learning_rules=Trueの場合、learnerが参照される"""
        resp = client.post(
            "/api/v1/feedback/convert-enhanced",
            json={
                "raw_text": "テロップのフォントサイズを大きくして",
                "project_id": EXISTING_PID or "test-project",
                "use_learning_rules": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # learning_rules_appliedがbool型
        assert isinstance(data["learning_rules_applied"], bool)
