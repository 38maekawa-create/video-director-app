"""guest_classifier のユニットテスト"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.integrations.ai_dev5_connector import parse_markdown_file, VideoData, PersonProfile
from src.video_direction.analyzer.guest_classifier import classify_guest, _extract_income


SAMPLE_FILES = {
    "izu": Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_Izuさん：30代中盤元アクセンチュア年収1000万円台.md",
    "ryosuke": Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_りょうすけさん：20代後半内資IT勤務年収600万.md",
    "yurika": Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.28_ゆりかさん.md",
    "mintia": Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251130撮影_みんてぃあさん：40代前半AWS管理職年収2200万.md",
    "komo": Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_こもさん：30代後半年収650万.md",
}


class TestClassifyGuest:
    """ゲスト分類のテスト — ディレクションマニュアルの分類と一致するか検証"""

    def test_izu_tier_a(self):
        """Izuさん → 層a（元アクセンチュアマネージャー、年収1500万→3000万）"""
        if not SAMPLE_FILES["izu"].exists():
            return
        data = parse_markdown_file(SAMPLE_FILES["izu"])
        result = classify_guest(data)
        assert result.tier == "a", f"Izuさんは層aであるべき（実際: {result.tier}, 理由: {result.reason}）"

    def test_ryosuke_tier_b(self):
        """りょうすけさん → 層b（20代後半、年収600万）"""
        if not SAMPLE_FILES["ryosuke"].exists():
            return
        data = parse_markdown_file(SAMPLE_FILES["ryosuke"])
        result = classify_guest(data)
        assert result.tier == "b", f"りょうすけさんは層bであるべき（実際: {result.tier}, 理由: {result.reason}）"

    def test_mintia_tier_a(self):
        """みんてぃあさん → 層a（GAFA管理職、年収2200万）"""
        if not SAMPLE_FILES["mintia"].exists():
            return
        data = parse_markdown_file(SAMPLE_FILES["mintia"])
        result = classify_guest(data)
        assert result.tier == "a", f"みんてぃあさんは層aであるべき（実際: {result.tier}, 理由: {result.reason}）"

    def test_komo_tier_b(self):
        """こもさん → 層b（30代後半、年収650万）"""
        if not SAMPLE_FILES["komo"].exists():
            return
        data = parse_markdown_file(SAMPLE_FILES["komo"])
        result = classify_guest(data)
        assert result.tier == "b", f"こもさんは層bであるべき（実際: {result.tier}, 理由: {result.reason}）"

    def test_yurika_tier_b(self):
        """ゆりかさん → 層b（年収450-500万、週4勤務の強み）"""
        if not SAMPLE_FILES["yurika"].exists():
            return
        data = parse_markdown_file(SAMPLE_FILES["yurika"])
        result = classify_guest(data)
        assert result.tier == "b", f"ゆりかさんは層bであるべき（実際: {result.tier}, 理由: {result.reason}）"


class TestExtractIncome:
    """年収抽出のテスト"""

    def test_simple_income(self):
        assert _extract_income("年収600万円", "") == 600

    def test_income_with_prefix(self):
        assert _extract_income("年収約900万円", "") == 900

    def test_annual_profit(self):
        assert _extract_income("年間利益3000万円", "") == 3000

    def test_multiple_incomes(self):
        """複数年収がある場合は最大値を返す"""
        result = _extract_income("年収1500万円。独立後現在：年間利益3000万円", "")
        assert result == 3000

    def test_no_income(self):
        assert _extract_income("不明", "") is None
