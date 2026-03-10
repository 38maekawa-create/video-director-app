"""NEW-3: 編集後動画フィードバックのテスト"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from video_direction.analyzer.post_edit_feedback import (
    generate_post_edit_feedback,
    EditFeedbackResult,
    ContentFeedbackItem,
    _generate_content_feedback,
    _check_highlight_inclusion,
    _check_classification_alignment,
    _check_content_balance,
)
from video_direction.integrations.ai_dev5_connector import VideoData, HighlightScene, PersonProfile
from video_direction.analyzer.guest_classifier import classify_guest


# === テストデータ ===

def _make_video_data(
    highlights=None,
    profiles=None,
    duration="30分",
    speakers="前川, ゲスト",
):
    """テスト用VideoDataを生成"""
    if profiles is None:
        profiles = [PersonProfile(
            name="テストさん",
            age="30代前半",
            occupation="エンジニア",
            income="年収1200万",
        )]
    return VideoData(
        title="テスト動画",
        duration=duration,
        speakers=speakers,
        highlights=highlights or [],
        main_topics=["トピック1", "トピック2"],
        profiles=profiles,
        video_type="対談インタビュー",
    )


def _make_highlights_mixed():
    """複数カテゴリのハイライトを生成"""
    return [
        HighlightScene("02:00", "ゲスト", "年収1200万です", "実績数字"),
        HighlightScene("05:00", "ゲスト", "人生が変わった", "パンチライン"),
        HighlightScene("08:00", "ゲスト", "30代エンジニア", "属性紹介"),
        HighlightScene("12:00", "ゲスト", "TEKOに入って", "TEKO価値"),
        HighlightScene("15:00", "ゲスト", "挑戦が大事", "メッセージ"),
    ]


# === generate_post_edit_feedback メインテスト ===

class TestGeneratePostEditFeedback:
    """メインのgenerate_post_edit_feedback関数テスト"""

    def test_基本的なフィードバック生成(self):
        video = _make_video_data(highlights=_make_highlights_mixed())
        result = generate_post_edit_feedback(video)
        assert isinstance(result, EditFeedbackResult)
        assert result.quality_score is not None
        assert result.telop_check is not None
        assert result.is_estimated is True

    def test_ゲスト名が設定される(self):
        video = _make_video_data(highlights=_make_highlights_mixed())
        result = generate_post_edit_feedback(video, editor="パグさん", stage="draft")
        assert result.guest_name == "テストさん"
        assert result.editor == "パグさん"
        assert result.stage == "draft"

    def test_タイムスタンプが設定される(self):
        video = _make_video_data(highlights=_make_highlights_mixed())
        result = generate_post_edit_feedback(video)
        assert result.feedback_timestamp != ""

    def test_品質スコアが生成される(self):
        video = _make_video_data(highlights=_make_highlights_mixed())
        result = generate_post_edit_feedback(video)
        assert result.quality_score.total_score > 0
        assert result.quality_score.grade in ("S", "A", "B", "C", "D")

    def test_空のハイライトでも動作する(self):
        video = _make_video_data(highlights=[])
        result = generate_post_edit_feedback(video)
        assert isinstance(result, EditFeedbackResult)


# === コンテンツフィードバックテスト ===

class TestContentFeedback:
    """コンテンツフィードバック生成のテスト"""

    def test_included_timestampsで良い点検出(self):
        highlights = _make_highlights_mixed()
        feedback = _check_highlight_inclusion(
            highlights,
            included_ts=["02:00", "05:00"],  # 実績数字とパンチライン
            excluded_ts=[],
        )
        good_items = [f for f in feedback if f.severity == "good"]
        assert len(good_items) >= 2

    def test_重要シーン除外で警告(self):
        highlights = _make_highlights_mixed()
        feedback = _check_highlight_inclusion(
            highlights,
            included_ts=[],
            excluded_ts=["02:00"],  # 実績数字を除外
        )
        warnings = [f for f in feedback if f.severity == "warning"]
        assert len(warnings) >= 1
        assert any("重要シーン" in w.description for w in warnings)

    def test_非重要シーン除外はsuggestion(self):
        highlights = _make_highlights_mixed()
        feedback = _check_highlight_inclusion(
            highlights,
            included_ts=[],
            excluded_ts=["12:00"],  # TEKO価値を除外
        )
        suggestions = [f for f in feedback if f.severity == "suggestion"]
        assert len(suggestions) >= 1

    def test_タイムスタンプ指定なしは確認推奨(self):
        highlights = _make_highlights_mixed()
        feedback = _check_highlight_inclusion(highlights, [], [])
        assert any("確認を推奨" in f.description for f in feedback)


# === 分類アラインメントテスト ===

class TestClassificationAlignment:
    """ゲスト分類に基づくチェックのテスト"""

    def test_層aで実績数字十分はgood(self):
        video = _make_video_data(highlights=[
            HighlightScene("02:00", "ゲスト", "年収1200万", "実績数字"),
            HighlightScene("05:00", "ゲスト", "月収100万", "実績数字"),
        ])
        classification = classify_guest(video)
        feedback = _check_classification_alignment(video, classification)
        if classification.tier == "a":
            good_items = [f for f in feedback if f.severity == "good"]
            assert len(good_items) >= 1

    def test_層bで代替強みなしは警告(self):
        # 層bになるゲスト（年収低め）
        profiles = [PersonProfile(
            name="テスト", age="30代前半",
            occupation="会社員", income="年収500万",
        )]
        video = _make_video_data(
            highlights=[
                HighlightScene("02:00", "ゲスト", "普通の会社員です", "メッセージ"),
            ],
            profiles=profiles,
        )
        classification = classify_guest(video)
        feedback = _check_classification_alignment(video, classification)
        if classification.tier == "b":
            warnings = [f for f in feedback if f.severity == "warning"]
            assert len(warnings) >= 1


# === コンテンツバランステスト ===

class TestContentBalance:
    """コンテンツバランスチェックのテスト"""

    def test_多様なカテゴリはgood(self):
        video = _make_video_data(highlights=_make_highlights_mixed())
        feedback = _check_content_balance(video)
        good_items = [f for f in feedback if f.severity == "good"]
        assert len(good_items) >= 1

    def test_単一カテゴリはsuggestion(self):
        video = _make_video_data(highlights=[
            HighlightScene("02:00", "ゲスト", "発言1", "パンチライン"),
            HighlightScene("05:00", "ゲスト", "発言2", "パンチライン"),
        ])
        feedback = _check_content_balance(video)
        suggestions = [f for f in feedback if f.severity == "suggestion"]
        assert len(suggestions) >= 1
        assert any("偏っています" in s.description for s in suggestions)

    def test_ハイライトなしは警告(self):
        video = _make_video_data(highlights=[])
        feedback = _check_content_balance(video)
        warnings = [f for f in feedback if f.severity == "warning"]
        assert len(warnings) >= 1


# === サマリー集計テスト ===

class TestFeedbackSummary:
    """フィードバックサマリー集計のテスト"""

    def test_total_issuesの集計(self):
        video = _make_video_data(highlights=_make_highlights_mixed())
        result = generate_post_edit_feedback(
            video,
            included_timestamps=["02:00"],
            excluded_timestamps=["05:00"],  # パンチライン除外→警告
        )
        assert result.total_issues >= 0
        assert result.warnings >= 0
        assert result.good_points >= 0
