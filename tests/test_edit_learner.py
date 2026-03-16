"""EditLearner のユニットテスト"""

import sys
import json
import tempfile
from pathlib import Path
from dataclasses import dataclass
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.video_direction.tracker.edit_learner import (
    EditLearner,
    EditPattern,
    EditLearningRule,
    _normalize_text,
    _tokenize_for_similarity,
)


# ────────────────────────────────────────────────
# ヘルパー: diff_resultのモック
# ────────────────────────────────────────────────

@dataclass
class MockDiffResult:
    edit_id: str
    changes: list


# ────────────────────────────────────────────────
# パターン蓄積テスト
# ────────────────────────────────────────────────

class TestIngestEdit:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.learner = EditLearner(data_dir=Path(self.tmp))

    def test_新規パターンが蓄積される(self):
        diff = MockDiffResult(
            edit_id="edit_0",
            changes=[{"type": "modify", "content": "テロップサイズを拡大", "context": ""}],
        )
        result = self.learner.ingest_edit("proj_1", "direction", diff)
        assert result["new_patterns"] == 1
        assert result["updated_patterns"] == 0
        assert len(self.learner._patterns) == 1

    def test_類似パターンはfrequencyが増加する(self):
        diff1 = MockDiffResult(
            edit_id="edit_0",
            changes=[{"type": "modify", "content": "テロップサイズを拡大する", "context": ""}],
        )
        diff2 = MockDiffResult(
            edit_id="edit_1",
            changes=[{"type": "modify", "content": "テロップのサイズを拡大した", "context": ""}],
        )
        self.learner.ingest_edit("proj_1", "direction", diff1)
        result = self.learner.ingest_edit("proj_1", "direction", diff2)
        assert result["updated_patterns"] == 1
        assert len(self.learner._patterns) == 1
        pattern = list(self.learner._patterns.values())[0]
        assert pattern.frequency == 2

    def test_異なるカテゴリの変更は別パターンになる(self):
        diff = MockDiffResult(
            edit_id="edit_0",
            changes=[
                {"type": "modify", "content": "テロップサイズを拡大", "context": ""},
                {"type": "modify", "content": "BGMのボリュームを下げる", "context": ""},
            ],
        )
        result = self.learner.ingest_edit("proj_1", "direction", diff)
        assert result["new_patterns"] == 2
        categories = {p.category for p in self.learner._patterns.values()}
        assert "telop" in categories
        assert "bgm" in categories

    def test_空のchangesは何も蓄積しない(self):
        diff = MockDiffResult(edit_id="edit_0", changes=[])
        result = self.learner.ingest_edit("proj_1", "direction", diff)
        assert result["new_patterns"] == 0
        assert len(self.learner._patterns) == 0

    def test_asset_typeが正しく記録される(self):
        diff = MockDiffResult(
            edit_id="edit_0",
            changes=[{"type": "add", "content": "タイトルにキーワード追加", "context": ""}],
        )
        self.learner.ingest_edit("proj_1", "title", diff)
        pattern = list(self.learner._patterns.values())[0]
        assert pattern.asset_type == "title"

    def test_change_typeがaddの場合プレフィックスが付く(self):
        diff = MockDiffResult(
            edit_id="edit_0",
            changes=[{"type": "add", "content": "新しいテロップ追加", "context": ""}],
        )
        self.learner.ingest_edit("proj_1", "direction", diff)
        pattern = list(self.learner._patterns.values())[0]
        assert pattern.pattern.startswith("追加")

    def test_confidenceは3回で1_0に到達(self):
        """手修正の閾値: confidence = frequency / 3.0"""
        for i in range(3):
            diff = MockDiffResult(
                edit_id=f"edit_{i}",
                changes=[{"type": "modify", "content": "テロップサイズを拡大する修正", "context": ""}],
            )
            self.learner.ingest_edit("proj_1", "direction", diff)
        pattern = list(self.learner._patterns.values())[0]
        assert pattern.frequency == 3
        assert pattern.confidence == 1.0

    def test_dictとオブジェクト両方のchangeに対応(self):
        """changeがdictでもオブジェクトでも動作する"""
        @dataclass
        class MockChange:
            type: str
            content: str
            context: str

        diff = MockDiffResult(
            edit_id="edit_0",
            changes=[MockChange(type="modify", content="カメラアングル変更", context="")],
        )
        result = self.learner.ingest_edit("proj_1", "direction", diff)
        assert result["new_patterns"] == 1


# ────────────────────────────────────────────────
# ルール生成閾値テスト
# ────────────────────────────────────────────────

class TestRuleGeneration:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.learner = EditLearner(data_dir=Path(self.tmp))

    def test_閾値未満ではルール生成されない(self):
        """confidence 0.33 (1回) < 0.5 → ルール未生成"""
        diff = MockDiffResult(
            edit_id="edit_0",
            changes=[{"type": "modify", "content": "テロップサイズ拡大", "context": ""}],
        )
        result = self.learner.ingest_edit("proj_1", "direction", diff)
        assert result["rules_generated"] == 0
        assert len(self.learner._rules) == 0

    def test_2回でルール生成される(self):
        """confidence 0.67 (2回) >= 0.5 → ルール生成"""
        for i in range(2):
            diff = MockDiffResult(
                edit_id=f"edit_{i}",
                changes=[{"type": "modify", "content": "テロップサイズを拡大する修正", "context": ""}],
            )
            self.learner.ingest_edit("proj_1", "direction", diff)
        assert len(self.learner._rules) == 1

    def test_ルールに手修正学習タグが付く(self):
        for i in range(2):
            diff = MockDiffResult(
                edit_id=f"edit_{i}",
                changes=[{"type": "modify", "content": "テロップサイズを拡大する修正", "context": ""}],
            )
            self.learner.ingest_edit("proj_1", "direction", diff)
        rule = list(self.learner._rules.values())[0]
        assert "[手修正学習]" in rule.rule_text
        assert "2回の手修正から学習" in rule.rule_text

    def test_高確信度パターンはhighプライオリティ(self):
        """confidence >= 0.8 → priority = high"""
        for i in range(3):
            diff = MockDiffResult(
                edit_id=f"edit_{i}",
                changes=[{"type": "modify", "content": "テロップサイズ拡大修正", "context": ""}],
            )
            self.learner.ingest_edit("proj_1", "direction", diff)
        rule = list(self.learner._rules.values())[0]
        assert rule.priority == "high"

    def test_get_active_rulesでフィルタできる(self):
        for i in range(2):
            diff = MockDiffResult(
                edit_id=f"edit_{i}",
                changes=[
                    {"type": "modify", "content": "テロップサイズ拡大", "context": ""},
                    {"type": "modify", "content": "BGMボリューム調整", "context": ""},
                ],
            )
            self.learner.ingest_edit("proj_1", "direction", diff)
        all_rules = self.learner.get_active_rules()
        telop_rules = self.learner.get_active_rules(category="telop")
        assert len(all_rules) >= 2
        assert all(r.category == "telop" for r in telop_rules)

    def test_asset_typeでフィルタできる(self):
        for i in range(2):
            diff = MockDiffResult(
                edit_id=f"edit_{i}",
                changes=[{"type": "modify", "content": "テロップサイズ拡大", "context": ""}],
            )
            self.learner.ingest_edit("proj_1", "direction", diff)
        direction_rules = self.learner.get_active_rules(asset_type="direction")
        title_rules = self.learner.get_active_rules(asset_type="title")
        assert len(direction_rules) == 1
        assert len(title_rules) == 0


# ────────────────────────────────────────────────
# 永続化テスト
# ────────────────────────────────────────────────

class TestPersistence:
    def test_保存と読み込みが一致する(self):
        tmp = tempfile.mkdtemp()
        learner1 = EditLearner(data_dir=Path(tmp))
        for i in range(3):
            diff = MockDiffResult(
                edit_id=f"edit_{i}",
                changes=[{"type": "modify", "content": "テロップサイズ拡大修正", "context": ""}],
            )
            learner1.ingest_edit("proj_1", "direction", diff)

        # 新しいインスタンスで読み込み
        learner2 = EditLearner(data_dir=Path(tmp))
        assert len(learner2._patterns) == len(learner1._patterns)
        assert len(learner2._rules) == len(learner1._rules)
        # パターンの中身が一致
        for pid in learner1._patterns:
            assert pid in learner2._patterns
            assert learner2._patterns[pid].frequency == learner1._patterns[pid].frequency
            assert learner2._patterns[pid].confidence == learner1._patterns[pid].confidence

    def test_パターンJSONが正しいフォーマット(self):
        tmp = tempfile.mkdtemp()
        learner = EditLearner(data_dir=Path(tmp))
        diff = MockDiffResult(
            edit_id="edit_0",
            changes=[{"type": "modify", "content": "テロップサイズ拡大", "context": ""}],
        )
        learner.ingest_edit("proj_1", "direction", diff)

        data = json.loads((Path(tmp) / "edit_patterns.json").read_text())
        assert "patterns" in data
        assert "updated_at" in data
        pattern = data["patterns"][0]
        assert pattern["id"].startswith("epat_")
        assert pattern["asset_type"] == "direction"
        assert pattern["category"] == "telop"

    def test_ルールJSONが正しいフォーマット(self):
        tmp = tempfile.mkdtemp()
        learner = EditLearner(data_dir=Path(tmp))
        for i in range(2):
            diff = MockDiffResult(
                edit_id=f"edit_{i}",
                changes=[{"type": "modify", "content": "テロップサイズ拡大修正", "context": ""}],
            )
            learner.ingest_edit("proj_1", "direction", diff)

        data = json.loads((Path(tmp) / "edit_rules.json").read_text())
        assert "rules" in data
        rule = data["rules"][0]
        assert rule["id"].startswith("erule_")
        assert "[手修正学習]" in rule["rule_text"]


# ────────────────────────────────────────────────
# get_insightsテスト
# ────────────────────────────────────────────────

class TestGetInsights:
    def test_空の状態でinsightsを取得できる(self):
        tmp = tempfile.mkdtemp()
        learner = EditLearner(data_dir=Path(tmp))
        insights = learner.get_insights()
        assert insights["total_patterns"] == 0
        assert insights["total_rules"] == 0

    def test_データがある状態のinsights(self):
        tmp = tempfile.mkdtemp()
        learner = EditLearner(data_dir=Path(tmp))
        for i in range(3):
            diff = MockDiffResult(
                edit_id=f"edit_{i}",
                changes=[
                    {"type": "modify", "content": "テロップサイズ拡大", "context": ""},
                    {"type": "modify", "content": "カメラアングル変更", "context": ""},
                ],
            )
            learner.ingest_edit("proj_1", "direction", diff)
        insights = learner.get_insights()
        assert insights["total_patterns"] == 2
        assert insights["total_rules"] >= 1
        assert "telop" in insights["category_distribution"]
        assert "direction" in insights["asset_type_distribution"]


# ────────────────────────────────────────────────
# カテゴリ分類テスト
# ────────────────────────────────────────────────

class TestClassifyEdit:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.learner = EditLearner(data_dir=Path(self.tmp))

    def test_テロップ関連(self):
        assert self.learner._classify_edit("テロップサイズ変更") == "telop"

    def test_BGM関連(self):
        assert self.learner._classify_edit("BGMボリューム調整") == "bgm"

    def test_カメラ関連(self):
        assert self.learner._classify_edit("カメラアングルを変更") == "camera"

    def test_色関連(self):
        assert self.learner._classify_edit("色調補正を追加") == "color"

    def test_カット関連(self):
        assert self.learner._classify_edit("カット割りを変更") == "cutting"

    def test_テンポ関連(self):
        assert self.learner._classify_edit("テンポを速くする") == "tempo"

    def test_不明はgeneral(self):
        assert self.learner._classify_edit("全体的に良くする") == "general"

    def test_contextも分類に使われる(self):
        assert self.learner._classify_edit("サイズ変更", "テロップ関連の修正") == "telop"


# ────────────────────────────────────────────────
# direction_generatorとの統合テスト
# ────────────────────────────────────────────────

class TestDirectionGeneratorIntegration:
    """direction_generatorのget_learning_contextとの統合テスト"""

    def test_get_learning_contextにedit_learnerを渡せる(self):
        """edit_learnerのルールがget_learning_contextの結果に含まれる"""
        tmp = tempfile.mkdtemp()
        learner = EditLearner(data_dir=Path(tmp))

        # ルール生成までデータを蓄積
        for i in range(3):
            diff = MockDiffResult(
                edit_id=f"edit_{i}",
                changes=[{"type": "modify", "content": "テロップサイズ拡大修正", "context": ""}],
            )
            learner.ingest_edit("proj_1", "direction", diff)

        # direction_generatorのget_learning_contextをインポート
        from src.video_direction.analyzer.direction_generator import get_learning_context
        context = get_learning_context(edit_learner=learner)
        assert context["has_rules"] is True
        assert len(context["active_rules"]) >= 1
        assert any(r["source"] == "edit" for r in context["active_rules"])
        assert context["edit_learning"]["total_patterns"] > 0

    def test_edit_learnerなしでも互換性が保たれる(self):
        """edit_learner=Noneの場合、既存動作に影響しない"""
        from src.video_direction.analyzer.direction_generator import get_learning_context
        context = get_learning_context()
        assert context["has_rules"] is False
        assert "edit_learning" in context
        assert context["edit_learning"] == {}

    def test_EditLearningRuleはLearningRuleと互換のインターフェースを持つ(self):
        """_apply_learned_rules()が期待する属性（rule_text, category, priority, applied_count, id, is_active）を持つ"""
        rule = EditLearningRule(
            id="erule_test",
            rule_text="[手修正学習] テスト",
            asset_type="direction",
            category="telop",
        )
        # _apply_learned_rules()が期待する属性の存在チェック
        assert hasattr(rule, "id")
        assert hasattr(rule, "rule_text")
        assert hasattr(rule, "category")
        assert hasattr(rule, "priority")
        assert hasattr(rule, "applied_count")
        assert hasattr(rule, "is_active")
