"""Whisper APIによる音声文字起こし

動画ファイルから音声を抽出し、Whisper API (large-v3) で
タイムスタンプ付きの文字起こしを取得する。
テロップ誤字検出の「正解データ」として使用。
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    """文字起こしの1セグメント"""
    start: float       # 開始時刻（秒）
    end: float         # 終了時刻（秒）
    text: str          # 文字起こしテキスト

    @property
    def start_timecode(self) -> str:
        """MM:SS形式のタイムコード"""
        m, s = divmod(int(self.start), 60)
        return f"{m:02d}:{s:02d}"

    @property
    def end_timecode(self) -> str:
        m, s = divmod(int(self.end), 60)
        return f"{m:02d}:{s:02d}"


@dataclass
class TranscriptResult:
    """文字起こし結果"""
    segments: list[TranscriptSegment] = field(default_factory=list)
    full_text: str = ""
    language: str = "ja"
    duration: float = 0.0

    def get_text_at(self, timestamp_sec: float, window_sec: float = 3.0) -> list[TranscriptSegment]:
        """指定タイムスタンプ周辺のセグメントを取得

        Args:
            timestamp_sec: 検索対象の時刻（秒）
            window_sec: 前後の許容範囲（秒）
        """
        results = []
        for seg in self.segments:
            # セグメントの時間範囲とウィンドウが重なるか
            if seg.end >= (timestamp_sec - window_sec) and seg.start <= (timestamp_sec + window_sec):
                results.append(seg)
        return results

    def to_dict(self) -> dict:
        return {
            "segments": [
                {"start": s.start, "end": s.end, "text": s.text}
                for s in self.segments
            ],
            "full_text": self.full_text,
            "language": self.language,
            "duration": self.duration,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TranscriptResult:
        segments = [
            TranscriptSegment(start=s["start"], end=s["end"], text=s["text"])
            for s in data.get("segments", [])
        ]
        return cls(
            segments=segments,
            full_text=data.get("full_text", ""),
            language=data.get("language", "ja"),
            duration=data.get("duration", 0.0),
        )


def extract_audio(video_path: str | Path, output_path: Optional[str | Path] = None) -> Path:
    """動画ファイルから音声を抽出（ffmpeg使用）

    Args:
        video_path: 入力動画ファイルパス
        output_path: 出力音声ファイルパス（省略時はtmpfile）

    Returns:
        音声ファイルのパス
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"動画ファイルが見つかりません: {video_path}")

    if output_path is None:
        # Whisper APIは25MB制限があるので、mp3で圧縮して出力
        fd, tmp = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        output_path = Path(tmp)
    else:
        output_path = Path(output_path)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",                   # 映像を除外
        "-acodec", "libmp3lame", # MP3エンコード
        "-ar", "16000",          # 16kHz（Whisper推奨）
        "-ac", "1",              # モノラル
        "-b:a", "64k",           # 低ビットレート（ファイルサイズ抑制）
        str(output_path),
    ]

    logger.info(f"音声抽出: {video_path} -> {output_path}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg音声抽出に失敗: {result.stderr}")

    return output_path


def transcribe_with_whisper(
    audio_path: str | Path,
    language: str = "ja",
    model: str = "whisper-1",
) -> TranscriptResult:
    """Whisper APIで音声を文字起こし

    Args:
        audio_path: 音声ファイルパス
        language: 言語コード
        model: Whisperモデル名

    Returns:
        タイムスタンプ付き文字起こし結果
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai パッケージが必要です: pip install openai")

    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"音声ファイルが見つかりません: {audio_path}")

    # ファイルサイズチェック（Whisper APIは25MB制限）
    file_size_mb = audio_path.stat().st_size / (1024 * 1024)
    if file_size_mb > 25:
        logger.warning(f"音声ファイルが25MBを超えています ({file_size_mb:.1f}MB)。分割が必要な可能性あり。")

    client = OpenAI()

    logger.info(f"Whisper API呼び出し: {audio_path} ({file_size_mb:.1f}MB)")

    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model=model,
            file=f,
            language=language,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    # レスポンスからTranscriptResultを構築
    segments = []
    if hasattr(response, "segments") and response.segments:
        for seg in response.segments:
            segments.append(TranscriptSegment(
                start=seg.get("start", seg.start) if isinstance(seg, dict) else seg.start,
                end=seg.get("end", seg.end) if isinstance(seg, dict) else seg.end,
                text=(seg.get("text", "") if isinstance(seg, dict) else seg.text).strip(),
            ))

    full_text = response.text if hasattr(response, "text") else ""
    duration = response.duration if hasattr(response, "duration") else 0.0

    result = TranscriptResult(
        segments=segments,
        full_text=full_text,
        language=language,
        duration=duration,
    )

    logger.info(f"文字起こし完了: {len(segments)}セグメント, {duration:.1f}秒")
    return result


def transcribe_video(
    video_path: str | Path,
    language: str = "ja",
    cache_dir: Optional[str | Path] = None,
) -> TranscriptResult:
    """動画ファイルから文字起こしを実行（音声抽出 + Whisper API）

    Args:
        video_path: 動画ファイルパス
        language: 言語コード
        cache_dir: キャッシュディレクトリ（指定時は結果をJSON保存）

    Returns:
        タイムスタンプ付き文字起こし結果
    """
    video_path = Path(video_path)

    # キャッシュ確認
    if cache_dir:
        cache_dir = Path(cache_dir)
        cache_file = cache_dir / f"{video_path.stem}_whisper.json"
        if cache_file.exists():
            logger.info(f"キャッシュから文字起こしを読み込み: {cache_file}")
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return TranscriptResult.from_dict(data)

    # 音声抽出
    audio_path = extract_audio(video_path)

    try:
        # Whisper APIで文字起こし
        result = transcribe_with_whisper(audio_path, language=language)
    finally:
        # 一時ファイルの削除
        if audio_path.exists():
            audio_path.unlink()

    # キャッシュ保存
    if cache_dir:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{video_path.stem}_whisper.json"
        cache_file.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"キャッシュ保存: {cache_file}")

    return result
