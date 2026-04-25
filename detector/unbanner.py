from __future__ import annotations

import time

from detector.detector import AnomalyDetector
from detector.state import RuntimeState


class Unbanner:
    def __init__(self, state: RuntimeState, detector: AnomalyDetector, interval_seconds: int = 5) -> None:
        self.state = state
        self.detector = detector
        self.interval_seconds = interval_seconds

    def run(self) -> None:
        while True:
            due = self.state.due_unbans()
            for record in due:
                self.detector.process_unban(record.ip)
            time.sleep(self.interval_seconds)
