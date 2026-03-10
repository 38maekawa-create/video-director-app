from __future__ import annotations
"""B-3: 編集者別スキルマトリクス

各編集者の得意/苦手を数値化し、タスクアサイン時の最適マッチング提案と
成長推移記録を提供する。

スキルの次元はB-1の7要素品質スコアに対応:
カット割り、色彩、テロップ、BGM、カメラワーク、構図、テンポ
"""

import json
from datetime import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# スキル次元（B-1の7要素と対応）
SKILL_DIMENSIONS = [
    "cut",          # カット割り
    "color",        # 色彩
    "telop",        # テロップ
    "bgm",          # BGM
    "camera",       # カメラワーク
    "composition",  # 構図
    "tempo",        # テンポ
]

SKILL_LABELS = {
    "cut": "カット割り",
    "color": "色彩",
    "telop": "テロップ",
    "bgm": "BGM",
    "camera": "カメラワーク",
    "composition": "構図",
    "tempo": "テンポ",
}

# デフォルトのデータ保存先
DEFAULT_DATA_DIR = Path.home() / "TEKO" / "knowledge" / "raw-data" / "video-direction"
DEFAULT_SKILL_FILE = "skill_matrix.json"


@dataclass
class SkillSnapshot:
    """スキルスナップショット（特定時点のスキル値）"""
    timestamp: str  # ISO形式
    scores: dict = field(default_factory=dict)  # {dimension: score(0-100)}
    overall: float = 0.0
    source_video_id: str = ""  # スコアの元になった動画ID
    notes: str = ""


@dataclass
class EditorProfile:
    """編集者のプロファイル"""
    editor_id: str  # ユニークID（名前ベース）
    name: str
    created_at: str
    updated_at: str
    current_skills: dict = field(default_factory=dict)  # {dimension: score(0-100)}
    skill_history: list = field(default_factory=list)  # List[SkillSnapshot]
    strengths: list = field(default_factory=list)  # 得意領域
    weaknesses: list = field(default_factory=list)  # 苦手領域
    total_videos: int = 0  # 担当動画数
    average_score: float = 0.0  # 平均品質スコア

    def update_skills(self, dimension_scores: dict, video_id: str = ""):
        """新しいスコアでスキルを更新（指数移動平均）"""
        now = datetime.now().isoformat()
        alpha = 0.3  # 新しいスコアの重み（0.0-1.0）

        for dim in SKILL_DIMENSIONS:
            new_score = dimension_scores.get(dim, 0)
            if dim in self.current_skills:
                # 指数移動平均で更新
                old_score = self.current_skills[dim]
                self.current_skills[dim] = round(
                    alpha * new_score + (1 - alpha) * old_score, 1
                )
            else:
                self.current_skills[dim] = new_score

        # スナップショット記録
        self.skill_history.append(SkillSnapshot(
            timestamp=now,
            scores=dict(self.current_skills),
            overall=self._calc_overall(),
            source_video_id=video_id,
        ))

        # 得意/苦手の更新
        self._update_strengths_weaknesses()
        self.total_videos += 1
        self.average_score = self._calc_overall()
        self.updated_at = now

    def _calc_overall(self) -> float:
        """総合スコアを計算"""
        if not self.current_skills:
            return 0.0
        return round(
            sum(self.current_skills.values()) / len(self.current_skills), 1
        )

    def _update_strengths_weaknesses(self):
        """得意/苦手領域を更新"""
        if not self.current_skills:
            return

        sorted_skills = sorted(
            self.current_skills.items(), key=lambda x: x[1], reverse=True
        )

        # 上位2つが得意、下位2つが苦手
        self.strengths = [
            SKILL_LABELS.get(dim, dim) for dim, _ in sorted_skills[:2]
        ]
        self.weaknesses = [
            SKILL_LABELS.get(dim, dim) for dim, _ in sorted_skills[-2:]
        ]


@dataclass
class TaskMatch:
    """タスクマッチング結果"""
    editor_id: str
    editor_name: str
    match_score: float  # マッチ度（0-100）
    match_reason: str  # マッチ理由
    strengths_match: list = field(default_factory=list)  # このタスクに合う強み
    growth_opportunity: list = field(default_factory=list)  # 成長機会


class SkillMatrix:
    """編集者別スキルマトリクス

    各編集者のスキルを記録・追跡し、
    タスクアサイン時の最適マッチングを提案する。
    """

    def __init__(self, data_dir: Optional[str | Path] = None):
        """初期化"""
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.data_file = self.data_dir / DEFAULT_SKILL_FILE
        self.editors: dict = {}  # {editor_id: EditorProfile}
        self._load()

    def _load(self):
        """データファイルから読み込み"""
        if self.data_file.exists():
            try:
                data = json.loads(self.data_file.read_text(encoding="utf-8"))
                for eid, ed_data in data.get("editors", {}).items():
                    history = [
                        SkillSnapshot(**s) for s in ed_data.get("skill_history", [])
                    ]
                    self.editors[eid] = EditorProfile(
                        editor_id=ed_data["editor_id"],
                        name=ed_data["name"],
                        created_at=ed_data["created_at"],
                        updated_at=ed_data["updated_at"],
                        current_skills=ed_data.get("current_skills", {}),
                        skill_history=history,
                        strengths=ed_data.get("strengths", []),
                        weaknesses=ed_data.get("weaknesses", []),
                        total_videos=ed_data.get("total_videos", 0),
                        average_score=ed_data.get("average_score", 0.0),
                    )
            except (json.JSONDecodeError, KeyError, TypeError):
                self.editors = {}

    def _save(self):
        """データファイルに保存"""
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "editors": {},
        }
        for eid, profile in self.editors.items():
            data["editors"][eid] = {
                "editor_id": profile.editor_id,
                "name": profile.name,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
                "current_skills": profile.current_skills,
                "skill_history": [asdict(s) for s in profile.skill_history],
                "strengths": profile.strengths,
                "weaknesses": profile.weaknesses,
                "total_videos": profile.total_videos,
                "average_score": profile.average_score,
            }
        self.data_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def update_editor_skills(
        self,
        editor_name: str,
        dimension_scores: dict,
        video_id: str = "",
    ) -> EditorProfile:
        """編集者のスキルを更新する

        Args:
            editor_name: 編集者名
            dimension_scores: 各次元のスコア {dimension: score}
            video_id: スコアの元になった動画ID

        Returns:
            EditorProfile: 更新された編集者プロファイル
        """
        editor_id = _normalize_editor_id(editor_name)
        now = datetime.now().isoformat()

        if editor_id not in self.editors:
            self.editors[editor_id] = EditorProfile(
                editor_id=editor_id,
                name=editor_name,
                created_at=now,
                updated_at=now,
            )

        profile = self.editors[editor_id]
        profile.update_skills(dimension_scores, video_id)
        self._save()

        return profile

    def get_editor(self, editor_name: str) -> Optional[EditorProfile]:
        """編集者プロファイルを取得"""
        editor_id = _normalize_editor_id(editor_name)
        return self.editors.get(editor_id)

    def get_all_editors(self) -> list:
        """全編集者プロファイルを取得（スコア降順）"""
        return sorted(
            self.editors.values(),
            key=lambda e: e.average_score,
            reverse=True,
        )

    def suggest_best_editor(
        self,
        required_skills: dict,
        exclude_editors: list = None,
    ) -> list:
        """タスクに最適な編集者を提案する

        Args:
            required_skills: タスクに必要なスキル {dimension: importance(0-100)}
            exclude_editors: 除外する編集者名リスト

        Returns:
            list[TaskMatch]: マッチング結果（マッチ度降順）
        """
        exclude_ids = set()
        if exclude_editors:
            exclude_ids = {_normalize_editor_id(n) for n in exclude_editors}

        matches = []
        for profile in self.editors.values():
            if profile.editor_id in exclude_ids:
                continue
            if not profile.current_skills:
                continue

            match = _calculate_match(profile, required_skills)
            matches.append(match)

        return sorted(matches, key=lambda m: m.match_score, reverse=True)

    def get_skill_growth(self, editor_name: str) -> list:
        """編集者のスキル成長推移を取得

        Returns:
            list[dict]: [{"timestamp": "...", "overall": 70.0, "scores": {...}}]
        """
        editor_id = _normalize_editor_id(editor_name)
        profile = self.editors.get(editor_id)
        if not profile:
            return []

        return [
            {
                "timestamp": s.timestamp,
                "overall": s.overall,
                "scores": s.scores,
                "video_id": s.source_video_id,
            }
            for s in profile.skill_history
        ]

    def get_skill_comparison(self) -> dict:
        """全編集者のスキル比較表を生成

        Returns:
            dict: {
                "dimensions": ["カット割り", ...],
                "editors": [{"name": "...", "scores": [70, 80, ...]}],
            }
        """
        dimensions = [SKILL_LABELS[d] for d in SKILL_DIMENSIONS]
        editors_data = []

        for profile in self.get_all_editors():
            scores = [
                profile.current_skills.get(dim, 0)
                for dim in SKILL_DIMENSIONS
            ]
            editors_data.append({
                "name": profile.name,
                "scores": scores,
                "overall": profile.average_score,
            })

        return {
            "dimensions": dimensions,
            "editors": editors_data,
        }

    def clear_all(self):
        """全データをクリア（テスト用）"""
        self.editors = {}
        if self.data_file.exists():
            self.data_file.unlink()


def _normalize_editor_id(name: str) -> str:
    """編集者名からIDを生成"""
    return name.strip().lower().replace(" ", "_").replace("　", "_")


def _calculate_match(profile: EditorProfile, required_skills: dict) -> TaskMatch:
    """マッチ度を計算"""
    if not required_skills:
        return TaskMatch(
            editor_id=profile.editor_id,
            editor_name=profile.name,
            match_score=profile.average_score,
            match_reason="一般的なスキルレベルに基づく",
        )

    weighted_sum = 0
    weight_total = 0
    strengths_match = []
    growth_opp = []

    for dim, importance in required_skills.items():
        if dim not in SKILL_DIMENSIONS:
            continue
        editor_score = profile.current_skills.get(dim, 50)
        weighted_sum += editor_score * (importance / 100)
        weight_total += importance / 100

        dim_label = SKILL_LABELS.get(dim, dim)
        if editor_score >= 75:
            strengths_match.append(f"{dim_label}（{editor_score}点）")
        elif editor_score < 60:
            growth_opp.append(f"{dim_label}（{editor_score}点）")

    match_score = weighted_sum / weight_total if weight_total > 0 else 0
    match_score = round(match_score, 1)

    reason_parts = []
    if strengths_match:
        reason_parts.append(f"強み: {', '.join(strengths_match[:2])}")
    if growth_opp:
        reason_parts.append(f"成長機会: {', '.join(growth_opp[:2])}")
    reason = " / ".join(reason_parts) if reason_parts else "データ不足"

    return TaskMatch(
        editor_id=profile.editor_id,
        editor_name=profile.name,
        match_score=match_score,
        match_reason=reason,
        strengths_match=strengths_match,
        growth_opportunity=growth_opp,
    )
