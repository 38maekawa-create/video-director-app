from __future__ import annotations
"""B-2: 品質トラッキングダッシュボード

動画ごとの品質スコア時系列推移 + 改善率の可視化。
初稿 → 修正1 → 修正2 → 完成版 の各段階での品質変化を記録・追跡する。

データはJSON形式でローカルファイルに永続化。
将来的にはWebダッシュボードとして可視化を検討。
"""

import json
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# デフォルトのデータ保存先
DEFAULT_DATA_DIR = Path.home() / "TEKO" / "knowledge" / "raw-data" / "video-direction"
DEFAULT_DASHBOARD_FILE = "quality_dashboard.json"


@dataclass
class QualitySnapshot:
    """品質スコアのスナップショット（特定時点の記録）"""
    timestamp: str  # ISO形式のタイムスタンプ
    stage: str  # "draft" / "revision_1" / "revision_2" / "final"
    stage_label: str  # "初稿" / "修正1" / "修正2" / "完成版"
    total_score: float  # 総合スコア（0-100）
    grade: str  # "S"/"A"/"B"/"C"/"D"
    dimension_scores: dict = field(default_factory=dict)  # {dimension: score}
    notes: str = ""  # メモ


@dataclass
class VideoQualityRecord:
    """動画ごとの品質記録"""
    video_id: str  # ユニークID（ゲスト名+撮影日等）
    guest_name: str
    video_title: str
    created_at: str  # 最初の記録日時
    updated_at: str  # 最終更新日時
    snapshots: list = field(default_factory=list)  # List[QualitySnapshot]
    editor: str = ""  # 担当編集者
    improvement_rate: float = 0.0  # 改善率（%）（初稿→最新の変化率）

    def latest_snapshot(self) -> Optional[QualitySnapshot]:
        """最新のスナップショットを取得"""
        if not self.snapshots:
            return None
        return self.snapshots[-1]

    def calculate_improvement_rate(self) -> float:
        """改善率を計算（初稿→最新）"""
        if len(self.snapshots) < 2:
            return 0.0
        first = self.snapshots[0].total_score
        latest = self.snapshots[-1].total_score
        if first == 0:
            return 0.0
        rate = ((latest - first) / first) * 100
        return round(rate, 1)


@dataclass
class DashboardSummary:
    """ダッシュボードサマリー"""
    total_videos: int = 0
    average_score: float = 0.0
    average_improvement_rate: float = 0.0
    grade_distribution: dict = field(default_factory=dict)  # {"S": 2, "A": 5, ...}
    top_performers: list = field(default_factory=list)  # 上位動画リスト
    needs_improvement: list = field(default_factory=list)  # 改善が必要な動画リスト
    editor_stats: dict = field(default_factory=dict)  # {editor: {avg_score, count}}


class QualityDashboard:
    """品質トラッキングダッシュボード

    動画ごとの品質スコアを記録・追跡し、
    時系列推移や改善率を可視化するためのデータ管理を行う。
    """

    def __init__(self, data_dir: Optional[str | Path] = None):
        """初期化

        Args:
            data_dir: データ保存先ディレクトリ（Noneの場合はデフォルト）
        """
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.data_file = self.data_dir / DEFAULT_DASHBOARD_FILE
        self.records: dict = {}  # {video_id: VideoQualityRecord}
        self._load()

    def _load(self):
        """データファイルから読み込み"""
        if self.data_file.exists():
            try:
                data = json.loads(self.data_file.read_text(encoding="utf-8"))
                for vid, record_data in data.get("records", {}).items():
                    snapshots = [
                        QualitySnapshot(**s) for s in record_data.get("snapshots", [])
                    ]
                    self.records[vid] = VideoQualityRecord(
                        video_id=record_data["video_id"],
                        guest_name=record_data["guest_name"],
                        video_title=record_data["video_title"],
                        created_at=record_data["created_at"],
                        updated_at=record_data["updated_at"],
                        snapshots=snapshots,
                        editor=record_data.get("editor", ""),
                        improvement_rate=record_data.get("improvement_rate", 0.0),
                    )
            except (json.JSONDecodeError, KeyError, TypeError):
                # データ破損の場合は空で初期化
                self.records = {}

    def _save(self):
        """データファイルに保存"""
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "records": {},
        }
        for vid, record in self.records.items():
            data["records"][vid] = {
                "video_id": record.video_id,
                "guest_name": record.guest_name,
                "video_title": record.video_title,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
                "snapshots": [asdict(s) for s in record.snapshots],
                "editor": record.editor,
                "improvement_rate": record.improvement_rate,
            }
        self.data_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def record_quality(
        self,
        video_id: str,
        guest_name: str,
        video_title: str,
        stage: str,
        total_score: float,
        grade: str,
        dimension_scores: dict = None,
        editor: str = "",
        notes: str = "",
    ) -> VideoQualityRecord:
        """品質スコアを記録する

        Args:
            video_id: 動画のユニークID
            guest_name: ゲスト名
            video_title: 動画タイトル
            stage: 段階（"draft" / "revision_1" / "revision_2" / "final"）
            total_score: 総合スコア
            grade: グレード
            dimension_scores: 各次元のスコア
            editor: 担当編集者
            notes: メモ

        Returns:
            VideoQualityRecord: 更新された品質記録
        """
        now = datetime.now().isoformat()

        stage_labels = {
            "draft": "初稿",
            "revision_1": "修正1",
            "revision_2": "修正2",
            "final": "完成版",
        }

        snapshot = QualitySnapshot(
            timestamp=now,
            stage=stage,
            stage_label=stage_labels.get(stage, stage),
            total_score=total_score,
            grade=grade,
            dimension_scores=dimension_scores or {},
            notes=notes,
        )

        if video_id in self.records:
            record = self.records[video_id]
            record.snapshots.append(snapshot)
            record.updated_at = now
            if editor:
                record.editor = editor
        else:
            record = VideoQualityRecord(
                video_id=video_id,
                guest_name=guest_name,
                video_title=video_title,
                created_at=now,
                updated_at=now,
                snapshots=[snapshot],
                editor=editor,
            )
            self.records[video_id] = record

        # 改善率を更新
        record.improvement_rate = record.calculate_improvement_rate()

        # 永続化
        self._save()

        return record

    def get_record(self, video_id: str) -> Optional[VideoQualityRecord]:
        """動画IDで品質記録を取得"""
        return self.records.get(video_id)

    def get_all_records(self) -> list:
        """全記録を取得（更新日時降順）"""
        return sorted(
            self.records.values(),
            key=lambda r: r.updated_at,
            reverse=True,
        )

    def get_summary(self) -> DashboardSummary:
        """ダッシュボードサマリーを生成"""
        records = list(self.records.values())
        if not records:
            return DashboardSummary()

        # 最新スナップショットのスコアを集計
        latest_scores = []
        grade_dist = {}
        editor_data = {}

        for record in records:
            latest = record.latest_snapshot()
            if latest:
                latest_scores.append(latest.total_score)
                grade_dist[latest.grade] = grade_dist.get(latest.grade, 0) + 1

                if record.editor:
                    if record.editor not in editor_data:
                        editor_data[record.editor] = {"scores": [], "count": 0}
                    editor_data[record.editor]["scores"].append(latest.total_score)
                    editor_data[record.editor]["count"] += 1

        # 平均スコア
        avg_score = sum(latest_scores) / len(latest_scores) if latest_scores else 0

        # 平均改善率
        improvement_rates = [r.improvement_rate for r in records if r.improvement_rate != 0]
        avg_improvement = (
            sum(improvement_rates) / len(improvement_rates)
            if improvement_rates else 0
        )

        # 上位・下位
        sorted_records = sorted(
            records,
            key=lambda r: (r.latest_snapshot().total_score if r.latest_snapshot() else 0),
            reverse=True,
        )
        top = [
            {"video_id": r.video_id, "guest_name": r.guest_name,
             "score": r.latest_snapshot().total_score if r.latest_snapshot() else 0}
            for r in sorted_records[:3]
        ]
        bottom = [
            {"video_id": r.video_id, "guest_name": r.guest_name,
             "score": r.latest_snapshot().total_score if r.latest_snapshot() else 0}
            for r in sorted_records[-3:]
        ]

        # 編集者統計
        editor_stats = {}
        for editor, data in editor_data.items():
            editor_stats[editor] = {
                "avg_score": round(sum(data["scores"]) / len(data["scores"]), 1),
                "count": data["count"],
            }

        return DashboardSummary(
            total_videos=len(records),
            average_score=round(avg_score, 1),
            average_improvement_rate=round(avg_improvement, 1),
            grade_distribution=grade_dist,
            top_performers=top,
            needs_improvement=bottom,
            editor_stats=editor_stats,
        )

    def get_timeline(self, video_id: str) -> list:
        """動画の品質スコア時系列を取得

        Returns:
            list[dict]: [{"stage": "初稿", "score": 65, "grade": "B", "timestamp": "..."}]
        """
        record = self.records.get(video_id)
        if not record:
            return []

        return [
            {
                "stage": s.stage_label,
                "score": s.total_score,
                "grade": s.grade,
                "timestamp": s.timestamp,
                "notes": s.notes,
            }
            for s in record.snapshots
        ]

    def get_editor_ranking(self) -> list:
        """編集者ランキング（平均スコア順）

        Returns:
            list[dict]: [{"editor": "名前", "avg_score": 85.0, "count": 5, "avg_improvement": 10.5}]
        """
        editor_data = {}

        for record in self.records.values():
            if not record.editor:
                continue
            if record.editor not in editor_data:
                editor_data[record.editor] = {
                    "scores": [],
                    "improvements": [],
                    "count": 0,
                }
            latest = record.latest_snapshot()
            if latest:
                editor_data[record.editor]["scores"].append(latest.total_score)
                editor_data[record.editor]["count"] += 1
                if record.improvement_rate != 0:
                    editor_data[record.editor]["improvements"].append(record.improvement_rate)

        ranking = []
        for editor, data in editor_data.items():
            avg_score = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
            avg_improvement = (
                sum(data["improvements"]) / len(data["improvements"])
                if data["improvements"] else 0
            )
            ranking.append({
                "editor": editor,
                "avg_score": round(avg_score, 1),
                "count": data["count"],
                "avg_improvement": round(avg_improvement, 1),
            })

        return sorted(ranking, key=lambda x: x["avg_score"], reverse=True)

    def clear_all(self):
        """全データをクリア（テスト用）"""
        self.records = {}
        if self.data_file.exists():
            self.data_file.unlink()
