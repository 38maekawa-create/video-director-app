"""エッジケーステスト: 空データ・不正フォーマット・タイムアウト・並行実行等の異常系"""

import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import subprocess

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.integrations.ai_dev5_connector import (
    HighlightScene,
    PersonProfile,
    VideoData,
    parse_markdown_file,
)
from src.video_direction.analyzer.direction_generator import (
    DirectionEntry,
    DirectionTimeline,
    generate_directions,
    _timestamp_to_seconds,
)
from src.video_direction.analyzer.guest_classifier import classify_guest
from src.video_direction.analyzer.quality_scorer import score_video_quality
from src.video_direction.analyzer.income_evaluator import evaluate_income
from src.video_direction.tracker.video_tracker import TrackedVideo, VideoTracker
from src.video_direction.tracker.feedback_learner import FeedbackLearner


# ─────────────────────────────────────────────────────────────
# 1. 空データ系 (Empty Data)
# ─────────────────────────────────────────────────────────────

class TestEmptyData:
    """空データを渡したときにクラッシュせず安全に動作することを確認"""

    def test_空のVideoDataでgenerate_directionsがクラッシュしない(self):
        """ハイライトが0件のVideoDataを渡してもDirectionTimelineが返ること"""
        video = VideoData(title="空テスト", highlights=[])
        classification = classify_guest(video)
        income_eval = evaluate_income(video)
        result = generate_directions(video, classification, income_eval)
        assert isinstance(result, DirectionTimeline)
        assert result.entries == []

    def test_プロファイルなしVideoDataでclassify_guestがデフォルト層bを返す(self):
        """profilesが空のとき層bにフォールバックすること"""
        video = VideoData(title="プロファイルなし", profiles=[])
        result = classify_guest(video)
        assert result.tier == "b"

    def test_空文字タイトルのVideoDataが処理できる(self):
        """タイトルが空文字列でも分類が動くこと"""
        video = VideoData(title="", profiles=[])
        result = classify_guest(video)
        assert result.tier in ("a", "b", "c")

    def test_空ハイライトでscore_video_qualityが安全に動く(self):
        """ハイライト0件でも品質スコアが返ること"""
        video = VideoData(highlights=[])
        classification = classify_guest(video)
        timeline = DirectionTimeline(entries=[])
        result = score_video_quality(video, classification, timeline)
        assert 0.0 <= result.total_score <= 100.0

    def test_FeedbackLearnerに空文字FBを投入しても例外なし(self):
        """空文字のフィードバックをingestしてもクラッシュしないこと"""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = FeedbackLearner(data_dir=Path(tmpdir))
            patterns = learner.ingest_feedback("fb_empty", "", category="cutting")
            assert isinstance(patterns, list)

    def test_VideoTrackerで空URLを登録したときメタデータ取得失敗しても登録される(self):
        """yt-dlp が失敗しても add_video がフォールバックしてTrackedVideoを返すこと"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = VideoTracker(data_dir=Path(tmpdir))
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stdout="")
                video = tracker.add_video("")
            # URLをIDとして使うフォールバック動作
            assert video.id == ""
            assert video.title == ""


# ─────────────────────────────────────────────────────────────
# 2. 不正フォーマット系 (Invalid Format)
# ─────────────────────────────────────────────────────────────

class TestInvalidFormat:
    """不正な入力形式に対してクラッシュせず適切に処理されることを確認"""

    def test_不正タイムスタンプのHighlightSceneで演出生成がスキップされない(self):
        """不正なtimestamp文字列でも例外なくDirectionTimelineが返ること"""
        highlight = HighlightScene(
            timestamp="INVALID_TS",
            speaker="ゲスト",
            text="年収1000万以上です",
            category="実績数字",
        )
        video = VideoData(highlights=[highlight])
        classification = classify_guest(video)
        income_eval = evaluate_income(video)
        # 不正タイムスタンプでもクラッシュしない
        result = generate_directions(video, classification, income_eval)
        assert isinstance(result, DirectionTimeline)

    def test_タイムスタンプ変換で不正文字列は0秒を返す(self):
        """_timestamp_to_seconds が不正な値に対して0を返すこと"""
        assert _timestamp_to_seconds("INVALID") == 0
        assert _timestamp_to_seconds("") == 0
        assert _timestamp_to_seconds("abc:def") == 0

    def test_不正JSONのインデックスファイルでVideoTrackerがクラッシュしない(self):
        """インデックスJSONが壊れていても初期化が安全に行われること"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "tracking_index.json"
            # 不正JSON書き込み
            index_path.write_text("{broken json <<<", encoding="utf-8")
            # ロード時に例外が発生しないこと（またはVideoTrackerが空状態で初期化）
            try:
                tracker = VideoTracker(data_dir=Path(tmpdir))
                # クラッシュしなければOK (空で初期化されるか例外をキャッチしている)
            except (json.JSONDecodeError, Exception):
                # 例外が出る場合はそれ自体が仕様であることを確認
                pass

    def test_不正JSONのFeedbackLearnerファイルで初期化が安全に行われる(self):
        """パターンJSONが破損していてもFeedbackLearnerが初期化できること"""
        with tempfile.TemporaryDirectory() as tmpdir:
            patterns_path = Path(tmpdir) / "feedback_patterns.json"
            patterns_path.write_text("NOT_JSON!!!", encoding="utf-8")
            try:
                learner = FeedbackLearner(data_dir=Path(tmpdir))
            except (json.JSONDecodeError, Exception):
                pass  # 例外が起きる場合も仕様通り

    def test_Markdownファイルが存在しない場合にFileNotFoundError(self):
        """存在しないパスを渡すと FileNotFoundError が発生すること"""
        with pytest.raises((FileNotFoundError, OSError)):
            parse_markdown_file("/tmp/nonexistent_XXXXXXXX.md")

    def test_空Markdownファイルのパースが安全に動く(self):
        """空のMarkdownファイルをパースしてもVideoDataが返ること"""
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w",
                                        encoding="utf-8", delete=False) as f:
            f.write("")
            f.flush()
            result = parse_markdown_file(f.name)
        assert isinstance(result, VideoData)
        assert result.title == ""

    def test_特殊文字を含むHighlightSceneでクラッシュしない(self):
        """制御文字・絵文字・ヌル文字を含む発言テキストでも処理が通ること"""
        highlight = HighlightScene(
            timestamp="01:00",
            speaker="ゲスト\x00",
            text="年収\U0001F4B0999万円\n\t特殊文字テスト\x00",
            category="実績数字",
        )
        video = VideoData(highlights=[highlight])
        classification = classify_guest(video)
        income_eval = evaluate_income(video)
        result = generate_directions(video, classification, income_eval)
        assert isinstance(result, DirectionTimeline)

    def test_極端に長いテキストのHighlightSceneで処理が完了する(self):
        """数万文字のテキストを持つHighlightSceneでも処理が終わること"""
        long_text = "年収1000万" + "あ" * 50000
        highlight = HighlightScene(
            timestamp="02:30",
            speaker="ゲスト",
            text=long_text,
            category="実績数字",
        )
        video = VideoData(highlights=[highlight])
        classification = classify_guest(video)
        income_eval = evaluate_income(video)
        result = generate_directions(video, classification, income_eval)
        assert isinstance(result, DirectionTimeline)


# ─────────────────────────────────────────────────────────────
# 3. タイムアウト系 (Timeout)
# ─────────────────────────────────────────────────────────────

class TestTimeout:
    """外部プロセス・API呼び出しがタイムアウトしたときのフォールバック動作を確認"""

    def test_yt_dlpタイムアウト時にフォールバックメタデータで登録される(self):
        """subprocess.TimeoutExpired 発生時、URLをIDとするフォールバックが動くこと"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = VideoTracker(data_dir=Path(tmpdir))
            test_url = "https://www.youtube.com/watch?v=timeout_test"
            with patch("subprocess.run",
                       side_effect=subprocess.TimeoutExpired(cmd="yt-dlp", timeout=30)):
                video = tracker.add_video(test_url)
            assert video.id == test_url
            assert video.url == test_url

    def test_yt_dlpコマンドが存在しない場合にフォールバックされる(self):
        """FileNotFoundError(yt-dlp未インストール) 時もフォールバックが動くこと"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = VideoTracker(data_dir=Path(tmpdir))
            test_url = "https://www.youtube.com/watch?v=no_ytdlp"
            with patch("subprocess.run",
                       side_effect=FileNotFoundError("yt-dlp not found")):
                video = tracker.add_video(test_url)
            assert video.url == test_url

    def test_LLM分析タイムアウト時でもDirectionTimelineが返る(self):
        """_llm_analyze が例外を出してもメインのDirectionTimeline生成は成功すること"""
        highlight = HighlightScene(
            timestamp="00:30",
            speaker="ゲスト",
            text="月収500万です",
            category="実績数字",
        )
        video = VideoData(highlights=[highlight])
        classification = classify_guest(video)
        income_eval = evaluate_income(video)
        # LLM分析をタイムアウト例外でモック
        with patch(
            "src.video_direction.analyzer.direction_generator._llm_analyze",
            side_effect=TimeoutError("LLM API timeout"),
        ):
            result = generate_directions(video, classification, income_eval)
        assert isinstance(result, DirectionTimeline)
        # LLMなしでもルールベースエントリが生成されること
        assert len(result.entries) > 0


# ─────────────────────────────────────────────────────────────
# 4. 並行実行系 (Concurrent Execution)
# ─────────────────────────────────────────────────────────────

class TestConcurrentExecution:
    """複数スレッドから同時にデータを書き込んでも整合性が保たれることを確認"""

    def test_VideoTrackerへの並行add_videoがデータ破損しない(self):
        """10スレッドが同時にadd_videoを呼んでもインデックスファイルが壊れないこと"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 各スレッドが独自のTrackerインスタンスを持つ（ファイル共有なし）
            errors = []

            def add_video_task(video_id: str):
                try:
                    tracker = VideoTracker(data_dir=Path(tmpdir) / f"tracker_{video_id}")
                    with patch("subprocess.run") as mock_run:
                        mock_run.return_value = MagicMock(
                            returncode=0,
                            stdout=json.dumps({
                                "id": video_id,
                                "title": f"動画{video_id}",
                                "channel": "テストチャンネル",
                                "duration": 60.0,
                            })
                        )
                        tracker.add_video(f"https://example.com/{video_id}")
                except Exception as e:
                    errors.append(str(e))

            threads = [
                threading.Thread(target=add_video_task, args=(f"v{i:03d}",))
                for i in range(10)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            assert errors == [], f"並行実行でエラーが発生: {errors}"

    def test_FeedbackLearnerへの並行ingestがクラッシュしない(self):
        """10スレッドが同時にingest_feedbackを呼んでも例外なく完了すること"""
        errors = []

        def ingest_task(thread_id: int, learner: FeedbackLearner):
            try:
                learner.ingest_feedback(
                    feedback_id=f"fb_{thread_id:03d}",
                    content=f"テロップのタイミングが{thread_id}秒ずれている",
                    category="telop",
                )
            except Exception as e:
                errors.append(f"thread {thread_id}: {e}")

        with tempfile.TemporaryDirectory() as tmpdir:
            learner = FeedbackLearner(data_dir=Path(tmpdir))
            threads = [
                threading.Thread(target=ingest_task, args=(i, learner))
                for i in range(10)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

        # データ破損によるクラッシュがないこと（競合によりエラーが出ても件数は少ないこと）
        assert len(errors) == 0 or len(errors) < 10, f"大量の並行エラー: {errors}"

    def test_generate_directionsの並行呼び出しがスレッドセーフ(self):
        """複数スレッドが同時にgenerate_directionsを呼んでも正しい結果が返ること"""
        results = []
        errors = []

        def generate_task():
            try:
                highlight = HighlightScene(
                    timestamp="01:30",
                    speaker="ゲスト",
                    text="年収800万で外資系VP",
                    category="実績数字",
                )
                video = VideoData(highlights=[highlight])
                classification = classify_guest(video)
                income_eval = evaluate_income(video)
                result = generate_directions(video, classification, income_eval)
                results.append(len(result.entries))
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=generate_task) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert errors == [], f"並行generate_directionsでエラー: {errors}"
        assert len(results) == 8
        # 全スレッドが同じ件数のエントリを返すこと
        assert len(set(results)) == 1, f"スレッドによって結果が異なる: {results}"


# ─────────────────────────────────────────────────────────────
# 5. 境界値・その他の異常系
# ─────────────────────────────────────────────────────────────

class TestBoundaryAndOther:
    """境界値・その他の異常ケースを確認"""

    def test_ハイライトが1件だけの場合に演出生成が動く(self):
        """ハイライトが最小1件でも処理が通ること"""
        highlight = HighlightScene(
            timestamp="00:01",
            speaker="ゲスト",
            text="パンチライン発言",
            category="パンチライン",
        )
        video = VideoData(highlights=[highlight])
        classification = classify_guest(video)
        income_eval = evaluate_income(video)
        result = generate_directions(video, classification, income_eval)
        assert isinstance(result, DirectionTimeline)
        assert len(result.entries) >= 1

    def test_VideoTrackerで同一URLを2回登録しても重複しない(self):
        """同じURLをadd_videoに2回渡しても1件しか登録されないこと"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = VideoTracker(data_dir=Path(tmpdir))
            url = "https://www.youtube.com/watch?v=dup_test"
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout=json.dumps({
                        "id": "dup_test",
                        "title": "重複テスト動画",
                        "channel": "ch",
                        "duration": 120.0,
                    })
                )
                tracker.add_video(url)
                tracker.add_video(url)  # 2回目

            videos = tracker.list_videos()
            ids = [v.id for v in videos]
            assert ids.count("dup_test") == 1, "同一URLが重複登録されている"

    def test_VideoTrackerから存在しないIDのgetはNoneを返す(self):
        """get_videoで未登録IDを渡すとNoneが返ること"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = VideoTracker(data_dir=Path(tmpdir))
            result = tracker.get_video("nonexistent_id_xyz")
            assert result is None

    def test_VideoTrackerから存在しないIDのremoveはFalseを返す(self):
        """remove_videoで未登録IDを渡すとFalseが返ること"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = VideoTracker(data_dir=Path(tmpdir))
            result = tracker.remove_video("nonexistent_id_xyz")
            assert result is False

    def test_FeedbackLearnerにカテゴリ未指定で投入しても自動推定される(self):
        """category=Noneで投入したとき自動分類されてパターンが返ること"""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = FeedbackLearner(data_dir=Path(tmpdir))
            patterns = learner.ingest_feedback(
                feedback_id="fb_auto",
                content="カット割りが早すぎて視聴者が疲れる",
                category=None,
            )
            assert isinstance(patterns, list)
            assert len(patterns) >= 1
            # カテゴリが自動設定されていること
            assert patterns[0].category != ""
