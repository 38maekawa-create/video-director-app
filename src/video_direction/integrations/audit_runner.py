from __future__ import annotations

"""定期巡回監査: パイプライン死活監視・品質異常値検出・滞留アラート"""
import json
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class AuditReport:
    run_at: str = field(default_factory=lambda: datetime.now().isoformat())
    pipeline_status: str = "healthy"     # healthy / warning / error
    pending_videos: int = 0              # 未処理動画数
    quality_anomalies: list = field(default_factory=list)
    stale_projects: list = field(default_factory=list)  # 滞留プロジェクト
    api_health: str = "unknown"          # healthy / unhealthy
    db_health: str = "unknown"
    overall_health: str = "good"         # good / warning / critical
    details: dict = field(default_factory=dict)


class AuditRunner:
    """パイプラインの死活監視・品質異常値検出"""

    def __init__(self, db_path: Path = None, transcript_dir: Path = None):
        self.db_path = db_path or Path.home() / ".data" / "video_director.db"
        self.transcript_dir = transcript_dir or Path.home() / "TEKO" / "knowledge" / "raw-data" / "video_transcripts"
        self.report_dir = Path.home() / "AI開発10" / ".data" / "audit"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def run_audit(self) -> AuditReport:
        """全項目の監査を実行"""
        report = AuditReport()

        # 1. DB死活確認
        report.db_health = self._check_db()

        # 2. 未処理動画の検出
        report.pending_videos = self._count_pending_videos()

        # 3. 品質異常値の検出
        report.quality_anomalies = self._detect_quality_anomalies()

        # 4. 滞留プロジェクトの検出
        report.stale_projects = self._detect_stale_projects()

        # 5. API死活確認
        report.api_health = self._check_api()

        # 6. 総合判定
        report.overall_health = self._judge_overall(report)
        report.pipeline_status = report.overall_health

        # レポート保存
        self._save_report(report)

        return report

    def _check_db(self) -> str:
        try:
            if not self.db_path.exists():
                return "unhealthy"
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.execute("SELECT COUNT(*) FROM projects")
            count = cursor.fetchone()[0]
            conn.close()
            return "healthy" if count > 0 else "warning"
        except Exception:
            return "unhealthy"

    def _count_pending_videos(self) -> int:
        """未処理の文字起こしファイル数をチェック"""
        if not self.transcript_dir.exists():
            return 0
        # DBに登録済みのゲスト名を取得
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.execute("SELECT guest_name FROM projects")
            registered = {row[0].lower() for row in cursor.fetchall()}
            conn.close()
        except Exception:
            registered = set()

        # 文字起こしファイル数 - 登録済み数
        transcript_files = list(self.transcript_dir.glob("*.json"))
        return max(0, len(transcript_files) - len(registered))

    def _detect_quality_anomalies(self) -> list:
        """品質スコアの異常値を検出"""
        anomalies = []
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.execute(
                "SELECT guest_name, quality_score FROM projects WHERE quality_score IS NOT NULL"
            )
            scores = cursor.fetchall()
            conn.close()

            if not scores:
                return []

            avg = sum(s[1] for s in scores) / len(scores)
            for name, score in scores:
                if score < avg * 0.7:  # 平均の70%以下は異常
                    anomalies.append(f"{name}: スコア{score}（平均{avg:.0f}の{score/avg*100:.0f}%）")
        except Exception:
            pass
        return anomalies

    def _detect_stale_projects(self, days_threshold: int = 7) -> list:
        """更新が滞留しているプロジェクト"""
        stale = []
        try:
            conn = sqlite3.connect(str(self.db_path))
            threshold = (datetime.now() - timedelta(days=days_threshold)).isoformat()
            cursor = conn.execute(
                "SELECT guest_name, status, updated_at FROM projects "
                "WHERE status != 'completed' AND updated_at < ?",
                (threshold,)
            )
            for name, status, updated_at in cursor.fetchall():
                stale.append(f"{name}（状態: {status}、最終更新: {updated_at[:10]}）")
            conn.close()
        except Exception:
            pass
        return stale

    def _check_api(self) -> str:
        """APIサーバーの死活確認"""
        import urllib.request
        try:
            req = urllib.request.urlopen("http://localhost:8210/api/health", timeout=5)
            if req.status == 200:
                return "healthy"
        except Exception:
            pass
        return "unhealthy"

    def _judge_overall(self, report: AuditReport) -> str:
        """総合判定"""
        if report.db_health == "unhealthy" or report.api_health == "unhealthy":
            return "critical"
        if report.quality_anomalies or report.stale_projects or report.pending_videos > 5:
            return "warning"
        return "good"

    def _save_report(self, report: AuditReport):
        """監査レポートを保存"""
        filename = f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.report_dir / filename
        filepath.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2))

        # 最新レポートへのシンボリックリンク
        latest = self.report_dir / "latest.json"
        if latest.exists() or latest.is_symlink():
            latest.unlink()
        latest.symlink_to(filepath)

    def get_latest_report(self) -> Optional[AuditReport]:
        """最新の監査レポートを取得"""
        latest = self.report_dir / "latest.json"
        if latest.exists():
            data = json.loads(latest.read_text())
            return AuditReport(**data)
        return None

    def get_report_history(self, limit: int = 10) -> list[AuditReport]:
        """過去の監査レポート一覧"""
        reports = []
        for f in sorted(self.report_dir.glob("audit_*.json"), reverse=True)[:limit]:
            data = json.loads(f.read_text())
            reports.append(AuditReport(**data))
        return reports
