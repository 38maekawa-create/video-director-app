"""
APIサーバー (api_server.py) のユニットテスト
- /api/v1/projects/{id}/feedbacks-with-timecodes エンドポイント
- タイムコードフィルタリング・ソート
- フィードバック新規保存 (POST)
"""

import json
import os
import sys
import tempfile
import uuid
from unittest.mock import patch

import pytest

# パスを通す
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.video_direction.api_server import (
    _get_sample_feedbacks,
    get_feedbacks_by_project,
    save_feedback,
)


# ---------------------------------------------------------------------------
# フィードバック取得テスト
# ---------------------------------------------------------------------------


class TestGetFeedbacksByProject:
    """get_feedbacks_by_project のテスト"""

    def test_空プロジェクトはサンプルデータを返す(self):
        """DBに存在しないプロジェクトIDはサンプルデータにフォールバックする"""
        with patch(
            "src.video_direction.api_server._load_feedback_store",
            return_value={},
        ):
            feedbacks = get_feedbacks_by_project("unknown_project")

        assert len(feedbacks) > 0, "サンプルデータが1件以上返ること"

    def test_timestamp_mark昇順でソートされる(self):
        """返却フィードバック一覧が timestamp_mark 昇順になること"""
        # 逆順でストアに保存
        unsorted = [
            {"id": str(uuid.uuid4()), "timestamp_mark": 300.0, "element": "BGM",
             "priority": "中", "note": "テスト", "vimeo_video_id": "v1"},
            {"id": str(uuid.uuid4()), "timestamp_mark": 12.0, "element": "カット割り",
             "priority": "高", "note": "テスト", "vimeo_video_id": "v1"},
            {"id": str(uuid.uuid4()), "timestamp_mark": 78.0, "element": "テロップ",
             "priority": "高", "note": "テスト", "vimeo_video_id": "v1"},
        ]

        with patch(
            "src.video_direction.api_server._load_feedback_store",
            return_value={"proj_1": unsorted},
        ):
            result = get_feedbacks_by_project("proj_1")

        timestamps = [fb["timestamp_mark"] for fb in result]
        assert timestamps == sorted(timestamps), "timestamp_mark が昇順にソートされていること"

    def test_特定プロジェクトのFBのみ返る(self):
        """指定プロジェクトのフィードバックのみが返ること"""
        store = {
            "proj_A": [{"id": "a1", "timestamp_mark": 10.0, "element": "テロップ",
                         "priority": "高", "note": "A", "vimeo_video_id": "v1"}],
            "proj_B": [{"id": "b1", "timestamp_mark": 20.0, "element": "BGM",
                         "priority": "中", "note": "B", "vimeo_video_id": "v2"}],
        }
        with patch(
            "src.video_direction.api_server._load_feedback_store",
            return_value=store,
        ):
            result = get_feedbacks_by_project("proj_A")

        assert len(result) == 1
        assert result[0]["id"] == "a1"


# ---------------------------------------------------------------------------
# サンプルデータテスト
# ---------------------------------------------------------------------------


class TestGetSampleFeedbacks:
    """_get_sample_feedbacks のテスト"""

    def test_必要なフィールドがすべて含まれる(self):
        """各フィードバックに必須フィールドが揃っていること"""
        required_fields = {
            "id", "timestamp_mark", "element", "priority", "note", "vimeo_video_id"
        }
        feedbacks = _get_sample_feedbacks("test_proj")
        for fb in feedbacks:
            missing = required_fields - set(fb.keys())
            assert not missing, f"不足フィールド: {missing}"

    def test_timestamp_markが数値(self):
        """timestamp_mark が float であること"""
        feedbacks = _get_sample_feedbacks("test_proj")
        for fb in feedbacks:
            assert isinstance(fb["timestamp_mark"], float), \
                f"timestamp_mark は float であること: {fb['timestamp_mark']}"

    def test_priorityが正しい値(self):
        """priority が '高' / '中' / '低' のいずれかであること"""
        valid_priorities = {"高", "中", "低"}
        feedbacks = _get_sample_feedbacks("test_proj")
        for fb in feedbacks:
            assert fb["priority"] in valid_priorities, \
                f"不正な priority: {fb['priority']}"

    def test_各FBにuuidが付与される(self):
        """各フィードバックに一意のIDが付与されること"""
        feedbacks = _get_sample_feedbacks("test_proj")
        ids = [fb["id"] for fb in feedbacks]
        assert len(ids) == len(set(ids)), "IDが重複していないこと"


# ---------------------------------------------------------------------------
# タイムコードフィルタリングテスト
# ---------------------------------------------------------------------------


class TestTimecodeFiltering:
    """タイムコードによるフィルタリング・ソートのテスト"""

    def _make_feedback(self, ts: float, priority: str = "中") -> dict:
        return {
            "id": str(uuid.uuid4()),
            "timestamp_mark": ts,
            "element": "テロップ",
            "priority": priority,
            "note": "テストノート",
            "vimeo_video_id": "v123",
        }

    def test_タイムコード範囲フィルタリング(self):
        """開始・終了タイムコードで絞り込みができること"""
        feedbacks = [
            self._make_feedback(10.0),   # 範囲外（前）
            self._make_feedback(60.0),   # 範囲内
            self._make_feedback(120.0),  # 範囲内
            self._make_feedback(200.0),  # 範囲外（後）
        ]

        start, end = 30.0, 150.0
        filtered = [fb for fb in feedbacks if start <= fb["timestamp_mark"] <= end]

        assert len(filtered) == 2
        timestamps = [fb["timestamp_mark"] for fb in filtered]
        assert 60.0 in timestamps
        assert 120.0 in timestamps

    def test_ゼロ秒のFBが含まれる(self):
        """timestamp_mark = 0 のフィードバックがソート後先頭になること"""
        feedbacks = [
            self._make_feedback(100.0),
            self._make_feedback(0.0),
            self._make_feedback(50.0),
        ]
        sorted_feedbacks = sorted(feedbacks, key=lambda x: x["timestamp_mark"])
        assert sorted_feedbacks[0]["timestamp_mark"] == 0.0

    def test_同一タイムコードは安定ソート(self):
        """同じ timestamp_mark でも元の順序が保たれること（安定ソート）"""
        feedbacks = [
            {**self._make_feedback(30.0), "note": "first"},
            {**self._make_feedback(30.0), "note": "second"},
        ]
        sorted_feedbacks = sorted(feedbacks, key=lambda x: x["timestamp_mark"])
        # Pythonのsortは安定ソートなので元の順序が維持される
        assert sorted_feedbacks[0]["note"] == "first"
        assert sorted_feedbacks[1]["note"] == "second"


# ---------------------------------------------------------------------------
# フィードバック保存テスト
# ---------------------------------------------------------------------------


class TestSaveFeedback:
    """save_feedback のテスト"""

    def test_IDなしFBにuuidが付与される(self, tmp_path):
        """id が空のフィードバックに UUID が自動付与されること"""
        store_path = str(tmp_path / "store.json")
        feedback = {
            "timestamp_mark": 45.0,
            "element": "BGM",
            "priority": "中",
            "note": "テスト",
            "vimeo_video_id": "v456",
        }

        with patch("src.video_direction.api_server._FEEDBACK_STORE_PATH", store_path):
            saved = save_feedback("proj_test", feedback)

        assert "id" in saved
        assert saved["id"] != ""
        # UUID形式の簡易検証
        try:
            uuid.UUID(saved["id"])
        except ValueError:
            pytest.fail("付与されたIDがUUID形式でない")

    def test_既存IDはそのまま保持される(self, tmp_path):
        """既にIDが付与されているFBは上書きされないこと"""
        store_path = str(tmp_path / "store.json")
        existing_id = str(uuid.uuid4())
        feedback = {
            "id": existing_id,
            "timestamp_mark": 90.0,
            "element": "カット割り",
            "priority": "高",
            "note": "既存IDテスト",
            "vimeo_video_id": "v789",
        }

        with patch("src.video_direction.api_server._FEEDBACK_STORE_PATH", store_path):
            saved = save_feedback("proj_test", feedback)

        assert saved["id"] == existing_id, "既存IDが変更されていないこと"

    def test_保存後に読み込みで取得できる(self, tmp_path):
        """保存したFBがget_feedbacks_by_projectで取得できること"""
        store_path = str(tmp_path / "store.json")
        feedback = {
            "timestamp_mark": 55.0,
            "element": "テロップ",
            "priority": "低",
            "note": "保存後取得テスト",
            "vimeo_video_id": "vX",
        }

        with patch("src.video_direction.api_server._FEEDBACK_STORE_PATH", store_path):
            saved = save_feedback("proj_read_test", feedback)
            results = get_feedbacks_by_project("proj_read_test")

        ids_in_results = [fb["id"] for fb in results]
        assert saved["id"] in ids_in_results, "保存したFBが取得できること"
