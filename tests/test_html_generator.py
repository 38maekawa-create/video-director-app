"""html_generator のユニットテスト"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.integrations.ai_dev5_connector import parse_markdown_file
from src.video_direction.analyzer.guest_classifier import classify_guest
from src.video_direction.analyzer.income_evaluator import evaluate_income
from src.video_direction.analyzer.proper_noun_filter import detect_proper_nouns
from src.video_direction.analyzer.target_labeler import label_targets
from src.video_direction.analyzer.direction_generator import generate_directions
from src.video_direction.reporter.html_generator import generate_direction_html, generate_index_html


SAMPLE_FILE = Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_Izuさん：30代中盤元アクセンチュア年収1000万円台.md"


class TestHtmlGeneration:
    """HTML生成のテスト"""

    def test_generates_valid_html(self):
        """有効なHTMLが生成される"""
        if not SAMPLE_FILE.exists():
            return
        data = parse_markdown_file(SAMPLE_FILE)
        classification = classify_guest(data)
        income_eval = evaluate_income(data)
        proper_nouns = detect_proper_nouns(data)
        target_result = label_targets(data)
        direction_timeline = generate_directions(data, classification, income_eval)

        html = generate_direction_html(
            data, classification, income_eval, proper_nouns, target_result, direction_timeline
        )

        assert "<!DOCTYPE html>" in html
        assert "<title>" in html
        assert "ディレクションレポート" in html
        assert "guest-classification" in html
        assert "income-direction" in html
        assert "proper-nouns" in html
        assert "direction-timeline" in html
        assert "target-checklist" in html

    def test_contains_guest_info(self):
        """ゲスト情報が含まれる"""
        if not SAMPLE_FILE.exists():
            return
        data = parse_markdown_file(SAMPLE_FILE)
        classification = classify_guest(data)
        income_eval = evaluate_income(data)
        proper_nouns = detect_proper_nouns(data)
        target_result = label_targets(data)
        direction_timeline = generate_directions(data, classification, income_eval)

        html = generate_direction_html(
            data, classification, income_eval, proper_nouns, target_result, direction_timeline
        )

        assert "Izu" in html
        assert "層a" in html or "tier-a" in html

    def test_index_html_generation(self):
        """index.htmlが正しく生成される"""
        pages = [
            {"filename": "20251123_Izu_direction.html", "title": "ディレクション: Izu", "date": "2025/11/23", "tier": "a"},
            {"filename": "20251123_ryosuke_direction.html", "title": "ディレクション: りょうすけ", "date": "2025/11/23", "tier": "b"},
        ]
        html = generate_index_html(pages)
        assert "<!DOCTYPE html>" in html
        assert "ディレクションレポート" in html
        assert "全2件" in html
        assert "Izu" in html
