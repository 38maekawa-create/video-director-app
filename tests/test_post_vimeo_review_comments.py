"""post_vimeo_review_comments.py のテスト"""

import io
import json
import sys
from datetime import datetime, timezone
import urllib.error
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "post_vimeo_review_comments.py"
SPEC = spec_from_file_location("post_vimeo_review_comments", SCRIPT_PATH)
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_parse_retry_after_seconds():
    assert MODULE._parse_retry_after("5") == 5.0


def test_parse_retry_after_http_date(monkeypatch):
    monkeypatch.setattr(MODULE.time, "time", lambda: 1000.0)
    retry_dt = datetime.fromtimestamp(1005, tz=timezone.utc)
    retry_http_date = retry_dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
    wait = MODULE._parse_retry_after(retry_http_date)
    assert wait is not None
    assert 4.0 <= wait <= 6.0


def test_post_with_retry_retries_urlerror_and_succeeds(monkeypatch):
    calls = {"count": 0}

    def fake_post_json(url, token, payload, timeout=20):
        calls["count"] += 1
        if calls["count"] < 3:
            raise urllib.error.URLError("temporary network error")
        return 201, '{"ok": true}'

    monkeypatch.setattr(MODULE, "post_json", fake_post_json)
    monkeypatch.setattr(MODULE.time, "sleep", lambda _: None)

    result = MODULE.post_with_retry(
        url="https://example.test/videos/v1/comments",
        token="token",
        payload={"text": "hello"},
        max_retries=3,
        initial_backoff=0.01,
    )
    assert result["status"] == "posted"
    assert result["httpStatus"] == 201
    assert result["retries"] == 2
    assert calls["count"] == 3


def test_post_with_retry_returns_immediately_for_non_retryable_http_error(monkeypatch):
    def fake_post_json(url, token, payload, timeout=20):
        raise urllib.error.HTTPError(
            url=url,
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"bad"}'),
        )

    monkeypatch.setattr(MODULE, "post_json", fake_post_json)
    result = MODULE.post_with_retry(
        url="https://example.test/videos/v1/comments",
        token="token",
        payload={"text": "hello"},
        max_retries=3,
        initial_backoff=0.01,
    )
    assert result["status"] == "failed"
    assert result["httpStatus"] == 400
    assert result["retries"] == 0


def test_main_live_mode_posts_without_dry_run(monkeypatch, tmp_path):
    relay_payload = {
        "targetVideoId": "vimeo-001",
        "body": {
            "targetVideoId": "vimeo-001",
            "comments": [
                {
                    "feedbackId": "fb-1",
                    "timestamp": "00:10",
                    "timestampSeconds": 10,
                    "convertedText": "ここを調整したいです",
                }
            ],
        },
    }
    json_path = tmp_path / "relay_request.json"
    json_path.write_text(json.dumps(relay_payload, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(MODULE, "load_token", lambda: "token")
    monkeypatch.setattr(
        MODULE,
        "post_with_retry",
        lambda *args, **kwargs: {
            "status": "posted",
            "httpStatus": 201,
            "response": '{"ok":true}',
            "retries": 0,
        },
    )
    monkeypatch.setattr(sys, "argv", ["post_vimeo_review_comments.py", str(json_path)])

    rc = MODULE.main()
    assert rc == 0


def test_main_dry_run_skips_invalid_and_duplicate_feedback(monkeypatch, tmp_path, capsys):
    relay_payload = {
        "targetVideoId": "vimeo-001",
        "body": {
            "targetVideoId": "vimeo-001",
            "comments": [
                {"feedbackId": "fb-1", "timestampSeconds": 10, "convertedText": "ok"},
                {"feedbackId": "fb-1", "timestampSeconds": 11, "convertedText": "duplicate"},
                {"feedbackId": "fb-2", "convertedText": "missing timestamp"},
            ],
        },
    }
    json_path = tmp_path / "relay_request.json"
    json_path.write_text(json.dumps(relay_payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["post_vimeo_review_comments.py", str(json_path), "--dry-run"],
    )

    rc = MODULE.main()
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert len(data["requests"]) == 3
    skipped = [item for item in data["requests"] if item.get("status") == "skipped"]
    assert len(skipped) == 2
    assert any(item["reason"] == "duplicate feedbackId" for item in skipped)
    assert any("timestampSeconds" in item["reason"] for item in skipped)
