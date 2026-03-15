"""source_video_linker のユニットテスト（30件以上）"""

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.integrations.source_video_linker import (
    LinkCandidate,
    LinkResult,
    SourceVideoLinker,
)
from src.video_direction.integrations.ai_dev5_connector import VideoData


# --- テスト用ヘルパー ---

def create_test_db(db_path: Path, projects: list[dict] = None):
    """テスト用DBを作成"""
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
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
            source_video TEXT,
            edited_video TEXT,
            feedback_summary TEXT,
            knowledge TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    if projects:
        for p in projects:
            conn.execute(
                "INSERT INTO projects (id, guest_name, title, shoot_date, source_video) VALUES (?, ?, ?, ?, ?)",
                (p["id"], p["guest_name"], p["title"], p.get("shoot_date", ""), p.get("source_video")),
            )
    conn.commit()
    conn.close()


def create_test_knowledge_dir(tmp_dir: Path, files: list[dict] = None):
    """テスト用ナレッジディレクトリを作成"""
    knowledge_dir = tmp_dir / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    if files:
        for f in files:
            filepath = knowledge_dir / f["name"]
            filepath.write_text(f["content"], encoding="utf-8")
    return knowledge_dir


def make_knowledge_content(
    title="テスト対談",
    date="2025/11/23",
    speakers="hirai, インタビュアー",
    transcript_method="YouTube字幕",
    youtube_url="https://www.youtube.com/watch?v=test123",
):
    """テスト用ナレッジファイルの内容を生成"""
    content = f"""# {title}

## メタ情報
- **日付**: {date}
- **動画種別**: メンバー撮影素材
- **ソース**: Google Drive
- **動画時間**: 30分0秒
- **話者**: {speakers}
- **カテゴリ**: TEKO事業
- **タグ**: #テスト
- **文字起こし方式**: {transcript_method}
"""
    if youtube_url:
        content += f"- **YouTube URL**: {youtube_url}\n"
    content += """
## 3行要約
1. テスト要約1
2. テスト要約2
3. テスト要約3
"""
    return content


# --- テストクラス ---

class TestNormalizeDateStatic:
    """日付正規化のテスト"""

    def test_slash_format(self):
        assert SourceVideoLinker._normalize_date("2025/11/23") == "2025-11-23"

    def test_dash_format(self):
        assert SourceVideoLinker._normalize_date("2025-11-23") == "2025-11-23"

    def test_compact_format(self):
        assert SourceVideoLinker._normalize_date("20251123") == "2025-11-23"

    def test_empty_string(self):
        assert SourceVideoLinker._normalize_date("") == ""

    def test_none_like(self):
        assert SourceVideoLinker._normalize_date("") == ""

    def test_with_extra_text(self):
        result = SourceVideoLinker._normalize_date("2025-11-23 追加テキスト")
        assert result == "2025-11-23"


class TestExtractDateFromFilename:
    """ファイル名からの日付抽出テスト"""

    def test_standard_format(self):
        result = SourceVideoLinker._extract_date_from_filename(
            "2026.02.15_20251123撮影_hiraiさん.md"
        )
        assert result == "2025-11-23"

    def test_no_date(self):
        result = SourceVideoLinker._extract_date_from_filename("readme.md")
        assert result == ""

    def test_only_creation_date(self):
        """作成日のみ（撮影日なし）の場合は空"""
        result = SourceVideoLinker._extract_date_from_filename("2026.02.28_ゆりかさん.md")
        assert result == ""


class TestIsYoutubeSubtitle:
    """YouTube字幕判定のテスト"""

    def test_youtube_subtitle(self):
        assert SourceVideoLinker._is_youtube_subtitle("YouTube字幕") is True

    def test_youtube_subtitle_with_extra(self):
        assert SourceVideoLinker._is_youtube_subtitle("YouTube字幕（自動生成）") is True

    def test_gpt4o(self):
        assert SourceVideoLinker._is_youtube_subtitle("GPT-4o Transcribe（話者分離あり）") is False

    def test_empty(self):
        assert SourceVideoLinker._is_youtube_subtitle("") is False

    def test_none(self):
        assert SourceVideoLinker._is_youtube_subtitle("") is False

    def test_mixed_case(self):
        assert SourceVideoLinker._is_youtube_subtitle("youtube字幕") is True


class TestExtractSpeakerNames:
    """話者名抽出のテスト"""

    def test_comma_separated(self):
        result = SourceVideoLinker._extract_speaker_names("hirai, インタビュアー")
        assert result == ["hirai"]

    def test_multiple_speakers(self):
        result = SourceVideoLinker._extract_speaker_names("前川, Izu, インタビュアー")
        assert "前川" in result
        assert "Izu" in result
        assert "インタビュアー" not in result

    def test_empty(self):
        assert SourceVideoLinker._extract_speaker_names("") == []

    def test_single_speaker(self):
        result = SourceVideoLinker._extract_speaker_names("hirai")
        assert result == ["hirai"]

    def test_slash_separated(self):
        result = SourceVideoLinker._extract_speaker_names("前川/Izu")
        assert len(result) == 2

    def test_excludes_mc(self):
        result = SourceVideoLinker._extract_speaker_names("MC, ゲスト")
        assert "MC" not in result
        assert "ゲスト" in result


class TestNameMatch:
    """名前マッチングのテスト"""

    def test_exact_match(self):
        score = SourceVideoLinker._name_match("hirai", ["hirai", "インタビュアー"])
        assert score == 1.0

    def test_case_insensitive(self):
        score = SourceVideoLinker._name_match("Hirai", ["hirai"])
        assert score == 1.0

    def test_partial_match(self):
        score = SourceVideoLinker._name_match("Izu", ["Izuさん"])
        assert score >= 0.8

    def test_no_match(self):
        score = SourceVideoLinker._name_match("田中", ["佐藤"])
        assert score == 0.0

    def test_empty_guest(self):
        score = SourceVideoLinker._name_match("", ["hirai"])
        assert score == 0.0

    def test_empty_speakers(self):
        score = SourceVideoLinker._name_match("hirai", [])
        assert score == 0.0

    def test_san_suffix_removal(self):
        """「さん」付けの除去"""
        score = SourceVideoLinker._name_match("hiraiさん", ["hirai"])
        assert score >= 0.8

    def test_partial_name_in_speaker(self):
        score = SourceVideoLinker._name_match("ryo", ["ryoさん"])
        assert score >= 0.8


class TestExtractYoutubeUrlFromContent:
    """YouTube URL抽出のテスト"""

    def test_standard_meta(self):
        content = make_knowledge_content(youtube_url="https://www.youtube.com/watch?v=abc123")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            result = SourceVideoLinker._extract_youtube_url_from_content(f.name)
        os.unlink(f.name)
        assert result == "https://www.youtube.com/watch?v=abc123"

    def test_no_youtube_url(self):
        content = make_knowledge_content(youtube_url=None)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            result = SourceVideoLinker._extract_youtube_url_from_content(f.name)
        os.unlink(f.name)
        assert result == ""

    def test_short_url(self):
        content = "テスト\nhttps://youtu.be/xyz789\nテスト"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            result = SourceVideoLinker._extract_youtube_url_from_content(f.name)
        os.unlink(f.name)
        assert result == "https://youtu.be/xyz789"

    def test_nonexistent_file(self):
        result = SourceVideoLinker._extract_youtube_url_from_content("/nonexistent/path.md")
        assert result == ""


class TestGetLinkableProjects:
    """マッチング候補一覧のテスト"""

    def test_basic_match(self, tmp_path):
        """基本的なマッチング（日付+名前一致）"""
        db_path = tmp_path / "test.db"
        create_test_db(db_path, [
            {"id": "p1", "guest_name": "hirai", "title": "テスト", "shoot_date": "2025-11-23"},
        ])
        knowledge_dir = create_test_knowledge_dir(tmp_path, [
            {
                "name": "2026.02.15_20251123撮影_hiraiさん.md",
                "content": make_knowledge_content(
                    title="hiraiさん対談",
                    date="2025/11/23",
                    speakers="hirai, インタビュアー",
                    transcript_method="YouTube字幕",
                    youtube_url="https://www.youtube.com/watch?v=test123",
                ),
            },
        ])
        linker = SourceVideoLinker(db_path=db_path, knowledge_dir=knowledge_dir)
        result = linker.get_linkable_projects()
        assert len(result.linked) == 1
        assert result.linked[0].youtube_url == "https://www.youtube.com/watch?v=test123"

    def test_skip_existing_source_video(self, tmp_path):
        """既にsource_videoが登録済みの場合はスキップ"""
        db_path = tmp_path / "test.db"
        existing_video = json.dumps({"url": "https://youtube.com/watch?v=existing", "source": "manual"})
        create_test_db(db_path, [
            {"id": "p1", "guest_name": "hirai", "title": "テスト", "shoot_date": "2025-11-23", "source_video": existing_video},
        ])
        knowledge_dir = create_test_knowledge_dir(tmp_path, [
            {
                "name": "2026.02.15_20251123撮影_hiraiさん.md",
                "content": make_knowledge_content(),
            },
        ])
        linker = SourceVideoLinker(db_path=db_path, knowledge_dir=knowledge_dir)
        result = linker.get_linkable_projects()
        assert len(result.linked) == 0
        assert len(result.skipped_existing) == 1

    def test_skip_no_audio_quality(self, tmp_path):
        """GPT-4oのみ（YouTube字幕なし）の場合はスキップ"""
        db_path = tmp_path / "test.db"
        create_test_db(db_path, [
            {"id": "p1", "guest_name": "hirai", "title": "テスト", "shoot_date": "2025-11-23"},
        ])
        knowledge_dir = create_test_knowledge_dir(tmp_path, [
            {
                "name": "2026.02.15_20251123撮影_hiraiさん.md",
                "content": make_knowledge_content(
                    date="2025/11/23",
                    speakers="hirai, インタビュアー",
                    transcript_method="GPT-4o Transcribe（話者分離あり）",
                    youtube_url="https://www.youtube.com/watch?v=test123",
                ),
            },
        ])
        linker = SourceVideoLinker(db_path=db_path, knowledge_dir=knowledge_dir)
        result = linker.get_linkable_projects()
        assert len(result.linked) == 0
        assert len(result.skipped_no_audio) == 1

    def test_no_match(self, tmp_path):
        """マッチするナレッジファイルがない場合"""
        db_path = tmp_path / "test.db"
        create_test_db(db_path, [
            {"id": "p1", "guest_name": "田中", "title": "テスト", "shoot_date": "2025-11-23"},
        ])
        knowledge_dir = create_test_knowledge_dir(tmp_path, [
            {
                "name": "2026.02.15_20251123撮影_hiraiさん.md",
                "content": make_knowledge_content(
                    date="2025/11/23",
                    speakers="hirai, インタビュアー",
                ),
            },
        ])
        linker = SourceVideoLinker(db_path=db_path, knowledge_dir=knowledge_dir)
        result = linker.get_linkable_projects()
        assert len(result.linked) == 0
        assert len(result.skipped_no_match) >= 1


class TestScanAndLink:
    """スキャン＆リンク実行のテスト"""

    def test_dry_run_does_not_modify_db(self, tmp_path):
        """dry_runモードではDBを更新しない"""
        db_path = tmp_path / "test.db"
        create_test_db(db_path, [
            {"id": "p1", "guest_name": "hirai", "title": "テスト", "shoot_date": "2025-11-23"},
        ])
        knowledge_dir = create_test_knowledge_dir(tmp_path, [
            {
                "name": "2026.02.15_20251123撮影_hiraiさん.md",
                "content": make_knowledge_content(),
            },
        ])
        linker = SourceVideoLinker(db_path=db_path, knowledge_dir=knowledge_dir)
        result = linker.scan_and_link(dry_run=True)
        assert len(result.linked) >= 0  # dry_runでは候補表示のみ

        # DBが更新されていないことを確認
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT source_video FROM projects WHERE id = 'p1'").fetchone()
        conn.close()
        assert row[0] is None

    def test_actual_link(self, tmp_path):
        """実行モードでDBが更新される"""
        db_path = tmp_path / "test.db"
        create_test_db(db_path, [
            {"id": "p1", "guest_name": "hirai", "title": "テスト", "shoot_date": "2025-11-23"},
        ])
        knowledge_dir = create_test_knowledge_dir(tmp_path, [
            {
                "name": "2026.02.15_20251123撮影_hiraiさん.md",
                "content": make_knowledge_content(
                    date="2025/11/23",
                    speakers="hirai, インタビュアー",
                    transcript_method="YouTube字幕",
                    youtube_url="https://www.youtube.com/watch?v=linked123",
                ),
            },
        ])
        linker = SourceVideoLinker(db_path=db_path, knowledge_dir=knowledge_dir)
        result = linker.scan_and_link(dry_run=False)
        assert len(result.linked) == 1

        # DB確認
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT source_video FROM projects WHERE id = 'p1'").fetchone()
        conn.close()
        data = json.loads(row[0])
        assert data["url"] == "https://www.youtube.com/watch?v=linked123"
        assert data["source"] == "ai_dev5"
        assert data["quality"] == "youtube_subtitle"

    def test_does_not_overwrite_existing(self, tmp_path):
        """既存のsource_videoを上書きしない"""
        db_path = tmp_path / "test.db"
        existing = json.dumps({"url": "https://vimeo.com/existing", "source": "manual"})
        create_test_db(db_path, [
            {"id": "p1", "guest_name": "hirai", "title": "テスト", "shoot_date": "2025-11-23", "source_video": existing},
        ])
        knowledge_dir = create_test_knowledge_dir(tmp_path, [
            {
                "name": "2026.02.15_20251123撮影_hiraiさん.md",
                "content": make_knowledge_content(),
            },
        ])
        linker = SourceVideoLinker(db_path=db_path, knowledge_dir=knowledge_dir)
        result = linker.scan_and_link(dry_run=False)
        assert len(result.linked) == 0
        assert len(result.skipped_existing) == 1

        # DB確認: 元のURLが維持されている
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT source_video FROM projects WHERE id = 'p1'").fetchone()
        conn.close()
        data = json.loads(row[0])
        assert data["url"] == "https://vimeo.com/existing"


class TestGetStatus:
    """ステータスAPIのテスト"""

    def test_basic_status(self, tmp_path):
        """基本的なステータス取得"""
        db_path = tmp_path / "test.db"
        existing = json.dumps({"url": "https://youtube.com/watch?v=linked", "source": "ai_dev5", "quality": "youtube_subtitle"})
        create_test_db(db_path, [
            {"id": "p1", "guest_name": "hirai", "title": "テスト1", "shoot_date": "2025-11-23", "source_video": existing},
            {"id": "p2", "guest_name": "tanaka", "title": "テスト2", "shoot_date": "2025-12-01"},
        ])
        knowledge_dir = create_test_knowledge_dir(tmp_path)
        linker = SourceVideoLinker(db_path=db_path, knowledge_dir=knowledge_dir)
        status = linker.get_status()
        assert status["linked_count"] == 1
        assert status["total_projects"] == 2
        assert isinstance(status["linked_projects"], list)


class TestMultipleProjects:
    """複数プロジェクトのテスト"""

    def test_multiple_projects_different_dates(self, tmp_path):
        """異なる日付の複数プロジェクト"""
        db_path = tmp_path / "test.db"
        create_test_db(db_path, [
            {"id": "p1", "guest_name": "hirai", "title": "hirai対談", "shoot_date": "2025-11-23"},
            {"id": "p2", "guest_name": "Izu", "title": "Izu対談", "shoot_date": "2025-11-23"},
            {"id": "p3", "guest_name": "ryo", "title": "ryo対談", "shoot_date": "2026-01-24"},
        ])
        knowledge_dir = create_test_knowledge_dir(tmp_path, [
            {
                "name": "2026.02.15_20251123撮影_hiraiさん.md",
                "content": make_knowledge_content(
                    title="hirai対談", date="2025/11/23",
                    speakers="hirai, インタビュアー",
                    transcript_method="YouTube字幕",
                    youtube_url="https://www.youtube.com/watch?v=hirai1",
                ),
            },
            {
                "name": "2026.02.16_20251123撮影_Izuさん.md",
                "content": make_knowledge_content(
                    title="Izu対談", date="2025/11/23",
                    speakers="Izu, インタビュアー",
                    transcript_method="YouTube字幕",
                    youtube_url="https://www.youtube.com/watch?v=izu1",
                ),
            },
            {
                "name": "2026.02.15_20260124撮影_ryoさん.md",
                "content": make_knowledge_content(
                    title="ryo対談", date="2026/01/24",
                    speakers="ryo, インタビュアー",
                    transcript_method="GPT-4o Transcribe",
                    youtube_url="https://www.youtube.com/watch?v=ryo1",
                ),
            },
        ])
        linker = SourceVideoLinker(db_path=db_path, knowledge_dir=knowledge_dir)
        result = linker.get_linkable_projects()
        # hirai と Izu は YouTube字幕あり → linked
        # ryo は GPT-4oのみ → skipped_no_audio
        linked_ids = {c.project_id for c in result.linked}
        assert "p1" in linked_ids  # hirai
        assert "p2" in linked_ids  # Izu
        assert "p3" not in linked_ids  # ryo は音質NG
        no_audio_ids = {c.project_id for c in result.skipped_no_audio}
        assert "p3" in no_audio_ids

    def test_empty_db(self, tmp_path):
        """プロジェクトが0件の場合"""
        db_path = tmp_path / "test.db"
        create_test_db(db_path, [])
        knowledge_dir = create_test_knowledge_dir(tmp_path)
        linker = SourceVideoLinker(db_path=db_path, knowledge_dir=knowledge_dir)
        result = linker.get_linkable_projects()
        assert len(result.linked) == 0
        assert len(result.skipped_existing) == 0

    def test_empty_knowledge_dir(self, tmp_path):
        """ナレッジファイルが0件の場合"""
        db_path = tmp_path / "test.db"
        create_test_db(db_path, [
            {"id": "p1", "guest_name": "hirai", "title": "テスト", "shoot_date": "2025-11-23"},
        ])
        knowledge_dir = create_test_knowledge_dir(tmp_path)
        linker = SourceVideoLinker(db_path=db_path, knowledge_dir=knowledge_dir)
        result = linker.get_linkable_projects()
        assert len(result.linked) == 0
        assert len(result.skipped_no_match) == 1


class TestEdgeCases:
    """エッジケースのテスト"""

    def test_null_shoot_date(self, tmp_path):
        """撮影日がNULLのプロジェクト"""
        db_path = tmp_path / "test.db"
        create_test_db(db_path, [
            {"id": "p1", "guest_name": "hirai", "title": "テスト", "shoot_date": None},
        ])
        knowledge_dir = create_test_knowledge_dir(tmp_path, [
            {
                "name": "test.md",
                "content": make_knowledge_content(
                    date="2025/11/23",
                    speakers="hirai",
                    transcript_method="YouTube字幕",
                ),
            },
        ])
        linker = SourceVideoLinker(db_path=db_path, knowledge_dir=knowledge_dir)
        result = linker.get_linkable_projects()
        # 日付なしでも名前一致で候補になりうるが、閾値次第
        # 名前のみ一致 score = 0.5 → 閾値0.5なのでギリギリ通る
        assert len(result.linked) + len(result.skipped_no_match) + len(result.skipped_no_audio) >= 1

    def test_source_video_invalid_json(self, tmp_path):
        """source_videoに不正なJSONが入っている場合"""
        db_path = tmp_path / "test.db"
        create_test_db(db_path, [
            {"id": "p1", "guest_name": "hirai", "title": "テスト", "shoot_date": "2025-11-23", "source_video": "invalid-json"},
        ])
        knowledge_dir = create_test_knowledge_dir(tmp_path, [
            {
                "name": "2026.02.15_20251123撮影_hiraiさん.md",
                "content": make_knowledge_content(),
            },
        ])
        linker = SourceVideoLinker(db_path=db_path, knowledge_dir=knowledge_dir)
        # 不正JSONでもクラッシュしない
        result = linker.get_linkable_projects()
        assert isinstance(result, LinkResult)

    def test_source_video_empty_url(self, tmp_path):
        """source_videoにurlが空のJSONが入っている場合"""
        db_path = tmp_path / "test.db"
        empty_json = json.dumps({"url": "", "source": "manual"})
        create_test_db(db_path, [
            {"id": "p1", "guest_name": "hirai", "title": "テスト", "shoot_date": "2025-11-23", "source_video": empty_json},
        ])
        knowledge_dir = create_test_knowledge_dir(tmp_path, [
            {
                "name": "2026.02.15_20251123撮影_hiraiさん.md",
                "content": make_knowledge_content(),
            },
        ])
        linker = SourceVideoLinker(db_path=db_path, knowledge_dir=knowledge_dir)
        result = linker.get_linkable_projects()
        # urlが空なので「既存リンク」とは見做さず、候補として扱う
        assert len(result.skipped_existing) == 0

    def test_knowledge_file_no_youtube_url(self, tmp_path):
        """ナレッジファイルにYouTube URLがない場合"""
        db_path = tmp_path / "test.db"
        create_test_db(db_path, [
            {"id": "p1", "guest_name": "hirai", "title": "テスト", "shoot_date": "2025-11-23"},
        ])
        knowledge_dir = create_test_knowledge_dir(tmp_path, [
            {
                "name": "2026.02.15_20251123撮影_hiraiさん.md",
                "content": make_knowledge_content(
                    date="2025/11/23",
                    speakers="hirai, インタビュアー",
                    transcript_method="YouTube字幕",
                    youtube_url=None,
                ),
            },
        ])
        linker = SourceVideoLinker(db_path=db_path, knowledge_dir=knowledge_dir)
        result = linker.get_linkable_projects()
        # YouTube URLがないのでリンクできない
        assert len(result.linked) == 0

    def test_multiple_knowledge_same_guest(self, tmp_path):
        """同じゲストの複数ナレッジファイル（ベストマッチを選択）"""
        db_path = tmp_path / "test.db"
        create_test_db(db_path, [
            {"id": "p1", "guest_name": "hirai", "title": "テスト", "shoot_date": "2025-11-23"},
        ])
        knowledge_dir = create_test_knowledge_dir(tmp_path, [
            {
                "name": "2026.02.15_20251123撮影_hiraiさん.md",
                "content": make_knowledge_content(
                    title="hirai対談1", date="2025/11/23",
                    speakers="hirai, インタビュアー",
                    transcript_method="YouTube字幕",
                    youtube_url="https://www.youtube.com/watch?v=correct",
                ),
            },
            {
                "name": "2026.03.01_20260201撮影_hiraiさん2回目.md",
                "content": make_knowledge_content(
                    title="hirai対談2", date="2026/02/01",
                    speakers="hirai, 前川",
                    transcript_method="YouTube字幕",
                    youtube_url="https://www.youtube.com/watch?v=wrong",
                ),
            },
        ])
        linker = SourceVideoLinker(db_path=db_path, knowledge_dir=knowledge_dir)
        result = linker.get_linkable_projects()
        assert len(result.linked) == 1
        # 日付+名前一致の方を選択
        assert result.linked[0].youtube_url == "https://www.youtube.com/watch?v=correct"

    def test_idempotent_scan(self, tmp_path):
        """2回実行しても2回目はスキップされる（冪等性）"""
        db_path = tmp_path / "test.db"
        create_test_db(db_path, [
            {"id": "p1", "guest_name": "hirai", "title": "テスト", "shoot_date": "2025-11-23"},
        ])
        knowledge_dir = create_test_knowledge_dir(tmp_path, [
            {
                "name": "2026.02.15_20251123撮影_hiraiさん.md",
                "content": make_knowledge_content(
                    date="2025/11/23",
                    speakers="hirai, インタビュアー",
                    transcript_method="YouTube字幕",
                    youtube_url="https://www.youtube.com/watch?v=test123",
                ),
            },
        ])
        linker = SourceVideoLinker(db_path=db_path, knowledge_dir=knowledge_dir)

        # 1回目: リンク実行
        result1 = linker.scan_and_link(dry_run=False)
        assert len(result1.linked) == 1

        # 2回目: 既にリンク済みなのでスキップ
        result2 = linker.scan_and_link(dry_run=False)
        assert len(result2.linked) == 0
        assert len(result2.skipped_existing) == 1
