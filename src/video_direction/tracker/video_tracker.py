from __future__ import annotations

"""映像トラッキング: 外部映像の収集・追跡

YouTube URLを登録し、メタデータ・字幕を自動取得。
分析→学習→ディレクション反映のE2Eフローの起点。
"""
import json
import logging
import subprocess
import re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class TrackedVideo:
    id: str
    url: str
    title: str
    channel_name: str = ""
    thumbnail_url: str = ""
    duration_seconds: float = 0.0
    view_count: int = 0
    upload_date: str = ""
    description: str = ""
    analysis_status: str = "pending"  # pending / analyzing / completed / error
    analysis_result: Optional[dict] = None
    transcript: str = ""  # 字幕テキスト（分析の入力として使用）
    tags: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


logger = logging.getLogger(__name__)


class VideoTracker:
    """外部映像の収集・追跡を管理"""

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path.home() / "AI開発10" / ".data" / "tracking"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.data_dir / "tracking_index.json"
        self._videos: dict[str, TrackedVideo] = {}
        self._load_index()

    def _load_index(self):
        """インデックスファイルからトラッキングデータを読み込み"""
        if self.index_path.exists():
            try:
                data = json.loads(self.index_path.read_text())
                for v in data.get("videos", []):
                    try:
                        video = TrackedVideo(**v)
                        self._videos[video.id] = video
                    except TypeError as e:
                        logger.warning("TrackedVideoの復元をスキップ（不正データ）: %s", e)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning("トラッキングインデックスの読み込みに失敗。空辞書にフォールバック: %s", e)
                self._videos = {}

    def _save_index(self):
        """インデックスファイルに保存"""
        data = {
            "videos": [asdict(v) for v in self._videos.values()],
            "updated_at": datetime.now().isoformat(),
        }
        self.index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def add_video(self, url: str, tags: list = None) -> TrackedVideo:
        """YouTube URLからメタデータを取得してトラッキング登録"""
        # yt-dlp でメタデータ取得（ダウンロードはしない）
        meta = self._fetch_metadata(url)
        video_id = meta.get("id", url)

        if video_id in self._videos:
            return self._videos[video_id]

        video = TrackedVideo(
            id=video_id,
            url=url,
            title=meta.get("title", "Unknown"),
            channel_name=meta.get("channel", meta.get("uploader", "")),
            thumbnail_url=meta.get("thumbnail", ""),
            duration_seconds=meta.get("duration", 0.0),
            view_count=meta.get("view_count", 0),
            upload_date=meta.get("upload_date", ""),
            description=(meta.get("description", "") or "")[:500],
            tags=tags or [],
        )
        self._videos[video_id] = video
        self._save_index()
        return video

    def add_videos_batch(self, urls: list[str], tags: list = None) -> list[TrackedVideo]:
        """複数URLを一括登録（バッチ登録）

        Args:
            urls: YouTube URLのリスト
            tags: 全動画に共通で付けるタグ

        Returns:
            登録された TrackedVideo のリスト（重複は既存を返す）
        """
        results = []
        for url in urls:
            try:
                video = self.add_video(url, tags=tags)
                results.append(video)
            except Exception:
                # 1本の失敗で全体が止まらないように
                results.append(TrackedVideo(
                    id=url, url=url, title=f"登録失敗: {url}",
                    analysis_status="error",
                ))
        return results

    def fetch_transcript(self, video_id: str) -> str:
        """YouTube動画の字幕テキストを取得・保存

        yt-dlpで自動字幕（日本語優先）を取得し、TrackedVideoのtranscriptに格納する。
        VideoAnalyzerの入力として使用する。
        """
        video = self._videos.get(video_id)
        if not video:
            return ""

        # 既に取得済みならそのまま返す
        if video.transcript:
            return video.transcript

        transcript = self._download_transcript(video.url)
        if transcript:
            video.transcript = transcript
            video.updated_at = datetime.now().isoformat()
            self._save_index()
        return transcript

    def _download_transcript(self, url: str) -> str:
        """yt-dlp で字幕テキスト取得"""
        yt_dlp_cmd = self._get_yt_dlp_cmd()
        try:
            # まず自動字幕（日本語）を試行
            result = subprocess.run(
                [yt_dlp_cmd, "--write-auto-sub", "--sub-lang", "ja",
                 "--skip-download", "--sub-format", "vtt",
                 "--print-to-file", "%(subtitles.ja.ext)s", "/dev/null",
                 "-o", "-", "--dump-json", url],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                meta = json.loads(result.stdout)
                # 字幕URLがある場合はアクセスして取得
                subs = meta.get("subtitles", {}) or meta.get("automatic_captions", {})
                for lang in ["ja", "en"]:
                    if lang in subs and subs[lang]:
                        return self._fetch_subtitle_text(subs[lang], yt_dlp_cmd, url, lang)

            # フォールバック: yt-dlpのget-subtitlesで直接取得
            result2 = subprocess.run(
                [yt_dlp_cmd, "--write-auto-sub", "--sub-lang", "ja,en",
                 "--skip-download", "--print-to-file", "subtitle:%(filepath)s", "/dev/null",
                 "--get-filename", "-o", "%(id)s", url],
                capture_output=True, text=True, timeout=30,
            )
            # 字幕が取れなかった場合は空文字を返す
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return ""

    def _fetch_subtitle_text(self, sub_entries: list, yt_dlp_cmd: str, url: str, lang: str) -> str:
        """字幕エントリからテキストを抽出"""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                result = subprocess.run(
                    [yt_dlp_cmd, "--write-auto-sub", "--sub-lang", lang,
                     "--skip-download", "--sub-format", "vtt",
                     "-o", f"{tmpdir}/%(id)s.%(ext)s", url],
                    capture_output=True, text=True, timeout=60,
                )
                # 生成された字幕ファイルを探して読み込む
                for f in Path(tmpdir).glob("*.vtt"):
                    raw = f.read_text(encoding="utf-8", errors="ignore")
                    return self._parse_vtt(raw)
                for f in Path(tmpdir).glob("*.srt"):
                    raw = f.read_text(encoding="utf-8", errors="ignore")
                    return self._parse_srt(raw)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        return ""

    @staticmethod
    def _parse_vtt(raw: str) -> str:
        """VTT形式の字幕からテキスト部分だけを抽出"""
        lines = []
        for line in raw.split("\n"):
            line = line.strip()
            # タイムスタンプ行やヘッダーを除外
            if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
                continue
            if "-->" in line:
                continue
            if re.match(r"^\d+$", line):
                continue
            # HTMLタグ除去
            clean = re.sub(r"<[^>]+>", "", line)
            if clean and clean not in lines[-1:]:
                lines.append(clean)
        return "\n".join(lines)

    @staticmethod
    def _parse_srt(raw: str) -> str:
        """SRT形式の字幕からテキスト部分だけを抽出"""
        lines = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line or re.match(r"^\d+$", line) or "-->" in line:
                continue
            clean = re.sub(r"<[^>]+>", "", line)
            if clean and clean not in lines[-1:]:
                lines.append(clean)
        return "\n".join(lines)

    def get_status_summary(self) -> dict:
        """トラッキング全体の状態サマリー"""
        videos = list(self._videos.values())
        status_counts = {}
        for v in videos:
            status_counts[v.analysis_status] = status_counts.get(v.analysis_status, 0) + 1

        has_transcript = sum(1 for v in videos if v.transcript)
        channels = list(set(v.channel_name for v in videos if v.channel_name))

        return {
            "total_videos": len(videos),
            "status_counts": status_counts,
            "has_transcript": has_transcript,
            "channels": channels,
            "tags": list(set(t for v in videos for t in v.tags)),
        }

    def _fetch_metadata(self, url: str) -> dict:
        """yt-dlp でメタデータ取得"""
        try:
            yt_dlp_cmd = self._get_yt_dlp_cmd()
            result = subprocess.run(
                [yt_dlp_cmd, "--dump-json", "--no-download", url],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass
        return {"id": url, "title": url}

    @staticmethod
    def _get_yt_dlp_cmd() -> str:
        """yt-dlpコマンドのパスを解決"""
        yt_dlp_user_path = Path.home() / "Library" / "Python" / "3.9" / "bin" / "yt-dlp"
        if yt_dlp_user_path.exists():
            return str(yt_dlp_user_path)
        return "yt-dlp"

    def list_videos(self, status: str = None) -> list[TrackedVideo]:
        """トラッキング中の映像一覧"""
        videos = list(self._videos.values())
        if status:
            videos = [v for v in videos if v.analysis_status == status]
        return sorted(videos, key=lambda v: v.created_at, reverse=True)

    def get_video(self, video_id: str) -> Optional[TrackedVideo]:
        return self._videos.get(video_id)

    def update_analysis(self, video_id: str, result: dict, status: str = "completed"):
        """分析結果を更新"""
        if video_id in self._videos:
            self._videos[video_id].analysis_result = result
            self._videos[video_id].analysis_status = status
            self._videos[video_id].updated_at = datetime.now().isoformat()
            self._save_index()

    def remove_video(self, video_id: str) -> bool:
        if video_id in self._videos:
            del self._videos[video_id]
            self._save_index()
            return True
        return False
