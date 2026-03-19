"""source_videos登録後にディレクションレポートを自動生成するモジュール

source_videosテーブルにレコードが追加された際に、以下を自動実行する:
1. e2e-pipeline（ディレクション生成）
2. HTMLレポート生成
3. GitHub Pagesデプロイ
4. DBのdirection_report_urlを更新

既にdirection_report_urlが設定済みのプロジェクトはスキップ（再生成防止）。
エラー時はログに記録し、サイレントに失敗する（ユーザー操作をブロックしない）。
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# DBパス（api_server.pyと同じ）
DB_PATH = Path.home() / "AI開発10" / ".data" / "video_director.db"


def _get_db() -> sqlite3.Connection:
    """DB接続を取得"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def should_generate_report(project_id: str) -> bool:
    """プロジェクトにレポート生成が必要かどうか判定する

    以下の条件を全て満たす場合にTrueを返す:
    - プロジェクトが存在する
    - direction_report_urlが未設定（NULLまたは空文字）
    """
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT id, direction_report_url FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        if not row:
            logger.warning("プロジェクトが見つかりません: %s", project_id)
            return False
        existing_url = row["direction_report_url"]
        if existing_url and existing_url.strip():
            logger.info(
                "レポート生成スキップ（既に生成済み）: project=%s, url=%s",
                project_id, existing_url,
            )
            return False
        return True
    finally:
        conn.close()


def generate_report_for_project(project_id: str) -> Optional[str]:
    """プロジェクトのディレクションレポートを生成し、公開URLを返す

    処理フロー:
    1. プロジェクト情報取得
    2. ディレクション生成（e2e-pipelineのStep 4相当）
    3. HTMLレポート生成
    4. GitHub Pagesデプロイ
    5. DBのdirection_report_urlを更新

    Returns:
        公開URL（成功時）またはNone（失敗時）
    """
    conn = _get_db()
    try:
        project_row = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if not project_row:
            logger.error("プロジェクトが見つかりません: %s", project_id)
            return None
        project_data = dict(project_row)
    finally:
        conn.close()

    guest_name = project_data.get("guest_name", "不明")
    logger.info("レポート自動生成開始: project=%s, guest=%s", project_id, guest_name)

    try:
        # --- Step 1: ディレクション生成 ---
        from ..integrations.ai_dev5_connector import VideoData, HighlightScene, PersonProfile
        from ..analyzer.guest_classifier import ClassificationResult
        from ..analyzer.income_evaluator import IncomeEvaluation
        from ..analyzer.direction_generator import generate_directions
        from ..analyzer.proper_noun_filter import detect_proper_nouns
        from ..analyzer.target_labeler import label_targets

        # knowledgeからハイライト復元
        highlights = []
        knowledge_json = project_data.get("knowledge")
        profiles_data = []
        if knowledge_json:
            try:
                knowledge = json.loads(knowledge_json) if isinstance(knowledge_json, str) else knowledge_json
                for h in knowledge.get("highlights", []):
                    highlights.append(HighlightScene(
                        timestamp=h.get("timestamp", "00:00"),
                        speaker=h.get("speaker", ""),
                        text=h.get("text", ""),
                        category=h.get("category", ""),
                    ))
                profiles_data = knowledge.get("profiles", [])
            except (json.JSONDecodeError, TypeError):
                pass

        video_data = VideoData(
            title=project_data.get("title", ""),
            speakers=guest_name,
            highlights=highlights,
        )

        # プロフィール情報の補完
        if profiles_data:
            p = profiles_data[0]
            video_data.profiles = [PersonProfile(
                name=p.get("name", guest_name),
                age=p.get("age", str(project_data.get("guest_age", "")) if project_data.get("guest_age") else ""),
                occupation=p.get("occupation", project_data.get("guest_occupation", "")),
                income=p.get("income", ""),
                side_business=p.get("side_business", ""),
            )]
        elif guest_name and guest_name != "不明":
            video_data.profiles = [PersonProfile(
                name=guest_name,
                age=str(project_data.get("guest_age", "")) if project_data.get("guest_age") else "",
                occupation=project_data.get("guest_occupation", ""),
                income="",
                side_business="",
            )]

        # ゲスト層分類（デフォルト。knowledgeに分類情報があれば後で上書きされる）
        classification = ClassificationResult(
            tier="c", tier_label="層c",
            reason="自動生成デフォルト分類", presentation_template="標準テンプレート",
            confidence="low",
        )
        income_eval = IncomeEvaluation(
            income_value=None, age_bracket="不明", threshold=0,
            emphasize=False, emphasis_reason="デフォルト", telop_suggestion="",
        )

        # 年収情報があれば強調ON
        if video_data.profiles and video_data.profiles[0].income:
            income_eval = IncomeEvaluation(
                income_value=None, age_bracket="不明", threshold=0,
                emphasize=True, emphasis_reason="年収情報あり", telop_suggestion="",
            )

        # 固有名詞フィルタ
        proper_nouns = detect_proper_nouns(video_data)

        # ターゲットラベリング
        target_result = label_targets(video_data)

        # FB学習ルール
        feedback_learner = None
        video_learner = None
        edit_learner_instance = None
        try:
            from ..tracker.feedback_learner import FeedbackLearner
            feedback_learner = FeedbackLearner()
        except Exception:
            pass
        try:
            from ..tracker.video_learner import VideoLearner
            video_learner = VideoLearner()
        except Exception:
            pass
        try:
            from ..tracker.edit_learner import EditLearner
            edit_learner_instance = EditLearner()
        except Exception:
            pass

        # ディレクション生成
        direction_timeline = generate_directions(
            video_data=video_data,
            classification=classification,
            income_eval=income_eval,
            feedback_learner=feedback_learner,
            video_learner=video_learner,
            edit_learner=edit_learner_instance,
        )

        logger.info(
            "ディレクション生成完了: project=%s, entries=%d",
            project_id, len(direction_timeline.entries),
        )

        # --- Step 2: YouTube素材生成（タイトル・概要欄・サムネ指示書） ---
        thumbnail_design = None
        title_proposals = None
        video_description = None
        try:
            from ..analyzer.title_generator import generate_title_proposals
            from ..analyzer.description_writer import generate_description
            from ..analyzer.thumbnail_designer import generate_thumbnail_design
            from ..knowledge.loader import KnowledgeLoader

            knowledge_ctx = KnowledgeLoader().load()
            thumbnail_design = generate_thumbnail_design(
                video_data, classification, income_eval, knowledge_ctx,
            )
            title_proposals = generate_title_proposals(
                video_data, classification, income_eval, knowledge_ctx,
            )
            video_description = generate_description(
                video_data, classification, income_eval, knowledge_ctx,
            )
        except Exception as e:
            logger.warning("YouTube素材生成スキップ: %s", e)

        # --- Step 3: HTMLレポート生成 ---
        from ..reporter.html_generator import generate_direction_html

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

        # --- Step 4: GitHub Pages公開 ---
        from ..reporter.publisher import publish_direction_page

        # 撮影日を取得
        shoot_date = project_data.get("shoot_date", "")
        if shoot_date:
            # "2025/11/23" → "20251123"
            date_str = shoot_date.replace("/", "").replace("-", "")[:8]
        else:
            date_str = datetime.now().strftime("%Y%m%d")

        url = publish_direction_page(
            html_content=html_content,
            guest_name=guest_name,
            tier=classification.tier,
            date_str=date_str,
        )

        logger.info("レポート公開成功: project=%s, url=%s", project_id, url)

        # --- Step 5: DBのdirection_report_urlを更新 ---
        conn = _get_db()
        try:
            conn.execute(
                "UPDATE projects SET direction_report_url = ?, updated_at = datetime('now') WHERE id = ?",
                (url, project_id),
            )
            conn.commit()
            logger.info("DB更新完了: project=%s, direction_report_url=%s", project_id, url)
        finally:
            conn.close()

        return url

    except Exception as e:
        logger.error(
            "レポート自動生成失敗: project=%s, error=%s",
            project_id, e,
            exc_info=True,
        )
        return None


def trigger_auto_report(project_id: str) -> None:
    """source_videos登録後に呼ばれるトリガー関数

    バックグラウンドスレッドでレポート生成を非同期実行する。
    既にレポートが生成済みの場合はスキップする。
    """
    if not should_generate_report(project_id):
        return

    def _run():
        try:
            result_url = generate_report_for_project(project_id)
            if result_url:
                logger.info(
                    "自動レポート生成完了: project=%s, url=%s",
                    project_id, result_url,
                )
            else:
                logger.warning(
                    "自動レポート生成: URLが返されませんでした: project=%s",
                    project_id,
                )
        except Exception as e:
            logger.error(
                "自動レポート生成で予期しないエラー: project=%s, error=%s",
                project_id, e,
                exc_info=True,
            )

    thread = threading.Thread(
        target=_run,
        name=f"auto-report-{project_id}",
        daemon=True,
    )
    thread.start()
    logger.info("自動レポート生成をバックグラウンドで開始: project=%s", project_id)


def trigger_auto_report_sync(project_id: str) -> Optional[str]:
    """同期版のトリガー関数（source_video_linker等の非API経由用）

    バックグラウンドスレッドではなく、呼び出し元スレッドで直接実行する。
    """
    if not should_generate_report(project_id):
        return None

    return generate_report_for_project(project_id)
