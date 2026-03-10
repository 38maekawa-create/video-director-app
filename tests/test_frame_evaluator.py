"""C-1: フレーム画像マルチモデル評価のテスト"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from video_direction.analyzer.frame_evaluator import (
    evaluate_frames,
    FrameEvaluationResult,
    FrameEvaluation,
    FrameInfo,
    ModelEvaluation,
    Finding,
    _select_representative_frames,
    _evaluate_frame_stub,
    _generate_stub_evaluation,
    _analyze_agreement,
    _calculate_consensus_score,
    _determine_agreement_level,
    extract_frames_from_video,
    EVALUATION_AXES,
    AXIS_LABELS,
)
from video_direction.integrations.ai_dev5_connector import VideoData, HighlightScene


# === テストデータ ===

def _make_video_data(highlights=None, speakers="ホスト, ゲスト", video_type="対談インタビュー"):
    """テスト用VideoDataを生成"""
    return VideoData(
        title="テスト動画",
        duration="30分",
        speakers=speakers,
        video_type=video_type,
        highlights=highlights or [],
        main_topics=["トピック1", "トピック2"],
    )


def _make_highlights(count=5):
    """テスト用ハイライトリストを生成"""
    categories = ["実績数字", "パンチライン", "属性紹介", "TEKO価値", "メッセージ"]
    return [
        HighlightScene(
            timestamp=f"{i*5:02d}:00",
            speaker="ゲスト",
            text=f"テスト発言{i+1}",
            category=categories[i % len(categories)],
        )
        for i in range(count)
    ]


# === evaluate_frames メインテスト ===

class TestEvaluateFrames:
    """メインのevaluate_frames関数テスト"""

    def test_空のハイライトでスタブ結果(self):
        video = _make_video_data(highlights=[])
        result = evaluate_frames(video)
        assert isinstance(result, FrameEvaluationResult)
        assert result.total_frames == 0
        assert result.is_stub is True

    def test_ハイライトありで評価結果生成(self):
        video = _make_video_data(highlights=_make_highlights(5))
        result = evaluate_frames(video)
        assert result.total_frames == 5
        assert len(result.evaluations) == 5
        assert result.is_stub is True

    def test_平均スコアが計算される(self):
        video = _make_video_data(highlights=_make_highlights(3))
        result = evaluate_frames(video)
        assert result.average_score > 0

    def test_APIなしではスタブフラグがTrue(self):
        video = _make_video_data(highlights=_make_highlights(1))
        result = evaluate_frames(video, use_api=False)
        assert result.is_stub is True

    def test_最大10フレームまで(self):
        video = _make_video_data(highlights=_make_highlights(15))
        result = evaluate_frames(video)
        assert result.total_frames <= 10


# === 代表フレーム選定テスト ===

class TestSelectRepresentativeFrames:
    """代表フレーム選定のテスト"""

    def test_ハイライトなしで空リスト(self):
        video = _make_video_data(highlights=[])
        frames = _select_representative_frames(video)
        assert len(frames) == 0

    def test_ハイライトからフレーム選定(self):
        video = _make_video_data(highlights=_make_highlights(3))
        frames = _select_representative_frames(video)
        assert len(frames) == 3
        assert all(isinstance(f, FrameInfo) for f in frames)

    def test_フレームにタイムスタンプが設定される(self):
        highlights = [HighlightScene("03:30", "ゲスト", "発言", "パンチライン")]
        video = _make_video_data(highlights=highlights)
        frames = _select_representative_frames(video)
        assert frames[0].timestamp == "03:30"

    def test_フレームはスタブフラグTrue(self):
        video = _make_video_data(highlights=_make_highlights(1))
        frames = _select_representative_frames(video)
        assert frames[0].is_stub is True

    def test_重複タイムスタンプは除外(self):
        highlights = [
            HighlightScene("03:30", "ゲスト", "発言1", "パンチライン"),
            HighlightScene("03:30", "ゲスト", "発言2", "実績数字"),
        ]
        video = _make_video_data(highlights=highlights)
        frames = _select_representative_frames(video)
        assert len(frames) == 1


# === スタブ評価テスト ===

class TestStubEvaluation:
    """スタブ評価生成のテスト"""

    def test_スタブ評価が生成される(self):
        frame = FrameInfo(timestamp="05:00", frame_index=0, is_stub=True)
        video = _make_video_data(highlights=_make_highlights(3))
        eval_result = _evaluate_frame_stub(frame, video)
        assert isinstance(eval_result, FrameEvaluation)
        assert len(eval_result.evaluations) == 2  # 2モデル

    def test_2モデルの名前が正しい(self):
        frame = FrameInfo(timestamp="05:00", frame_index=0, is_stub=True)
        video = _make_video_data(highlights=_make_highlights(3))
        eval_result = _evaluate_frame_stub(frame, video)
        model_names = {e.model_name for e in eval_result.evaluations}
        assert "claude-opus-4.6" in model_names
        assert "gpt-5.4" in model_names

    def test_合意レベルが設定される(self):
        frame = FrameInfo(timestamp="05:00", frame_index=0, is_stub=True)
        video = _make_video_data(highlights=_make_highlights(3))
        eval_result = _evaluate_frame_stub(frame, video)
        assert eval_result.agreement_level in ("agreed", "partial", "disagreed")

    def test_各モデルの全軸にスコアがある(self):
        video = _make_video_data(highlights=_make_highlights(3))
        eval_result = _generate_stub_evaluation(
            "test-model", FrameInfo("05:00", 0), video, bias_seed=1
        )
        for axis in EVALUATION_AXES:
            assert axis in eval_result.scores
            assert 0 <= eval_result.scores[axis] <= 100


# === 合意分析テスト ===

class TestAgreementAnalysis:
    """合意分析のテスト"""

    def test_両モデル高スコアで指摘なし(self):
        eval_a = ModelEvaluation(
            model_name="model_a",
            scores={axis: 80 for axis in EVALUATION_AXES},
            overall_score=80.0,
        )
        eval_b = ModelEvaluation(
            model_name="model_b",
            scores={axis: 82 for axis in EVALUATION_AXES},
            overall_score=82.0,
        )
        findings = _analyze_agreement(eval_a, eval_b)
        assert len(findings) == 0  # 高スコアなので指摘なし

    def test_両モデル低スコア合意でissue(self):
        eval_a = ModelEvaluation(
            model_name="model_a",
            scores={axis: 45 for axis in EVALUATION_AXES},
            overall_score=45.0,
        )
        eval_b = ModelEvaluation(
            model_name="model_b",
            scores={axis: 50 for axis in EVALUATION_AXES},
            overall_score=50.0,
        )
        findings = _analyze_agreement(eval_a, eval_b)
        issues = [f for f in findings if f.level == "issue"]
        assert len(issues) > 0

    def test_モデル間不合意でreview(self):
        eval_a = ModelEvaluation(
            model_name="model_a",
            scores={"composition": 30, "lighting": 70, "color_balance": 70, "focus": 70, "framing": 70},
            overall_score=62.0,
        )
        eval_b = ModelEvaluation(
            model_name="model_b",
            scores={"composition": 55, "lighting": 70, "color_balance": 70, "focus": 70, "framing": 70},
            overall_score=67.0,
        )
        findings = _analyze_agreement(eval_a, eval_b)
        reviews = [f for f in findings if f.level == "review"]
        assert len(reviews) > 0  # compositionで不合意

    def test_合意レベル判定_agreed(self):
        eval_a = ModelEvaluation(
            model_name="model_a",
            scores={axis: 70 for axis in EVALUATION_AXES},
            overall_score=70.0,
        )
        eval_b = ModelEvaluation(
            model_name="model_b",
            scores={axis: 72 for axis in EVALUATION_AXES},
            overall_score=72.0,
        )
        level = _determine_agreement_level(eval_a, eval_b)
        assert level == "agreed"

    def test_合意レベル判定_pending(self):
        eval_a = ModelEvaluation(model_name="model_a", scores={}, overall_score=0)
        eval_b = ModelEvaluation(model_name="model_b", scores={}, overall_score=0)
        level = _determine_agreement_level(eval_a, eval_b)
        assert level == "pending"


# === コンセンサススコアテスト ===

class TestConsensusScore:
    """合意スコア計算のテスト"""

    def test_正常なスコア計算(self):
        eval_a = ModelEvaluation(model_name="a", scores={"x": 80}, overall_score=80.0)
        eval_b = ModelEvaluation(model_name="b", scores={"x": 70}, overall_score=70.0)
        score = _calculate_consensus_score(eval_a, eval_b)
        assert score == 75.0

    def test_空のスコアで0(self):
        eval_a = ModelEvaluation(model_name="a", scores={}, overall_score=0)
        eval_b = ModelEvaluation(model_name="b", scores={}, overall_score=0)
        score = _calculate_consensus_score(eval_a, eval_b)
        assert score == 0.0


# === フレーム抽出スタブテスト ===

class TestFrameExtraction:
    """フレーム抽出スタブのテスト"""

    def test_スタブは空リストを返す(self):
        result = extract_frames_from_video("/dummy/path.mp4", ["00:00", "01:00"])
        assert result == []


# === データ構造テスト ===

class TestDataStructures:
    """データ構造のテスト"""

    def test_FrameInfo生成(self):
        frame = FrameInfo(timestamp="05:00", frame_index=0, is_stub=True)
        assert frame.timestamp == "05:00"
        assert frame.is_stub is True

    def test_Finding生成(self):
        finding = Finding(
            axis="composition",
            axis_label="構図",
            level="issue",
            description="構図の改善が必要",
        )
        assert finding.level == "issue"
        assert finding.axis_label == "構図"

    def test_EVALUATION_AXES定数(self):
        assert len(EVALUATION_AXES) == 5
        for axis in EVALUATION_AXES:
            assert axis in AXIS_LABELS
