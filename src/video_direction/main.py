from __future__ import annotations
"""メインエントリーポイント — 全体オーケストレーション

使い方:
    # 単一ファイル処理
    python -m src.video_direction.main /path/to/markdown_file.md

    # 全件一括処理
    python -m src.video_direction.main --all

    # ドライラン（HTMLファイル生成のみ、push/スプシ書き込みなし）
    python -m src.video_direction.main --all --dry-run
"""

import argparse
import re
import sys
import os
from pathlib import Path
from datetime import datetime

# APIキー読み込み
def _load_api_keys():
    """~/.config/maekawa/api-keys.env からAPIキーを環境変数に設定"""
    env_file = Path.home() / ".config" / "maekawa" / "api-keys.env"
    if env_file.exists():
        for line in env_file.read_text().split("\n"):
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                if key.strip() not in os.environ:
                    os.environ[key.strip()] = value.strip()

_load_api_keys()

from .integrations.ai_dev5_connector import parse_markdown_file, list_video_markdown_files, VideoData
from .integrations.member_master import MemberMaster
from .analyzer.guest_classifier import classify_guest
from .analyzer.income_evaluator import evaluate_income
from .analyzer.proper_noun_filter import detect_proper_nouns
from .analyzer.target_labeler import label_targets
from .analyzer.direction_generator import generate_directions
from .analyzer.thumbnail_designer import generate_thumbnail_design
from .analyzer.title_generator import generate_title_proposals
from .analyzer.description_writer import generate_description
from .knowledge.loader import KnowledgeLoader
from .reporter.html_generator import generate_direction_html
from .reporter.publisher import publish_direction_page
from .integrations.sheets_manager import SheetsManager


def process_single_file(
    filepath: str | Path,
    member_master: MemberMaster = None,
    dry_run: bool = False,
    output_dir: str | Path = None,
) -> dict:
    """単一ファイルの処理パイプライン

    Returns:
        dict: {"guest_name": str, "tier": str, "html_path": str, "url": str, "success": bool}
    """
    filepath = Path(filepath)
    print(f"📄 処理中: {filepath.name}")

    # Step 1: パース
    video_data = parse_markdown_file(filepath)
    if not video_data.profiles and not video_data.title:
        print(f"  ⚠️ スキップ: パース結果が空（{filepath.name}）")
        return {"success": False, "reason": "パース結果が空"}

    # メンバーマスターとの連動
    if member_master and video_data.profiles:
        guest_name = video_data.profiles[0].name
        member_info = member_master.find_member(guest_name)
        if member_info:
            print(f"  ✅ メンバーマスター連動: {member_info.canonical_name}")

    # Step 2: 分析
    classification = classify_guest(video_data)
    print(f"  🏷️ ゲスト分類: {classification.tier_label} ({classification.reason})")

    income_eval = evaluate_income(video_data)
    emphasis_text = "強調ON" if income_eval.emphasize else "強調OFF"
    print(f"  💰 年収演出: {emphasis_text} ({income_eval.emphasis_reason})")

    proper_nouns = detect_proper_nouns(video_data)
    hide_count = sum(1 for n in proper_nouns if n.action == "hide")
    print(f"  🔇 固有名詞: {len(proper_nouns)}件検出（うち{hide_count}件伏せ）")

    target_result = label_targets(video_data)
    print(f"  🎯 ターゲット: 1層{target_result.balance.tier1_count}件 / 2層{target_result.balance.tier2_count}件 / 両層{target_result.balance.both_count}件")

    direction_timeline = generate_directions(video_data, classification, income_eval)
    print(f"  🎬 演出指示: {len(direction_timeline.entries)}件")

    # Step 2.5: YouTube素材生成（サムネ指示書・タイトル案・概要欄）
    thumbnail_design = None
    title_proposals = None
    video_description = None
    try:
        knowledge_ctx = KnowledgeLoader().load()
        thumbnail_design = generate_thumbnail_design(video_data, classification, income_eval, knowledge_ctx)
        print(f"  🖼️ サムネ指示書: Z型4ゾーン設計完了")

        title_proposals = generate_title_proposals(video_data, classification, income_eval, knowledge_ctx)
        title_count = len(title_proposals.candidates) if title_proposals.candidates else 0
        print(f"  📝 タイトル案: {title_count}件")

        video_description = generate_description(video_data, classification, income_eval, knowledge_ctx)
        desc_len = len(video_description.full_text) if video_description.full_text else 0
        print(f"  📋 概要欄: {desc_len}文字")
    except Exception as e:
        print(f"  ⚠️ YouTube素材生成スキップ: {e}")

    # Step 3: HTMLレポート生成
    html_content = generate_direction_html(
        video_data=video_data,
        classification=classification,
        income_eval=income_eval,
        proper_nouns=proper_nouns,
        target_result=target_result,
        direction_timeline=direction_timeline,
        thumbnail_design=thumbnail_design,
        title_proposals=title_proposals,
        video_description=video_description,
    )

    # ゲスト名の取得（プロファイル → タイトルからフォールバック）
    if video_data.profiles:
        guest_name = video_data.profiles[0].name
    elif video_data.title:
        name_match = re.search(r"撮影_(.+?)(?:さん|：|$)", video_data.title)
        guest_name = (name_match.group(1) + "さん") if name_match else "不明"
    else:
        guest_name = "不明"

    # 撮影日を取得（ファイル名から）
    date_match = re.search(r"(\d{8})撮影", filepath.name)
    date_str = date_match.group(1) if date_match else datetime.now().strftime("%Y%m%d")

    if dry_run:
        # ドライラン: ローカルに保存のみ
        if output_dir:
            out_path = Path(output_dir)
        else:
            out_path = Path(__file__).parent.parent.parent.parent / "output" / "reports"
        out_path.mkdir(parents=True, exist_ok=True)

        from .reporter.publisher import _safe_filename
        filename = f"{date_str}_{_safe_filename(guest_name)}_direction.html"
        html_path = out_path / filename
        html_path.write_text(html_content, encoding="utf-8")
        print(f"  📝 HTML保存: {html_path}")

        return {
            "guest_name": guest_name,
            "tier": classification.tier,
            "html_path": str(html_path),
            "url": "",
            "success": True,
        }

    # Step 4: GitHub Pages公開
    try:
        url = publish_direction_page(
            html_content=html_content,
            guest_name=guest_name,
            tier=classification.tier,
            date_str=date_str,
        )
        print(f"  🌐 公開URL: {url}")
    except Exception as e:
        print(f"  ❌ 公開失敗: {e}")
        url = ""

    # Step 5: スプシ連携
    if url:
        try:
            sheets = SheetsManager()
            written = sheets.write_direction_url(guest_name, url)
            if written:
                print(f"  📊 スプシ書き込み完了")
            else:
                print(f"  ⚠️ スプシ: ゲスト「{guest_name}」の行が見つかりません")
        except Exception as e:
            print(f"  ❌ スプシ書き込み失敗: {e}")

    return {
        "guest_name": guest_name,
        "tier": classification.tier,
        "html_path": "",
        "url": url,
        "success": True,
    }


def process_all(dry_run: bool = False, output_dir: str | Path = None) -> list[dict]:
    """全件一括処理"""
    member_master = MemberMaster()
    files = list_video_markdown_files()
    print(f"🎬 処理対象: {len(files)}件")

    results = []
    for filepath in files:
        try:
            result = process_single_file(
                filepath,
                member_master=member_master,
                dry_run=dry_run,
                output_dir=output_dir,
            )
            results.append(result)
        except Exception as e:
            print(f"  ❌ エラー: {filepath.name}: {e}")
            results.append({"success": False, "reason": str(e)})

    # サマリー
    success = sum(1 for r in results if r.get("success"))
    failed = len(results) - success
    print(f"\n📊 処理結果: {success}件成功 / {failed}件失敗 / 全{len(results)}件")

    return results


def main():
    parser = argparse.ArgumentParser(description="ディレクションレポート自動生成")
    parser.add_argument("filepath", nargs="?", help="処理対象のMarkdownファイルパス")
    parser.add_argument("--all", action="store_true", help="全件一括処理")
    parser.add_argument("--dry-run", action="store_true", help="ドライラン（ローカル保存のみ）")
    parser.add_argument("--output-dir", help="出力先ディレクトリ")
    args = parser.parse_args()

    if args.all:
        process_all(dry_run=args.dry_run, output_dir=args.output_dir)
    elif args.filepath:
        member_master = MemberMaster()
        process_single_file(
            args.filepath,
            member_master=member_master,
            dry_run=args.dry_run,
            output_dir=args.output_dir,
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
