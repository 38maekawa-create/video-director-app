"""direction_generator の拡張ユニットテスト

テスト対象:
- generate_directions() のルールベース生成（基本動作）
- _apply_learned_rules(): FB学習ルール適用
- 映像学習ルール適用（VideoLearner経由）
- LLM分析統合（モック使用）
- DirectionEntry / DirectionTimeline のデータ構造
- 空の feedback / tracking 時の挙動
- カテゴリフィルタリング
- 優先度ソート
- get_learning_context() の挙動
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.analyzer.direction_generator import (
    generate_directions,
    get_learning_context,
    DirectionEntry,
    DirectionTimeline,
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
from src.video_direction.tracker.video_learner import VideoLearner, VideoLearningRule


# ────────────────────────────────────────────────
# テスト用ヘルパー
# ────────────────────────────────────────────────

def _make_classification(tier: str = "a", tier_label: str = "超高年収層") -> ClassificationResult:
    return ClassificationResult(
        tier=tier,
        tier_label=tier_label,
        reason="テスト",
        presentation_template="強調",
        confidence="high",
    )


def _make_income_eval(income: int = 3000, emphasize: bool = True) -> IncomeEvaluation:
    return IncomeEvaluation(
        income_value=income,
        age_bracket="30代",
        threshold=800,
        emphasize=emphasize,
        emphasis_reason="高年収" if emphasize else "標準",
        telop_suggestion=f"年収{income}万円" if emphasize else "",
    )


def _make_highlight(timestamp: str, category: str, text: str = "", speaker: str = "ゲスト") -> HighlightScene:
    return HighlightScene(
        timestamp=timestamp,
        speaker=speaker,
        text=text,
        category=category,
    )


def _make_video_data(highlights: list, title: str = "テスト動画") -> VideoData:
    return VideoData(title=title, highlights=highlights)


# ────────────────────────────────────────────────
# _extract_punchline
# ────────────────────────────────────────────────

class TestExtractPunchline:
    def test_50文字以下はそのまま返す(self):
        text = "人生は一度きり"
        assert _extract_punchline(text) == text

    def test_文末句点で切り出す(self):
        text = "これが最も大事なポイントです。" + "あ" * 50
        result = _extract_punchline(text)
        assert result == "これが最も大事なポイントです"

    def test_50文字超は省略記号を付与(self):
        text = "あ" * 55
        result = _extract_punchline(text)
        assert result.endswith("...")
        assert len(result) <= 50

    def test_空文字列はそのまま返す(self):
        assert _extract_punchline("") == ""

    def test_ちょうど50文字はそのまま返す(self):
        text = "あ" * 50
        assert _extract_punchline(text) == text

    def test_句点で分割しても50文字超の場合は切り詰める(self):
        # 最初の文が50文字を超える場合
        text = "あ" * 55 + "。短い文。"
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

    def test_空文字列は0を返す(self):
        assert _timestamp_to_seconds("") == 0

    def test_コロンなしは0を返す(self):
        assert _timestamp_to_seconds("12345") == 0

    def test_大きな値(self):
        assert _timestamp_to_seconds("99:59") == 99 * 60 + 59

    def test_HH_MM_SS_ゼロパディング(self):
        assert _timestamp_to_seconds("00:05:30") == 330


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

    def test_カテゴリマッピングでマッチする(self):
        # telop カテゴリのルールは "実績数字" ハイライトにマッチする
        rule = self._make_rule("telop")
        hl = _make_highlight("01:00", "実績数字")
        assert _rule_matches_highlight(rule, hl) is True

    def test_テキストのキーワードでマッチする(self):
        rule = self._make_rule("camera")
        hl = _make_highlight("01:00", "general", text="カメラアングルについて")
        assert _rule_matches_highlight(rule, hl) is True

    def test_全く関係ないカテゴリはFalse(self):
        rule = self._make_rule("cutting")
        hl = _make_highlight("01:00", "属性紹介", text="テキスト")
        assert _rule_matches_highlight(rule, hl) is False

    def test_bgmカテゴリはメッセージにマッチ(self):
        rule = self._make_rule("bgm")
        hl = _make_highlight("01:00", "メッセージ")
        assert _rule_matches_highlight(rule, hl) is True

    def test_bgmカテゴリはTEKO価値にマッチ(self):
        rule = self._make_rule("bgm")
        hl = _make_highlight("01:00", "TEKO価値")
        assert _rule_matches_highlight(rule, hl) is True

    def test_compositionカテゴリは属性紹介にマッチ(self):
        rule = self._make_rule("composition")
        hl = _make_highlight("01:00", "属性紹介")
        assert _rule_matches_highlight(rule, hl) is True

    def test_テンポカテゴリはパンチラインにマッチ(self):
        rule = self._make_rule("tempo")
        hl = _make_highlight("01:00", "パンチライン")
        assert _rule_matches_highlight(rule, hl) is True

    def test_テキストにキーワードが含まれる場合マッチ(self):
        rule = self._make_rule("color")
        hl = _make_highlight("01:00", "general", text="明るい場面での色調整")
        assert _rule_matches_highlight(rule, hl) is True

    def test_未知のカテゴリはFalse(self):
        rule = self._make_rule("unknown_category")
        hl = _make_highlight("01:00", "実績数字", text="テスト")
        assert _rule_matches_highlight(rule, hl) is False

    def test_空テキストのハイライト(self):
        rule = self._make_rule("cutting")
        hl = _make_highlight("01:00", "パンチライン", text="")
        # カテゴリマッピングでマッチする
        assert _rule_matches_highlight(rule, hl) is True

    def test_Noneテキストのハイライト(self):
        """textがNoneでもクラッシュしない"""
        rule = self._make_rule("telop")
        hl = HighlightScene(timestamp="01:00", speaker="ゲスト", text=None, category="実績数字")
        assert _rule_matches_highlight(rule, hl) is True

    def test_Noneカテゴリのハイライト(self):
        """categoryがNoneでもクラッシュしない"""
        rule = self._make_rule("telop")
        hl = HighlightScene(timestamp="01:00", speaker="ゲスト", text="テスト", category=None)
        # カテゴリマッピングに合わないのでFalse（テキストにキーワードが含まれない限り）
        assert _rule_matches_highlight(rule, hl) is False


# ────────────────────────────────────────────────
# _apply_learned_rules
# ────────────────────────────────────────────────

class TestApplyLearnedRules:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.learner = FeedbackLearner(data_dir=Path(self.tmp))
        self.classification = _make_classification()
        self.income_eval = _make_income_eval()

    def test_ルールなしは空を返す(self):
        video = _make_video_data([])
        entries, applied = _apply_learned_rules(
            video, self.classification, self.income_eval, self.learner
        )
        assert entries == []
        assert applied == []

    def test_有効なルールが適用される(self):
        rule = LearningRule(
            id="rule_telop_001",
            rule_text="[telop] テロップを大きく表示",
            category="telop",
            priority="high",
        )
        self.learner._rules[rule.id] = rule

        hl = _make_highlight("01:00", "実績数字", text="年収1000万円台")
        video = _make_video_data([hl])
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

        hl = _make_highlight("02:00", "パンチライン", text="重要な発言")
        video = _make_video_data([hl])
        before = rule.applied_count
        _apply_learned_rules(
            video, self.classification, self.income_eval, self.learner
        )
        assert rule.applied_count > before

    def test_ハイライトなしのvideoでルールが存在する場合(self):
        """ハイライトが空ならルールがあっても適用されない"""
        rule = LearningRule(
            id="rule_001",
            rule_text="テロップ強調",
            category="telop",
            priority="high",
        )
        self.learner._rules[rule.id] = rule

        video = _make_video_data([])
        entries, applied = _apply_learned_rules(
            video, self.classification, self.income_eval, self.learner
        )
        assert entries == []
        assert applied == []

    def test_複数ルールが同一ハイライトに適用(self):
        """同じハイライトに複数ルールが適用されるケース"""
        rule1 = LearningRule(id="r1", rule_text="テロップ強調", category="telop", priority="high")
        rule2 = LearningRule(id="r2", rule_text="カメラアングル変更", category="camera", priority="medium")
        self.learner._rules[rule1.id] = rule1
        self.learner._rules[rule2.id] = rule2

        # "パンチライン" は telop と camera の両方のルールにマッチする
        hl = _make_highlight("01:00", "パンチライン", text="重要な発言")
        video = _make_video_data([hl])
        entries, applied = _apply_learned_rules(
            video, self.classification, self.income_eval, self.learner
        )
        assert len(applied) == 2
        applied_ids = {a["rule_id"] for a in applied}
        assert "r1" in applied_ids
        assert "r2" in applied_ids

    def test_非アクティブなルールは適用されない(self):
        """is_active=False のルールは get_active_rules() で返されない"""
        rule = LearningRule(
            id="r_inactive",
            rule_text="テロップ",
            category="telop",
            priority="high",
            is_active=False,
        )
        self.learner._rules[rule.id] = rule

        hl = _make_highlight("01:00", "実績数字", text="年収1000万")
        video = _make_video_data([hl])
        entries, applied = _apply_learned_rules(
            video, self.classification, self.income_eval, self.learner
        )
        assert entries == []
        assert applied == []

    def test_適用エントリにFB学習プレフィックスがつく(self):
        """生成されたエントリの instruction に [FB学習] プレフィックスがつく"""
        rule = LearningRule(
            id="r_prefix",
            rule_text="テロップを大きく",
            category="telop",
            priority="high",
        )
        self.learner._rules[rule.id] = rule

        hl = _make_highlight("01:00", "実績数字", text="年収500万")
        video = _make_video_data([hl])
        entries, _ = _apply_learned_rules(
            video, self.classification, self.income_eval, self.learner
        )
        assert len(entries) >= 1
        assert entries[0].instruction.startswith("[FB学習]")

    def test_direction_typeがカテゴリから正しくマッピングされる(self):
        """cutting → composite, color → color, etc."""
        test_cases = [
            ("cutting", "composite"),
            ("color", "color"),
            ("telop", "telop"),
            ("bgm", "composite"),
            ("camera", "camera"),
            ("composition", "camera"),
            ("tempo", "composite"),
            ("general", "composite"),
        ]
        for category, expected_type in test_cases:
            self.learner._rules.clear()
            rule = LearningRule(
                id=f"r_{category}",
                rule_text=f"{category}テスト",
                category=category,
                priority="medium",
            )
            self.learner._rules[rule.id] = rule

            # 各カテゴリに対応するハイライトカテゴリを選ぶ
            # category_map から対応するハイライトカテゴリを取得
            category_to_hl = {
                "cutting": "パンチライン",
                "color": "実績数字",
                "telop": "実績数字",
                "bgm": "メッセージ",
                "camera": "パンチライン",
                "composition": "属性紹介",
                "tempo": "パンチライン",
                "general": "パンチライン",  # generalはどこにもマッチしないので直接キーワード
            }
            hl_cat = category_to_hl.get(category, "パンチライン")
            hl = _make_highlight("01:00", hl_cat, text="カメラ カット テロップ BGM テンポ 構図 色")
            video = _make_video_data([hl])
            entries, applied = _apply_learned_rules(
                video, self.classification, self.income_eval, self.learner
            )
            if entries:
                assert entries[0].direction_type == expected_type, \
                    f"カテゴリ {category} のdirection_typeは {expected_type} であるべきだが {entries[0].direction_type} だった"


# ────────────────────────────────────────────────
# _generate_for_highlight
# ────────────────────────────────────────────────

class TestGenerateForHighlight:
    def test_実績数字カテゴリでtelopとcolorエントリを生成(self):
        hl = _make_highlight("01:00", "実績数字", text="年収1000万円台達成")
        entries = _generate_for_highlight(hl, _make_classification(), _make_income_eval())
        types = [e.direction_type for e in entries]
        assert "telop" in types
        assert "color" in types

    def test_パンチラインカテゴリでtelopとcameraとcolorエントリを生成(self):
        hl = _make_highlight("02:00", "パンチライン", text="人生は一度きりです")
        entries = _generate_for_highlight(hl, _make_classification("a"), _make_income_eval())
        types = [e.direction_type for e in entries]
        assert "telop" in types
        assert "camera" in types
        # 層a + パンチライン → 色変えも追加
        assert "color" in types

    def test_属性紹介カテゴリでtelopエントリを生成(self):
        hl = _make_highlight("00:30", "属性紹介", text="元アクセンチュア勤務")
        entries = _generate_for_highlight(hl, _make_classification(), _make_income_eval())
        types = [e.direction_type for e in entries]
        assert "telop" in types

    def test_TEKO価値カテゴリでcameraエントリを生成(self):
        hl = _make_highlight("03:00", "TEKO価値", text="TEKOのおかげで成長できた")
        entries = _generate_for_highlight(hl, _make_classification(), _make_income_eval())
        types = [e.direction_type for e in entries]
        assert "camera" in types

    def test_メッセージカテゴリでcameraエントリを生成(self):
        hl = _make_highlight("04:00", "メッセージ", text="最後に伝えたいことは")
        entries = _generate_for_highlight(hl, _make_classification(), _make_income_eval())
        types = [e.direction_type for e in entries]
        assert "camera" in types

    def test_全エントリのpriorityが有効値(self):
        categories = ["実績数字", "パンチライン", "属性紹介", "TEKO価値", "メッセージ"]
        for cat in categories:
            hl = _make_highlight("03:00", cat, text="年収1000万 テスト")
            entries = _generate_for_highlight(hl, _make_classification(), _make_income_eval())
            for e in entries:
                assert e.priority in ("high", "medium", "low"), \
                    f"カテゴリ{cat}のエントリ優先度 {e.priority} が無効"

    def test_層cでは色変えが追加されない(self):
        """層c + パンチライン → 色変えは追加されない"""
        hl = _make_highlight("02:00", "パンチライン", text="テスト発言")
        entries = _generate_for_highlight(hl, _make_classification("c", "層c"), _make_income_eval())
        types = [e.direction_type for e in entries]
        assert "color" not in types

    def test_層bでは色変えが追加される(self):
        """層b + パンチライン → 色変えが追加される"""
        hl = _make_highlight("02:00", "パンチライン", text="テスト発言")
        entries = _generate_for_highlight(hl, _make_classification("b", "層b"), _make_income_eval())
        types = [e.direction_type for e in entries]
        assert "color" in types

    def test_実績数字で数字パターンがない場合(self):
        """実績数字カテゴリでも数字パターンがなければtelopエントリなし"""
        hl = _make_highlight("01:00", "実績数字", text="実績がすごいです")
        entries = _generate_for_highlight(hl, _make_classification(), _make_income_eval())
        telop_entries = [e for e in entries if e.direction_type == "telop"]
        # 数字が含まれないのでtelopは生成されない（色変えのみ可能性あり）
        assert len(telop_entries) == 0

    def test_未知カテゴリではエントリが空(self):
        """定義外のカテゴリはエントリが生成されない"""
        hl = _make_highlight("01:00", "未知のカテゴリ", text="テスト")
        entries = _generate_for_highlight(hl, _make_classification(), _make_income_eval())
        assert len(entries) == 0


# ────────────────────────────────────────────────
# generate_directions() 基本動作テスト
# ────────────────────────────────────────────────

class TestGenerateDirectionsBasic:
    """generate_directions() のルールベース生成テスト"""

    def test_空のハイライトで空タイムラインを返す(self):
        video = _make_video_data([])
        timeline = generate_directions(video, _make_classification(), _make_income_eval())
        assert isinstance(timeline, DirectionTimeline)
        assert len(timeline.entries) == 0
        assert timeline.applied_rules == []

    def test_単一ハイライトでエントリが生成される(self):
        hl = _make_highlight("01:00", "パンチライン", text="名言テスト")
        video = _make_video_data([hl])
        timeline = generate_directions(video, _make_classification(), _make_income_eval())
        assert len(timeline.entries) >= 1

    def test_複数ハイライトでタイムスタンプ順にソートされる(self):
        highlights = [
            _make_highlight("03:00", "メッセージ", text="最後に"),
            _make_highlight("01:00", "実績数字", text="年収1000万円"),
            _make_highlight("02:00", "パンチライン", text="人生は一度きり"),
        ]
        video = _make_video_data(highlights)
        timeline = generate_directions(video, _make_classification(), _make_income_eval())

        # タイムスタンプ昇順
        timestamps = [e.timestamp for e in timeline.entries]
        seconds = [_timestamp_to_seconds(ts) for ts in timestamps]
        assert seconds == sorted(seconds)

    def test_feedback_learnerなしでもエラーにならない(self):
        hl = _make_highlight("01:00", "パンチライン", text="テスト")
        video = _make_video_data([hl])
        timeline = generate_directions(
            video, _make_classification(), _make_income_eval(),
            feedback_learner=None, video_learner=None,
        )
        assert isinstance(timeline, DirectionTimeline)
        assert timeline.applied_rules == []

    def test_LLM分析が失敗した場合は空文字(self):
        """LLM呼び出しが例外を投げた場合、llm_analysisは空文字（teko_core.llm移行後はAPIキー不要）"""
        hl = _make_highlight("01:00", "パンチライン", text="テスト")
        video = _make_video_data([hl])
        with patch("teko_core.llm.ask", side_effect=Exception("LLM unavailable")):
            timeline = generate_directions(
                video, _make_classification(), _make_income_eval()
            )
        assert timeline.llm_analysis == ""


# ────────────────────────────────────────────────
# generate_directions() + FB学習ルール統合テスト
# ────────────────────────────────────────────────

class TestGenerateDirectionsWithFeedbackLearner:
    """FeedbackLearner統合時のgenerate_directions()テスト"""

    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.learner = FeedbackLearner(data_dir=Path(self.tmp))

    def test_FB学習ルールがタイムラインに反映される(self):
        rule = LearningRule(
            id="r_fb_telop",
            rule_text="テロップを目立たせる",
            category="telop",
            priority="high",
        )
        self.learner._rules[rule.id] = rule

        hl = _make_highlight("01:00", "実績数字", text="年収2000万")
        video = _make_video_data([hl])
        timeline = generate_directions(
            video, _make_classification(), _make_income_eval(),
            feedback_learner=self.learner,
        )

        # 通常のエントリ + FB学習のエントリが含まれる
        fb_entries = [e for e in timeline.entries if "[FB学習]" in e.instruction]
        assert len(fb_entries) >= 1
        assert len(timeline.applied_rules) >= 1

    def test_applied_rulesの構造が正しい(self):
        rule = LearningRule(
            id="r_struct",
            rule_text="カメラ演出ルール",
            category="camera",
            priority="medium",
        )
        self.learner._rules[rule.id] = rule

        hl = _make_highlight("01:00", "パンチライン", text="テスト")
        video = _make_video_data([hl])
        timeline = generate_directions(
            video, _make_classification(), _make_income_eval(),
            feedback_learner=self.learner,
        )

        for ar in timeline.applied_rules:
            assert "rule_id" in ar
            assert "rule_text" in ar
            assert "category" in ar
            assert "priority" in ar


# ────────────────────────────────────────────────
# generate_directions() + 映像学習ルール統合テスト
# ────────────────────────────────────────────────

class TestGenerateDirectionsWithVideoLearner:
    """VideoLearner統合時のgenerate_directions()テスト"""

    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.vlearner = VideoLearner(data_dir=Path(self.tmp))

    def test_映像学習ルールが適用される(self):
        """確信度0.4以上のパターンがルールとして適用される"""
        from src.video_direction.tracker.video_learner import VideoPattern
        pattern = VideoPattern(
            id="vp_001",
            category="cutting",
            pattern="テスト映像パターン",
            confidence=0.8,
            source_count=5,
            is_active=True,
        )
        self.vlearner._patterns[pattern.id] = pattern

        hl = _make_highlight("01:00", "パンチライン", text="重要な発言")
        video = _make_video_data([hl])
        timeline = generate_directions(
            video, _make_classification(), _make_income_eval(),
            video_learner=self.vlearner,
        )
        # 映像学習ルールのエントリ（[FB学習]プレフィックスが付く）
        fb_entries = [e for e in timeline.entries if "[FB学習]" in e.instruction]
        assert len(fb_entries) >= 1

    def test_確信度が低いパターンは適用されない(self):
        """確信度0.4未満のパターンはルールにならない"""
        from src.video_direction.tracker.video_learner import VideoPattern
        pattern = VideoPattern(
            id="vp_low",
            category="cutting",
            pattern="低確信度パターン",
            confidence=0.2,
            source_count=1,
            is_active=True,
        )
        self.vlearner._patterns[pattern.id] = pattern

        hl = _make_highlight("01:00", "パンチライン", text="テスト")
        video = _make_video_data([hl])
        timeline = generate_directions(
            video, _make_classification(), _make_income_eval(),
            video_learner=self.vlearner,
        )
        # 映像学習ルールのエントリはなし
        vl_entries = [e for e in timeline.entries if "[FB学習]" in e.instruction]
        assert len(vl_entries) == 0


# ────────────────────────────────────────────────
# generate_directions() + FB + VideoLearner 同時統合テスト
# ────────────────────────────────────────────────

class TestGenerateDirectionsDualLearner:
    """FeedbackLearnerとVideoLearnerの同時使用テスト"""

    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.fb_learner = FeedbackLearner(data_dir=Path(self.tmp) / "fb")
        self.vl = VideoLearner(data_dir=Path(self.tmp) / "vl")

    def test_両方のルールが統合される(self):
        from src.video_direction.tracker.video_learner import VideoPattern
        # FBルール追加
        fb_rule = LearningRule(
            id="r_fb_dual",
            rule_text="テロップ演出",
            category="telop",
            priority="high",
        )
        self.fb_learner._rules[fb_rule.id] = fb_rule

        # 映像パターン追加
        vp = VideoPattern(
            id="vp_dual",
            category="camera",
            pattern="カメラワーク改善",
            confidence=0.9,
            source_count=3,
            is_active=True,
        )
        self.vl._patterns[vp.id] = vp

        hl = _make_highlight("01:00", "パンチライン", text="重要")
        video = _make_video_data([hl])
        timeline = generate_directions(
            video, _make_classification(), _make_income_eval(),
            feedback_learner=self.fb_learner,
            video_learner=self.vl,
        )

        # 両方のルールが applied_rules に含まれる
        assert len(timeline.applied_rules) >= 2
        rule_ids = {ar["rule_id"] for ar in timeline.applied_rules}
        assert "r_fb_dual" in rule_ids


# ────────────────────────────────────────────────
# LLM分析統合テスト（モック使用）
# ────────────────────────────────────────────────

class TestLLMAnalysisIntegration:
    """LLM分析部分のモックテスト"""

    def test_LLM分析結果がllm_analysisに入る(self):
        hl = _make_highlight("01:00", "パンチライン", text="テスト")
        video = _make_video_data([hl])

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="LLMからの追加分析テスト")]

        with patch("src.video_direction.analyzer.direction_generator._llm_analyze",
                    return_value="LLMからの追加分析テスト"):
            timeline = generate_directions(
                video, _make_classification(), _make_income_eval()
            )
            # _llm_analyzeをモックしたのでllm_analysisに反映される
            assert timeline.llm_analysis == "LLMからの追加分析テスト"

    def test_LLM例外時はllm_analysisが空(self):
        hl = _make_highlight("01:00", "パンチライン", text="テスト")
        video = _make_video_data([hl])

        with patch("src.video_direction.analyzer.direction_generator._llm_analyze",
                    side_effect=Exception("API Error")):
            timeline = generate_directions(
                video, _make_classification(), _make_income_eval()
            )
            assert timeline.llm_analysis == ""


# ────────────────────────────────────────────────
# DirectionEntry / DirectionTimeline データ構造テスト
# ────────────────────────────────────────────────

class TestDataStructures:
    """DirectionEntryとDirectionTimelineのデータ構造テスト"""

    def test_DirectionEntryの全フィールド(self):
        entry = DirectionEntry(
            timestamp="01:30",
            direction_type="telop",
            instruction="テロップ強調テスト",
            reason="テスト理由",
            priority="high",
        )
        assert entry.timestamp == "01:30"
        assert entry.direction_type == "telop"
        assert entry.instruction == "テロップ強調テスト"
        assert entry.reason == "テスト理由"
        assert entry.priority == "high"

    def test_DirectionTimelineのデフォルト値(self):
        timeline = DirectionTimeline()
        assert timeline.entries == []
        assert timeline.llm_analysis == ""
        assert timeline.applied_rules == []

    def test_DirectionTimelineにエントリ追加(self):
        entry = DirectionEntry(
            timestamp="00:30",
            direction_type="camera",
            instruction="寄り",
            reason="テスト",
            priority="medium",
        )
        timeline = DirectionTimeline(entries=[entry])
        assert len(timeline.entries) == 1
        assert timeline.entries[0].direction_type == "camera"

    def test_DirectionEntryのdirection_typeが想定値(self):
        """direction_typeは telop / camera / color / composite のいずれか"""
        valid_types = {"telop", "camera", "color", "composite"}
        for dt in valid_types:
            entry = DirectionEntry(
                timestamp="00:00",
                direction_type=dt,
                instruction="テスト",
                reason="テスト",
                priority="medium",
            )
            assert entry.direction_type in valid_types


# ────────────────────────────────────────────────
# 空の feedback / tracking 時の挙動テスト
# ────────────────────────────────────────────────

class TestEmptyInputBehavior:
    """空入力時のエッジケーステスト"""

    def test_空VideoDataでエラーなく完了(self):
        video = VideoData(title="")
        timeline = generate_directions(
            video, _make_classification(), _make_income_eval()
        )
        assert isinstance(timeline, DirectionTimeline)
        assert len(timeline.entries) == 0

    def test_ルールありだがハイライトなし(self):
        tmp = tempfile.mkdtemp()
        learner = FeedbackLearner(data_dir=Path(tmp))
        rule = LearningRule(id="r_empty", rule_text="テスト", category="telop", priority="high")
        learner._rules[rule.id] = rule

        video = _make_video_data([])
        timeline = generate_directions(
            video, _make_classification(), _make_income_eval(),
            feedback_learner=learner,
        )
        assert len(timeline.entries) == 0
        assert len(timeline.applied_rules) == 0

    def test_FB_learnerとvideo_learnerが両方Noneでも正常(self):
        hl = _make_highlight("01:00", "パンチライン", text="テスト")
        video = _make_video_data([hl])
        timeline = generate_directions(
            video, _make_classification(), _make_income_eval(),
            feedback_learner=None, video_learner=None,
        )
        assert isinstance(timeline, DirectionTimeline)
        assert timeline.applied_rules == []


# ────────────────────────────────────────────────
# 優先度ソートテスト
# ────────────────────────────────────────────────

class TestPrioritySort:
    """エントリの優先度に関するテスト"""

    def test_実績数字のtelopはhigh(self):
        hl = _make_highlight("01:00", "実績数字", text="年収1000万円")
        entries = _generate_for_highlight(hl, _make_classification(), _make_income_eval())
        telop_entries = [e for e in entries if e.direction_type == "telop"]
        for e in telop_entries:
            assert e.priority == "high"

    def test_パンチラインのtelopとcameraはhigh(self):
        hl = _make_highlight("02:00", "パンチライン", text="人生は一度きりです")
        entries = _generate_for_highlight(hl, _make_classification(), _make_income_eval())
        for e in entries:
            if e.direction_type in ("telop", "camera"):
                assert e.priority == "high"

    def test_属性紹介のtelopはmedium(self):
        hl = _make_highlight("00:30", "属性紹介", text="元アクセンチュア")
        entries = _generate_for_highlight(hl, _make_classification(), _make_income_eval())
        telop_entries = [e for e in entries if e.direction_type == "telop"]
        for e in telop_entries:
            assert e.priority == "medium"

    def test_タイムスタンプ順ソートは優先度に関係なく行われる(self):
        """generate_directionsはタイムスタンプ順でソート（優先度ではない）"""
        highlights = [
            _make_highlight("05:00", "メッセージ", text="最後のメッセージ"),  # medium
            _make_highlight("01:00", "実績数字", text="年収2000万"),  # high
        ]
        video = _make_video_data(highlights)
        timeline = generate_directions(video, _make_classification(), _make_income_eval())
        if len(timeline.entries) >= 2:
            ts0 = _timestamp_to_seconds(timeline.entries[0].timestamp)
            ts1 = _timestamp_to_seconds(timeline.entries[-1].timestamp)
            assert ts0 <= ts1


# ────────────────────────────────────────────────
# get_learning_context() テスト
# ────────────────────────────────────────────────

class TestGetLearningContext:
    """get_learning_context()の挙動テスト"""

    def test_両方Noneの場合(self):
        ctx = get_learning_context(feedback_learner=None, video_learner=None)
        assert ctx["active_rules"] == []
        assert ctx["has_rules"] is False
        assert ctx["insights"] == {}
        assert ctx["video_learning"] == {}

    def test_FB_learnerのみ(self):
        tmp = tempfile.mkdtemp()
        learner = FeedbackLearner(data_dir=Path(tmp))
        rule = LearningRule(
            id="r_ctx",
            rule_text="テスト",
            category="telop",
            priority="high",
        )
        learner._rules[rule.id] = rule

        ctx = get_learning_context(feedback_learner=learner)
        assert ctx["has_rules"] is True
        assert len(ctx["active_rules"]) >= 1
        assert ctx["active_rules"][0]["source"] == "feedback"

    def test_video_learnerのみ(self):
        from src.video_direction.tracker.video_learner import VideoPattern
        tmp = tempfile.mkdtemp()
        vl = VideoLearner(data_dir=Path(tmp))
        pattern = VideoPattern(
            id="vp_ctx",
            category="cutting",
            pattern="テスト",
            confidence=0.9,
            source_count=3,
            is_active=True,
        )
        vl._patterns[pattern.id] = pattern

        ctx = get_learning_context(video_learner=vl)
        assert ctx["has_rules"] is True
        assert len(ctx["active_rules"]) >= 1
        assert ctx["active_rules"][0]["source"] == "video_tracking"

    def test_両方ありの場合ルールが統合される(self):
        from src.video_direction.tracker.video_learner import VideoPattern
        tmp = tempfile.mkdtemp()
        fb = FeedbackLearner(data_dir=Path(tmp) / "fb")
        fb._rules["r_fb"] = LearningRule(id="r_fb", rule_text="FB", category="telop", priority="high")

        vl = VideoLearner(data_dir=Path(tmp) / "vl")
        vl._patterns["vp_01"] = VideoPattern(
            id="vp_01", category="camera", pattern="VL", confidence=0.9, source_count=3, is_active=True,
        )

        ctx = get_learning_context(feedback_learner=fb, video_learner=vl)
        sources = {r["source"] for r in ctx["active_rules"]}
        assert "feedback" in sources
        assert "video_tracking" in sources

    def test_active_rulesの構造(self):
        tmp = tempfile.mkdtemp()
        fb = FeedbackLearner(data_dir=Path(tmp))
        fb._rules["r_s"] = LearningRule(id="r_s", rule_text="テスト", category="color", priority="medium")

        ctx = get_learning_context(feedback_learner=fb)
        for rule in ctx["active_rules"]:
            assert "id" in rule
            assert "rule_text" in rule
            assert "category" in rule
            assert "priority" in rule
            assert "applied_count" in rule
            assert "source" in rule
