"""人間フィードバック学習: FB蓄積→ディレクションルール自動反映"""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
from collections import Counter


@dataclass
class FeedbackPattern:
    id: str
    category: str  # "cutting" / "color" / "telop" / "bgm" / "camera" / "composition" / "tempo"
    pattern: str  # パターンの説明
    frequency: int = 1  # 出現回数
    source_feedbacks: list = field(default_factory=list)  # 元FBのID一覧
    confidence: float = 0.0  # 確信度 (0-1)
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class LearningRule:
    id: str
    rule_text: str  # ルールの文言
    category: str  # 品質カテゴリ
    source_pattern_ids: list = field(default_factory=list)
    priority: str = "medium"  # high / medium / low
    applied_count: int = 0
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class FeedbackLearner:
    """人間のフィードバックからパターンを抽出し、ディレクションルールに反映"""

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path.home() / "AI開発10" / ".data" / "learning"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.patterns_path = self.data_dir / "feedback_patterns.json"
        self.rules_path = self.data_dir / "learning_rules.json"
        self._patterns: dict[str, FeedbackPattern] = {}
        self._rules: dict[str, LearningRule] = {}
        self._load()

    def _load(self):
        if self.patterns_path.exists():
            data = json.loads(self.patterns_path.read_text())
            for p in data.get("patterns", []):
                pattern = FeedbackPattern(**p)
                self._patterns[pattern.id] = pattern
        if self.rules_path.exists():
            data = json.loads(self.rules_path.read_text())
            for r in data.get("rules", []):
                rule = LearningRule(**r)
                self._rules[rule.id] = rule

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
        self.rules_path.write_text(
            json.dumps(
                {
                    "rules": [asdict(r) for r in self._rules.values()],
                    "updated_at": datetime.now().isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    def ingest_feedback(
        self,
        feedback_id: str,
        content: str,
        category: str = None,
        created_by: str = None,
    ) -> list[FeedbackPattern]:
        """フィードバックを取り込み、パターンを抽出"""
        # カテゴリ推定（キーワードベース）
        if not category:
            category = self._classify_feedback(content)

        # 既存パターンとのマッチング
        matched_patterns = []
        for pid, pattern in self._patterns.items():
            if pattern.category == category and self._is_similar(
                content, pattern.pattern
            ):
                pattern.frequency += 1
                pattern.source_feedbacks.append(feedback_id)
                pattern.updated_at = datetime.now().isoformat()
                # 確信度更新（頻度ベース）
                pattern.confidence = min(1.0, pattern.frequency / 5.0)
                matched_patterns.append(pattern)

        # 新規パターンの生成
        if not matched_patterns:
            new_pattern = FeedbackPattern(
                id=f"pat_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self._patterns)}",
                category=category,
                pattern=self._extract_pattern(content),
                source_feedbacks=[feedback_id],
                confidence=0.2,
            )
            self._patterns[new_pattern.id] = new_pattern
            matched_patterns.append(new_pattern)

        # 高確信度パターンからルール自動生成
        self._generate_rules()
        self._save()
        return matched_patterns

    def _classify_feedback(self, content: str) -> str:
        """FBの内容からカテゴリを推定"""
        keywords = {
            "cutting": ["カット", "切り", "繋ぎ", "トランジション", "場面転換"],
            "color": ["色", "カラー", "明るさ", "暗い", "彩度", "色調"],
            "telop": ["テロップ", "字幕", "フォント", "テキスト", "文字"],
            "bgm": ["BGM", "音楽", "SE", "効果音", "サウンド"],
            "camera": ["カメラ", "アングル", "画角", "ズーム", "パン"],
            "composition": ["構図", "レイアウト", "配置", "フレーミング"],
            "tempo": ["テンポ", "リズム", "スピード", "間", "尺"],
        }
        scores = {}
        for cat, words in keywords.items():
            scores[cat] = sum(1 for w in words if w in content)

        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        return "general"

    def _is_similar(self, content: str, pattern: str) -> bool:
        """類似度チェック（日本語文を考慮したトークン + 文字列類似度）"""
        content_norm = _normalize_text(content)
        pattern_norm = _normalize_text(pattern)
        if not content_norm or not pattern_norm:
            return False
        if content_norm == pattern_norm:
            return True

        # 長文の包含は同一意図として扱う
        if len(content_norm) >= 8 and (
            content_norm in pattern_norm or pattern_norm in content_norm
        ):
            return True

        content_tokens = _tokenize_for_similarity(content_norm)
        pattern_tokens = _tokenize_for_similarity(pattern_norm)
        if content_tokens and pattern_tokens:
            overlap = len(content_tokens & pattern_tokens)
            jaccard = overlap / max(1, len(content_tokens | pattern_tokens))
            if jaccard >= 0.35:
                return True

        ratio = SequenceMatcher(None, content_norm, pattern_norm).ratio()
        return ratio >= 0.72

    def _extract_pattern(self, content: str) -> str:
        """FBからパターン（要点）を抽出"""
        # 長文の場合は最初の100文字
        return _normalize_text(content)[:100].strip()

    def _generate_rules(self):
        """高確信度パターンからルールを自動生成"""
        for pid, pattern in self._patterns.items():
            if pattern.confidence >= 0.6 and pattern.is_active:
                # 既存ルールがなければ生成
                rule_exists = any(
                    pid in r.source_pattern_ids for r in self._rules.values()
                )
                if not rule_exists:
                    rule = LearningRule(
                        id=f"rule_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self._rules)}",
                        rule_text=f"[{pattern.category}] {pattern.pattern}",
                        category=pattern.category,
                        source_pattern_ids=[pid],
                        priority="high" if pattern.confidence >= 0.8 else "medium",
                    )
                    self._rules[rule.id] = rule

    def get_active_rules(self, category: str = None) -> list[LearningRule]:
        """有効なルール一覧（ディレクション生成時に参照）"""
        rules = [r for r in self._rules.values() if r.is_active]
        if category:
            rules = [r for r in rules if r.category == category]
        return sorted(rules, key=lambda r: r.priority == "high", reverse=True)

    def get_patterns(self, category: str = None) -> list[FeedbackPattern]:
        """パターン一覧"""
        patterns = list(self._patterns.values())
        if category:
            patterns = [p for p in patterns if p.category == category]
        return sorted(patterns, key=lambda p: p.confidence, reverse=True)

    def get_insights(self) -> dict:
        """学習状況のサマリー"""
        category_counts = Counter(p.category for p in self._patterns.values())
        return {
            "total_patterns": len(self._patterns),
            "total_rules": len(self._rules),
            "active_rules": len([r for r in self._rules.values() if r.is_active]),
            "high_confidence_patterns": len(
                [p for p in self._patterns.values() if p.confidence >= 0.6]
            ),
            "category_distribution": dict(category_counts),
            "top_categories": category_counts.most_common(3),
        }


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    # 文意に不要な記号を除去
    text = re.sub(r"[「」『』【】\[\]（）()、。.,!！?？:：;；/\\\-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokenize_for_similarity(text: str) -> set[str]:
    if not text:
        return set()
    tokens = {w for w in text.split(" ") if len(w) >= 2}
    dense = text.replace(" ", "")
    # 日本語文で空白がないケース向けに2-gramを追加
    if len(dense) >= 2:
        tokens.update(dense[i:i + 2] for i in range(len(dense) - 1))
    return tokens
