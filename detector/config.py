from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class AppConfig:
    raw: dict[str, Any]

    @property
    def server(self) -> dict[str, Any]:
        return self.raw["server"]

    @property
    def monitor(self) -> dict[str, Any]:
        return self.raw["monitor"]

    @property
    def windows(self) -> dict[str, Any]:
        return self.raw["windows"]

    @property
    def thresholds(self) -> dict[str, Any]:
        return self.raw["thresholds"]

    @property
    def blocking(self) -> dict[str, Any]:
        return self.raw["blocking"]

    @property
    def notifications(self) -> dict[str, Any]:
        return self.raw["notifications"]

    @property
    def logging(self) -> dict[str, Any]:
        return self.raw["logging"]


def load_config(path: str | Path) -> AppConfig:
    with Path(path).expanduser().open("r", encoding="utf-8") as handle:
        raw_text = handle.read()
    data = yaml.safe_load(os.path.expandvars(raw_text))
    return AppConfig(raw=data)
