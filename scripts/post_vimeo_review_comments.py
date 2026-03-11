#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Post converted review comments to Vimeo API from a relay request JSON."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


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


def post_json(url: str, token: str, payload: dict) -> tuple[int, str]:
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
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, resp.read().decode('utf-8')


def save_output(path: str | None, payload: dict) -> None:
    if not path:
        return
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description='Post converted review comments to Vimeo API')
    parser.add_argument('json_path', help='Path to relay request JSON file')
    parser.add_argument('--dry-run', action='store_true', help='Print Vimeo request plan instead of posting')
    parser.add_argument('--output', help='Optional path to save the Vimeo result JSON')
    args = parser.parse_args()

    relay_request = load_payload(Path(args.json_path))
    body = relay_request.get('body') or {}
    target_video_id = relay_request.get('targetVideoId') or body.get('targetVideoId')
    comments = body.get('comments') or []
    if not target_video_id:
        raise ValueError('targetVideoId is required')

    endpoint = build_endpoint(target_video_id)
    plan = []
    for comment in comments:
        if not comment.get('feedbackId') or not comment.get('convertedText'):
            plan.append({'feedbackId': comment.get('feedbackId'), 'status': 'skipped', 'reason': 'missing fields'})
            continue
        payload = build_vimeo_payload(comment)
        plan.append({
            'feedbackId': comment['feedbackId'],
            'endpoint': endpoint,
            'payload': payload,
        })

    if args.dry_run:
        dry_payload = {'targetVideoId': target_video_id, 'requests': plan}
        save_output(args.output, dry_payload)
        print(json.dumps(dry_payload, ensure_ascii=False, indent=2))
        return 0

    token = os.getenv('VIMEO_ACCESS_TOKEN')
    if not token:
        raise ValueError('VIMEO_ACCESS_TOKEN is required unless --dry-run is used')

    results = []
    for item in plan:
        if item.get('status') == 'skipped':
            results.append(item)
            continue
        try:
            status, response_text = post_json(item['endpoint'], token, item['payload'])
            results.append({
                'feedbackId': item['feedbackId'],
                'status': 'posted' if 200 <= status < 300 else 'failed',
                'httpStatus': status,
                'response': response_text,
            })
        except urllib.error.HTTPError as exc:
            results.append({
                'feedbackId': item['feedbackId'],
                'status': 'failed',
                'httpStatus': exc.code,
                'response': exc.read().decode('utf-8', errors='replace'),
            })
        except urllib.error.URLError as exc:
            results.append({
                'feedbackId': item['feedbackId'],
                'status': 'failed',
                'response': f'{exc}',
            })

    result_payload = {'targetVideoId': target_video_id, 'results': results}
    save_output(args.output, result_payload)
    print(json.dumps(result_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
