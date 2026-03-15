"""direction_generator の追加ユニットテスト（_apply_learned_rules等）"""

import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.analyzer.direction_generator import (
    _extract_punchline,
    _timestamp_to_seconds,
    _rule_matches_highlight,
    _apply_learned_rules,
    _generate_for_highlight,
)
from src.video_direction.integrations.ai_dev5_connector import (
    VideoData,
    HighlightScene,
)
from src.video_direction.analyzer.guest_classifier import ClassificationResult
from src.video_direction.analyzer.income_evaluator import IncomeEvaluation
from src.video_direction.tracker.feedback_learner import FeedbackLearner, LearningRule


# ────────────────────────────────────────────────
# _extract_punchline
# ────────────────────────────────────────────────

class TestExtractPunchline:
    def test_50文字以下はそのまま返す(self):
        text = "人生は一度きり"
        assert _extract_punchline(text) == text

    def test_文末句点で切り出す(self):
        text = "これが大事です。それ以外はあまり重要ではありません。補足説明。"
        result = _extract_punchline(text)
        assert result == "これが大事です"

    def test_50文字超は省略記号を付与(self):
        text = "あ" * 55
        result = _extract_punchline(text)
        assert result.endswith("...")
        assert len(result) <= 50


# ────────────────────────────────────────────────
# _timestamp_to_seconds
# ────────────────────────────────────────────────

class TestTimestampToSeconds:
    def test_MM_SS形式(self):
        assert _timestamp_to_seconds("01:30") == 90

    def test_HH_MM_SS形式(self):
        assert _timestamp_to_seconds("01:01:01") == 3661

    def test_00_00は0を返す(self):
        assert _timestamp_to_seconds("00:00") == 0

    def test_不正な形式は0を返す(self):
        assert _timestamp_to_seconds("invalid") == 0


# ────────────────────────────────────────────────
# _rule_matches_highlight
# ────────────────────────────────────────────────

class TestRuleMatchesHighlight:
    def _make_rule(self, category: str, rule_text: str = "テストルール") -> LearningRule:
        return LearningRule(
            id="rule_test",
            rule_text=rule_text,
            category=category,
        )

    def _make_highlight(self, category: str, text: str = "") -> HighlightScene:
        return HighlightScene(
            timestamp="01:00",
            speaker="ゲスト",
            text=text,
            category=category,
        )

    def test_カテゴリマッピングでマッチする(self):
        # telop カテゴリのルールは "実績数字" ハイライトにマッチする
        rule = self._make_rule("telop")
        hl = self._make_highlight("実績数字")
        assert _rule_matches_highlight(rule, hl) is True

    def test_テキストのキーワードでマッチする(self):
        # camera カテゴリのルール → "カメラ" というキーワードがテキストにあればマッチ
        rule = self._make_rule("camera")
        hl = self._make_highlight("general", text="カメラアングルについて")
        assert _rule_matches_highlight(rule, hl) is True

    def test_全く関係ないカテゴリはFalse(self):
        # cutting ルールが "属性紹介" ハイライトに適用されないはず
        rule = self._make_rule("cutting")
        hl = self._make_highlight("属性紹介", text="テキスト")
        result = _rule_matches_highlight(rule, hl)
        # "カット"/"切り" 等がテキストにない場合はFalse
        assert result is False


# ────────────────────────────────────────────────
# _apply_learned_rules
# ────────────────────────────────────────────────

class TestApplyLearnedRules:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.learner = FeedbackLearner(data_dir=Path(self.tmp))
        self.classification = ClassificationResult(
            tier="a",
            tier_label="超高年収層",
            income_range="3000万円以上",
            confidence=0.9,
            reasoning="",
        )
        self.income_eval = IncomeEvaluation(
            emphasis_level="strong",
            emphasis_reason="高年収",
            suggested_visuals=[],
        )

    def _make_video_data(self, highlights: list) -> VideoData:
        return VideoData(title="テスト動画", highlights=highlights)

    def test_ルールなしは空を返す(self):
        video = self._make_video_data([])
        entries, applied = _apply_learned_rules(
            video, self.classification, self.income_eval, self.learner
        )
        assert entries == []
        assert applied == []

    def test_有効なルールが適用される(self):
        # telop カテゴリのルールを直接追加
        rule = LearningRule(
            id="rule_telop_001",
            rule_text="[telop] テロップを大きく表示",
            category="telop",
            priority="high",
        )
        self.learner._rules[rule.id] = rule

        hl = HighlightScene(
            timestamp="01:00",
            speaker="ゲスト",
            text="年収1000万円台",
            category="実績数字",
        )
        video = self._make_video_data([hl])
        entries, applied = _apply_learned_rules(
            video, self.classification, self.income_eval, self.learner
        )
        assert len(entries) >= 1
        assert len(applied) >= 1
        assert applied[0]["rule_id"] == "rule_telop_001"

    def test_適用後にapplied_countが増える(self):
        rule = LearningRule(
            id="rule_camera_001",
            rule_text="[camera] パンチライン時に寄り",
            category="camera",
            priority="medium",
        )
        self.learner._rules[rule.id] = rule

        hl = HighlightScene(
            timestamp="02:00",
            speaker="ゲスト",
            text="重要な発言",
            category="パンチライン",
        )
        video = self._make_video_data([hl])
        before = rule.applied_count
        _apply_learned_rules(
            video, self.classification, self.income_eval, self.learner
        )
        assert rule.applied_count > before


# ────────────────────────────────────────────────
# _generate_for_highlight
# ────────────────────────────────────────────────

class TestGenerateForHighlight:
    def _make_classification(self, tier: str = "a") -> ClassificationResult:
        return ClassificationResult(
            tier=tier,
            tier_label="層a",
            income_range="1000万円以上",
            confidence=0.9,
            reasoning="",
        )

    def _make_income_eval(self) -> IncomeEvaluation:
        return IncomeEvaluation(
            emphasis_level="strong",
            emphasis_reason="高年収",
            suggested_visuals=[],
        )

    def test_実績数字カテゴリでtelopエントリを生成(self):
        hl = HighlightScene(
            timestamp="01:00",
            speaker="ゲスト",
            text="年収1000万円台達成",
            category="実績数字",
        )
        entries = _generate_for_highlight(
            hl, self._make_classification(), self._make_income_eval()
        )
        types = [e.direction_type for e in entries]
        assert "telop" in types

    def test_パンチラインカテゴリでcameraエントリを生成(self):
        hl = HighlightScene(
            timestamp="02:00",
            speaker="ゲスト",
            text="人生は一度きりです",
            category="パンチライン",
        )
        entries = _generate_for_highlight(
            hl, self._make_classification(), self._make_income_eval()
        )
        types = [e.direction_type for e in entries]
        assert "camera" in types

    def test_属性紹介カテゴリでtelopエントリを生成(self):
        hl = HighlightScene(
            timestamp="00:30",
            speaker="ゲスト",
            text="元アクセンチュア勤務",
            category="属性紹介",
        )
        entries = _generate_for_highlight(
            hl, self._make_classification(), self._make_income_eval()
        )
        types = [e.direction_type for e in entries]
        assert "telop" in types

    def test_全エントリのpriorityが有効値(self):
        hl = HighlightScene(
            timestamp="03:00",
            speaker="ゲスト",
            text="テストテキスト",
            category="TEKO価値",
        )
        entries = _generate_for_highlight(
            hl, self._make_classification(), self._make_income_eval()
        )
        for e in entries:
            assert e.priority in ("high", "medium", "low")
