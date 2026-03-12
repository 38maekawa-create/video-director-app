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
        "SELECT * FROM feedbacks WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/projects/{project_id}/feedbacks")
def create_feedback(project_id: str, fb: FeedbackCreate):
    conn = _get_db()
    conn.execute(
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
    return {"status": "created", "project_id": project_id}


@app.get("/api/feedbacks")
def list_all_feedbacks():
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM feedbacks ORDER BY created_at DESC"
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
