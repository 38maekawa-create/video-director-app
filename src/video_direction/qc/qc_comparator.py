"""テロップ正確性チェック（突合エンジン）

Whisper文字起こし（正解データ）とGPT-4oビジョン読み取り（テロップ実物）を
突合し、不一致箇所をフラグする。
"""

from __future__ import annotations

import difflib
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from .whisper_transcriber import TranscriptResult, TranscriptSegment
from .telop_reader import TelopReadResult, TelopReading

logger = logging.getLogger(__name__)


@dataclass
class QCIssue:
    """QCで検出された問題"""
    timestamp_sec: float
    timecode: str
    issue_type: str          # "typo" | "missing_text" | "extra_text" | "mismatch"
    severity: str            # "error" | "warning" | "info"
    spoken_text: str         # Whisper文字起こし（正解）
    telop_text: str          # テロップの実テキスト
    description: str         # 問題の説明
    similarity: float = 0.0  # テキスト類似度 (0.0〜1.0)

    def to_dict(self) -> dict:
        return {
            "timestamp_sec": self.timestamp_sec,
            "timecode": self.timecode,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "spoken_text": self.spoken_text,
            "telop_text": self.telop_text,
            "description": self.description,
            "similarity": round(self.similarity, 3),
        }

    @classmethod
    def from_dict(cls, data: dict) -> QCIssue:
        return cls(**data)


@dataclass
class QCResult:
    """QC突合の結果"""
    project_id: str = ""
    video_path: str = ""
    issues: list[QCIssue] = field(default_factory=list)
    total_telop_frames: int = 0
    checked_frames: int = 0
    error_count: int = 0
    warning_count: int = 0
    status: str = "pending"  # "pending" | "passed" | "failed"

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "video_path": self.video_path,
            "issues": [i.to_dict() for i in self.issues],
            "total_telop_frames": self.total_telop_frames,
            "checked_frames": self.checked_frames,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> QCResult:
        issues = [QCIssue.from_dict(i) for i in data.get("issues", [])]
        return cls(
            project_id=data.get("project_id", ""),
            video_path=data.get("video_path", ""),
            issues=issues,
            total_telop_frames=data.get("total_telop_frames", 0),
            checked_frames=data.get("checked_frames", 0),
            error_count=data.get("error_count", 0),
            warning_count=data.get("warning_count", 0),
            status=data.get("status", "pending"),
        )


def _normalize_text(text: str) -> str:
    """テキストを正規化して比較しやすくする

    - 全角/半角統一（NFKC）
    - 句読点・記号を除去
    - スペース除去
    - 小文字化
    """
    text = unicodedata.normalize("NFKC", text)
    # 句読点・記号を除去
    text = re.sub(r'[、。！？!?.,\s　…「」『』【】（）()]', '', text)
    return text.lower().strip()


def _compute_similarity(text1: str, text2: str) -> float:
    """2つのテキストの類似度を計算 (0.0〜1.0)"""
    if not text1 and not text2:
        return 1.0
    if not text1 or not text2:
        return 0.0

    norm1 = _normalize_text(text1)
    norm2 = _normalize_text(text2)

    if norm1 == norm2:
        return 1.0

    return difflib.SequenceMatcher(None, norm1, norm2).ratio()


def _find_differences(spoken: str, telop: str) -> str:
    """正解テキストとテロップの具体的な差分を説明"""
    norm_spoken = _normalize_text(spoken)
    norm_telop = _normalize_text(telop)

    if norm_spoken == norm_telop:
        return "正規化後は一致（句読点・記号の差異のみ）"

    # 文字単位のdiff
    matcher = difflib.SequenceMatcher(None, norm_spoken, norm_telop)
    diffs = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            diffs.append(f"「{norm_spoken[i1:i2]}」→「{norm_telop[j1:j2]}」")
        elif tag == "delete":
            diffs.append(f"「{norm_spoken[i1:i2]}」が脱落")
        elif tag == "insert":
            diffs.append(f"「{norm_telop[j1:j2]}」が余分")

    return "、".join(diffs) if diffs else "不明な差異"


def compare_single(
    reading: TelopReading,
    transcript: TranscriptResult,
    similarity_threshold: float = 0.7,
    time_window_sec: float = 3.0,
) -> list[QCIssue]:
    """1フレームのテロップと文字起こしを突合

    Args:
        reading: GPT-4oビジョンのテロップ読み取り結果
        transcript: Whisper文字起こし結果
        similarity_threshold: 類似度がこの値未満なら不一致フラグ
        time_window_sec: タイムスタンプ突合の許容範囲（秒）

    Returns:
        検出された問題のリスト
    """
    issues = []

    if not reading.has_telop or not reading.telop_texts:
        return issues

    # テロップのタイムスタンプ周辺のWhisperセグメントを取得
    nearby_segments = transcript.get_text_at(
        reading.timestamp_sec,
        window_sec=time_window_sec,
    )

    if not nearby_segments:
        # Whisperに該当セグメントがない → テロップが発言と対応しない可能性
        # （BGMテロップ等の場合もあるのでwarning止まり）
        for telop_text in reading.telop_texts:
            issues.append(QCIssue(
                timestamp_sec=reading.timestamp_sec,
                timecode=reading.timecode,
                issue_type="extra_text",
                severity="warning",
                spoken_text="（該当する発言なし）",
                telop_text=telop_text,
                description=f"テロップ「{telop_text}」に対応する発言が見つかりません",
                similarity=0.0,
            ))
        return issues

    # 各テロップテキストについて、最も近い発言セグメントと突合
    spoken_combined = " ".join(seg.text for seg in nearby_segments)

    for telop_text in reading.telop_texts:
        # 個別セグメントとの最良マッチを探す
        best_similarity = 0.0
        best_segment_text = spoken_combined

        for seg in nearby_segments:
            sim = _compute_similarity(seg.text, telop_text)
            if sim > best_similarity:
                best_similarity = sim
                best_segment_text = seg.text

        # 結合テキストとの比較も行い、高い方を採用
        combined_sim = _compute_similarity(spoken_combined, telop_text)
        if combined_sim > best_similarity:
            best_similarity = combined_sim
            best_segment_text = spoken_combined

        if best_similarity >= 0.95:
            # ほぼ完全一致 → 問題なし
            continue
        elif best_similarity >= similarity_threshold:
            # 部分一致 → 誤字の可能性
            diff_desc = _find_differences(best_segment_text, telop_text)
            issues.append(QCIssue(
                timestamp_sec=reading.timestamp_sec,
                timecode=reading.timecode,
                issue_type="typo",
                severity="error",
                spoken_text=best_segment_text,
                telop_text=telop_text,
                description=f"誤字の可能性: {diff_desc}",
                similarity=best_similarity,
            ))
        else:
            # 類似度低 → 大きな乖離
            issues.append(QCIssue(
                timestamp_sec=reading.timestamp_sec,
                timecode=reading.timecode,
                issue_type="mismatch",
                severity="error",
                spoken_text=best_segment_text,
                telop_text=telop_text,
                description=f"発言とテロップが大きく乖離 (類似度: {best_similarity:.1%})",
                similarity=best_similarity,
            ))

    return issues


def run_qc_comparison(
    transcript: TranscriptResult,
    telop_result: TelopReadResult,
    project_id: str = "",
    video_path: str = "",
    similarity_threshold: float = 0.7,
    time_window_sec: float = 3.0,
) -> QCResult:
    """テロップQC突合のメイン処理

    Args:
        transcript: Whisper文字起こし結果
        telop_result: GPT-4oテロップ読み取り結果
        project_id: プロジェクトID
        video_path: 動画ファイルパス
        similarity_threshold: 類似度閾値
        time_window_sec: タイムスタンプ許容範囲

    Returns:
        QC結果
    """
    all_issues = []
    checked = 0

    for reading in telop_result.readings:
        if not reading.has_telop:
            continue

        checked += 1
        issues = compare_single(
            reading,
            transcript,
            similarity_threshold=similarity_threshold,
            time_window_sec=time_window_sec,
        )
        all_issues.extend(issues)

    error_count = sum(1 for i in all_issues if i.severity == "error")
    warning_count = sum(1 for i in all_issues if i.severity == "warning")

    status = "passed" if error_count == 0 else "failed"

    result = QCResult(
        project_id=project_id,
        video_path=video_path,
        issues=all_issues,
        total_telop_frames=telop_result.telop_frames,
        checked_frames=checked,
        error_count=error_count,
        warning_count=warning_count,
        status=status,
    )

    logger.info(
        f"QC完了: {checked}フレーム検査, "
        f"{error_count}エラー, {warning_count}警告, "
        f"ステータス: {status}"
    )

    return result
