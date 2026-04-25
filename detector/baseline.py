from __future__ import annotations

import math
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Deque


@dataclass(slots=True)
class BaselineSnapshot:
    mean_rps: float
    stddev_rps: float
    error_rate: float
    sample_count: int
    computed_at: str
    source: str


@dataclass(slots=True)
class HourlySlot:
    request_counts: Deque[int] = field(default_factory=lambda: deque(maxlen=3600))
    error_counts: Deque[int] = field(default_factory=lambda: deque(maxlen=3600))


class BaselineManager:
    """Maintains rolling per-second traffic history and recalculates effective baselines.

    The detector needs a learning baseline instead of hardcoded thresholds. To do that,
    this manager stores per-second counts inside hour buckets and recomputes mean/stddev
    every 60 seconds. If the current hour has enough samples we trust it first, because
    it best reflects time-of-day traffic. Otherwise we fall back to the rolling 30-minute
    history assembled from recent hour slots.
    """

    def __init__(
        self,
        baseline_window_seconds: int,
        min_hour_samples: int,
        minimum_mean_rps: float,
        minimum_stddev_rps: float,
        minimum_error_rate: float,
    ) -> None:
        self.baseline_window_seconds = baseline_window_seconds
        self.min_hour_samples = min_hour_samples
        self.minimum_mean_rps = minimum_mean_rps
        self.minimum_stddev_rps = minimum_stddev_rps
        self.minimum_error_rate = minimum_error_rate
        self.lock = threading.Lock()
        self.hourly_counts: dict[str, dict[str, HourlySlot]] = defaultdict(dict)
        self.current_second_counts: dict[str, int] = defaultdict(int)
        self.current_second_errors: dict[str, int] = defaultdict(int)
        self.snapshots: dict[str, BaselineSnapshot] = {}
        self.hourly_effective_means: dict[str, dict[str, float]] = defaultdict(dict)
        self.last_second_epoch: int | None = None
        self.last_seen: dict[str, float] = {}
        self.known_keys: set[str] = {"global"}

    def observe(self, timestamp_epoch: float, source_ip: str, is_error: bool) -> None:
        second_epoch = int(timestamp_epoch)
        with self.lock:
            if self.last_second_epoch is None:
                self.last_second_epoch = second_epoch
            while self.last_second_epoch is not None and second_epoch > self.last_second_epoch:
                self._flush_current_second(self.last_second_epoch)
                self.last_second_epoch += 1

            self.current_second_counts["global"] += 1
            self.current_second_counts[source_ip] += 1
            self.known_keys.add(source_ip)
            self.last_seen["global"] = timestamp_epoch
            self.last_seen[source_ip] = timestamp_epoch

            if is_error:
                self.current_second_errors["global"] += 1
                self.current_second_errors[source_ip] += 1

    def _flush_current_second(self, second_epoch: int) -> None:
        second_dt = datetime.fromtimestamp(second_epoch, tz=timezone.utc)
        hour_key = second_dt.strftime("%Y-%m-%dT%H:00:00Z")
        keys = (
            set(self.known_keys)
            | set(self.hourly_counts.keys())
            | set(self.current_second_counts)
            | set(self.current_second_errors)
        )
        for key in keys:
            slot = self.hourly_counts[key].get(hour_key)
            if slot is None:
                slot = HourlySlot()
                self.hourly_counts[key][hour_key] = slot
            slot.request_counts.append(self.current_second_counts.get(key, 0))
            slot.error_counts.append(self.current_second_errors.get(key, 0))
        self.current_second_counts.clear()
        self.current_second_errors.clear()

    def recalculate(self, now_epoch: float) -> list[tuple[str, BaselineSnapshot]]:
        with self.lock:
            if self.last_second_epoch is not None:
                current_second = int(now_epoch)
                while current_second > self.last_second_epoch:
                    self._flush_current_second(self.last_second_epoch)
                    self.last_second_epoch += 1

            snapshots: list[tuple[str, BaselineSnapshot]] = []
            stale_before = now_epoch - 3600
            for key, last_seen in list(self.last_seen.items()):
                if key != "global" and last_seen < stale_before:
                    self.hourly_counts.pop(key, None)
                    self.snapshots.pop(key, None)
                    self.hourly_effective_means.pop(key, None)
                    self.last_seen.pop(key, None)
                    self.known_keys.discard(key)

            for key in list(self.hourly_counts.keys()):
                snapshot = self._build_snapshot(key, now_epoch)
                self.snapshots[key] = snapshot
                snapshots.append((key, snapshot))
            return snapshots

    def _build_snapshot(self, key: str, now_epoch: float) -> BaselineSnapshot:
        now_dt = datetime.fromtimestamp(now_epoch, tz=timezone.utc)
        current_hour_key = now_dt.strftime("%Y-%m-%dT%H:00:00Z")
        hour_slot = self.hourly_counts.get(key, {}).get(current_hour_key)

        if hour_slot and len(hour_slot.request_counts) >= self.min_hour_samples:
            counts = list(hour_slot.request_counts)
            errors = list(hour_slot.error_counts)
            source = f"hour-slot:{current_hour_key}"
        else:
            counts = self._collect_recent_counts(key)
            errors = self._collect_recent_errors(key)
            source = "rolling-30m"

        mean = max(self._mean(counts), self.minimum_mean_rps)
        stddev = max(self._stddev(counts, mean), self.minimum_stddev_rps)
        error_rate = max(self._ratio(sum(errors), max(sum(counts), 1)), self.minimum_error_rate)
        computed_at = now_dt.isoformat()

        self.hourly_effective_means[key][current_hour_key] = mean
        return BaselineSnapshot(
            mean_rps=mean,
            stddev_rps=stddev,
            error_rate=error_rate,
            sample_count=len(counts),
            computed_at=computed_at,
            source=source,
        )

    def _collect_recent_counts(self, key: str) -> list[int]:
        values: list[int] = []
        slots = [slot for _, slot in sorted(self.hourly_counts.get(key, {}).items())][-2:]
        for slot in slots:
            values.extend(slot.request_counts)
        return values[-self.baseline_window_seconds :]

    def _collect_recent_errors(self, key: str) -> list[int]:
        values: list[int] = []
        slots = [slot for _, slot in sorted(self.hourly_counts.get(key, {}).items())][-2:]
        for slot in slots:
            values.extend(slot.error_counts)
        return values[-self.baseline_window_seconds :]

    @staticmethod
    def _mean(values: list[int]) -> float:
        if not values:
            return 0.0
        return sum(values) / len(values)

    @staticmethod
    def _stddev(values: list[int], mean: float) -> float:
        if not values:
            return 0.0
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return math.sqrt(variance)

    @staticmethod
    def _ratio(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return numerator / denominator

    def get_snapshot(self, key: str) -> BaselineSnapshot | None:
        with self.lock:
            return self.snapshots.get(key)

    def get_hourly_means(self, key: str) -> dict[str, float]:
        with self.lock:
            return dict(sorted(self.hourly_effective_means.get(key, {}).items()))
