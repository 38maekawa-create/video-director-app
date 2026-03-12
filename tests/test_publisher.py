"""publisher のユニットテスト"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.reporter.publisher import _extract_existing_tier_map, _safe_filename


def test_safe_filename_keeps_japanese_and_sanitizes():
    name = "Izuさん / 特別回 #1"
    result = _safe_filename(name)
    assert result == "Izuさん_特別回_1"


def test_extract_existing_tier_map(tmp_path: Path):
    html = """<!DOCTYPE html>
<html>
<body>
<div class="item">
<a href="20251123_Izu_direction.html">ディレクション: Izu</a>
<span class="tier tier-a">層a</span>
</div>
<div class="item">
<a href="20251123_ryosuke_direction.html">ディレクション: りょうすけ</a>
<span class="tier tier-b">層b</span>
</div>
</body>
</html>"""
    index = tmp_path / "index.html"
    index.write_text(html, encoding="utf-8")

    tiers = _extract_existing_tier_map(index)
    assert tiers["20251123_Izu_direction.html"] == "a"
    assert tiers["20251123_ryosuke_direction.html"] == "b"
