#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Send a relay request JSON to the Mac-side Vimeo relay adapter."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def load_payload(path: Path) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('relay request must be a JSON object')
    return data


def resolve_endpoint(payload: dict) -> str:
    endpoint = os.getenv('VIMEO_RELAY_ENDPOINT') or payload.get('endpoint')
    if not endpoint:
        raise ValueError('endpoint is required in payload or VIMEO_RELAY_ENDPOINT')
    return endpoint


def build_headers(payload: dict) -> dict:
    headers = {'Content-Type': 'application/json'}
    auth_mode = payload.get('authMode') or 'relay_token'
    if auth_mode == 'relay_token':
        token = os.getenv('VIMEO_RELAY_TOKEN')
        if not token:
            raise ValueError('VIMEO_RELAY_TOKEN is required for relay_token auth mode')
        headers['Authorization'] = f'Bearer {token}'
    return headers


def post_payload(endpoint: str, payload: dict, headers: dict) -> tuple[int, str]:
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(endpoint, data=body, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, resp.read().decode('utf-8')


def save_output(path: str | None, content: str) -> None:
    if not path:
        return
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description='Send Vimeo relay request JSON to relay adapter')
    parser.add_argument('json_path', help='Path to relay request JSON file')
    parser.add_argument('--dry-run', action='store_true', help='Print request instead of sending')
    parser.add_argument('--output', help='Optional path to save the relay response JSON/text')
    args = parser.parse_args()

    payload = load_payload(Path(args.json_path))
    endpoint = resolve_endpoint(payload)
    headers = build_headers(payload)

    if args.dry_run:
        content = json.dumps({'endpoint': endpoint, 'headers': headers, 'payload': payload}, ensure_ascii=False, indent=2)
        save_output(args.output, content)
        print(content)
        return 0

    try:
        status, response_text = post_payload(endpoint, payload, headers)
    except urllib.error.HTTPError as exc:
        error_text = exc.read().decode('utf-8', errors='replace')
        save_output(args.output, error_text)
        sys.stderr.write(error_text)
        sys.stderr.write('\n')
        return exc.code or 1
    except urllib.error.URLError as exc:
        error_text = f'relay request failed: {exc}\n'
        save_output(args.output, error_text)
        sys.stderr.write(error_text)
        return 1

    save_output(args.output, response_text)
    print(response_text)
    return 0 if 200 <= status < 300 else 1


if __name__ == '__main__':
    raise SystemExit(main())
