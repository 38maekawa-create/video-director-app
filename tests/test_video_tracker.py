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


# ────────────────────────────────────────────────
# VideoTracker — バッチ登録
# ────────────────────────────────────────────────

class TestVideoTrackerBatch:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.tracker = VideoTracker(data_dir=self.tmp)

    def _mock_fetch(self, url):
        # URLからIDを抽出
        vid = url.split("=")[-1] if "=" in url else url[-5:]
        return {"id": vid, "title": f"動画_{vid}", "channel": "テストch", "duration": 300.0}

    def test_バッチ登録で複数動画を一括追加できる(self):
        urls = [
            "https://example.com/watch?v=aaa",
            "https://example.com/watch?v=bbb",
            "https://example.com/watch?v=ccc",
        ]
        with patch.object(self.tracker, "_fetch_metadata", side_effect=self._mock_fetch):
            results = self.tracker.add_videos_batch(urls, tags=["テスト"])
        assert len(results) == 3
        assert len(self.tracker.list_videos()) == 3

    def test_バッチ登録でタグが全動画に付与される(self):
        urls = ["https://example.com/watch?v=x1", "https://example.com/watch?v=x2"]
        with patch.object(self.tracker, "_fetch_metadata", side_effect=self._mock_fetch):
            results = self.tracker.add_videos_batch(urls, tags=["共通タグ"])
        assert all("共通タグ" in v.tags for v in results)

    def test_バッチ登録で1件失敗しても他は成功する(self):
        def _flaky_fetch(url):
            if "bad" in url:
                raise Exception("取得失敗")
            return self._mock_fetch(url)

        urls = [
            "https://example.com/watch?v=ok1",
            "https://example.com/watch?v=bad",
            "https://example.com/watch?v=ok2",
        ]
        with patch.object(self.tracker, "_fetch_metadata", side_effect=_flaky_fetch):
            results = self.tracker.add_videos_batch(urls)
        # 3件返される（1件はerrorステータス）
        assert len(results) == 3
        errors = [r for r in results if r.analysis_status == "error"]
        assert len(errors) == 1


# ────────────────────────────────────────────────
# VideoTracker — 新フィールド
# ────────────────────────────────────────────────

class TestTrackedVideoNewFields:
    def test_新フィールドのデフォルト値(self):
        v = TrackedVideo(id="v_new", url="https://example.com", title="新規")
        assert v.view_count == 0
        assert v.upload_date == ""
        assert v.description == ""
        assert v.transcript == ""

    def test_transcriptを設定できる(self):
        v = TrackedVideo(id="v_tr", url="https://example.com", title="字幕テスト")
        v.transcript = "話者A: テスト発言\n話者B: 返答"
        assert "話者A" in v.transcript


# ────────────────────────────────────────────────
# VideoTracker — VTT/SRTパース
# ────────────────────────────────────────────────

class TestSubtitleParsing:
    def test_VTTパースでテキスト部分のみ抽出(self):
        vtt = """WEBVTT

00:00:01.000 --> 00:00:03.000
こんにちは

00:00:04.000 --> 00:00:06.000
テストです
"""
        result = VideoTracker._parse_vtt(vtt)
        assert "こんにちは" in result
        assert "テストです" in result
        assert "-->" not in result
        assert "WEBVTT" not in result

    def test_VTTパースでHTMLタグを除去(self):
        vtt = """WEBVTT

00:00:01.000 --> 00:00:03.000
<b>太字</b>テキスト
"""
        result = VideoTracker._parse_vtt(vtt)
        assert "<b>" not in result
        assert "太字テキスト" in result

    def test_SRTパースでテキスト部分のみ抽出(self):
        srt = """1
00:00:01,000 --> 00:00:03,000
最初の字幕

2
00:00:04,000 --> 00:00:06,000
二番目の字幕
"""
        result = VideoTracker._parse_srt(srt)
        assert "最初の字幕" in result
        assert "二番目の字幕" in result
        assert "-->" not in result


# ────────────────────────────────────────────────
# VideoTracker — ステータスサマリー
# ────────────────────────────────────────────────

class TestStatusSummary:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.tracker = VideoTracker(data_dir=self.tmp)
        # テストデータ追加
        for i, status in enumerate(["pending", "completed", "completed"]):
            v = TrackedVideo(
                id=f"v{i}", url=f"https://example.com/{i}",
                title=f"動画{i}", channel_name="テストch",
                analysis_status=status, tags=["タグA"],
            )
            self.tracker._videos[v.id] = v

    def test_サマリーが正しい件数を返す(self):
        summary = self.tracker.get_status_summary()
        assert summary["total_videos"] == 3
        assert summary["status_counts"]["pending"] == 1
        assert summary["status_counts"]["completed"] == 2

    def test_チャンネル一覧が含まれる(self):
        summary = self.tracker.get_status_summary()
        assert "テストch" in summary["channels"]

    def test_タグ一覧が含まれる(self):
        summary = self.tracker.get_status_summary()
        assert "タグA" in summary["tags"]
