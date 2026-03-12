#!/usr/bin/env python3
"""巡回監査の定期実行スクリプト（launchdから呼び出し）"""
import sys
sys.path.insert(0, str(__import__('pathlib').Path.home() / 'AI開発10'))

from src.video_direction.integrations.audit_runner import AuditRunner

def main():
    runner = AuditRunner()
    report = runner.run_audit()
    print(f"監査完了: {report.overall_health}")
    print(f"  DB: {report.db_health}")
    print(f"  API: {report.api_health}")
    print(f"  未処理: {report.pending_videos}件")
    print(f"  品質異常: {len(report.quality_anomalies)}件")
    print(f"  滞留: {len(report.stale_projects)}件")

    # 警告以上の場合は通知
    if report.overall_health in ("warning", "critical"):
        try:
            from src.video_direction.integrations.notifier import Notifier
            notifier = Notifier()
            issues = report.quality_anomalies + report.stale_projects
            message = f"⚠️ 巡回監査: {report.overall_health}\n"
            message += f"未処理: {report.pending_videos}件\n"
            if issues:
                message += "\n".join(f"  - {i}" for i in issues[:5])
            notifier.notify(message, "quality_warning")
        except Exception:
            pass

if __name__ == "__main__":
    main()
