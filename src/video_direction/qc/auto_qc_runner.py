"""自動QCパイプラインランナー

タイミング3: 編集後自動QCの全ステップを統合実行する。
Step 1: Whisper音声文字起こし
Step 2: フレームキャプチャ
Step 3: テロップ有無フィルタリング + GPT-4oビジョン読み取り
Step 4A: 正解データ vs テロップの突合（テロップ正確性チェック）
Step 4B: マーケティング品質QC（QUALITY_JUDGMENT_GUIDE注入 + Opus定額内判定）

使い方:
    python -m src.video_direction.qc.auto_qc_runner --video /path/to/video.mp4
    python -m src.video_direction.qc.auto_qc_runner --video /path/to/video.mp4 --project-id PRJ001
    python -m src.video_direction.qc.auto_qc_runner --video /path/to/video.mp4 --skip-marketing-qc
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from .whisper_transcriber import transcribe_video, TranscriptResult
from .frame_extractor import extract_and_filter, ExtractedFrame
from .telop_reader import read_telops_batch, TelopReadResult
from .qc_comparator import run_qc_comparison, QCResult
from .marketing_qc import run_marketing_qc, MarketingQCResult

logger = logging.getLogger(__name__)

# デフォルト設定
DEFAULT_FRAME_INTERVAL = 2.0      # 2秒間隔
DEFAULT_SIMILARITY_THRESHOLD = 0.7
DEFAULT_TIME_WINDOW = 3.0         # 前後3秒
DEFAULT_MAX_FRAMES = 100          # 最大100フレーム
DEFAULT_BOTTOM_RATIO = 0.33       # 下部1/3
DEFAULT_MIN_EDGE_DENSITY = 0.02   # エッジ密度閾値

# QC結果のデフォルト保存先
QC_OUTPUT_DIR = Path.home() / "AI開発10" / "output" / "qc_results"


def run_auto_qc(
    video_path: str | Path,
    project_id: str = "",
    output_dir: Optional[str | Path] = None,
    frame_interval: float = DEFAULT_FRAME_INTERVAL,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    time_window: float = DEFAULT_TIME_WINDOW,
    max_frames: int = DEFAULT_MAX_FRAMES,
    cache_dir: Optional[str | Path] = None,
    cleanup_frames: bool = True,
    # Phase2: マーケQCオプション
    enable_marketing_qc: bool = True,
    direction_report: str = "",
    guest_profile: str = "",
    content_line: Optional[str] = None,
    marketing_qc_model: str = "opus",
) -> QCResult:
    """自動QCパイプラインのメイン実行

    Args:
        video_path: 動画ファイルパス
        project_id: プロジェクトID
        output_dir: QC結果の保存先
        frame_interval: フレームキャプチャ間隔（秒）
        similarity_threshold: テキスト類似度の閾値
        time_window: タイムスタンプ突合の許容範囲（秒）
        max_frames: GPT-4oに投げる最大フレーム数
        cache_dir: Whisper結果のキャッシュディレクトリ
        cleanup_frames: 処理後にフレーム画像を削除するか
        enable_marketing_qc: マーケQC（Phase2）を実行するか
        direction_report: ディレクションレポート（マーケQC用）
        guest_profile: ゲストプロファイル（マーケQC用）
        content_line: コンテンツライン（None=自動判定）
        marketing_qc_model: マーケQCに使うモデル（デフォルト: opus）

    Returns:
        QC結果（マーケQC結果が含まれる場合あり）
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"動画ファイルが見つかりません: {video_path}")

    if output_dir is None:
        output_dir = QC_OUTPUT_DIR
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if cache_dir is None:
        cache_dir = output_dir / "cache"

    # フレーム出力用一時ディレクトリ
    frames_dir = Path(tempfile.mkdtemp(prefix="qc_frames_"))

    try:
        # === Step 1: Whisper音声文字起こし ===
        logger.info("=== Step 1: Whisper音声文字起こし ===")
        transcript = transcribe_video(
            video_path,
            language="ja",
            cache_dir=cache_dir,
        )
        logger.info(f"文字起こし完了: {len(transcript.segments)}セグメント")

        # === Step 2 & 3: フレーム抽出 + テロップフィルタリング ===
        logger.info("=== Step 2: フレーム抽出 ===")
        all_frames, telop_frames = extract_and_filter(
            video_path,
            output_dir=frames_dir,
            interval_sec=frame_interval,
            bottom_ratio=DEFAULT_BOTTOM_RATIO,
            min_edge_density=DEFAULT_MIN_EDGE_DENSITY,
        )
        logger.info(f"フレーム抽出完了: 全{len(all_frames)}枚, テロップあり{len(telop_frames)}枚")

        # === Step 3: GPT-4oビジョンでテロップ読み取り ===
        logger.info("=== Step 3: GPT-4oビジョンテロップ読み取り ===")
        telop_result = read_telops_batch(
            telop_frames,
            model="gpt-4o",
            max_frames=max_frames,
        )
        logger.info(
            f"テロップ読み取り完了: {telop_result.telop_frames}/{telop_result.total_frames}枚にテロップ検出"
        )

        # === Step 4A: テロップ正確性チェック ===
        logger.info("=== Step 4A: テロップ正確性チェック ===")
        qc_result = run_qc_comparison(
            transcript=transcript,
            telop_result=telop_result,
            project_id=project_id,
            video_path=str(video_path),
            similarity_threshold=similarity_threshold,
            time_window_sec=time_window,
        )

        # === Step 4B: マーケティング品質QC（Phase2） ===
        marketing_qc_result = None
        if enable_marketing_qc:
            logger.info("=== Step 4B: マーケティング品質QC ===")
            try:
                # テロップテキストをタイムスタンプ付きリストに変換
                telop_text_list = []
                for reading in telop_result.readings:
                    if reading.has_telop and reading.telop_texts:
                        for text in reading.telop_texts:
                            telop_text_list.append(f"[{reading.timecode}] {text}")

                marketing_qc_result = run_marketing_qc(
                    telop_texts=telop_text_list,
                    transcript_text=transcript.full_text,
                    project_id=project_id,
                    direction_report=direction_report,
                    guest_profile=guest_profile,
                    content_line=content_line,
                    model=marketing_qc_model,
                )

                # マーケQC結果をQCResultに統合
                qc_result.marketing_qc = marketing_qc_result.to_dict()

                logger.info(
                    f"マーケQC完了: {marketing_qc_result.error_count}エラー, "
                    f"{marketing_qc_result.warning_count}警告"
                )
            except Exception as e:
                logger.error(f"マーケQC実行エラー（テロップQCには影響なし）: {e}")
                # マーケQCが失敗してもテロップQC結果は返す
                qc_result.marketing_qc = {
                    "status": "error",
                    "error_message": str(e),
                }

        # 結果をJSONファイルに保存
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = output_dir / f"qc_{project_id or 'unknown'}_{timestamp}.json"
        result_data = {
            "qc_result": qc_result.to_dict(),
            "transcript_summary": {
                "segments": len(transcript.segments),
                "duration": transcript.duration,
                "full_text_length": len(transcript.full_text),
            },
            "frame_summary": {
                "total_frames": len(all_frames),
                "telop_frames_detected": len(telop_frames),
                "telop_frames_confirmed": telop_result.telop_frames,
            },
            "config": {
                "frame_interval": frame_interval,
                "similarity_threshold": similarity_threshold,
                "time_window": time_window,
                "max_frames": max_frames,
                "enable_marketing_qc": enable_marketing_qc,
                "marketing_qc_model": marketing_qc_model,
            },
            "executed_at": datetime.now().isoformat(),
        }
        result_file.write_text(
            json.dumps(result_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"QC結果保存: {result_file}")

        return qc_result

    finally:
        # フレーム画像の後片付け
        if cleanup_frames and frames_dir.exists():
            shutil.rmtree(frames_dir, ignore_errors=True)
            logger.info("フレーム画像を削除しました")


def main():
    """CLIエントリーポイント"""
    parser = argparse.ArgumentParser(
        description="タイミング3: テロップ誤字自動QCパイプライン"
    )
    parser.add_argument(
        "--video", "-v",
        required=True,
        help="動画ファイルパス",
    )
    parser.add_argument(
        "--project-id", "-p",
        default="",
        help="プロジェクトID",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="QC結果の保存先ディレクトリ",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_FRAME_INTERVAL,
        help=f"フレームキャプチャ間隔（秒）。デフォルト: {DEFAULT_FRAME_INTERVAL}",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_SIMILARITY_THRESHOLD,
        help=f"類似度閾値。デフォルト: {DEFAULT_SIMILARITY_THRESHOLD}",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=DEFAULT_MAX_FRAMES,
        help=f"GPT-4oに投げる最大フレーム数。デフォルト: {DEFAULT_MAX_FRAMES}",
    )
    parser.add_argument(
        "--skip-marketing-qc",
        action="store_true",
        help="マーケティング品質QC（Phase2）をスキップする",
    )
    parser.add_argument(
        "--direction-report",
        default="",
        help="ディレクションレポートファイルパス（マーケQC用）",
    )
    parser.add_argument(
        "--guest-profile",
        default="",
        help="ゲストプロファイルファイルパス（マーケQC用）",
    )
    parser.add_argument(
        "--content-line",
        choices=["career", "realestate"],
        default=None,
        help="コンテンツライン（未指定で自動判定）",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="詳細ログを表示",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # ファイル指定の場合は読み込み
    direction_report = ""
    if args.direction_report:
        dr_path = Path(args.direction_report)
        if dr_path.exists():
            direction_report = dr_path.read_text(encoding="utf-8")

    guest_profile = ""
    if args.guest_profile:
        gp_path = Path(args.guest_profile)
        if gp_path.exists():
            guest_profile = gp_path.read_text(encoding="utf-8")

    result = run_auto_qc(
        video_path=args.video,
        project_id=args.project_id,
        output_dir=args.output_dir,
        frame_interval=args.interval,
        similarity_threshold=args.threshold,
        max_frames=args.max_frames,
        enable_marketing_qc=not args.skip_marketing_qc,
        direction_report=direction_report,
        guest_profile=guest_profile,
        content_line=args.content_line,
    )

    # サマリー表示
    print("\n" + "=" * 60)
    print(f"テロップQC: {'PASSED' if result.status == 'passed' else 'FAILED'}")
    print(f"検査フレーム: {result.checked_frames}枚")
    print(f"エラー: {result.error_count}件, 警告: {result.warning_count}件")

    if result.marketing_qc:
        mq = result.marketing_qc
        mq_status = mq.get("status", "unknown")
        print(f"\nマーケQC: {'PASSED' if mq_status == 'passed' else mq_status.upper()}")
        print(f"マーケQCエラー: {mq.get('error_count', 0)}件, 警告: {mq.get('warning_count', 0)}件")
        if mq.get("highlight_assessment"):
            print(f"ハイライト評価: {mq['highlight_assessment']}")
        if mq.get("direction_assessment"):
            print(f"演出評価: {mq['direction_assessment']}")

    print(f"\n統合ステータス: {result.combined_status.upper()}")
    print("=" * 60)

    if result.issues:
        print("\n【テロップ誤字検出】")
        for issue in result.issues:
            icon = "!" if issue.severity == "error" else "?"
            print(f"  [{icon}] [{issue.timecode}] {issue.description}")
            print(f"     発言: {issue.spoken_text}")
            print(f"     テロップ: {issue.telop_text}")
            print()

    if result.marketing_qc and result.marketing_qc.get("issues"):
        print("\n【マーケティング品質指摘】")
        for issue in result.marketing_qc["issues"]:
            sev = issue.get("severity", "warning")
            icon = "!" if sev == "error" else ("?" if sev == "warning" else "i")
            print(f"  [{icon}] [{issue.get('category', 'general')}] {issue.get('description', '')}")
            if issue.get("suggestion"):
                print(f"     提案: {issue['suggestion']}")
            print()

    sys.exit(0 if result.combined_status == "passed" else 1)


if __name__ == "__main__":
    main()
