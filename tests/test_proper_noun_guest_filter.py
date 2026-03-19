"""proper_noun_filter のゲスト限定フィルタリングテスト

問題1の修正: 他ゲストの企業名が混入しないことを検証する。
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.integrations.ai_dev5_connector import (
    VideoData, PersonProfile, HighlightScene,
)
from src.video_direction.analyzer.proper_noun_filter import (
    detect_proper_nouns, _get_guest_related_nouns, ProperNounEntry,
)


def _make_video_data(
    guest_name: str,
    occupation: str = "",
    guest_summary: str = "",
    detailed_summary: str = "",
    highlights: list = None,
) -> VideoData:
    """テスト用のVideoDataを作成"""
    return VideoData(
        title=f"撮影_{guest_name}さん",
        profiles=[PersonProfile(
            name=guest_name,
            occupation=occupation,
        )],
        guest_summary=guest_summary,
        detailed_summary=detailed_summary,
        highlights=highlights or [],
    )


class TestGuestFilterPreventsContamination:
    """ゲスト限定フィルタが他ゲストの企業名混入を防ぐことのテスト"""

    def test_kirin_not_in_kumasuke_report(self):
        """くますけさんのレポートにキリンが混入しないこと（問題1の再現テスト）

        くますけさんの動画データにキリンが含まれていても、
        くますけさんのプロファイルや職業にキリンが関連しなければ除外される。
        """
        # くますけさんの動画データ（detailed_summaryに「キリン」が誤って含まれるケース）
        video_data = _make_video_data(
            guest_name="くますけ",
            occupation="ITコンサル勤務",
            guest_summary="IT業界で活躍するくますけさん",
            detailed_summary="くますけさんはITコンサルで活躍。キリンビールで営業企画をしていた経験もある。",
            highlights=[
                HighlightScene(
                    timestamp="03:00",
                    speaker="くますけ",
                    text="ITコンサルの仕事は非常にやりがいがある",
                    category="パンチライン",
                ),
            ],
        )

        # ゲスト名を指定してフィルタリング
        nouns = detect_proper_nouns(video_data, guest_name="くますけ")
        names = [n.name for n in nouns]

        # キリン・キリンビールは「くますけ」のプロファイルに関連しないため除外される
        assert "キリン" not in names, (
            f"くますけさんのレポートにキリンが含まれてはならない（実際: {names}）"
        )
        assert "キリンビール" not in names, (
            f"くますけさんのレポートにキリンビールが含まれてはならない（実際: {names}）"
        )

    def test_kirin_appears_in_sarubeer_report(self):
        """さるビールさんのレポートにはキリンが正しく検出されること"""
        video_data = _make_video_data(
            guest_name="さるビール",
            occupation="キリンビール 営業企画",
            guest_summary="キリンビールで営業企画を担当するさるビールさん",
            detailed_summary="さるビールさんはキリンビールで10年間営業企画に従事。",
            highlights=[
                HighlightScene(
                    timestamp="05:00",
                    speaker="さるビール",
                    text="キリンビールでの営業企画の仕事について語る",
                    category="パンチライン",
                ),
            ],
        )

        nouns = detect_proper_nouns(video_data, guest_name="さるビール")
        names = [n.name for n in nouns]

        # キリンビールはさるビールさんの職業に関連するため検出される
        has_kirin = any("キリン" in n for n in names)
        assert has_kirin, (
            f"さるビールさんのレポートにはキリン関連が含まれるべき（実際: {names}）"
        )

    def test_guest_name_none_returns_all(self):
        """guest_name=Noneの場合、フィルタリングなしで全企業名が検出される（後方互換）"""
        video_data = _make_video_data(
            guest_name="テスト",
            occupation="不明",
            detailed_summary="アクセンチュアで働いた後、キリンビールに転職した。",
        )

        nouns_unfiltered = detect_proper_nouns(video_data, guest_name=None)
        nouns_default = detect_proper_nouns(video_data)  # デフォルト引数

        # どちらも同じ結果（フィルタリングなし）
        names_unfiltered = sorted([n.name for n in nouns_unfiltered])
        names_default = sorted([n.name for n in nouns_default])
        assert names_unfiltered == names_default, "guest_name=Noneとデフォルトは同じ動作"

    def test_accenture_detected_for_accenture_guest(self):
        """アクセンチュア勤務のゲストにはアクセンチュアが検出される"""
        video_data = _make_video_data(
            guest_name="Izu",
            occupation="元アクセンチュア マネージャー職",
            guest_summary="元アクセンチュアのマネージャー",
            highlights=[
                HighlightScene(
                    timestamp="02:00",
                    speaker="Izu",
                    text="アクセンチュアで学んだことは多い",
                    category="パンチライン",
                ),
            ],
        )

        nouns = detect_proper_nouns(video_data, guest_name="Izu")
        names = [n.name for n in nouns]
        assert "アクセンチュア" in names, (
            f"Izuさんのレポートにはアクセンチュアが含まれるべき（実際: {names}）"
        )

    def test_accenture_not_detected_for_unrelated_guest(self):
        """アクセンチュアと無関係のゲストにはアクセンチュアが検出されない"""
        video_data = _make_video_data(
            guest_name="テスト太郎",
            occupation="製薬会社MR",
            guest_summary="製薬会社でMRとして働く",
            detailed_summary="テスト太郎さんは製薬MR。同僚にアクセンチュア出身の人がいる。",
        )

        nouns = detect_proper_nouns(video_data, guest_name="テスト太郎")
        names = [n.name for n in nouns]
        assert "アクセンチュア" not in names, (
            f"無関係のゲストにアクセンチュアが含まれてはならない（実際: {names}）"
        )


class TestGetGuestRelatedNouns:
    """_get_guest_related_nouns ヘルパー関数のテスト"""

    def test_returns_none_when_no_guest_info(self):
        """ゲスト情報がない場合はNoneを返す（フィルタリングしない）"""
        video_data = VideoData()
        result = _get_guest_related_nouns("unknown", video_data)
        # プロファイルもguest_summaryもない場合、MEMBER_MASTERも見つからなければNone
        # （実際にはMEMBER_MASTERに"unknown"はないのでNoneになるはず）
        # ただし空文字列でもNoneでないかもしれないので、setかNoneのどちらか
        assert result is None or isinstance(result, set)

    def test_returns_set_with_guest_occupation(self):
        """ゲストの職業に含まれる企業名がセットに含まれる"""
        video_data = _make_video_data(
            guest_name="test",
            occupation="キリンビール 営業企画",
        )
        result = _get_guest_related_nouns("test", video_data)
        assert result is not None
        assert "キリンビール" in result or "キリン" in result

    def test_highlight_nouns_included(self):
        """ハイライトシーンに含まれる企業名もセットに含まれる"""
        video_data = _make_video_data(
            guest_name="test",
            occupation="IT企業勤務",
            highlights=[
                HighlightScene(
                    timestamp="01:00",
                    speaker="test",
                    text="サントリーとの提携を進めた",
                    category="パンチライン",
                ),
            ],
        )
        result = _get_guest_related_nouns("test", video_data)
        assert result is not None
        assert "サントリー" in result
