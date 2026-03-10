"""proper_noun_filter のユニットテスト"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.integrations.ai_dev5_connector import parse_markdown_file
from src.video_direction.analyzer.proper_noun_filter import detect_proper_nouns


SAMPLE_FILES = {
    "izu": Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_Izuさん：30代中盤元アクセンチュア年収1000万円台.md",
    "ryosuke": Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_りょうすけさん：20代後半内資IT勤務年収600万.md",
}


class TestDetectProperNouns:
    """固有名詞検出のテスト"""

    def test_izu_has_accenture(self):
        """Izuさんのファイルからアクセンチュアが検出される"""
        if not SAMPLE_FILES["izu"].exists():
            return
        data = parse_markdown_file(SAMPLE_FILES["izu"])
        nouns = detect_proper_nouns(data)
        names = [n.name for n in nouns]
        assert "アクセンチュア" in names, f"アクセンチュアが検出されるべき（実際: {names}）"

    def test_ryosuke_has_company(self):
        """りょうすけさんのファイルから凸版が検出される"""
        if not SAMPLE_FILES["ryosuke"].exists():
            return
        data = parse_markdown_file(SAMPLE_FILES["ryosuke"])
        nouns = detect_proper_nouns(data)
        names = [n.name for n in nouns]
        # 凸版 or 凸版ホールディングス が検出されるべき
        has_toppan = any("凸版" in n for n in names)
        assert has_toppan, f"凸版関連の固有名詞が検出されるべき（実際: {names}）"

    def test_hidden_noun_has_telop(self):
        """伏せると判定された固有名詞にテロップ提案がある"""
        if not SAMPLE_FILES["izu"].exists():
            return
        data = parse_markdown_file(SAMPLE_FILES["izu"])
        nouns = detect_proper_nouns(data)
        for noun in nouns:
            if noun.action == "hide":
                assert noun.telop_template != "", f"伏せる固有名詞にはテロップ提案が必要: {noun.name}"

    def test_no_teko_in_results(self):
        """TEKOは固有名詞リストに含まれない（判定不要のため）"""
        for key, filepath in SAMPLE_FILES.items():
            if not filepath.exists():
                continue
            data = parse_markdown_file(filepath)
            nouns = detect_proper_nouns(data)
            names = [n.name for n in nouns]
            assert "TEKO" not in names, "TEKOは判定対象外"
