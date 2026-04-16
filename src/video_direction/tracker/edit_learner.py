from __future__ import annotations

"""手修正学習: 手修正のdiff結果からパターンを抽出し、ディレクションルールに自動反映"""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
from collections import Counter


@dataclass
class EditPattern:
    """手修正パターン"""
    id: str
    asset_type: str  # "direction" / "title" / "description" / "thumbnail"
    category: str  # "telop" / "cutting" / "color" / "bgm" / "camera" / "composition" / "tempo" / "general"
    pattern: str  # パターンの説明
    frequency: int = 1  # 出現回数
    source_edits: list = field(default_factory=list)  # 元手修正のID一覧
    confidence: float = 0.0  # 確信度 (0-1)
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class EditLearningRule:
    """手修正から生成されたルール（FeedbackLearner.LearningRuleと互換）"""
    id: str
    rule_text: str  # ルールの文言
    asset_type: str  # "direction" / "title" / "description" / "thumbnail"
    category: str  # 品質カテゴリ
    source_pattern_ids: list = field(default_factory=list)
    priority: str = "high"  # 手修正由来は基本high
    applied_count: int = 0
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class EditLearner:
    """手修正のdiff結果からパターンを抽出し、ディレクションルールに反映

    FeedbackLearnerと同じインターフェースを持つ。
    手修正は音声FBより価値が高いため、confidence閾値を低く設定:
    - confidence = frequency / 3.0（FeedbackLearnerは5.0）
    - ルール生成閾値 = 0.5（FeedbackLearnerは0.6）
    """

    # 手修正は価値が高いため、FeedbackLearnerの5.0より低い分母を使う
    CONFIDENCE_DIVISOR = 3.0
    # ルール生成の確信度閾値（FeedbackLearnerの0.6より低い）
    RULE_THRESHOLD = 0.5
    # 類似度判定のJaccard閾値
    SIMILARITY_THRESHOLD = 0.35

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path.home() / "AI開発10" / ".data" / "learning"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.patterns_path = self.data_dir / "edit_patterns.json"
        self.rules_path = self.data_dir / "edit_rules.json"
        self._patterns: dict[str, EditPattern] = {}
        self._rules: dict[str, EditLearningRule] = {}
        self._load()

    def _load(self):
        """永続化されたパターン・ルールを読み込む"""
        if self.patterns_path.exists():
            data = json.loads(self.patterns_path.read_text())
            for p in data.get("patterns", []):
                pattern = EditPattern(**p)
                self._patterns[pattern.id] = pattern
        if self.rules_path.exists():
            data = json.loads(self.rules_path.read_text())
            for r in data.get("rules", []):
                rule = EditLearningRule(**r)
                self._rules[rule.id] = rule

    def _save(self):
        """パターン・ルールを永続化"""
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

    def ingest_edit(self, project_id: str, asset_type: str, diff_result) -> dict:
        """手修正のdiff結果からパターンを抽出・蓄積する

        Args:
            project_id: プロジェクトID
            asset_type: アセットタイプ（direction / title / description / thumbnail）
            diff_result: diff結果オブジェクト。以下の属性を期待:
                - changes: list[dict] 各changeは {"type": "modify"/"add"/"remove", "content": str, "context": str} を持つ
                - edit_id: str 手修正の識別子

        Returns:
            dict: {
                "new_patterns": int,     # 新規パターン数
                "updated_patterns": int, # 更新されたパターン数
                "patterns": list,        # 抽出・更新されたパターン一覧
                "rules_generated": int,  # 今回生成されたルール数
            }
        """
        edit_id = getattr(diff_result, "edit_id", f"edit_{project_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        changes = getattr(diff_result, "changes", [])
        if not changes:
            return {"new_patterns": 0, "updated_patterns": 0, "patterns": [], "rules_generated": 0}

        new_count = 0
        updated_count = 0
        affected_patterns = []

        for change in changes:
            # changeがdictの場合とオブジェクトの場合の両方に対応
            if isinstance(change, dict):
                content = change.get("content", "")
                context = change.get("context", "")
                change_type = change.get("type", "modify")
            else:
                content = getattr(change, "content", "")
                context = getattr(change, "context", "")
                change_type = getattr(change, "type", "modify")

            if not content:
                continue

            # カテゴリ推定
            category = self._classify_edit(content, context)
            # パターン文字列の抽出
            pattern_text = self._extract_pattern(content, change_type)

            # 既存パターンとの類似度チェック
            matched = False
            for pid, pattern in self._patterns.items():
                if pattern.asset_type == asset_type and pattern.category == category:
                    if self._is_similar(pattern_text, pattern.pattern):
                        # 既存パターンの更新
                        pattern.frequency += 1
                        if edit_id not in pattern.source_edits:
                            pattern.source_edits.append(edit_id)
                        pattern.updated_at = datetime.now().isoformat()
                        # 確信度更新（手修正は価値が高いので分母3.0）
                        pattern.confidence = min(1.0, pattern.frequency / self.CONFIDENCE_DIVISOR)
                        affected_patterns.append(pattern)
                        updated_count += 1
                        matched = True
                        break

            if not matched:
                # 新規パターンの生成
                new_pattern = EditPattern(
                    id=f"epat_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self._patterns)}",
                    asset_type=asset_type,
                    category=category,
                    pattern=pattern_text,
                    source_edits=[edit_id],
                    # 初回の確信度（1/3.0 ≈ 0.33）
                    confidence=min(1.0, 1.0 / self.CONFIDENCE_DIVISOR),
                )
                self._patterns[new_pattern.id] = new_pattern
                affected_patterns.append(new_pattern)
                new_count += 1

        # 高確信度パターンからルール自動生成
        rules_before = len(self._rules)
        self._generate_rules()
        rules_generated = len(self._rules) - rules_before

        self._save()

        return {
            "new_patterns": new_count,
            "updated_patterns": updated_count,
            "patterns": [asdict(p) for p in affected_patterns],
            "rules_generated": rules_generated,
        }

    def _classify_edit(self, content: str, context: str = "") -> str:
        """手修正内容からカテゴリを推定"""
        combined = f"{content} {context}".lower()
        keywords = {
            "cutting": ["カット", "切り", "繋ぎ", "トランジション", "場面転換"],
            "color": ["色", "カラー", "明るさ", "暗い", "彩度", "色調", "フィルター"],
            "telop": ["テロップ", "字幕", "フォント", "テキスト", "文字", "サイズ"],
            "bgm": ["bgm", "音楽", "se", "効果音", "サウンド"],
            "camera": ["カメラ", "アングル", "画角", "ズーム", "パン", "寄り", "引き"],
            "composition": ["構図", "レイアウト", "配置", "フレーミング"],
            "tempo": ["テンポ", "リズム", "スピード", "間", "尺", "タイミング"],
        }
        scores = {}
        for cat, words in keywords.items():
            scores[cat] = sum(1 for w in words if w in combined)

        if max(scores.values(), default=0) > 0:
            return max(scores, key=scores.get)
        return "general"

    def _extract_pattern(self, content: str, change_type: str = "modify") -> str:
        """手修正内容からパターン（要点）を抽出"""
        text = _normalize_text(content)
        # 変更タイプに応じたプレフィックス
        prefix_map = {
            "add": "追加: ",
            "remove": "削除: ",
            "modify": "",
        }
        prefix = prefix_map.get(change_type, "")
        # 長文は100文字に切り詰め
        return f"{prefix}{text[:100].strip()}"

    def _is_similar(self, content: str, pattern: str) -> bool:
        """類似度チェック（FeedbackLearnerと同じロジック）"""
        content_norm = _normalize_text(content)
        pattern_norm = _normalize_text(pattern)
        if not content_norm or not pattern_norm:
            return False
        if content_norm == pattern_norm:
            return True

        # 長文の包含チェック
        if len(content_norm) >= 8 and (
            content_norm in pattern_norm or pattern_norm in content_norm
        ):
            return True

        # Jaccard類似度
        content_tokens = _tokenize_for_similarity(content_norm)
        pattern_tokens = _tokenize_for_similarity(pattern_norm)
        if content_tokens and pattern_tokens:
            overlap = len(content_tokens & pattern_tokens)
            jaccard = overlap / max(1, len(content_tokens | pattern_tokens))
            if jaccard >= self.SIMILARITY_THRESHOLD:
                return True

        # SequenceMatcher
        ratio = SequenceMatcher(None, content_norm, pattern_norm).ratio()
        return ratio >= 0.72

    def _generate_rules(self):
        """高確信度パターンからルールを自動生成・更新"""
        for pid, pattern in self._patterns.items():
            if pattern.confidence >= self.RULE_THRESHOLD and pattern.is_active:
                # 既存ルールがあれば更新、なければ生成
                existing_rule = None
                for r in self._rules.values():
                    if pid in r.source_pattern_ids:
                        existing_rule = r
                        break

                freq = pattern.frequency
                new_priority = "high" if pattern.confidence >= 0.8 else "medium"
                new_rule_text = f"[手修正学習] {pattern.pattern}（{freq}回の手修正から学習）"

                if existing_rule is not None:
                    # 既存ルールの優先度・テキストを更新
                    existing_rule.priority = new_priority
                    existing_rule.rule_text = new_rule_text
                else:
                    rule = EditLearningRule(
                        id=f"erule_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self._rules)}",
                        rule_text=new_rule_text,
                        asset_type=pattern.asset_type,
                        category=pattern.category,
                        source_pattern_ids=[pid],
                        priority=new_priority,
                    )
                    self._rules[rule.id] = rule

    def get_active_rules(self, asset_type: str = None, category: str = None) -> list[EditLearningRule]:
        """有効なルール一覧（ディレクション生成時に参照）

        FeedbackLearner.get_active_rules()と互換のインターフェース。
        direction_generatorの_apply_learned_rules()から呼ばれる。

        Args:
            asset_type: フィルタ用アセットタイプ（Noneなら全件）
            category: フィルタ用カテゴリ（Noneなら全件）

        Returns:
            有効なルールのリスト（優先度降順）
        """
        rules = [r for r in self._rules.values() if r.is_active]
        if asset_type:
            rules = [r for r in rules if r.asset_type == asset_type]
        if category:
            rules = [r for r in rules if r.category == category]
        return sorted(rules, key=lambda r: r.priority == "high", reverse=True)

    def get_patterns(self, asset_type: str = None, category: str = None) -> list[EditPattern]:
        """パターン一覧"""
        patterns = list(self._patterns.values())
        if asset_type:
            patterns = [p for p in patterns if p.asset_type == asset_type]
        if category:
            patterns = [p for p in patterns if p.category == category]
        return sorted(patterns, key=lambda p: p.confidence, reverse=True)

    def get_insights(self) -> dict:
        """学習状況のサマリー"""
        category_counts = Counter(p.category for p in self._patterns.values())
        asset_type_counts = Counter(p.asset_type for p in self._patterns.values())
        return {
            "total_patterns": len(self._patterns),
            "total_rules": len(self._rules),
            "active_rules": len([r for r in self._rules.values() if r.is_active]),
            "high_confidence_patterns": len(
                [p for p in self._patterns.values() if p.confidence >= self.RULE_THRESHOLD]
            ),
            "category_distribution": dict(category_counts),
            "asset_type_distribution": dict(asset_type_counts),
            "top_categories": category_counts.most_common(3),
        }


# ────────────────────────────────────────────────
# ユーティリティ関数（FeedbackLearnerと同じロジック）
# ────────────────────────────────────────────────

def _normalize_text(text: str) -> str:
    """テキストを正規化する"""
    if not text:
        return ""
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    # 文意に不要な記号を除去
    text = re.sub(r"[「」『』【】\[\]（）()、。.,!！?？:：;；/\\\-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokenize_for_similarity(text: str) -> set[str]:
    """類似度計算用のトークン化"""
    if not text:
        return set()
    tokens = {w for w in text.split(" ") if len(w) >= 2}
    dense = text.replace(" ", "")
    # 日本語文で空白がないケース向けに2-gramを追加
    if len(dense) >= 2:
        tokens.update(dense[i:i + 2] for i in range(len(dense) - 1))
    return tokens
