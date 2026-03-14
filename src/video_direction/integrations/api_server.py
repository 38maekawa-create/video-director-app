"""映像ディレクションエージェント — REST APIサーバー

Mac常駐のFastAPIサーバー。iOSアプリとPythonパイプラインの橋渡し。
SQLiteをデータストアとして使用し、外部サービス不要で動作する。

起動: source venv/bin/activate && uvicorn src.video_direction.integrations.api_server:app --host 0.0.0.0 --port 8210
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- データベース ---

DB_PATH = Path.home() / "AI開発10" / ".data" / "video_director.db"


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """テーブル作成（冪等）"""
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            guest_name TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'directed',
            shoot_date TEXT,
            guest_age INTEGER,
            guest_occupation TEXT,
            quality_score INTEGER,
            has_unsent_feedback INTEGER DEFAULT 0,
            unreviewed_count INTEGER DEFAULT 0,
            direction_report_url TEXT,
            source_video TEXT,       -- JSON
            edited_video TEXT,       -- JSON
            feedback_summary TEXT,   -- JSON
            knowledge TEXT,          -- JSON
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS youtube_assets (
            project_id TEXT PRIMARY KEY REFERENCES projects(id),
            thumbnail_design TEXT,   -- JSON
            title_proposals TEXT,    -- JSON
            description_original TEXT,
            description_edited TEXT,
            description_finalized_at TEXT,
            description_finalized_by TEXT,
            selected_title_index INTEGER,
            edited_title TEXT,
            last_edited_by TEXT,
            generated_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS feedbacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT REFERENCES projects(id),
            timestamp_mark TEXT,
            raw_voice_text TEXT,
            converted_text TEXT,
            category TEXT,
            priority TEXT DEFAULT 'medium',
            created_by TEXT,
            is_sent INTEGER DEFAULT 0,
            editor_status TEXT DEFAULT '未対応',
            learning_effect TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


# --- Pydantic モデル ---

class ProjectCreate(BaseModel):
    id: str
    guest_name: str
    title: str
    status: str = "directed"
    shoot_date: Optional[str] = None
    guest_age: Optional[int] = None
    guest_occupation: Optional[str] = None
    quality_score: Optional[int] = None
    direction_report_url: Optional[str] = None
    source_video: Optional[dict] = None
    edited_video: Optional[dict] = None
    feedback_summary: Optional[dict] = None
    knowledge: Optional[dict] = None


class YouTubeAssetsUpsert(BaseModel):
    thumbnail_design: Optional[dict] = None
    title_proposals: Optional[dict] = None
    description_original: Optional[str] = None
    description_edited: Optional[str] = None
    selected_title_index: Optional[int] = None
    edited_title: Optional[str] = None
    last_edited_by: Optional[str] = None


class DescriptionUpdate(BaseModel):
    edited: str
    by: str


class TitleSelect(BaseModel):
    index: int
    edited_title: Optional[str] = None
    by: str


class FeedbackCreate(BaseModel):
    timestamp_mark: Optional[str] = None
    raw_voice_text: Optional[str] = None
    converted_text: Optional[str] = None
    category: Optional[str] = None
    priority: str = "medium"
    created_by: Optional[str] = None


# --- FastAPI アプリ ---

app = FastAPI(title="Video Director Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


# --- プロジェクト ---

@app.get("/api/projects")
def list_projects():
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM projects ORDER BY shoot_date DESC"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        # SQLiteはBooleanを0/1で返すためPython boolに変換
        for bool_field in ("has_unsent_feedback",):
            if bool_field in d:
                d[bool_field] = bool(d[bool_field])
        for json_field in ("source_video", "edited_video", "feedback_summary", "knowledge"):
            if d.get(json_field):
                d[json_field] = json.loads(d[json_field])
        result.append(d)
    return result


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    conn = _get_db()
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Project not found")
    d = dict(row)
    for bool_field in ("has_unsent_feedback",):
        if bool_field in d:
            d[bool_field] = bool(d[bool_field])
    for json_field in ("source_video", "edited_video", "feedback_summary", "knowledge"):
        if d.get(json_field):
            d[json_field] = json.loads(d[json_field])
    return d


@app.post("/api/projects")
def create_project(project: ProjectCreate):
    conn = _get_db()
    try:
        conn.execute(
            """INSERT INTO projects (id, guest_name, title, status, shoot_date,
               guest_age, guest_occupation, quality_score, direction_report_url,
               source_video, edited_video, feedback_summary, knowledge)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project.id, project.guest_name, project.title, project.status,
                project.shoot_date, project.guest_age, project.guest_occupation,
                project.quality_score, project.direction_report_url,
                json.dumps(project.source_video) if project.source_video else None,
                json.dumps(project.edited_video) if project.edited_video else None,
                json.dumps(project.feedback_summary) if project.feedback_summary else None,
                json.dumps(project.knowledge) if project.knowledge else None,
            )
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(409, "Project already exists")
    finally:
        conn.close()
    return {"status": "created", "id": project.id}


@app.put("/api/projects/{project_id}")
def update_project(project_id: str, project: ProjectCreate):
    conn = _get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE projects SET guest_name=?, title=?, status=?, shoot_date=?,
           guest_age=?, guest_occupation=?, quality_score=?, direction_report_url=?,
           source_video=?, edited_video=?, feedback_summary=?, knowledge=?, updated_at=?
           WHERE id=?""",
        (
            project.guest_name, project.title, project.status, project.shoot_date,
            project.guest_age, project.guest_occupation, project.quality_score,
            project.direction_report_url,
            json.dumps(project.source_video) if project.source_video else None,
            json.dumps(project.edited_video) if project.edited_video else None,
            json.dumps(project.feedback_summary) if project.feedback_summary else None,
            json.dumps(project.knowledge) if project.knowledge else None,
            now, project_id,
        )
    )
    conn.commit()
    conn.close()
    return {"status": "updated", "id": project_id}


# --- YouTube素材 ---

@app.get("/api/projects/{project_id}/youtube-assets")
def get_youtube_assets(project_id: str):
    conn = _get_db()
    row = conn.execute(
        "SELECT * FROM youtube_assets WHERE project_id = ?", (project_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "YouTube assets not found")
    d = dict(row)
    for json_field in ("thumbnail_design", "title_proposals"):
        if d.get(json_field):
            d[json_field] = json.loads(d[json_field])
    return d


@app.put("/api/projects/{project_id}/youtube-assets")
def upsert_youtube_assets(project_id: str, assets: YouTubeAssetsUpsert):
    conn = _get_db()
    now = datetime.now(timezone.utc).isoformat()
    # UPSERT
    conn.execute(
        """INSERT INTO youtube_assets (project_id, thumbnail_design, title_proposals,
           description_original, description_edited, selected_title_index,
           edited_title, last_edited_by, generated_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(project_id) DO UPDATE SET
             thumbnail_design=excluded.thumbnail_design,
             title_proposals=excluded.title_proposals,
             description_original=excluded.description_original,
             description_edited=excluded.description_edited,
             selected_title_index=excluded.selected_title_index,
             edited_title=excluded.edited_title,
             last_edited_by=excluded.last_edited_by,
             updated_at=excluded.updated_at""",
        (
            project_id,
            json.dumps(assets.thumbnail_design) if assets.thumbnail_design else None,
            json.dumps(assets.title_proposals) if assets.title_proposals else None,
            assets.description_original,
            assets.description_edited,
            assets.selected_title_index,
            assets.edited_title,
            assets.last_edited_by,
            now, now,
        )
    )
    conn.commit()
    conn.close()
    return {"status": "upserted", "project_id": project_id}


@app.patch("/api/projects/{project_id}/youtube-assets/description")
def update_description(project_id: str, body: DescriptionUpdate):
    conn = _get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE youtube_assets SET description_edited=?, description_finalized_by=?,
           description_finalized_at=?, last_edited_by=?, updated_at=?
           WHERE project_id=?""",
        (body.edited, body.by, now, body.by, now, project_id)
    )
    conn.commit()
    conn.close()
    return {"status": "updated"}


@app.patch("/api/projects/{project_id}/youtube-assets/title")
def select_title(project_id: str, body: TitleSelect):
    conn = _get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE youtube_assets SET selected_title_index=?, edited_title=?,
           last_edited_by=?, updated_at=?
           WHERE project_id=?""",
        (body.index, body.edited_title, body.by, now, project_id)
    )
    conn.commit()
    conn.close()
    return {"status": "updated"}


# --- フィードバック ---

@app.get("/api/projects/{project_id}/feedbacks")
def list_feedbacks(project_id: str):
    conn = _get_db()
    rows = conn.execute(
        "SELECT f.*, p.guest_name, p.title as project_title "
        "FROM feedbacks f "
        "LEFT JOIN projects p ON f.project_id = p.id "
        "WHERE f.project_id = ? ORDER BY f.created_at DESC",
        (project_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/projects/{project_id}/feedbacks")
def create_feedback(project_id: str, fb: FeedbackCreate):
    conn = _get_db()
    cursor = conn.execute(
        """INSERT INTO feedbacks (project_id, timestamp_mark, raw_voice_text,
           converted_text, category, priority, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (project_id, fb.timestamp_mark, fb.raw_voice_text,
         fb.converted_text, fb.category, fb.priority, fb.created_by)
    )
    # プロジェクトの未レビュー数を更新
    conn.execute(
        "UPDATE projects SET unreviewed_count = unreviewed_count + 1, "
        "has_unsent_feedback = 1, updated_at = datetime('now') WHERE id = ?",
        (project_id,)
    )
    conn.commit()
    conn.close()

    # FB学習ループ: 保存されたFBを学習データとして取り込む
    learned = False
    learned_patterns = 0
    content = (fb.converted_text or fb.raw_voice_text or "").strip()
    if content:
        learner = _get_feedback_learner()
        if learner:
            try:
                feedback_id = f"fb_{cursor.lastrowid}" if cursor.lastrowid else f"fb_{project_id}"
                patterns = learner.ingest_feedback(
                    feedback_id=feedback_id,
                    content=content,
                    category=fb.category,
                    created_by=fb.created_by,
                )
                learned = True
                learned_patterns = len(patterns)
            except Exception:
                # 学習はベストエフォート。FB保存自体は成功扱いにする
                pass

    return {
        "status": "created",
        "project_id": project_id,
        "learning_applied": learned,
        "learned_patterns": learned_patterns,
    }


@app.get("/api/feedbacks")
def list_all_feedbacks(limit: int = 100):
    """全フィードバック一覧（プロジェクト名・ゲスト名付き）"""
    conn = _get_db()
    rows = conn.execute(
        "SELECT f.*, p.guest_name, p.title as project_title "
        "FROM feedbacks f "
        "LEFT JOIN projects p ON f.project_id = p.id "
        "ORDER BY f.created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- 同期チェック（ポーリング用） ---

@app.get("/api/projects/{project_id}/sync-check")
def sync_check(project_id: str):
    """クライアントがポーリングで最終更新時刻を確認するためのエンドポイント"""
    conn = _get_db()
    row = conn.execute(
        "SELECT updated_at FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    assets_row = conn.execute(
        "SELECT updated_at, last_edited_by FROM youtube_assets WHERE project_id = ?",
        (project_id,)
    ).fetchone()
    fb_count = conn.execute(
        "SELECT COUNT(*) FROM feedbacks WHERE project_id = ?", (project_id,)
    ).fetchone()[0]
    conn.close()
    return {
        "project_updated_at": row["updated_at"] if row else None,
        "assets_updated_at": assets_row["updated_at"] if assets_row else None,
        "assets_last_edited_by": assets_row["last_edited_by"] if assets_row else None,
        "feedback_count": fb_count,
    }


# --- 品質ダッシュボード ---

@app.get("/api/dashboard/summary")
def dashboard_summary():
    """品質ダッシュボードのサマリーデータ"""
    conn = _get_db()
    total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    with_assets = conn.execute("SELECT COUNT(*) FROM youtube_assets").fetchone()[0]
    avg_score = conn.execute(
        "SELECT AVG(quality_score) FROM projects WHERE quality_score IS NOT NULL"
    ).fetchone()[0]
    status_counts = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM projects GROUP BY status"
    ).fetchall()
    recent_fbs = conn.execute(
        "SELECT f.*, p.guest_name FROM feedbacks f "
        "JOIN projects p ON f.project_id = p.id "
        "ORDER BY f.created_at DESC LIMIT 10"
    ).fetchall()
    unsent_count = conn.execute(
        "SELECT COUNT(*) FROM projects WHERE has_unsent_feedback = 1"
    ).fetchone()[0]
    conn.close()
    return {
        "total_projects": total,
        "projects_with_assets": with_assets,
        "average_quality_score": round(avg_score, 1) if avg_score else None,
        "status_breakdown": {r["status"]: r["cnt"] for r in status_counts},
        "recent_feedbacks": [dict(r) for r in recent_fbs],
        "unsent_feedback_count": unsent_count,
    }


@app.get("/api/dashboard/quality-trend")
def quality_trend():
    """品質スコアの推移データ"""
    conn = _get_db()
    rows = conn.execute(
        "SELECT guest_name, shoot_date, quality_score FROM projects "
        "WHERE quality_score IS NOT NULL ORDER BY shoot_date ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- 編集者管理 (NEW-8) ---

def _get_editor_manager():
    """EditorManagerのシングルトン取得"""
    try:
        from src.video_direction.integrations.editor_manager import EditorManager
        return EditorManager()
    except ImportError:
        return None


class EditorCreate(BaseModel):
    name: str
    contact_info: str = ""
    contract_type: str = "freelance"
    specialties: list = []
    capacity: int = 3
    notes: str = ""


class EditorUpdate(BaseModel):
    name: Optional[str] = None
    contact_info: Optional[str] = None
    status: Optional[str] = None
    contract_type: Optional[str] = None
    specialties: Optional[list] = None
    capacity: Optional[int] = None
    notes: Optional[str] = None


@app.get("/api/editors")
def list_editors(status: Optional[str] = None):
    mgr = _get_editor_manager()
    if not mgr:
        return []
    editors = mgr.list_editors(status=status)
    from dataclasses import asdict
    return [asdict(e) for e in editors]


@app.get("/api/editors/{editor_id}")
def get_editor(editor_id: str):
    mgr = _get_editor_manager()
    if not mgr:
        raise HTTPException(404, "Editor manager not available")
    editor = mgr.get_editor(editor_id)
    if not editor:
        raise HTTPException(404, "Editor not found")
    from dataclasses import asdict
    return asdict(editor)


@app.post("/api/editors")
def create_editor(body: EditorCreate):
    mgr = _get_editor_manager()
    if not mgr:
        raise HTTPException(500, "Editor manager not available")
    editor = mgr.add_editor(
        name=body.name, contact_info=body.contact_info,
        contract_type=body.contract_type, capacity=body.capacity,
        notes=body.notes,
    )
    from dataclasses import asdict
    return asdict(editor)


@app.put("/api/editors/{editor_id}")
def update_editor(editor_id: str, body: EditorUpdate):
    mgr = _get_editor_manager()
    if not mgr:
        raise HTTPException(500, "Editor manager not available")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    editor = mgr.update_editor(editor_id, **updates)
    if not editor:
        raise HTTPException(404, "Editor not found")
    from dataclasses import asdict
    return asdict(editor)


@app.get("/api/editors/{editor_id}/handover")
def editor_handover(editor_id: str):
    """F-3: 編集者引き継ぎパッケージ"""
    mgr = _get_editor_manager()
    if not mgr:
        raise HTTPException(500, "Editor manager not available")
    package = mgr.generate_handover_package(editor_id)
    if not package:
        raise HTTPException(404, "Editor not found")
    return package


# --- 映像トラッキング (NEW-4/5) ---

def _get_video_tracker():
    try:
        from src.video_direction.tracker.video_tracker import VideoTracker
        return VideoTracker()
    except ImportError:
        return None


def _get_video_analyzer():
    try:
        from src.video_direction.tracker.video_analyzer import VideoAnalyzer
        return VideoAnalyzer()
    except ImportError:
        return None


class TrackingVideoAdd(BaseModel):
    url: str
    tags: list = []


@app.get("/api/tracking/videos")
def list_tracking_videos(status: Optional[str] = None):
    tracker = _get_video_tracker()
    if not tracker:
        return []
    from dataclasses import asdict
    return [asdict(v) for v in tracker.list_videos(status=status)]


@app.get("/api/tracking/videos/{video_id}")
def get_tracking_video(video_id: str):
    tracker = _get_video_tracker()
    if not tracker:
        raise HTTPException(404, "Tracker not available")
    video = tracker.get_video(video_id)
    if not video:
        raise HTTPException(404, "Tracked video not found")
    from dataclasses import asdict
    return asdict(video)


@app.post("/api/tracking/videos")
def add_tracking_video(body: TrackingVideoAdd):
    tracker = _get_video_tracker()
    if not tracker:
        raise HTTPException(500, "Tracker not available")
    video = tracker.add_video(url=body.url, tags=body.tags)
    from dataclasses import asdict
    return asdict(video)


@app.post("/api/tracking/videos/{video_id}/analyze")
def analyze_tracking_video(video_id: str):
    """トラッキング映像を分析"""
    tracker = _get_video_tracker()
    analyzer = _get_video_analyzer()
    if not tracker or not analyzer:
        raise HTTPException(500, "Tracker/Analyzer not available")
    video = tracker.get_video(video_id)
    if not video:
        raise HTTPException(404, "Tracked video not found")
    # 分析実行
    result = analyzer.analyze(video_url=video.url)
    from dataclasses import asdict
    result_dict = asdict(result)
    tracker.update_analysis(video_id, result_dict, "completed")
    return result_dict


@app.delete("/api/tracking/videos/{video_id}")
def remove_tracking_video(video_id: str):
    tracker = _get_video_tracker()
    if not tracker:
        raise HTTPException(500, "Tracker not available")
    if tracker.remove_video(video_id):
        return {"status": "removed"}
    raise HTTPException(404, "Tracked video not found")


# --- 映像学習インサイト (NEW-6/7) ---

def _get_feedback_learner():
    try:
        from src.video_direction.tracker.feedback_learner import FeedbackLearner
        return FeedbackLearner()
    except ImportError:
        return None


def _get_video_learner():
    try:
        from src.video_direction.tracker.video_learner import VideoLearner
        return VideoLearner()
    except ImportError:
        return None


@app.get("/api/tracking/insights")
def list_tracking_insights():
    """学習済みインサイト一覧（映像+FB統合）"""
    insights = []
    vl = _get_video_learner()
    if vl:
        for p in vl.get_patterns(min_confidence=0.2):
            from dataclasses import asdict
            insights.append(asdict(p))
    return insights


@app.get("/api/learning/feedback-patterns")
def list_feedback_patterns(category: Optional[str] = None):
    """FB学習パターン一覧"""
    fl = _get_feedback_learner()
    if not fl:
        return []
    from dataclasses import asdict
    return [asdict(p) for p in fl.get_patterns(category=category)]


@app.get("/api/learning/summary")
def learning_summary():
    """学習状況サマリー"""
    result = {"feedback_learning": {}, "video_learning": {}}
    fl = _get_feedback_learner()
    if fl:
        result["feedback_learning"] = fl.get_insights()
    vl = _get_video_learner()
    if vl:
        result["video_learning"] = vl.get_summary()
    return result


# --- 巡回監査 (J-3) ---

def _get_audit_runner():
    try:
        from src.video_direction.integrations.audit_runner import AuditRunner
        return AuditRunner()
    except ImportError:
        return None


@app.get("/api/audit/latest")
def get_latest_audit():
    runner = _get_audit_runner()
    if not runner:
        return {"error": "Audit runner not available"}
    report = runner.get_latest_report()
    if not report:
        return {"error": "No audit reports yet"}
    from dataclasses import asdict
    return asdict(report)


@app.post("/api/audit/run")
def run_audit():
    """手動で監査を実行"""
    runner = _get_audit_runner()
    if not runner:
        raise HTTPException(500, "Audit runner not available")
    report = runner.run_audit()
    from dataclasses import asdict
    return asdict(report)


@app.get("/api/audit/history")
def audit_history(limit: int = 10):
    runner = _get_audit_runner()
    if not runner:
        return []
    from dataclasses import asdict
    return [asdict(r) for r in runner.get_report_history(limit=limit)]


# --- 通知設定 (J-4) ---

def _get_notifier():
    try:
        from src.video_direction.integrations.notifier import Notifier
        return Notifier()
    except ImportError:
        return None


class NotificationConfigUpdate(BaseModel):
    telegram_enabled: Optional[bool] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    line_enabled: Optional[bool] = None
    line_channel_token: Optional[str] = None
    line_user_id: Optional[str] = None
    notify_on_report: Optional[bool] = None
    notify_on_quality_warning: Optional[bool] = None
    notify_on_feedback: Optional[bool] = None


@app.get("/api/notifications/config")
def get_notification_config():
    notifier = _get_notifier()
    if not notifier:
        return {"error": "Notifier not available"}
    return notifier.get_config()


@app.put("/api/notifications/config")
def update_notification_config(body: NotificationConfigUpdate):
    notifier = _get_notifier()
    if not notifier:
        raise HTTPException(500, "Notifier not available")
    from src.video_direction.integrations.notifier import NotificationConfig
    config = notifier.config
    for key, value in body.model_dump().items():
        if value is not None:
            setattr(config, key, value)
    notifier.save_config(config)
    return notifier.get_config()


@app.post("/api/notifications/test")
def test_notification():
    """テスト通知を送信"""
    notifier = _get_notifier()
    if not notifier:
        raise HTTPException(500, "Notifier not available")
    return notifier.notify("🔔 テスト通知 — Video Director Agent が正常に接続されています", "general")


# --- PDCA品質改善ループ (J-5) ---

def _get_pdca_loop():
    try:
        from src.video_direction.integrations.pdca_loop import PDCALoop
        return PDCALoop()
    except ImportError:
        return None


@app.get("/api/pdca/states")
def list_pdca_states(phase: Optional[str] = None):
    loop = _get_pdca_loop()
    if not loop:
        return []
    from dataclasses import asdict
    return [asdict(s) for s in loop.list_states(phase=phase)]


@app.get("/api/pdca/states/{project_id}")
def get_pdca_state(project_id: str):
    loop = _get_pdca_loop()
    if not loop:
        raise HTTPException(500, "PDCA loop not available")
    state = loop.get_state(project_id)
    if not state:
        raise HTTPException(404, "PDCA state not found")
    from dataclasses import asdict
    return asdict(state)


@app.get("/api/pdca/summary")
def pdca_summary():
    loop = _get_pdca_loop()
    if not loop:
        return {}
    return loop.get_summary()


# --- 分散処理 (J-6) ---

def _get_distributed_processor():
    try:
        from src.video_direction.integrations.distributed_processor import DistributedProcessor
        return DistributedProcessor()
    except ImportError:
        return None


@app.get("/api/distributed/macs")
def list_remote_macs():
    proc = _get_distributed_processor()
    if not proc:
        return []
    from dataclasses import asdict
    return [asdict(m) for m in proc.list_macs()]


@app.post("/api/distributed/macs/check")
def check_all_remote_macs():
    proc = _get_distributed_processor()
    if not proc:
        raise HTTPException(500, "Distributed processor not available")
    return proc.check_all_macs()


# --- フィードバック変換 (音声→プロ指示) ---

class FeedbackConvertRequest(BaseModel):
    raw_text: str
    project_id: str


@app.post("/api/feedback/convert")
def convert_feedback(body: FeedbackConvertRequest):
    """音声テキストをプロのディレクション指示に変換"""
    # Claude APIで変換（APIキーがない場合は簡易変換）
    raw = body.raw_text
    try:
        import anthropic
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f"""以下の音声フィードバックを、映像編集者向けのプロフェッショナルなディレクション指示に変換してください。

音声テキスト:
{raw}

以下のJSON形式で出力:
{{
  "converted_text": "変換後のプロの指示テキスト",
  "structured_items": [
    {{
      "id": "1",
      "timestamp": "該当タイムスタンプ（推定）",
      "element": "対象要素（テロップ/カット/BGM/カメラ等）",
      "instruction": "具体的な指示",
      "priority": "high/medium/low"
    }}
  ]
}}"""
            }]
        )
        import re
        text = response.content[0].text
        # JSONブロックを抽出
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            result = json.loads(json_match.group())
            return result
    except (ImportError, Exception):
        pass

    # フォールバック: 簡易変換
    return {
        "converted_text": f"【ディレクション指示】\n{raw}\n\n※ 上記の音声フィードバックを確認し、該当箇所を修正してください。",
        "structured_items": [{
            "id": "1",
            "timestamp": "00:00",
            "element": "全般",
            "instruction": raw[:200],
            "priority": "medium",
        }],
    }


# --- ヘルスチェック ---

@app.get("/api/health")
def health():
    conn = _get_db()
    project_count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    assets_count = conn.execute("SELECT COUNT(*) FROM youtube_assets").fetchone()[0]
    feedback_count = conn.execute("SELECT COUNT(*) FROM feedbacks").fetchone()[0]
    conn.close()
    return {
        "status": "ok",
        "db_path": str(DB_PATH),
        "projects": project_count,
        "youtube_assets": assets_count,
        "feedbacks": feedback_count,
    }


# --- Webアプリ静的ファイル配信 ---
# PCブラウザから http://localhost:8210/ でアクセス可能にする

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# ルートの index.html を返す
@app.get("/")
def serve_index():
    index_path = Path.home() / "AI開発10" / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path), media_type="text/html")
    return {"error": "index.html not found"}

# webapp/ ディレクトリの静的ファイルを配信
WEBAPP_DIR = Path.home() / "AI開発10" / "webapp"
if WEBAPP_DIR.exists():
    app.mount("/webapp", StaticFiles(directory=str(WEBAPP_DIR)), name="webapp")

# ルートレベルの静的ファイル（app.js, styles.css, data.js等）
ROOT_DIR = Path.home() / "AI開発10"
for ext in ["js", "css"]:
    pass  # 個別ルートで対応

@app.get("/{filename:path}")
def serve_root_static(filename: str):
    """APIパスでないリクエストを静的ファイルとして配信"""
    if filename.startswith("api/"):
        raise HTTPException(status_code=404)
    file_path = Path.home() / "AI開発10" / filename
    if file_path.exists() and file_path.is_file():
        suffix = file_path.suffix
        media_types = {
            ".js": "application/javascript",
            ".css": "text/css",
            ".html": "text/html",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".svg": "image/svg+xml",
        }
        return FileResponse(str(file_path), media_type=media_types.get(suffix, "application/octet-stream"))
    raise HTTPException(status_code=404, detail=f"File not found: {filename}")
