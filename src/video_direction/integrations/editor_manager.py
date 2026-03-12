"""編集者管理: 名簿・スキル・工程・実績の統合管理"""
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class EditorProfile:
    id: str
    name: str
    contact_info: str = ""
    status: str = "active"        # active / inactive / on_leave
    contract_type: str = "freelance"  # fulltime / freelance
    specialties: list = field(default_factory=list)  # 得意分野
    skills: dict = field(default_factory=dict)  # 7要素スキル {cutting: 75, color: 80, ...}
    active_projects: list = field(default_factory=list)  # 担当中の案件ID
    completed_count: int = 0
    avg_quality_score: float = 0.0
    capacity: int = 3             # 同時担当可能数
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class EditorManager:
    """編集者の統合管理"""

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path.home() / "AI開発10" / ".data" / "editors"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.data_dir / "editors.json"
        self._editors: dict[str, EditorProfile] = {}
        self._load()

    def _load(self):
        if self.index_path.exists():
            data = json.loads(self.index_path.read_text())
            for e in data.get("editors", []):
                editor = EditorProfile(**e)
                self._editors[editor.id] = editor

    def _save(self):
        self.index_path.write_text(json.dumps(
            {"editors": [asdict(e) for e in self._editors.values()],
             "updated_at": datetime.now().isoformat()},
            ensure_ascii=False, indent=2))

    def add_editor(self, name: str, contact_info: str = "",
                   contract_type: str = "freelance", **kwargs) -> EditorProfile:
        editor_id = f"editor_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self._editors)}"
        editor = EditorProfile(
            id=editor_id, name=name, contact_info=contact_info,
            contract_type=contract_type, **kwargs
        )
        self._editors[editor_id] = editor
        self._save()
        return editor

    def update_editor(self, editor_id: str, **kwargs) -> Optional[EditorProfile]:
        if editor_id not in self._editors:
            return None
        editor = self._editors[editor_id]
        for key, value in kwargs.items():
            if hasattr(editor, key):
                setattr(editor, key, value)
        editor.updated_at = datetime.now().isoformat()
        self._save()
        return editor

    def get_editor(self, editor_id: str) -> Optional[EditorProfile]:
        return self._editors.get(editor_id)

    def list_editors(self, status: str = None) -> list[EditorProfile]:
        editors = list(self._editors.values())
        if status:
            editors = [e for e in editors if e.status == status]
        return sorted(editors, key=lambda e: e.name)

    def remove_editor(self, editor_id: str) -> bool:
        if editor_id in self._editors:
            del self._editors[editor_id]
            self._save()
            return True
        return False

    def update_skills(self, editor_id: str, project_scores: dict):
        """プロジェクト完了時にスキルを更新（指数移動平均）"""
        editor = self._editors.get(editor_id)
        if not editor:
            return
        alpha = 0.3  # 新しいスコアの重み
        for key, score in project_scores.items():
            old = editor.skills.get(key, 50.0)
            editor.skills[key] = old * (1 - alpha) + score * alpha
        editor.completed_count += 1
        editor.updated_at = datetime.now().isoformat()
        self._save()

    def assign_project(self, editor_id: str, project_id: str) -> bool:
        editor = self._editors.get(editor_id)
        if not editor:
            return False
        if len(editor.active_projects) >= editor.capacity:
            return False
        if project_id not in editor.active_projects:
            editor.active_projects.append(project_id)
            editor.updated_at = datetime.now().isoformat()
            self._save()
        return True

    def complete_project(self, editor_id: str, project_id: str, quality_score: float = None):
        editor = self._editors.get(editor_id)
        if not editor:
            return
        if project_id in editor.active_projects:
            editor.active_projects.remove(project_id)
        if quality_score is not None:
            # 移動平均で更新
            if editor.avg_quality_score == 0:
                editor.avg_quality_score = quality_score
            else:
                editor.avg_quality_score = editor.avg_quality_score * 0.7 + quality_score * 0.3
        editor.updated_at = datetime.now().isoformat()
        self._save()

    def suggest_best_editor(self, required_skills: dict = None) -> Optional[EditorProfile]:
        """タスクに最適な編集者を提案"""
        available = [e for e in self._editors.values()
                     if e.status == "active" and len(e.active_projects) < e.capacity]
        if not available:
            return None
        if not required_skills:
            return min(available, key=lambda e: len(e.active_projects))

        # スキルマッチング
        def skill_match_score(editor):
            total = 0
            for skill, weight in required_skills.items():
                editor_skill = editor.skills.get(skill, 50)
                total += editor_skill * weight
            return total

        return max(available, key=skill_match_score)

    def generate_handover_package(self, editor_id: str) -> dict:
        """F-3: 編集者引き継ぎパッケージ生成"""
        editor = self._editors.get(editor_id)
        if not editor:
            return {}
        return {
            "editor_profile": asdict(editor),
            "skill_summary": {
                "strengths": [k for k, v in editor.skills.items() if v >= 70],
                "weaknesses": [k for k, v in editor.skills.items() if v < 50],
                "overall_avg": sum(editor.skills.values()) / max(len(editor.skills), 1),
            },
            "active_projects": editor.active_projects,
            "completed_count": editor.completed_count,
            "avg_quality": editor.avg_quality_score,
            "generated_at": datetime.now().isoformat(),
            "notes": editor.notes,
        }
