from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass(slots=True)
class Notifier:
    webhook_url: str
    enabled: bool
    timeout_seconds: int

    def send(self, title: str, body: str) -> None:
        if not self.enabled or not self.webhook_url:
            return
        payload = {"text": f"*{title}*\n{body}"}
        try:
            requests.post(self.webhook_url, json=payload, timeout=self.timeout_seconds)
        except requests.RequestException:
            return
