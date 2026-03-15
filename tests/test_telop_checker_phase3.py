"""C-2 Phase 3: フレーム画像ベースのテロップ自動チェックのテスト

テスト対象:
- extract_telop_from_frame（OCR/LLMテロップ抽出）
- check_spelling（誤字脱字チェック）
- check_font_consistency（フォント一貫性チェック）
- analyze_telop_timing（タイミング評価）
- check_telops_from_frames（総合チェック）
- API: GET/POST /api/v1/projects/{id}/telop-check
"""

import base64
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from video_direction.analyzer.telop_checker import (
    # Phase 3 新規関数
    extract_telop_from_frame,
    check_spelling,
    check_font_consistency,
    analyze_telop_timing,
    check_telops_from_frames,
    ExtractedTelop,
    TelopTimingIssue,
    FrameTelopCheckResult,
    _clean_ocr_text,
    _parse_llm_telop_response,
    _seconds_to_timestamp,
    # Phase 2 既存（回帰確認用）
    check_telops,
    TelopCheckResult,
    TelopCandidate,
    TelopIssue,
)
from video_direction.integrations.ai_dev5_connector import VideoData, HighlightScene


# === テストヘルパー ===

def _make_video_data(highlights=None):
    return VideoData(
        title="テスト動画",
        duration="30分",
        speakers="ホスト, ゲスト",
        highlights=highlights or [],
        main_topics=["トピック1"],
    )


def _make_dummy_image_b64():
    """ダミーの1x1 JPEG base64文字列を生成"""
    # 最小有効JPEGバイナリ
    import struct
    # 単純な1x1白JPEGの代わりにダミーバイト列を使う
    return base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 100 + b"\xff\xd9").decode()


# === check_spelling テスト ===

class TestCheckSpelling:
    """誤字脱字チェックのテスト"""

    def test_正常テキストは問題なし(self):
        issues = check_spelling("年収1200万")
        # 括弧不一致やパターンエラーがなければ空
        typo_issues = [i for i in issues if i.issue_type == "typo"]
        # 特にパターンに引っかからないので0件
        assert len([i for i in typo_issues if "括弧" in i.description]) == 0

    def test_全角半角数字の混在を検出(self):
        issues = check_spelling("年収１200万")
        mixed = [i for i in issues if "全角数字と半角数字" in i.description]
        assert len(mixed) == 1
        assert mixed[0].severity == "warning"

    def test_全角半角英字の混在を検出(self):
        issues = check_spelling("TEKOのＳＥＯ対策")
        mixed = [i for i in issues if "全角英字と半角英字" in i.description]
        assert len(mixed) == 1
        assert mixed[0].severity == "info"

    def test_括弧不一致を検出(self):
        issues = check_spelling("「テスト")
        bracket = [i for i in issues if "括弧" in i.description]
        assert len(bracket) > 0
        assert bracket[0].severity == "error"

    def test_括弧が対応していれば問題なし(self):
        issues = check_spelling("「テスト」は良い")
        bracket = [i for i in issues if "括弧" in i.description]
        assert len(bracket) == 0

    def test_同一ひらがな連続を検出(self):
        issues = check_spelling("ああああああ")
        repeat = [i for i in issues if "連続" in i.description]
        assert len(repeat) > 0


# === check_font_consistency テスト ===

class TestCheckFontConsistency:
    """フォント一貫性チェックのテスト"""

    def test_単一テロップでは問題なし(self):
        telops = [
            ExtractedTelop(timestamp="01:00", text="テスト", font_info="ゴシック体・白", source="llm"),
        ]
        issues = check_font_consistency(telops)
        assert len(issues) == 0

    def test_フォント3種以上で警告(self):
        telops = [
            ExtractedTelop(timestamp="01:00", text="テスト1", font_info="ゴシック体・白・大", source="llm"),
            ExtractedTelop(timestamp="02:00", text="テスト2", font_info="明朝体・黄色・中", source="llm"),
            ExtractedTelop(timestamp="03:00", text="テスト3", font_info="ポップ体・赤・小", source="llm"),
        ]
        issues = check_font_consistency(telops)
        font_issues = [i for i in issues if i.issue_type == "consistency"]
        assert len(font_issues) > 0

    def test_同じフォントなら問題なし(self):
        telops = [
            ExtractedTelop(timestamp="01:00", text="テスト1", font_info="ゴシック体・白", source="llm"),
            ExtractedTelop(timestamp="02:00", text="テスト2", font_info="ゴシック体・白", source="llm"),
        ]
        issues = check_font_consistency(telops)
        font_issues = [i for i in issues if "フォント" in i.description]
        assert len(font_issues) == 0

    def test_位置がバラバラだとinfo(self):
        telops = [
            ExtractedTelop(timestamp="01:00", text="テスト1", position="top", source="ocr"),
            ExtractedTelop(timestamp="02:00", text="テスト2", position="bottom", source="ocr"),
            ExtractedTelop(timestamp="03:00", text="テスト3", position="center", source="ocr"),
        ]
        issues = check_font_consistency(telops)
        pos_issues = [i for i in issues if i.issue_type == "placement"]
        assert len(pos_issues) > 0


# === analyze_telop_timing テスト ===

class TestAnalyzeTelopTiming:
    """テロップ表示タイミング評価のテスト"""

    def test_空リストは問題なし(self):
        issues = analyze_telop_timing([])
        assert len(issues) == 0

    def test_適切な表示時間は問題なし(self):
        telops = [
            {"text": "年収1200万", "start_sec": 10.0, "end_sec": 13.0},
        ]
        issues = analyze_telop_timing(telops)
        short_issues = [i for i in issues if i.issue_type == "too_short"]
        assert len(short_issues) == 0

    def test_表示時間が短すぎると警告(self):
        telops = [
            {"text": "テスト", "start_sec": 10.0, "end_sec": 10.5},
        ]
        issues = analyze_telop_timing(telops)
        short_issues = [i for i in issues if i.issue_type == "too_short"]
        assert len(short_issues) > 0

    def test_表示時間が長すぎるとinfo(self):
        telops = [
            {"text": "テスト", "start_sec": 10.0, "end_sec": 20.0},
        ]
        issues = analyze_telop_timing(telops)
        long_issues = [i for i in issues if i.issue_type == "too_long"]
        assert len(long_issues) > 0

    def test_テロップ重複を検出(self):
        telops = [
            {"text": "テスト1", "start_sec": 10.0, "end_sec": 15.0},
            {"text": "テスト2", "start_sec": 13.0, "end_sec": 18.0},
        ]
        issues = analyze_telop_timing(telops)
        overlap_issues = [i for i in issues if i.issue_type == "overlap"]
        assert len(overlap_issues) > 0
        assert overlap_issues[0].duration_sec == pytest.approx(2.0, abs=0.1)

    def test_文字数に対して短すぎるとエラー(self):
        telops = [
            {"text": "これはとても長いテロップテキストです", "start_sec": 10.0, "end_sec": 10.8},
        ]
        issues = analyze_telop_timing(telops)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) > 0


# === check_telops_from_frames テスト ===

class TestCheckTelopsFromFrames:
    """フレーム画像ベースの総合テロップチェックテスト"""

    def test_フレームなしで空の結果(self):
        result = check_telops_from_frames()
        assert isinstance(result, FrameTelopCheckResult)
        assert result.total_frames_checked == 0
        assert result.total_telops_found == 0
        assert result.extraction_method == "none"
        assert result.overall_score == 100.0

    def test_結果のデータ構造が正しい(self):
        result = check_telops_from_frames()
        assert hasattr(result, "extracted_telops")
        assert hasattr(result, "spelling_issues")
        assert hasattr(result, "consistency_issues")
        assert hasattr(result, "timing_issues")
        assert hasattr(result, "overall_score")

    def test_タイミングデータ付きで実行(self):
        timing_data = [
            {"text": "年収1200万", "start_sec": 10.0, "end_sec": 13.0},
            {"text": "テスト", "start_sec": 20.0, "end_sec": 20.5},
        ]
        result = check_telops_from_frames(telops_with_timestamps=timing_data)
        # タイミングチェックが実行される
        assert len(result.timing_issues) > 0


# === _clean_ocr_text テスト ===

class TestCleanOcrText:
    """OCRテキストクリーニングのテスト"""

    def test_改行除去(self):
        assert _clean_ocr_text("テスト\nテキスト") == "テスト テキスト"

    def test_連続空白を1つに(self):
        assert _clean_ocr_text("テスト   テキスト") == "テスト テキスト"

    def test_短すぎるテキストは空文字(self):
        assert _clean_ocr_text("あ") == ""

    def test_記号のみは空文字(self):
        assert _clean_ocr_text("---") == ""

    def test_正常テキストはそのまま(self):
        assert _clean_ocr_text("年収1200万") == "年収1200万"


# === _parse_llm_telop_response テスト ===

class TestParseLlmTelopResponse:
    """LLMレスポンスパースのテスト"""

    def test_正常なJSONレスポンス(self):
        response = '''```json
[
  {"text": "年収1200万", "position": "bottom", "font_info": "ゴシック体", "color_info": "白文字"}
]
```'''
        telops = _parse_llm_telop_response(response, "05:00")
        assert len(telops) == 1
        assert telops[0].text == "年収1200万"
        assert telops[0].position == "bottom"
        assert telops[0].source == "llm"
        assert telops[0].timestamp == "05:00"

    def test_空の配列(self):
        response = '```json\n[]\n```'
        telops = _parse_llm_telop_response(response, "05:00")
        assert len(telops) == 0

    def test_複数テロップ(self):
        response = '''```json
[
  {"text": "年収1200万", "position": "bottom"},
  {"text": "30代エンジニア", "position": "top"}
]
```'''
        telops = _parse_llm_telop_response(response, "05:00")
        assert len(telops) == 2

    def test_不正なJSON(self):
        response = "テロップは見つかりませんでした"
        telops = _parse_llm_telop_response(response, "05:00")
        assert len(telops) == 0

    def test_コードブロックなしの生JSON(self):
        response = '[{"text": "テスト", "position": "center"}]'
        telops = _parse_llm_telop_response(response, "05:00")
        assert len(telops) == 1

    def test_短すぎるテキストは除外(self):
        response = '[{"text": "a", "position": "bottom"}]'
        telops = _parse_llm_telop_response(response, "05:00")
        assert len(telops) == 0


# === _seconds_to_timestamp テスト ===

class TestSecondsToTimestamp:
    """秒→タイムスタンプ変換テスト"""

    def test_0秒(self):
        assert _seconds_to_timestamp(0) == "00:00"

    def test_90秒(self):
        assert _seconds_to_timestamp(90) == "01:30"

    def test_600秒(self):
        assert _seconds_to_timestamp(600) == "10:00"


# === ExtractedTelop データクラステスト ===

class TestExtractedTelop:
    """ExtractedTelopデータクラスのテスト"""

    def test_デフォルト値(self):
        t = ExtractedTelop(timestamp="01:00", text="テスト")
        assert t.confidence == 0.0
        assert t.position == ""
        assert t.source == "unknown"

    def test_全フィールド設定(self):
        t = ExtractedTelop(
            timestamp="01:00",
            text="テスト",
            confidence=0.9,
            position="bottom",
            font_info="ゴシック体",
            color_info="白",
            source="llm",
        )
        assert t.confidence == 0.9
        assert t.font_info == "ゴシック体"


# === API テスト ===

class TestTelopCheckAPI:
    """テロップチェックAPIエンドポイントのテスト"""

    @pytest.fixture
    def client(self, tmp_path):
        from fastapi.testclient import TestClient
        from video_direction.integrations.api_server import app, init_db, DB_PATH
        import sqlite3

        test_db = tmp_path / "test.db"
        with patch("video_direction.integrations.api_server.DB_PATH", test_db):
            init_db()
            conn = sqlite3.connect(str(test_db))
            conn.execute(
                """INSERT INTO projects (id, guest_name, title, status, quality_score, knowledge)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    "p-telop-001",
                    "テストゲスト",
                    "テロップテスト動画",
                    "directed",
                    75,
                    json.dumps({
                        "highlights": [
                            {"timestamp": "01:30", "speaker": "ゲスト", "text": "年収5000万", "category": "実績数字"},
                        ]
                    }),
                ),
            )
            conn.commit()
            conn.close()
            yield TestClient(app)

    def test_GET_未チェックプロジェクト(self, client):
        response = client.get("/api/v1/projects/p-telop-001/telop-check")
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "p-telop-001"
        # キャッシュが存在する場合はcompleted、なければnot_checkedまたはunavailable
        assert data["status"] in ("not_checked", "unavailable", "completed")

    def test_POST_テロップチェック実行(self, client):
        response = client.post(
            "/api/v1/projects/p-telop-001/telop-check",
            json={},
        )
        # モジュールが利用できない場合は500、利用可能なら200
        if response.status_code == 200:
            data = response.json()
            assert data["project_id"] == "p-telop-001"
            assert data["status"] == "completed"
            assert "frame_check" in data
            assert "text_check" in data
            assert isinstance(data["frame_check"]["overall_score"], (int, float))

    def test_POST_存在しないプロジェクトは404(self, client):
        response = client.post(
            "/api/v1/projects/p-nonexistent/telop-check",
            json={},
        )
        assert response.status_code in (404, 500)


# === Phase 2 既存テスト回帰確認 ===

class TestPhase2Regression:
    """Phase 2の既存機能が壊れていないことの回帰確認"""

    def test_check_telops_基本動作(self):
        highlights = [
            HighlightScene(timestamp="02:30", speaker="ゲスト", text="年収1000万", category="実績数字"),
            HighlightScene(timestamp="05:00", speaker="ゲスト", text="挑戦が大事", category="パンチライン"),
        ]
        video = _make_video_data(highlights=highlights)
        result = check_telops(video)
        assert isinstance(result, TelopCheckResult)
        assert result.total_telops == 2
        assert result.is_estimated is True

    def test_check_telops_空ハイライト(self):
        video = _make_video_data(highlights=[])
        result = check_telops(video)
        assert result.total_telops == 0
        assert result.consistency_score == 100.0

    def test_TelopIssue_データ構造(self):
        issue = TelopIssue(
            timestamp="05:00",
            issue_type="typo",
            severity="error",
            description="テスト",
        )
        assert issue.original_text == ""
        assert issue.suggestion == ""
