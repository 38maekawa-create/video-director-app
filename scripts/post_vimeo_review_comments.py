#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Post converted review comments to Vimeo API from a relay request JSON.

本番投稿モード（--dry-runなし）でVimeo APIにレビューコメントを投稿する。
リトライロジック（指数バックオフ）・レート制限対応・詳細エラーハンドリング付き。
"""

from __future__ import annotations

import argparse
import email.utils
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# リトライ設定
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # 秒
BACKOFF_MULTIPLIER = 2.0
# レート制限対応: コメント間の待機時間（秒）
COMMENT_INTERVAL = 0.5
# リトライ対象のHTTPステータスコード
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def load_payload(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('relay request must be a JSON object')
    return payload


def build_comment_text(comment: dict) -> str:
    parts = [comment['convertedText']]
    ref = comment.get('referenceExample') or {}
    if ref.get('url'):
        parts.append(f"参考事例: {ref['url']}")
    if ref.get('note'):
        parts.append(f"補足: {ref['note']}")
    return "\n\n".join(parts)


def build_vimeo_payload(comment: dict) -> dict:
    payload = {'text': build_comment_text(comment)}
    mode = os.getenv('VIMEO_TIMECODE_MODE', 'embed_text').strip()
    field_name = os.getenv('VIMEO_TIMECODE_FIELD', 'timecode').strip() or 'timecode'

    if mode == 'body_field':
        payload[field_name] = comment.get('timestampSeconds')
    elif mode == 'embed_text':
        payload['text'] = f"[{comment.get('timestamp', '-')}] {payload['text']}"
    elif mode == 'skip':
        pass
    else:
        raise ValueError(f'unsupported VIMEO_TIMECODE_MODE: {mode}')

    return payload


def build_endpoint(target_video_id: str) -> str:
    api_base = os.getenv('VIMEO_API_BASE', 'https://api.vimeo.com').rstrip('/')
    return f"{api_base}/videos/{target_video_id}/comments"


def post_json(url: str, token: str, payload: dict, timeout: int = 20) -> tuple[int, str]:
    """HTTP POSTを実行してステータスコードとレスポンスを返す"""
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode('utf-8')


def _parse_retry_after(value: str | None) -> float | None:
    """Retry-Afterヘッダー（秒 or HTTP-date）を秒数に変換する"""
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return max(float(raw), 0.0)
    except ValueError:
        pass

    try:
        retry_dt = email.utils.parsedate_to_datetime(raw)
        wait_sec = retry_dt.timestamp() - time.time()
        return max(wait_sec, 0.0)
    except (ValueError, TypeError, OverflowError):
        return None


def _is_retryable_http_status(status_code: int | None) -> bool:
    return status_code in RETRYABLE_STATUS_CODES if status_code is not None else False


def _build_retryable_http_result(status_code: int, response_text: str, retries: int) -> dict:
    return {
        'status': 'failed',
        'httpStatus': status_code,
        'response': response_text,
        'retries': retries,
        'errorCode': f'http_{status_code}',
        'retryable': _is_retryable_http_status(status_code),
    }


def post_with_retry(
    url: str,
    token: str,
    payload: dict,
    max_retries: int = MAX_RETRIES,
    initial_backoff: float = INITIAL_BACKOFF,
) -> dict:
    """リトライロジック付きのPOST

    指数バックオフで最大max_retries回リトライする。
    429（レート制限）の場合はRetry-Afterヘッダーを尊重する。

    Returns:
        dict: {"status": "posted"|"failed", "httpStatus": int, "response": str, "retries": int}
    """
    backoff = initial_backoff
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            status, response_text = post_json(url, token, payload)
            result = {
                'status': 'posted' if 200 <= status < 300 else 'failed',
                'httpStatus': status,
                'response': response_text,
                'retries': attempt,
                'retryable': _is_retryable_http_status(status),
            }
            # 成功 or リトライ不要なエラー
            if 200 <= status < 300 or status not in RETRYABLE_STATUS_CODES:
                return result
            last_error = result

        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode('utf-8', errors='replace')
            last_error = _build_retryable_http_result(exc.code, error_body, attempt)

            if exc.code not in RETRYABLE_STATUS_CODES:
                return last_error

            # 429の場合、Retry-Afterヘッダーを確認
            if exc.code == 429:
                retry_after = _parse_retry_after(exc.headers.get('Retry-After'))
                if retry_after is not None:
                    backoff = max(retry_after, backoff)

        except urllib.error.URLError as exc:
            last_error = {
                'status': 'failed',
                'response': f'URLError: {exc}',
                'retries': attempt,
                'errorCode': 'network_error',
                'retryable': True,
            }

        except TimeoutError:
            last_error = {
                'status': 'failed',
                'response': 'Request timed out',
                'retries': attempt,
                'errorCode': 'timeout',
                'retryable': True,
            }

        # リトライ前にバックオフ待機（最後の試行の後は待機しない）
        if attempt < max_retries:
            print(f"    ⏳ リトライ {attempt + 1}/{max_retries} ({backoff:.1f}秒後)...",
                  file=sys.stderr)
            time.sleep(backoff)
            backoff *= BACKOFF_MULTIPLIER

    return last_error


def save_output(path: str | None, payload: dict) -> None:
    if not path:
        return
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def load_token() -> str:
    """Vimeo APIトークンを取得（環境変数 → api-keys.env）"""
    token = os.getenv('VIMEO_ACCESS_TOKEN')
    if token:
        return token.strip()

    # api-keys.envからフォールバック読み込み
    env_file = Path.home() / ".config" / "maekawa" / "api-keys.env"
    if env_file.exists():
        for line in env_file.read_text().split("\n"):
            line = line.strip()
            if line.startswith("VIMEO_ACCESS_TOKEN="):
                return line.split("=", 1)[1].strip()

    raise ValueError(
        'VIMEO_ACCESS_TOKEN is required. Set it as an environment variable '
        'or add it to ~/.config/maekawa/api-keys.env'
    )


def _validate_comment(comment: dict) -> tuple[bool, list[str]]:
    missing = []
    if not comment.get('feedbackId'):
        missing.append('feedbackId')
    if not comment.get('convertedText'):
        missing.append('convertedText')
    if comment.get('timestampSeconds') is None:
        missing.append('timestampSeconds')

    if missing:
        return False, missing

    try:
        timestamp_seconds = float(comment['timestampSeconds'])
    except (ValueError, TypeError):
        return False, ['timestampSeconds(invalid_number)']

    if timestamp_seconds < 0:
        return False, ['timestampSeconds(negative)']

    return True, []


def main() -> int:
    parser = argparse.ArgumentParser(description='Post converted review comments to Vimeo API')
    parser.add_argument('json_path', help='Path to relay request JSON file')
    parser.add_argument('--dry-run', action='store_true', help='Print Vimeo request plan instead of posting')
    parser.add_argument('--output', help='Optional path to save the Vimeo result JSON')
    parser.add_argument('--max-retries', type=int, default=MAX_RETRIES,
                        help=f'Max retries per comment (default: {MAX_RETRIES})')
    parser.add_argument('--interval', type=float, default=COMMENT_INTERVAL,
                        help=f'Interval between comments in seconds (default: {COMMENT_INTERVAL})')
    args = parser.parse_args()

    try:
        if args.max_retries < 0:
            raise ValueError('--max-retries must be >= 0')
        if args.interval < 0:
            raise ValueError('--interval must be >= 0')

        relay_request = load_payload(Path(args.json_path))
        body = relay_request.get('body') or {}
        target_video_id = relay_request.get('targetVideoId') or body.get('targetVideoId')
        comments = body.get('comments') or []
        if not target_video_id:
            raise ValueError('targetVideoId is required')
        if not isinstance(comments, list):
            raise ValueError('body.comments must be an array')

        endpoint = build_endpoint(target_video_id)
        plan = []
        seen_feedback_ids = set()
        for comment in comments:
            valid, reasons = _validate_comment(comment)
            feedback_id = comment.get('feedbackId')
            if valid and feedback_id in seen_feedback_ids:
                valid = False
                reasons = ['duplicate feedbackId']
            if not valid:
                plan.append({
                    'feedbackId': feedback_id,
                    'status': 'skipped',
                    'reason': ', '.join(reasons),
                })
                continue

            seen_feedback_ids.add(feedback_id)
            payload = build_vimeo_payload(comment)
            plan.append({
                'feedbackId': feedback_id,
                'endpoint': endpoint,
                'payload': payload,
            })

        if args.dry_run:
            dry_payload = {'targetVideoId': target_video_id, 'requests': plan}
            save_output(args.output, dry_payload)
            print(json.dumps(dry_payload, ensure_ascii=False, indent=2))
            return 0

        token = load_token()

        results = []
        posted_count = 0
        failed_count = 0
        skipped_count = 0
        retryable_failed_count = 0

        for i, item in enumerate(plan):
            if item.get('status') == 'skipped':
                results.append(item)
                skipped_count += 1
                continue

            feedback_id = item['feedbackId']
            print(f"  📤 投稿中 [{i+1}/{len(plan)}]: {feedback_id}", file=sys.stderr)

            result = post_with_retry(
                item['endpoint'], token, item['payload'],
                max_retries=args.max_retries,
            )
            result['feedbackId'] = feedback_id

            if result['status'] == 'posted':
                posted_count += 1
                print(f"    ✅ 成功 (HTTP {result.get('httpStatus', '?')})", file=sys.stderr)
            else:
                failed_count += 1
                if result.get('retryable'):
                    retryable_failed_count += 1
                print(f"    ❌ 失敗 (HTTP {result.get('httpStatus', '?')}): "
                      f"{result.get('response', '')[:100]}", file=sys.stderr)

            results.append(result)

            # コメント間のインターバル（レート制限対策、最後の1件は不要）
            if i < len(plan) - 1 and args.interval > 0:
                time.sleep(args.interval)

        # サマリー出力
        print(f"\n📊 投稿結果: {posted_count}件成功 / {failed_count}件失敗 / "
              f"{skipped_count}件スキップ / 全{len(plan)}件", file=sys.stderr)

        result_payload = {
            'targetVideoId': target_video_id,
            'results': results,
            'summary': {
                'total': len(plan),
                'posted': posted_count,
                'failed': failed_count,
                'skipped': skipped_count,
                'retryable_failed': retryable_failed_count,
                'permanent_failed': max(failed_count - retryable_failed_count, 0),
            },
        }
        save_output(args.output, result_payload)
        print(json.dumps(result_payload, ensure_ascii=False, indent=2))
        return 1 if failed_count > 0 else 0
    except Exception as exc:
        error_payload = {'status': 'error', 'error': str(exc)}
        save_output(args.output, error_payload)
        print(json.dumps(error_payload, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
