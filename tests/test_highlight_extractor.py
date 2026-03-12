"""highlight_extractor（NEW-2: ハイライトカットポイント）のユニットテスト"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.video_direction.integrations.ai_dev5_connector import (
    VideoData, HighlightScene, parse_markdown_file,
)
from src.video_direction.analyzer.target_labeler import (
    label_targets, TargetLabelResult, SceneLabel,
)
from src.video_direction.analyzer.highlight_extractor import (
    extract_highlights,
    HighlightExtractorResult,
    HighlightCutPoint,
    TierRepresentatives,
    HighlightSequence,
    _ts_to_seconds,
    _seconds_to_ts,
    _calc_priority_score,
    _extract_timestamps_from_transcript,
    _find_nearest_timestamp,
)


# テスト用サンプルファイル
SAMPLE_FILES = {
    "izu": Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_Izuさん：30代中盤元アクセンチュア年収1000万円台.md",
    "ryosuke": Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_りょうすけさん：20代後半内資IT勤務年収600万.md",
}


class TestTimestampUtils:
    """タイムスタンプユーティリティのテスト"""

    def test_ts_to_seconds(self):
        assert _ts_to_seconds("02:30") == 150
        assert _ts_to_seconds("00:00") == 0

    def test_seconds_to_ts(self):
        assert _seconds_to_ts(150) == "02:30"
        assert _seconds_to_ts(0) == "00:00"

    def test_extract_timestamps(self):
        """トランスクリプトからタイムスタンプを抽出"""
        transcript = "[02:30] 前川: テスト\n[05:00] Izu: テスト\n[10:00] 前川: テスト"
        timestamps = _extract_timestamps_from_transcript(transcript)
        assert 150 in timestamps
        assert 300 in timestamps
        assert 600 in timestamps

    def test_find_nearest_before(self):
        """前方の最も近いタイムスタンプを探す"""
        timestamps = [0, 60, 120, 180, 240]
        result = _find_nearest_timestamp(timestamps, 150, "before")
        assert result == 120

    def test_find_nearest_after(self):
        """後方の最も近いタイムスタンプを探す"""
        timestamps = [0, 60, 120, 180, 240]
        result = _find_nearest_timestamp(timestamps, 150, "after")
        assert result == 180

    def test_find_nearest_empty(self):
        """空リストからの検索"""
        assert _find_nearest_timestamp([], 100, "before") is None
        assert _find_nearest_timestamp([], 100, "after") is None


class TestPriorityScoring:
    """優先度スコアリングのテスト"""

    def test_high_priority_scene(self):
        """実績数字+両層向けは高スコア"""
        scene = SceneLabel(
            timestamp="05:00",
            speaker="テスト",
            text="年収1500万円で独立しました",
            target_tier="both",
            tier_label="両層向け",
            reason="テスト",
            emotional_hook="焦燥感+共感",
        )
        score = _calc_priority_score(scene, "実績数字")
        assert score > 0.5, f"高優先度シーンのスコアが低い: {score}"

    def test_low_priority_scene(self):
        """メッセージ+tier2は低めのスコア"""
        scene = SceneLabel(
            timestamp="05:00",
            speaker="テスト",
            text="ありがとうございました",
            target_tier="tier2",
            tier_label="2層向け",
            reason="テスト",
            emotional_hook="共感・安心感",
        )
        score = _calc_priority_score(scene, "メッセージ")
        assert score < 0.7, f"低優先度シーンのスコアが高い: {score}"


class TestHighlightExtraction:
    """ハイライト抽出のテスト"""

    def _make_test_data(self):
        """テスト用データ生成"""
        video_data = VideoData(
            title="テスト動画",
            duration="30分",
            highlights=[
                HighlightScene("02:30", "Izu", "年収1500万円です", "実績数字"),
                HighlightScene("05:00", "Izu", "独立して人生変わりました", "パンチライン"),
                HighlightScene("10:00", "前川", "TEKOの価値", "TEKO価値"),
                HighlightScene("15:00", "Izu", "仲間が大事", "メッセージ"),
                HighlightScene("20:00", "Izu", "元アクセンチュア", "属性紹介"),
            ],
            full_transcript=(
                "[02:30] Izu: 年収1500万円です。\n"
                "[05:00] Izu: 独立して人生変わりました。\n"
                "[10:00] 前川: TEKOの価値。\n"
                "[15:00] Izu: 仲間が大事。\n"
                "[20:00] Izu: 元アクセンチュアです。\n"
            ),
        )
        target_result = label_targets(video_data)
        return video_data, target_result

    def test_basic_extraction(self):
        """基本的なハイライト抽出"""
        video_data, target_result = self._make_test_data()
        result = extract_highlights(video_data, target_result)
        assert isinstance(result, HighlightExtractorResult)
        assert len(result.cut_points) > 0, "カットポイントが生成されるべき"

    def test_cut_points_have_required_fields(self):
        """カットポイントに必要なフィールドがある"""
        video_data, target_result = self._make_test_data()
        result = extract_highlights(video_data, target_result)
        for cp in result.cut_points:
            assert isinstance(cp, HighlightCutPoint)
            assert cp.timestamp != ""
            assert cp.cut_in != ""
            assert cp.cut_out != ""
            assert cp.estimated_duration > 0
            assert cp.target_tier in ("tier1", "tier2", "both")
            assert 0 <= cp.priority_score <= 1.0

    def test_cut_in_before_timestamp(self):
        """カットインはタイムスタンプより前"""
        video_data, target_result = self._make_test_data()
        result = extract_highlights(video_data, target_result)
        for cp in result.cut_points:
            cut_in_sec = _ts_to_seconds(cp.cut_in)
            ts_sec = _ts_to_seconds(cp.timestamp)
            assert cut_in_sec <= ts_sec, (
                f"カットイン({cp.cut_in})がタイムスタンプ({cp.timestamp})より後"
            )

    def test_cut_out_after_cut_in(self):
        """カットアウトはカットインより後"""
        video_data, target_result = self._make_test_data()
        result = extract_highlights(video_data, target_result)
        for cp in result.cut_points:
            in_sec = _ts_to_seconds(cp.cut_in)
            out_sec = _ts_to_seconds(cp.cut_out)
            assert out_sec > in_sec, (
                f"カットアウト({cp.cut_out})がカットイン({cp.cut_in})より前"
            )

    def test_tier_representatives(self):
        """各層の代表シーンが抽出される"""
        video_data, target_result = self._make_test_data()
        result = extract_highlights(video_data, target_result)
        reps = result.tier_representatives
        assert isinstance(reps, TierRepresentatives)
        # 少なくとも1つの層に代表シーンがある
        total_reps = (
            len(reps.tier1_scenes) + len(reps.tier2_scenes) + len(reps.both_scenes)
        )
        assert total_reps > 0, "代表シーンが少なくとも1つは必要"

    def test_recommended_sequence(self):
        """推奨シーン順序が生成される"""
        video_data, target_result = self._make_test_data()
        result = extract_highlights(video_data, target_result)
        seq = result.recommended_sequence
        assert isinstance(seq, HighlightSequence)
        assert len(seq.scenes) > 0, "推奨シーンが1つ以上あるべき"
        assert seq.total_duration > 0, "合計時間が0より大きいべき"
        assert seq.sequence_rationale != ""

    def test_recommended_sequence_time_ordered(self):
        """推奨シーンがタイムスタンプ順に並んでいる"""
        video_data, target_result = self._make_test_data()
        result = extract_highlights(video_data, target_result)
        scenes = result.recommended_sequence.scenes
        for i in range(len(scenes) - 1):
            ts1 = _ts_to_seconds(scenes[i].timestamp)
            ts2 = _ts_to_seconds(scenes[i + 1].timestamp)
            assert ts1 <= ts2, (
                f"推奨シーンが時系列順でない: {scenes[i].timestamp} > {scenes[i+1].timestamp}"
            )

    def test_empty_target_result(self):
        """空のTargetLabelResultで分析"""
        video_data = VideoData()
        target_result = TargetLabelResult(scenes=[], balance=None)
        # balance=Noneでもエラーにならない
        result = extract_highlights(video_data, target_result)
        assert "分析不可" in result.analysis_summary

    def test_analysis_summary(self):
        """分析サマリーが生成される"""
        video_data, target_result = self._make_test_data()
        result = extract_highlights(video_data, target_result)
        assert result.analysis_summary != ""
        assert "シーン" in result.analysis_summary


class TestWithRealData:
    """実データでのテスト"""

    def test_izu_highlights(self):
        """Izuさんの動画でハイライト抽出"""
        if not SAMPLE_FILES["izu"].exists():
            pytest.skip("サンプルファイルなし")
        data = parse_markdown_file(SAMPLE_FILES["izu"])
        target_result = label_targets(data)
        result = extract_highlights(data, target_result)
        assert len(result.cut_points) > 0, "カットポイントが生成されるべき"
        assert result.recommended_sequence.total_duration > 0

    def test_ryosuke_highlights(self):
        """りょうすけさんの動画でハイライト抽出"""
        if not SAMPLE_FILES["ryosuke"].exists():
            pytest.skip("サンプルファイルなし")
        data = parse_markdown_file(SAMPLE_FILES["ryosuke"])
        target_result = label_targets(data)
        result = extract_highlights(data, target_result)
        assert isinstance(result, HighlightExtractorResult)

    def test_highlight_duration_bounds(self):
        """ハイライトの長さが10〜45秒の範囲内"""
        if not SAMPLE_FILES["izu"].exists():
            pytest.skip("サンプルファイルなし")
        data = parse_markdown_file(SAMPLE_FILES["izu"])
        target_result = label_targets(data)
        result = extract_highlights(data, target_result)
        for cp in result.cut_points:
            assert cp.estimated_duration >= 10, (
                f"ハイライトが短すぎる: {cp.estimated_duration}秒"
            )
            assert cp.estimated_duration <= 45, (
                f"ハイライトが長すぎる: {cp.estimated_duration}秒"
            )
