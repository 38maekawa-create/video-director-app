"""send_vimeo_relay_package.py のテスト"""

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "send_vimeo_relay_package.py"
SPEC = spec_from_file_location("send_vimeo_relay_package", SCRIPT_PATH)
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_build_headers_requires_token(monkeypatch):
    monkeypatch.delenv("VIMEO_RELAY_TOKEN", raising=False)
    try:
        MODULE.build_headers({"authMode": "relay_token"})
    except ValueError as exc:
        assert "VIMEO_RELAY_TOKEN" in str(exc)
    else:
        raise AssertionError("ValueError was not raised")


def test_main_dry_run_outputs_request_plan(monkeypatch, tmp_path, capsys):
    payload = {
        "endpoint": "http://127.0.0.1:8787/api/vimeo/review-comments",
        "authMode": "none",
        "body": {"comments": []},
    }
    json_path = tmp_path / "relay_request.json"
    out_path = tmp_path / "relay_dry_run.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["send_vimeo_relay_package.py", str(json_path), "--dry-run", "--output", str(out_path)],
    )

    rc = MODULE.main()
    assert rc == 0

    stdout_text = capsys.readouterr().out
    data = json.loads(stdout_text)
    assert data["endpoint"] == payload["endpoint"]
    assert data["headers"]["Content-Type"] == "application/json"
    assert out_path.exists()


def test_main_live_mode_posts_payload(monkeypatch, tmp_path, capsys):
    payload = {
        "endpoint": "http://127.0.0.1:8787/api/vimeo/review-comments",
        "authMode": "none",
        "body": {"comments": []},
    }
    json_path = tmp_path / "relay_request.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(MODULE, "post_payload", lambda endpoint, payload, headers: (200, '{"ok":true}'))
    monkeypatch.setattr(sys, "argv", ["send_vimeo_relay_package.py", str(json_path)])

    rc = MODULE.main()
    assert rc == 0
    assert "{\"ok\":true}" in capsys.readouterr().out
