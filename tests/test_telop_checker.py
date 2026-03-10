"""C-2: テロップ自動チェックのテスト"""
import pytest
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from video_direction.analyzer.telop_checker import (
    check_telops,
    TelopCheckResult,
    TelopCandidate,
    TelopIssue,
    _create_telop_candidate_from_highlight,
    _check_single_telop,
    _check_consistency,
    _check_brackets,
    _extract_number_telop,
    _extract_punchline_telop,
    _truncate_for_telop,
    _calculate_consistency_score,
)
from video_direction.integrations.ai_dev5_connector import VideoData, HighlightScene


# === テストデータ ===

def _make_video_data(highlights=None, duration="30分"):
    """テスト用VideoDataを生成"""
    return VideoData(
        title="テスト動画",
        duration=duration,
        speakers="ホスト, ゲスト",
        highlights=highlights or [],
        main_topics=["トピック1"],
    )


def _make_highlight(ts="05:00", speaker="ゲスト", text="テスト発言", category="パンチライン"):
    """テスト用HighlightSceneを生成"""
    return HighlightScene(
        timestamp=ts,
        speaker=speaker,
        text=text,
        category=category,
    )


# === check_telops 基本テスト ===

class TestCheckTelops:
    """メインのcheck_telops関数テスト"""

    def test_空のハイライトで空の結果(self):
        video = _make_video_data(highlights=[])
        result = check_telops(video)
        assert isinstance(result, TelopCheckResult)
        assert result.total_telops == 0
        assert result.is_estimated is True
        assert result.consistency_score == 100.0

    def test_正常なハイライトでテロップ候補生成(self):
        highlights = [
            _make_highlight(ts="02:30", text="年収1000万", category="実績数字"),
            _make_highlight(ts="05:00", text="挑戦が大事", category="パンチライン"),
            _make_highlight(ts="10:00", text="30代エンジニア", category="属性紹介"),
        ]
        video = _make_video_data(highlights=highlights)
        result = check_telops(video)
        assert result.total_telops == 3
        assert len(result.candidates) == 3

    def test_問題ないテロップはエラーゼロ(self):
        highlights = [
            _make_highlight(text="年収1200万", category="実績数字"),
        ]
        video = _make_video_data(highlights=highlights)
        result = check_telops(video)
        assert result.error_count == 0

    def test_推定フラグがTrue(self):
        video = _make_video_data()
        result = check_telops(video)
        assert result.is_estimated is True


# === テロップ候補生成テスト ===

class TestTelopCandidateCreation:
    """テロップ候補生成のテスト"""

    def test_実績数字カテゴリは数字強調になる(self):
        hl = _make_highlight(text="年収1500万稼いでいます", category="実績数字")
        candidate = _create_telop_candidate_from_highlight(hl)
        assert candidate.category == "数字強調"

    def test_パンチラインカテゴリはキー発言強調になる(self):
        hl = _make_highlight(text="「人生変わった」", category="パンチライン")
        candidate = _create_telop_candidate_from_highlight(hl)
        assert candidate.category == "キー発言強調"
        assert "人生変わった" in candidate.text

    def test_属性紹介カテゴリ(self):
        hl = _make_highlight(text="30代・外資系コンサル", category="属性紹介")
        candidate = _create_telop_candidate_from_highlight(hl)
        assert candidate.category == "属性テロップ"

    def test_その他カテゴリは一般テロップ(self):
        hl = _make_highlight(text="TEKOのコミュニティが最高", category="TEKO価値")
        candidate = _create_telop_candidate_from_highlight(hl)
        assert candidate.category == "一般テロップ"

    def test_文字数が正しく計算される(self):
        hl = _make_highlight(text="テスト", category="パンチライン")
        candidate = _create_telop_candidate_from_highlight(hl)
        assert candidate.char_count == 3


# === 単一テロップチェックテスト ===

class TestSingleTelopCheck:
    """単一テロップの品質チェックテスト"""

    def test_適切な長さのテロップは警告なし(self):
        candidate = TelopCandidate(
            timestamp="05:00",
            text="年収1200万",
            category="数字強調",
            char_count=7,
        )
        issues = _check_single_telop(candidate)
        length_issues = [i for i in issues if i.issue_type == "length"]
        assert len(length_issues) == 0

    def test_長すぎるテロップはwarning(self):
        long_text = "これはとても長いテロップテキストで読みにくくなる可能性があります"
        candidate = TelopCandidate(
            timestamp="05:00",
            text=long_text,
            category="一般テロップ",
            char_count=len(long_text),
        )
        issues = _check_single_telop(candidate)
        length_issues = [i for i in issues if i.issue_type == "length"]
        assert len(length_issues) > 0
        assert length_issues[0].severity == "warning"

    def test_冗長表現の検出(self):
        candidate = TelopCandidate(
            timestamp="05:00",
            text="成功ということで",
            category="一般テロップ",
            char_count=8,
        )
        issues = _check_single_telop(candidate)
        readability_issues = [i for i in issues if i.issue_type == "readability"]
        assert len(readability_issues) > 0

    def test_括弧不一致の検出(self):
        candidate = TelopCandidate(
            timestamp="05:00",
            text="「年収1000万",
            category="数字強調",
            char_count=8,
        )
        issues = _check_brackets(candidate)
        assert len(issues) > 0
        assert issues[0].severity == "error"
        assert issues[0].issue_type == "typo"

    def test_括弧が正しく対応していれば問題なし(self):
        candidate = TelopCandidate(
            timestamp="05:00",
            text="「年収1000万」",
            category="数字強調",
            char_count=9,
        )
        issues = _check_brackets(candidate)
        assert len(issues) == 0


# === 一貫性チェックテスト ===

class TestConsistencyCheck:
    """テロップ間の一貫性チェックテスト"""

    def test_単一テロップでは一貫性問題なし(self):
        candidates = [
            TelopCandidate(timestamp="05:00", text="年収1000万", category="数字強調", char_count=7),
        ]
        issues = _check_consistency(candidates)
        assert len(issues) == 0

    def test_数字表記の不統一を検出(self):
        candidates = [
            TelopCandidate(timestamp="05:00", text="年収1000万", category="数字強調", char_count=7),
            TelopCandidate(timestamp="10:00", text="15000000円", category="数字強調", char_count=11),
        ]
        issues = _check_consistency(candidates)
        consistency_issues = [i for i in issues if i.issue_type == "consistency"]
        assert any("統一" in i.description for i in consistency_issues)


# === テキスト抽出テスト ===

class TestTextExtraction:
    """テロップ用テキスト抽出のテスト"""

    def test_年収パターンの抽出(self):
        result = _extract_number_telop("年収1500万稼いでいます")
        assert "年収" in result
        assert "1500万" in result

    def test_パンチライン引用の抽出(self):
        result = _extract_punchline_telop("彼は「人生が変わった」と言いました")
        assert result == "人生が変わった"

    def test_引用なしのパンチライン(self):
        result = _extract_punchline_telop("挑戦が大事")
        assert result == "挑戦が大事"

    def test_テロップ短縮(self):
        result = _truncate_for_telop("これはとても長いテロップテキストです", max_chars=10)
        assert len(result) <= 10

    def test_短いテキストはそのまま(self):
        result = _truncate_for_telop("短い", max_chars=10)
        assert result == "短い"


# === 一貫性スコアテスト ===

class TestConsistencyScore:
    """一貫性スコア計算のテスト"""

    def test_問題なしで100点(self):
        score = _calculate_consistency_score(
            [TelopCandidate(timestamp="05:00", text="テスト", category="一般", char_count=3)],
            [],
        )
        assert score == 100.0

    def test_エラーで減点(self):
        issues = [
            TelopIssue(timestamp="05:00", issue_type="typo", severity="error", description="テスト"),
        ]
        score = _calculate_consistency_score(
            [TelopCandidate(timestamp="05:00", text="テスト", category="一般", char_count=3)],
            issues,
        )
        assert score == 85.0

    def test_警告で減点(self):
        issues = [
            TelopIssue(timestamp="05:00", issue_type="length", severity="warning", description="テスト"),
        ]
        score = _calculate_consistency_score(
            [TelopCandidate(timestamp="05:00", text="テスト", category="一般", char_count=3)],
            issues,
        )
        assert score == 95.0

    def test_スコアは0以下にならない(self):
        issues = [
            TelopIssue(timestamp="05:00", issue_type="typo", severity="error", description="テスト")
            for _ in range(10)
        ]
        score = _calculate_consistency_score(
            [TelopCandidate(timestamp="05:00", text="テスト", category="一般", char_count=3)],
            issues,
        )
        assert score == 0.0

    def test_空のテロップ候補で100点(self):
        score = _calculate_consistency_score([], [])
        assert score == 100.0
