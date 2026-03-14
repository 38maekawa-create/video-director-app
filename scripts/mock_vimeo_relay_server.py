#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Relay server for AI開発10 Vimeo review flow.

Modes:
- mock: return fake posted results without downstream execution
- dry_run: call post_vimeo_review_comments.py --dry-run and return the plan
- post: call post_vimeo_review_comments.py for real posting
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HOST = os.getenv('VIMEO_RELAY_HOST', '127.0.0.1')
PORT = int(os.getenv('VIMEO_RELAY_PORT', '8787'))
LOG_DIR = Path(os.getenv('VIMEO_RELAY_LOG_DIR', Path.cwd() / 'runs' / 'relay_logs'))
RELAY_MODE = os.getenv('VIMEO_RELAY_MODE', 'dry_run').strip() or 'dry_run'
POST_SCRIPT = Path(__file__).with_name('post_vimeo_review_comments.py')


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def _today_key() -> str:
    return datetime.now().strftime('%Y%m%d')


def _safe_filename(value: str | None) -> str:
    if not value:
        return 'unknown'
    safe = ''.join(ch if ch.isalnum() or ch in {'-', '_'} else '_' for ch in value.strip())
    return safe[:80] or 'unknown'


def _load_env_value_from_file(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith(f'{key}='):
            return line.split('=', 1)[1].strip() or None
    return None


def load_relay_token(relay_mode: str) -> str:
    token = (os.getenv('VIMEO_RELAY_TOKEN') or '').strip()
    if token:
        return token

    env_file = Path.home() / '.config' / 'maekawa' / 'api-keys.env'
    file_token = _load_env_value_from_file(env_file, 'VIMEO_RELAY_TOKEN')
    if file_token:
        return file_token

    if relay_mode == 'mock':
        return 'dev-relay-token'
    raise ValueError(
        'VIMEO_RELAY_TOKEN is required for dry_run/post mode '
        '(env var or ~/.config/maekawa/api-keys.env)'
    )


def validate_payload(payload: dict) -> tuple[list[str], list[dict], str | None, str | None, str | None]:
    body = payload.get('body') or {}
    comments = body.get('comments') or []
    project_id = payload.get('projectId')
    video_id = payload.get('videoId')
    target_video_id = payload.get('targetVideoId') or body.get('targetVideoId')

    missing = []
    for field, value in [('projectId', project_id), ('videoId', video_id), ('targetVideoId', target_video_id)]:
        if not value:
            missing.append(field)
    return missing, comments, project_id, video_id, target_video_id


def build_mock_results(comments: list[dict]) -> tuple[list[dict], int]:
    results = []
    for item in comments:
        if not item.get('feedbackId') or item.get('timestampSeconds') is None or not item.get('convertedText'):
            results.append({
                'feedbackId': item.get('feedbackId'),
                'status': 'failed',
                'error': 'invalid_comment_payload',
            })
            continue
        results.append({
            'feedbackId': item['feedbackId'],
            'status': 'posted',
            'vimeoCommentId': f"mock-{item['feedbackId']}",
            'timestampSeconds': item['timestampSeconds'],
        })
    posted_count = len([r for r in results if r['status'] == 'posted'])
    return results, posted_count


def run_downstream(payload: dict, dry_run: bool) -> tuple[int, dict]:
    if not POST_SCRIPT.exists():
        return 500, {'ok': False, 'error': f'post_script_missing: {POST_SCRIPT}'}

    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as temp_file:
        temp_file.write(json.dumps(payload, ensure_ascii=False, indent=2))
        temp_path = Path(temp_file.name)

    try:
        command = ['python3', str(POST_SCRIPT), str(temp_path)]
        if dry_run:
            command.append('--dry-run')
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        output = (completed.stdout or completed.stderr or '').strip()
        if not output:
            return 500, {'ok': False, 'error': 'downstream_empty_response'}
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return 500, {
                'ok': False,
                'error': 'downstream_invalid_json',
                'stdout': completed.stdout,
                'stderr': completed.stderr,
                'returncode': completed.returncode,
            }
        status_code = 200 if completed.returncode == 0 else 502
        return status_code, {
            'ok': completed.returncode == 0,
            'mode': 'dry_run' if dry_run else 'post',
            'downstream': data,
            'returncode': completed.returncode,
        }
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


def extract_retry_queue_items(payload: dict, response_payload: dict) -> list[dict]:
    if response_payload.get('mode') != 'post':
        return []
    downstream = response_payload.get('downstream') or {}
    results = downstream.get('results') or []
    original_comments = (payload.get('body') or {}).get('comments') or []
    comments_by_feedback_id = {
        item.get('feedbackId'): item for item in original_comments if isinstance(item, dict)
    }

    queue_items = []
    for result in results:
        if not isinstance(result, dict):
            continue
        if result.get('status') != 'failed' or not result.get('retryable'):
            continue
        feedback_id = result.get('feedbackId')
        queue_items.append({
            'feedbackId': feedback_id,
            'errorCode': result.get('errorCode') or 'unknown',
            'httpStatus': result.get('httpStatus'),
            'response': result.get('response'),
            'comment': comments_by_feedback_id.get(feedback_id),
        })
    return queue_items


def persist_request_log(
    log_dir: Path,
    payload: dict,
    response_payload: dict,
    mode: str,
    project_id: str | None,
    request_id: str,
) -> Path:
    day_dir = log_dir / _today_key()
    day_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    file_path = day_dir / f'{stamp}-{_safe_filename(project_id)}-{request_id}.json'
    file_path.write_text(
        json.dumps(
            {'requestId': request_id, 'receivedAt': now_iso(), 'mode': mode, 'payload': payload, 'response': response_payload},
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    return file_path


def persist_retry_queue(
    log_dir: Path,
    payload: dict,
    response_payload: dict,
    project_id: str | None,
    video_id: str | None,
    target_video_id: str | None,
) -> Path | None:
    queue_items = extract_retry_queue_items(payload, response_payload)
    if not queue_items:
        return None

    day_dir = log_dir / 'retry_queue' / _today_key()
    day_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    queue_file = day_dir / f'{stamp}-{_safe_filename(project_id)}.json'
    queue_file.write_text(
        json.dumps(
            {
                'createdAt': now_iso(),
                'projectId': project_id,
                'videoId': video_id,
                'targetVideoId': target_video_id,
                'items': queue_items,
                'originalPayload': payload,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    return queue_file


class RelayHandler(BaseHTTPRequestHandler):
    server_version = 'AIDev10Relay/0.2'

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != '/api/vimeo/review-comments':
            self._send_json(404, {'ok': False, 'error': 'not_found'})
            return

        request_id = uuid.uuid4().hex[:10]

        try:
            relay_token = load_relay_token(RELAY_MODE)
        except ValueError as exc:
            self._send_json(500, {'ok': False, 'error': str(exc)})
            return

        auth = self.headers.get('Authorization', '')
        if auth != f'Bearer {relay_token}':
            self._send_json(401, {'ok': False, 'error': 'unauthorized'})
            return

        try:
            content_length = int(self.headers.get('Content-Length', '0'))
            raw = self.rfile.read(content_length)
            payload = json.loads(raw.decode('utf-8'))
        except Exception as exc:
            self._send_json(400, {'ok': False, 'error': f'invalid_json: {exc}'})
            return

        missing, comments, project_id, video_id, target_video_id = validate_payload(payload)
        if missing:
            self._send_json(400, {'ok': False, 'error': f'missing_fields: {", ".join(missing)}'})
            return

        if RELAY_MODE == 'mock':
            results, posted_count = build_mock_results(comments)
            response_payload = {
                'ok': posted_count == len(results),
                'requestId': request_id,
                'mode': 'mock',
                'projectId': project_id,
                'videoId': video_id,
                'targetVideoId': target_video_id,
                'postedCount': posted_count,
                'results': results,
                'receivedAt': now_iso(),
            }
            response_code = 200
        elif RELAY_MODE in {'dry_run', 'post'}:
            response_code, downstream_payload = run_downstream(payload, dry_run=(RELAY_MODE == 'dry_run'))
            response_payload = {
                'requestId': request_id,
                'projectId': project_id,
                'videoId': video_id,
                'targetVideoId': target_video_id,
                'receivedAt': now_iso(),
                **downstream_payload,
            }
        else:
            response_code = 500
            response_payload = {'ok': False, 'error': f'unsupported_mode: {RELAY_MODE}'}

        retry_queue_items = extract_retry_queue_items(payload, response_payload)
        retry_queue_file = persist_retry_queue(LOG_DIR, payload, response_payload, project_id, video_id, target_video_id)
        if retry_queue_file:
            response_payload['retryQueueFile'] = str(retry_queue_file)
            response_payload['retryQueueCount'] = len(retry_queue_items)

        log_file = persist_request_log(LOG_DIR, payload, response_payload, RELAY_MODE, project_id, request_id)
        response_payload['logFile'] = str(log_file)

        self._send_json(response_code, response_payload)


def main() -> None:
    httpd = HTTPServer((HOST, PORT), RelayHandler)
    print(f'Vimeo relay server ({RELAY_MODE}) listening on http://{HOST}:{PORT}')
    httpd.serve_forever()


if __name__ == '__main__':
    main()
