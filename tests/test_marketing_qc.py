"""タイミング3: マーケティング品質QC Phase2 テスト

teko_core.llm はモックして、プロンプト構築・レスポンス解析・データ構造を網羅的にテスト。
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from video_direction.qc.marketing_qc import (
    MarketingQCIssue,
    MarketingQCResult,
    _build_marketing_qc_prompt,
    _parse_llm_response,
    run_marketing_qc,
)
from video_direction.qc.qc_comparator import QCResult


# ===================================================================
# MarketingQCIssue テスト
# ===================================================================

class TestMarketingQCIssue:
    def test_to_dict(self):
        issue = MarketingQCIssue(
            category="highlight",
            severity="error",
            description="パンチラインが弱い",
            suggestion="共感型のフレーズに差し替えを検討",
            timestamp_sec=30.0,
            timecode="00:30",
        )
        d = issue.to_dict()
        assert d["category"] == "highlight"
        assert d["severity"] == "error"
        assert d["description"] == "パンチラインが弱い"
        assert d["suggestion"] == "共感型のフレーズに差し替えを検討"

    def test_from_dict(self):
        data = {
            "category": "direction",
            "severity": "warning",
            "description": "テスト",
            "suggestion": "改善案",
            "timestamp_sec": 10.0,
            "timecode": "00:10",
        }
        issue = MarketingQCIssue.from_dict(data)
        assert issue.category == "direction"
        assert issue.severity == "warning"

    def test_from_dict_defaults(self):
        issue = MarketingQCIssue.from_dict({})
        assert issue.category == "general"
        assert issue.severity == "warning"
        assert issue.description == ""

    def test_roundtrip(self):
        original = MarketingQCIssue(
            category="punchline",
            severity="info",
            description="代替パンチライン候補あり",
            suggestion="「歯車でいることには飽きた」を検討",
        )
        restored = MarketingQCIssue.from_dict(original.to_dict())
        assert restored.category == original.category
        assert restored.severity == original.severity
        assert restored.description == original.description
        assert restored.suggestion == original.suggestion


# ===================================================================
# MarketingQCResult テスト
# ===================================================================

class TestMarketingQCResult:
    def test_to_dict(self):
        result = MarketingQCResult(
            project_id="PRJ001",
            status="failed",
            issues=[
                MarketingQCIssue(category="highlight", severity="error", description="テスト"),
            ],
            error_count=1,
            warning_count=0,
            info_count=0,
            content_line="career",
            highlight_assessment="パンチラインが弱い",
            direction_assessment="演出は問題なし",
        )
        d = result.to_dict()
        assert d["project_id"] == "PRJ001"
        assert d["status"] == "failed"
        assert len(d["issues"]) == 1
        assert d["content_line"] == "career"
        assert d["highlight_assessment"] == "パンチラインが弱い"
        # raw_llm_response はto_dictに含まれない（デバッグ用）
        assert "raw_llm_response" not in d

    def test_from_dict(self):
        data = {
            "project_id": "PRJ002",
            "status": "passed",
            "issues": [],
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "content_line": "realestate",
            "highlight_assessment": "問題なし",
            "direction_assessment": "問題なし",
        }
        result = MarketingQCResult.from_dict(data)
        assert result.project_id == "PRJ002"
        assert result.status == "passed"
        assert result.content_line == "realestate"

    def test_has_errors(self):
        r1 = MarketingQCResult(error_count=0)
        assert r1.has_errors is False
        r2 = MarketingQCResult(error_count=1)
        assert r2.has_errors is True

    def test_roundtrip(self):
        original = MarketingQCResult(
            project_id="PRJ003",
            status="failed",
            issues=[
                MarketingQCIssue(category="tier", severity="error", description="層分類誤り"),
                MarketingQCIssue(category="direction", severity="warning", description="抽象的"),
            ],
            error_count=1,
            warning_count=1,
            info_count=0,
            content_line="career",
        )
        restored = MarketingQCResult.from_dict(original.to_dict())
        assert restored.project_id == original.project_id
        assert restored.status == original.status
        assert len(restored.issues) == 2
        assert restored.issues[0].category == "tier"


# ===================================================================
# プロンプト構築テスト
# ===================================================================

class TestBuildMarketingQCPrompt:
    def test_basic_prompt(self):
        """基本的なプロンプト構築が成功すること"""
        system, user = _build_marketing_qc_prompt(
            telop_texts=["[00:30] キャッシュフローが重要です"],
            transcript_text="キャッシュフローが重要ですよね",
            content_line="career",
        )
        # システムプロンプトに品質基準が含まれる
        assert "品質基準" in system
        assert "QC判定ルール" in system
        assert "JSON" in system

        # ユーザープロンプトにデータが含まれる
        assert "テロップ一覧" in user
        assert "キャッシュフローが重要です" in user
        assert "文字起こし" in user

    def test_with_direction_report(self):
        """ディレクションレポートが含まれること"""
        _, user = _build_marketing_qc_prompt(
            telop_texts=["[00:10] テスト"],
            transcript_text="テスト",
            direction_report="冒頭ハイライトは年収をフォーカス",
            content_line="career",
        )
        assert "ディレクションレポート" in user
        assert "冒頭ハイライトは年収をフォーカス" in user

    def test_with_guest_profile(self):
        """ゲストプロファイルが含まれること"""
        _, user = _build_marketing_qc_prompt(
            telop_texts=["[00:10] テスト"],
            transcript_text="テスト",
            guest_profile="年収850万 国内大手生保 マーケティング",
            content_line="career",
        )
        assert "ゲストプロファイル" in user
        assert "年収850万" in user

    def test_realestate_content_line(self):
        """不動産軸が正しくラベル付けされること"""
        _, user = _build_marketing_qc_prompt(
            telop_texts=[],
            transcript_text="不動産投資の話",
            content_line="realestate",
        )
        assert "不動産実績対談" in user

    def test_career_content_line(self):
        """キャリア軸が正しくラベル付けされること"""
        _, user = _build_marketing_qc_prompt(
            telop_texts=[],
            transcript_text="キャリアの話",
            content_line="career",
        )
        assert "キャリア軸" in user

    def test_empty_telops(self):
        """テロップ空でもエラーにならないこと"""
        system, user = _build_marketing_qc_prompt(
            telop_texts=[],
            transcript_text="テスト",
            content_line="career",
        )
        assert "テロップ検出なし" in user

    def test_long_transcript_truncated(self):
        """長い文字起こしが適切に切り詰められること"""
        long_text = "あ" * 20000
        _, user = _build_marketing_qc_prompt(
            telop_texts=[],
            transcript_text=long_text,
            content_line="career",
        )
        assert "中略" in user
        # 元テキスト全文は含まれない
        assert len(user) < 20000

    def test_check_items_present(self):
        """5つのチェック項目がプロンプトに含まれること"""
        _, user = _build_marketing_qc_prompt(
            telop_texts=["[00:10] テスト"],
            transcript_text="テスト",
            content_line="career",
        )
        assert "ハイライト選定" in user
        assert "強調演出ポイント" in user
        assert "層分類" in user
        assert "コンテンツライン" in user
        assert "NGパターン" in user


# ===================================================================
# LLMレスポンス解析テスト
# ===================================================================

class TestParseLLMResponse:
    def test_json_block(self):
        """```json ... ``` ブロックからの解析"""
        response = '''分析結果:

```json
{
  "highlight_assessment": "ハイライトは適切",
  "direction_assessment": "演出品質に問題なし",
  "issues": [
    {
      "category": "highlight",
      "severity": "warning",
      "description": "パンチラインの候補を追加検討可能",
      "suggestion": "共感型のパンチラインも検討"
    }
  ]
}
```

以上です。'''
        highlight, direction, issues = _parse_llm_response(response)
        assert highlight == "ハイライトは適切"
        assert direction == "演出品質に問題なし"
        assert len(issues) == 1
        assert issues[0]["category"] == "highlight"
        assert issues[0]["severity"] == "warning"

    def test_raw_json(self):
        """生JSONからの解析"""
        response = '{"highlight_assessment": "問題なし", "direction_assessment": "OK", "issues": []}'
        highlight, direction, issues = _parse_llm_response(response)
        assert highlight == "問題なし"
        assert direction == "OK"
        assert len(issues) == 0

    def test_no_json(self):
        """JSON未含有のレスポンス"""
        response = "この動画は特に問題ありません。"
        highlight, direction, issues = _parse_llm_response(response)
        assert highlight == ""
        assert direction == ""
        assert len(issues) == 0

    def test_invalid_json(self):
        """壊れたJSON"""
        response = '```json\n{"highlight_assessment": "テスト", invalid}\n```'
        highlight, direction, issues = _parse_llm_response(response)
        assert highlight == ""
        assert len(issues) == 0

    def test_multiple_issues(self):
        """複数の問題を含むレスポンス"""
        response = json.dumps({
            "highlight_assessment": "弱い",
            "direction_assessment": "抽象的",
            "issues": [
                {"category": "highlight", "severity": "error", "description": "パンチラインが弱い", "suggestion": "差し替え"},
                {"category": "direction", "severity": "warning", "description": "抽象的すぎる", "suggestion": "具体化"},
                {"category": "tier", "severity": "info", "description": "層分類は適切", "suggestion": ""},
            ]
        }, ensure_ascii=False)
        highlight, direction, issues = _parse_llm_response(response)
        assert highlight == "弱い"
        assert len(issues) == 3
        assert issues[0]["severity"] == "error"
        assert issues[1]["severity"] == "warning"
        assert issues[2]["severity"] == "info"

    def test_empty_issues(self):
        """issuesが空配列のレスポンス"""
        response = json.dumps({
            "highlight_assessment": "問題なし",
            "direction_assessment": "問題なし",
            "issues": []
        })
        highlight, direction, issues = _parse_llm_response(response)
        assert highlight == "問題なし"
        assert len(issues) == 0


# ===================================================================
# run_marketing_qc 統合テスト（LLMモック）
# ===================================================================

class TestRunMarketingQC:
    def _mock_llm_response(self, status="passed", issues=None):
        """LLMレスポンスのモックを生成"""
        if issues is None:
            issues = []
        return json.dumps({
            "highlight_assessment": "ハイライト選定は品質基準を満たしている",
            "direction_assessment": "演出ディレクションは適切",
            "issues": issues,
        }, ensure_ascii=False)

    def test_passed_result(self):
        """問題なしの場合のテスト"""
        mock_response = self._mock_llm_response()

        with patch.dict("sys.modules", {"teko_core": MagicMock(), "teko_core.llm": MagicMock(ask=lambda *a, **kw: mock_response)}):
            result = run_marketing_qc(
                telop_texts=["[00:30] キャッシュフロー"],
                transcript_text="キャッシュフローが重要です",
                project_id="TEST001",
            )

        assert result.status == "passed"
        assert result.error_count == 0
        assert result.project_id == "TEST001"

    def test_failed_result(self):
        """問題ありの場合のテスト"""
        mock_response = self._mock_llm_response(
            status="failed",
            issues=[
                {"category": "highlight", "severity": "error", "description": "パンチラインが弱い", "suggestion": "差し替え"},
            ]
        )

        with patch.dict("sys.modules", {"teko_core": MagicMock(), "teko_core.llm": MagicMock(ask=lambda *a, **kw: mock_response)}):
            result = run_marketing_qc(
                telop_texts=["[00:30] 外車買ってもらったりとか"],
                transcript_text="外車買ってもらったりとか",
                project_id="TEST002",
            )

        assert result.status == "failed"
        assert result.error_count == 1
        assert len(result.issues) == 1
        assert result.issues[0].category == "highlight"

    def test_llm_error_returns_error_status(self):
        """LLM呼び出しエラー時にerrorステータスを返すこと"""
        def raise_error(*args, **kwargs):
            raise RuntimeError("LLM接続エラー")

        with patch.dict("sys.modules", {"teko_core": MagicMock(), "teko_core.llm": MagicMock(ask=raise_error)}):
            result = run_marketing_qc(
                telop_texts=["[00:10] テスト"],
                transcript_text="テスト",
                project_id="TEST003",
            )

        assert result.status == "error"
        assert "LLM接続エラー" in result.raw_llm_response

    def test_content_line_auto_detection(self):
        """コンテンツラインの自動判定テスト"""
        mock_response = self._mock_llm_response()

        with patch.dict("sys.modules", {"teko_core": MagicMock(), "teko_core.llm": MagicMock(ask=lambda *a, **kw: mock_response)}):
            # 不動産キーワードが多いテキスト
            result = run_marketing_qc(
                telop_texts=["[00:10] 物件 利回り 融資"],
                transcript_text="不動産投資で物件を購入し、利回り8%で融資を受けて、キャッシュフローが月20万。築10年の一棟マンション。",
                project_id="TEST004",
                content_line=None,  # 自動判定
            )
            assert result.content_line == "realestate"

    def test_content_line_manual_override(self):
        """コンテンツラインの手動指定テスト"""
        mock_response = self._mock_llm_response()

        with patch.dict("sys.modules", {"teko_core": MagicMock(), "teko_core.llm": MagicMock(ask=lambda *a, **kw: mock_response)}):
            result = run_marketing_qc(
                telop_texts=[],
                transcript_text="キャリアの話",
                project_id="TEST005",
                content_line="realestate",  # 手動で上書き
            )
            assert result.content_line == "realestate"


# ===================================================================
# QCResult マーケQC統合テスト
# ===================================================================

class TestQCResultMarketingIntegration:
    def test_combined_status_both_passed(self):
        """テロップQC・マーケQC両方passedの場合"""
        result = QCResult(
            status="passed",
            marketing_qc={"status": "passed", "error_count": 0},
        )
        assert result.combined_status == "passed"

    def test_combined_status_telop_failed(self):
        """テロップQCがfailedの場合"""
        result = QCResult(
            status="failed",
            error_count=1,
            marketing_qc={"status": "passed", "error_count": 0},
        )
        assert result.combined_status == "failed"

    def test_combined_status_marketing_failed(self):
        """マーケQCがfailedの場合"""
        result = QCResult(
            status="passed",
            marketing_qc={"status": "failed", "error_count": 1},
        )
        assert result.combined_status == "failed"

    def test_combined_status_no_marketing(self):
        """マーケQC未実行の場合"""
        result = QCResult(status="passed", marketing_qc=None)
        assert result.combined_status == "passed"

    def test_combined_status_marketing_error(self):
        """マーケQCがerrorの場合"""
        result = QCResult(
            status="passed",
            marketing_qc={"status": "error", "error_message": "LLMエラー"},
        )
        assert result.combined_status == "error"

    def test_to_dict_includes_marketing_qc(self):
        """to_dictにマーケQCが含まれること"""
        mq = {"status": "passed", "issues": [], "error_count": 0}
        result = QCResult(status="passed", marketing_qc=mq)
        d = result.to_dict()
        assert "marketing_qc" in d
        assert d["marketing_qc"]["status"] == "passed"
        assert "combined_status" in d
        assert d["combined_status"] == "passed"

    def test_to_dict_without_marketing_qc(self):
        """マーケQCなしの場合to_dictにmarketing_qcキーがないこと"""
        result = QCResult(status="passed", marketing_qc=None)
        d = result.to_dict()
        assert "marketing_qc" not in d
        assert d["combined_status"] == "passed"

    def test_from_dict_with_marketing_qc(self):
        """from_dictでマーケQCが復元されること"""
        data = {
            "project_id": "PRJ001",
            "status": "passed",
            "issues": [],
            "marketing_qc": {"status": "failed", "error_count": 1, "issues": []},
        }
        result = QCResult.from_dict(data)
        assert result.marketing_qc is not None
        assert result.marketing_qc["status"] == "failed"

    def test_from_dict_without_marketing_qc(self):
        """Phase1のみの古いデータでもfrom_dictが成功すること（後方互換性）"""
        data = {
            "project_id": "PRJ001",
            "status": "passed",
            "issues": [],
        }
        result = QCResult.from_dict(data)
        assert result.marketing_qc is None
        assert result.combined_status == "passed"
