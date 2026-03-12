"""マルチMac分散処理: SSH経由で重い処理を他Macに分散"""
import subprocess
import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RemoteMac:
    name: str
    host: str           # SSH host (e.g., "pao" or "192.168.x.x")
    ssh_user: str = ""
    status: str = "unknown"  # online / offline / busy / unknown
    current_task: str = ""
    last_check: str = ""


@dataclass
class DistributedTask:
    id: str
    command: str
    target_mac: str
    status: str = "pending"  # pending / running / completed / failed
    result: str = ""
    started_at: str = ""
    completed_at: str = ""
    timeout_seconds: int = 600


class DistributedProcessor:
    """マルチMac分散処理マネージャー"""

    def __init__(self, config_dir: Path = None):
        self.config_dir = config_dir or Path.home() / "AI開発10" / ".data" / "distributed"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.macs_config_path = self.config_dir / "remote_macs.json"
        self._macs: dict[str, RemoteMac] = {}
        self._tasks: dict[str, DistributedTask] = {}
        self._load_macs()

    def _load_macs(self):
        if self.macs_config_path.exists():
            data = json.loads(self.macs_config_path.read_text())
            for m in data.get("macs", []):
                mac = RemoteMac(**m)
                self._macs[mac.name] = mac
        else:
            # デフォルトMac登録（SSH接続済みの想定）
            self._macs = {
                "pao": RemoteMac(name="pao", host="pao"),
                "mac-mini": RemoteMac(name="mac-mini", host="mac-mini-m4.local"),
            }
            self._save_macs()

    def _save_macs(self):
        data = {"macs": [{"name": m.name, "host": m.host, "ssh_user": m.ssh_user,
                          "status": m.status, "current_task": m.current_task,
                          "last_check": m.last_check}
                         for m in self._macs.values()]}
        self.macs_config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def check_mac_status(self, mac_name: str) -> str:
        """SSH接続でMacの死活確認"""
        mac = self._macs.get(mac_name)
        if not mac:
            return "unknown"

        try:
            result = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=5", mac.host, "echo", "alive"],
                capture_output=True, text=True, timeout=10
            )
            status = "online" if result.returncode == 0 else "offline"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            status = "offline"

        mac.status = status
        mac.last_check = datetime.now().isoformat()
        self._save_macs()
        return status

    def check_all_macs(self) -> dict[str, str]:
        """全Macの死活確認"""
        return {name: self.check_mac_status(name) for name in self._macs}

    def dispatch_task(self, mac_name: str, command: str,
                      timeout: int = 600) -> Optional[DistributedTask]:
        """リモートMacにタスクを投げる"""
        mac = self._macs.get(mac_name)
        if not mac or mac.status == "offline":
            return None

        task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        task = DistributedTask(
            id=task_id,
            command=command,
            target_mac=mac_name,
            status="running",
            started_at=datetime.now().isoformat(),
            timeout_seconds=timeout,
        )

        try:
            result = subprocess.run(
                ["ssh", mac.host, command],
                capture_output=True, text=True, timeout=timeout
            )
            task.result = result.stdout[:5000]  # 結果は5000文字まで
            task.status = "completed" if result.returncode == 0 else "failed"
            if result.returncode != 0 and result.stderr:
                task.result += f"\nSTDERR: {result.stderr[:1000]}"
        except subprocess.TimeoutExpired:
            task.status = "failed"
            task.result = f"Timeout after {timeout}s"
        except Exception as e:
            task.status = "failed"
            task.result = str(e)

        task.completed_at = datetime.now().isoformat()
        self._tasks[task_id] = task

        mac.current_task = "" if task.status != "running" else task_id
        self._save_macs()

        return task

    def list_macs(self) -> list[RemoteMac]:
        return list(self._macs.values())

    def list_tasks(self, status: str = None) -> list[DistributedTask]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.started_at or "", reverse=True)

    def get_available_mac(self) -> Optional[RemoteMac]:
        """利用可能なMacを返す"""
        for mac in self._macs.values():
            if mac.status == "online" and not mac.current_task:
                return mac
        return None
