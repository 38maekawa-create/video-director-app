"""direction_generator のユニットテスト"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.integrations.ai_dev5_connector import parse_markdown_file
from src.video_direction.analyzer.guest_classifier import classify_guest
from src.video_direction.analyzer.income_evaluator import evaluate_income
from src.video_direction.analyzer.direction_generator import generate_directions


SAMPLE_FILES = {
    "izu": Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_Izuさん：30代中盤元アクセンチュア年収1000万円台.md",
    "ryosuke": Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_りょうすけさん：20代後半内資IT勤務年収600万.md",
}


class TestDirectionGeneration:
    """演出ディレクション生成のテスト"""

    def test_izu_has_directions(self):
        """Izuさんの動画に演出指示が生成される"""
        if not SAMPLE_FILES["izu"].exists():
            return
        data = parse_markdown_file(SAMPLE_FILES["izu"])
        classification = classify_guest(data)
        income_eval = evaluate_income(data)
        timeline = generate_directions(data, classification, income_eval)
        assert len(timeline.entries) > 0, "演出指示が1つ以上生成されるべき"

    def test_direction_types(self):
        """演出指示に複数タイプが含まれる"""
        if not SAMPLE_FILES["izu"].exists():
            return
        data = parse_markdown_file(SAMPLE_FILES["izu"])
        classification = classify_guest(data)
        income_eval = evaluate_income(data)
        timeline = generate_directions(data, classification, income_eval)
        types = set(e.direction_type for e in timeline.entries)
        assert len(types) >= 2, f"複数の演出タイプが含まれるべき（実際: {types}）"

    def test_timestamps_sorted(self):
        """演出指示がタイムスタンプ順にソートされている"""
        for key, filepath in SAMPLE_FILES.items():
            if not filepath.exists():
                continue
            data = parse_markdown_file(filepath)
            classification = classify_guest(data)
            income_eval = evaluate_income(data)
            timeline = generate_directions(data, classification, income_eval)
            timestamps = [e.timestamp for e in timeline.entries]
            for i in range(len(timestamps) - 1):
                ts1 = _ts_to_sec(timestamps[i])
                ts2 = _ts_to_sec(timestamps[i + 1])
                assert ts1 <= ts2, f"タイムスタンプが昇順でない: {timestamps[i]} > {timestamps[i+1]}"

    def test_all_entries_have_instruction(self):
        """全エントリに演出指示がある"""
        for key, filepath in SAMPLE_FILES.items():
            if not filepath.exists():
                continue
            data = parse_markdown_file(filepath)
            classification = classify_guest(data)
            income_eval = evaluate_income(data)
            timeline = generate_directions(data, classification, income_eval)
            for entry in timeline.entries:
                assert entry.instruction != "", "全エントリに演出指示が必要"
                assert entry.priority in ("high", "medium", "low")


def _ts_to_sec(ts: str) -> int:
    parts = ts.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0
