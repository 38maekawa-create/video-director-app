"""通知: Telegram/LINE通知連携"""
import json
import urllib.request
import urllib.parse
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class NotificationConfig:
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    line_enabled: bool = False
    line_channel_token: str = ""
    line_user_id: str = ""
    notify_on_report: bool = True
    notify_on_quality_warning: bool = True
    notify_on_feedback: bool = True


class Notifier:
    """Telegram / LINE 通知送信"""

    def __init__(self, config_dir: Path = None):
        self.config_dir = config_dir or Path.home() / "AI開発10" / ".data"
        self.config_path = self.config_dir / "notification_config.json"
        self.config = self._load_config()

    def _load_config(self) -> NotificationConfig:
        if self.config_path.exists():
            data = json.loads(self.config_path.read_text())
            return NotificationConfig(**data)
        return NotificationConfig()

    def save_config(self, config: NotificationConfig):
        self.config = config
        self.config_path.write_text(json.dumps({
            "telegram_enabled": config.telegram_enabled,
            "telegram_bot_token": config.telegram_bot_token,
            "telegram_chat_id": config.telegram_chat_id,
            "line_enabled": config.line_enabled,
            "line_channel_token": config.line_channel_token,
            "line_user_id": config.line_user_id,
            "notify_on_report": config.notify_on_report,
            "notify_on_quality_warning": config.notify_on_quality_warning,
            "notify_on_feedback": config.notify_on_feedback,
        }, ensure_ascii=False, indent=2))

    def notify(self, message: str, event_type: str = "general") -> dict:
        """通知を送信"""
        results = {}

        # イベントタイプによるフィルタ
        if event_type == "report" and not self.config.notify_on_report:
            return {"skipped": "report notification disabled"}
        if event_type == "quality_warning" and not self.config.notify_on_quality_warning:
            return {"skipped": "quality warning notification disabled"}
        if event_type == "feedback" and not self.config.notify_on_feedback:
            return {"skipped": "feedback notification disabled"}

        if self.config.telegram_enabled:
            results["telegram"] = self._send_telegram(message)

        if self.config.line_enabled:
            results["line"] = self._send_line(message)

        if not results:
            results["info"] = "No notification channels configured"

        return results

    def _send_telegram(self, message: str) -> str:
        """Telegram Bot API で送信"""
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            return "error: token or chat_id not configured"

        url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
        data = json.dumps({
            "chat_id": self.config.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML",
        }).encode("utf-8")

        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=10)
            if resp.status == 200:
                return "sent"
            return f"error: HTTP {resp.status}"
        except Exception as e:
            return f"error: {str(e)[:100]}"

    def _send_line(self, message: str) -> str:
        """LINE Messaging API で送信"""
        if not self.config.line_channel_token or not self.config.line_user_id:
            return "error: token or user_id not configured"

        url = "https://api.line.me/v2/bot/message/push"
        data = json.dumps({
            "to": self.config.line_user_id,
            "messages": [{"type": "text", "text": message}],
        }).encode("utf-8")

        try:
            req = urllib.request.Request(url, data=data, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.line_channel_token}",
            })
            resp = urllib.request.urlopen(req, timeout=10)
            if resp.status == 200:
                return "sent"
            return f"error: HTTP {resp.status}"
        except Exception as e:
            return f"error: {str(e)[:100]}"

    def notify_report_complete(self, guest_name: str, report_url: str):
        """レポート完成通知"""
        message = f"📋 ディレクションレポート完成\nゲスト: {guest_name}\n{report_url}"
        return self.notify(message, "report")

    def notify_quality_warning(self, guest_name: str, score: float, issues: list):
        """品質警告通知"""
        issues_text = "\n".join(f"  ⚠️ {i}" for i in issues[:5])
        message = f"⚠️ 品質警告: {guest_name}\nスコア: {score:.0f}\n{issues_text}"
        return self.notify(message, "quality_warning")

    def notify_feedback_received(self, guest_name: str, created_by: str, content_preview: str):
        """FB受信通知"""
        message = f"💬 新しいフィードバック\n案件: {guest_name}\n投稿者: {created_by}\n{content_preview[:100]}"
        return self.notify(message, "feedback")

    def get_config(self) -> dict:
        """現在の設定を辞書で返す"""
        return {
            "telegram_enabled": self.config.telegram_enabled,
            "telegram_configured": bool(self.config.telegram_bot_token and self.config.telegram_chat_id),
            "line_enabled": self.config.line_enabled,
            "line_configured": bool(self.config.line_channel_token and self.config.line_user_id),
            "notify_on_report": self.config.notify_on_report,
            "notify_on_quality_warning": self.config.notify_on_quality_warning,
            "notify_on_feedback": self.config.notify_on_feedback,
        }
