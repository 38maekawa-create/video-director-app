"""FB学習ループの統合テスト"""

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


def test_get_learning_context_with_rules(tmp_path):
    """get_learning_contextが学習ルールのコンテキストを正しく返すことを確認"""
    learner = FeedbackLearner(data_dir=tmp_path / "learning")

    # ルールなし
    ctx = get_learning_context(learner)
    assert ctx["has_rules"] is False
    assert ctx["active_rules"] == []

    # FB取り込みでルール生成
    for i in range(4):
        learner.ingest_feedback(
            feedback_id=f"fb_{i}",
            content="カメラ アングルをもう少し寄りにして",
            category="camera",
        )

    ctx = get_learning_context(learner)
    assert ctx["has_rules"] is True
    assert len(ctx["active_rules"]) >= 1
    assert ctx["active_rules"][0]["category"] == "camera"
    assert "insights" in ctx
    assert ctx["insights"]["total_patterns"] >= 1


def test_get_learning_context_without_learner():
    """feedback_learnerがNoneの場合、空のコンテキストを返す"""
    ctx = get_learning_context(None)
    assert ctx["has_rules"] is False
    assert ctx["active_rules"] == []
    assert ctx["insights"] == {}


def test_multiple_categories_learning(tmp_path):
    """異なるカテゴリのFBが正しく分類・蓄積されることを確認"""
    learner = FeedbackLearner(data_dir=tmp_path / "learning")

    # テロップ系FB
    for i in range(3):
        learner.ingest_feedback(f"telop_{i}", "テロップが小さすぎて見えない")
    # カメラ系FB
    for i in range(3):
        learner.ingest_feedback(f"camera_{i}", "カメラの寄りが足りない")

    telop_rules = learner.get_active_rules(category="telop")
    camera_rules = learner.get_active_rules(category="camera")
    assert len(telop_rules) >= 1
    assert len(camera_rules) >= 1

    # ディレクション生成に両方反映されることを確認
    video_data = VideoData(
        title="テスト動画",
        profiles=[PersonProfile(name="テスト太郎", age="30代", income="年収800万")],
        highlights=[
            HighlightScene(timestamp="01:00", speaker="テスト太郎",
                           text="実績数字のシーン", category="実績数字"),
            HighlightScene(timestamp="02:00", speaker="テスト太郎",
                           text="パンチラインのシーン", category="パンチライン"),
        ],
    )
    classification = ClassificationResult(
        tier="b", tier_label="層b（強い）", reason="テスト",
        presentation_template="テスト", confidence="high",
    )
    income_eval = IncomeEvaluation(
        income_value=800, age_bracket="30代", threshold=700,
        emphasize=True, emphasis_reason="テスト", telop_suggestion="テスト",
    )

    timeline = generate_directions(video_data, classification, income_eval,
                                   feedback_learner=learner)
    assert len(timeline.applied_rules) >= 2  # テロップ + カメラの両ルール適用


def test_applied_rules_count_increments(tmp_path):
    """ルール適用後にapplied_countが加算されることを確認"""
    learner = FeedbackLearner(data_dir=tmp_path / "learning")
    for i in range(4):
        learner.ingest_feedback(f"fb_{i}", "BGMのテンポが速すぎる", category="bgm")

    rules_before = learner.get_active_rules(category="bgm")
    assert len(rules_before) >= 1
    count_before = rules_before[0].applied_count

    video_data = VideoData(
        title="テスト", profiles=[],
        highlights=[
            HighlightScene(timestamp="00:30", speaker="A",
                           text="メッセージ", category="メッセージ"),
        ],
    )
    classification = ClassificationResult(
        tier="c", tier_label="層c", reason="テスト",
        presentation_template="テスト", confidence="medium",
    )
    income_eval = IncomeEvaluation(
        income_value=500, age_bracket="20代", threshold=600,
        emphasize=False, emphasis_reason="テスト", telop_suggestion="テスト",
    )

    generate_directions(video_data, classification, income_eval, feedback_learner=learner)

    rules_after = learner.get_active_rules(category="bgm")
    assert rules_after[0].applied_count > count_before
