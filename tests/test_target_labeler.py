"""target_labeler のユニットテスト"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.integrations.ai_dev5_connector import parse_markdown_file
from src.video_direction.analyzer.target_labeler import label_targets


SAMPLE_FILES = {
    "izu": Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_Izuさん：30代中盤元アクセンチュア年収1000万円台.md",
    "ryosuke": Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_りょうすけさん：20代後半内資IT勤務年収600万.md",
    "yurika": Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.28_ゆりかさん.md",
}


class TestTargetLabeling:
    """ターゲットラベリングのテスト"""

    def test_izu_has_tier1(self):
        """Izuさん（層a）は1層向けシーンが多い"""
        if not SAMPLE_FILES["izu"].exists():
            return
        data = parse_markdown_file(SAMPLE_FILES["izu"])
        result = label_targets(data)
        assert len(result.scenes) > 0
        tier1_count = result.balance.tier1_count + result.balance.both_count
        assert tier1_count > 0, "Izuさんには1層向けシーンがあるべき"

    def test_yurika_has_tier2(self):
        """ゆりかさんは2層向けシーンが含まれる"""
        if not SAMPLE_FILES["yurika"].exists():
            return
        data = parse_markdown_file(SAMPLE_FILES["yurika"])
        result = label_targets(data)
        assert len(result.scenes) > 0
        tier2_count = result.balance.tier2_count + result.balance.both_count
        assert tier2_count > 0, "ゆりかさんには2層向けシーンがあるべき"

    def test_balance_check(self):
        """バランスチェックが正しく動作する"""
        for key, filepath in SAMPLE_FILES.items():
            if not filepath.exists():
                continue
            data = parse_markdown_file(filepath)
            result = label_targets(data)
            b = result.balance
            assert b.total == len(result.scenes)
            assert b.tier1_count + b.tier2_count + b.both_count == b.total
            assert b.balance_assessment in ("良好", "1層偏重", "2層偏重")

    def test_scene_labels_valid(self):
        """各シーンのラベルが有効な値"""
        for key, filepath in SAMPLE_FILES.items():
            if not filepath.exists():
                continue
            data = parse_markdown_file(filepath)
            result = label_targets(data)
            for scene in result.scenes:
                assert scene.target_tier in ("tier1", "tier2", "both")
                assert scene.tier_label in ("1層向け", "2層向け", "両層向け")
                assert scene.timestamp != ""
