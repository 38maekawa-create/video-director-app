"""マーケティング品質QC（Phase2）

QUALITY_JUDGMENT_GUIDEの品質基準をプロンプトに注入し、
テロップ内容・ハイライト選定・強調演出ポイントがマーケ基準を満たしているか
Opus定額内（teko_core.llm経由）で自動判定する。

設計書: docs/TIMING3_AUTO_QC_DESIGN.md Phase2
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from ..knowledge.quality_knowledge_loader import (
    build_quality_injection_text,
    determine_content_line,
    get_highlight_criteria,
    get_direction_criteria,
    get_guest_tier_criteria,
)

logger = logging.getLogger(__name__)


@dataclass
class MarketingQCIssue:
    """マーケQCで検出された問題"""
    category: str          # "highlight" | "direction" | "tier" | "punchline" | "general"
    severity: str          # "error" | "warning" | "info"
    description: str       # 問題の説明
    suggestion: str = ""   # 改善提案
    timestamp_sec: float = 0.0  # 該当箇所のタイムスタンプ（特定できる場合）
    timecode: str = ""     # MM:SS形式

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "severity": self.severity,
            "description": self.description,
            "suggestion": self.suggestion,
            "timestamp_sec": self.timestamp_sec,
            "timecode": self.timecode,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MarketingQCIssue:
        return cls(
            category=data.get("category", "general"),
            severity=data.get("severity", "warning"),
            description=data.get("description", ""),
            suggestion=data.get("suggestion", ""),
            timestamp_sec=data.get("timestamp_sec", 0.0),
            timecode=data.get("timecode", ""),
        )


@dataclass
class MarketingQCResult:
    """マーケQCの判定結果"""
    project_id: str = ""
    status: str = "pending"  # "pending" | "passed" | "failed" | "error"
    issues: list[MarketingQCIssue] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    content_line: str = ""         # "career" | "realestate"
    highlight_assessment: str = ""  # ハイライト選定の総合評価テキスト
    direction_assessment: str = ""  # 演出ディレクションの総合評価テキスト
    raw_llm_response: str = ""      # LLMの生レスポンス（デバッグ用）

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "status": self.status,
            "issues": [i.to_dict() for i in self.issues],
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "content_line": self.content_line,
            "highlight_assessment": self.highlight_assessment,
            "direction_assessment": self.direction_assessment,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MarketingQCResult:
        issues = [MarketingQCIssue.from_dict(i) for i in data.get("issues", [])]
        return cls(
            project_id=data.get("project_id", ""),
            status=data.get("status", "pending"),
            issues=issues,
            error_count=data.get("error_count", 0),
            warning_count=data.get("warning_count", 0),
            info_count=data.get("info_count", 0),
            content_line=data.get("content_line", ""),
            highlight_assessment=data.get("highlight_assessment", ""),
            direction_assessment=data.get("direction_assessment", ""),
        )


def _build_marketing_qc_prompt(
    telop_texts: list[str],
    transcript_text: str,
    direction_report: str = "",
    guest_profile: str = "",
    content_line: str = "career",
) -> tuple[str, str]:
    """マーケQC用のシステムプロンプトとユーザープロンプトを構築する

    Args:
        telop_texts: テロップテキスト一覧（タイムスタンプ付き）
        transcript_text: Whisper文字起こし全文
        direction_report: ディレクションレポート（あれば）
        guest_profile: ゲストプロファイル（あれば）
        content_line: コンテンツライン（"career" or "realestate"）

    Returns:
        (system_prompt, user_prompt) のタプル
    """
    # QUALITY_JUDGMENT_GUIDEから品質基準テキストを注入
    quality_text = build_quality_injection_text(
        content_line=content_line,
        include_highlight=True,
        include_direction=True,
        include_content_line=True,
        include_tier=True,
        compact=False,
    )

    system_prompt = f"""あなたはTEKO対談動画のマーケティング品質QC担当者です。
以下の品質基準に基づいて、編集済み動画のテロップ内容・ハイライト選定・強調演出ポイントを精査してください。

{quality_text}

## QC判定ルール
- 各チェック項目について「問題なし」「警告」「エラー」の3段階で判定する
- エラー: マーケ品質基準を明確に違反。修正必須
- 警告: 基準を完全には満たしていないが、許容範囲の可能性あり。確認推奨
- 情報: 品質向上の提案。対応は任意

## 回答フォーマット（必ずJSON形式で返すこと）
```json
{{
  "highlight_assessment": "ハイライト選定の総合評価（1-2文）",
  "direction_assessment": "演出ディレクションの総合評価（1-2文）",
  "issues": [
    {{
      "category": "highlight|direction|tier|punchline|general",
      "severity": "error|warning|info",
      "description": "問題の説明",
      "suggestion": "改善提案"
    }}
  ]
}}
```

issuesが空の場合は空配列[]を返すこと。"""

    # ユーザープロンプト: 実際の動画データを提供
    user_parts = ["以下の編集済み動画のマーケティング品質をチェックしてください。\n"]

    if guest_profile:
        user_parts.append(f"## ゲストプロファイル\n{guest_profile}\n")

    if content_line:
        line_label = "不動産実績対談（ノウハウ軸）" if content_line == "realestate" else "通常のTEKO実績対談（キャリア軸）"
        user_parts.append(f"## コンテンツライン\n{line_label}\n")

    if direction_report:
        user_parts.append(f"## ディレクションレポート（編集者への指示内容）\n{direction_report}\n")

    user_parts.append("## テロップ一覧（編集済み動画から検出）")
    if telop_texts:
        for t in telop_texts:
            user_parts.append(f"- {t}")
    else:
        user_parts.append("（テロップ検出なし）")

    user_parts.append("")
    user_parts.append("## 文字起こし（発言内容）")
    # 文字起こしが長すぎる場合は先頭・末尾に絞る
    if len(transcript_text) > 15000:
        user_parts.append(transcript_text[:7500])
        user_parts.append("\n... (中略) ...\n")
        user_parts.append(transcript_text[-7500:])
    else:
        user_parts.append(transcript_text)

    user_parts.append("\n## チェック項目")
    user_parts.append("1. ハイライト選定: 冒頭ハイライトのパンチラインは「1フレーズで続きが見たくなる」か？共感・好奇心・パンチ力・逆説の4軸で判定")
    user_parts.append("2. 強調演出ポイント: テロップの強調表現はディレクションレポートの指示通りか？抽象的すぎないか？")
    user_parts.append("3. 層分類の反映: ゲストの層分類に合った演出がされているか？")
    user_parts.append("4. コンテンツラインとの整合性: キャリア軸/不動産軸に合った見せ方がされているか？")
    user_parts.append("5. NGパターン該当: セクション5のNGパターンに該当するテロップ・ハイライトがないか？")

    user_prompt = "\n".join(user_parts)

    return system_prompt, user_prompt


def _parse_llm_response(raw_response: str) -> tuple[str, str, list[dict]]:
    """LLMレスポンスからJSON部分をパースする

    Returns:
        (highlight_assessment, direction_assessment, issues_list)
    """
    # JSON部分を抽出（```json ... ``` ブロック or 生JSON）
    import re
    json_match = re.search(r'```json\s*\n?(.*?)\n?\s*```', raw_response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # 生JSONを試す
        json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            logger.warning("LLMレスポンスからJSONを抽出できませんでした")
            return "", "", []

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON解析エラー: {e}")
        return "", "", []

    highlight = data.get("highlight_assessment", "")
    direction = data.get("direction_assessment", "")
    issues = data.get("issues", [])

    return highlight, direction, issues


def run_marketing_qc(
    telop_texts: list[str],
    transcript_text: str,
    project_id: str = "",
    direction_report: str = "",
    guest_profile: str = "",
    content_line: Optional[str] = None,
    model: str = "opus",
) -> MarketingQCResult:
    """マーケティング品質QCのメイン実行

    Args:
        telop_texts: テロップテキスト一覧（「[MM:SS] テキスト」形式推奨）
        transcript_text: Whisper文字起こし全文
        project_id: プロジェクトID
        direction_report: ディレクションレポート（あれば突合する）
        guest_profile: ゲストプロファイル（あれば層分類判定に使う）
        content_line: コンテンツライン（None の場合は自動判定）
        model: 使用モデル（デフォルト: "opus" — MAX定額内）

    Returns:
        マーケティングQC結果
    """
    # コンテンツライン自動判定
    if content_line is None:
        content_line = determine_content_line(
            transcript=transcript_text,
            guest_summary=guest_profile,
        )
    logger.info(f"コンテンツライン判定: {content_line}")

    # プロンプト構築
    system_prompt, user_prompt = _build_marketing_qc_prompt(
        telop_texts=telop_texts,
        transcript_text=transcript_text,
        direction_report=direction_report,
        guest_profile=guest_profile,
        content_line=content_line,
    )

    # LLM呼び出し（teko_core.llm経由 — MAX定額内Opus）
    try:
        from teko_core.llm import ask
        raw_response = ask(
            user_prompt,
            system=system_prompt,
            model=model,
            max_tokens=4096,
            timeout=180,
        )
    except Exception as e:
        logger.error(f"マーケQC LLM呼び出しエラー: {e}")
        return MarketingQCResult(
            project_id=project_id,
            status="error",
            content_line=content_line,
            raw_llm_response=str(e),
        )

    # レスポンス解析
    highlight_assessment, direction_assessment, raw_issues = _parse_llm_response(raw_response)

    # MarketingQCIssueに変換
    issues = []
    for raw in raw_issues:
        issue = MarketingQCIssue(
            category=raw.get("category", "general"),
            severity=raw.get("severity", "warning"),
            description=raw.get("description", ""),
            suggestion=raw.get("suggestion", ""),
            timestamp_sec=raw.get("timestamp_sec", 0.0),
            timecode=raw.get("timecode", ""),
        )
        issues.append(issue)

    # 集計
    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")
    status = "passed" if error_count == 0 else "failed"

    result = MarketingQCResult(
        project_id=project_id,
        status=status,
        issues=issues,
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
        content_line=content_line,
        highlight_assessment=highlight_assessment,
        direction_assessment=direction_assessment,
        raw_llm_response=raw_response,
    )

    logger.info(
        f"マーケQC完了: {error_count}エラー, {warning_count}警告, "
        f"{info_count}情報, ステータス: {status}"
    )

    return result
