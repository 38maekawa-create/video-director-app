"""VideoTracker / TrackedVideo のユニットテスト（外部API・yt-dlp不要）"""

import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.tracker.video_tracker import TrackedVideo, VideoTracker


# ────────────────────────────────────────────────
# TrackedVideo データクラス
# ────────────────────────────────────────────────

class TestTrackedVideo:
    def test_最低限のフィールドで生成できる(self):
        v = TrackedVideo(id="v001", url="https://example.com", title="テスト動画")
        assert v.id == "v001"
        assert v.url == "https://example.com"
        assert v.title == "テスト動画"

    def test_デフォルト値が正しく設定される(self):
        v = TrackedVideo(id="v002", url="https://example.com", title="動画B")
        assert v.channel_name == ""
        assert v.thumbnail_url == ""
        assert v.duration_seconds == 0.0
        assert v.analysis_status == "pending"
        assert v.analysis_result is None
        assert v.tags == []

    def test_タグを指定して生成できる(self):
        v = TrackedVideo(id="v003", url="https://example.com", title="タグ付き", tags=["不動産", "投資"])
        assert "不動産" in v.tags
        assert "投資" in v.tags

    def test_created_atがISO形式で自動設定される(self):
        v = TrackedVideo(id="v004", url="https://example.com", title="日時テスト")
        # ISO 8601 形式かどうか確認
        datetime.fromisoformat(v.created_at)

    def test_analysis_resultにdictを設定できる(self):
        v = TrackedVideo(id="v005", url="https://example.com", title="結果あり")
        v.analysis_result = {"score": 0.9, "comment": "良い動画"}
        assert v.analysis_result["score"] == 0.9


# ────────────────────────────────────────────────
# VideoTracker — 初期化・インデックス管理
# ────────────────────────────────────────────────

class TestVideoTrackerInit:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.tracker = VideoTracker(data_dir=self.tmp)

    def test_初期化で空のリストになる(self):
        assert self.tracker.list_videos() == []

    def test_インデックスファイルが存在しない場合も初期化成功(self):
        assert not (self.tmp / "tracking_index.json").exists()
        tracker2 = VideoTracker(data_dir=self.tmp)
        assert tracker2.list_videos() == []

    def test_インデックスファイルを読み込んで復元する(self):
        """既存インデックスがあれば復元されること"""
        index_data = {
            "videos": [
                {
                    "id": "existing_v1",
                    "url": "https://example.com/v1",
                    "title": "既存動画",
                    "channel_name": "テストch",
                    "thumbnail_url": "",
                    "duration_seconds": 300.0,
                    "analysis_status": "completed",
                    "analysis_result": None,
                    "tags": [],
                    "created_at": "2026-01-01T00:00:00",
                    "updated_at": "2026-01-01T00:00:00",
                }
            ],
            "updated_at": "2026-01-01T00:00:00",
        }
        (self.tmp / "tracking_index.json").write_text(
            json.dumps(index_data, ensure_ascii=False)
        )
        tracker2 = VideoTracker(data_dir=self.tmp)
        videos = tracker2.list_videos()
        assert len(videos) == 1
        assert videos[0].id == "existing_v1"


# ────────────────────────────────────────────────
# VideoTracker — add_video / get_video
# ────────────────────────────────────────────────

class TestVideoTrackerAddVideo:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.tracker = VideoTracker(data_dir=self.tmp)

    def _mock_fetch(self, url):
        return {"id": "mock_id", "title": "モックタイトル", "channel": "モックch", "duration": 600.0}

    def test_動画を追加できる(self):
        with patch.object(self.tracker, "_fetch_metadata", side_effect=self._mock_fetch):
            video = self.tracker.add_video("https://example.com/watch?v=abc", tags=["テスト"])
        assert video.id == "mock_id"
        assert video.title == "モックタイトル"
        assert "テスト" in video.tags

    def test_同じIDの動画は重複追加されない(self):
        with patch.object(self.tracker, "_fetch_metadata", side_effect=self._mock_fetch):
            v1 = self.tracker.add_video("https://example.com/watch?v=abc")
            v2 = self.tracker.add_video("https://example.com/watch?v=abc")
        assert v1.id == v2.id
        assert len(self.tracker.list_videos()) == 1

    def test_追加後にget_videoで取得できる(self):
        with patch.object(self.tracker, "_fetch_metadata", side_effect=self._mock_fetch):
            self.tracker.add_video("https://example.com/watch?v=abc")
        video = self.tracker.get_video("mock_id")
        assert video is not None
        assert video.title == "モックタイトル"

    def test_存在しないIDでget_videoはNoneを返す(self):
        result = self.tracker.get_video("nonexistent_id")
        assert result is None


# ────────────────────────────────────────────────
# VideoTracker — list_videos / update / remove
# ────────────────────────────────────────────────

class TestVideoTrackerOperations:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.tracker = VideoTracker(data_dir=self.tmp)
        # 2件登録
        for i in range(2):
            v = TrackedVideo(
                id=f"v{i}",
                url=f"https://example.com/{i}",
                title=f"動画{i}",
                analysis_status="pending" if i == 0 else "completed",
            )
            self.tracker._videos[v.id] = v
        self.tracker._save_index()

    def test_list_videosで全件取得できる(self):
        assert len(self.tracker.list_videos()) == 2

    def test_statusフィルタでpendingのみ取得できる(self):
        pending = self.tracker.list_videos(status="pending")
        assert all(v.analysis_status == "pending" for v in pending)
        assert len(pending) == 1

    def test_update_analysisで分析結果を更新できる(self):
        self.tracker.update_analysis("v0", result={"score": 0.8}, status="completed")
        v = self.tracker.get_video("v0")
        assert v.analysis_status == "completed"
        assert v.analysis_result["score"] == 0.8

    def test_存在しないIDのupdate_analysisは無視される(self):
        # 例外が発生しないことを確認
        self.tracker.update_analysis("no_such_id", result={})

    def test_remove_videoで削除できる(self):
        result = self.tracker.remove_video("v0")
        assert result is True
        assert self.tracker.get_video("v0") is None

    def test_存在しないIDのremove_videoはFalseを返す(self):
        result = self.tracker.remove_video("no_such_id")
        assert result is False


# ────────────────────────────────────────────────
# VideoTracker — _fetch_metadata フォールバック
# ────────────────────────────────────────────────

class TestFetchMetadataFallback:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.tracker = VideoTracker(data_dir=self.tmp)

    def test_yt_dlpが見つからない場合はURLをidとして返す(self):
        import subprocess
        with patch("subprocess.run", side_effect=FileNotFoundError):
            meta = self.tracker._fetch_metadata("https://example.com/v=xyz")
        assert meta["id"] == "https://example.com/v=xyz"
        assert meta["title"] == "https://example.com/v=xyz"

    def test_yt_dlpがタイムアウトした場合はフォールバックを返す(self):
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("yt-dlp", 30)):
            meta = self.tracker._fetch_metadata("https://example.com/timeout")
        assert meta["id"] == "https://example.com/timeout"
