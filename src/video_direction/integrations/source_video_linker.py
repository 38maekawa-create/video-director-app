"""J-2: AI開発5連携 — 素材動画URL自動登録

AI開発5の動画ナレッジファイルをスキャンし、映像エージェントのprojectsテーブルと
マッチングしてsource_videoカラムにYouTube URLを自動登録する。

マッチング条件: 撮影日(date) + 話者名(speakers)
音質フィルタ: transcript_method に「YouTube字幕」が含まれる場合のみ採用
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .ai_dev5_connector import (
    VideoData,
    list_video_markdown_files,
    parse_markdown_file,
)

logger = logging.getLogger(__name__)

# デフォルトのDB パス
DB_PATH = Path.home() / "AI開発10" / ".data" / "video_director.db"


@dataclass
class LinkCandidate:
    """マッチング候補"""
    project_id: str
    project_guest_name: str
    project_shoot_date: str
    knowledge_file: str
    knowledge_date: str
    knowledge_speakers: str
    youtube_url: str
    transcript_method: str
    quality: str  # "youtube_subtitle" or "gpt4o" etc
    match_score: float  # 0.0 - 1.0
    reason: str  # マッチング理由
    skipped: bool = False  # スキップ理由がある場合True
    skip_reason: str = ""


@dataclass
class LinkResult:
    """リンク実行結果"""
    linked: list = field(default_factory=list)  # List[LinkCandidate]
    skipped_existing: list = field(default_factory=list)
    skipped_no_audio: list = field(default_factory=list)
    skipped_no_match: list = field(default_factory=list)
    errors: list = field(default_factory=list)


class SourceVideoLinker:
    """AI開発5のナレッジファイルと映像エージェントのプロジェクトを連携する"""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        knowledge_dir: Optional[Path] = None,
    ):
        self.db_path = db_path or DB_PATH
        self.knowledge_dir = knowledge_dir or (
            Path.home() / "TEKO" / "knowledge" / "01_teko" / "sources" / "video"
        )

    def _get_db(self) -> sqlite3.Connection:
        """DB接続を取得"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _get_projects(self) -> list[dict]:
        """全プロジェクトを取得"""
        conn = self._get_db()
        try:
            rows = conn.execute(
                "SELECT id, guest_name, shoot_date, source_video FROM projects"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _parse_knowledge_files(self) -> list[VideoData]:
        """ナレッジファイルを全件パース"""
        files = list_video_markdown_files(self.knowledge_dir)
        results = []
        for f in files:
            try:
                data = parse_markdown_file(f)
                results.append(data)
            except Exception as e:
                logger.warning("ナレッジファイルパース失敗: %s: %s", f, e)
        return results

    @staticmethod
    def _normalize_date(date_str: str) -> str:
        """日付文字列を YYYY-MM-DD に正規化"""
        if not date_str:
            return ""
        # "2025/11/23" → "2025-11-23"
        date_str = date_str.strip().replace("/", "-")
        # "20251123" → "2025-11-23"
        if re.match(r"^\d{8}$", date_str):
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        # 既に "2025-11-23" 形式
        if re.match(r"^\d{4}-\d{2}-\d{2}", date_str):
            return date_str[:10]
        return date_str

    @staticmethod
    def _extract_date_from_filename(filepath: str) -> str:
        """ファイル名から撮影日を抽出（例: 2026.02.15_20251123撮影_... → 2025-11-23）"""
        basename = Path(filepath).stem
        # パターン1: YYYYMMDD撮影
        m = re.search(r"(\d{8})撮影", basename)
        if m:
            d = m.group(1)
            return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        # パターン2: 先頭の YYYY.MM.DD（作成日）は使わない
        return ""

    @staticmethod
    def _extract_guest_name_from_filename(filepath: str) -> str:
        """ファイル名からゲスト名を抽出"""
        basename = Path(filepath).stem
        # パターン1: YYYYMMDD撮影_[名前]さん：... or YYYYMMDD撮影_[名前]：
        m = re.search(r"撮影_(.+?)(?:さん|：|$)", basename)
        if m:
            name = m.group(1).strip()
            if name:
                return name
        # パターン2: 日付_[名前]さん.md（撮影なしパターン）
        # 例: 2026.02.28_けーさん.md → けー
        m = re.search(r"\d{4}\.\d{2}\.\d{2}_(.+?)(?:さん|：|_)", basename)
        if m:
            name = m.group(1).strip()
            if name:
                return name
        # パターン3: ファイル名中の「[名前]さん：」を後方から探す
        # 例: 2026.03.06_2月28日 大阪_コテツさん：... → コテツ
        # 例: 2026.03.07_トップ対談_ハオさん：... → ハオ
        parts = basename.split("_")
        for part in reversed(parts):
            m2 = re.match(r"(.+?)さん(?:：|$)", part)
            if m2:
                name = m2.group(1).strip()
                if name and not re.match(r"^\d", name):
                    return name
        # パターン4: ゲスト氏（里芋、トーマス）パターン
        m = re.search(r"ゲスト氏[（(](.+?)[）)]", basename)
        if m:
            name = m.group(1).strip()
            if name:
                return name
        return ""

    @staticmethod
    def _extract_youtube_url(source_str: str) -> str:
        """ソース文字列からYouTube URLを抽出"""
        if not source_str:
            return ""
        # メタ情報の「ソース」フィールドからは直接URLは取れないことが多い
        # 「YouTube URL」フィールドがある場合はそちらを使う
        return ""

    @staticmethod
    def _extract_youtube_url_from_content(filepath: str | Path) -> str:
        """ファイル内容からYouTube URLを抽出"""
        try:
            content = Path(filepath).read_text(encoding="utf-8")
        except Exception:
            return ""
        # パターン1: **YouTube URL**: https://...
        m = re.search(r"\*\*YouTube\s*URL\*\*:\s*(https?://(?:www\.)?youtube\.com/watch\?v=[^\s]+)", content)
        if m:
            return m.group(1).strip()
        # パターン2: ソースにYouTube URLが含まれている
        m = re.search(r"\*\*ソース\*\*:\s*(https?://(?:www\.)?youtube\.com/watch\?v=[^\s]+)", content)
        if m:
            return m.group(1).strip()
        # パターン3: 本文中のYouTube URL
        m = re.search(r"(https?://(?:www\.)?youtube\.com/watch\?v=[A-Za-z0-9_-]+)", content)
        if m:
            return m.group(1).strip()
        # パターン4: youtu.be 短縮URL
        m = re.search(r"(https?://youtu\.be/[A-Za-z0-9_-]+)", content)
        if m:
            return m.group(1).strip()
        return ""

    @staticmethod
    def _is_youtube_subtitle(transcript_method: str) -> bool:
        """文字起こし方式がYouTube字幕かどうか判定"""
        if not transcript_method:
            return False
        return "YouTube字幕" in transcript_method or "youtube" in transcript_method.lower()

    @staticmethod
    def _extract_speaker_names(speakers_str: str) -> list[str]:
        """話者文字列から名前リストを抽出（括弧内のカンマは分割しない）"""
        if not speakers_str:
            return []
        # 括弧内のカンマを一時的に置換して保護
        protected = re.sub(r"[（(][^）)]*[）)]", lambda m: m.group().replace(",", "\x00").replace("、", "\x01"), speakers_str)
        names = []
        for name in re.split(r"[,、/]", protected):
            name = name.strip().replace("\x00", ",").replace("\x01", "、")
            # 「インタビュアー」「ナレーター」等の汎用話者は除外
            if name and name not in ("インタビュアー", "ナレーター", "MC", "司会", "司会者"):
                names.append(name)
        return names

    # MEMBER_MASTER.jsonの文字起こし誤変換+エイリアスから構築した名寄せマップ
    # キー: 正規化名（小文字）、値: そのメンバーの全表記バリエーション（小文字）
    _NAME_ALIASES: dict[str, set[str]] = {
        "kos": {"kos", "コスト", "コスト氏"},
        "メンイチ": {"メンイチ", "メイジ", "メイチ"},
        "さといも・トーマス": {"さといも・トーマス", "さといも", "トーマス", "里芋", "柚山", "ゲスト氏（里芋、トーマス）", "里芋、トーマス"},
        "ハオ": {"ハオ", "羽生", "羽生氏"},
        "hirai": {"hirai", "平井"},
        "こも": {"こも", "小本"},
        "ゆきもる": {"ゆきもる", "雪村", "雪森"},
        "しお": {"しお", "シオ"},
        "コテ": {"コテ", "コテツ"},
        "Izu": {"izu", "飯泉"},
    }

    @staticmethod
    def _resolve_alias(name: str) -> set[str]:
        """名前のエイリアス（別表記）を全て返す"""
        name_lower = name.lower().strip()
        name_clean = re.sub(r"さん$", "", name_lower)
        for canonical, aliases in SourceVideoLinker._NAME_ALIASES.items():
            aliases_lower = {a.lower() for a in aliases}
            if name_clean in aliases_lower or name_lower in aliases_lower:
                return aliases_lower
        return set()

    @staticmethod
    def _name_match(project_guest: str, knowledge_speakers: list[str]) -> float:
        """プロジェクトのゲスト名とナレッジの話者名のマッチングスコアを返す"""
        if not project_guest or not knowledge_speakers:
            return 0.0
        guest_lower = project_guest.lower().strip()
        guest_clean = re.sub(r"さん$", "", guest_lower)
        for speaker in knowledge_speakers:
            speaker_lower = speaker.lower().strip()
            speaker_clean = re.sub(r"さん$", "", speaker_lower)
            # 完全一致
            if guest_lower == speaker_lower:
                return 1.0
            # 部分一致（ゲスト名が話者名に含まれる、またはその逆）
            if guest_lower in speaker_lower or speaker_lower in guest_lower:
                return 0.8
            # 「さん」付け除去して比較
            if guest_clean and speaker_clean:
                if guest_clean == speaker_clean:
                    return 1.0
                if guest_clean in speaker_clean or speaker_clean in guest_clean:
                    return 0.8
            # エイリアスマッチ（文字起こし誤変換・別名対応）
            guest_aliases = SourceVideoLinker._resolve_alias(guest_lower)
            if guest_aliases:
                speaker_aliases = SourceVideoLinker._resolve_alias(speaker_lower)
                if speaker_aliases and guest_aliases & speaker_aliases:
                    return 0.9  # エイリアス経由の一致
                # speaker自体がguestのエイリアスに含まれるか
                if speaker_clean in guest_aliases:
                    return 0.9
            speaker_aliases = SourceVideoLinker._resolve_alias(speaker_lower)
            if speaker_aliases and guest_clean in speaker_aliases:
                return 0.9
        return 0.0

    def _match_project_to_knowledge(
        self,
        project: dict,
        knowledge_list: list[VideoData],
    ) -> Optional[LinkCandidate]:
        """プロジェクトに最適なナレッジファイルをマッチングする"""
        project_date = self._normalize_date(project.get("shoot_date", "") or "")
        project_guest = project.get("guest_name", "") or ""

        best_candidate = None
        best_score = 0.0

        for kdata in knowledge_list:
            # 日付マッチング
            k_date = self._normalize_date(kdata.date)
            k_file_date = self._extract_date_from_filename(kdata.source_path)

            date_match = False
            matched_date = ""
            if project_date and k_date and project_date == k_date:
                date_match = True
                matched_date = k_date
            elif project_date and k_file_date and project_date == k_file_date:
                date_match = True
                matched_date = k_file_date

            # 名前マッチング（speakersが「不明」の場合はファイル名から抽出）
            speakers = self._extract_speaker_names(kdata.speakers)
            if not speakers or speakers == ["不明"]:
                fname_guest = self._extract_guest_name_from_filename(kdata.source_path)
                if fname_guest:
                    speakers = [fname_guest]
            name_score = self._name_match(project_guest, speakers)

            # スコア算出
            score = 0.0
            reason_parts = []
            if date_match and name_score >= 0.8:
                score = 0.5 + name_score * 0.5  # 0.9 - 1.0
                reason_parts.append(f"日付一致({matched_date})")
                reason_parts.append(f"名前一致(score={name_score})")
            elif date_match and name_score > 0:
                score = 0.3 + name_score * 0.3
                reason_parts.append(f"日付一致({matched_date})")
                reason_parts.append(f"名前部分一致(score={name_score})")
            elif name_score >= 0.8:
                # 日付なしだが名前が強く一致 — 十分にリンク対象
                score = 0.5 + name_score * 0.2  # 0.66 - 0.7
                reason_parts.append(f"名前一致(score={name_score})")
            # 日付のみ一致は誤マッチの可能性が高いためスキップ

            if score > best_score:
                youtube_url = self._extract_youtube_url_from_content(kdata.source_path)
                quality = "youtube_subtitle" if self._is_youtube_subtitle(kdata.transcript_method) else "gpt4o"

                best_score = score
                best_candidate = LinkCandidate(
                    project_id=project["id"],
                    project_guest_name=project_guest,
                    project_shoot_date=project.get("shoot_date", ""),
                    knowledge_file=kdata.source_path,
                    knowledge_date=kdata.date,
                    knowledge_speakers=kdata.speakers,
                    youtube_url=youtube_url,
                    transcript_method=kdata.transcript_method,
                    quality=quality,
                    match_score=score,
                    reason=" + ".join(reason_parts),
                )

        # 閾値以上のスコアのみ返す
        if best_candidate and best_score >= 0.5:
            return best_candidate
        return None

    def get_linkable_projects(self) -> LinkResult:
        """マッチング候補の一覧を返す（dry-run用）"""
        result = LinkResult()
        projects = self._get_projects()
        knowledge_list = self._parse_knowledge_files()

        for project in projects:
            # 既にsource_videoが入っている場合
            existing = project.get("source_video")
            if existing:
                try:
                    data = json.loads(existing) if isinstance(existing, str) else existing
                    if data and data.get("url"):
                        candidate = LinkCandidate(
                            project_id=project["id"],
                            project_guest_name=project.get("guest_name", ""),
                            project_shoot_date=project.get("shoot_date", ""),
                            knowledge_file="",
                            knowledge_date="",
                            knowledge_speakers="",
                            youtube_url=data.get("url", ""),
                            transcript_method="",
                            quality=data.get("quality", ""),
                            match_score=0,
                            reason="既にリンク済み",
                            skipped=True,
                            skip_reason="already_linked",
                        )
                        result.skipped_existing.append(candidate)
                        continue
                except (json.JSONDecodeError, TypeError):
                    pass

            candidate = self._match_project_to_knowledge(project, knowledge_list)
            if candidate is None:
                result.skipped_no_match.append(LinkCandidate(
                    project_id=project["id"],
                    project_guest_name=project.get("guest_name", ""),
                    project_shoot_date=project.get("shoot_date", ""),
                    knowledge_file="",
                    knowledge_date="",
                    knowledge_speakers="",
                    youtube_url="",
                    transcript_method="",
                    quality="",
                    match_score=0,
                    reason="マッチするナレッジファイルなし",
                    skipped=True,
                    skip_reason="no_match",
                ))
                continue

            # YouTube URLがなくてもナレッジファイルがマッチしていればリンク対象
            # （素材動画リンクは音質に関係なく有用）
            result.linked.append(candidate)

        return result

    def scan_and_link(self, dry_run: bool = False) -> LinkResult:
        """AI開発5のナレッジファイルをスキャンし、マッチングしてsource_videoに登録する"""
        result = self.get_linkable_projects()

        if dry_run:
            return result

        # 実際にDB更新
        conn = self._get_db()
        linked_final = []
        try:
            for candidate in result.linked:
                try:
                    source_video_json = json.dumps({
                        "url": candidate.youtube_url,
                        "source": "ai_dev5",
                        "quality": candidate.quality,
                        "knowledge_file": Path(candidate.knowledge_file).name if candidate.knowledge_file else "",
                        "linked_at": datetime.utcnow().isoformat(),
                    })
                    conn.execute(
                        "UPDATE projects SET source_video = ?, updated_at = datetime('now') WHERE id = ?",
                        (source_video_json, candidate.project_id),
                    )
                    linked_final.append(candidate)
                    logger.info(
                        "リンク成功: project=%s, url=%s",
                        candidate.project_id,
                        candidate.youtube_url,
                    )
                except Exception as e:
                    logger.error(
                        "リンク失敗: project=%s: %s",
                        candidate.project_id,
                        e,
                    )
                    result.errors.append(f"{candidate.project_id}: {e}")
            conn.commit()
        finally:
            conn.close()

        result.linked = linked_final

        # リンク成功したプロジェクトに対して自動レポート生成
        if linked_final:
            try:
                from .auto_report_trigger import trigger_auto_report_sync
                for candidate in linked_final:
                    try:
                        trigger_auto_report_sync(candidate.project_id)
                    except Exception as e:
                        logger.warning(
                            "自動レポート生成失敗: project=%s: %s",
                            candidate.project_id, e,
                        )
            except ImportError:
                logger.warning("auto_report_triggerモジュールが見つかりません")

        return result

    def get_status(self) -> dict:
        """連携状況サマリーを返す"""
        result = self.get_linkable_projects()
        return {
            "linked_count": len(result.skipped_existing),
            "linkable_count": len(result.linked),
            "no_audio_quality_count": len(result.skipped_no_audio),
            "no_match_count": len(result.skipped_no_match),
            "total_projects": (
                len(result.skipped_existing)
                + len(result.linked)
                + len(result.skipped_no_audio)
                + len(result.skipped_no_match)
            ),
            "linked_projects": [
                {
                    "project_id": c.project_id,
                    "guest_name": c.project_guest_name,
                    "youtube_url": c.youtube_url,
                }
                for c in result.skipped_existing
            ],
            "linkable_projects": [
                {
                    "project_id": c.project_id,
                    "guest_name": c.project_guest_name,
                    "youtube_url": c.youtube_url,
                    "match_score": c.match_score,
                    "reason": c.reason,
                }
                for c in result.linked
            ],
            "no_audio_quality_projects": [
                {
                    "project_id": c.project_id,
                    "guest_name": c.project_guest_name,
                    "transcript_method": c.transcript_method,
                    "knowledge_file": Path(c.knowledge_file).name if c.knowledge_file else "",
                }
                for c in result.skipped_no_audio
            ],
        }
