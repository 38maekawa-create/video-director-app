from __future__ import annotations

"""トラッキング映像分析: 映像の要素分解

ルールベース分析 + LLM分析（Claude Sonnet）を組み合わせた多層分析。
VideoTrackerで取得した字幕・メタデータを入力にし、
VideoLearnerが消費できる構造化出力を生成する。
"""
import json
import os
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
    llm_analysis: str = ""  # LLMによる深掘り分析テキスト
    strengths: list = field(default_factory=list)  # この映像の強み
    weaknesses: list = field(default_factory=list)  # この映像の弱み
    learnable_patterns: list = field(default_factory=list)  # 学習すべきパターン


class VideoAnalyzer:
    """外部映像の要素分解・分析

    3層の分析を順に適用:
    1. 字幕ベース分析（テンポ・構成の推定）
    2. メタデータ分析（動画尺・タグ・チャンネル情報）
    3. LLM分析（Claude Sonnetで深掘り → 構造化パターン抽出）
    """

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
        title: str = None,
        channel_name: str = None,
        duration_seconds: float = 0.0,
        use_llm: bool = True,
    ) -> VideoAnalysisResult:
        """映像を分析して要素分解

        Args:
            video_path: ローカル映像ファイルパス（あれば）
            video_url: YouTube URL
            transcript: 字幕テキスト
            title: 動画タイトル（メタデータ取得済みの場合）
            channel_name: チャンネル名
            duration_seconds: 動画尺（秒）
            use_llm: LLM分析を実行するか（APIキーが必要）
        """
        video_id = video_url or video_path or "unknown"
        result = VideoAnalysisResult(video_id=video_id)

        # 1. 文字起こしベースの分析（映像ファイルがなくても動作）
        if transcript:
            result = self._analyze_from_transcript(result, transcript)

        # 2. 映像ファイルがある場合はフレーム分析
        if video_path and Path(video_path).exists():
            result = self._analyze_from_video(result, video_path)

        # 3. YouTube URLの場合はメタデータ分析
        if video_url:
            result = self._analyze_from_metadata(result, video_url)

        # 4. LLM分析（字幕 or メタデータがある場合）
        if use_llm and (transcript or title):
            result = self._analyze_with_llm(
                result, transcript=transcript, title=title,
                channel_name=channel_name, duration_seconds=duration_seconds,
            )

        # 5. 総合スコア算出
        result.overall_score = self._calculate_score(result)

        # 6. 分析サマリー生成（空の場合のみ）
        if not result.summary:
            result.summary = self._generate_summary(result)

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

    def _analyze_with_llm(
        self,
        result: VideoAnalysisResult,
        transcript: str = None,
        title: str = None,
        channel_name: str = None,
        duration_seconds: float = 0.0,
    ) -> VideoAnalysisResult:
        """LLM（teko_core.llm経由 — MAX定額内）で映像を深掘り分析し、構造化パターンを抽出"""
        # 字幕は先頭3000文字に制限
        transcript_excerpt = (transcript or "")[:3000]
        duration_min = int(duration_seconds / 60) if duration_seconds else 0

        prompt = f"""以下の映像情報を分析し、映像制作の観点から構造化された分析結果をJSON形式で出力してください。

## 映像情報
- タイトル: {title or '不明'}
- チャンネル: {channel_name or '不明'}
- 尺: {duration_min}分
- 既存の分析結果:
  - テンポ: {result.tempo or '未分析'}
  - 構成: {result.composition or '未分析'}
  - カット割り: {result.cutting_style or '未分析'}

## 字幕テキスト（抜粋）:
{transcript_excerpt if transcript_excerpt else '（字幕なし — メタデータのみで分析）'}

## 出力形式（JSON）:
{{
  "cutting_style": "カット割りの特徴（例: 高速カット、ロングテイク、対談標準）",
  "color_grading": "色彩・ルックの特徴",
  "tempo": "テンポの特徴",
  "composition": "構成の特徴（例: 起承転結、問題提起→解決型）",
  "key_techniques": ["テクニック1", "テクニック2", "テクニック3"],
  "strengths": ["この映像の強み1", "強み2"],
  "weaknesses": ["改善点1", "改善点2"],
  "learnable_patterns": ["TEKO対談に応用できるパターン1", "パターン2"],
  "summary": "30文字以内の要約"
}}

注意:
- TEKO対談インタビュー動画の品質向上に活かせる知見を重視
- 具体的・実践的なパターンを抽出（抽象論は不要）
- JSONのみ出力、マークダウンや説明文は不要
"""

        try:
            from teko_core.llm import ask
            raw_text = ask(prompt, model="opus", max_tokens=800, timeout=120).strip()

            # JSON部分を抽出
            parsed = self._extract_json(raw_text)
            if parsed:
                # ルールベース分析結果が空の場合のみLLM結果で埋める
                if not result.cutting_style and parsed.get("cutting_style"):
                    result.cutting_style = parsed["cutting_style"]
                if not result.color_grading and parsed.get("color_grading"):
                    result.color_grading = parsed["color_grading"]
                if not result.tempo and parsed.get("tempo"):
                    result.tempo = parsed["tempo"]
                if not result.composition and parsed.get("composition"):
                    result.composition = parsed["composition"]
                # key_techniquesは追加（重複除去）
                existing = set(result.key_techniques)
                for t in parsed.get("key_techniques", []):
                    if t not in existing:
                        result.key_techniques.append(t)
                # LLM固有フィールド
                result.strengths = parsed.get("strengths", [])
                result.weaknesses = parsed.get("weaknesses", [])
                result.learnable_patterns = parsed.get("learnable_patterns", [])
                if parsed.get("summary"):
                    result.summary = parsed["summary"]

            result.llm_analysis = raw_text

        except Exception:
            pass

        return result

    @staticmethod
    def _extract_json(text: str) -> Optional[dict]:
        """テキストからJSON部分を抽出してパース"""
        # まず全体をパース試行
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # ```json ... ``` ブロック内を試行
        import re
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # { ... } を探す
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None

    @staticmethod
    def _calculate_score(result: VideoAnalysisResult) -> float:
        """分析結果の充実度からスコアを算出（0.0〜1.0）

        実際の映像品質ではなく「分析データの充実度」を測る。
        充実した分析ほどVideoLearnerが有用なパターンを抽出しやすい。
        """
        score = 0.0
        # 各分析項目が埋まっているかで加点
        if result.cutting_style and "未分析" not in result.cutting_style:
            score += 0.15
        if result.color_grading:
            score += 0.10
        if result.tempo and "未分析" not in result.tempo:
            score += 0.15
        if result.composition:
            score += 0.15
        if result.summary:
            score += 0.05
        if result.key_techniques:
            score += min(0.15, len(result.key_techniques) * 0.03)
        if result.llm_analysis:
            score += 0.10
        if result.learnable_patterns:
            score += min(0.15, len(result.learnable_patterns) * 0.05)
        return min(1.0, round(score, 2))

    @staticmethod
    def _generate_summary(result: VideoAnalysisResult) -> str:
        """分析結果から要約文を生成"""
        parts = []
        if result.tempo:
            parts.append(result.tempo.split("—")[0].strip() if "—" in result.tempo else result.tempo)
        if result.cutting_style:
            parts.append(result.cutting_style.split("—")[0].strip() if "—" in result.cutting_style else result.cutting_style)
        if result.composition:
            parts.append(result.composition.split("—")[0].strip() if "—" in result.composition else result.composition)
        if result.key_techniques:
            parts.append(f"テクニック{len(result.key_techniques)}件")
        return "、".join(parts[:3]) if parts else "分析データなし"
