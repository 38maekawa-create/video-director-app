"""mock_vimeo_relay_server.py の連携ロジックテスト（ソケット不要）"""

import json
import subprocess
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "mock_vimeo_relay_server.py"
SPEC = spec_from_file_location("mock_vimeo_relay_server", SCRIPT_PATH)
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_validate_payload_detects_missing_fields():
    missing, comments, project_id, video_id, target_video_id = MODULE.validate_payload({"body": {"comments": []}})
    assert sorted(missing) == ["projectId", "targetVideoId", "videoId"]
    assert comments == []
    assert project_id is None
    assert video_id is None
    assert target_video_id is None


def test_build_mock_results_mixed_validity():
    comments = [
        {"feedbackId": "fb-1", "timestampSeconds": 10, "convertedText": "ok"},
        {"feedbackId": "fb-2", "convertedText": "missing timestamp"},
    ]
    results, posted_count = MODULE.build_mock_results(comments)
    assert len(results) == 2
    assert posted_count == 1
    assert any(item["status"] == "failed" for item in results)


def test_run_downstream_dry_run_success(monkeypatch, tmp_path):
    monkeypatch.setattr(MODULE, "POST_SCRIPT", tmp_path / "post_vimeo_review_comments.py")
    MODULE.POST_SCRIPT.write_text("# stub", encoding="utf-8")

    completed = subprocess.CompletedProcess(
        args=["python3"],
        returncode=0,
        stdout=json.dumps({"targetVideoId": "vimeo-001", "requests": []}, ensure_ascii=False),
        stderr="",
    )
    monkeypatch.setattr(MODULE.subprocess, "run", lambda *a, **k: completed)

    code, payload = MODULE.run_downstream({"targetVideoId": "vimeo-001", "body": {"comments": []}}, dry_run=True)
    assert code == 200
    assert payload["ok"] is True
    assert payload["mode"] == "dry_run"
    assert payload["downstream"]["targetVideoId"] == "vimeo-001"
