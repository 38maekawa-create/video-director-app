from __future__ import annotations

"""品質改善ループ: ディレクション→編集→評価→FB→ルール更新のPDCA自動化"""
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class PDCAState:
    project_id: str
    guest_name: str = ""
    # Plan
    direction_generated: bool = False
    direction_url: str = ""
    # Do
    editing_assigned: bool = False
    editor_id: str = ""
    editing_completed: bool = False
    # Check
    quality_scored: bool = False
    quality_score: float = 0.0
    feedback_count: int = 0
    # Act
    rules_updated: bool = False
    learning_applied: bool = False
    # メタ
    current_phase: str = "plan"  # plan / do / check / act / completed
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class PDCALoop:
    """品質改善PDCAサイクルの管理"""

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path.home() / "AI開発10" / ".data" / "pdca"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.data_dir / "pdca_states.json"
        self._states: dict[str, PDCAState] = {}
        self._load()

    def _load(self):
        if self.index_path.exists():
            data = json.loads(self.index_path.read_text())
            for s in data.get("states", []):
                state = PDCAState(**s)
                self._states[state.project_id] = state

    def _save(self):
        self.index_path.write_text(json.dumps(
            {"states": [asdict(s) for s in self._states.values()],
             "updated_at": datetime.now().isoformat()},
            ensure_ascii=False, indent=2))

    def start_cycle(self, project_id: str, guest_name: str = "") -> PDCAState:
        """新しいPDCAサイクルを開始"""
        state = PDCAState(project_id=project_id, guest_name=guest_name)
        self._states[project_id] = state
        self._save()
        return state

    def mark_direction_generated(self, project_id: str, url: str):
        """Plan完了: ディレクション生成済み"""
        if state := self._states.get(project_id):
            state.direction_generated = True
            state.direction_url = url
            state.current_phase = "do"
            state.updated_at = datetime.now().isoformat()
            self._save()

    def mark_editing_assigned(self, project_id: str, editor_id: str):
        """Do開始: 編集者アサイン"""
        if state := self._states.get(project_id):
            state.editing_assigned = True
            state.editor_id = editor_id
            state.updated_at = datetime.now().isoformat()
            self._save()

    def mark_editing_completed(self, project_id: str):
        """Do完了: 編集完了"""
        if state := self._states.get(project_id):
            state.editing_completed = True
            state.current_phase = "check"
            state.updated_at = datetime.now().isoformat()
            self._save()

    def mark_quality_scored(self, project_id: str, score: float):
        """Check: 品質評価完了"""
        if state := self._states.get(project_id):
            state.quality_scored = True
            state.quality_score = score
            state.updated_at = datetime.now().isoformat()
            self._save()

    def add_feedback(self, project_id: str):
        """Check: FB追加"""
        if state := self._states.get(project_id):
            state.feedback_count += 1
            state.current_phase = "act"
            state.updated_at = datetime.now().isoformat()
            self._save()

    def mark_rules_updated(self, project_id: str):
        """Act: ルール更新完了"""
        if state := self._states.get(project_id):
            state.rules_updated = True
            state.learning_applied = True
            state.current_phase = "completed"
            state.completed_at = datetime.now().isoformat()
            state.updated_at = datetime.now().isoformat()
            self._save()

    def get_state(self, project_id: str) -> Optional[PDCAState]:
        return self._states.get(project_id)

    def list_states(self, phase: str = None) -> list[PDCAState]:
        states = list(self._states.values())
        if phase:
            states = [s for s in states if s.current_phase == phase]
        return sorted(states, key=lambda s: s.updated_at, reverse=True)

    def get_summary(self) -> dict:
        """PDCA全体のサマリー"""
        from collections import Counter
        phase_counts = Counter(s.current_phase for s in self._states.values())
        return {
            "total_cycles": len(self._states),
            "phase_distribution": dict(phase_counts),
            "completed_cycles": phase_counts.get("completed", 0),
            "active_cycles": len(self._states) - phase_counts.get("completed", 0),
            "avg_quality_score": (
                sum(s.quality_score for s in self._states.values() if s.quality_scored)
                / max(1, sum(1 for s in self._states.values() if s.quality_scored))
            ),
        }
