"""B-3: 編集者別スキルマトリクスのテスト"""
import pytest
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from video_direction.tracker.skill_matrix import (
    SkillMatrix,
    EditorProfile,
    SkillSnapshot,
    TaskMatch,
    SKILL_DIMENSIONS,
    SKILL_LABELS,
    _normalize_editor_id,
    _calculate_match,
)


@pytest.fixture
def tmp_dir():
    """テスト用一時ディレクトリ"""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def matrix(tmp_dir):
    """テスト用スキルマトリクスインスタンス"""
    return SkillMatrix(data_dir=tmp_dir)


def _sample_scores(base=70):
    """テスト用スコアを生成"""
    return {dim: base + i * 2 for i, dim in enumerate(SKILL_DIMENSIONS)}


# === 基本テスト ===

class TestSkillMatrixBasic:
    """スキルマトリクスの基本テスト"""

    def test_初期化(self, matrix):
        assert isinstance(matrix, SkillMatrix)
        assert len(matrix.editors) == 0

    def test_編集者スキル登録(self, matrix):
        profile = matrix.update_editor_skills(
            editor_name="パグさん",
            dimension_scores=_sample_scores(70),
            video_id="test_v1",
        )
        assert profile.name == "パグさん"
        assert len(profile.skill_history) == 1
        assert profile.total_videos == 1

    def test_同一編集者のスキル更新(self, matrix):
        matrix.update_editor_skills("パグさん", _sample_scores(60), "v1")
        matrix.update_editor_skills("パグさん", _sample_scores(80), "v2")
        profile = matrix.get_editor("パグさん")
        assert profile.total_videos == 2
        assert len(profile.skill_history) == 2
        # 指数移動平均で更新されている
        for dim in SKILL_DIMENSIONS:
            assert profile.current_skills[dim] > 60  # 初期値60から上昇

    def test_複数編集者の管理(self, matrix):
        matrix.update_editor_skills("編集者A", _sample_scores(70))
        matrix.update_editor_skills("編集者B", _sample_scores(80))
        assert len(matrix.editors) == 2

    def test_get_editor存在しない場合はNone(self, matrix):
        assert matrix.get_editor("存在しない") is None


# === 永続化テスト ===

class TestSkillPersistence:
    """データ永続化のテスト"""

    def test_保存と読み込み(self, tmp_dir):
        sm1 = SkillMatrix(data_dir=tmp_dir)
        sm1.update_editor_skills("テスト", _sample_scores(70))

        sm2 = SkillMatrix(data_dir=tmp_dir)
        profile = sm2.get_editor("テスト")
        assert profile is not None
        assert profile.name == "テスト"

    def test_clear_all(self, matrix):
        matrix.update_editor_skills("テスト", _sample_scores(70))
        matrix.clear_all()
        assert len(matrix.editors) == 0


# === 得意/苦手判定テスト ===

class TestStrengthsWeaknesses:
    """得意/苦手領域判定のテスト"""

    def test_得意領域の判定(self, matrix):
        scores = {
            "cut": 90, "color": 85, "telop": 60,
            "bgm": 55, "camera": 70, "composition": 65, "tempo": 50,
        }
        profile = matrix.update_editor_skills("テスト", scores)
        assert "カット割り" in profile.strengths
        assert "色彩" in profile.strengths

    def test_苦手領域の判定(self, matrix):
        scores = {
            "cut": 90, "color": 85, "telop": 60,
            "bgm": 55, "camera": 70, "composition": 65, "tempo": 50,
        }
        profile = matrix.update_editor_skills("テスト", scores)
        assert "テンポ" in profile.weaknesses


# === マッチング提案テスト ===

class TestTaskMatching:
    """タスクマッチング提案のテスト"""

    def test_最適編集者の提案(self, matrix):
        matrix.update_editor_skills("編集者A", {
            "cut": 90, "color": 85, "telop": 80,
            "bgm": 70, "camera": 75, "composition": 80, "tempo": 85,
        })
        matrix.update_editor_skills("編集者B", {
            "cut": 60, "color": 65, "telop": 90,
            "bgm": 85, "camera": 55, "composition": 60, "tempo": 70,
        })

        # カット割り重視のタスク
        matches = matrix.suggest_best_editor(
            required_skills={"cut": 100, "color": 50}
        )
        assert len(matches) == 2
        assert matches[0].editor_name == "編集者A"  # カット割り90

    def test_編集者の除外(self, matrix):
        matrix.update_editor_skills("A", _sample_scores(80))
        matrix.update_editor_skills("B", _sample_scores(70))
        matches = matrix.suggest_best_editor(
            required_skills={"cut": 100},
            exclude_editors=["A"],
        )
        assert len(matches) == 1
        assert matches[0].editor_name == "B"

    def test_空のrequired_skills(self, matrix):
        matrix.update_editor_skills("テスト", _sample_scores(70))
        matches = matrix.suggest_best_editor(required_skills={})
        assert len(matches) == 1

    def test_スキルなし編集者はマッチングされない(self, matrix):
        # current_skillsが空の場合
        profile = EditorProfile(
            editor_id="empty", name="空の人",
            created_at="", updated_at="",
        )
        matrix.editors["empty"] = profile
        matches = matrix.suggest_best_editor(required_skills={"cut": 100})
        assert all(m.editor_id != "empty" for m in matches)


# === スキル成長推移テスト ===

class TestSkillGrowth:
    """スキル成長推移のテスト"""

    def test_成長推移の取得(self, matrix):
        matrix.update_editor_skills("テスト", _sample_scores(60), "v1")
        matrix.update_editor_skills("テスト", _sample_scores(70), "v2")
        matrix.update_editor_skills("テスト", _sample_scores(80), "v3")
        growth = matrix.get_skill_growth("テスト")
        assert len(growth) == 3
        # 各スナップショットにoverallとscoresがある
        for g in growth:
            assert "overall" in g
            assert "scores" in g

    def test_存在しない編集者の成長推移(self, matrix):
        growth = matrix.get_skill_growth("存在しない")
        assert growth == []


# === スキル比較テスト ===

class TestSkillComparison:
    """スキル比較表のテスト"""

    def test_比較表の生成(self, matrix):
        matrix.update_editor_skills("A", _sample_scores(80))
        matrix.update_editor_skills("B", _sample_scores(70))
        comparison = matrix.get_skill_comparison()
        assert "dimensions" in comparison
        assert "editors" in comparison
        assert len(comparison["dimensions"]) == 7
        assert len(comparison["editors"]) == 2

    def test_空の比較表(self, matrix):
        comparison = matrix.get_skill_comparison()
        assert comparison["editors"] == []


# === ユーティリティテスト ===

class TestUtilities:
    """ユーティリティ関数のテスト"""

    def test_editor_id正規化(self):
        assert _normalize_editor_id("パグさん") == "パグさん"
        assert _normalize_editor_id("  テスト  ") == "テスト"
        assert _normalize_editor_id("Test User") == "test_user"

    def test_全スキル次元にラベルがある(self):
        for dim in SKILL_DIMENSIONS:
            assert dim in SKILL_LABELS


# === EditorProfile メソッドテスト ===

class TestEditorProfile:
    """EditorProfileのメソッドテスト"""

    def test_指数移動平均更新(self):
        profile = EditorProfile(
            editor_id="test", name="テスト",
            created_at="", updated_at="",
        )
        # 初回は直接設定
        profile.update_skills({"cut": 80, "color": 70}, "v1")
        assert profile.current_skills["cut"] == 80

        # 2回目は指数移動平均（alpha=0.3）
        profile.update_skills({"cut": 100, "color": 60}, "v2")
        # 0.3 * 100 + 0.7 * 80 = 86.0
        assert profile.current_skills["cut"] == 86.0
