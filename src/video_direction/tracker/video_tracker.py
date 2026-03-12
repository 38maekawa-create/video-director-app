"""映像トラッキング: 外部映像の収集・追跡"""
import json
import subprocess
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
    analysis_status: str = "pending"  # pending / analyzing / completed / error
    analysis_result: Optional[dict] = None
    tags: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


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
            data = json.loads(self.index_path.read_text())
            for v in data.get("videos", []):
                video = TrackedVideo(**v)
                self._videos[video.id] = video

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
            tags=tags or [],
        )
        self._videos[video_id] = video
        self._save_index()
        return video

    def _fetch_metadata(self, url: str) -> dict:
        """yt-dlp でメタデータ取得"""
        try:
            result = subprocess.run(
                ["yt-dlp", "--dump-json", "--no-download", url],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass
        return {"id": url, "title": url}

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
