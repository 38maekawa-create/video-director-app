"""フレームキャプチャ + テロップ有無の前処理フィルタ

ffmpegで2秒間隔のフレームを抽出し、画像下部1/3に文字領域があるかを
軽量判定してテロップありフレームだけをフィルタリングする。
GPT-4oビジョンに投げるフレーム数を抑制し、コストを最適化。
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# opencv-python のgraceful import
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    cv2 = None
    np = None
    HAS_CV2 = False


@dataclass
class ExtractedFrame:
    """抽出されたフレーム"""
    path: Path               # 画像ファイルパス
    timestamp_sec: float     # 動画内の時刻（秒）
    has_telop: bool = False  # テロップ有無の推定結果

    @property
    def timecode(self) -> str:
        """MM:SS形式のタイムコード"""
        m, s = divmod(int(self.timestamp_sec), 60)
        return f"{m:02d}:{s:02d}"

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "timestamp_sec": self.timestamp_sec,
            "has_telop": self.has_telop,
            "timecode": self.timecode,
        }


def extract_frames(
    video_path: str | Path,
    output_dir: Optional[str | Path] = None,
    interval_sec: float = 2.0,
) -> list[ExtractedFrame]:
    """ffmpegで動画から一定間隔でフレームをキャプチャ

    Args:
        video_path: 入力動画ファイルパス
        output_dir: 出力ディレクトリ（省略時はtmpdir）
        interval_sec: キャプチャ間隔（秒）。デフォルト2秒

    Returns:
        抽出されたフレームのリスト
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"動画ファイルが見つかりません: {video_path}")

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="qc_frames_"))
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fps = 1.0 / interval_sec
    pattern = str(output_dir / "frame_%04d.jpg")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", f"fps={fps}",
        "-q:v", "2",    # JPEG品質（2=高品質）
        pattern,
    ]

    logger.info(f"フレーム抽出: {video_path} -> {output_dir} (間隔: {interval_sec}秒)")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpegフレーム抽出に失敗: {result.stderr}")

    # 出力ファイルをリスト化
    frames = []
    for i, frame_path in enumerate(sorted(output_dir.glob("frame_*.jpg"))):
        timestamp_sec = i * interval_sec
        frames.append(ExtractedFrame(
            path=frame_path,
            timestamp_sec=timestamp_sec,
        ))

    logger.info(f"フレーム抽出完了: {len(frames)}枚")
    return frames


def detect_telop_frames(
    frames: list[ExtractedFrame],
    bottom_ratio: float = 0.33,
    edge_threshold: int = 50,
    min_edge_density: float = 0.02,
) -> list[ExtractedFrame]:
    """テロップが映っている可能性の高いフレームをフィルタリング

    画像下部（bottom_ratio）の領域にエッジ（文字の輪郭）が
    一定密度以上あるフレームを「テロップあり」と判定する。
    軽量なOpenCV処理のみで、API呼び出しなし。

    Args:
        frames: 抽出済みフレームのリスト
        bottom_ratio: テロップ領域とみなす下部の割合
        edge_threshold: Cannyエッジ検出の閾値
        min_edge_density: テロップありと判定するエッジ密度の最小値

    Returns:
        テロップあり判定されたフレームのリスト
    """
    if not HAS_CV2:
        logger.warning("OpenCVが未インストール。全フレームをテロップありとして返します")
        for f in frames:
            f.has_telop = True
        return frames

    telop_frames = []

    for frame in frames:
        if not frame.path.exists():
            continue

        img = cv2.imread(str(frame.path))
        if img is None:
            continue

        h, w = img.shape[:2]

        # 下部1/3を切り出し
        bottom_region = img[int(h * (1 - bottom_ratio)):, :]

        # グレースケール変換 + エッジ検出
        gray = cv2.cvtColor(bottom_region, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, edge_threshold, edge_threshold * 2)

        # エッジ密度を計算
        edge_density = np.count_nonzero(edges) / edges.size

        if edge_density >= min_edge_density:
            frame.has_telop = True
            telop_frames.append(frame)

    logger.info(
        f"テロップフィルタリング: {len(frames)}枚中 {len(telop_frames)}枚がテロップあり"
    )
    return telop_frames


def extract_and_filter(
    video_path: str | Path,
    output_dir: Optional[str | Path] = None,
    interval_sec: float = 2.0,
    bottom_ratio: float = 0.33,
    min_edge_density: float = 0.02,
) -> tuple[list[ExtractedFrame], list[ExtractedFrame]]:
    """フレーム抽出 + テロップフィルタリングの一括処理

    Args:
        video_path: 入力動画ファイルパス
        output_dir: 出力ディレクトリ
        interval_sec: キャプチャ間隔
        bottom_ratio: テロップ領域の割合
        min_edge_density: エッジ密度閾値

    Returns:
        (全フレーム, テロップありフレーム) のタプル
    """
    all_frames = extract_frames(video_path, output_dir, interval_sec)
    telop_frames = detect_telop_frames(
        all_frames,
        bottom_ratio=bottom_ratio,
        min_edge_density=min_edge_density,
    )
    return all_frames, telop_frames
