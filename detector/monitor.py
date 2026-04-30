from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Callable


class LogMonitor:
    def __init__(self, log_path: str, poll_interval_seconds: float) -> None:
        self.log_path = Path(log_path)
        self.poll_interval_seconds = poll_interval_seconds

    def follow(self, on_record: Callable[[dict[str, object]], None]) -> None:
        while not self.log_path.exists():
            time.sleep(self.poll_interval_seconds)

        # 🔥 FIX: make decoding fault-tolerant
        with self.log_path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(0, 2)

            while True:
                line = handle.readline()

                if not line:
                    time.sleep(self.poll_interval_seconds)
                    continue

                # 🔒 skip empty / garbage lines early
                if not line.strip():
                    continue

                try:
                    payload = self._parse_line(line)
                    if payload is not None:
                        on_record(payload)
                except Exception as e:
                    # 🔒 NEVER crash the detector because of bad input
                    logging.warning("log parse failure: %s", e)
                    continue

    @staticmethod
    def _parse_line(line: str) -> dict[str, object] | None:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None

        source_ip = payload.get("source_ip")
        timestamp_text = payload.get("timestamp")
        status = payload.get("status")

        if not source_ip or not timestamp_text or status is None:
            return None

        try:
            timestamp_epoch = datetime.fromisoformat(
                str(timestamp_text).replace("Z", "+00:00")
            ).timestamp()
        except ValueError:
            return None

        payload["timestamp_epoch"] = timestamp_epoch

        try:
            payload["status"] = int(status)
        except (ValueError, TypeError):
            return None

        return payload