"""FeedbackLearner のユニットテスト"""

import sys
import json
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.video_direction.tracker.feedback_learner import (
    FeedbackLearner,
    FeedbackPattern,
    LearningRule,
    _normalize_text,
    _tokenize_for_similarity,
)


# ────────────────────────────────────────────────
# _normalize_text
# ────────────────────────────────────────────────

class TestNormalizeText:
    def test_空文字はそのまま返す(self):
        assert _normalize_text("") == ""

    def test_Noneは空文字を返す(self):
        assert _normalize_text(None) == ""

    def test_大文字を小文字に変換(self):
        result = _normalize_text("BGM が良い")
        assert result == result.lower()

    def test_記号を除去する(self):
        # 「」【】等の記号はスペースに置換される
        result = _normalize_text("【テロップ】が良い")
        assert "【" not in result
        assert "】" not in result

    def test_前後のスペースをトリム(self):
        result = _normalize_text("  テスト  ")
        assert result == result.strip()

    def test_連続スペースを圧縮(self):
        result = _normalize_text("テスト  テキスト")
        assert "  " not in result


# ────────────────────────────────────────────────
# _tokenize_for_similarity
# ────────────────────────────────────────────────

class TestTokenizeForSimilarity:
    def test_空文字は空セットを返す(self):
        assert _tokenize_for_similarity("") == set()

    def test_2文字未満のトークンを除外(self):
        tokens = _tokenize_for_similarity("a bc def")
        assert "a" not in tokens
        assert "bc" in tokens

    def test_日本語文はバイグラムを含む(self):
        tokens = _tokenize_for_similarity("カット割り")
        # 2-gramが含まれること
        assert any(len(t) == 2 for t in tokens)

    def test_同一テキストのトークン集合は等しい(self):
        t1 = _tokenize_for_similarity("テロップが良い")
        t2 = _tokenize_for_similarity("テロップが良い")
        assert t1 == t2


# ────────────────────────────────────────────────
# FeedbackLearner._classify_feedback
# ────────────────────────────────────────────────

class TestClassifyFeedback:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.learner = FeedbackLearner(data_dir=Path(self.tmp))

    def test_テロップキーワードでtelop分類(self):
        result = self.learner._classify_feedback("テロップのフォントが小さい")
        assert result == "telop"

    def test_BGMキーワードでbgm分類(self):
        result = self.learner._classify_feedback("BGMが合っていない")
        assert result == "bgm"

    def test_カメラキーワードでcamera分類(self):
        result = self.learner._classify_feedback("カメラアングルを変えてほしい")
        assert result == "camera"

    def test_カットキーワードでcutting分類(self):
        result = self.learner._classify_feedback("カット割りが早すぎる")
        assert result == "cutting"

    def test_色キーワードでcolor分類(self):
        result = self.learner._classify_feedback("色調が暗い")
        assert result == "color"

    def test_テンポキーワードでtempo分類(self):
        result = self.learner._classify_feedback("テンポが遅い")
        assert result == "tempo"

    def test_該当なしはgeneral(self):
        result = self.learner._classify_feedback("全体的に良いと思います")
        assert result == "general"


# ────────────────────────────────────────────────
# FeedbackLearner._is_similar
# ────────────────────────────────────────────────

class TestIsSimilar:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.learner = FeedbackLearner(data_dir=Path(self.tmp))

    def test_完全一致はTrue(self):
        assert self.learner._is_similar("テロップが小さい", "テロップが小さい") is True

    def test_全く異なるテキストはFalse(self):
        assert self.learner._is_similar("テロップ", "BGMが合わない") is False

    def test_空文字はFalse(self):
        assert self.learner._is_similar("", "テロップ") is False
        assert self.learner._is_similar("テロップ", "") is False

    def test_長文包含はTrue(self):
        # 8文字以上の文が相手に含まれる場合はTrue
        short = "テロップのフォントを変えてほしい"
        long = "テロップのフォントを変えてほしいと思います"
        assert self.learner._is_similar(short, long) is True


# ────────────────────────────────────────────────
# FeedbackLearner.ingest_feedback
# ────────────────────────────────────────────────

class TestIngestFeedback:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.learner = FeedbackLearner(data_dir=Path(self.tmp))

    def test_新規FBでパターンが生成される(self):
        patterns = self.learner.ingest_feedback("fb001", "テロップのフォントが小さい")
        assert len(patterns) == 1
        assert patterns[0].category == "telop"

    def test_同じFBを複数回投入すると頻度が増える(self):
        self.learner.ingest_feedback("fb001", "テロップのフォントが小さい")
        self.learner.ingest_feedback("fb002", "テロップのフォントが小さい")
        patterns = self.learner.get_patterns(category="telop")
        assert patterns[0].frequency >= 2

    def test_5回投入で高確信度ルールが生成される(self):
        """頻度5以上（確信度1.0）でルールが自動生成される"""
        for i in range(5):
            self.learner.ingest_feedback(f"fb{i:03d}", "テロップのフォントが小さい")
        rules = self.learner.get_active_rules(category="telop")
        assert len(rules) >= 1
        assert rules[0].category == "telop"

    def test_JSONに永続化される(self):
        self.learner.ingest_feedback("fb001", "テロップのフォントが小さい")
        patterns_file = Path(self.tmp) / "feedback_patterns.json"
        assert patterns_file.exists()
        data = json.loads(patterns_file.read_text())
        assert len(data["patterns"]) == 1


# ────────────────────────────────────────────────
# FeedbackLearner.get_active_rules
# ────────────────────────────────────────────────

class TestGetActiveRules:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.learner = FeedbackLearner(data_dir=Path(self.tmp))

    def _make_rule(self, category: str, priority: str = "medium") -> str:
        """テスト用ルールを直接作成して返す（ID）"""
        rule = LearningRule(
            id=f"rule_{category}",
            rule_text=f"[{category}] テストルール",
            category=category,
            priority=priority,
        )
        self.learner._rules[rule.id] = rule
        return rule.id

    def test_カテゴリフィルタが機能する(self):
        self._make_rule("telop")
        self._make_rule("camera")
        rules = self.learner.get_active_rules(category="telop")
        assert all(r.category == "telop" for r in rules)
        assert len(rules) == 1

    def test_is_active_Falseは除外される(self):
        rid = self._make_rule("telop")
        self.learner._rules[rid].is_active = False
        rules = self.learner.get_active_rules()
        assert all(r.id != rid for r in rules)

    def test_highが先頭に来る(self):
        self._make_rule("telop", "medium")
        self._make_rule("camera", "high")
        rules = self.learner.get_active_rules()
        assert rules[0].priority == "high"


# ────────────────────────────────────────────────
# FeedbackLearner.get_insights
# ────────────────────────────────────────────────

class TestGetInsights:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.learner = FeedbackLearner(data_dir=Path(self.tmp))

    def test_初期状態のinsights(self):
        insights = self.learner.get_insights()
        assert insights["total_patterns"] == 0
        assert insights["total_rules"] == 0
        assert insights["active_rules"] == 0

    def test_パターン追加後のinsights(self):
        self.learner.ingest_feedback("fb001", "テロップのフォントが小さい")
        insights = self.learner.get_insights()
        assert insights["total_patterns"] == 1
        assert "telop" in insights["category_distribution"]


# ────────────────────────────────────────────────
# _load による永続化の往復テスト
# ────────────────────────────────────────────────

class TestPersistence:
    def test_保存と再ロードでデータが一致する(self):
        tmp = tempfile.mkdtemp()
        learner1 = FeedbackLearner(data_dir=Path(tmp))
        learner1.ingest_feedback("fb001", "テロップのフォントが小さい")

        # 新規インスタンスで再読み込み
        learner2 = FeedbackLearner(data_dir=Path(tmp))
        patterns = learner2.get_patterns()
        assert len(patterns) == 1
        assert patterns[0].category == "telop"
