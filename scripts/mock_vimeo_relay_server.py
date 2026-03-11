#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal mock relay server for AI開発10 Vimeo review flow."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HOST = os.getenv('VIMEO_RELAY_HOST', '127.0.0.1')
PORT = int(os.getenv('VIMEO_RELAY_PORT', '8787'))
TOKEN = os.getenv('VIMEO_RELAY_TOKEN', 'dev-relay-token')
LOG_DIR = Path(os.getenv('VIMEO_RELAY_LOG_DIR', Path.cwd() / 'runs' / 'relay_logs'))


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


class RelayHandler(BaseHTTPRequestHandler):
    server_version = 'AIDev10MockRelay/0.1'

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

        body = payload.get('body') or {}
        comments = body.get('comments') or []
        project_id = payload.get('projectId')
        video_id = payload.get('videoId')
        target_video_id = payload.get('targetVideoId') or body.get('targetVideoId')

        missing = []
        for field, value in [('projectId', project_id), ('videoId', video_id), ('targetVideoId', target_video_id)]:
            if not value:
                missing.append(field)
        if missing:
            self._send_json(400, {'ok': False, 'error': f'missing_fields: {", ".join(missing)}'})
            return

        results = []
        for item in comments:
            if not item.get('feedbackId') or item.get('timestampSeconds') is None or not item.get('convertedText'):
                results.append({
                    'feedbackId': item.get('feedbackId'),
                    'status': 'failed',
                    'error': 'invalid_comment_payload'
                })
                continue
            results.append({
                'feedbackId': item['feedbackId'],
                'status': 'posted',
                'vimeoCommentId': f"mock-{item['feedbackId']}",
                'timestampSeconds': item['timestampSeconds']
            })

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        (LOG_DIR / f'{stamp}-{project_id}.json').write_text(
            json.dumps({'receivedAt': now_iso(), 'payload': payload, 'results': results}, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

        posted_count = len([r for r in results if r['status'] == 'posted'])
        self._send_json(200, {
            'ok': posted_count == len(results),
            'projectId': project_id,
            'videoId': video_id,
            'targetVideoId': target_video_id,
            'postedCount': posted_count,
            'results': results,
            'receivedAt': now_iso(),
        })


def main() -> None:
    httpd = HTTPServer((HOST, PORT), RelayHandler)
    print(f'Mock Vimeo relay server listening on http://{HOST}:{PORT}')
    httpd.serve_forever()


if __name__ == '__main__':
    main()
