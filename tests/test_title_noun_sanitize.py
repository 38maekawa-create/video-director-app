"""title_generator / description_writer の固有名詞伏せ字テスト

問題2の修正: 「伏せる」と判定された企業名がタイトル・概要欄に
丸出しにならないことを検証する。
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.integrations.ai_dev5_connector import (
    VideoData, PersonProfile, HighlightScene,
)
from src.video_direction.analyzer.proper_noun_filter import ProperNounEntry
from src.video_direction.analyzer.title_generator import (
    TitleCandidate, TitleProposals,
    _get_hidden_noun_names, _sanitize_title_candidates, _fallback_titles,
)
from src.video_direction.analyzer.guest_classifier import ClassificationResult
from src.video_direction.analyzer.income_evaluator import IncomeEvaluation


def _make_hidden_noun(name: str, category: str = "企業名") -> ProperNounEntry:
    """伏せ判定の固有名詞エントリを作成"""
    return ProperNounEntry(
        name=name,
        category=category,
        action="hide",
        reason="テスト用: 伏せ判定",
        telop_template="業界大手企業",
        occurrences=[],
    )


def _make_shown_noun(name: str) -> ProperNounEntry:
    """表示判定の固有名詞エントリを作成"""
    return ProperNounEntry(
        name=name,
        category="企業名",
        action="show",
        reason="テスト用: 表示判定",
        telop_template="",
        occurrences=["01:00"],
    )


class TestGetHiddenNounNames:
    """_get_hidden_noun_names のテスト"""

    def test_empty_list(self):
        assert _get_hidden_noun_names(None) == []
        assert _get_hidden_noun_names([]) == []

    def test_extracts_hidden_only(self):
        nouns = [
            _make_hidden_noun("キリン"),
            _make_shown_noun("アクセンチュア"),
            _make_hidden_noun("サントリー"),
        ]
        result = _get_hidden_noun_names(nouns)
        assert result == ["キリン", "サントリー"]

    def test_all_shown(self):
        nouns = [_make_shown_noun("アクセンチュア")]
        assert _get_hidden_noun_names(nouns) == []


class TestSanitizeTitleCandidates:
    """_sanitize_title_candidates のテスト"""

    def test_replaces_hidden_noun_in_title(self):
        """伏せ対象の企業名がタイトルから置換されること（問題2の再現テスト）"""
        proposals = TitleProposals(
            candidates=[
                TitleCandidate(
                    title="年収1000万30代キリン営業企画のさるビールさんが語るキャリア戦略とは",
                    target_segment="30代ハイキャリア",
                    appeal_type="数字系",
                    rationale="テスト",
                ),
            ],
        )
        hidden_nouns = ["キリン"]
        result = _sanitize_title_candidates(proposals, hidden_nouns)

        assert "キリン" not in result.candidates[0].title, (
            f"伏せ対象のキリンがタイトルに残っている: {result.candidates[0].title}"
        )
        # 「大手飲料メーカー」等に置換されていること
        assert "大手" in result.candidates[0].title or "飲料" in result.candidates[0].title

    def test_replaces_kirin_beer_in_title(self):
        """キリンビールも正しく置換されること"""
        proposals = TitleProposals(
            candidates=[
                TitleCandidate(
                    title="キリンビール営業企画のさるビールさん",
                ),
            ],
        )
        result = _sanitize_title_candidates(proposals, ["キリンビール"])
        assert "キリンビール" not in result.candidates[0].title

    def test_no_replacement_when_no_hidden_nouns(self):
        """伏せ対象がない場合はタイトルが変更されないこと"""
        original_title = "年収1000万30代ITコンサルのテストさん"
        proposals = TitleProposals(
            candidates=[TitleCandidate(title=original_title)],
        )
        result = _sanitize_title_candidates(proposals, [])
        assert result.candidates[0].title == original_title

    def test_multiple_hidden_nouns(self):
        """複数の伏せ対象がすべて置換されること"""
        proposals = TitleProposals(
            candidates=[
                TitleCandidate(
                    title="元キリン→サントリーに転職したテストさん",
                ),
            ],
        )
        result = _sanitize_title_candidates(proposals, ["キリン", "サントリー"])
        assert "キリン" not in result.candidates[0].title
        assert "サントリー" not in result.candidates[0].title


class TestFallbackTitlesWithProperNouns:
    """_fallback_titles が proper_nouns を受け取って伏せ字を適用するテスト"""

    def test_fallback_sanitizes_hidden_nouns(self):
        """フォールバックタイトルでも伏せ対象が除去されること"""
        video_data = VideoData(
            title="撮影_さるビールさん",
            profiles=[PersonProfile(
                name="さるビール",
                age="30代",
                occupation="キリンビール営業企画",
                income="800万",
            )],
            highlights=[
                HighlightScene(
                    timestamp="05:00",
                    speaker="さるビール",
                    text="キリンビールでの営業企画で学んだこと",
                    category="パンチライン",
                ),
            ],
        )
        classification = ClassificationResult(
            tier="b",
            tier_label="tier b: 相対的な強さの言語化が必要",
            reason="テスト",
            presentation_template="テスト",
            confidence="high",
        )
        income_eval = IncomeEvaluation(
            income_value="800万",
            age_bracket="30代",
            threshold=1000,
            emphasize=True,
            emphasis_reason="テスト",
            telop_suggestion="年収800万",
        )

        proper_nouns = [_make_hidden_noun("キリンビール")]
        result = _fallback_titles(video_data, classification, income_eval, proper_nouns=proper_nouns)

        for candidate in result.candidates:
            assert "キリンビール" not in candidate.title, (
                f"フォールバックタイトルに伏せ対象が残っている: {candidate.title}"
            )


class TestDescriptionWriterSanitize:
    """description_writer の固有名詞サニタイズテスト"""

    def test_sanitize_description_replaces_hidden_nouns(self):
        from src.video_direction.analyzer.description_writer import (
            VideoDescription, _sanitize_description,
        )
        from src.video_direction.analyzer.proper_noun_filter import INDUSTRY_CATEGORIES

        desc = VideoDescription(
            full_text="キリンビールで営業企画をしていたさるビールさん",
            hook="キリンビール出身のさるビールさん",
            summary="キリンビールでの経験を語る",
            hashtags="#キリンビール #営業企画",
        )
        hidden_nouns = ["キリンビール"]
        result = _sanitize_description(desc, hidden_nouns)

        assert "キリンビール" not in result.full_text, (
            f"full_textに伏せ対象が残っている: {result.full_text}"
        )
        assert "キリンビール" not in result.hook, (
            f"hookに伏せ対象が残っている: {result.hook}"
        )
        assert "キリンビール" not in result.summary, (
            f"summaryに伏せ対象が残っている: {result.summary}"
        )
        assert "キリンビール" not in result.hashtags, (
            f"hashtagsに伏せ対象が残っている: {result.hashtags}"
        )

    def test_sanitize_description_no_change_when_no_hidden(self):
        from src.video_direction.analyzer.description_writer import (
            VideoDescription, _sanitize_description,
        )

        original_text = "ITコンサルで活躍するテストさん"
        desc = VideoDescription(full_text=original_text)
        result = _sanitize_description(desc, [])
        assert result.full_text == original_text

    def test_hashtag_with_partial_match_removed(self):
        """「キリン」が伏せ対象の時、#キリンビール もハッシュタグごと除去される"""
        from src.video_direction.analyzer.description_writer import (
            VideoDescription, _sanitize_description,
        )

        desc = VideoDescription(
            full_text="大手飲料メーカーで営業",
            hashtags="#キリンビール　#営業企画　#副業　#年収700万",
        )
        result = _sanitize_description(desc, ["キリン"])

        assert "#キリンビール" not in result.hashtags, (
            f"部分一致するハッシュタグが除去されていない: {result.hashtags}"
        )
        assert "#営業企画" in result.hashtags
        assert "#副業" in result.hashtags
        assert "#年収700万" in result.hashtags

    def test_hashtag_no_removal_when_no_match(self):
        """伏せ対象でない企業名のハッシュタグは残る"""
        from src.video_direction.analyzer.description_writer import (
            VideoDescription, _sanitize_description,
        )

        desc = VideoDescription(
            hashtags="#アクセンチュア　#コンサル　#年収1500万",
        )
        result = _sanitize_description(desc, ["キリン"])

        assert "#アクセンチュア" in result.hashtags
        assert "#コンサル" in result.hashtags
        assert "#年収1500万" in result.hashtags
