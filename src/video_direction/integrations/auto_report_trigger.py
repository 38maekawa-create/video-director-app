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
import re
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

        # --- titleから年収情報を抽出 ---
        title = project_data.get("title", "")
        extracted_income = _extract_income_from_title(title)

        # --- categoryからvideo_typeにマッピング ---
        category = project_data.get("category", "")
        video_type = _category_to_video_type(category)

        # --- source_videosからdurationを取得 ---
        duration = _get_duration_from_source_videos(project_id)

        video_data = VideoData(
            title=title,
            speakers=guest_name,
            highlights=highlights,
            video_type=video_type,
            duration=duration,
        )

        # プロフィール情報の補完
        if profiles_data:
            p = profiles_data[0]
            # knowledgeのprofilesにincomeがなければtitleから抽出した年収を使用
            profile_income = p.get("income", "") or extracted_income
            video_data.profiles = [PersonProfile(
                name=p.get("name", guest_name),
                age=p.get("age", str(project_data.get("guest_age", "")) if project_data.get("guest_age") else ""),
                occupation=p.get("occupation", project_data.get("guest_occupation", "")),
                income=profile_income,
                side_business=p.get("side_business", ""),
            )]
        elif guest_name and guest_name != "不明":
            video_data.profiles = [PersonProfile(
                name=guest_name,
                age=str(project_data.get("guest_age", "")) if project_data.get("guest_age") else "",
                occupation=project_data.get("guest_occupation", ""),
                income=extracted_income,
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

        # 固有名詞フィルタ（ゲスト名を渡して他ゲストの企業名混入を防止）
        _guest_name_for_filter = video_data.profiles[0].name if video_data.profiles else None
        proper_nouns = detect_proper_nouns(video_data, guest_name=_guest_name_for_filter)

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
                proper_nouns=proper_nouns,
            )
            video_description = generate_description(
                video_data, classification, income_eval, knowledge_ctx,
                proper_nouns=proper_nouns,
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
        # publish後にDB更新が失敗した場合、URLは公開済みだがDBに反映されない状態になる。
        # この場合は例外を外側のexceptに伝播させ、呼び出し元がエラーとして認識できるようにする。
        conn = _get_db()
        try:
            conn.execute(
                "UPDATE projects SET direction_report_url = ?, updated_at = datetime('now') WHERE id = ?",
                (url, project_id),
            )
            conn.commit()
            logger.info("DB更新完了: project=%s, direction_report_url=%s", project_id, url)
        except Exception as db_err:
            # DB更新失敗: URLは公開済みのためログに残してエラーを伝播
            logger.error(
                "DB更新失敗（URLは公開済み）: project=%s, url=%s, error=%s",
                project_id, url, db_err,
            )
            raise
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


# スレッド重複実行防止用
_running_projects: set = set()
_running_lock = threading.Lock()


def trigger_auto_report(project_id: str) -> None:
    """source_videos登録後に呼ばれるトリガー関数

    バックグラウンドスレッドでレポート生成を非同期実行する。
    既にレポートが生成済みの場合はスキップする。
    同一project_idのスレッドが既に実行中の場合もスキップする。
    """
    if not should_generate_report(project_id):
        return

    with _running_lock:
        if project_id in _running_projects:
            logger.info(
                "自動レポート生成: 既に実行中のためスキップ: project=%s",
                project_id,
            )
            return
        _running_projects.add(project_id)

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
        finally:
            with _running_lock:
                _running_projects.discard(project_id)

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


def _extract_income_from_title(title: str) -> str:
    """titleフィールドから年収情報を抽出する

    例:
    - "年収870万" → "年収870万"
    - "年収1000万円台" → "年収1000万円台"
    - "年収約900万円" → "年収約900万円"
    - "年収3,600-4,800万円規模" → "年収3,600-4,800万円規模"
    - "年収1000万円台...独立後3000万円" のような複合パターンも抽出
    """
    if not title:
        return ""

    # 年収パターンを正規表現で抽出（「年収」の後に続く金額表現を取得）
    patterns = [
        # 「年収」で始まるパターン（最も一般的）
        r'年収[約]?[\d,]+[\-〜～]?[\d,]*万円?[台規模超]*',
    ]

    matches = []
    for pattern in patterns:
        found = re.findall(pattern, title)
        matches.extend(found)

    if matches:
        return "、".join(matches)

    # 「年収」が含まれるが上記パターンにマッチしない場合、周辺テキストを抽出
    if "年収" in title:
        # 「年収」を含む部分を広めに抽出
        match = re.search(r'年収[^\s、。：:）)]*', title)
        if match:
            return match.group(0)

    return ""


def _category_to_video_type(category: str) -> str:
    """DBのcategoryカラムをvideo_typeに変換する"""
    mapping = {
        "teko_member": "TEKOメンバー対談",
        "teko_realestate": "TEKO不動産",
    }
    return mapping.get(category, category or "")


def _get_duration_from_source_videos(project_id: str) -> str:
    """source_videosテーブルからdurationを取得する"""
    try:
        conn = _get_db()
        try:
            row = conn.execute(
                "SELECT duration FROM source_videos WHERE project_id = ? AND duration IS NOT NULL AND duration != '' LIMIT 1",
                (project_id,),
            ).fetchone()
            if row and row["duration"]:
                return row["duration"]
        finally:
            conn.close()
    except Exception:
        pass
    return ""
