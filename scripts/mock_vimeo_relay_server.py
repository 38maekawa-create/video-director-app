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
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HOST = os.getenv('VIMEO_RELAY_HOST', '127.0.0.1')
PORT = int(os.getenv('VIMEO_RELAY_PORT', '8787'))
TOKEN = os.getenv('VIMEO_RELAY_TOKEN', 'dev-relay-token')
LOG_DIR = Path(os.getenv('VIMEO_RELAY_LOG_DIR', Path.cwd() / 'runs' / 'relay_logs'))
RELAY_MODE = os.getenv('VIMEO_RELAY_MODE', 'dry_run').strip() or 'dry_run'
POST_SCRIPT = Path(__file__).with_name('post_vimeo_review_comments.py')


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


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

        auth = self.headers.get('Authorization', '')
        if auth != f'Bearer {TOKEN}':
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
                'projectId': project_id,
                'videoId': video_id,
                'targetVideoId': target_video_id,
                'receivedAt': now_iso(),
                **downstream_payload,
            }
        else:
            response_code = 500
            response_payload = {'ok': False, 'error': f'unsupported_mode: {RELAY_MODE}'}

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        (LOG_DIR / f'{stamp}-{project_id}.json').write_text(
            json.dumps({'receivedAt': now_iso(), 'mode': RELAY_MODE, 'payload': payload, 'response': response_payload}, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

        self._send_json(response_code, response_payload)


def main() -> None:
    httpd = HTTPServer((HOST, PORT), RelayHandler)
    print(f'Vimeo relay server ({RELAY_MODE}) listening on http://{HOST}:{PORT}')
    httpd.serve_forever()


if __name__ == '__main__':
    main()
