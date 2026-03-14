"""FB学習ループの統合テスト"""

from src.video_direction.tracker.feedback_learner import FeedbackLearner
from src.video_direction.analyzer.direction_generator import generate_directions
from src.video_direction.integrations.ai_dev5_connector import (
    VideoData,
    HighlightScene,
    PersonProfile,
)
from src.video_direction.analyzer.guest_classifier import ClassificationResult
from src.video_direction.analyzer.income_evaluator import IncomeEvaluation


def test_feedback_learning_rule_is_applied_to_direction_generation(tmp_path):
    learner = FeedbackLearner(data_dir=tmp_path / "learning")

    # 同種FBを複数回取り込み、確信度を上げてルール生成させる
    for i in range(3):
        learner.ingest_feedback(
            feedback_id=f"fb_{i}",
            content="テロップ もう少し大きくして強調したい",
            category=None,
            created_by="tester",
        )

    active_rules = learner.get_active_rules()
    assert len(active_rules) >= 1

    video_data = VideoData(
        title="テスト動画",
        profiles=[PersonProfile(name="テスト太郎", age="30代前半", income="年収900万")],
        highlights=[
            HighlightScene(
                timestamp="00:10",
                speaker="テスト太郎",
                text="ここは実績数字を強く見せたい",
                category="実績数字",
            ),
            HighlightScene(
                timestamp="00:25",
                speaker="テスト太郎",
                text="キー発言です",
                category="パンチライン",
            ),
        ],
    )
    classification = ClassificationResult(
        tier="a",
        tier_label="層a（圧倒的に強い）",
        reason="テスト",
        presentation_template="テスト",
        confidence="high",
    )
    income_eval = IncomeEvaluation(
        income_value=900,
        age_bracket="30代前半",
        threshold=700,
        emphasize=True,
        emphasis_reason="テスト",
        telop_suggestion="テスト",
    )

    timeline = generate_directions(
        video_data=video_data,
        classification=classification,
        income_eval=income_eval,
        feedback_learner=learner,
    )

    assert len(timeline.applied_rules) >= 1
    assert any("[FB学習]" in e.instruction for e in timeline.entries)
