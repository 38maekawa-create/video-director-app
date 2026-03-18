"""タイトル・概要欄・サムネイル指示の手修正API

YouTube公開用アセット（タイトル・概要欄・サムネイル指示）に対する
手修正を記録・管理するエンドポイント。
修正履歴はasset_editsテーブルに保存し、差分分析結果も自動付与する。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..analyzer.edit_diff_analyzer import (
    analyze_description_diff,
    analyze_thumbnail_diff,
    analyze_title_diff,
)

# --- DB設定（api_server.pyと同一方式） ---

DB_PATH = Path.home() / "AI開発10" / ".data" / "video_director.db"

router = APIRouter()


def _get_db() -> sqlite3.Connection:
    """DB接続を取得する。api_server.pyと同一方式。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_asset_edits_table():
    """asset_editsテーブルを作成する（冪等）。"""
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS asset_edits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL REFERENCES projects(id),
            asset_type TEXT NOT NULL CHECK(asset_type IN ('title', 'description', 'thumbnail')),
            original_content TEXT,
            edited_content TEXT NOT NULL,
            edited_by TEXT NOT NULL,
            diff_summary TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


# モジュールインポート時にテーブル作成
_init_asset_edits_table()


# --- リクエスト/レスポンスモデル ---

class AssetEditRequest(BaseModel):
    edited_content: str
    edited_by: str


class AssetEditResponse(BaseModel):
    id: int
    project_id: str
    asset_type: str
    edited_by: str
    diff_summary: Optional[str]
    created_at: str


class AssetEditHistoryItem(BaseModel):
    id: int
    project_id: str
    asset_type: str
    original_content: Optional[str]
    edited_content: str
    edited_by: str
    diff_summary: Optional[str]
    created_at: str


class AssetDiffResponse(BaseModel):
    project_id: str
    asset_type: str
    original_content: Optional[str]
    edited_content: Optional[str]
    total_changes: int
    categories_affected: list[str]
    severity: str
    learning_signal: str
    changes: list[dict]


# --- アセットタイプ別の分析関数マッピング ---

_ANALYZE_FN = {
    "title": analyze_title_diff,
    "description": analyze_description_diff,
    "thumbnail": analyze_thumbnail_diff,
}


# --- ヘルパー ---

def _get_original_asset(
    project_id: str, asset_type: str, conn: sqlite3.Connection
) -> Optional[str]:
    """youtube_assetsテーブルからオリジナルのアセット内容を取得する。"""
    row = conn.execute(
        "SELECT * FROM youtube_assets WHERE project_id = ?", (project_id,)
    ).fetchone()
    if not row:
        return None

    if asset_type == "title":
        # edited_titleがあればそれ、なければtitle_proposalsの最初
        if row["edited_title"]:
            return row["edited_title"]
        if row["title_proposals"]:
            try:
                proposals = json.loads(row["title_proposals"])
                if isinstance(proposals, list) and proposals:
                    idx = row["selected_title_index"] or 0
                    if 0 <= idx < len(proposals):
                        prop = proposals[idx]
                        return prop if isinstance(prop, str) else prop.get("title", str(prop))
            except (json.JSONDecodeError, TypeError):
                pass
        return None

    elif asset_type == "description":
        return row["description_edited"] or row["description_original"]

    elif asset_type == "thumbnail":
        if row["thumbnail_design"]:
            try:
                design = json.loads(row["thumbnail_design"])
                return json.dumps(design, ensure_ascii=False, indent=2) if isinstance(design, dict) else str(design)
            except (json.JSONDecodeError, TypeError):
                return str(row["thumbnail_design"])
        return None

    return None


def _put_asset(project_id: str, asset_type: str, req: AssetEditRequest) -> AssetEditResponse:
    """アセットの手修正を保存する共通処理。"""
    conn = _get_db()
    try:
        # プロジェクト存在確認
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if not project:
            raise HTTPException(status_code=404, detail=f"プロジェクト {project_id} が見つかりません")

        # オリジナルコンテンツを取得
        original = _get_original_asset(project_id, asset_type, conn)

        # 直前の編集があればそれを比較ベースにする
        last_edit = conn.execute(
            """SELECT edited_content FROM asset_edits
               WHERE project_id = ? AND asset_type = ?
               ORDER BY id DESC LIMIT 1""",
            (project_id, asset_type),
        ).fetchone()
        compare_base = last_edit["edited_content"] if last_edit else original

        # diff分析
        diff_summary = None
        analyze_fn = _ANALYZE_FN[asset_type]
        if compare_base:
            result = analyze_fn(compare_base, req.edited_content)
            diff_summary = json.dumps({
                "total_changes": result.total_changes,
                "categories_affected": result.categories_affected,
                "severity": result.severity,
                "learning_signal": result.learning_signal,
            }, ensure_ascii=False)

        # 保存
        cursor = conn.execute(
            """INSERT INTO asset_edits
               (project_id, asset_type, original_content, edited_content, edited_by, diff_summary)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (project_id, asset_type, original, req.edited_content, req.edited_by, diff_summary),
        )
        conn.commit()

        # --- EditLearnerに手修正を蓄積（自己学習ループ） ---
        if compare_base and compare_base != req.edited_content:
            try:
                from ..tracker.edit_learner import EditLearner
                diff_result = analyze_fn(compare_base, req.edited_content)
                diff_result.edit_id = f"{asset_type}_{project_id}_{cursor.lastrowid}"
                edit_learner = EditLearner()
                edit_learner.ingest_edit(
                    project_id=project_id,
                    asset_type=asset_type,
                    diff_result=diff_result,
                )
            except Exception:
                pass  # 学習失敗は修正保存には影響させない

        return AssetEditResponse(
            id=cursor.lastrowid,  # type: ignore[arg-type]
            project_id=project_id,
            asset_type=asset_type,
            edited_by=req.edited_by,
            diff_summary=diff_summary,
            created_at=datetime.utcnow().isoformat(),
        )
    finally:
        conn.close()


def _get_history(project_id: str, asset_type: str) -> list[AssetEditHistoryItem]:
    """アセットの全編集履歴を返す共通処理。"""
    conn = _get_db()
    try:
        rows = conn.execute(
            """SELECT id, project_id, asset_type, original_content, edited_content,
                      edited_by, diff_summary, created_at
               FROM asset_edits
               WHERE project_id = ? AND asset_type = ?
               ORDER BY id DESC""",
            (project_id, asset_type),
        ).fetchall()

        return [
            AssetEditHistoryItem(
                id=r["id"],
                project_id=r["project_id"],
                asset_type=r["asset_type"],
                original_content=r["original_content"],
                edited_content=r["edited_content"],
                edited_by=r["edited_by"],
                diff_summary=r["diff_summary"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
    finally:
        conn.close()


def _get_diff(project_id: str, asset_type: str) -> AssetDiffResponse:
    """最新の編集とオリジナルのdiffを返す共通処理。"""
    conn = _get_db()
    try:
        latest = conn.execute(
            """SELECT original_content, edited_content
               FROM asset_edits
               WHERE project_id = ? AND asset_type = ?
               ORDER BY id DESC LIMIT 1""",
            (project_id, asset_type),
        ).fetchone()

        if not latest:
            raise HTTPException(
                status_code=404,
                detail=f"プロジェクト {project_id} の{asset_type}編集履歴がありません",
            )

        original = latest["original_content"] or ""
        edited = latest["edited_content"]

        analyze_fn = _ANALYZE_FN[asset_type]
        result = analyze_fn(original, edited)

        return AssetDiffResponse(
            project_id=project_id,
            asset_type=asset_type,
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


# --- タイトル エンドポイント ---

@router.put(
    "/api/v1/projects/{project_id}/title",
    response_model=AssetEditResponse,
)
def update_title(project_id: str, req: AssetEditRequest):
    """タイトルの手修正を保存する。"""
    return _put_asset(project_id, "title", req)


@router.get(
    "/api/v1/projects/{project_id}/title/history",
    response_model=list[AssetEditHistoryItem],
)
def get_title_history(project_id: str):
    """タイトルの全編集履歴を返す（新しい順）。"""
    return _get_history(project_id, "title")


@router.get(
    "/api/v1/projects/{project_id}/title/diff",
    response_model=AssetDiffResponse,
)
def get_title_diff(project_id: str):
    """タイトルの最新編集とオリジナルのdiffを返す。"""
    return _get_diff(project_id, "title")


# --- 概要欄 エンドポイント ---

@router.put(
    "/api/v1/projects/{project_id}/description",
    response_model=AssetEditResponse,
)
def update_description(project_id: str, req: AssetEditRequest):
    """概要欄の手修正を保存する。"""
    return _put_asset(project_id, "description", req)


@router.get(
    "/api/v1/projects/{project_id}/description/history",
    response_model=list[AssetEditHistoryItem],
)
def get_description_history(project_id: str):
    """概要欄の全編集履歴を返す（新しい順）。"""
    return _get_history(project_id, "description")


@router.get(
    "/api/v1/projects/{project_id}/description/diff",
    response_model=AssetDiffResponse,
)
def get_description_diff(project_id: str):
    """概要欄の最新編集とオリジナルのdiffを返す。"""
    return _get_diff(project_id, "description")


# --- サムネイル指示 エンドポイント ---

@router.put(
    "/api/v1/projects/{project_id}/thumbnail-instruction",
    response_model=AssetEditResponse,
)
def update_thumbnail_instruction(project_id: str, req: AssetEditRequest):
    """サムネイル指示の手修正を保存する。"""
    return _put_asset(project_id, "thumbnail", req)


@router.get(
    "/api/v1/projects/{project_id}/thumbnail-instruction/history",
    response_model=list[AssetEditHistoryItem],
)
def get_thumbnail_history(project_id: str):
    """サムネイル指示の全編集履歴を返す（新しい順）。"""
    return _get_history(project_id, "thumbnail")


@router.get(
    "/api/v1/projects/{project_id}/thumbnail-instruction/diff",
    response_model=AssetDiffResponse,
)
def get_thumbnail_diff(project_id: str):
    """サムネイル指示の最新編集とオリジナルのdiffを返す。"""
    return _get_diff(project_id, "thumbnail")
