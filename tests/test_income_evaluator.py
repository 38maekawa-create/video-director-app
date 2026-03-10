"""income_evaluator のユニットテスト"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.integrations.ai_dev5_connector import parse_markdown_file
from src.video_direction.analyzer.income_evaluator import evaluate_income, _extract_age_bracket


SAMPLE_FILES = {
    "izu": Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_Izuさん：30代中盤元アクセンチュア年収1000万円台.md",
    "ryosuke": Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_りょうすけさん：20代後半内資IT勤務年収600万.md",
    "yurika": Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.28_ゆりかさん.md",
}


class TestEvaluateIncome:
    """年収演出判断のテスト"""

    def test_izu_emphasize_on(self):
        """Izuさん: 年収1500万→3000万 → 強調ON"""
        if not SAMPLE_FILES["izu"].exists():
            return
        data = parse_markdown_file(SAMPLE_FILES["izu"])
        result = evaluate_income(data)
        assert result.emphasize is True, f"Izuさんは強調ONであるべき（理由: {result.emphasis_reason}）"

    def test_ryosuke_emphasize_off(self):
        """りょうすけさん: 20代後半、年収600万 → 強調OFF（基準600万と同等）"""
        if not SAMPLE_FILES["ryosuke"].exists():
            return
        data = parse_markdown_file(SAMPLE_FILES["ryosuke"])
        result = evaluate_income(data)
        assert result.emphasize is False, f"りょうすけさんは強調OFFであるべき（理由: {result.emphasis_reason}）"
        # 代替の強みが検出されるべき
        assert len(result.alternative_strengths) > 0, "代替の強みが検出されるべき"

    def test_yurika_emphasize_off_with_alternatives(self):
        """ゆりかさん: 年収450-500万、週4勤務 → 強調OFF + 勤務形態が強み"""
        if not SAMPLE_FILES["yurika"].exists():
            return
        data = parse_markdown_file(SAMPLE_FILES["yurika"])
        result = evaluate_income(data)
        assert result.emphasize is False
        # 週4勤務 or 勤務形態の自由度が代替の強みに含まれるべき
        categories = [s.category for s in result.alternative_strengths]
        assert any("勤務形態" in c or "副業" in c for c in categories), \
            f"ゆりかさんには勤務形態 or 副業の強みが検出されるべき（実際: {categories}）"


class TestAgeExtraction:
    """年齢帯抽出のテスト"""

    def test_explicit_age(self):
        assert _extract_age_bracket("28歳") == "20代後半"

    def test_bracket_format(self):
        assert _extract_age_bracket("30代中盤") == "30代中盤"

    def test_halba(self):
        assert _extract_age_bracket("30代半ば") == "30代中盤"

    def test_twenties(self):
        assert _extract_age_bracket("20代") == "20代中盤"

    def test_forties(self):
        assert _extract_age_bracket("40代前半") == "40代"
