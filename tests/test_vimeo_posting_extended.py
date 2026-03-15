"""post_vimeo_review_comments.py の拡張テスト

既存の test_post_vimeo_review_comments.py を補完する追加テストケース。
Vimeo APIへの実リクエストは行わず、全てモックで検証する。
"""

import io
import json
import sys
import urllib.error
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# スクリプトモジュールの動的ロード
SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "post_vimeo_review_comments.py"
SPEC = spec_from_file_location("post_vimeo_review_comments", SCRIPT_PATH)
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


# ---------------------------------------------------------------------------
# build_comment_text() のフォーマット確認
# ---------------------------------------------------------------------------
class TestBuildCommentText:
    """コメントテキスト組み立てのテスト"""

    def test_priority_medium_prefix(self):
        """優先度「中」のプレフィックスが付与されること"""
        comment = {
            "convertedText": "カット位置を調整してください",
            "priority": "中",
        }
        text = MODULE.build_comment_text(comment)
        assert text.startswith("🟡【優先度: 中】")
        assert "カット位置を調整してください" in text

    def test_unknown_priority_no_prefix(self):
        """定義外の優先度値ではプレフィックスが付かないこと"""
        comment = {
            "convertedText": "修正お願いします",
            "priority": "最高",
        }
        text = MODULE.build_comment_text(comment)
        assert "優先度" not in text
        assert text == "修正お願いします"

    def test_whitespace_priority_treated_as_none(self):
        """空白のみの優先度はプレフィックスなしになること"""
        comment = {
            "convertedText": "テスト",
            "priority": "   ",
        }
        text = MODULE.build_comment_text(comment)
        assert "優先度" not in text

    def test_reference_url_only(self):
        """参考URL付き・補足なしの場合にURLのみ追加されること"""
        comment = {
            "convertedText": "BGM調整",
            "referenceExample": {"url": "https://example.com/ref"},
        }
        text = MODULE.build_comment_text(comment)
        assert "参考事例: https://example.com/ref" in text
        assert "補足:" not in text

    def test_reference_note_only(self):
        """補足のみ（URLなし）の場合に補足だけ追加されること"""
        comment = {
            "convertedText": "テロップ修正",
            "referenceExample": {"note": "スタイルは統一"},
        }
        text = MODULE.build_comment_text(comment)
        assert "参考事例:" not in text
        assert "補足: スタイルは統一" in text

    def test_reference_url_and_note(self):
        """URL+補足の両方が正しくフォーマットされること"""
        comment = {
            "convertedText": "カラーグレーディング",
            "priority": "高",
            "referenceExample": {
                "url": "https://example.com/grade",
                "note": "暖色系で",
            },
        }
        text = MODULE.build_comment_text(comment)
        parts = text.split("\n\n")
        assert len(parts) == 3
        assert parts[0].startswith("🔴【優先度: 高】")
        assert "カラーグレーディング" in parts[0]
        assert parts[1] == "参考事例: https://example.com/grade"
        assert parts[2] == "補足: 暖色系で"

    def test_empty_reference_object(self):
        """空の参考事例オブジェクトでは追記されないこと"""
        comment = {
            "convertedText": "そのまま",
            "referenceExample": {},
        }
        text = MODULE.build_comment_text(comment)
        assert text == "そのまま"

    def test_all_three_priorities(self):
        """高・中・低の全優先度ラベルが正しいこと"""
        for priority, emoji in [("高", "🔴"), ("中", "🟡"), ("低", "🟢")]:
            comment = {"convertedText": "test", "priority": priority}
            text = MODULE.build_comment_text(comment)
            assert emoji in text
            assert f"【優先度: {priority}】" in text


# ---------------------------------------------------------------------------
# build_vimeo_payload() の各モード検証
# ---------------------------------------------------------------------------
class TestBuildVimeoPayload:
    """Vimeoペイロード構築のテスト（環境変数でモード切替）"""

    def test_embed_text_mode(self, monkeypatch):
        """embed_textモード: タイムスタンプがテキスト先頭に埋め込まれること"""
        monkeypatch.setenv("VIMEO_TIMECODE_MODE", "embed_text")
        comment = {
            "convertedText": "ここを修正",
            "timestamp": "01:30",
            "timestampSeconds": 90,
        }
        payload = MODULE.build_vimeo_payload(comment)
        assert payload["text"].startswith("[01:30]")
        assert "ここを修正" in payload["text"]
        # body_fieldのキーは含まれないこと
        assert "timecode" not in payload or payload.get("timecode") is None

    def test_body_field_mode(self, monkeypatch):
        """body_fieldモード: タイムスタンプ秒数がペイロードのフィールドに設定されること"""
        monkeypatch.setenv("VIMEO_TIMECODE_MODE", "body_field")
        monkeypatch.setenv("VIMEO_TIMECODE_FIELD", "timecode")
        comment = {
            "convertedText": "音声修正",
            "timestamp": "02:00",
            "timestampSeconds": 120,
        }
        payload = MODULE.build_vimeo_payload(comment)
        assert payload["timecode"] == 120
        # テキストにタイムスタンプが埋め込まれていないこと
        assert not payload["text"].startswith("[")

    def test_body_field_mode_custom_field_name(self, monkeypatch):
        """body_fieldモードでカスタムフィールド名を使用できること"""
        monkeypatch.setenv("VIMEO_TIMECODE_MODE", "body_field")
        monkeypatch.setenv("VIMEO_TIMECODE_FIELD", "time_offset")
        comment = {
            "convertedText": "テスト",
            "timestamp": "00:30",
            "timestampSeconds": 30,
        }
        payload = MODULE.build_vimeo_payload(comment)
        assert payload["time_offset"] == 30
        assert "timecode" not in payload

    def test_skip_mode(self, monkeypatch):
        """skipモード: タイムコード情報がペイロードに含まれないこと"""
        monkeypatch.setenv("VIMEO_TIMECODE_MODE", "skip")
        comment = {
            "convertedText": "タイムコードなし",
            "timestamp": "05:00",
            "timestampSeconds": 300,
        }
        payload = MODULE.build_vimeo_payload(comment)
        assert "timecode" not in payload
        assert not payload["text"].startswith("[")
        assert payload["text"] == "タイムコードなし"

    def test_unsupported_mode_raises(self, monkeypatch):
        """未知のモードでValueErrorが発生すること"""
        monkeypatch.setenv("VIMEO_TIMECODE_MODE", "unknown_mode")
        comment = {
            "convertedText": "テスト",
            "timestamp": "00:00",
            "timestampSeconds": 0,
        }
        with pytest.raises(ValueError, match="unsupported VIMEO_TIMECODE_MODE"):
            MODULE.build_vimeo_payload(comment)

    def test_embed_text_missing_timestamp_uses_dash(self, monkeypatch):
        """embed_textモードでtimestampが無い場合は'-'が使われること"""
        monkeypatch.setenv("VIMEO_TIMECODE_MODE", "embed_text")
        comment = {
            "convertedText": "タイムスタンプなし",
            "timestampSeconds": 0,
        }
        payload = MODULE.build_vimeo_payload(comment)
        assert payload["text"].startswith("[-]")


# ---------------------------------------------------------------------------
# タイムコード・タイムスタンプ秒数のバリデーション
# ---------------------------------------------------------------------------
class TestTimestampValidation:
    """timestampSecondsのバリデーションテスト"""

    def test_zero_seconds_is_valid(self):
        """0秒は有効な値として扱われること"""
        comment = {
            "feedbackId": "fb-zero",
            "convertedText": "冒頭のフィードバック",
            "timestampSeconds": 0,
        }
        valid, reasons = MODULE._validate_comment(comment)
        assert valid is True

    def test_large_seconds_is_valid(self):
        """大きな秒数（長時間動画）も有効であること"""
        comment = {
            "feedbackId": "fb-large",
            "convertedText": "3時間地点のフィードバック",
            "timestampSeconds": 10800,  # 3時間
        }
        valid, reasons = MODULE._validate_comment(comment)
        assert valid is True

    def test_float_seconds_is_valid(self):
        """小数秒が有効であること"""
        comment = {
            "feedbackId": "fb-float",
            "convertedText": "フレーム単位の指定",
            "timestampSeconds": 150.5,
        }
        valid, reasons = MODULE._validate_comment(comment)
        assert valid is True

    def test_negative_seconds_is_invalid(self):
        """負の秒数はバリデーションエラーになること"""
        comment = {
            "feedbackId": "fb-neg",
            "convertedText": "テスト",
            "timestampSeconds": -10,
        }
        valid, reasons = MODULE._validate_comment(comment)
        assert valid is False
        assert "timestampSeconds(negative)" in reasons

    def test_nan_string_is_invalid(self):
        """文字列'NaN'はバリデーションエラーになること"""
        comment = {
            "feedbackId": "fb-nan",
            "convertedText": "テスト",
            "timestampSeconds": "NaN",
        }
        valid, reasons = MODULE._validate_comment(comment)
        assert valid is False

    def test_infinity_is_invalid(self):
        """float('inf')はバリデーションエラーになること"""
        comment = {
            "feedbackId": "fb-inf",
            "convertedText": "テスト",
            "timestampSeconds": float("inf"),
        }
        valid, reasons = MODULE._validate_comment(comment)
        assert valid is False
        assert "timestampSeconds(non_finite)" in reasons

    def test_non_numeric_string_is_invalid(self):
        """数値に変換できない文字列はバリデーションエラーになること"""
        comment = {
            "feedbackId": "fb-str",
            "convertedText": "テスト",
            "timestampSeconds": "abc",
        }
        valid, reasons = MODULE._validate_comment(comment)
        assert valid is False
        assert "timestampSeconds(invalid_number)" in reasons


# ---------------------------------------------------------------------------
# post_with_retry() のリトライロジック（モック）
# ---------------------------------------------------------------------------
class TestPostWithRetry:
    """リトライロジックのテスト"""

    def test_success_on_first_attempt(self, monkeypatch):
        """初回成功時はリトライなしで返ること"""
        monkeypatch.setattr(
            MODULE, "post_json",
            lambda *a, **kw: (201, '{"ok": true}'),
        )
        result = MODULE.post_with_retry("http://test", "tok", {"text": "t"})
        assert result["status"] == "posted"
        assert result["retries"] == 0

    def test_exhausts_all_retries_on_500(self, monkeypatch):
        """500エラーが続く場合に全リトライを使い切ること"""
        call_count = {"n": 0}

        def always_500(*a, **kw):
            call_count["n"] += 1
            raise urllib.error.HTTPError(
                url="http://test", code=500, msg="ISE",
                hdrs=None, fp=io.BytesIO(b"error"),
            )

        monkeypatch.setattr(MODULE, "post_json", always_500)
        monkeypatch.setattr(MODULE.time, "sleep", lambda _: None)

        result = MODULE.post_with_retry(
            "http://test", "tok", {"text": "t"},
            max_retries=2, initial_backoff=0.01,
        )
        assert result["status"] == "failed"
        assert result["httpStatus"] == 500
        assert result["retries"] == 2
        # 初回 + 2回リトライ = 計3回
        assert call_count["n"] == 3

    def test_timeout_error_is_retried(self, monkeypatch):
        """TimeoutErrorがリトライ対象になること"""
        call_count = {"n": 0}

        def timeout_then_ok(*a, **kw):
            call_count["n"] += 1
            if call_count["n"] <= 2:
                raise TimeoutError("timed out")
            return (200, '{"ok": true}')

        monkeypatch.setattr(MODULE, "post_json", timeout_then_ok)
        monkeypatch.setattr(MODULE.time, "sleep", lambda _: None)

        result = MODULE.post_with_retry(
            "http://test", "tok", {"text": "t"},
            max_retries=3, initial_backoff=0.01,
        )
        assert result["status"] == "posted"
        assert result["retries"] == 2

    def test_backoff_increases_exponentially(self, monkeypatch):
        """バックオフが指数的に増加すること"""
        sleep_values = []

        def record_sleep(seconds):
            sleep_values.append(seconds)

        def always_503(*a, **kw):
            raise urllib.error.HTTPError(
                url="http://test", code=503, msg="Unavailable",
                hdrs=None, fp=io.BytesIO(b""),
            )

        monkeypatch.setattr(MODULE, "post_json", always_503)
        monkeypatch.setattr(MODULE.time, "sleep", record_sleep)

        MODULE.post_with_retry(
            "http://test", "tok", {"text": "t"},
            max_retries=3, initial_backoff=1.0,
        )
        # 3回リトライ → sleep 3回（最後の試行後はsleepなし）
        assert len(sleep_values) == 3
        assert sleep_values[0] == pytest.approx(1.0)
        assert sleep_values[1] == pytest.approx(2.0)
        assert sleep_values[2] == pytest.approx(4.0)

    def test_429_respects_retry_after_header(self, monkeypatch):
        """429エラーでRetry-Afterヘッダーを尊重すること"""
        sleep_values = []
        call_count = {"n": 0}

        def record_sleep(seconds):
            sleep_values.append(seconds)

        def rate_limited_then_ok(*a, **kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                headers = MagicMock()
                headers.get = lambda key, default=None: "10" if key == "Retry-After" else default
                exc = urllib.error.HTTPError(
                    url="http://test", code=429, msg="Rate Limited",
                    hdrs=headers, fp=io.BytesIO(b"rate limited"),
                )
                raise exc
            return (201, '{"ok": true}')

        monkeypatch.setattr(MODULE, "post_json", rate_limited_then_ok)
        monkeypatch.setattr(MODULE.time, "sleep", record_sleep)

        result = MODULE.post_with_retry(
            "http://test", "tok", {"text": "t"},
            max_retries=2, initial_backoff=1.0,
        )
        assert result["status"] == "posted"
        # Retry-After=10 > initial_backoff=1.0 なので10秒待機
        assert sleep_values[0] >= 10.0

    def test_non_retryable_403_returns_immediately(self, monkeypatch):
        """403（リトライ対象外）は即座にfailedを返すこと"""
        call_count = {"n": 0}

        def forbidden(*a, **kw):
            call_count["n"] += 1
            raise urllib.error.HTTPError(
                url="http://test", code=403, msg="Forbidden",
                hdrs=None, fp=io.BytesIO(b"forbidden"),
            )

        monkeypatch.setattr(MODULE, "post_json", forbidden)
        result = MODULE.post_with_retry(
            "http://test", "tok", {"text": "t"},
            max_retries=3, initial_backoff=0.01,
        )
        assert result["status"] == "failed"
        assert result["httpStatus"] == 403
        assert result["retries"] == 0
        # リトライなしで1回のみ呼ばれること
        assert call_count["n"] == 1

    def test_zero_max_retries(self, monkeypatch):
        """max_retries=0ではリトライしないこと"""
        def always_500(*a, **kw):
            raise urllib.error.HTTPError(
                url="http://test", code=500, msg="ISE",
                hdrs=None, fp=io.BytesIO(b"error"),
            )

        monkeypatch.setattr(MODULE, "post_json", always_500)
        result = MODULE.post_with_retry(
            "http://test", "tok", {"text": "t"},
            max_retries=0, initial_backoff=0.01,
        )
        assert result["status"] == "failed"
        assert result["retries"] == 0


# ---------------------------------------------------------------------------
# dry_runモードの出力形式
# ---------------------------------------------------------------------------
class TestDryRunOutput:
    """dry-runモードの出力形式テスト"""

    def _run_dry_run(self, monkeypatch, tmp_path, capsys, comments):
        """dry-run実行のヘルパー"""
        relay = {
            "targetVideoId": "vid-dry",
            "body": {
                "targetVideoId": "vid-dry",
                "comments": comments,
            },
        }
        json_path = tmp_path / "relay.json"
        json_path.write_text(json.dumps(relay, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(
            sys, "argv",
            ["post_vimeo_review_comments.py", str(json_path)],
        )
        rc = MODULE.main()
        out = capsys.readouterr().out
        return rc, json.loads(out)

    def test_dry_run_output_structure(self, monkeypatch, tmp_path, capsys):
        """dry-run出力にtargetVideoIdとrequestsが含まれること"""
        comments = [
            {"feedbackId": "fb-1", "timestampSeconds": 10, "convertedText": "ok"},
        ]
        rc, data = self._run_dry_run(monkeypatch, tmp_path, capsys, comments)
        assert rc == 0
        assert data["targetVideoId"] == "vid-dry"
        assert "requests" in data
        assert len(data["requests"]) == 1

    def test_dry_run_valid_comment_has_endpoint_and_payload(self, monkeypatch, tmp_path, capsys):
        """有効なコメントのdry-run出力にendpointとpayloadが含まれること"""
        comments = [
            {"feedbackId": "fb-1", "timestampSeconds": 60, "convertedText": "修正"},
        ]
        rc, data = self._run_dry_run(monkeypatch, tmp_path, capsys, comments)
        req = data["requests"][0]
        assert "endpoint" in req
        assert "payload" in req
        assert "vid-dry" in req["endpoint"]

    def test_dry_run_saves_to_output_file(self, monkeypatch, tmp_path, capsys):
        """--output指定時にファイルに保存されること"""
        relay = {
            "targetVideoId": "vid-out",
            "body": {
                "targetVideoId": "vid-out",
                "comments": [
                    {"feedbackId": "fb-1", "timestampSeconds": 5, "convertedText": "test"},
                ],
            },
        }
        json_path = tmp_path / "relay.json"
        json_path.write_text(json.dumps(relay, ensure_ascii=False), encoding="utf-8")
        output_path = tmp_path / "output" / "result.json"
        monkeypatch.setattr(
            sys, "argv",
            ["post_vimeo_review_comments.py", str(json_path), "--output", str(output_path)],
        )
        rc = MODULE.main()
        assert rc == 0
        assert output_path.exists()
        saved = json.loads(output_path.read_text(encoding="utf-8"))
        assert saved["targetVideoId"] == "vid-out"


# ---------------------------------------------------------------------------
# 空のコメントリスト時の挙動
# ---------------------------------------------------------------------------
class TestEmptyComments:
    """コメントリストが空の場合のテスト"""

    def test_dry_run_with_empty_comments(self, monkeypatch, tmp_path, capsys):
        """コメントが空でもdry-runは成功すること"""
        relay = {
            "targetVideoId": "vid-empty",
            "body": {
                "targetVideoId": "vid-empty",
                "comments": [],
            },
        }
        json_path = tmp_path / "relay.json"
        json_path.write_text(json.dumps(relay, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(
            sys, "argv",
            ["post_vimeo_review_comments.py", str(json_path)],
        )
        rc = MODULE.main()
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["requests"] == []

    def test_execute_with_empty_comments(self, monkeypatch, tmp_path, capsys):
        """コメントが空でもexecuteモードは成功すること（投稿0件）"""
        relay = {
            "targetVideoId": "vid-empty-exec",
            "body": {
                "targetVideoId": "vid-empty-exec",
                "comments": [],
            },
        }
        json_path = tmp_path / "relay.json"
        json_path.write_text(json.dumps(relay, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(MODULE, "load_token", lambda: "token")
        monkeypatch.setattr(
            sys, "argv",
            ["post_vimeo_review_comments.py", str(json_path), "--execute", "--yes"],
        )
        rc = MODULE.main()
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["summary"]["total"] == 0
        assert data["summary"]["posted"] == 0


# ---------------------------------------------------------------------------
# 不正なVimeo Video IDのエラーハンドリング
# ---------------------------------------------------------------------------
class TestInvalidVideoId:
    """不正な動画IDのテスト"""

    def test_missing_video_id_raises_error(self, monkeypatch, tmp_path, capsys):
        """targetVideoIdが無い場合にエラーになること"""
        relay = {
            "body": {
                "comments": [
                    {"feedbackId": "fb-1", "timestampSeconds": 10, "convertedText": "テスト"},
                ],
            },
        }
        json_path = tmp_path / "relay.json"
        json_path.write_text(json.dumps(relay, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(
            sys, "argv",
            ["post_vimeo_review_comments.py", str(json_path)],
        )
        rc = MODULE.main()
        assert rc == 1
        err = capsys.readouterr().err
        assert "targetVideoId" in err

    def test_empty_string_video_id_raises_error(self, monkeypatch, tmp_path, capsys):
        """targetVideoIdが空文字列の場合にエラーになること"""
        relay = {
            "targetVideoId": "",
            "body": {
                "targetVideoId": "",
                "comments": [],
            },
        }
        json_path = tmp_path / "relay.json"
        json_path.write_text(json.dumps(relay, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(
            sys, "argv",
            ["post_vimeo_review_comments.py", str(json_path)],
        )
        rc = MODULE.main()
        assert rc == 1

    def test_video_id_used_in_endpoint(self, monkeypatch):
        """動画IDがエンドポイントURLに正しく組み込まれること"""
        endpoint = MODULE.build_endpoint("12345678")
        assert "/videos/12345678/comments" in endpoint

    def test_custom_api_base(self, monkeypatch):
        """VIMEO_API_BASE環境変数でAPIベースURLを変更できること"""
        monkeypatch.setenv("VIMEO_API_BASE", "https://custom.vimeo.test/api")
        endpoint = MODULE.build_endpoint("vid-custom")
        assert endpoint == "https://custom.vimeo.test/api/videos/vid-custom/comments"


# ---------------------------------------------------------------------------
# APIレート制限（429）対応のバックオフ
# ---------------------------------------------------------------------------
class TestRateLimitBackoff:
    """429レート制限のバックオフ挙動テスト"""

    def test_retry_after_seconds_parsed_correctly(self):
        """Retry-Afterヘッダー（秒数指定）が正しくパースされること"""
        assert MODULE._parse_retry_after("30") == 30.0
        assert MODULE._parse_retry_after("0") == 0.0
        assert MODULE._parse_retry_after("0.5") == 0.5

    def test_retry_after_none_returns_none(self):
        """Retry-Afterがnullの場合はNoneが返ること"""
        assert MODULE._parse_retry_after(None) is None

    def test_retry_after_empty_string_returns_none(self):
        """Retry-Afterが空文字列の場合はNoneが返ること"""
        assert MODULE._parse_retry_after("") is None
        assert MODULE._parse_retry_after("   ") is None

    def test_retry_after_invalid_string_returns_none(self):
        """Retry-Afterが不正な文字列の場合はNoneが返ること"""
        result = MODULE._parse_retry_after("not-a-date-or-number")
        assert result is None

    def test_retryable_status_codes(self):
        """リトライ対象のステータスコードが正しく判定されること"""
        for code in [429, 500, 502, 503, 504]:
            assert MODULE._is_retryable_http_status(code) is True
        for code in [200, 201, 400, 401, 403, 404]:
            assert MODULE._is_retryable_http_status(code) is False
        assert MODULE._is_retryable_http_status(None) is False

    def test_429_all_retries_exhausted(self, monkeypatch):
        """429が続く場合に全リトライ消費後にfailedを返すこと"""
        sleep_values = []

        def record_sleep(s):
            sleep_values.append(s)

        # headersにMagicMockを使用（hdrs=Noneだとexc.headers.get()でAttributeError）
        mock_headers = MagicMock()
        mock_headers.get = lambda key, default=None: default

        def always_429(*a, **kw):
            raise urllib.error.HTTPError(
                url="http://test", code=429, msg="Too Many Requests",
                hdrs=mock_headers, fp=io.BytesIO(b"rate limited"),
            )

        monkeypatch.setattr(MODULE, "post_json", always_429)
        monkeypatch.setattr(MODULE.time, "sleep", record_sleep)

        result = MODULE.post_with_retry(
            "http://test", "tok", {"text": "t"},
            max_retries=2, initial_backoff=1.0,
        )
        assert result["status"] == "failed"
        assert result["httpStatus"] == 429
        assert result["retries"] == 2
        assert result["retryable"] is True


# ---------------------------------------------------------------------------
# _validate_comment() の追加テスト
# ---------------------------------------------------------------------------
class TestValidateComment:
    """コメントバリデーションの追加テスト"""

    def test_whitespace_feedback_id_stripped(self):
        """feedbackIdの前後の空白がトリムされること"""
        comment = {
            "feedbackId": "  fb-trim  ",
            "convertedText": "テスト",
            "timestampSeconds": 10,
        }
        valid, _ = MODULE._validate_comment(comment)
        assert valid is True
        assert comment["feedbackId"] == "fb-trim"

    def test_whitespace_converted_text_stripped(self):
        """convertedTextの前後の空白がトリムされること"""
        comment = {
            "feedbackId": "fb-trim2",
            "convertedText": "  テスト  ",
            "timestampSeconds": 10,
        }
        valid, _ = MODULE._validate_comment(comment)
        assert valid is True
        assert comment["convertedText"] == "テスト"

    def test_empty_feedback_id_is_invalid(self):
        """feedbackIdが空文字列の場合は無効であること"""
        comment = {
            "feedbackId": "",
            "convertedText": "テスト",
            "timestampSeconds": 10,
        }
        valid, reasons = MODULE._validate_comment(comment)
        assert valid is False
        assert "feedbackId" in reasons

    def test_empty_converted_text_is_invalid(self):
        """convertedTextが空文字列の場合は無効であること"""
        comment = {
            "feedbackId": "fb-empty-text",
            "convertedText": "",
            "timestampSeconds": 10,
        }
        valid, reasons = MODULE._validate_comment(comment)
        assert valid is False
        assert "convertedText" in reasons

    def test_missing_all_fields_reports_all(self):
        """全フィールド欠落時に全てのmissing理由が報告されること"""
        comment = {}
        valid, reasons = MODULE._validate_comment(comment)
        assert valid is False
        assert "feedbackId" in reasons
        assert "convertedText" in reasons
        assert "timestampSeconds" in reasons

    def test_non_dict_comment_is_invalid(self):
        """コメントが辞書でない場合は無効であること"""
        valid, reasons = MODULE._validate_comment("not a dict")
        assert valid is False
        assert "comment(not_object)" in reasons

    def test_none_comment_is_invalid(self):
        """コメントがNoneの場合は無効であること"""
        valid, reasons = MODULE._validate_comment(None)
        assert valid is False


# ---------------------------------------------------------------------------
# load_payload() のエラーハンドリング
# ---------------------------------------------------------------------------
class TestLoadPayload:
    """ペイロード読み込みのテスト"""

    def test_valid_json_object(self, tmp_path):
        """有効なJSONオブジェクトが読み込めること"""
        path = tmp_path / "valid.json"
        path.write_text('{"key": "value"}', encoding="utf-8")
        result = MODULE.load_payload(path)
        assert result == {"key": "value"}

    def test_json_array_raises_error(self, tmp_path):
        """JSONが配列の場合はValueErrorが発生すること"""
        path = tmp_path / "array.json"
        path.write_text('[1, 2, 3]', encoding="utf-8")
        with pytest.raises(ValueError, match="JSON object"):
            MODULE.load_payload(path)

    def test_invalid_json_raises_error(self, tmp_path):
        """不正なJSONでエラーが発生すること"""
        path = tmp_path / "invalid.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            MODULE.load_payload(path)


# ---------------------------------------------------------------------------
# build_endpoint() のテスト
# ---------------------------------------------------------------------------
class TestBuildEndpoint:
    """エンドポイントURL構築のテスト"""

    def test_default_api_base(self, monkeypatch):
        """デフォルトでapi.vimeo.comが使われること"""
        monkeypatch.delenv("VIMEO_API_BASE", raising=False)
        endpoint = MODULE.build_endpoint("123")
        assert endpoint == "https://api.vimeo.com/videos/123/comments"

    def test_trailing_slash_stripped(self, monkeypatch):
        """APIベースURLの末尾スラッシュが除去されること"""
        monkeypatch.setenv("VIMEO_API_BASE", "https://api.vimeo.com/")
        endpoint = MODULE.build_endpoint("456")
        assert endpoint == "https://api.vimeo.com/videos/456/comments"
