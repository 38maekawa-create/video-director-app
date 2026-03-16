"""ディレクションレポート手修正API

プロジェクトのディレクションレポートに対する手修正を記録・管理するエンドポイント。
修正履歴はdirection_editsテーブルに保存し、差分分析結果も自動付与する。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..analyzer.edit_diff_analyzer import analyze_direction_diff

# --- DB設定（api_server.pyと同一方式） ---

DB_PATH = Path.home() / "AI開発10" / ".data" / "video_director.db"

router = APIRouter()


def _get_db() -> sqlite3.Connection:
    """DB接続を取得する。api_server.pyと同一方式。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_direction_edits_table():
    """direction_editsテーブルを作成する（冪等）。"""
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS direction_edits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL REFERENCES projects(id),
            original_content TEXT,
            edited_content TEXT NOT NULL,
            edited_by TEXT NOT NULL,
            edit_notes TEXT,
            diff_summary TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


# モジュールインポート時にテーブル作成
_init_direction_edits_table()


# --- リクエスト/レスポンスモデル ---

class DirectionEditRequest(BaseModel):
    edited_content: str
    edited_by: str
    edit_notes: Optional[str] = None


class DirectionEditResponse(BaseModel):
    id: int
    project_id: str
    edited_by: str
    edit_notes: Optional[str]
    diff_summary: Optional[str]
    created_at: str


class DirectionEditHistoryItem(BaseModel):
    id: int
    project_id: str
    original_content: Optional[str]
    edited_content: str
    edited_by: str
    edit_notes: Optional[str]
    diff_summary: Optional[str]
    created_at: str


class DirectionDiffResponse(BaseModel):
    project_id: str
    original_content: Optional[str]
    edited_content: Optional[str]
    total_changes: int
    categories_affected: list[str]
    severity: str
    learning_signal: str
    changes: list[dict]


# --- ヘルパー ---

def _get_original_direction(project_id: str, conn: sqlite3.Connection) -> Optional[str]:
    """プロジェクトのオリジナルディレクションレポートを取得する。

    projects.knowledgeのJSON内からdirection_report相当の情報を抽出する。
    """
    row = conn.execute(
        "SELECT knowledge FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if not row or not row["knowledge"]:
        return None

    try:
        knowledge = json.loads(row["knowledge"])
    except (json.JSONDecodeError, TypeError):
        return None

    # knowledgeの中からディレクションレポート関連のテキストを抽出
    # direction_report キーがあればそれを使用
    if isinstance(knowledge, dict):
        for key in ("direction_report", "direction", "report"):
            if key in knowledge:
                val = knowledge[key]
                return val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)
        # 見つからなければknowledge全体をテキスト化
        return json.dumps(knowledge, ensure_ascii=False, indent=2)

    return str(knowledge)


# --- エンドポイント ---

@router.put(
    "/api/v1/projects/{project_id}/direction-report",
    response_model=DirectionEditResponse,
)
def update_direction_report(project_id: str, req: DirectionEditRequest):
    """ディレクションレポートの手修正を保存する。"""
    conn = _get_db()
    try:
        # プロジェクト存在確認
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if not project:
            raise HTTPException(status_code=404, detail=f"プロジェクト {project_id} が見つかりません")

        # オリジナルコンテンツを取得
        original = _get_original_direction(project_id, conn)

        # 直前の編集があればそれをオリジナルとして使用
        last_edit = conn.execute(
            "SELECT edited_content FROM direction_edits WHERE project_id = ? ORDER BY id DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        compare_base = last_edit["edited_content"] if last_edit else original

        # diff分析
        diff_summary = None
        if compare_base:
            result = analyze_direction_diff(compare_base, req.edited_content)
            diff_summary = json.dumps({
                "total_changes": result.total_changes,
                "categories_affected": result.categories_affected,
                "severity": result.severity,
                "learning_signal": result.learning_signal,
            }, ensure_ascii=False)

        # 保存
        cursor = conn.execute(
            """INSERT INTO direction_edits
               (project_id, original_content, edited_content, edited_by, edit_notes, diff_summary)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (project_id, original, req.edited_content, req.edited_by, req.edit_notes, diff_summary),
        )
        conn.commit()

        return DirectionEditResponse(
            id=cursor.lastrowid,  # type: ignore[arg-type]
            project_id=project_id,
            edited_by=req.edited_by,
            edit_notes=req.edit_notes,
            diff_summary=diff_summary,
            created_at=datetime.utcnow().isoformat(),
        )
    finally:
        conn.close()


@router.get(
    "/api/v1/projects/{project_id}/direction-report/history",
    response_model=list[DirectionEditHistoryItem],
)
def get_direction_edit_history(project_id: str):
    """ディレクションレポートの全編集履歴を返す（新しい順）。"""
    conn = _get_db()
    try:
        rows = conn.execute(
            """SELECT id, project_id, original_content, edited_content,
                      edited_by, edit_notes, diff_summary, created_at
               FROM direction_edits
               WHERE project_id = ?
               ORDER BY id DESC""",
            (project_id,),
        ).fetchall()

        return [
            DirectionEditHistoryItem(
                id=r["id"],
                project_id=r["project_id"],
                original_content=r["original_content"],
                edited_content=r["edited_content"],
                edited_by=r["edited_by"],
                edit_notes=r["edit_notes"],
                diff_summary=r["diff_summary"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
    finally:
        conn.close()


@router.get(
    "/api/v1/projects/{project_id}/direction-report/diff",
    response_model=DirectionDiffResponse,
)
def get_direction_diff(project_id: str):
    """最新の編集とオリジナルのdiffを返す。"""
    conn = _get_db()
    try:
        # 最新の編集を取得
        latest = conn.execute(
            """SELECT original_content, edited_content
               FROM direction_edits
               WHERE project_id = ?
               ORDER BY id DESC LIMIT 1""",
            (project_id,),
        ).fetchone()

        if not latest:
            raise HTTPException(
                status_code=404,
                detail=f"プロジェクト {project_id} の編集履歴がありません",
            )

        original = latest["original_content"] or ""
        edited = latest["edited_content"]

        result = analyze_direction_diff(original, edited)

        return DirectionDiffResponse(
            project_id=project_id,
            original_content=original,
            edited_content=edited,
            total_changes=result.total_changes,
            categories_affected=result.categories_affected,
            severity=result.severity,
            learning_signal=result.learning_signal,
            changes=[
                {
                    "change_type": c.change_type,
                    "original_text": c.original_text,
                    "edited_text": c.edited_text,
                    "category": c.category,
                }
                for c in result.changes
            ],
        )
    finally:
        conn.close()
