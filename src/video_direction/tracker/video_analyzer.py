"""トラッキング映像分析: 映像の要素分解"""
import json
import subprocess
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class VideoAnalysisResult:
    video_id: str
    overall_score: float = 0.0
    composition: str = ""  # 構図分析
    tempo: str = ""  # テンポ分析
    cutting_style: str = ""  # カット割り分析
    color_grading: str = ""  # 色彩分析
    audio_balance: str = ""  # 音声バランス
    key_techniques: list = field(default_factory=list)
    summary: str = ""
    frame_count: int = 0
    avg_scene_duration: float = 0.0


class VideoAnalyzer:
    """外部映像の要素分解・分析"""

    def __init__(self, cache_dir: Path = None):
        self.cache_dir = (
            cache_dir or Path.home() / "AI開発10" / ".cache" / "video_analysis"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def analyze(
        self,
        video_path: str = None,
        video_url: str = None,
        transcript: str = None,
    ) -> VideoAnalysisResult:
        """映像を分析して要素分解"""
        video_id = video_url or video_path or "unknown"
        result = VideoAnalysisResult(video_id=video_id)

        # 文字起こしベースの分析（映像ファイルがなくても動作）
        if transcript:
            result = self._analyze_from_transcript(result, transcript)

        # 映像ファイルがある場合はフレーム分析
        if video_path and Path(video_path).exists():
            result = self._analyze_from_video(result, video_path)

        # YouTube URLの場合はメタデータ分析
        if video_url:
            result = self._analyze_from_metadata(result, video_url)

        return result

    def _analyze_from_transcript(
        self, result: VideoAnalysisResult, transcript: str
    ) -> VideoAnalysisResult:
        """文字起こしからテンポ・構成を分析"""
        lines = transcript.strip().split("\n")
        result.frame_count = len(lines)

        # 話者切り替え頻度でテンポを推定
        speaker_changes = 0
        prev_speaker = None
        for line in lines:
            if ":" in line:
                speaker = line.split(":")[0].strip()
                if speaker != prev_speaker and prev_speaker is not None:
                    speaker_changes += 1
                prev_speaker = speaker

        if speaker_changes > len(lines) * 0.3:
            result.tempo = "テンポが速い — 話者切り替えが頻繁"
        elif speaker_changes > len(lines) * 0.15:
            result.tempo = "標準的なテンポ — バランスの良い対話"
        else:
            result.tempo = "ゆったりしたテンポ — じっくり語るスタイル"

        # 発言長から構成を分析
        long_segments = sum(1 for line in lines if len(line) > 100)
        if long_segments > len(lines) * 0.5:
            result.composition = "ロングトーク構成 — 深堀り型"
        else:
            result.composition = "ショートカット構成 — テンポ重視型"

        result.summary = (
            f"話者切替{speaker_changes}回、全{len(lines)}行、{result.tempo}"
        )
        return result

    def _analyze_from_video(
        self, result: VideoAnalysisResult, video_path: str
    ) -> VideoAnalysisResult:
        """映像ファイルからフレーム分析"""
        try:
            import cv2

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return result

            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0

            # シーンチェンジ検出
            scene_changes = []
            prev_frame = None
            sample_interval = max(1, int(fps))  # 1秒ごとにサンプリング

            for i in range(0, total_frames, sample_interval):
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()
                if not ret:
                    break

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if prev_frame is not None:
                    diff = cv2.absdiff(prev_frame, gray)
                    mean_diff = diff.mean()
                    if mean_diff > 30:  # シーンチェンジ閾値
                        scene_changes.append(i / fps)
                prev_frame = gray

            cap.release()

            result.frame_count = total_frames
            num_scenes = len(scene_changes) + 1
            result.avg_scene_duration = (
                duration / num_scenes if num_scenes > 0 else duration
            )

            # カット割り分析
            if result.avg_scene_duration < 3:
                result.cutting_style = (
                    "高速カット — MTV/リール風"
                    f"（平均{result.avg_scene_duration:.1f}秒/カット）"
                )
            elif result.avg_scene_duration < 8:
                result.cutting_style = (
                    "標準カット — YouTube対談標準"
                    f"（平均{result.avg_scene_duration:.1f}秒/カット）"
                )
            else:
                result.cutting_style = (
                    "ロングテイク — ドキュメンタリー風"
                    f"（平均{result.avg_scene_duration:.1f}秒/カット）"
                )

            result.key_techniques.append(
                f"シーンチェンジ{len(scene_changes)}箇所検出"
            )

            # 色彩分析（代表フレームの平均色）
            cap = cv2.VideoCapture(video_path)
            cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
            ret, mid_frame = cap.read()
            if ret:
                avg_color = mid_frame.mean(axis=(0, 1))
                b, g, r = avg_color
                if r > g and r > b:
                    result.color_grading = "暖色系 — 温かみのあるトーン"
                elif b > r and b > g:
                    result.color_grading = "寒色系 — クールなトーン"
                else:
                    result.color_grading = "ニュートラル — 自然な色合い"
            cap.release()

        except ImportError:
            result.cutting_style = "（opencv未インストール — 推定値）"
        except Exception as e:
            result.cutting_style = f"（分析エラー: {str(e)[:50]}）"

        return result

    def _analyze_from_metadata(
        self, result: VideoAnalysisResult, url: str
    ) -> VideoAnalysisResult:
        """YouTube メタデータから分析"""
        try:
            yt_dlp_cmd = "yt-dlp"
            yt_dlp_user_path = Path.home() / "Library" / "Python" / "3.9" / "bin" / "yt-dlp"
            if yt_dlp_user_path.exists():
                yt_dlp_cmd = str(yt_dlp_user_path)
            proc = subprocess.run(
                [yt_dlp_cmd, "--dump-json", "--no-download", url],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode == 0:
                meta = json.loads(proc.stdout)
                duration = meta.get("duration", 0)
                tags = meta.get("tags", [])

                if duration < 60:
                    result.key_techniques.append("ショート動画（60秒以内）")
                elif duration < 600:
                    result.key_techniques.append("ミドル動画（10分以内）")
                else:
                    result.key_techniques.append("ロング動画（10分以上）")

                if tags:
                    result.key_techniques.append(f"タグ: {', '.join(tags[:5])}")

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return result
