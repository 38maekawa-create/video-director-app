"""映像トラッキング学習ループの統合テスト

テスト対象:
- VideoLearner → direction_generator への接続
- get_learning_context への video_learner 統合
- VideoLearningRuleのdirection_generator互換性
"""

from src.video_direction.tracker.video_learner import VideoLearner, VideoLearningRule
from src.video_direction.tracker.feedback_learner import FeedbackLearner
from src.video_direction.analyzer.direction_generator import (
    generate_directions,
    get_learning_context,
)
from src.video_direction.integrations.ai_dev5_connector import (
    VideoData,
    HighlightScene,
    PersonProfile,
)
from src.video_direction.analyzer.guest_classifier import ClassificationResult
from src.video_direction.analyzer.income_evaluator import IncomeEvaluation


def _make_test_fixtures():
    """テスト用の共通フィクスチャを生成"""
    video_data = VideoData(
        title="テスト動画",
        profiles=[PersonProfile(name="テスト太郎", age="30代前半", income="年収900万")],
        highlights=[
            HighlightScene(
                timestamp="00:10", speaker="テスト太郎",
                text="ここは実績数字を強く見せたい", category="実績数字",
            ),
            HighlightScene(
                timestamp="00:25", speaker="テスト太郎",
                text="キー発言です", category="パンチライン",
            ),
        ],
    )
    classification = ClassificationResult(
        tier="a", tier_label="層a（圧倒的に強い）", reason="テスト",
        presentation_template="テスト", confidence="high",
    )
    income_eval = IncomeEvaluation(
        income_value=900, age_bracket="30代前半", threshold=700,
        emphasize=True, emphasis_reason="テスト", telop_suggestion="テスト",
    )
    return video_data, classification, income_eval


def test_video_learner_rules_applied_to_direction(tmp_path):
    """VideoLearnerのルールがdirection_generatorに反映されることを確認"""
    learner = VideoLearner(data_dir=tmp_path / "learning")

    # 同じパターンを複数回学習してconfidenceを上げる
    for i in range(5):
        learner.learn_from_analysis(
            video_id=f"yt_{i:03d}",
            analysis_result={"cutting_style": "高速カットで緩急をつける編集"},
        )

    rules = learner.get_active_rules()
    assert len(rules) >= 1

    video_data, classification, income_eval = _make_test_fixtures()

    timeline = generate_directions(
        video_data=video_data,
        classification=classification,
        income_eval=income_eval,
        video_learner=learner,
    )

    # video_learnerのルールが適用されていることを確認
    assert len(timeline.applied_rules) >= 1
    assert any("[FB学習]" in e.instruction for e in timeline.entries)


def test_both_learners_applied_to_direction(tmp_path):
    """FeedbackLearnerとVideoLearnerの両方のルールが同時に適用されることを確認"""
    fb_learner = FeedbackLearner(data_dir=tmp_path / "fb_learning")
    vl_learner = VideoLearner(data_dir=tmp_path / "vl_learning")

    # FB学習ルール
    for i in range(4):
        fb_learner.ingest_feedback(f"fb_{i}", "テロップが小さすぎる", category="telop")

    # 映像学習ルール
    for i in range(4):
        vl_learner.learn_from_analysis(
            video_id=f"yt_{i}",
            analysis_result={"color_grading": "暖色系で温かみのあるトーン"},
        )

    video_data, classification, income_eval = _make_test_fixtures()

    timeline = generate_directions(
        video_data=video_data,
        classification=classification,
        income_eval=income_eval,
        feedback_learner=fb_learner,
        video_learner=vl_learner,
    )

    # 両方のルールが適用されていること
    assert len(timeline.applied_rules) >= 2
    fb_rules = [r for r in timeline.applied_rules if r.get("category") == "telop"]
    vl_rules = [r for r in timeline.applied_rules if r.get("category") == "color"]
    assert len(fb_rules) >= 1
    assert len(vl_rules) >= 1


def test_get_learning_context_with_video_learner(tmp_path):
    """get_learning_contextがvideo_learnerの情報を含むことを確認"""
    vl = VideoLearner(data_dir=tmp_path / "learning")
    for i in range(3):
        vl.learn_from_analysis(
            video_id=f"yt_{i}",
            analysis_result={"tempo": "テンポが速い"},
        )

    ctx = get_learning_context(video_learner=vl)
    assert ctx["has_rules"] is True
    assert len(ctx["active_rules"]) >= 1
    assert ctx["active_rules"][0]["source"] == "video_tracking"
    assert "video_learning" in ctx
    assert ctx["video_learning"]["total_patterns"] >= 1


def test_get_learning_context_with_both_learners(tmp_path):
    """FB学習 + 映像学習の両方を含むコンテキストが取得できることを確認"""
    fb = FeedbackLearner(data_dir=tmp_path / "fb_learning")
    vl = VideoLearner(data_dir=tmp_path / "vl_learning")

    for i in range(4):
        fb.ingest_feedback(f"fb_{i}", "カメラをもっと寄りに", category="camera")
    for i in range(3):
        vl.learn_from_analysis(
            video_id=f"yt_{i}",
            analysis_result={"cutting_style": "テスト"},
        )

    ctx = get_learning_context(feedback_learner=fb, video_learner=vl)
    assert ctx["has_rules"] is True

    fb_sources = [r for r in ctx["active_rules"] if r.get("source") == "feedback"]
    vl_sources = [r for r in ctx["active_rules"] if r.get("source") == "video_tracking"]
    assert len(fb_sources) >= 1
    assert len(vl_sources) >= 1


def test_video_learner_none_does_not_break_direction(tmp_path):
    """video_learner=Noneでもdirection_generatorが正常に動作することを確認"""
    video_data, classification, income_eval = _make_test_fixtures()

    timeline = generate_directions(
        video_data=video_data,
        classification=classification,
        income_eval=income_eval,
        video_learner=None,
    )

    # ルールベースのエントリは生成される
    assert len(timeline.entries) >= 1


def test_video_learning_rule_is_compatible_with_feedback_rule():
    """VideoLearningRuleがFB LearningRuleと同じ必須属性を持つことを確認"""
    rule = VideoLearningRule(
        id="vr_test",
        rule_text="高速カット",
        category="cutting",
        priority="high",
    )
    # direction_generatorの_apply_learned_rulesが使うフィールド
    assert hasattr(rule, "id")
    assert hasattr(rule, "rule_text")
    assert hasattr(rule, "category")
    assert hasattr(rule, "priority")
    assert hasattr(rule, "applied_count")
    assert hasattr(rule, "is_active")
