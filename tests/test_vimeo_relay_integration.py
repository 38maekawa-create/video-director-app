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


def test_load_relay_token_from_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("VIMEO_RELAY_TOKEN", raising=False)
    fake_home = tmp_path / "home"
    env_dir = fake_home / ".config" / "maekawa"
    env_dir.mkdir(parents=True)
    (env_dir / "api-keys.env").write_text("VIMEO_RELAY_TOKEN=file-token\n", encoding="utf-8")
    monkeypatch.setattr(MODULE.Path, "home", lambda: fake_home)

    token = MODULE.load_relay_token("post")
    assert token == "file-token"


def test_load_relay_token_raises_in_post_mode(monkeypatch, tmp_path):
    monkeypatch.delenv("VIMEO_RELAY_TOKEN", raising=False)
    fake_home = tmp_path / "home"
    monkeypatch.setattr(MODULE.Path, "home", lambda: fake_home)

    try:
        MODULE.load_relay_token("post")
    except ValueError as exc:
        assert "VIMEO_RELAY_TOKEN is required" in str(exc)
    else:
        raise AssertionError("ValueError was not raised")


def test_extract_retry_queue_items_collects_only_retryable_failed():
    payload = {
        "body": {
            "comments": [
                {"feedbackId": "fb-1", "convertedText": "retry me"},
                {"feedbackId": "fb-2", "convertedText": "skip me"},
            ]
        }
    }
    response_payload = {
        "mode": "post",
        "downstream": {
            "results": [
                {"feedbackId": "fb-1", "status": "failed", "retryable": True, "errorCode": "network_error"},
                {"feedbackId": "fb-2", "status": "failed", "retryable": False, "errorCode": "http_400"},
                {"feedbackId": "fb-3", "status": "posted"},
            ]
        },
    }

    items = MODULE.extract_retry_queue_items(payload, response_payload)
    assert len(items) == 1
    assert items[0]["feedbackId"] == "fb-1"
    assert items[0]["comment"]["convertedText"] == "retry me"


def test_persist_request_log_and_retry_queue(tmp_path):
    payload = {
        "projectId": "proj-001",
        "videoId": "video-001",
        "targetVideoId": "vimeo-001",
        "body": {
            "comments": [{"feedbackId": "fb-1", "timestampSeconds": 10, "convertedText": "text"}]
        },
    }
    response_payload = {
        "mode": "post",
        "downstream": {
            "results": [
                {
                    "feedbackId": "fb-1",
                    "status": "failed",
                    "retryable": True,
                    "errorCode": "network_error",
                    "response": "timeout",
                }
            ]
        },
    }

    queue_file = MODULE.persist_retry_queue(
        tmp_path,
        payload,
        response_payload,
        project_id="proj-001",
        video_id="video-001",
        target_video_id="vimeo-001",
    )
    assert queue_file is not None
    assert queue_file.exists()
    queue_data = json.loads(queue_file.read_text(encoding="utf-8"))
    assert len(queue_data["items"]) == 1
    assert queue_data["items"][0]["feedbackId"] == "fb-1"

    log_file = MODULE.persist_request_log(
        tmp_path,
        payload,
        response_payload,
        mode="post",
        project_id="proj-001",
        request_id="req123",
    )
    assert log_file.exists()
    log_data = json.loads(log_file.read_text(encoding="utf-8"))
    assert log_data["requestId"] == "req123"
