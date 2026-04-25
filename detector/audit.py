from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


class AuditLogger:
    def __init__(self, file_path: str) -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()

    def write(self, action: str, ip_address: str, condition: str, rate: float, baseline: float, duration: str) -> None:
        timestamp = datetime.now(tz=timezone.utc).isoformat()
        line = f"[{timestamp}] {action} {ip_address} | {condition} | {rate:.3f} | {baseline:.3f} | {duration}\n"
        with self.lock:
            with self.file_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
