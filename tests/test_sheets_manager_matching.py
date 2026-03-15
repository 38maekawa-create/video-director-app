"""スプシ名寄せマッチング精度テスト"""

from src.video_direction.integrations.sheets_manager import (
    _normalize_name,
    _extract_names_from_title,
    _match_guest_name,
    _romaji_to_hiragana,
    _resolve_via_member_master,
)


def test_normalize_name_removes_honorifics_and_symbols():
    assert _normalize_name("  ＰＡＹさん  ") == "pay"
    assert _normalize_name("ゲスト氏（里芋、トーマス）") == ""
    assert _normalize_name("20251123撮影_りょうすけさん") == "20251123撮影りょうすけ"


def test_extract_names_from_title_includes_aliases():
    names = _extract_names_from_title("ゲスト氏（里芋、トーマス）さん：30代前半")
    normalized = {_normalize_name(n) for n in names}
    assert "里芋" in normalized
    assert "トーマス" in normalized


def test_matching_accuracy_over_30_cases():
    # 要件: 15/30 -> 25/30以上
    cases = [
        ("Izu", "INT015_Izuさん", True),
        ("izu", "53.izuさん", True),
        ("りょうすけ", "20251123撮影_りょうすけさん20代後半内資IT勤務年収600万", True),
        ("PAY", "20251213撮影_payさん30代中盤LINEyahoo年収850万", True),
        ("PAY", "20251213撮影_PAYさん30代中盤LINEyahoo年収850万", True),
        ("トーマス", "ゲスト氏（里芋、トーマス）さん：30代前半", True),
        ("里芋", "ゲスト氏（里芋、トーマス）さん：30代前半", True),
        ("こてつ", "コテツさん：31歳製造業", True),
        ("ブン", "INT001_ブンさん", True),
        ("ゆきもる", "20251213撮影_ゆきもるさん30代前半外資製薬MR年収1000万", True),
        ("ryo", "20260124撮影_ryoさん40代前半大手不動産年収1100万円", True),
        ("RYO", "20260124撮影_ryoさん40代前半大手不動産年収1100万円", True),
        ("あんでぃ", "20260215撮影_アンディさん", True),
        ("アンディ", "20260215撮影_あんでぃさん", True),
        ("しお", "20251213撮影_しおさん30代前半外資製薬MR年収1050万", True),
        ("ひらい", "20260215撮影_hiraiさん仮名34歳損保マーケティング年収850万", True),
        ("hirai", "20260215撮影_hiraiさん仮名34歳損保マーケティング年収850万", True),
        ("スリマン", "20251213撮影_スリマンさん30代前半外資IT年収1900万", True),
        ("みんてぃあ", "20251130撮影_みんてぃあさん40代前半AWS管理職年収2200万", True),
        ("Izu", "INT015_IzU氏", True),
        ("やーまん", "20260124撮影_やーまんさん", True),
        ("ロキ", "20260215撮影_ロキさん", True),
        ("くますけ", "20260215撮影_くますけさん", True),
        ("真生", "20251130撮影_真生さん30代前半薬剤師年収700万", True),
        ("さるビール", "20251130撮影_さるビールさん30代前半キリンビール年収700万", True),
        ("山田", "INT001_ブンさん", False),
        ("abc", "20251123撮影_りょうすけさん", False),
        ("Izu", "INT020_Suzuさん", False),
        ("トーマス", "INT003_タケシさん", False),
        ("PAY", "INT777_ぱやさん", False),
    ]

    correct = 0
    for guest_name, title, expected in cases:
        got = _match_guest_name(guest_name, title)
        if got == expected:
            correct += 1

    assert correct >= 25, f"matching accuracy too low: {correct}/30"


def test_romaji_to_hiragana_basic():
    """ローマ字→ひらがな変換の基本テスト"""
    assert _romaji_to_hiragana("hirai") == "ひらい"
    assert _romaji_to_hiragana("ryo") == "りょ"
    assert _romaji_to_hiragana("izu") == "いず"
    assert _romaji_to_hiragana("tsubasa") == "つばさ"
    assert _romaji_to_hiragana("shin") == "しん"
    assert _romaji_to_hiragana("") == ""
    # 日本語が混ざっている場合は変換しない
    assert _romaji_to_hiragana("ひらい") == ""


def test_romaji_hiragana_matching():
    """ローマ字↔ひらがなの相互マッチングテスト"""
    # ひらがな → ローマ字タイトル
    assert _match_guest_name("ひらい", "20260215撮影_hiraiさん仮名34歳損保マーケティング年収850万")
    # ローマ字 → ひらがなタイトル
    assert _match_guest_name("hirai", "20260215撮影_ひらいさん仮名34歳")


def test_member_master_transcription_error_matching():
    """MEMBER_MASTER.jsonのtranscription_errorsを使ったマッチングテスト"""
    # MEMBER_MASTER.jsonが存在する場合のみ実行
    canonical = _resolve_via_member_master("コスト")
    if canonical is None:
        return  # MEMBER_MASTER.jsonがない環境ではスキップ
    # 「コスト」→ canonical_name「kos」に解決されるべき
    assert canonical == "kos"
    # 「コスト氏」も同様
    assert _resolve_via_member_master("コスト氏") == "kos"


def test_negative_cases_remain_negative():
    """False期待のケースが誤ってTrueにならないことを確認"""
    # 短すぎる名前での偶発的マッチを防ぐ
    assert not _match_guest_name("abc", "20251123撮影_りょうすけさん")
    assert not _match_guest_name("山田", "INT001_ブンさん")
    assert not _match_guest_name("Izu", "INT020_Suzuさん")
    assert not _match_guest_name("トーマス", "INT003_タケシさん")
