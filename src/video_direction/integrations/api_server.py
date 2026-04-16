"""映像ディレクションエージェント — REST APIサーバー

Mac常駐のFastAPIサーバー。iOSアプリとPythonパイプラインの橋渡し。
SQLiteをデータストアとして使用し、外部サービス不要で動作する。

起動: source venv/bin/activate && uvicorn src.video_direction.integrations.api_server:app --host 0.0.0.0 --port 8210
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from .edit_direction_routes import router as edit_direction_router
from .edit_assets_routes import router as edit_assets_router
from ..tracker.edit_learner import EditLearner

# --- データベース ---

DB_PATH = Path.home() / "AI開発10" / ".data" / "video_director.db"


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
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
            category TEXT,           -- プロジェクトカテゴリ: teko_member / teko_realestate / NULL
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

        CREATE TABLE IF NOT EXISTS source_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL REFERENCES projects(id),
            youtube_url TEXT NOT NULL,
            video_id TEXT NOT NULL,
            title TEXT,
            duration TEXT,
            quality_status TEXT DEFAULT 'pending',
            source TEXT DEFAULT 'manual',
            knowledge_file TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS fb_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL REFERENCES projects(id),
            comment_uri TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(project_id, comment_uri)
        );
    """)
    conn.commit()

    # categoryカラムのマイグレーション（既存DBへの追加対応）
    columns = [row[1] for row in conn.execute("PRAGMA table_info(projects)").fetchall()]
    if "category" not in columns:
        conn.execute("ALTER TABLE projects ADD COLUMN category TEXT")
        conn.commit()

    # feedback_targetカラムのマイグレーション（AI生成物へのFB種別管理）
    fb_columns = [row[1] for row in conn.execute("PRAGMA table_info(feedbacks)").fetchall()]
    if "feedback_target" not in fb_columns:
        conn.execute("ALTER TABLE feedbacks ADD COLUMN feedback_target TEXT DEFAULT 'direction'")
        conn.commit()

    # 承認フロー用カラムのマイグレーション（FB変換結果の事前承認制）
    fb_columns = [row[1] for row in conn.execute("PRAGMA table_info(feedbacks)").fetchall()]
    if "approval_status" not in fb_columns:
        conn.execute("ALTER TABLE feedbacks ADD COLUMN approval_status TEXT DEFAULT 'pending'")
        conn.commit()
    if "approved_at" not in fb_columns:
        conn.execute("ALTER TABLE feedbacks ADD COLUMN approved_at TEXT")
        conn.commit()
    if "modified_text" not in fb_columns:
        conn.execute("ALTER TABLE feedbacks ADD COLUMN modified_text TEXT")
        conn.commit()
    if "approved_by" not in fb_columns:
        conn.execute("ALTER TABLE feedbacks ADD COLUMN approved_by TEXT")
        conn.commit()

    conn.close()


# --- ナレッジページURL マッチング ---

KNOWLEDGE_PAGES_DIR = Path.home() / "video-knowledge-pages"
KNOWLEDGE_PAGES_BASE_URL = "https://38maekawa-create.github.io/video-knowledge-pages/"


def _normalize_name(name: str) -> str:
    """ゲスト名を正規化して比較可能にする（敬称除去・小文字化・全角半角統一）"""
    name = unicodedata.normalize("NFKC", name).lower().strip()
    # 敬称除去
    for suffix in ("さん", "氏", "先生", "様"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name


def find_knowledge_page_url(guest_name: str, shoot_date: Optional[str] = None) -> Optional[str]:
    """プロジェクトのゲスト名(+撮影日)からナレッジページHTMLのURLを返す。

    マッチング戦略:
    1. ファイル名に撮影日とゲスト名の両方が含まれる → 最優先マッチ
    2. ファイル名にゲスト名が含まれる → 日付の新しいものを優先
    """
    if not KNOWLEDGE_PAGES_DIR.exists():
        return None

    normalized_guest = _normalize_name(guest_name)
    if not normalized_guest:
        return None

    html_files = sorted(KNOWLEDGE_PAGES_DIR.glob("*.html"), reverse=True)

    # 撮影日を正規化（YYYY-MM-DD → YYYYMMDD）
    shoot_date_compact = None
    if shoot_date:
        shoot_date_compact = shoot_date.replace("-", "")

    best_match = None
    best_with_date = None

    for f in html_files:
        fname_lower = f.name.lower()
        fname_normalized = unicodedata.normalize("NFKC", fname_lower)

        # ゲスト名がファイル名に含まれるか確認
        if normalized_guest not in fname_normalized:
            continue

        # 撮影日がファイル名に含まれるか確認
        if shoot_date_compact and shoot_date_compact in fname_normalized:
            best_with_date = f.name
            break  # 撮影日+ゲスト名の完全マッチは最優先

        if best_match is None:
            best_match = f.name

    matched = best_with_date or best_match
    if matched:
        return KNOWLEDGE_PAGES_BASE_URL + matched
    return None


def _extract_video_urls(d: dict) -> dict:
    """edited_video / source_video からURLを抽出し、edited_video_url / source_video_url を追加する。
    iOS側の decodeNestedURL が primary key（editedVideoURL / sourceVideoURL）で直接マッチできるようにする。"""
    for video_field in ("edited_video", "source_video"):
        url_key = f"{video_field}_url"
        if url_key in d and d[url_key]:
            continue  # 既にある場合はスキップ
        raw = d.get(video_field)
        if not raw:
            continue
        # raw が既にdict（json.loadsされた後）の場合
        if isinstance(raw, dict):
            for k in ("url", "vimeo_url", "video_url", "link"):
                if raw.get(k):
                    d[url_key] = raw[k]
                    break
        elif isinstance(raw, str):
            # JSON文字列の場合
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    for k in ("url", "vimeo_url", "video_url", "link"):
                        if parsed.get(k):
                            d[url_key] = parsed[k]
                            break
                elif isinstance(parsed, str):
                    d[url_key] = parsed
            except (json.JSONDecodeError, TypeError):
                # プレーンURL文字列の場合
                if "vimeo.com" in raw or "http" in raw:
                    d[url_key] = raw
    return d


def _enrich_project_with_knowledge_url(d: dict) -> dict:
    """プロジェクト辞書にknowledge_page_urlフィールドを追加する"""
    guest_name = d.get("guest_name", "")
    shoot_date = d.get("shoot_date", "")
    d["knowledge_page_url"] = find_knowledge_page_url(guest_name, shoot_date)
    return d


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
    category: Optional[str] = None


class CategoryUpdate(BaseModel):
    """カテゴリ更新リクエスト"""
    category: Optional[str] = None  # teko_member / teko_realestate / null(未分類)


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


class SourceVideoCreate(BaseModel):
    """素材動画の手動登録リクエスト"""
    youtube_url: str
    title: Optional[str] = None
    duration: Optional[str] = None
    quality_status: str = "pending"  # good_audio / pending / poor_audio


class FeedbackCreate(BaseModel):
    timestamp_mark: Optional[str] = None
    raw_voice_text: Optional[str] = None
    converted_text: Optional[str] = None
    category: Optional[str] = None
    priority: str = "medium"
    created_by: Optional[str] = None
    feedback_target: str = "direction"  # "direction" / "title" / "description"


# --- FastAPI アプリ ---

app = FastAPI(title="Video Director Agent API", version="1.0.0")

# --- CORS設定 ---
_DEFAULT_ORIGINS = [
    "http://localhost:8210",
    "http://127.0.0.1:8210",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
_env_origins = os.getenv("API_ALLOW_ORIGINS")
_allowed_origins = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    if _env_origins
    else _DEFAULT_ORIGINS
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(edit_direction_router)
app.include_router(edit_assets_router)


# --- 共通エラーハンドラ ---

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTPExceptionを統一フォーマットで返す"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail or "Unknown error",
                "retryable": exc.status_code >= 500,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """未処理例外をキャッチし、詳細をログに残しつつ一般メッセージを返す"""
    logger.exception("未処理例外: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "retryable": True,
            }
        },
    )


@app.on_event("startup")
def startup():
    init_db()
    repair_known_shoot_dates()


def repair_known_shoot_dates():
    """既知の誤投入データを起動時に補正する。"""
    conn = _get_db()
    # 初期シードデータ（開発用）: 2026/02/28 大阪撮影のゲスト名ハードコード
    conn.execute(
        """UPDATE projects
           SET shoot_date = ?, updated_at = ?
           WHERE shoot_date = ?
             AND (title LIKE ? OR guest_name IN (?, ?, ?, ?, ?, ?, ?, ?))""",
        (
            "2026/02/28",
            datetime.now(timezone.utc).isoformat(),
            "2026/01/01",
            "%2月28日 大阪%",
            # 初期シードデータ（開発用）: 2026/02/28 大阪撮影の参加ゲスト
            "コテさん",
            "kosさん",
            "メンイチさん",
            "さといも・トーマスさん",
            "ハオさん",
            "けーさん",
            "さくらさん",
            "ゆりかさん",
        ),
    )
    conn.commit()
    conn.close()


# --- プロジェクト ---

@app.get("/api/projects")
def list_projects(category: Optional[str] = None):
    """プロジェクト一覧を取得する。categoryパラメータでフィルタ可能。"""
    conn = _get_db()
    if category:
        if category == "uncategorized":
            rows = conn.execute(
                "SELECT * FROM projects WHERE category IS NULL ORDER BY shoot_date DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM projects WHERE category = ? ORDER BY shoot_date DESC",
                (category,),
            ).fetchall()
    else:
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
        for json_field in ("feedback_summary", "knowledge"):
            if d.get(json_field):
                try:
                    d[json_field] = json.loads(d[json_field])
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"JSON decode failed for field {json_field}: {e}")
                    d[json_field] = None
        # edited_video / source_video からURLを抽出してトップレベルに追加
        # iOS側の decodeNestedURL が primary key で直接マッチできるようにする
        _extract_video_urls(d)
        _enrich_project_with_knowledge_url(d)
        result.append(d)
    return result


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    conn = _get_db()
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Project not found")
    d = dict(row)
    conn.close()
    for bool_field in ("has_unsent_feedback",):
        if bool_field in d:
            d[bool_field] = bool(d[bool_field])
    for json_field in ("source_video", "edited_video", "feedback_summary", "knowledge"):
        if d.get(json_field):
            try:
                d[json_field] = json.loads(d[json_field])
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"JSON decode failed for field {json_field}: {e}")
                d[json_field] = None
    _extract_video_urls(d)
    _enrich_project_with_knowledge_url(d)
    return d


@app.post("/api/projects")
def create_project(project: ProjectCreate):
    conn = _get_db()
    try:
        conn.execute(
            """INSERT INTO projects (id, guest_name, title, status, shoot_date,
               guest_age, guest_occupation, quality_score, direction_report_url,
               source_video, edited_video, feedback_summary, knowledge, category)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project.id, project.guest_name, project.title, project.status,
                project.shoot_date, project.guest_age, project.guest_occupation,
                project.quality_score, project.direction_report_url,
                json.dumps(project.source_video) if project.source_video else None,
                json.dumps(project.edited_video) if project.edited_video else None,
                json.dumps(project.feedback_summary) if project.feedback_summary else None,
                json.dumps(project.knowledge) if project.knowledge else None,
                project.category,
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
    try:
        cur = conn.execute(
            """UPDATE projects SET guest_name=?, title=?, status=?, shoot_date=?,
               guest_age=?, guest_occupation=?, quality_score=?, direction_report_url=?,
               source_video=?, edited_video=?, feedback_summary=?, knowledge=?, category=?, updated_at=?
               WHERE id=?""",
            (
                project.guest_name, project.title, project.status, project.shoot_date,
                project.guest_age, project.guest_occupation, project.quality_score,
                project.direction_report_url,
                json.dumps(project.source_video) if project.source_video else None,
                json.dumps(project.edited_video) if project.edited_video else None,
                json.dumps(project.feedback_summary) if project.feedback_summary else None,
                json.dumps(project.knowledge) if project.knowledge else None,
                project.category, now, project_id,
            )
        )
        if cur.rowcount == 0:
            conn.rollback()
            raise HTTPException(404, "Project not found")
        conn.commit()
    finally:
        conn.close()
    return {"status": "updated", "id": project_id}


# --- カテゴリ ---

@app.put("/api/v1/projects/{project_id}/category")
def update_project_category(project_id: str, body: CategoryUpdate):
    """プロジェクトのカテゴリを変更する"""
    # カテゴリ値のバリデーション
    valid_categories = ("teko_member", "teko_realestate", None)
    if body.category not in valid_categories:
        raise HTTPException(400, f"Invalid category. Must be one of: {valid_categories}")

    conn = _get_db()
    row = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Project not found")

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE projects SET category = ?, updated_at = ? WHERE id = ?",
        (body.category, now, project_id),
    )
    conn.commit()
    conn.close()
    return {"status": "updated", "id": project_id, "category": body.category}


@app.get("/api/v1/projects/by-category/{category}")
def get_projects_by_category(category: str):
    """カテゴリ別プロジェクト一覧を取得する"""
    valid_categories = ("teko_member", "teko_realestate", "uncategorized")
    if category not in valid_categories:
        raise HTTPException(400, f"Invalid category. Must be one of: {valid_categories}")

    conn = _get_db()
    if category == "uncategorized":
        rows = conn.execute(
            "SELECT * FROM projects WHERE category IS NULL ORDER BY shoot_date DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM projects WHERE category = ? ORDER BY shoot_date DESC",
            (category,),
        ).fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        for bool_field in ("has_unsent_feedback",):
            if bool_field in d:
                d[bool_field] = bool(d[bool_field])
        for json_field in ("feedback_summary", "knowledge"):
            if d.get(json_field):
                try:
                    d[json_field] = json.loads(d[json_field])
                except (json.JSONDecodeError, TypeError):
                    pass
        _enrich_project_with_knowledge_url(d)
        result.append(d)
    return result


@app.post("/api/v1/sync-categories")
def sync_categories_from_sheet(force_reset_unmatched: bool = False):
    """スプレッドシートのA列「コンテンツ」を基準にDBのプロジェクトカテゴリを一括同期する。

    スプシのA列値に基づくカテゴリマッピング:
    - 「対談」→ teko_member
    - 「オフ会インタビュー」→ teko_member
    - 「不動産対談」→ teko_realestate
    - それ以外 → null（未分類）

    force_reset_unmatched=True: スプシに見つからないプロジェクトのcategoryをNULLへリセットする。
    デフォルトFalse: スプシ未一致でも既存のcategoryを保持する（データ消失防止）。
    """
    try:
        from .sheets_manager import SheetsManager, _match_guest_name
    except ImportError:
        raise HTTPException(500, "SheetsManager import failed. Check dependencies.")

    try:
        sm = SheetsManager()
        sheet_categories = sm.get_content_categories()
    except Exception as e:
        logger.exception("スプレッドシートからカテゴリ取得に失敗")
        raise HTTPException(502, "Failed to fetch categories from spreadsheet")

    conn = _get_db()
    projects = conn.execute("SELECT id, guest_name, title FROM projects").fetchall()

    updated = []
    skipped = []
    now = datetime.now(timezone.utc).isoformat()

    from .sheets_manager import _normalize_name, _resolve_via_member_master, _to_hiragana, _to_katakana, _get_member_default_category

    for proj in projects:
        proj_id = proj["id"]
        guest_name = proj["guest_name"] or ""
        title = proj["title"] or ""

        # テストゲスト除外: カテゴリ決定の前に最初にチェック
        if guest_name and "テスト" in guest_name:
            skipped.append({"id": proj_id, "guest_name": guest_name, "reason": "test_guest"})
            continue

        # 多段階マッチング: 精度の高い方法から順に試す
        matched_category = None
        db_norm = _normalize_name(guest_name)

        # ステージ1: 正規化後の完全一致
        for sheet_guest, cat in sheet_categories.items():
            sheet_norm = _normalize_name(sheet_guest)
            if db_norm and sheet_norm and db_norm == sheet_norm:
                matched_category = cat
                break

        # ステージ2: MEMBER_MASTER.jsonのcanonical_name解決
        if matched_category is None:
            db_canonical = _resolve_via_member_master(guest_name)
            if db_canonical:
                db_can_norm = _normalize_name(db_canonical)
                for sheet_guest, cat in sheet_categories.items():
                    sheet_canonical = _resolve_via_member_master(sheet_guest)
                    if sheet_canonical and db_can_norm == _normalize_name(sheet_canonical):
                        matched_category = cat
                        break

        # ステージ3: ひらがな/カタカナ変換後の完全一致
        if matched_category is None and db_norm:
            db_hira = _to_hiragana(db_norm)
            db_kata = _to_katakana(db_norm)
            for sheet_guest, cat in sheet_categories.items():
                sheet_norm = _normalize_name(sheet_guest)
                if not sheet_norm:
                    continue
                sheet_hira = _to_hiragana(sheet_norm)
                if db_hira == sheet_hira or db_kata == _to_katakana(sheet_norm):
                    matched_category = cat
                    break

        # ステージ4: _match_guest_nameによる柔軟マッチング（部分一致含む）
        # ただしカテゴリがNoneのエントリとの部分一致はスキップ（誤爆防止）
        if matched_category is None:
            for sheet_guest, cat in sheet_categories.items():
                if _match_guest_name(guest_name, sheet_guest):
                    # 部分一致でカテゴリNoneにマッチした場合は、それが本当の一致か検証
                    if cat is not None:
                        matched_category = cat
                        break
                    # カテゴリNoneでも正規化完全一致なら信頼できる
                    if _normalize_name(guest_name) == _normalize_name(sheet_guest):
                        matched_category = cat
                        break

        # ステージ5: MEMBER_MASTER.jsonのdefault_categoryフォールバック/オーバーライド
        # スプシからカテゴリが取れなかった場合のフォールバック、
        # または MEMBER_MASTER に明示的なdefault_categoryがある場合はオーバーライド
        if guest_name:
            member_category = _get_member_default_category(guest_name)
            if member_category is not None:
                matched_category = member_category

        if matched_category is not None:
            conn.execute(
                "UPDATE projects SET category = ?, updated_at = ? WHERE id = ?",
                (matched_category, now, proj_id),
            )
            updated.append({"id": proj_id, "guest_name": guest_name, "category": matched_category})
        else:
            if force_reset_unmatched:
                # 明示フラグがある場合のみNULLにリセット（データ消失防止）
                logger.warning("sync_categories: スプシ未一致によりcategoryをNULLリセット: id=%s guest=%s", proj_id, guest_name)
                conn.execute(
                    "UPDATE projects SET category = NULL, updated_at = ? WHERE id = ?",
                    (now, proj_id),
                )
            # force_reset_unmatched=False (デフォルト) は既存categoryを保持
            skipped.append({"id": proj_id, "guest_name": guest_name, "reason": "not_found_in_sheet"})

    conn.commit()
    conn.close()

    return {
        "status": "synced",
        "updated_count": len(updated),
        "skipped_count": len(skipped),
        "updated": updated,
        "skipped": skipped,
    }


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
            try:
                d[json_field] = json.loads(d[json_field])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


@app.put("/api/projects/{project_id}/youtube-assets")
def upsert_youtube_assets(project_id: str, assets: YouTubeAssetsUpsert):
    conn = _get_db()
    now = datetime.now(timezone.utc).isoformat()
    # description_originalが空の場合は既存値を保持する（空文字上書き防止）
    desc_original_value = assets.description_original
    # Noneまたは未送信項目はCOALESCEで既存値を維持し、NULL上書きを防ぐ
    conn.execute(
        """INSERT INTO youtube_assets (project_id, thumbnail_design, title_proposals,
           description_original, description_edited, selected_title_index,
           edited_title, last_edited_by, generated_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(project_id) DO UPDATE SET
             thumbnail_design=COALESCE(excluded.thumbnail_design, youtube_assets.thumbnail_design),
             title_proposals=COALESCE(excluded.title_proposals, youtube_assets.title_proposals),
             description_original=COALESCE(excluded.description_original, youtube_assets.description_original),
             description_edited=COALESCE(excluded.description_edited, youtube_assets.description_edited),
             selected_title_index=COALESCE(excluded.selected_title_index, youtube_assets.selected_title_index),
             edited_title=COALESCE(excluded.edited_title, youtube_assets.edited_title),
             last_edited_by=COALESCE(excluded.last_edited_by, youtube_assets.last_edited_by),
             updated_at=excluded.updated_at""",
        (
            project_id,
            json.dumps(assets.thumbnail_design) if assets.thumbnail_design else None,
            json.dumps(assets.title_proposals) if assets.title_proposals else None,
            desc_original_value if desc_original_value and desc_original_value.strip() else None,
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
    try:
        cur = conn.execute(
            """UPDATE youtube_assets SET description_edited=?, description_finalized_by=?,
               description_finalized_at=?, last_edited_by=?, updated_at=?
               WHERE project_id=?""",
            (body.edited, body.by, now, body.by, now, project_id)
        )
        if cur.rowcount == 0:
            conn.rollback()
            raise HTTPException(404, "YouTube assets not found for project")
        conn.commit()
    finally:
        conn.close()
    return {"status": "updated"}


@app.patch("/api/projects/{project_id}/youtube-assets/title")
def select_title(project_id: str, body: TitleSelect):
    conn = _get_db()
    now = datetime.now(timezone.utc).isoformat()
    try:
        cur = conn.execute(
            """UPDATE youtube_assets SET selected_title_index=?, edited_title=?,
               last_edited_by=?, updated_at=?
               WHERE project_id=?""",
            (body.index, body.edited_title, body.by, now, project_id)
        )
        if cur.rowcount == 0:
            conn.rollback()
            raise HTTPException(404, "YouTube assets not found for project")
        conn.commit()
    finally:
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
           converted_text, category, priority, created_by, feedback_target)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (project_id, fb.timestamp_mark, fb.raw_voice_text,
         fb.converted_text, fb.category, fb.priority, fb.created_by,
         fb.feedback_target)
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
        if fb.feedback_target in ("title", "description"):
            # AI生成物へのFB → EditLearnerに蓄積
            try:
                from ..tracker.edit_learner import EditLearner
                from ..tracker.asset_feedback_adapter import voice_fb_to_edit_diff
                edit_learner = EditLearner()
                diff_result = voice_fb_to_edit_diff(content, fb.feedback_target)
                result = edit_learner.ingest_edit(
                    project_id=project_id,
                    asset_type=fb.feedback_target,
                    diff_result=diff_result,
                )
                learned = True
                learned_patterns = result.get("new_patterns", 0) + result.get("updated_patterns", 0)
            except Exception:
                pass
        else:
            # 既存動作: FeedbackLearnerに蓄積（ディレクション/映像FB）
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
                    pass

    return {
        "status": "created",
        "project_id": project_id,
        "feedback_id": cursor.lastrowid,
        "learning_applied": learned,
        "learned_patterns": learned_patterns,
        "feedback_target": fb.feedback_target,
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


# --- FB承認フロー ---

@app.get("/api/v1/feedbacks/pending")
def list_pending_feedbacks():
    """承認待ちFB一覧（approval_status='pending'のFBをプロジェクト情報付きで返す）"""
    conn = _get_db()
    rows = conn.execute(
        "SELECT f.*, p.guest_name, p.title as project_title "
        "FROM feedbacks f "
        "LEFT JOIN projects p ON f.project_id = p.id "
        "WHERE (f.approval_status = 'pending' OR f.approval_status IS NULL) "
        "ORDER BY f.created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.put("/api/v1/feedbacks/{feedback_id}/approve")
def approve_feedback(feedback_id: int, body: dict = None):
    """FBを承認する（approval_status='approved'に変更）"""
    conn = _get_db()
    existing = conn.execute(
        "SELECT id, created_by FROM feedbacks WHERE id = ?", (feedback_id,)
    ).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Feedback not found")

    # 承認者のチェック（bodyにapproved_byがあれば、created_byと一致するか検証）
    approved_by = (body or {}).get("approved_by", existing["created_by"])
    if approved_by != existing["created_by"]:
        conn.close()
        raise HTTPException(
            status_code=403,
            detail="FB投稿者本人のみが承認できます"
        )

    cur = conn.execute(
        "UPDATE feedbacks SET approval_status = 'approved', "
        "approved_at = datetime('now'), approved_by = ? "
        "WHERE id = ? AND COALESCE(approval_status, 'pending') = 'pending'",
        (approved_by, feedback_id),
    )
    if cur.rowcount == 0:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=409, detail="このFBは既に承認・却下済みです")
    conn.commit()
    conn.close()
    return {"status": "approved", "feedback_id": feedback_id, "approved_by": approved_by}


@app.put("/api/v1/feedbacks/{feedback_id}/modify")
def modify_feedback(feedback_id: int, body: dict):
    """FBを修正して承認する（修正テキストを保存し、approval_status='modified'に変更）"""
    modified_text = (body or {}).get("modified_text", "")
    if not modified_text:
        raise HTTPException(status_code=400, detail="modified_text is required")

    conn = _get_db()
    existing = conn.execute(
        "SELECT id, created_by FROM feedbacks WHERE id = ?", (feedback_id,)
    ).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Feedback not found")

    # 承認者のチェック
    approved_by = body.get("approved_by", existing["created_by"])
    if approved_by != existing["created_by"]:
        conn.close()
        raise HTTPException(
            status_code=403,
            detail="FB投稿者本人のみが修正承認できます"
        )

    cur = conn.execute(
        "UPDATE feedbacks SET approval_status = 'modified', "
        "approved_at = datetime('now'), modified_text = ?, approved_by = ? "
        "WHERE id = ? AND COALESCE(approval_status, 'pending') = 'pending'",
        (modified_text, approved_by, feedback_id),
    )
    if cur.rowcount == 0:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=409, detail="このFBは既に承認・却下済みです")
    conn.commit()
    conn.close()
    return {
        "status": "modified",
        "feedback_id": feedback_id,
        "modified_text": modified_text,
        "approved_by": approved_by,
    }


@app.put("/api/v1/feedbacks/{feedback_id}/reject")
def reject_feedback(feedback_id: int, body: dict = None):
    """FBを却下する（approval_status='rejected'に変更）"""
    conn = _get_db()
    existing = conn.execute(
        "SELECT id, created_by FROM feedbacks WHERE id = ?", (feedback_id,)
    ).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Feedback not found")

    # 承認者のチェック
    approved_by = (body or {}).get("approved_by", existing["created_by"])
    if approved_by != existing["created_by"]:
        conn.close()
        raise HTTPException(
            status_code=403,
            detail="FB投稿者本人のみが却下できます"
        )

    cur = conn.execute(
        "UPDATE feedbacks SET approval_status = 'rejected', "
        "approved_at = datetime('now'), approved_by = ? "
        "WHERE id = ? AND COALESCE(approval_status, 'pending') = 'pending'",
        (approved_by, feedback_id),
    )
    if cur.rowcount == 0:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=409, detail="このFBは既に承認・却下済みです")
    conn.commit()
    conn.close()
    return {"status": "rejected", "feedback_id": feedback_id, "approved_by": approved_by}


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


def _grade_from_score_100(score: int) -> str:
    """0-100スケールのスコアをグレードに変換（品質ダッシュボード用）"""
    if score >= 90:
        return "A+"
    elif score >= 80:
        return "A"
    elif score >= 70:
        return "B+"
    elif score >= 60:
        return "B"
    elif score >= 50:
        return "C"
    elif score >= 40:
        return "D"
    return "E"


@app.get("/api/v1/dashboard/quality")
def quality_dashboard_stats():
    """品質ダッシュボード統計（グレード分布・カテゴリ別平均・改善傾向）

    プロジェクト全体の品質スコアを集計し、グレード分布・平均・推移を返す。
    iOS品質ダッシュボードの実データ連動に使用する。
    """
    conn = _get_db()

    # 全プロジェクトのスコア取得
    all_rows = conn.execute(
        "SELECT guest_name, shoot_date, quality_score FROM projects ORDER BY shoot_date ASC"
    ).fetchall()

    scored_rows = [r for r in all_rows if r["quality_score"] is not None]
    unscored_count = len(all_rows) - len(scored_rows)

    # グレード分布を集計
    grade_order = ["A+", "A", "B+", "B", "C", "D", "E"]
    grade_distribution: dict[str, int] = {g: 0 for g in grade_order}
    for row in scored_rows:
        g = _grade_from_score_100(row["quality_score"])
        grade_distribution[g] += 1

    # 平均スコア
    avg_score = None
    if scored_rows:
        avg_score = round(sum(r["quality_score"] for r in scored_rows) / len(scored_rows), 1)

    # 直近5件のトレンド（shoot_date降順で取得後反転）
    recent_rows = conn.execute(
        "SELECT guest_name, shoot_date, quality_score FROM projects "
        "WHERE quality_score IS NOT NULL ORDER BY shoot_date DESC LIMIT 5"
    ).fetchall()
    recent_trend = [dict(r) for r in reversed(recent_rows)]

    # 改善傾向: 直近3件の平均 vs その前3件の平均
    improvement_delta = None
    if len(scored_rows) >= 6:
        recent3 = [r["quality_score"] for r in scored_rows[-3:]]
        prev3 = [r["quality_score"] for r in scored_rows[-6:-3]]
        improvement_delta = round(sum(recent3) / 3 - sum(prev3) / 3, 1)
    elif len(scored_rows) >= 2:
        improvement_delta = round(
            scored_rows[-1]["quality_score"] - scored_rows[0]["quality_score"], 1
        )

    conn.close()

    return {
        "total_scored": len(scored_rows),
        "total_unscored": unscored_count,
        "average_score": avg_score,
        "grade_distribution": grade_distribution,
        "recent_trend": recent_trend,
        "improvement_delta": improvement_delta,
    }


# --- 品質統計（強化版） ---

def _get_quality_stats_calculator():
    """QualityStatsCalculatorのシングルトン取得（遅延初期化）"""
    if not hasattr(_get_quality_stats_calculator, "_instance"):
        from ..analyzer.quality_stats import QualityStatsCalculator
        _get_quality_stats_calculator._instance = QualityStatsCalculator(
            db_path=DB_PATH,
        )
    return _get_quality_stats_calculator._instance


@app.get("/api/v1/dashboard/quality/full")
def quality_full_stats():
    """品質統計の全体結果を一括取得（強化版）

    プロジェクト別トレンド、カテゴリ別問題頻度、編集者別品質傾向、
    FB学習ルール効果測定、改善率統計、月別平均を含む。
    """
    calc = _get_quality_stats_calculator()
    return calc.get_full_stats()


@app.get("/api/v1/dashboard/quality/project-trends")
def quality_project_trends(limit: int = 20):
    """プロジェクト別の品質スコアトレンド（時系列）"""
    calc = _get_quality_stats_calculator()
    return calc.get_project_trends(limit=limit)


@app.get("/api/v1/dashboard/quality/category-ranking")
def quality_category_ranking(limit: int = 10):
    """カテゴリ別の問題頻度ランキング"""
    calc = _get_quality_stats_calculator()
    return calc.get_category_problem_ranking(limit=limit)


@app.get("/api/v1/dashboard/quality/editor-profiles")
def quality_editor_profiles():
    """編集者別の品質傾向"""
    calc = _get_quality_stats_calculator()
    return calc.get_editor_quality_profiles()


@app.get("/api/v1/dashboard/quality/learning-effects")
def quality_learning_effects():
    """FB学習ルールの適用効果測定"""
    calc = _get_quality_stats_calculator()
    return calc.get_learning_rule_effects()


@app.get("/api/v1/dashboard/quality/improvement")
def quality_improvement_stats():
    """改善率の統計（前半/後半の比較、ベスト/ワーストスコア等）"""
    calc = _get_quality_stats_calculator()
    return calc.get_improvement_stats()


@app.get("/api/v1/dashboard/quality/monthly")
def quality_monthly_averages():
    """月別の平均品質スコア推移"""
    calc = _get_quality_stats_calculator()
    return calc.get_monthly_averages()


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


class TrackingBatchAdd(BaseModel):
    urls: list = []
    tags: list = []


class TrackingAnalyzeBatch(BaseModel):
    video_ids: list = []  # 空なら全pending
    use_llm: bool = True
    auto_learn: bool = True  # 分析後に自動でVideoLearnerに学習させるか


@app.post("/api/tracking/videos/{video_id}/analyze")
def analyze_tracking_video(video_id: str, use_llm: bool = True, auto_learn: bool = True):
    """トラッキング映像を分析 → 自動学習"""
    tracker = _get_video_tracker()
    analyzer = _get_video_analyzer()
    if not tracker or not analyzer:
        raise HTTPException(500, "Tracker/Analyzer not available")
    video = tracker.get_video(video_id)
    if not video:
        raise HTTPException(404, "Tracked video not found")

    # 字幕がなければ先に取得
    transcript = video.transcript
    if not transcript:
        transcript = tracker.fetch_transcript(video_id)

    # 分析実行（字幕・メタデータを渡す）
    tracker.update_analysis(video_id, {}, "analyzing")
    try:
        result = analyzer.analyze(
            video_url=video.url,
            transcript=transcript,
            title=video.title,
            channel_name=video.channel_name,
            duration_seconds=video.duration_seconds,
            use_llm=use_llm,
        )
        from dataclasses import asdict
        result_dict = asdict(result)
        tracker.update_analysis(video_id, result_dict, "completed")
    except Exception as e:
        tracker.update_analysis(video_id, {"error": str(e)}, "error")
        raise HTTPException(500, f"分析実行エラー: {str(e)[:200]}")

    # 自動学習: 分析結果をVideoLearnerに投入
    learned_patterns = []
    if auto_learn:
        learner = _get_video_learner()
        if learner:
            patterns = learner.learn_from_analysis(
                video_id=video_id,
                analysis_result=result_dict,
                video_url=video.url,
            )
            learned_patterns = [asdict(p) for p in patterns]

    result_dict["learned_patterns_count"] = len(learned_patterns)
    return result_dict


@app.post("/api/tracking/videos/batch")
def add_tracking_videos_batch(body: TrackingBatchAdd):
    """複数URLの一括登録"""
    tracker = _get_video_tracker()
    if not tracker:
        raise HTTPException(500, "Tracker not available")
    videos = tracker.add_videos_batch(urls=body.urls, tags=body.tags)
    from dataclasses import asdict
    return {"added": len(videos), "videos": [asdict(v) for v in videos]}


@app.post("/api/tracking/analyze-batch")
def analyze_tracking_batch(body: TrackingAnalyzeBatch):
    """複数映像の一括分析 → 学習"""
    tracker = _get_video_tracker()
    analyzer = _get_video_analyzer()
    if not tracker or not analyzer:
        raise HTTPException(500, "Tracker/Analyzer not available")

    # 対象映像を決定
    if body.video_ids:
        target_ids = body.video_ids
    else:
        # 全pending映像を対象
        target_ids = [v.id for v in tracker.list_videos(status="pending")]

    results = []
    learner = _get_video_learner() if body.auto_learn else None
    from dataclasses import asdict

    for vid in target_ids:
        video = tracker.get_video(vid)
        if not video:
            results.append({"video_id": vid, "status": "not_found"})
            continue

        try:
            # 字幕取得
            transcript = video.transcript
            if not transcript:
                transcript = tracker.fetch_transcript(vid)

            # 分析実行
            tracker.update_analysis(vid, {}, "analyzing")
            result = analyzer.analyze(
                video_url=video.url,
                transcript=transcript,
                title=video.title,
                channel_name=video.channel_name,
                duration_seconds=video.duration_seconds,
                use_llm=body.use_llm,
            )
            result_dict = asdict(result)
            tracker.update_analysis(vid, result_dict, "completed")

            # 自動学習
            learned_count = 0
            if learner:
                patterns = learner.learn_from_analysis(
                    video_id=vid, analysis_result=result_dict, video_url=video.url,
                )
                learned_count = len(patterns)

            results.append({
                "video_id": vid,
                "title": video.title,
                "status": "completed",
                "overall_score": result.overall_score,
                "learned_patterns": learned_count,
            })
        except Exception as e:
            tracker.update_analysis(vid, {"error": str(e)}, "error")
            results.append({"video_id": vid, "status": "error", "error": str(e)[:200]})

    return {
        "total": len(target_ids),
        "completed": sum(1 for r in results if r.get("status") == "completed"),
        "results": results,
    }


@app.get("/api/tracking/status")
def get_tracking_status():
    """トラッキング全体のステータスサマリー"""
    tracker = _get_video_tracker()
    if not tracker:
        return {"error": "Tracker not available"}
    summary = tracker.get_status_summary()

    # 学習状況も追加
    learner = _get_video_learner()
    if learner:
        summary["learning"] = learner.get_insights()
    return summary


@app.delete("/api/tracking/videos/{video_id}")
def remove_tracking_video(video_id: str):
    tracker = _get_video_tracker()
    if not tracker:
        raise HTTPException(500, "Tracker not available")
    if tracker.remove_video(video_id):
        return {"status": "removed"}
    raise HTTPException(404, "Tracked video not found")


# --- フレーム評価 (C-1) ---

def _get_frame_evaluator():
    """フレーム評価モジュールの取得"""
    try:
        from src.video_direction.analyzer import frame_evaluator
        return frame_evaluator
    except ImportError:
        return None


class FrameEvaluationRequest(BaseModel):
    """フレーム評価リクエスト"""
    video_path: Optional[str] = None  # 動画ファイルパス（ローカル）
    use_api: bool = False  # Claude Vision APIを使うか
    timestamps: Optional[list[str]] = None  # 評価したいタイムスタンプ（省略時はハイライトから自動選定）


@app.get("/api/v1/projects/{project_id}/frame-evaluation")
def get_frame_evaluation(project_id: str):
    """プロジェクトのフレーム評価結果を取得する（キャッシュ済み結果）

    まだ評価が実行されていない場合は空の結果を返す。
    """
    evaluator = _get_frame_evaluator()
    if not evaluator:
        return {
            "project_id": project_id,
            "status": "unavailable",
            "message": "フレーム評価モジュールが利用できません",
            "evaluations": [],
        }

    # キャッシュされた評価結果を読み込む
    cache_path = Path.home() / "AI開発10" / ".data" / "frame_evaluations" / f"{project_id}.json"
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text())
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("フレーム評価キャッシュ読み込みエラー: project_id=%s error=%s", project_id, e)
            return {
                "project_id": project_id,
                "status": "corrupt_cache",
                "message": "キャッシュが破損しています。POSTで再評価を実行してください。",
                "evaluations": [],
            }

    return {
        "project_id": project_id,
        "status": "not_evaluated",
        "message": "フレーム評価がまだ実行されていません。POSTで評価を実行してください。",
        "evaluations": [],
    }


@app.post("/api/v1/projects/{project_id}/frame-evaluation")
def run_frame_evaluation(project_id: str, body: FrameEvaluationRequest = FrameEvaluationRequest()):
    """プロジェクトのフレーム評価を実行する

    動画ファイルパスが指定されていれば実映像ベースの評価を行い、
    なければ文字起こしデータベースの推定評価を行う。
    """
    evaluator = _get_frame_evaluator()
    if not evaluator:
        raise HTTPException(500, "フレーム評価モジュールが利用できません")

    # プロジェクト取得
    conn = _get_db()
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Project not found")

    project_data = dict(row)

    # AI開発5コネクタからVideoDataを構築（簡易版）
    try:
        from src.video_direction.integrations.ai_dev5_connector import VideoData, HighlightScene
        # knowledgeフィールドからハイライト情報を復元
        highlights = []
        knowledge_json = project_data.get("knowledge")
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
            except (json.JSONDecodeError, TypeError):
                pass

        video_data = VideoData(
            title=project_data.get("title", ""),
            speakers=project_data.get("guest_name", ""),
            highlights=highlights,
        )
    except ImportError:
        raise HTTPException(500, "AI開発5コネクタが利用できません")

    # フレーム評価の実行
    from dataclasses import asdict
    result = evaluator.evaluate_frames(
        video_data=video_data,
        video_path=body.video_path,
        use_api=body.use_api,
    )
    result_dict = asdict(result)

    # 結果にメタデータを追加
    response = {
        "project_id": project_id,
        "status": "completed",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "total_frames": result_dict.get("total_frames", 0),
        "issue_count": result_dict.get("issue_count", 0),
        "review_count": result_dict.get("review_count", 0),
        "average_score": result_dict.get("average_score", 0.0),
        "is_stub": result_dict.get("is_stub", True),
        "evaluations": result_dict.get("evaluations", []),
    }

    # 結果をキャッシュに保存（tmpファイル経由で原子的書き込み）
    cache_dir = Path.home() / "AI開発10" / ".data" / "frame_evaluations"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{project_id}.json"
    cache_tmp = cache_dir / f"{project_id}.json.tmp"
    cache_tmp.write_text(json.dumps(response, ensure_ascii=False, indent=2))
    import os as _os
    _os.replace(str(cache_tmp), str(cache_path))

    return response


# --- テロップチェック (C-2 Phase 3) ---

def _get_telop_checker():
    """テロップチェックモジュールの取得"""
    try:
        from src.video_direction.analyzer import telop_checker
        return telop_checker
    except ImportError:
        return None


class TelopCheckRequest(BaseModel):
    """テロップチェックリクエスト"""
    video_path: Optional[str] = None  # 動画ファイルパス（ローカル）
    frame_images_b64: Optional[list[dict]] = None  # base64フレーム画像リスト
    use_ocr: bool = True  # OCRを使用するか
    num_samples: int = 10  # フレームサンプリング数
    telops_with_timestamps: Optional[list[dict]] = None  # タイミング評価用データ


@app.get("/api/v1/projects/{project_id}/telop-check")
def get_telop_check(project_id: str):
    """プロジェクトのテロップチェック結果を取得する（キャッシュ済み結果）"""
    checker = _get_telop_checker()
    if not checker:
        return {
            "project_id": project_id,
            "status": "unavailable",
            "message": "テロップチェックモジュールが利用できません",
        }

    # キャッシュされた結果を読み込む
    cache_path = Path.home() / "AI開発10" / ".data" / "telop_checks" / f"{project_id}.json"
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("テロップチェックキャッシュ読み込みエラー: project_id=%s error=%s", project_id, e)
            return {
                "project_id": project_id,
                "status": "corrupt_cache",
                "message": "キャッシュが破損しています。POSTで再実行してください。",
            }

    return {
        "project_id": project_id,
        "status": "not_checked",
        "message": "テロップチェックがまだ実行されていません。POSTで実行してください。",
    }


@app.post("/api/v1/projects/{project_id}/telop-check")
def run_telop_check(project_id: str, body: TelopCheckRequest = TelopCheckRequest()):
    """プロジェクトのテロップチェックを実行する

    動画ファイルまたはbase64フレーム画像からテロップを抽出し、
    誤字脱字・フォント一貫性・タイミングをチェックする。
    """
    checker = _get_telop_checker()
    if not checker:
        raise HTTPException(500, "テロップチェックモジュールが利用できません")

    # プロジェクト取得
    conn = _get_db()
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Project not found")

    project_data = dict(row)

    # VideoDataの構築（テキストベースチェックとの統合用）
    video_data = None
    try:
        from src.video_direction.integrations.ai_dev5_connector import VideoData, HighlightScene
        highlights = []
        knowledge_json = project_data.get("knowledge")
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
            except (json.JSONDecodeError, TypeError):
                pass

        video_data = VideoData(
            title=project_data.get("title", ""),
            speakers=project_data.get("guest_name", ""),
            highlights=highlights,
        )
    except ImportError:
        pass

    # フレーム画像ベースのテロップチェック実行
    from dataclasses import asdict
    frame_result = checker.check_telops_from_frames(
        video_path=body.video_path,
        frame_images_b64=body.frame_images_b64,
        video_data=video_data,
        telops_with_timestamps=body.telops_with_timestamps,
    )

    # テキストベースのテロップチェックも同時実行（VideoDataがあれば）
    text_result = None
    if video_data:
        text_result = checker.check_telops(video_data)

    # 結果を統合
    frame_dict = asdict(frame_result)
    response = {
        "project_id": project_id,
        "status": "completed",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        # フレーム画像ベースの結果
        "frame_check": {
            "total_frames_checked": frame_dict["total_frames_checked"],
            "total_telops_found": frame_dict["total_telops_found"],
            "extraction_method": frame_dict["extraction_method"],
            "extracted_telops": frame_dict["extracted_telops"],
            "spelling_issues": frame_dict["spelling_issues"],
            "consistency_issues": frame_dict["consistency_issues"],
            "timing_issues": frame_dict["timing_issues"],
            "error_count": frame_dict["error_count"],
            "warning_count": frame_dict["warning_count"],
            "overall_score": frame_dict["overall_score"],
        },
    }

    # テキストベースの結果を追加
    if text_result:
        text_dict = asdict(text_result)
        response["text_check"] = {
            "total_telops": text_dict["total_telops"],
            "error_count": text_dict["error_count"],
            "warning_count": text_dict["warning_count"],
            "consistency_score": text_dict["consistency_score"],
            "candidates": text_dict["candidates"],
            "issues": text_dict["issues"],
        }

    # 結果をキャッシュに保存（tmpファイル経由で原子的書き込み）
    cache_dir = Path.home() / "AI開発10" / ".data" / "telop_checks"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{project_id}.json"
    cache_tmp = cache_dir / f"{project_id}.json.tmp"
    cache_tmp.write_text(json.dumps(response, ensure_ascii=False, indent=2))
    import os as _os
    _os.replace(str(cache_tmp), str(cache_path))

    return response


# --- 音声品質評価 (C-3) ---

class AudioEvaluationRequest(BaseModel):
    """音声品質評価リクエスト"""
    video_path: Optional[str] = None  # 動画/音声ファイルパス（ローカル）
    use_ffmpeg: bool = True  # ffmpegを使った実解析を行うか


def _get_audio_evaluator():
    """音声品質評価モジュールの取得"""
    try:
        from src.video_direction.analyzer.audio_evaluator import AudioEvaluator
        return AudioEvaluator()
    except ImportError:
        return None


@app.get("/api/v1/projects/{project_id}/audio-evaluation")
def get_audio_evaluation(project_id: str):
    """プロジェクトの音声品質評価結果を取得する（キャッシュ済み結果）

    まだ評価が実行されていない場合は空の結果を返す。
    """
    evaluator = _get_audio_evaluator()
    if not evaluator:
        return {
            "project_id": project_id,
            "status": "unavailable",
            "message": "音声品質評価モジュールが利用できません",
            "evaluation": {},
        }

    # キャッシュされた評価結果を読み込む
    cache_path = Path.home() / "AI開発10" / ".data" / "audio_evaluations" / f"{project_id}.json"
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text())
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("音声評価キャッシュ読み込みエラー: project_id=%s error=%s", project_id, e)
            return {
                "project_id": project_id,
                "status": "corrupt_cache",
                "message": "キャッシュが破損しています。POSTで再評価を実行してください。",
                "evaluation": {},
            }

    return {
        "project_id": project_id,
        "status": "not_evaluated",
        "message": "音声品質評価がまだ実行されていません。POSTで評価を実行してください。",
        "evaluation": {},
    }


@app.post("/api/v1/projects/{project_id}/audio-evaluation")
def run_audio_evaluation(project_id: str, body: AudioEvaluationRequest = AudioEvaluationRequest()):
    """プロジェクトの音声品質評価を実行する

    動画ファイルパスが指定されていればffmpegによる実測評価を行い、
    なければ文字起こしデータベースの推定評価を行う。
    """
    evaluator = _get_audio_evaluator()
    if not evaluator:
        raise HTTPException(500, "音声品質評価モジュールが利用できません")

    # プロジェクト取得
    conn = _get_db()
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Project not found")

    project_data = dict(row)

    # AI開発5コネクタからVideoDataを構築（簡易版）
    video_data = None
    try:
        from src.video_direction.integrations.ai_dev5_connector import VideoData, HighlightScene
        # knowledgeフィールドからハイライト情報を復元
        highlights = []
        knowledge_json = project_data.get("knowledge")
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
            except (json.JSONDecodeError, TypeError):
                pass

        video_data = VideoData(
            title=project_data.get("title", ""),
            speakers=project_data.get("guest_name", ""),
            highlights=highlights,
        )
    except ImportError:
        pass  # video_data=None のまま進む（AudioEvaluator側で空データ処理）

    # 音声品質評価の実行
    video_path = body.video_path or ""

    if body.use_ffmpeg and video_path:
        # ffmpegによる実測評価
        result_dict = evaluator.evaluate_overall(video_path, video_data)
    else:
        # 文字起こしベースの推定評価
        from dataclasses import asdict
        from src.video_direction.analyzer.audio_evaluator import evaluate_audio
        if video_data:
            result = evaluate_audio(video_data, use_ffmpeg=False)
            result_dict = asdict(result)
            result_dict["stats"] = {}
        else:
            result_dict = {
                "overall_score": 0,
                "grade": "D",
                "axis_scores": [],
                "issues": [],
                "analysis_method": "unavailable",
                "is_estimated": True,
                "stats": {},
            }

    # レスポンス構築
    response = {
        "project_id": project_id,
        "status": "completed",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "overall_score": result_dict.get("overall_score", 0),
        "grade": result_dict.get("grade", "D"),
        "analysis_method": result_dict.get("analysis_method", "unknown"),
        "is_estimated": result_dict.get("is_estimated", True),
        "has_ffmpeg": evaluator.has_ffmpeg,
        "axis_scores": result_dict.get("axis_scores", []),
        "issues": result_dict.get("issues", []),
        "stats": result_dict.get("stats", {}),
        "error_count": result_dict.get("error_count", 0),
        "warning_count": result_dict.get("warning_count", 0),
    }

    # 結果をキャッシュに保存（tmpファイル経由で原子的書き込み）
    cache_dir = Path.home() / "AI開発10" / ".data" / "audio_evaluations"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{project_id}.json"
    cache_tmp = cache_dir / f"{project_id}.json.tmp"
    cache_tmp.write_text(json.dumps(response, ensure_ascii=False, indent=2))
    import os as _os
    _os.replace(str(cache_tmp), str(cache_path))

    return response


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


# 手修正学習（EditLearner）グローバルインスタンス
edit_learner = EditLearner()


def _get_edit_learner():
    """EditLearnerインスタンスを返す"""
    return edit_learner


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


# --- Vimeoレビューコメント投稿 ---

class VimeoCommentItem(BaseModel):
    """個別のVimeoコメント"""
    timecode: str  # "MM:SS" 形式のタイムコード
    text: str  # コメント本文
    priority: str = "medium"  # high/medium/low
    feedback_id: Optional[str] = None  # 元のフィードバックID


class VimeoPostReviewRequest(BaseModel):
    """Vimeoレビューコメント投稿リクエスト"""
    vimeo_video_id: str
    comments: list[VimeoCommentItem]


def _timecode_to_seconds(timecode: str) -> float:
    """タイムコード文字列を秒数に変換する。

    対応フォーマット: "MM:SS", "HH:MM:SS", "SS", 数値そのまま
    """
    timecode = timecode.strip()
    parts = timecode.split(":")
    try:
        if len(parts) == 3:
            # HH:MM:SS
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            # MM:SS
            return float(parts[0]) * 60 + float(parts[1])
        else:
            # 秒数そのまま
            return float(timecode)
    except (ValueError, TypeError):
        return 0.0


def _priority_to_japanese(priority: str) -> str:
    """英語の優先度を日本語に変換"""
    mapping = {"high": "高", "medium": "中", "low": "低"}
    return mapping.get(priority.lower(), "中")


def _build_vimeo_comment_payload(comment: VimeoCommentItem) -> dict:
    """VimeoCommentItemからVimeo API投稿用ペイロードを構築する。

    post_vimeo_review_comments.pyのbuild_comment_text/build_vimeo_payloadと
    同じロジックを使用。タイムコードモードはデフォルトembed_text。
    """
    import os

    # 優先度プレフィックス
    priority_prefix = {
        "高": "🔴【優先度: 高】",
        "中": "🟡【優先度: 中】",
        "低": "🟢【優先度: 低】",
    }
    jp_priority = _priority_to_japanese(comment.priority)
    prefix = priority_prefix.get(jp_priority, "")
    body = f"{prefix} {comment.text}" if prefix else comment.text

    mode = os.getenv("VIMEO_TIMECODE_MODE", "embed_text").strip()
    timestamp_seconds = _timecode_to_seconds(comment.timecode)

    if mode == "embed_text":
        text = f"[{comment.timecode}] {body}"
    elif mode == "body_field":
        field_name = os.getenv("VIMEO_TIMECODE_FIELD", "timecode").strip() or "timecode"
        return {"text": body, field_name: timestamp_seconds}
    elif mode == "skip":
        text = body
    else:
        text = f"[{comment.timecode}] {body}"

    return {"text": text}


@app.post("/api/v1/vimeo/post-review")
def post_vimeo_review(body: VimeoPostReviewRequest, dry_run: bool = True):
    """Vimeoレビューコメントを投稿する。

    dry_run=True（デフォルト）: 投稿計画のみ返す。Vimeo APIには送信しない。
    dry_run=False: 実際にVimeo APIへコメントを投稿する。
    """
    import os
    import sys

    # スクリプトのパスを追加してimportできるようにする
    scripts_dir = Path.home() / "AI開発10" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    target_video_id = body.vimeo_video_id
    comments = body.comments

    if not target_video_id:
        raise HTTPException(400, "vimeo_video_id is required")
    if not comments:
        raise HTTPException(400, "comments list is empty")

    # 本番投稿時: feedback_idを持つコメントの承認状態をチェック
    if not dry_run:
        conn = _get_db()
        unapproved_ids = []
        for comment in comments:
            if comment.feedback_id and comment.feedback_id.isdigit():
                fb = conn.execute(
                    "SELECT id, approval_status FROM feedbacks WHERE id = ?",
                    (int(comment.feedback_id),)
                ).fetchone()
                if fb and fb["approval_status"] not in ("approved", "modified"):
                    unapproved_ids.append(comment.feedback_id)
        conn.close()
        if unapproved_ids:
            raise HTTPException(
                403,
                f"未承認のFBが含まれています（ID: {', '.join(unapproved_ids)}）。"
                "承認後に再試行してください。"
            )

    # コメントごとにVimeo APIペイロードを構築
    plan = []
    for i, comment in enumerate(comments):
        payload = _build_vimeo_comment_payload(comment)
        timestamp_seconds = _timecode_to_seconds(comment.timecode)
        plan.append({
            "index": i,
            "feedbackId": comment.feedback_id or f"comment_{i}",
            "timecode": comment.timecode,
            "timestampSeconds": timestamp_seconds,
            "priority": comment.priority,
            "vimeoPayload": payload,
        })

    if dry_run:
        # dry-runモード: 投稿計画のみ返す
        return {
            "mode": "dry_run",
            "targetVideoId": target_video_id,
            "commentCount": len(plan),
            "plan": plan,
        }

    # 本番投稿モード: post_vimeo_review_comments.pyのロジックを使用
    try:
        from post_vimeo_review_comments import (
            load_token,
            build_endpoint,
            post_with_retry,
            COMMENT_INTERVAL,
        )
    except ImportError:
        raise HTTPException(
            500,
            "post_vimeo_review_comments モジュールが見つかりません。"
            "scripts/post_vimeo_review_comments.py を確認してください。"
        )

    try:
        token = load_token()
    except ValueError as e:
        logger.exception("Vimeoトークン読み込み失敗")
        raise HTTPException(500, "Internal server error")

    endpoint = build_endpoint(target_video_id)
    results = []
    posted_count = 0
    failed_count = 0

    for i, item in enumerate(plan):
        result = post_with_retry(endpoint, token, item["vimeoPayload"])
        result["feedbackId"] = item["feedbackId"]
        result["timecode"] = item["timecode"]

        if result.get("status") == "posted":
            posted_count += 1
        else:
            failed_count += 1

        results.append(result)

        # コメント間のインターバル（レート制限対策）
        if i < len(plan) - 1:
            import time
            time.sleep(COMMENT_INTERVAL)

    return {
        "mode": "execute",
        "targetVideoId": target_video_id,
        "results": results,
        "summary": {
            "total": len(plan),
            "posted": posted_count,
            "failed": failed_count,
        },
    }


@app.get("/api/v1/projects/{project_id}/vimeo-comments")
def get_vimeo_comments(project_id: str):
    """プロジェクトに紐づく全Vimeo動画バージョンのコメントをVimeo APIから取得する。"""
    import urllib.request

    conn = _get_db()
    proj = conn.execute("SELECT id, edited_video FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not proj:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    # 最新バージョンのvimeo_idを取得
    latest = conn.execute(
        "SELECT vimeo_id, version_label, version_order FROM video_versions "
        "WHERE project_id = ? ORDER BY version_order DESC LIMIT 1",
        (project_id,),
    ).fetchone()

    vimeo_ids = []
    if latest and latest["vimeo_id"]:
        vimeo_ids.append({"vimeo_id": latest["vimeo_id"], "label": latest["version_label"], "order": latest["version_order"]})
    else:
        ev = proj["edited_video"] or ""
        m = re.search(r"vimeo\.com/(\d+)", ev)
        if m:
            vimeo_ids.append({"vimeo_id": m.group(1), "label": "最新", "order": 0})

    conn.close()

    if not vimeo_ids:
        return {"project_id": project_id, "comments": [], "message": "Vimeo動画が未登録です"}

    # Vimeoトークン取得
    token = os.environ.get("VIMEO_ACCESS_TOKEN", "")
    if not token:
        api_keys_path = Path.home() / ".config" / "maekawa" / "api-keys.env"
        if api_keys_path.exists():
            for line in api_keys_path.read_text().splitlines():
                if line.startswith("VIMEO_ACCESS_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not token:
        return {"project_id": project_id, "comments": [], "message": "VIMEO_ACCESS_TOKENが未設定です"}

    # 各バージョンのコメントを取得
    all_comments = []
    for vid_info in vimeo_ids:
        vid = vid_info["vimeo_id"]
        label = vid_info["label"]
        url = f"https://api.vimeo.com/videos/{vid}/comments?per_page=100"
        try:
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for c in data.get("data", []):
                    # タイムコード抽出（コメント本文から [MM:SS] パターンを探す）
                    text = c.get("text", "")
                    timecode = None
                    tc_match = re.search(r"\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?", text)
                    if tc_match:
                        timecode = tc_match.group(1)
                    all_comments.append({
                        "vimeo_id": vid,
                        "version_label": label,
                        "text": text,
                        "timecode": timecode,
                        "created_time": c.get("created_time", ""),
                        "user": c.get("user", {}).get("name", ""),
                        "uri": c.get("uri", ""),
                    })
        except Exception as e:
            all_comments.append({
                "vimeo_id": vid,
                "version_label": label,
                "text": f"コメント取得エラー: {str(e)}",
                "timecode": None,
                "created_time": "",
                "user": "system",
                "uri": "",
                "error": True,
            })

    return {
        "project_id": project_id,
        "total": len(all_comments),
        "comments": all_comments,
    }


# --- フィードバック変換 (音声→プロ指示) ---

class FeedbackConvertRequest(BaseModel):
    raw_text: str
    project_id: str


@app.post("/api/feedback/convert")
def convert_feedback(body: FeedbackConvertRequest):
    """音声テキストをプロのディレクション指示に変換（カテゴリ別専門プロンプト使用）

    自己学習エンジン接続済み:
    - FeedbackLearner: 過去のFBパターンからルールを取得しプロンプトに注入
    - VideoLearner: トラッキング映像の演出パターンを引用付きでプロンプトに注入
    """
    from ..analyzer.feedback_converter import (
        build_system_prompt,
        build_conversion_prompt,
        classify_feedback_category,
    )
    from ..tracker.feedback_learner import FeedbackLearner
    from ..tracker.video_learner import VideoLearner

    raw = body.raw_text
    # カテゴリ自動検出
    category = classify_feedback_category(raw)

    # --- 自己学習エンジンからルール・参考情報を取得 ---
    learned_rules_text = ""
    tracking_refs_text = ""
    fb_rules = []
    vid_rules = []

    try:
        fb_learner = FeedbackLearner()
        fb_rules = fb_learner.get_active_rules(category=category)
        if fb_rules:
            learned_rules_text = "\n\n## 過去のFBから学習したルール（優先的に適用すること）:\n"
            for rule in fb_rules:
                learned_rules_text += f"- [{rule.priority}] {rule.rule_text}\n"
    except Exception:
        pass

    try:
        vid_learner = VideoLearner()
        # カテゴリ一致ルールを優先、なければ全カテゴリから上位5件
        vid_rules = vid_learner.get_active_rules(category=category)
        if not vid_rules:
            vid_rules = vid_learner.get_active_rules()[:5]
        if vid_rules:
            tracking_refs_text = "\n\n## トラッキング映像から学習した演出パターン（参考として活用すること）:\n"
            for rule in vid_rules:
                tracking_refs_text += f"- [{rule.category}] {rule.rule_text}\n"
            # 引用URL付きのインサイトも追加
            insights = vid_learner.get_insights_for_direction()
            if insights:
                tracking_refs_text += "\n### 演出の参考引用:\n"
                for insight in insights[:5]:  # 最大5件
                    tracking_refs_text += f"- {insight}\n"
    except Exception:
        pass

    try:
        import re
        from teko_core.llm import ask

        system_prompt = build_system_prompt(category)
        user_prompt = build_conversion_prompt(
            raw, category,
            learned_rules_text=learned_rules_text,
            tracking_refs_text=tracking_refs_text,
        )

        text = ask(user_prompt, system=system_prompt, model="opus", max_tokens=2048, timeout=120)
        # JSONブロックを抽出
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            result = json.loads(json_match.group())
            # カテゴリ情報を付与
            result["detected_category"] = category
            # 学習ルール適用情報を付与
            result["learning_applied"] = {
                "fb_rules_count": len(fb_rules),
                "video_rules_count": len(vid_rules),
            }

            # --- 自己学習: 変換結果をFeedbackLearnerに蓄積 ---
            try:
                converted = result.get("converted_text", "")
                if converted:
                    fb_id = f"fb_{body.project_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    fb_learner = FeedbackLearner()
                    fb_learner.ingest_feedback(
                        feedback_id=fb_id,
                        content=raw,
                        category=category,
                        created_by="naoto",
                    )
            except Exception:
                logger.exception("EditLearner学習処理でエラー発生（FB変換自体には影響させない）")

            return result
    except Exception:
        logger.exception("FB変換でエラー発生（フォールバックに切り替え）")

    # フォールバック: 簡易変換（LLM不使用）
    return {
        "converted_text": f"【ディレクション指示】\n{raw}\n\n※ 上記の音声フィードバックを確認し、該当箇所を修正してください。",
        "detected_category": category,
        "structured_items": [{
            "id": "1",
            "timestamp": "00:00",
            "element": "全般",
            "note": raw[:200],  # iOS側 StructuredFeedbackItem の "note" キーに統一
            "priority": "medium",
            "reason": "音声FBの自動分類結果に基づく",
            "reference_url": None,
            "reference_note": None,
        }],
    }


# --- AI生成物への音声FB変換 ---

class AssetFeedbackConvertRequest(BaseModel):
    raw_text: str
    project_id: str
    asset_type: str  # "title" / "description" / "direction"


@app.post("/api/v1/asset-feedback/convert")
def convert_asset_feedback(body: AssetFeedbackConvertRequest):
    """AI生成物（タイトル・概要欄等）への音声FBを改善指示に変換

    既存の /api/feedback/convert（映像FB用）とは別エンドポイント。
    asset_type別の専門プロンプトを使用し、EditLearnerのルールを注入する。
    """
    from ..tracker.edit_learner import EditLearner

    raw = body.raw_text
    asset_type = body.asset_type

    # EditLearnerから過去の学習ルールを取得
    learned_rules_text = ""
    rules_count = 0
    try:
        edit_learner = EditLearner()
        rules = edit_learner.get_active_rules(asset_type=asset_type)
        if rules:
            rules_count = len(rules)
            learned_rules_text = "\n\n## 過去のフィードバック・手修正から学習した改善ルール（必ず反映すること）:\n"
            for rule in rules[:10]:
                learned_rules_text += f"- [{rule.priority}] {rule.rule_text}\n"
    except Exception:
        pass

    # asset_type別の専門プロンプト
    asset_prompts = {
        "title": (
            "あなたはYouTubeタイトルの品質改善の専門家です。"
            "ユーザーからの音声フィードバックをもとに、タイトルの具体的な改善指示を生成してください。"
            "TEKOチャンネルのタイトルフォーマット（パターンA: 年収先頭型、パターンB: パンチライン先頭型）を前提とします。"
        ),
        "description": (
            "あなたはYouTube概要欄の品質改善の専門家です。"
            "ユーザーからの音声フィードバックをもとに、概要欄の具体的な改善指示を生成してください。"
            "TEKOチャンネルの概要欄フォーマット（ハッシュタグ+タイムスタンプ+CTA+チャンネル紹介）を前提とします。"
        ),
        "direction": (
            "あなたは映像ディレクションの品質改善の専門家です。"
            "ユーザーからの音声フィードバックをもとに、ディレクションレポートの具体的な改善指示を生成してください。"
        ),
    }

    system_prompt = asset_prompts.get(asset_type, asset_prompts["direction"])

    user_prompt = f"""以下の音声フィードバックを、{asset_type}の具体的な改善指示に変換してください。
{learned_rules_text}

## 音声フィードバック:
{raw}

## 出力形式（JSON）:
{{
    "converted_text": "変換後の改善指示テキスト",
    "improvement_points": ["改善ポイント1", "改善ポイント2"],
    "priority": "high" または "medium" または "low"
}}"""

    try:
        import re
        from teko_core.llm import ask

        text = ask(user_prompt, system=system_prompt, model="opus", max_tokens=1024, timeout=120)
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            result = json.loads(json_match.group())
            result["asset_type"] = asset_type
            result["learning_applied"] = {"edit_rules_count": rules_count}
            return result
    except Exception:
        pass

    # フォールバック
    return {
        "converted_text": f"【{asset_type}改善指示】\n{raw}",
        "improvement_points": [raw[:200]],
        "priority": "medium",
        "asset_type": asset_type,
        "learning_applied": {"edit_rules_count": rules_count},
    }


# --- 編集FB変換（タイミング1: 抽象FB→具体的編集指示） ---

class EditingFeedbackConvertRequest(BaseModel):
    """編集FB変換リクエスト"""
    feedback: str                              # 抽象的なFBテキスト
    guest_name: str                            # 対象ゲスト名
    category: Optional[str] = None             # "highlight" | "direction" | "telop" | "general"（Noneなら自動推定）
    project_id: Optional[str] = None           # 動画プロジェクトID（オプション）


@app.post("/api/v1/editing-feedback/convert")
def convert_editing_feedback_api(body: EditingFeedbackConvertRequest):
    """編集者の映像に対するFBを品質基準に基づいて具体的な編集指示に変換

    抽象的な音声FB（例:「冒頭のハイライト、センスなさすぎ」）を、
    QUALITY_JUDGMENT_GUIDE.mdの品質基準を参照して、
    編集者が即アクションできる具体的な指示に変換する。
    """
    from ..tracker.editing_feedback_converter import (
        convert_editing_feedback,
        ConvertedEditingFeedback,
    )
    from dataclasses import asdict

    result = convert_editing_feedback(
        raw_feedback=body.feedback,
        guest_name=body.guest_name,
        feedback_category=body.category,
        project_id=body.project_id,
    )

    return asdict(result)


# --- 編集後フィードバック (P1: Before/After差分) ---

class EditFeedbackRequest(BaseModel):
    """編集後動画のメタデータ"""
    duration_seconds: int = 0              # 編集後の動画長さ（秒）
    original_duration_seconds: int = 0    # 元動画の長さ（秒）
    included_timestamps: list = []         # 採用されたシーンのタイムスタンプ
    excluded_timestamps: list = []         # カットされたシーンのタイムスタンプ
    telop_texts: list = []                 # 実際に使われたテロップテキスト
    scene_order: list = []                 # シーンの並び順
    editor_name: str = ""                  # 担当編集者名
    stage: str = "draft"                   # 編集段階: draft/revision_1/revision_2/final


def _grade_from_score(score: float) -> str:
    """スコアをグレードに変換"""
    if score >= 9.0:
        return "A+"
    elif score >= 8.0:
        return "A"
    elif score >= 7.0:
        return "B+"
    elif score >= 6.0:
        return "B"
    elif score >= 5.0:
        return "C"
    elif score >= 4.0:
        return "D"
    return "E"


def _compute_edit_feedback(project_row, body: EditFeedbackRequest) -> dict:
    """編集後フィードバックをインライン計算（パイプライン非依存）"""
    feedback_items = []
    score_sum = 0.0
    score_count = 0

    # ① テンポ評価（圧縮率）
    if body.original_duration_seconds > 0 and body.duration_seconds > 0:
        ratio = body.duration_seconds / body.original_duration_seconds
        if 0.3 <= ratio <= 0.6:
            tempo_score = 8.5
            tempo_msg = f"圧縮率{ratio:.0%}（適切な編集テンポ）"
            cat = "positive"
            sev = "low"
        elif ratio < 0.3:
            tempo_score = 5.0
            tempo_msg = f"圧縮率{ratio:.0%}（カットしすぎの可能性。重要シーンの確認を）"
            cat = "improvement"
            sev = "high"
        elif ratio > 0.8:
            tempo_score = 4.0
            tempo_msg = f"圧縮率{ratio:.0%}（編集量が少ない。冗長部分のカット検討を）"
            cat = "critical"
            sev = "high"
        else:
            tempo_score = 6.5
            tempo_msg = f"圧縮率{ratio:.0%}（やや編集量が少ない）"
            cat = "improvement"
            sev = "medium"
        score_sum += tempo_score
        score_count += 1
        feedback_items.append({"category": cat, "area": "テンポ", "message": tempo_msg, "severity": sev})

    # ② 構成力評価（シーン順序）
    if body.scene_order and len(body.scene_order) >= 2:
        def ts_sec(ts: str) -> int:
            parts = ts.split(":")
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            return 0

        secs = [ts_sec(t) for t in body.scene_order]
        chronological = all(secs[i] <= secs[i + 1] for i in range(len(secs) - 1))
        if chronological:
            comp_score = 8.0
            comp_msg = "時系列順の構成（論理的なシーン配置）"
            cat = "positive"
            sev = "low"
        else:
            comp_score = 7.0
            comp_msg = "非時系列構成（意図的な再構成か確認推奨）"
            cat = "improvement"
            sev = "medium"
        score_sum += comp_score
        score_count += 1
        feedback_items.append({"category": cat, "area": "構成力", "message": comp_msg, "severity": sev})

    # ③ ハイライト採用率評価
    included_cnt = len(body.included_timestamps)
    excluded_cnt = len(body.excluded_timestamps)
    total_cnt = included_cnt + excluded_cnt
    if total_cnt > 0:
        rate = included_cnt / total_cnt
        if rate >= 0.7:
            hl_score = 8.0 + rate * 2
            hl_msg = f"ハイライト採用率{rate:.0%}（高密度）"
            cat = "positive"
            sev = "low"
        elif rate >= 0.4:
            hl_score = 6.0 + rate * 2
            hl_msg = f"ハイライト採用率{rate:.0%}（標準的）"
            cat = "improvement"
            sev = "medium"
        else:
            hl_score = 4.0 + rate * 2
            hl_msg = f"ハイライト採用率{rate:.0%}（重要シーンの見落としの可能性）"
            cat = "critical"
            sev = "high"
        score_sum += hl_score
        score_count += 1
        feedback_items.append({"category": cat, "area": "内容密度", "message": hl_msg, "severity": sev})

    # スコアが計算できない場合のデフォルト
    if score_count == 0:
        overall_score = 5.0
        feedback_items.append({
            "category": "improvement",
            "area": "全般",
            "message": "編集済み動画のメタデータ（尺・タイムスタンプ等）を入力すると詳細な評価が生成されます。",
            "severity": "medium",
        })
    else:
        overall_score = round(score_sum / score_count, 1)

    grade = _grade_from_score(overall_score)

    # テロップチェック（Phase 3で本実装予定）
    telop_check = {
        "error_count": 0,
        "warning_count": 0,
        "note": "テロップチェックは映像フレーム分析（Phase 3）で実装予定",
    }

    # ハイライトチェックサマリー
    highlight_check = {
        "total": total_cnt,
        "included": included_cnt,
        "excluded": excluded_cnt,
        "inclusion_rate": round(included_cnt / total_cnt, 2) if total_cnt > 0 else 0.0,
        "key_excluded": [f"[{ts}]" for ts in body.excluded_timestamps[:5]],
        "comment": (
            f"カットされたシーンが{excluded_cnt}件あります。意図的なカットか確認してください。"
            if excluded_cnt > 0
            else "すべてのシーンが採用されています。"
        ),
    }

    # ディレクション準拠度（タイムスタンプ照合ベース）
    direction_adherence = {
        "total": 0,
        "followed": 0,
        "partial": 0,
        "not_followed": 0,
        "adherence_rate": 0.0,
        "note": "ディレクション準拠度はディレクションレポートとの照合で算出されます",
    }

    # サマリー生成
    critical_cnt = sum(1 for f in feedback_items if f["category"] == "critical")
    improvement_cnt = sum(1 for f in feedback_items if f["category"] == "improvement")
    positive_cnt = sum(1 for f in feedback_items if f["category"] == "positive")

    summary = f"総合評価: {grade}（{overall_score}/10.0）。"
    if critical_cnt:
        summary += f" 要改善{critical_cnt}件。"
    if improvement_cnt:
        summary += f" 改善推奨{improvement_cnt}件。"
    if positive_cnt:
        summary += f" 良好{positive_cnt}件。"

    return {
        "project_id": str(project_row["id"]),
        "quality_score": overall_score,
        "grade": grade,
        "content_feedback": feedback_items,
        "telop_check": telop_check,
        "highlight_check": highlight_check,
        "direction_adherence": direction_adherence,
        "summary": summary,
        "editor_name": body.editor_name,
        "stage": body.stage,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
    }


@app.post("/api/v1/projects/{project_id}/edit-feedback")
def generate_edit_feedback(project_id: str, body: EditFeedbackRequest):
    """編集後フィードバック生成（Before/After差分分析）

    編集者から戻ってきた動画のメタデータを受け取り、
    ディレクションとの差分を分析してフィードバックを生成する。
    """
    conn = _get_db()
    project_row = conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    conn.close()

    if not project_row:
        raise HTTPException(404, "Project not found")

    # まず evaluator モジュールで生成を試みる
    try:
        from src.video_direction.evaluator.post_edit_feedback import (
            generate_feedback,
            EditedVideoData,
        )
        from src.video_direction.integrations.ai_dev5_connector import VideoData
        from src.video_direction.analyzer.direction_generator import DirectionTimeline
        from src.video_direction.analyzer.target_labeler import TargetLabelResult

        video_data = VideoData(
            title=project_row["title"],
            duration="",
            speakers="",
            highlights=[],
            main_topics=[],
            profiles=[],
            video_type="対談インタビュー",
        )
        edited = EditedVideoData(
            title=project_row["title"],
            duration_seconds=body.duration_seconds,
            original_duration_seconds=body.original_duration_seconds,
            included_timestamps=body.included_timestamps,
            excluded_timestamps=body.excluded_timestamps,
            telop_texts=body.telop_texts,
            scene_order=body.scene_order,
            editor_name=body.editor_name,
        )
        timeline = DirectionTimeline(entries=[], generated_at="", video_title="")
        target = TargetLabelResult()

        result = generate_feedback(video_data, timeline, target, edited)
        return {
            "project_id": project_id,
            "quality_score": result.overall_score,
            "grade": result.overall_grade,
            "content_feedback": [
                {
                    "category": f.category,
                    "area": f.area,
                    "message": f.message,
                    "severity": f.priority,
                }
                for f in result.feedback_items
            ],
            "telop_check": {
                "error_count": 0,
                "warning_count": 0,
                "note": "テロップチェックは映像フレーム分析（Phase 3）で実装予定",
            },
            "highlight_check": {
                "total": result.scene_selection.total_highlights,
                "included": result.scene_selection.included_highlights,
                "excluded": result.scene_selection.excluded_highlights,
                "inclusion_rate": result.scene_selection.inclusion_rate,
                "key_excluded": result.scene_selection.key_excluded,
                "comment": result.scene_selection.analysis_comment,
            },
            "direction_adherence": {
                "total": result.direction_adherence.total_directions,
                "followed": result.direction_adherence.followed_count,
                "partial": result.direction_adherence.partially_followed,
                "not_followed": result.direction_adherence.not_followed,
                "adherence_rate": result.direction_adherence.adherence_rate,
                "note": "",
            },
            "summary": result.summary,
            "editor_name": body.editor_name,
            "stage": body.stage,
            "generated_at": result.generated_at,
        }
    except Exception:
        # パイプライン依存モジュールが使えない場合はインライン計算にフォールバック
        pass

    return _compute_edit_feedback(project_row, body)


# --- ディレクション生成 (E2E統合) ---


class GenerateDirectionRequest(BaseModel):
    """ディレクション生成リクエスト"""
    use_llm: bool = True  # LLM分析を使うか


@app.post("/api/v1/projects/{project_id}/generate-direction")
def generate_direction(project_id: str, body: GenerateDirectionRequest = GenerateDirectionRequest()):
    """FB学習ルール+映像学習インサイトを統合してディレクションを生成する

    1. プロジェクトのknowledgeフィールドからVideoDataを構築
    2. FB学習ルール（feedback_learner）を取得
    3. 映像学習ルール（video_learner）を取得
    4. トラッキング映像のインサイト（参考URL+タイムスタンプ）を取得
    5. direction_generator.generate_directions() を呼び出し
    6. 結果にトラッキング映像の参考URLを付与
    """
    # プロジェクト取得
    conn = _get_db()
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Project not found")

    project_data = dict(row)

    # VideoDataを構築
    try:
        from src.video_direction.integrations.ai_dev5_connector import VideoData, HighlightScene
        from src.video_direction.analyzer.guest_classifier import ClassificationResult
        from src.video_direction.analyzer.income_evaluator import IncomeEvaluation
        from src.video_direction.analyzer.direction_generator import (
            generate_directions,
            get_learning_context,
        )
    except ImportError as e:
        logger.exception("必要なモジュールのimportに失敗")
        raise HTTPException(500, "Internal server error")

    # knowledgeフィールドからハイライト復元
    highlights = []
    knowledge_json = project_data.get("knowledge")
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
        except (json.JSONDecodeError, TypeError):
            pass

    video_data = VideoData(
        title=project_data.get("title", ""),
        speakers=project_data.get("guest_name", ""),
        highlights=highlights,
    )

    # ゲスト分類（簡易デフォルト）
    classification = ClassificationResult(
        tier="c",
        tier_label="層c",
        reason="APIからのデフォルト分類（プロファイル情報不足）",
        presentation_template="標準テンプレート",
        confidence="low",
    )

    # 年収演出（簡易デフォルト）
    income_eval = IncomeEvaluation(
        income_value=None,
        age_bracket="不明",
        threshold=0,
        emphasize=False,
        emphasis_reason="デフォルト（情報不足）",
        telop_suggestion="",
    )

    # learnerインスタンス取得
    feedback_learner = _get_feedback_learner()
    video_learner = _get_video_learner()

    # ディレクション生成
    try:
        timeline = generate_directions(
            video_data=video_data,
            classification=classification,
            income_eval=income_eval,
            feedback_learner=feedback_learner,
            video_learner=video_learner,
            edit_learner=edit_learner,
        )
    except Exception as e:
        logger.exception("ディレクション生成エラー")
        raise HTTPException(500, "Internal server error")

    # 学習コンテキスト取得
    learning_ctx = get_learning_context(
        feedback_learner=feedback_learner,
        video_learner=video_learner,
        edit_learner=edit_learner,
    )

    # トラッキング映像の参考URL+タイムスタンプを収集
    tracking_references = []
    tracker = _get_video_tracker()
    if tracker:
        try:
            for video in tracker.list_videos(status="completed"):
                if video.analysis_result:
                    tracking_references.append({
                        "video_id": video.id,
                        "url": video.url,
                        "title": video.title,
                        "channel": video.channel_name,
                        "analysis": video.analysis_result,
                    })
        except Exception:
            pass

    # VideoLearnerのパターンからexample_urlsを収集
    video_reference_urls = []
    if video_learner:
        try:
            for pattern in video_learner.get_patterns(min_confidence=0.3):
                for url in pattern.example_urls:
                    video_reference_urls.append({
                        "url": url,
                        "pattern": pattern.pattern,
                        "category": pattern.category,
                        "confidence": pattern.confidence,
                    })
        except Exception:
            pass

    # DirectionTimelineをJSONシリアライズ
    from dataclasses import asdict
    entries_list = []
    for entry in timeline.entries:
        entries_list.append(asdict(entry))

    return {
        "project_id": project_id,
        "direction_timeline": {
            "entries": entries_list,
            "llm_analysis": timeline.llm_analysis,
            "applied_rules": timeline.applied_rules,
        },
        "learning_context": learning_ctx,
        "tracking_references": tracking_references,
        "video_reference_urls": video_reference_urls,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# --- E2Eパイプライン ---


class E2EPipelineRequest(BaseModel):
    """E2Eパイプラインリクエスト"""
    vimeo_video_id: Optional[str] = None  # Vimeo動画ID（投稿先）
    dry_run: bool = True  # Vimeo投稿をdry_runにするか
    use_llm: bool = True  # LLM分析を使うか


@app.post("/api/v1/projects/{project_id}/e2e-pipeline")
def run_e2e_pipeline(project_id: str, body: E2EPipelineRequest = E2EPipelineRequest()):
    """E2Eパイプライン: FB入力→FB学習→映像学習→手修正学習→ディレクション生成→Vimeo投稿

    統合フロー全体を1回のAPI呼び出しで実行する:
    1. プロジェクトのFB一覧取得
    2. FB学習ルール確認
    3. 映像学習インサイト取得（トラッキング映像の参考URL+タイムスタンプ含む）
    4. ディレクション生成（LLMで美しい言い回しに変換）
    4.5. 手修正学習ルール確認（既存editsのdiff分析→学習DB蓄積）
    5. Vimeoレビューコメント投稿（dry_runオプション付き）
    """
    pipeline_steps = {}
    errors = []

    # --- Step 1: プロジェクトとFB一覧取得 ---
    conn = _get_db()
    project_row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not project_row:
        conn.close()
        raise HTTPException(404, "Project not found")

    fb_rows = conn.execute(
        "SELECT * FROM feedbacks WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,)
    ).fetchall()
    conn.close()

    project_data = dict(project_row)
    feedbacks = [dict(r) for r in fb_rows]
    pipeline_steps["step1_feedbacks"] = {
        "status": "ok",
        "feedback_count": len(feedbacks),
        "project_title": project_data.get("title", ""),
        "guest_name": project_data.get("guest_name", ""),
    }

    # --- Step 2: FB学習ルール確認 ---
    feedback_learner = _get_feedback_learner()
    fb_learning = {}
    if feedback_learner:
        try:
            fb_learning = feedback_learner.get_insights()
            pipeline_steps["step2_fb_learning"] = {
                "status": "ok",
                "insights": fb_learning,
            }
        except Exception as e:
            pipeline_steps["step2_fb_learning"] = {"status": "error", "error": str(e)}
            errors.append(f"FB学習ルール取得エラー: {e}")
    else:
        pipeline_steps["step2_fb_learning"] = {"status": "unavailable"}

    # --- Step 3: 映像学習インサイト取得 ---
    video_learner = _get_video_learner()
    video_learning = {}
    tracking_references = []

    if video_learner:
        try:
            video_learning = video_learner.get_insights()
            pipeline_steps["step3_video_learning"] = {
                "status": "ok",
                "insights": video_learning,
            }
        except Exception as e:
            pipeline_steps["step3_video_learning"] = {"status": "error", "error": str(e)}
            errors.append(f"映像学習インサイト取得エラー: {e}")
    else:
        pipeline_steps["step3_video_learning"] = {"status": "unavailable"}

    # トラッキング映像の参考URL+タイムスタンプ
    tracker = _get_video_tracker()
    if tracker:
        try:
            for video in tracker.list_videos(status="completed"):
                if video.analysis_result:
                    tracking_references.append({
                        "video_id": video.id,
                        "url": video.url,
                        "title": video.title,
                        "channel": video.channel_name,
                        "analysis": video.analysis_result,
                    })
        except Exception:
            pass

    # VideoLearnerのパターンからexample_urls収集
    video_reference_urls = []
    if video_learner:
        try:
            for pattern in video_learner.get_patterns(min_confidence=0.3):
                for url in pattern.example_urls:
                    video_reference_urls.append({
                        "url": url,
                        "pattern": pattern.pattern,
                        "category": pattern.category,
                        "confidence": pattern.confidence,
                    })
        except Exception:
            pass

    # --- Step 4: ディレクション生成 ---
    direction_result = None
    try:
        from src.video_direction.integrations.ai_dev5_connector import VideoData, HighlightScene
        from src.video_direction.analyzer.guest_classifier import ClassificationResult
        from src.video_direction.analyzer.income_evaluator import IncomeEvaluation
        from src.video_direction.analyzer.direction_generator import (
            generate_directions,
            get_learning_context,
        )

        # knowledgeからハイライト復元
        highlights = []
        knowledge_json = project_data.get("knowledge")
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
            except (json.JSONDecodeError, TypeError):
                pass

        video_data = VideoData(
            title=project_data.get("title", ""),
            speakers=project_data.get("guest_name", ""),
            highlights=highlights,
        )

        classification = ClassificationResult(
            tier="c", tier_label="層c",
            reason="APIデフォルト分類", presentation_template="標準テンプレート",
            confidence="low",
        )
        income_eval = IncomeEvaluation(
            income_value=None, age_bracket="不明", threshold=0,
            emphasize=False, emphasis_reason="デフォルト", telop_suggestion="",
        )

        timeline = generate_directions(
            video_data=video_data,
            classification=classification,
            income_eval=income_eval,
            feedback_learner=feedback_learner,
            video_learner=video_learner,
            edit_learner=edit_learner,
        )

        learning_ctx = get_learning_context(
            feedback_learner=feedback_learner,
            video_learner=video_learner,
            edit_learner=edit_learner,
        )

        from dataclasses import asdict
        entries_list = [asdict(entry) for entry in timeline.entries]

        direction_result = {
            "entries": entries_list,
            "llm_analysis": timeline.llm_analysis,
            "applied_rules": timeline.applied_rules,
        }

        pipeline_steps["step4_direction"] = {
            "status": "ok",
            "entry_count": len(entries_list),
            "has_llm_analysis": bool(timeline.llm_analysis),
            "applied_rule_count": len(timeline.applied_rules),
            "learning_context": learning_ctx,
        }

    except Exception as e:
        pipeline_steps["step4_direction"] = {"status": "error", "error": str(e)}
        errors.append(f"ディレクション生成エラー: {e}")

    # --- Step 4.5: 手修正学習ルール確認 ---
    edit_learner_instance = _get_edit_learner()
    edit_learning = {}
    if edit_learner_instance:
        try:
            edit_learning = edit_learner_instance.get_insights()
            # プロジェクトに既存のeditsがあればdiff分析→学習DB蓄積
            if direction_result:
                existing_edits = []
                edit_conn = _get_db()
                try:
                    # editsテーブルがあればプロジェクトの手修正履歴を取得
                    edit_rows = edit_conn.execute(
                        "SELECT * FROM edits WHERE project_id = ? ORDER BY created_at DESC",
                        (project_id,)
                    ).fetchall()
                    existing_edits = [dict(r) for r in edit_rows]
                except Exception:
                    pass
                finally:
                    edit_conn.close()

                # 既存editがあればdiff分析→学習DB蓄積
                for edit_row in existing_edits:
                    try:
                        edit_learner_instance.ingest_edit(
                            project_id=project_id,
                            asset_type=edit_row.get("asset_type", "direction"),
                            diff_result=edit_row,
                        )
                    except Exception:
                        pass

                # 学習後に再取得
                edit_learning = edit_learner_instance.get_insights()

            pipeline_steps["step4_5_edit_learning"] = {
                "status": "ok",
                "insights": edit_learning,
                "edit_rules_count": len(edit_learner_instance.get_active_rules()),
                "edit_patterns_count": len(edit_learner_instance.get_patterns()),
            }
        except Exception as e:
            pipeline_steps["step4_5_edit_learning"] = {"status": "error", "error": str(e)}
            errors.append(f"手修正学習ルール取得エラー: {e}")
    else:
        pipeline_steps["step4_5_edit_learning"] = {"status": "unavailable"}

    # --- Step 4.6: YouTube素材（タイトル・概要欄・サムネ指示書）再生成 ---
    try:
        from ..analyzer.title_generator import generate_title_proposals
        from ..analyzer.description_writer import generate_description
        from ..analyzer.thumbnail_designer import generate_thumbnail_design
        from ..knowledge.loader import KnowledgeLoader

        knowledge_ctx = KnowledgeLoader().load()

        # Step 4で作成済みの video_data, classification, income_eval を再利用
        # （Step 4が失敗した場合は再構築）
        if 'video_data' not in dir() or video_data is None:
            from ..integrations.ai_dev5_connector import VideoData
            from ..analyzer.guest_classifier import ClassificationResult
            from ..analyzer.income_evaluator import IncomeEvaluation
            video_data = VideoData(
                title=project_data.get("title", ""),
                speakers=project_data.get("guest_name", ""),
            )
            classification = ClassificationResult(
                tier="c", tier_label="層c",
                reason="APIデフォルト分類", presentation_template="標準テンプレート",
                confidence="low",
            )
            income_eval = IncomeEvaluation(
                income_value=None, age_bracket="不明", threshold=0,
                emphasize=False, emphasis_reason="デフォルト", telop_suggestion="",
            )

        # knowledgeからプロフィール情報をVideoDataに補完
        if not video_data.profiles:
            try:
                from ..integrations.ai_dev5_connector import PersonProfile
                knowledge_json = project_data.get("knowledge")
                profiles_data = []
                if knowledge_json:
                    kd = json.loads(knowledge_json) if isinstance(knowledge_json, str) else knowledge_json
                    profiles_data = kd.get("profiles", [])
                if profiles_data:
                    p = profiles_data[0]
                    video_data.profiles = [PersonProfile(
                        name=p.get("name", project_data.get("guest_name", "")),
                        age=p.get("age", str(project_data.get("guest_age", "")) if project_data.get("guest_age") else ""),
                        occupation=p.get("occupation", project_data.get("guest_occupation", "")),
                        income=p.get("income", ""),
                        side_business=p.get("side_business", ""),
                    )]
                elif project_data.get("guest_name"):
                    video_data.profiles = [PersonProfile(
                        name=project_data.get("guest_name", ""),
                        age=str(project_data.get("guest_age", "")) if project_data.get("guest_age") else "",
                        occupation=project_data.get("guest_occupation", ""),
                        income="",
                        side_business="",
                    )]
            except Exception:
                pass

        # 年収情報があればincomeを強調に設定
        if video_data.profiles and video_data.profiles[0].income:
            income_eval = IncomeEvaluation(
                income_value=None, age_bracket="不明", threshold=0,
                emphasize=True, emphasis_reason="年収情報あり", telop_suggestion="",
            )

        # EditLearnerから学習ルールを取得して生成関数に注入
        _edit_learner = None
        try:
            from ..tracker.edit_learner import EditLearner
            _edit_learner = EditLearner()
        except Exception:
            pass
        # 固有名詞フィルタ（ゲスト名を渡して他ゲストの企業名混入を防止）
        from ..analyzer.proper_noun_filter import detect_proper_nouns
        _guest_name_for_filter = video_data.profiles[0].name if video_data.profiles else None
        _proper_nouns = detect_proper_nouns(video_data, guest_name=_guest_name_for_filter)
        yt_titles = generate_title_proposals(video_data, classification, income_eval, knowledge_ctx, edit_learner=_edit_learner, proper_nouns=_proper_nouns)
        yt_description = generate_description(video_data, classification, income_eval, knowledge_ctx, edit_learner=_edit_learner, proper_nouns=_proper_nouns)
        yt_thumbnail = generate_thumbnail_design(video_data, classification, income_eval, knowledge_ctx)

        # DB更新
        assets = YouTubeAssetsUpsert(
            thumbnail_design=json.loads(yt_thumbnail.to_json()) if hasattr(yt_thumbnail, 'to_json') else {"raw": str(yt_thumbnail)},
            title_proposals={"candidates": [{"title": c.title, "target_segment": c.target_segment, "appeal_type": c.appeal_type, "rationale": c.rationale} for c in yt_titles.candidates], "recommended_index": yt_titles.recommended_index} if yt_titles.candidates else None,
            description_original=yt_description.full_text if yt_description else None,
        )
        upsert_youtube_assets(project_id, assets)

        pipeline_steps["step4_6_youtube_assets"] = {
            "status": "ok",
            "title_count": len(yt_titles.candidates) if yt_titles.candidates else 0,
            "description_length": len(yt_description.full_text) if yt_description and yt_description.full_text else 0,
        }
    except Exception as e:
        pipeline_steps["step4_6_youtube_assets"] = {"status": "error", "error": str(e)}
        errors.append(f"YouTube素材再生成エラー: {e}")

    # --- Step 5: Vimeoレビューコメント投稿 ---
    vimeo_result = None
    if body.vimeo_video_id and direction_result and direction_result.get("entries"):
        try:
            # ディレクションエントリからVimeoコメントを構築
            vimeo_comments = []
            for entry in direction_result["entries"]:
                vimeo_comments.append(VimeoCommentItem(
                    timecode=entry["timestamp"],
                    text=entry["note"],  # "instruction" → "note" に統一
                    priority=entry.get("priority", "medium"),
                    feedback_id=None,
                ))

            vimeo_request = VimeoPostReviewRequest(
                vimeo_video_id=body.vimeo_video_id,
                comments=vimeo_comments,
            )

            # 既存のpost_vimeo_review関数を呼び出す
            vimeo_result = post_vimeo_review(body=vimeo_request, dry_run=body.dry_run)
            pipeline_steps["step5_vimeo"] = {
                "status": "ok",
                "mode": "dry_run" if body.dry_run else "execute",
                "comment_count": len(vimeo_comments),
            }
        except Exception as e:
            pipeline_steps["step5_vimeo"] = {"status": "error", "error": str(e)}
            errors.append(f"Vimeo投稿エラー: {e}")
    else:
        skip_reason = []
        if not body.vimeo_video_id:
            skip_reason.append("vimeo_video_idが未指定")
        if not direction_result:
            skip_reason.append("ディレクション生成に失敗")
        elif not direction_result.get("entries"):
            skip_reason.append("ディレクションエントリが空")
        pipeline_steps["step5_vimeo"] = {
            "status": "skipped",
            "reason": "、".join(skip_reason),
        }

    return {
        "project_id": project_id,
        "pipeline_steps": pipeline_steps,
        "direction_timeline": direction_result,
        "tracking_references": tracking_references,
        "video_reference_urls": video_reference_urls,
        "edit_learning": edit_learning,
        "vimeo_result": vimeo_result,
        "errors": errors,
        "success": len(errors) == 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# --- FB→LLM変換の強化版 ---


class FeedbackConvertEnhancedRequest(BaseModel):
    """FB変換強化版リクエスト"""
    raw_text: str
    project_id: str
    use_learning_rules: bool = True  # FB学習ルールを参照するか
    include_tracking_references: bool = True  # トラッキング映像の参考事例を含めるか


@app.post("/api/v1/feedback/convert-enhanced")
def convert_feedback_enhanced(body: FeedbackConvertEnhancedRequest):
    """FB→LLM変換の強化版: FB学習ルール+トラッキング映像参考事例を統合

    既存の /api/feedback/convert を拡張:
    - FB学習ルールを参照して具体的な指示に変換
    - トラッキング映像から参考事例をURL+タイムスタンプ付きで引用
    """
    raw = body.raw_text

    # FB学習ルールを収集
    learned_rules_text = ""
    if body.use_learning_rules:
        fl = _get_feedback_learner()
        if fl:
            try:
                active_rules = fl.get_active_rules()
                if active_rules:
                    rules_lines = [f"- [{r.category}] {r.rule_text} (優先度: {r.priority})" for r in active_rules[:10]]
                    learned_rules_text = "\n\n## 過去のフィードバックから学習した演出ルール:\n" + "\n".join(rules_lines)
            except Exception:
                pass

    # トラッキング映像の参考事例を収集
    tracking_refs_text = ""
    tracking_references = []
    if body.include_tracking_references:
        # VideoLearnerからパターン+URL
        vl = _get_video_learner()
        if vl:
            try:
                for pattern in vl.get_patterns(min_confidence=0.3):
                    for url in pattern.example_urls:
                        tracking_references.append({
                            "url": url,
                            "pattern": pattern.pattern,
                            "category": pattern.category,
                            "confidence": pattern.confidence,
                        })
                if tracking_references:
                    refs_lines = [f"- {r['url']} （{r['category']}: {r['pattern']}）" for r in tracking_references[:5]]
                    tracking_refs_text = "\n\n## 参考映像事例（トラッキング映像から）:\n" + "\n".join(refs_lines)
            except Exception:
                pass

        # VideoTrackerから完了済み映像
        tracker = _get_video_tracker()
        if tracker:
            try:
                for video in tracker.list_videos(status="completed"):
                    if video.analysis_result:
                        tracking_references.append({
                            "url": video.url,
                            "title": video.title,
                            "channel": video.channel_name,
                            "category": "analyzed_video",
                            "analysis": video.analysis_result,
                        })
            except Exception:
                pass

    # LLM変換
    # カテゴリ別専門プロンプトを使用
    from ..analyzer.feedback_converter import (
        build_system_prompt,
        build_conversion_prompt,
        classify_feedback_category,
    )

    category = classify_feedback_category(raw)

    try:
        import re
        from teko_core.llm import ask

        system_prompt = build_system_prompt(category)
        user_prompt = build_conversion_prompt(
            raw, category, learned_rules_text, tracking_refs_text
        )

        text = ask(user_prompt, system=system_prompt, model="opus", max_tokens=2048, timeout=120)
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            result = json.loads(json_match.group())
            result["detected_category"] = category
            result["tracking_references"] = tracking_references
            result["learning_rules_applied"] = bool(learned_rules_text)
            return result
    except Exception:
        logger.exception("AI生成物FB変換でエラー発生（フォールバックに切り替え）")

    # フォールバック: 簡易変換（LLM不使用）
    return {
        "converted_text": f"【ディレクション指示】\n{raw}\n\n※ 上記の音声フィードバックを確認し、該当箇所を修正してください。",
        "detected_category": category,
        "structured_items": [{
            "id": "1",
            "timestamp": "00:00",
            "element": "全般",
            "note": raw[:200],  # iOS側 StructuredFeedbackItem の "note" キーに統一
            "priority": "medium",
            "reason": "音声FBの自動分類結果に基づく",
            "reference_url": None,
            "reference_note": None,
        }],
        "tracking_references": tracking_references,
        "learning_rules_applied": bool(learned_rules_text),
    }


# --- ナレッジページ連携（KP-1: AI開発5 動画ナレッジページ統合） ---

from .knowledge_pages import KnowledgePageIntegration

_knowledge = KnowledgePageIntegration()


@app.get("/api/v1/knowledge/pages")
def list_knowledge_pages(limit: int = 50, offset: int = 0):
    """ナレッジページ一覧を返す"""
    pages = _knowledge.list_pages()
    total = len(pages)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "pages": pages[offset:offset + limit],
    }


@app.get("/api/v1/knowledge/pages/{page_id}")
def get_knowledge_page(page_id: str, format: str = "meta"):
    """個別のナレッジページを返す

    Args:
        page_id: ページID（拡張子なしのファイル名）
        format: "meta"（メタ情報のみ）, "html"（HTML全文）, "text"（テキスト抽出）
    """
    if format == "html":
        html = _knowledge.get_page_content(page_id)
        if html is None:
            raise HTTPException(status_code=404, detail=f"Knowledge page not found: {page_id}")
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html)

    if format == "text":
        text = _knowledge.get_page_text(page_id)
        if text is None:
            raise HTTPException(status_code=404, detail=f"Knowledge page not found: {page_id}")
        return {"id": page_id, "text": text}

    # デフォルト: メタ情報
    meta = _knowledge.get_page_meta(page_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Knowledge page not found: {page_id}")
    return meta


@app.get("/api/v1/knowledge/search")
def search_knowledge_pages(q: str, limit: int = 20):
    """ナレッジ内を全文検索"""
    if not q or len(q.strip()) == 0:
        raise HTTPException(status_code=400, detail="Search query 'q' is required")
    results = _knowledge.search_knowledge(q.strip())
    return {
        "query": q,
        "total": len(results),
        "results": results[:limit],
    }


@app.get("/api/v1/knowledge/guest/{guest_name}")
def get_guest_knowledge(guest_name: str):
    """特定ゲストに関連するナレッジ一覧"""
    results = _knowledge.get_guest_knowledge(guest_name)
    return {
        "guest_name": guest_name,
        "total": len(results),
        "pages": results,
    }


# --- プロジェクト別 素材動画 CRUD ---


def _extract_video_id(url: str) -> str:
    """YouTube URLからvideo_idを抽出する"""
    import re
    # https://www.youtube.com/watch?v=XXXX
    m = re.search(r"[?&]v=([A-Za-z0-9_-]+)", url)
    if m:
        return m.group(1)
    # https://youtu.be/XXXX
    m = re.search(r"youtu\.be/([A-Za-z0-9_-]+)", url)
    if m:
        return m.group(1)
    # https://www.youtube.com/embed/XXXX
    m = re.search(r"youtube\.com/embed/([A-Za-z0-9_-]+)", url)
    if m:
        return m.group(1)
    return ""


@app.get("/api/v1/projects/{project_id}/source-videos")
def list_project_source_videos(project_id: str):
    """プロジェクトに紐づく素材YouTube動画一覧を返す。

    source_videosテーブルと、既存のprojects.source_video JSONの両方を統合して返す。
    """
    conn = _get_db()

    # プロジェクト存在チェック
    proj = conn.execute("SELECT id, source_video FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not proj:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    videos = []

    # 1. source_videosテーブルから取得
    rows = conn.execute(
        "SELECT * FROM source_videos WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,),
    ).fetchall()
    for row in rows:
        videos.append({
            "id": row["id"],
            "project_id": row["project_id"],
            "youtube_url": row["youtube_url"],
            "video_id": row["video_id"],
            "title": row["title"],
            "duration": row["duration"],
            "quality_status": row["quality_status"],
            "source": row["source"],
            "knowledge_file": row["knowledge_file"],
            "created_at": row["created_at"],
        })

    # 2. projects.source_video JSON（レガシー互換）がテーブルに未登録なら追加表示
    legacy = proj["source_video"]
    if legacy:
        try:
            data = json.loads(legacy) if isinstance(legacy, str) else legacy
            if data and data.get("url"):
                legacy_url = data["url"]
                legacy_vid = _extract_video_id(legacy_url)
                # 重複チェック: 既にsource_videosテーブルに同じvideo_idがあればスキップ
                if legacy_vid and not any(v["video_id"] == legacy_vid for v in videos):
                    videos.append({
                        "id": None,
                        "project_id": project_id,
                        "youtube_url": legacy_url,
                        "video_id": legacy_vid,
                        "title": None,
                        "duration": None,
                        "quality_status": data.get("quality", "pending"),
                        "source": data.get("source", "ai_dev5"),
                        "knowledge_file": data.get("knowledge_file"),
                        "created_at": data.get("linked_at"),
                    })
        except (json.JSONDecodeError, TypeError):
            pass

    conn.close()
    return {
        "project_id": project_id,
        "total": len(videos),
        "videos": videos,
    }


@app.post("/api/v1/projects/{project_id}/source-videos")
def add_project_source_video(project_id: str, req: SourceVideoCreate):
    """素材動画URLを手動登録する"""
    conn = _get_db()

    # プロジェクト存在チェック
    proj = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not proj:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    video_id = _extract_video_id(req.youtube_url)
    if not video_id:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid YouTube URL: could not extract video_id")

    # 重複チェック
    existing = conn.execute(
        "SELECT id FROM source_videos WHERE project_id = ? AND video_id = ?",
        (project_id, video_id),
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=409, detail="This video is already registered for this project")

    conn.execute(
        """INSERT INTO source_videos (project_id, youtube_url, video_id, title, duration, quality_status, source)
           VALUES (?, ?, ?, ?, ?, ?, 'manual')""",
        (project_id, req.youtube_url, video_id, req.title, req.duration, req.quality_status),
    )
    conn.commit()

    # 登録したレコードを返す
    row = conn.execute(
        "SELECT * FROM source_videos WHERE project_id = ? AND video_id = ?",
        (project_id, video_id),
    ).fetchone()
    conn.close()

    # 自動レポート生成をバックグラウンドで実行
    try:
        from .auto_report_trigger import trigger_auto_report
        trigger_auto_report(project_id)
    except Exception as e:
        logger.warning("自動レポート生成トリガー失敗（source-videos API）: %s", e)

    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "youtube_url": row["youtube_url"],
        "video_id": row["video_id"],
        "title": row["title"],
        "duration": row["duration"],
        "quality_status": row["quality_status"],
        "source": row["source"],
        "knowledge_file": row["knowledge_file"],
        "created_at": row["created_at"],
    }


# --- 素材動画連携（AI開発5） ---

class SourceVideoScanRequest(BaseModel):
    dry_run: bool = True


@app.post("/api/v1/source-videos/scan")
def scan_source_videos(req: SourceVideoScanRequest):
    """AI開発5のナレッジファイルをスキャンし、素材動画URLを自動登録する"""
    from .source_video_linker import SourceVideoLinker
    linker = SourceVideoLinker(db_path=DB_PATH)
    result = linker.scan_and_link(dry_run=req.dry_run)

    # dry_runでない場合、リンク成功したプロジェクトに対して自動レポート生成
    if not req.dry_run and result.linked:
        try:
            from .auto_report_trigger import trigger_auto_report
            for candidate in result.linked:
                trigger_auto_report(candidate.project_id)
        except Exception as e:
            logger.warning("自動レポート生成トリガー失敗（scan）: %s", e)

    return {
        "dry_run": req.dry_run,
        "linked": [
            {
                "project_id": c.project_id,
                "guest_name": c.project_guest_name,
                "youtube_url": c.youtube_url,
                "match_score": c.match_score,
                "reason": c.reason,
                "quality": c.quality,
            }
            for c in result.linked
        ],
        "skipped_existing": [
            {
                "project_id": c.project_id,
                "guest_name": c.project_guest_name,
                "youtube_url": c.youtube_url,
            }
            for c in result.skipped_existing
        ],
        "skipped_no_audio": [
            {
                "project_id": c.project_id,
                "guest_name": c.project_guest_name,
                "transcript_method": c.transcript_method,
            }
            for c in result.skipped_no_audio
        ],
        "skipped_no_match": len(result.skipped_no_match),
        "errors": result.errors,
        "summary": {
            "total_linked": len(result.linked),
            "total_skipped_existing": len(result.skipped_existing),
            "total_skipped_no_audio": len(result.skipped_no_audio),
            "total_skipped_no_match": len(result.skipped_no_match),
            "total_errors": len(result.errors),
        },
    }


@app.get("/api/v1/source-videos/status")
def source_videos_status():
    """素材動画連携の状況サマリーを返す"""
    from .source_video_linker import SourceVideoLinker
    linker = SourceVideoLinker(db_path=DB_PATH)
    return linker.get_status()


# --- ビフォーアフター比較 ---

@app.get("/api/v1/projects/{project_id}/before-after")
def get_before_after(project_id: str):
    """プロジェクトの全動画バージョン一覧（素材 vs 編集後 vs FB後再編集版）を返す。"""
    conn = _get_db()

    proj = conn.execute(
        "SELECT id, guest_name, title, source_video, edited_video FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()
    if not proj:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    # 素材動画（YouTube）の収集
    source_videos = []
    rows = conn.execute(
        "SELECT * FROM source_videos WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,),
    ).fetchall()
    for row in rows:
        source_videos.append({
            "youtube_url": row["youtube_url"],
            "video_id": row["video_id"],
            "title": row["title"],
            "duration": row["duration"],
            "embed_url": f"https://www.youtube.com/embed/{row['video_id']}?playsinline=1&rel=0",
        })

    # レガシー source_video JSON
    legacy = proj["source_video"]
    if legacy:
        try:
            data = json.loads(legacy) if isinstance(legacy, str) else legacy
            if data and data.get("url"):
                legacy_vid = _extract_video_id(data["url"])
                if legacy_vid and not any(v["video_id"] == legacy_vid for v in source_videos):
                    source_videos.append({
                        "youtube_url": data["url"],
                        "video_id": legacy_vid,
                        "title": None,
                        "duration": None,
                        "embed_url": f"https://www.youtube.com/embed/{legacy_vid}?playsinline=1&rel=0",
                    })
        except (json.JSONDecodeError, TypeError):
            pass

    # --- video_versionsテーブルからバージョン情報を取得 ---
    versions = conn.execute(
        "SELECT * FROM video_versions WHERE project_id = ? ORDER BY version_order ASC",
        (project_id,),
    ).fetchall()

    def _build_vimeo_entry(row):
        """video_versionsの行からVimeo情報を構築"""
        vimeo_url = row["vimeo_url"] or ""
        vimeo_id = row["vimeo_id"] or ""
        privacy_hash = row["privacy_hash"] or ""
        embed_url = None
        if vimeo_id:
            hash_param = f"?h={privacy_hash}" if privacy_hash else ""
            embed_url = f"https://player.vimeo.com/video/{vimeo_id}{hash_param}"
        return {
            "vimeo_url": vimeo_url,
            "vimeo_id": vimeo_id,
            "embed_url": embed_url,
            "version_label": row["version_label"],
            "version_order": row["version_order"],
            "editor_name": row["editor_name"],
        }

    # 編集後動画 = 初稿（version_order=0）
    edited_video = None
    # FB後再編集版 = 最新のFB修正版（version_order最大、ただし初稿以外）
    fb_revised_video = None
    # 全バージョン一覧
    all_versions = []

    if versions:
        for v in versions:
            all_versions.append(_build_vimeo_entry(v))

        # 初稿を探す（version_order=0）
        shoko_versions = [v for v in versions if v["version_order"] == 0]
        if shoko_versions:
            edited_video = _build_vimeo_entry(shoko_versions[0])

        # FB修正版を探す（version_order > 0 かつ 完成(100)以外、最新=最大order）
        fb_versions = [v for v in versions if 0 < v["version_order"] < 100]
        if fb_versions:
            latest_fb = max(fb_versions, key=lambda v: v["version_order"])
            fb_revised_video = _build_vimeo_entry(latest_fb)
    else:
        # video_versionsにデータがない場合、レガシーのprojects.edited_videoから取得
        ev = proj["edited_video"]
        if ev:
            vimeo_url = None
            try:
                ev_data = json.loads(ev) if isinstance(ev, str) else ev
                if ev_data and isinstance(ev_data, dict) and ev_data.get("url"):
                    vimeo_url = ev_data["url"]
            except (json.JSONDecodeError, TypeError):
                if isinstance(ev, str) and "vimeo.com" in ev:
                    vimeo_url = ev.strip()

            if vimeo_url:
                vimeo_id = ""
                privacy_hash = ""
                m = re.search(r"vimeo\.com/(\d+)", vimeo_url)
                if m:
                    vimeo_id = m.group(1)
                m_hash = re.search(r"vimeo\.com/\d+/([a-f0-9]+)", vimeo_url)
                if m_hash:
                    privacy_hash = m_hash.group(1)
                embed_url = None
                if vimeo_id:
                    hash_param = f"?h={privacy_hash}" if privacy_hash else ""
                    embed_url = f"https://player.vimeo.com/video/{vimeo_id}{hash_param}"
                edited_video = {
                    "vimeo_url": vimeo_url,
                    "vimeo_id": vimeo_id,
                    "embed_url": embed_url,
                    "version_label": "不明",
                    "version_order": -1,
                    "editor_name": None,
                }

    # FBタイムスタンプ一覧（diff_highlights）
    fb_rows = conn.execute(
        "SELECT timestamp_mark, category, converted_text, priority FROM feedbacks "
        "WHERE project_id = ? AND timestamp_mark IS NOT NULL AND timestamp_mark != '' "
        "ORDER BY timestamp_mark",
        (project_id,),
    ).fetchall()
    diff_highlights = []
    for fb in fb_rows:
        diff_highlights.append({
            "timestamp": fb["timestamp_mark"],
            "category": fb["category"],
            "text": fb["converted_text"] or "",
            "priority": fb["priority"],
        })

    conn.close()

    return {
        "project_id": project_id,
        "guest_name": proj["guest_name"],
        "title": proj["title"],
        "source_videos": source_videos,
        "edited_video": edited_video,
        "fb_revised_video": fb_revised_video,
        "all_versions": all_versions,
        "diff_highlights": diff_highlights,
    }


# --- FB指示トラッカー ---

@app.get("/api/v1/projects/{project_id}/fb-tracker")
def get_fb_tracker(project_id: str):
    """Vimeoレビューコメント（=AI変換済みFB指示）に対応ステータスを付与して返す。"""
    import urllib.request

    conn = _get_db()
    proj = conn.execute("SELECT id, edited_video FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not proj:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    # 全バージョンのvimeo_idを取得
    versions = conn.execute(
        "SELECT vimeo_id, version_label, version_order FROM video_versions "
        "WHERE project_id = ? ORDER BY version_order ASC",
        (project_id,),
    ).fetchall()

    vimeo_ids = []
    if versions:
        for v in versions:
            if v["vimeo_id"]:
                vimeo_ids.append({"vimeo_id": v["vimeo_id"], "label": v["version_label"], "order": v["version_order"]})
    else:
        ev = proj["edited_video"] or ""
        m = re.search(r"vimeo\.com/(\d+)", ev)
        if m:
            vimeo_ids.append({"vimeo_id": m.group(1), "label": "最新", "order": 0})

    if not vimeo_ids:
        conn.close()
        return {"project_id": project_id, "items": [], "summary": {"total": 0, "resolved": 0, "pending": 0}}

    # Vimeoトークン取得
    token = os.environ.get("VIMEO_ACCESS_TOKEN", "")
    if not token:
        api_keys_path = Path.home() / ".config" / "maekawa" / "api-keys.env"
        if api_keys_path.exists():
            for line in api_keys_path.read_text().splitlines():
                if line.startswith("VIMEO_ACCESS_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not token:
        conn.close()
        return {"project_id": project_id, "items": [], "message": "VIMEO_ACCESS_TOKENが未設定です"}

    # 既存のトラッキングステータスをDB取得
    tracking_rows = conn.execute(
        "SELECT comment_uri, status, updated_at FROM fb_tracking WHERE project_id = ?",
        (project_id,),
    ).fetchall()
    tracking_map = {r["comment_uri"]: {"status": r["status"], "updated_at": r["updated_at"]} for r in tracking_rows}

    # Vimeoコメント取得＋ステータスマージ
    items = []
    for vid_info in vimeo_ids:
        vid = vid_info["vimeo_id"]
        label = vid_info["label"]
        url = f"https://api.vimeo.com/videos/{vid}/comments?per_page=100"
        try:
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for c in data.get("data", []):
                    uri = c.get("uri", "")
                    text = c.get("text", "")
                    timecode = None
                    tc_match = re.search(r"\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?", text)
                    if tc_match:
                        timecode = tc_match.group(1)

                    tracking = tracking_map.get(uri, {})
                    status = tracking.get("status", "pending")

                    # 新規コメントはDBに自動登録
                    if uri and uri not in tracking_map:
                        try:
                            conn.execute(
                                "INSERT OR IGNORE INTO fb_tracking (project_id, comment_uri, status) VALUES (?, ?, 'pending')",
                                (project_id, uri),
                            )
                        except Exception:
                            pass

                    items.append({
                        "uri": uri,
                        "vimeo_id": vid,
                        "version_label": label,
                        "text": text,
                        "timecode": timecode,
                        "created_time": c.get("created_time", ""),
                        "user": c.get("user", {}).get("name", ""),
                        "status": status,
                    })
        except Exception as e:
            items.append({
                "uri": "",
                "vimeo_id": vid,
                "version_label": label,
                "text": f"取得エラー: {str(e)}",
                "timecode": None,
                "created_time": "",
                "user": "system",
                "status": "error",
            })

    conn.commit()
    conn.close()

    resolved = sum(1 for i in items if i["status"] == "resolved")
    return {
        "project_id": project_id,
        "items": items,
        "summary": {
            "total": len(items),
            "resolved": resolved,
            "pending": len(items) - resolved,
        },
    }


class FBTrackingUpdate(BaseModel):
    status: str  # "pending" | "resolved"


@app.patch("/api/v1/projects/{project_id}/fb-tracker/{comment_uri:path}")
def update_fb_tracking(project_id: str, comment_uri: str, body: FBTrackingUpdate):
    """FB指示の対応ステータスを更新する。"""
    if body.status not in ("pending", "resolved"):
        raise HTTPException(status_code=400, detail="statusは 'pending' または 'resolved' のみ")

    conn = _get_db()
    # UPSERT
    conn.execute(
        "INSERT INTO fb_tracking (project_id, comment_uri, status, updated_at) "
        "VALUES (?, ?, ?, datetime('now')) "
        "ON CONFLICT(project_id, comment_uri) DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at",
        (project_id, comment_uri, body.status),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "comment_uri": comment_uri, "status": body.status}


# --- 文字起こしdiff可視化 ---

KNOWLEDGE_VIDEO_DIR = Path.home() / "TEKO" / "knowledge" / "01_teko" / "sources" / "video"


def _fuzzy_match(highlight_text: str, transcript_line: str) -> bool:
    """ハイライトテキストとトランスクリプト行の部分一致判定。
    完全包含 / 先頭末尾20文字 / 4-gramオーバーラップ（閾値0.3）でマッチ。
    """
    # 完全包含チェック
    if highlight_text in transcript_line or transcript_line in highlight_text:
        return True
    # 短いテキストは完全包含のみ
    if len(highlight_text) < 15 or len(transcript_line) < 15:
        return False
    # 記号除去
    _clean_re = re.compile(r'[「」『』【】（）\(\)、。！？!?\s>*\-:：\n]+')
    hl_clean = _clean_re.sub('', highlight_text)
    line_clean = _clean_re.sub('', transcript_line)
    # 先頭・末尾20文字の部分一致
    if len(hl_clean) >= 20:
        if hl_clean[:20] in line_clean or hl_clean[-20:] in line_clean:
            return True
    if len(line_clean) >= 20:
        if line_clean[:20] in hl_clean or line_clean[-20:] in hl_clean:
            return True
    # 4-gramオーバーラップ（日本語対応のファジーマッチ）
    if len(hl_clean) >= 4 and len(line_clean) >= 4:
        hl_ngrams = set(hl_clean[i:i+4] for i in range(len(hl_clean)-3))
        line_ngrams = set(line_clean[i:i+4] for i in range(len(line_clean)-3))
        overlap = len(hl_ngrams & line_ngrams)
        smaller = min(len(hl_ngrams), len(line_ngrams))
        if smaller > 0 and overlap / smaller >= 0.2:
            return True
    return False


def _load_transcript(guest_name: str, shoot_date: Optional[str] = None) -> Optional[str]:
    """ナレッジファイルから文字起こし全文を読み込む。
    「整形済みトランスクリプト（全文）」セクション以降のみ返す（メタデータ除外）。
    """
    if not KNOWLEDGE_VIDEO_DIR.exists():
        return None

    normalized = _normalize_name(guest_name)
    if not normalized:
        return None

    shoot_compact = shoot_date.replace("-", "").replace("/", "") if shoot_date else None

    best = None
    best_with_date = None

    for f in sorted(KNOWLEDGE_VIDEO_DIR.glob("*.md"), reverse=True):
        fname_norm = unicodedata.normalize("NFKC", f.name.lower())
        if normalized not in fname_norm:
            continue
        if shoot_compact and shoot_compact in fname_norm:
            best_with_date = f
            break
        if best is None:
            best = f

    target = best_with_date or best
    if target:
        try:
            full_text = target.read_text(encoding="utf-8")
            # メタデータを除外し、トランスクリプト本文のみ抽出
            marker = "## 整形済みトランスクリプト（全文）"
            idx = full_text.find(marker)
            if idx >= 0:
                return full_text[idx + len(marker):]
            return full_text
        except Exception:
            return None
    return None


def _fetch_vimeo_captions(vimeo_id: str) -> Optional[str]:
    """Vimeo APIから自動生成字幕（VTT）を取得し、テキスト部分のみ結合して返す。"""
    import urllib.request
    token = os.environ.get("VIMEO_ACCESS_TOKEN", "")
    if not token:
        api_keys_path = Path.home() / ".config" / "maekawa" / "api-keys.env"
        if api_keys_path.exists():
            for line in api_keys_path.read_text().splitlines():
                if line.startswith("VIMEO_ACCESS_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not token:
        return None

    try:
        # テキストトラック一覧を取得
        url = f"https://api.vimeo.com/videos/{vimeo_id}/texttracks"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        tracks = data.get("data", [])
        if not tracks:
            return None

        # 日本語トラックを優先、なければ最初のトラック
        ja_track = None
        for t in tracks:
            lang = (t.get("language") or "").lower()
            if "ja" in lang:
                ja_track = t
                break
        track = ja_track or tracks[0]
        vtt_url = track.get("link")
        if not vtt_url:
            return None

        # VTTファイルをダウンロード
        req2 = urllib.request.Request(vtt_url)
        with urllib.request.urlopen(req2, timeout=30) as resp2:
            vtt_text = resp2.read().decode("utf-8")

        # VTTからテキスト行だけ抽出（タイムスタンプ・番号・空行を除去）
        caption_lines = []
        _ts_re = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->")
        for line in vtt_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line == "WEBVTT":
                continue
            if line.isdigit():
                continue
            if _ts_re.match(line):
                continue
            # VTTのスペース区切りを除去して連結
            cleaned = re.sub(r'\s+', '', line)
            if cleaned:
                caption_lines.append(cleaned)

        return "".join(caption_lines) if caption_lines else None
    except Exception:
        return None


def _match_caption_to_transcript(caption_text: str, transcript_line: str) -> bool:
    """Vimeo字幕テキスト（連結済み）に素材文字起こしの行が含まれるかファジー判定。
    記号除去後の4-gramオーバーラップで照合。
    """
    _clean_re = re.compile(r'[「」『』【】（）\(\)、。！？!?\s>*\-:：\n\*]+')
    line_clean = _clean_re.sub('', transcript_line)
    if len(line_clean) < 4:
        return False

    # 話者名プレフィックスを除去（**インタビュアー**: 等）
    speaker_re = re.compile(r'^\*?\*?[^:：*]+\*?\*?\s*[:：]\s*')
    line_clean = speaker_re.sub('', line_clean)
    line_clean = _clean_re.sub('', line_clean)
    if len(line_clean) < 4:
        return False

    # 完全包含チェック
    if line_clean in caption_text:
        return True

    # 先頭・末尾の部分一致
    check_len = min(15, len(line_clean))
    if check_len >= 6:
        if line_clean[:check_len] in caption_text or line_clean[-check_len:] in caption_text:
            return True

    # 4-gramオーバーラップ
    if len(line_clean) >= 4:
        line_ngrams = set(line_clean[i:i+4] for i in range(len(line_clean)-3))
        # caption_textが巨大なので、行周辺のウィンドウで比較
        # line_cleanの各4-gramがcaption_textに含まれるか直接チェック
        hit = sum(1 for ng in line_ngrams if ng in caption_text)
        if len(line_ngrams) > 0 and hit / len(line_ngrams) >= 0.4:
            return True

    return False


@app.get("/api/v1/projects/{project_id}/transcript-diff")
def get_transcript_diff(project_id: str, version: Optional[str] = None):
    """素材の文字起こし全文と編集後動画（Vimeo字幕）を照合し、カット/採用の差分を返す。
    version: 比較対象のバージョン（指定なし=最新版）
    """
    conn = _get_db()

    proj = conn.execute(
        "SELECT id, guest_name, shoot_date, edited_video FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()
    if not proj:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    guest_name = proj["guest_name"]
    shoot_date = proj["shoot_date"]

    # 素材の文字起こし全文を読み込み
    transcript_text = _load_transcript(guest_name, shoot_date)
    if not transcript_text:
        conn.close()
        return {
            "project_id": project_id,
            "status": "no_transcript",
            "message": f"ゲスト '{guest_name}' の文字起こしファイルが見つかりません",
            "segments": [],
        }

    # 比較対象のVimeo動画IDを取得
    if version:
        ver_row = conn.execute(
            "SELECT vimeo_id, version_label FROM video_versions "
            "WHERE project_id = ? AND version_label = ?",
            (project_id, version),
        ).fetchone()
    else:
        # 最新版を取得
        ver_row = conn.execute(
            "SELECT vimeo_id, version_label FROM video_versions "
            "WHERE project_id = ? ORDER BY version_order DESC LIMIT 1",
            (project_id,),
        ).fetchone()

    compare_vimeo_id = None
    compare_label = "不明"
    if ver_row and ver_row["vimeo_id"]:
        compare_vimeo_id = str(ver_row["vimeo_id"])
        compare_label = ver_row["version_label"]
    else:
        # video_versionsにない場合、edited_videoからフォールバック
        ev = proj["edited_video"] or ""
        m = re.search(r"vimeo\.com/(\d+)", ev)
        if m:
            compare_vimeo_id = m.group(1)
            compare_label = "最新"

    conn.close()

    # Vimeo字幕を取得
    caption_text = None
    caption_status = "no_captions"
    if compare_vimeo_id:
        caption_text = _fetch_vimeo_captions(compare_vimeo_id)
        if caption_text:
            caption_status = "ok"
            # 記号除去した連結テキスト
            _clean_re = re.compile(r'[「」『』【】（）\(\)、。！？!?\s>*\-:：\n\*]+')
            caption_clean = _clean_re.sub('', caption_text)
        else:
            caption_status = "no_captions"
    else:
        caption_status = "no_video"

    # 文字起こしを行単位でセグメント化
    lines = transcript_text.split("\n")
    segments = []
    _skip_re = re.compile(r"^(#{1,6}\s|---$)")

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if _skip_re.match(stripped):
            continue

        if caption_text and caption_status == "ok":
            # Vimeo字幕との照合
            if _match_caption_to_transcript(caption_clean, stripped):
                status = "used"
            else:
                status = "unused"
        else:
            # 字幕取得できない場合は全部unknown
            status = "unknown"

        segments.append({
            "line_number": i + 1,
            "text": stripped,
            "status": status,
        })

    # 統計
    total = len(segments)
    used_count = sum(1 for s in segments if s["status"] == "used")
    unused_count = sum(1 for s in segments if s["status"] == "unused")

    return {
        "project_id": project_id,
        "status": "ok",
        "caption_status": caption_status,
        "compare_version": compare_label,
        "compare_vimeo_id": compare_vimeo_id,
        "total_segments": total,
        "used_count": used_count,
        "unused_count": unused_count,
        "used_ratio": f"{used_count/total*100:.1f}%" if total > 0 else "0%",
        "segments": segments,
    }


# --- feedbacks-with-timecodes (レビュータブ用) ---

@app.get("/api/v1/projects/{project_id}/feedbacks-with-timecodes")
def get_feedbacks_with_timecodes(project_id: str):
    """レビュータブ用: タイムコード付きフィードバック一覧を返す。"""
    conn = _get_db()

    proj = conn.execute(
        "SELECT id, edited_video FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if not proj:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    # 最新バージョンのvimeo_idを取得
    vimeo_id = ""
    latest_ver = conn.execute(
        "SELECT vimeo_id FROM video_versions WHERE project_id = ? "
        "ORDER BY version_order DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    if latest_ver and latest_ver["vimeo_id"]:
        vimeo_id = latest_ver["vimeo_id"]
    else:
        # フォールバック: projects.edited_video
        ev = proj["edited_video"] or ""
        m = re.search(r"vimeo\.com/(\d+)", ev)
        if m:
            vimeo_id = m.group(1)

    # feedbacksからタイムコード付きのものを取得
    fb_rows = conn.execute(
        "SELECT id, timestamp_mark, converted_text, raw_voice_text, category, priority "
        "FROM feedbacks "
        "WHERE project_id = ? AND timestamp_mark IS NOT NULL AND timestamp_mark != '' "
        "ORDER BY timestamp_mark",
        (project_id,),
    ).fetchall()
    conn.close()

    import uuid as _uuid
    results = []
    for fb in fb_rows:
        ts_str = fb["timestamp_mark"] or "0:00"
        # タイムコード → 秒変換
        seconds = _parse_timecode_to_seconds(ts_str)
        note = fb["converted_text"] or fb["raw_voice_text"] or ""
        category = fb["category"] or "その他"
        priority = fb["priority"] or "medium"

        results.append({
            "id": str(_uuid.uuid4()),
            "timestampMark": seconds,
            "element": category,
            "priorityRaw": priority,
            "note": note,
            "vimeoVideoId": vimeo_id,
        })

    return results


def _parse_timecode_to_seconds(tc: str) -> float:
    """タイムコード文字列を秒数に変換。 '1:23', '01:23:45', '90' 等に対応。"""
    tc = tc.strip()
    parts = tc.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        else:
            return float(tc)
    except (ValueError, IndexError):
        return 0.0


# --- feedbacks CRUD (FB・評価タブ用) ---

@app.put("/api/v1/feedbacks/{feedback_id}/converted-text")
def update_feedback_converted_text(feedback_id: int, body: dict):
    """FB・評価タブ: converted_text（変換後テキスト）を直接編集する。"""
    new_text = body.get("converted_text", "")
    if not new_text:
        raise HTTPException(status_code=400, detail="converted_text is required")

    conn = _get_db()
    existing = conn.execute("SELECT id FROM feedbacks WHERE id = ?", (feedback_id,)).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Feedback not found")

    conn.execute(
        "UPDATE feedbacks SET converted_text = ? WHERE id = ?",
        (new_text, feedback_id),
    )
    conn.commit()
    conn.close()

    return {"status": "ok", "feedback_id": feedback_id, "converted_text": new_text}


# --- Vimeoコメント編集（PATCH） ---

@app.patch("/api/v1/vimeo/comments/{comment_id}")
def edit_vimeo_comment(comment_id: str, body: dict):
    """Vimeoコメントをアプリから編集する。Vimeo APIのPATCHで直接書き換え。
    body: { "video_id": "1234567", "text": "修正後のコメントテキスト" }
    """
    import urllib.request

    video_id = body.get("video_id", "")
    new_text = body.get("text", "")
    if not video_id or not new_text:
        raise HTTPException(status_code=400, detail="video_id と text は必須です")

    # Vimeoトークン取得
    token = os.environ.get("VIMEO_ACCESS_TOKEN", "")
    if not token:
        api_keys_path = Path.home() / ".config" / "maekawa" / "api-keys.env"
        if api_keys_path.exists():
            for line in api_keys_path.read_text().splitlines():
                if line.startswith("VIMEO_ACCESS_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not token:
        raise HTTPException(status_code=500, detail="VIMEO_ACCESS_TOKENが未設定です")

    # Vimeo API: PATCH /videos/{video_id}/comments/{comment_id}
    url = f"https://api.vimeo.com/videos/{video_id}/comments/{comment_id}"
    payload = json.dumps({"text": new_text}).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=payload, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }, method="PATCH")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return {
                "status": "ok",
                "comment_id": comment_id,
                "video_id": video_id,
                "updated_text": result.get("text", new_text),
                "uri": result.get("uri", ""),
            }
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        logger.error("Vimeo APIエラー: %s %s", e.code, error_body[:200])
        raise HTTPException(
            status_code=e.code,
            detail=f"Vimeo APIエラー: {e.code}"
        )
    except Exception as e:
        logger.exception("Vimeoコメント編集エラー")
        raise HTTPException(status_code=500, detail="Internal server error")


# --- タイミング3: 自動QC ---

@app.get("/api/v1/projects/{project_id}/auto-qc")
def get_auto_qc_result(project_id: str):
    """プロジェクトの自動QC結果を取得"""
    from ..qc.qc_comparator import QCResult
    qc_output = Path.home() / "AI開発10" / "output" / "qc_results"
    if not qc_output.exists():
        return {"status": "no_results", "project_id": project_id, "results": []}

    # プロジェクトIDに一致するQC結果ファイルを検索（新しい順）
    results = []
    for f in sorted(qc_output.glob(f"qc_{project_id}_*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append(data)
        except Exception as e:
            logger.warning(f"QC結果ファイルの読み込みエラー: {f}: {e}")

    if not results:
        return {"status": "no_results", "project_id": project_id, "results": []}

    latest = results[0]
    qc_data = latest.get("qc_result", {})
    response = {
        "status": qc_data.get("status", "unknown"),
        "combined_status": qc_data.get("combined_status", qc_data.get("status", "unknown")),
        "project_id": project_id,
        "latest": latest,
        "total_results": len(results),
    }
    # マーケQC結果がある場合はトップレベルにも含める
    if "marketing_qc" in qc_data:
        response["marketing_qc"] = qc_data["marketing_qc"]
    return response


class AutoQCRequest(BaseModel):
    video_path: str
    frame_interval: float = 2.0
    similarity_threshold: float = 0.7
    max_frames: int = 100
    # Phase2: マーケQCオプション
    enable_marketing_qc: bool = True
    direction_report: str = ""
    guest_profile: str = ""
    content_line: Optional[str] = None  # "career" | "realestate" | None（自動判定）


@app.post("/api/v1/projects/{project_id}/auto-qc")
async def run_auto_qc_endpoint(project_id: str, req: AutoQCRequest):
    """プロジェクトの自動QCを実行

    動画ファイルパスを指定してテロップ誤字自動QCパイプラインを起動する。
    処理は同期的に実行され、完了までレスポンスを返さない（30分動画で数分程度）。
    """
    from ..qc.auto_qc_runner import run_auto_qc

    video_path = Path(req.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=400, detail=f"動画ファイルが見つかりません: {req.video_path}")

    try:
        result = run_auto_qc(
            video_path=video_path,
            project_id=project_id,
            frame_interval=req.frame_interval,
            similarity_threshold=req.similarity_threshold,
            max_frames=req.max_frames,
            enable_marketing_qc=req.enable_marketing_qc,
            direction_report=req.direction_report,
            guest_profile=req.guest_profile,
            content_line=req.content_line,
        )
        response = {
            "status": result.status,
            "combined_status": result.combined_status,
            "project_id": project_id,
            "error_count": result.error_count,
            "warning_count": result.warning_count,
            "checked_frames": result.checked_frames,
            "issues": [i.to_dict() for i in result.issues],
        }
        if result.marketing_qc is not None:
            response["marketing_qc"] = result.marketing_qc
        return response
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"自動QCパイプライン実行エラー: {e}")
        raise HTTPException(status_code=500, detail=f"QCパイプライン実行に失敗: {str(e)}")


@app.get("/api/v1/auto-qc/results")
def list_all_qc_results():
    """全QC結果の一覧取得"""
    qc_output = Path.home() / "AI開発10" / "output" / "qc_results"
    if not qc_output.exists():
        return {"results": []}

    results = []
    for f in sorted(qc_output.glob("qc_*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            qc_data = data.get("qc_result", {})
            entry = {
                "file": f.name,
                "project_id": qc_data.get("project_id", ""),
                "status": qc_data.get("status", "unknown"),
                "combined_status": qc_data.get("combined_status", qc_data.get("status", "unknown")),
                "error_count": qc_data.get("error_count", 0),
                "warning_count": qc_data.get("warning_count", 0),
                "executed_at": data.get("executed_at", ""),
            }
            # マーケQCサマリーを含める
            mq = qc_data.get("marketing_qc")
            if mq:
                entry["marketing_qc_status"] = mq.get("status", "unknown")
                entry["marketing_qc_error_count"] = mq.get("error_count", 0)
                entry["marketing_qc_warning_count"] = mq.get("warning_count", 0)
            results.append(entry)
        except Exception as e:
            logger.warning(f"QC結果ファイルの読み込みエラー: {f}: {e}")

    return {"results": results, "total": len(results)}


# --- ヘルスチェック ---

@app.get("/api/health")
def health():
    conn = _get_db()
    try:
        project_count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        assets_count = conn.execute("SELECT COUNT(*) FROM youtube_assets").fetchone()[0]
        feedback_count = conn.execute("SELECT COUNT(*) FROM feedbacks").fetchone()[0]
    finally:
        conn.close()
    return {
        "status": "ok",
        "projects": project_count,
        "youtube_assets": assets_count,
        "feedbacks": feedback_count,
    }


@app.get("/healthz")
def healthz():
    """軽量ヘルスチェック（DB不要）"""
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    """レディネスチェック（DB疎通確認）"""
    try:
        conn = _get_db()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        return {"status": "ok"}
    except Exception:
        logger.exception("readyz: DB疎通失敗")
        raise HTTPException(status_code=503, detail="Database not ready")


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
    # パストラバーサル防止
    base_dir = Path.home() / "AI開発10"
    file_path = (base_dir / filename).resolve()
    if not str(file_path).startswith(str(base_dir.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
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
