from __future__ import annotations

import threading
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Deque

from detector.baseline import BaselineSnapshot


@dataclass(slots=True)
class BanRecord:
    ip: str
    banned_at: datetime
    duration_minutes: int | None
    release_at: datetime | None
    reason: str
    current_rate: float
    baseline_mean: float
    strike_count: int


class RuntimeState:
    def __init__(self, sliding_window_seconds: int, ban_durations: list[int]) -> None:
        self.sliding_window_seconds = sliding_window_seconds
        self.ban_durations = ban_durations
        self.lock = threading.RLock()
        self.started_at = datetime.now(tz=timezone.utc)
        self.global_requests: Deque[float] = deque()
        self.ip_requests: dict[str, Deque[float]] = defaultdict(deque)
        self.ip_errors: dict[str, Deque[float]] = defaultdict(deque)
        self.total_requests = 0
        self.top_ip_counter: Counter[str] = Counter()
        self.banned_ips: dict[str, BanRecord] = {}
        self.ban_history: dict[str, int] = defaultdict(int)
        self.baseline_snapshots: dict[str, BaselineSnapshot] = {}
        self.last_global_alert_at: datetime | None = None
        self.last_ip_alert_at: dict[str, datetime] = {}
        self.latest_global_rate = 0.0

    def add_request(self, timestamp_epoch: float, source_ip: str, is_error: bool) -> None:
        with self.lock:
            self.total_requests += 1
            self.global_requests.append(timestamp_epoch)
            self.ip_requests[source_ip].append(timestamp_epoch)
            self.top_ip_counter[source_ip] += 1
            if is_error:
                self.ip_errors[source_ip].append(timestamp_epoch)
            self._evict(timestamp_epoch)
            self.latest_global_rate = len(self.global_requests) / self.sliding_window_seconds

    def _evict(self, now_epoch: float) -> None:
        cutoff = now_epoch - self.sliding_window_seconds
        while self.global_requests and self.global_requests[0] < cutoff:
            self.global_requests.popleft()
        for key in list(self.ip_requests.keys()):
            queue = self.ip_requests[key]
            while queue and queue[0] < cutoff:
                queue.popleft()
            if not queue:
                self.ip_requests.pop(key, None)
        for key in list(self.ip_errors.keys()):
            queue = self.ip_errors[key]
            while queue and queue[0] < cutoff:
                queue.popleft()
            if not queue:
                self.ip_errors.pop(key, None)

    def refresh_windows(self, now_epoch: float) -> None:
        with self.lock:
            self._evict(now_epoch)
            self.latest_global_rate = len(self.global_requests) / self.sliding_window_seconds

    def current_ip_rate(self, source_ip: str) -> float:
        with self.lock:
            return len(self.ip_requests.get(source_ip, ())) / self.sliding_window_seconds

    def current_ip_error_rate(self, source_ip: str) -> float:
        with self.lock:
            request_count = len(self.ip_requests.get(source_ip, ()))
            if request_count == 0:
                return 0.0
            return len(self.ip_errors.get(source_ip, ())) / request_count

    def top_ips(self, limit: int = 10) -> list[tuple[str, int, float]]:
        with self.lock:
            results = []
            for ip_address, _ in self.top_ip_counter.most_common(limit * 3):
                if ip_address not in self.ip_requests:
                    continue
                results.append((ip_address, self.top_ip_counter[ip_address], len(self.ip_requests[ip_address]) / self.sliding_window_seconds))
                if len(results) >= limit:
                    break
            return results

    def mark_banned(self, ip_address: str, reason: str, current_rate: float, baseline_mean: float) -> BanRecord:
        with self.lock:
            self.ban_history[ip_address] += 1
            strike_count = self.ban_history[ip_address]
            duration_minutes = None
            release_at = None
            if strike_count <= len(self.ban_durations):
                duration_minutes = self.ban_durations[strike_count - 1]
                release_at = datetime.now(tz=timezone.utc) + timedelta(minutes=duration_minutes)
            record = BanRecord(
                ip=ip_address,
                banned_at=datetime.now(tz=timezone.utc),
                duration_minutes=duration_minutes,
                release_at=release_at,
                reason=reason,
                current_rate=current_rate,
                baseline_mean=baseline_mean,
                strike_count=strike_count,
            )
            self.banned_ips[ip_address] = record
            return record

    def unban(self, ip_address: str) -> BanRecord | None:
        with self.lock:
            return self.banned_ips.pop(ip_address, None)

    def due_unbans(self) -> list[BanRecord]:
        now = datetime.now(tz=timezone.utc)
        with self.lock:
            return [
                record
                for record in self.banned_ips.values()
                if record.release_at is not None and record.release_at <= now
            ]

    def set_baseline_snapshot(self, key: str, snapshot: BaselineSnapshot) -> None:
        with self.lock:
            self.baseline_snapshots[key] = snapshot

    def is_banned(self, ip_address: str) -> bool:
        with self.lock:
            return ip_address in self.banned_ips

    def get_metrics(self) -> dict[str, object]:
        now = datetime.now(tz=timezone.utc)
        with self.lock:
            top_ips = [
                {"ip": ip_address, "total": total, "rate": rate}
                for ip_address, total, rate in self.top_ips()
            ]
            return {
                "uptime_seconds": int((now - self.started_at).total_seconds()),
                "global_rps": round(self.latest_global_rate, 3),
                "top_ips": top_ips,
                "banned_ips": [
                    {
                        "ip": record.ip,
                        "reason": record.reason,
                        "strike_count": record.strike_count,
                        "duration_minutes": record.duration_minutes,
                        "release_at": record.release_at.isoformat() if record.release_at else "permanent",
                    }
                    for record in sorted(self.banned_ips.values(), key=lambda item: item.banned_at, reverse=True)
                ],
                "global_baseline": self.baseline_snapshots.get("global"),
            }
