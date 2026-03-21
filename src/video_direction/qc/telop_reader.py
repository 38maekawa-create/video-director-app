"""GPT-4oビジョンによるテロップテキスト読み取り

テロップが映っているフレーム画像をGPT-4o Vision APIに投げ、
テロップのテキスト内容を読み取る。
OCRは精度不足のため不採用（AI開発3での実績に基づく判断）。
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .frame_extractor import ExtractedFrame

logger = logging.getLogger(__name__)


@dataclass
class TelopReading:
    """1フレームから読み取ったテロップ情報"""
    timestamp_sec: float       # 動画内の時刻（秒）
    timecode: str              # MM:SS形式
    telop_texts: list[str]     # 読み取ったテロップテキスト（複数行対応）
    has_telop: bool = True     # テロップの有無（GPT-4o判定）
    confidence: str = "high"   # 読み取り信頼度: high / medium / low
    raw_response: str = ""     # GPT-4oの生レスポンス

    def to_dict(self) -> dict:
        return {
            "timestamp_sec": self.timestamp_sec,
            "timecode": self.timecode,
            "telop_texts": self.telop_texts,
            "has_telop": self.has_telop,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TelopReading:
        return cls(
            timestamp_sec=data["timestamp_sec"],
            timecode=data["timecode"],
            telop_texts=data["telop_texts"],
            has_telop=data.get("has_telop", True),
            confidence=data.get("confidence", "high"),
        )


@dataclass
class TelopReadResult:
    """全フレームのテロップ読み取り結果"""
    readings: list[TelopReading] = field(default_factory=list)
    total_frames: int = 0
    telop_frames: int = 0

    def to_dict(self) -> dict:
        return {
            "readings": [r.to_dict() for r in self.readings],
            "total_frames": self.total_frames,
            "telop_frames": self.telop_frames,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TelopReadResult:
        return cls(
            readings=[TelopReading.from_dict(r) for r in data.get("readings", [])],
            total_frames=data.get("total_frames", 0),
            telop_frames=data.get("telop_frames", 0),
        )


def _encode_image_base64(image_path: Path) -> str:
    """画像をbase64エンコード"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# GPT-4oに送るプロンプト
TELOP_READ_PROMPT = """この動画のフレーム画像を見て、テロップ（字幕・テキスト）を読み取ってください。

以下のルールに従ってください:
1. 画面に表示されているテロップテキストを正確に読み取ってください
2. テロップが複数行ある場合は、各行を別々に返してください
3. テロップが映っていない場合は has_telop: false を返してください
4. 装飾やフォントの影響で読みにくい文字がある場合は、最も可能性が高い読みを返し、confidence を "low" にしてください
5. ナビゲーションバーやロゴなどの固定UI要素はテロップとして扱わないでください

回答は必ず以下のJSON形式で返してください:
{
    "has_telop": true/false,
    "telop_texts": ["テロップ1行目", "テロップ2行目"],
    "confidence": "high" / "medium" / "low"
}"""


def read_telop_single(
    frame: ExtractedFrame,
    model: str = "gpt-4o",
) -> TelopReading:
    """1フレームからテロップテキストを読み取り

    Args:
        frame: 抽出済みフレーム
        model: 使用するOpenAIモデル

    Returns:
        テロップ読み取り結果
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai パッケージが必要です: pip install openai")

    if not frame.path.exists():
        return TelopReading(
            timestamp_sec=frame.timestamp_sec,
            timecode=frame.timecode,
            telop_texts=[],
            has_telop=False,
            confidence="low",
        )

    client = OpenAI()

    base64_image = _encode_image_base64(frame.path)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": TELOP_READ_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                            "detail": "high",
                        },
                    },
                ],
            }
        ],
        max_tokens=500,
        temperature=0,
    )

    raw_text = response.choices[0].message.content or ""

    # JSONパース
    telop_texts = []
    has_telop = False
    confidence = "high"

    try:
        # JSONブロックを抽出（```json ... ``` にも対応）
        json_str = raw_text
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]

        parsed = json.loads(json_str.strip())
        has_telop = parsed.get("has_telop", False)
        telop_texts = parsed.get("telop_texts", [])
        confidence = parsed.get("confidence", "high")
    except (json.JSONDecodeError, IndexError):
        logger.warning(f"GPT-4oレスポンスのJSONパースに失敗: {raw_text[:200]}")
        # フォールバック: テキストをそのまま使用
        if raw_text.strip():
            telop_texts = [raw_text.strip()]
            has_telop = True
            confidence = "low"

    return TelopReading(
        timestamp_sec=frame.timestamp_sec,
        timecode=frame.timecode,
        telop_texts=telop_texts,
        has_telop=has_telop,
        confidence=confidence,
        raw_response=raw_text,
    )


def read_telops_batch(
    frames: list[ExtractedFrame],
    model: str = "gpt-4o",
    max_frames: int = 100,
) -> TelopReadResult:
    """複数フレームからテロップを一括読み取り

    Args:
        frames: テロップありと判定されたフレームのリスト
        model: 使用するOpenAIモデル
        max_frames: 処理する最大フレーム数（コスト制御）

    Returns:
        全フレームの読み取り結果
    """
    # コスト制御: フレーム数上限
    if len(frames) > max_frames:
        logger.warning(
            f"フレーム数が上限を超えています ({len(frames)} > {max_frames})。"
            f"均等サンプリングで{max_frames}枚に削減します"
        )
        step = len(frames) / max_frames
        frames = [frames[int(i * step)] for i in range(max_frames)]

    readings = []
    total = len(frames)

    for i, frame in enumerate(frames):
        logger.info(f"テロップ読み取り: {i + 1}/{total} ({frame.timecode})")
        try:
            reading = read_telop_single(frame, model=model)
            readings.append(reading)
        except Exception as e:
            logger.error(f"テロップ読み取りエラー ({frame.timecode}): {e}")
            readings.append(TelopReading(
                timestamp_sec=frame.timestamp_sec,
                timecode=frame.timecode,
                telop_texts=[],
                has_telop=False,
                confidence="low",
            ))

    telop_count = sum(1 for r in readings if r.has_telop)

    return TelopReadResult(
        readings=readings,
        total_frames=total,
        telop_frames=telop_count,
    )
