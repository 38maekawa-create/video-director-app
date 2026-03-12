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

import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

# プロジェクトルートをsys.pathに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.video_direction.integrations.ai_dev5_connector import (
    parse_markdown_file,
    list_video_markdown_files,
)
from src.video_direction.analyzer.guest_classifier import classify_guest
from src.video_direction.analyzer.income_evaluator import evaluate_income
from src.video_direction.analyzer.thumbnail_designer import generate_thumbnail_design
from src.video_direction.analyzer.title_generator import generate_title_proposals
from src.video_direction.analyzer.description_writer import generate_description
from src.video_direction.knowledge.loader import KnowledgeLoader
from src.video_direction.main import _sync_to_api_server

API_BASE = "http://localhost:8210"


def _api_request(method: str, path: str, data: dict = None) -> dict:
    """APIリクエストを送信する"""
    try:
        req = urllib.request.Request(f"{API_BASE}{path}", method=method)
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"API error: {e}")


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

        classification = classify_guest(video_data)
        income_eval = evaluate_income(video_data)

        thumbnail_design = None
        title_proposals = None
        video_description = None
        try:
            knowledge_ctx = KnowledgeLoader().load()
            thumbnail_design = generate_thumbnail_design(video_data, classification, income_eval, knowledge_ctx)
            title_proposals = generate_title_proposals(video_data, classification, income_eval, knowledge_ctx)
            video_description = generate_description(video_data, classification, income_eval, knowledge_ctx)
        except Exception as e:
            print(f"  ⚠️ YouTube素材生成スキップ: {e}")

        date_match = re.search(r"(\d{8})撮影", filepath.name)
        date_str = date_match.group(1) if date_match else "20260101"
        _sync_to_api_server(
            video_data=video_data,
            guest_name=guest_name,
            classification=classification,
            income_eval=income_eval,
            date_str=date_str,
            direction_url="",
            thumbnail_design=thumbnail_design,
            title_proposals=title_proposals,
            video_description=video_description,
        )
        print(f"  ✅ 投入完了: {guest_name}")

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
