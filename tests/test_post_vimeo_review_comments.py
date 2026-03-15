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


def test_main_live_mode_posts_with_execute_flag(monkeypatch, tmp_path):
    """--execute --yes フラグを指定した場合に本番投稿が行われること"""
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
    # --execute --yes で確認プロンプトをスキップして本番投稿
    monkeypatch.setattr(
        sys, "argv",
        ["post_vimeo_review_comments.py", str(json_path), "--execute", "--yes"],
    )

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


def test_main_default_is_dry_run(monkeypatch, tmp_path, capsys):
    """引数なし（--execute未指定）でdry-runになること"""
    relay_payload = {
        "targetVideoId": "vimeo-002",
        "body": {
            "targetVideoId": "vimeo-002",
            "comments": [
                {"feedbackId": "fb-1", "timestampSeconds": 5, "convertedText": "テスト"},
            ],
        },
    }
    json_path = tmp_path / "relay_request.json"
    json_path.write_text(json.dumps(relay_payload, ensure_ascii=False), encoding="utf-8")

    # load_token / post_with_retry はモックしない（dry-runなので呼ばれないはず）
    # 万一呼ばれた場合は例外で気づけるようにする
    monkeypatch.setattr(MODULE, "load_token", lambda: (_ for _ in ()).throw(AssertionError("dry-runなのにload_tokenが呼ばれた")))
    monkeypatch.setattr(sys, "argv", ["post_vimeo_review_comments.py", str(json_path)])

    rc = MODULE.main()
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    # dry-run出力には "requests" キーが含まれる
    assert "requests" in data


def test_main_execute_cancelled_by_user(monkeypatch, tmp_path):
    """--execute 指定でユーザーが 'no' と回答した場合は中止されること"""
    relay_payload = {
        "targetVideoId": "vimeo-003",
        "body": {
            "targetVideoId": "vimeo-003",
            "comments": [
                {"feedbackId": "fb-1", "timestampSeconds": 5, "convertedText": "テスト"},
            ],
        },
    }
    json_path = tmp_path / "relay_request.json"
    json_path.write_text(json.dumps(relay_payload, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(MODULE, "load_token", lambda: "token")
    # 'no' を入力するようシミュレート
    monkeypatch.setattr("builtins.input", lambda _: "no")
    monkeypatch.setattr(sys, "argv", ["post_vimeo_review_comments.py", str(json_path), "--execute"])

    rc = MODULE.main()
    assert rc == 1


def test_build_comment_text_priority_high():
    """優先度『高』のコメントにプレフィックスが付くこと"""
    comment = {
        "feedbackId": "fb-1",
        "timestampSeconds": 10,
        "convertedText": "サムネを変えてください",
        "priority": "高",
    }
    text = MODULE.build_comment_text(comment)
    assert "🔴【優先度: 高】" in text
    assert "サムネを変えてください" in text


def test_build_comment_text_priority_low():
    """優先度『低』のコメントに低ラベルプレフィックスが付くこと"""
    comment = {
        "feedbackId": "fb-2",
        "timestampSeconds": 20,
        "convertedText": "BGMを少し下げてください",
        "priority": "低",
    }
    text = MODULE.build_comment_text(comment)
    assert "🟢【優先度: 低】" in text


def test_build_comment_text_no_priority():
    """優先度未指定のコメントにはプレフィックスが付かないこと"""
    comment = {
        "feedbackId": "fb-3",
        "timestampSeconds": 30,
        "convertedText": "テロップを修正してください",
    }
    text = MODULE.build_comment_text(comment)
    assert "優先度" not in text
    assert "テロップを修正してください" in text


def test_build_comment_text_with_reference():
    """参考事例URLと補足がコメントに含まれること"""
    comment = {
        "feedbackId": "fb-4",
        "timestampSeconds": 5,
        "convertedText": "カット割り参照",
        "priority": "中",
        "referenceExample": {"url": "https://example.com/ref", "note": "3秒ルール適用"},
    }
    text = MODULE.build_comment_text(comment)
    assert "🟡【優先度: 中】" in text
    assert "参考事例: https://example.com/ref" in text
    assert "補足: 3秒ルール適用" in text


def test_main_dry_run_skips_non_object_and_non_finite_timestamp(monkeypatch, tmp_path, capsys):
    relay_payload = {
        "targetVideoId": "vimeo-001",
        "body": {
            "targetVideoId": "vimeo-001",
            "comments": [
                "invalid-comment",
                {"feedbackId": "  fb-3  ", "timestampSeconds": "NaN", "convertedText": "  text  "},
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
    skipped = [item for item in data["requests"] if item.get("status") == "skipped"]
    assert len(skipped) == 2
    assert any("comment(not_object)" in item["reason"] for item in skipped)
    assert any("timestampSeconds(non_finite)" in item["reason"] for item in skipped)
