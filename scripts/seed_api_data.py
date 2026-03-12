#!/usr/bin/env python3
"""既存プロジェクトデータをAPIサーバーに一括投入するスクリプト

video_transcriptsのマークダウンファイルをパースし、
APIサーバー（localhost:8210）にプロジェクトデータを投入する。

使い方:
    cd ~/AI開発10
    source venv/bin/activate
    python scripts/seed_api_data.py

前提:
    - APIサーバーが起動していること（uvicorn ... --port 8210）
    - venvがactivateされていること
"""

import json
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# プロジェクトルートをsys.pathに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.video_direction.integrations.ai_dev5_connector import (
    parse_markdown_file,
    list_video_markdown_files,
)

API_BASE = "http://localhost:8210"


def _parse_age(age_str: str) -> Optional[int]:
    """年齢文字列を数値に変換する（「28歳」→28、「30代前半」→32等）"""
    if not age_str:
        return None
    # 「28歳」「31歳」等の直接数値
    m = re.search(r"(\d{2})歳", age_str)
    if m:
        return int(m.group(1))
    # 「30代前半」「20代後半」等の範囲表現
    m = re.search(r"(\d)0代(前半|半ば|中盤|後半)?", age_str)
    if m:
        decade = int(m.group(1)) * 10
        qualifier = m.group(2) or ""
        if "前半" in qualifier:
            return decade + 2
        elif "半ば" in qualifier or "中盤" in qualifier:
            return decade + 5
        elif "後半" in qualifier:
            return decade + 8
        else:
            return decade + 5  # 「20代」のみ→25
    # 数値だけ
    m = re.search(r"(\d{2})", age_str)
    if m:
        return int(m.group(1))
    return None


def _api_request(method: str, path: str, data: dict = None) -> dict:
    """APIリクエストを送信する"""
    url = f"{API_BASE}{path}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method=method,
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 409:
            return {"status": "already_exists"}
        body = e.read().decode("utf-8") if e.fp else ""
        raise RuntimeError(f"API error {e.code}: {body}")


def seed_project(filepath: Path) -> bool:
    """1ファイルをパースしてAPIサーバーに投入する"""
    try:
        video_data = parse_markdown_file(filepath)
        if not video_data.profiles and not video_data.title:
            return False

        # ゲスト名
        if video_data.profiles:
            guest_name = video_data.profiles[0].name
        elif video_data.title:
            name_match = re.search(r"撮影_(.+?)(?:さん|：|$)", video_data.title)
            guest_name = (name_match.group(1) + "さん") if name_match else "不明"
        else:
            guest_name = "不明"

        # 撮影日
        date_match = re.search(r"(\d{8})撮影", filepath.name)
        date_str = date_match.group(1) if date_match else "20260101"

        # プロジェクトID
        safe_name = re.sub(r"[^\w]", "", guest_name)
        project_id = f"p-{date_str}-{safe_name}"

        # プロジェクトデータ
        project_data = {
            "id": project_id,
            "guest_name": guest_name,
            "title": video_data.title or f"{guest_name}さん対談",
            "status": "directed",
            "shoot_date": f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:8]}",
        }

        # ゲスト情報
        if video_data.profiles:
            profile = video_data.profiles[0]
            # 年齢を数値に変換（「28歳」→28、「30代前半」→32、「30代半ば」→35等）
            if profile.age:
                age_num = _parse_age(profile.age)
                if age_num:
                    project_data["guest_age"] = age_num
            project_data["guest_occupation"] = profile.occupation

        # ナレッジ情報
        if video_data.highlights:
            knowledge = {
                "highlights": [
                    {
                        "timestamp": h.timestamp,
                        "category": h.category,
                        "text": h.text[:100] if h.text else "",
                    }
                    for h in video_data.highlights[:10]
                ],
                "highlight_count": len(video_data.highlights),
            }
            project_data["knowledge"] = knowledge

        # API投入
        result = _api_request("POST", "/api/projects", project_data)
        status = result.get("status", "")

        if status == "already_exists":
            print(f"  ⏭️ スキップ（既存）: {guest_name} ({project_id})")
        else:
            print(f"  ✅ 投入完了: {guest_name} ({project_id})")

        return True

    except Exception as e:
        print(f"  ❌ 失敗: {filepath.name}: {e}")
        return False


def main():
    # APIサーバー稼働確認
    try:
        health = _api_request("GET", "/api/health")
        print(f"APIサーバー接続OK (既存プロジェクト: {health.get('projects', 0)}件)")
    except Exception as e:
        print(f"❌ APIサーバーに接続できません: {e}")
        print(f"   起動コマンド: cd ~/AI開発10 && source venv/bin/activate && uvicorn src.video_direction.integrations.api_server:app --host 0.0.0.0 --port 8210")
        sys.exit(1)

    # マークダウンファイル一覧
    files = list_video_markdown_files()
    print(f"\n📄 対象ファイル: {len(files)}件\n")

    success = 0
    failed = 0
    for filepath in files:
        if seed_project(filepath):
            success += 1
        else:
            failed += 1

    # 最終状態確認
    health = _api_request("GET", "/api/health")
    print(f"\n📊 結果: {success}件成功 / {failed}件スキップ")
    print(f"📊 DBプロジェクト数: {health.get('projects', 0)}件")


if __name__ == "__main__":
    main()
