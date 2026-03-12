"""トラッキング映像学習: 分析結果からパターンを学習"""
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
from collections import Counter


@dataclass
class VideoPattern:
    id: str
    category: str  # "cutting" / "color" / "tempo" / "composition" / "technique"
    pattern: str  # 発見されたパターンの説明
    source_count: int = 1  # 何件の映像から導出されたか
    source_video_ids: list = field(default_factory=list)
    confidence: float = 0.0  # 確信度
    example_urls: list = field(default_factory=list)
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class VideoLearner:
    """トラッキング映像の分析結果からパターンを学習"""

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path.home() / "AI開発10" / ".data" / "learning"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.patterns_path = self.data_dir / "video_patterns.json"
        self._patterns: dict[str, VideoPattern] = {}
        self._load()

    def _load(self):
        if self.patterns_path.exists():
            data = json.loads(self.patterns_path.read_text())
            for p in data.get("patterns", []):
                pattern = VideoPattern(**p)
                self._patterns[pattern.id] = pattern

    def _save(self):
        self.patterns_path.write_text(
            json.dumps(
                {
                    "patterns": [asdict(p) for p in self._patterns.values()],
                    "updated_at": datetime.now().isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    def learn_from_analysis(
        self, video_id: str, analysis_result: dict, video_url: str = None
    ) -> list[VideoPattern]:
        """映像分析結果からパターンを抽出・学習"""
        new_patterns = []

        # カット割りパターン
        if cutting := analysis_result.get("cutting_style"):
            pattern = self._update_or_create_pattern(
                category="cutting",
                pattern_text=cutting,
                video_id=video_id,
                video_url=video_url,
            )
            new_patterns.append(pattern)

        # 色彩パターン
        if color := analysis_result.get("color_grading"):
            pattern = self._update_or_create_pattern(
                category="color",
                pattern_text=color,
                video_id=video_id,
                video_url=video_url,
            )
            new_patterns.append(pattern)

        # テンポパターン
        if tempo := analysis_result.get("tempo"):
            pattern = self._update_or_create_pattern(
                category="tempo",
                pattern_text=tempo,
                video_id=video_id,
                video_url=video_url,
            )
            new_patterns.append(pattern)

        # テクニックパターン
        for technique in analysis_result.get("key_techniques", []):
            pattern = self._update_or_create_pattern(
                category="technique",
                pattern_text=technique,
                video_id=video_id,
                video_url=video_url,
            )
            new_patterns.append(pattern)

        self._save()
        return new_patterns

    def _update_or_create_pattern(
        self,
        category: str,
        pattern_text: str,
        video_id: str,
        video_url: str = None,
    ) -> VideoPattern:
        """既存パターンの更新 or 新規作成"""
        # 類似パターンを検索
        for pid, existing in self._patterns.items():
            if existing.category == category and self._is_similar(
                pattern_text, existing.pattern
            ):
                existing.source_count += 1
                if video_id not in existing.source_video_ids:
                    existing.source_video_ids.append(video_id)
                if video_url and video_url not in existing.example_urls:
                    existing.example_urls.append(video_url)
                existing.confidence = min(1.0, existing.source_count / 5.0)
                existing.updated_at = datetime.now().isoformat()
                return existing

        # 新規作成
        new_pattern = VideoPattern(
            id=f"vpat_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self._patterns)}",
            category=category,
            pattern=pattern_text,
            source_video_ids=[video_id],
            example_urls=[video_url] if video_url else [],
            confidence=0.2,
        )
        self._patterns[new_pattern.id] = new_pattern
        return new_pattern

    def _is_similar(self, text1: str, text2: str) -> bool:
        """簡易類似度（キーワードオーバーラップ）"""
        words1 = set(
            text1.replace("—", " ").replace("（", " ").replace("）", " ").split()
        )
        words2 = set(
            text2.replace("—", " ").replace("（", " ").replace("）", " ").split()
        )
        if not words2:
            return False
        return len(words1 & words2) / len(words2) > 0.4

    def get_patterns(
        self, category: str = None, min_confidence: float = 0.0
    ) -> list[VideoPattern]:
        """学習済みパターン一覧"""
        patterns = list(self._patterns.values())
        if category:
            patterns = [p for p in patterns if p.category == category]
        patterns = [p for p in patterns if p.confidence >= min_confidence]
        return sorted(patterns, key=lambda p: p.confidence, reverse=True)

    def get_insights_for_direction(self) -> list[str]:
        """ディレクション生成時に参照する学習済みインサイト"""
        insights = []
        for pattern in self.get_patterns(min_confidence=0.4):
            if pattern.is_active:
                insights.append(
                    f"[{pattern.category}] {pattern.pattern} "
                    f"（確信度: {pattern.confidence:.0%}、{pattern.source_count}件から導出）"
                )
        return insights

    def get_summary(self) -> dict:
        """学習状況サマリー"""
        category_counts = Counter(p.category for p in self._patterns.values())
        return {
            "total_patterns": len(self._patterns),
            "high_confidence": len(
                [p for p in self._patterns.values() if p.confidence >= 0.6]
            ),
            "category_distribution": dict(category_counts),
            "total_source_videos": len(
                set(
                    vid
                    for p in self._patterns.values()
                    for vid in p.source_video_ids
                )
            ),
        }
