from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from detector.audit import AuditLogger
from detector.baseline import BaselineManager, BaselineSnapshot
from detector.blocker import Blocker
from detector.notifier import Notifier
from detector.state import BanRecord, RuntimeState


@dataclass(slots=True)
class DetectionThresholds:
    zscore: float
    rate_multiplier: float
    error_surge_multiplier: float
    tightened_zscore: float
    tightened_rate_multiplier: float
    global_alert_cooldown_seconds: int
    ip_alert_cooldown_seconds: int


class AnomalyDetector:
    """Runs the decision logic that compares live 60-second rates with learned baselines.

    The live rate comes from deque windows. The baseline comes from rolling per-second
    history. We fire when either the z-score exceeds the threshold or the current rate is
    more than N times the learned mean. If an IP suddenly produces errors well above its
    normal error rate, we tighten thresholds automatically before making the decision.
    """

    def __init__(
        self,
        state: RuntimeState,
        baseline_manager: BaselineManager,
        blocker: Blocker,
        notifier: Notifier,
        audit_logger: AuditLogger,
        thresholds: DetectionThresholds,
    ) -> None:
        self.state = state
        self.baseline_manager = baseline_manager
        self.blocker = blocker
        self.notifier = notifier
        self.audit_logger = audit_logger
        self.thresholds = thresholds

    def on_request(self, timestamp_epoch: float, source_ip: str, status_code: int) -> None:
        is_error = status_code >= 400
        self.state.add_request(timestamp_epoch, source_ip, is_error)
        self.baseline_manager.observe(timestamp_epoch, source_ip, is_error)
        self._evaluate_ip(timestamp_epoch, source_ip)
        self._evaluate_global(timestamp_epoch)

    def on_baseline_recalculated(self, key: str, snapshot: BaselineSnapshot) -> None:
        self.state.set_baseline_snapshot(key, snapshot)
        self.audit_logger.write(
            "BASELINE",
            key,
            snapshot.source,
            snapshot.mean_rps,
            snapshot.stddev_rps,
            f"samples={snapshot.sample_count}",
        )

    def _evaluate_ip(self, timestamp_epoch: float, source_ip: str) -> None:
        if self.state.is_banned(source_ip):
            return
        baseline = self.baseline_manager.get_snapshot(source_ip)
        if baseline is None:
            return

        current_rate = self.state.current_ip_rate(source_ip)
        error_rate = self.state.current_ip_error_rate(source_ip)
        zscore = self._zscore(current_rate, baseline.mean_rps, baseline.stddev_rps)

        z_threshold = self.thresholds.zscore
        rate_multiplier = self.thresholds.rate_multiplier
        condition_suffix = ""
        if error_rate >= baseline.error_rate * self.thresholds.error_surge_multiplier:
            z_threshold = self.thresholds.tightened_zscore
            rate_multiplier = self.thresholds.tightened_rate_multiplier
            condition_suffix = " + error-surge"

        if zscore > z_threshold:
            condition = f"ip-zscore>{z_threshold:.1f}{condition_suffix}"
            self._ban_ip(timestamp_epoch, source_ip, condition, current_rate, baseline.mean_rps)
            return
        if current_rate > baseline.mean_rps * rate_multiplier:
            condition = f"ip-rate>{rate_multiplier:.1f}x{condition_suffix}"
            self._ban_ip(timestamp_epoch, source_ip, condition, current_rate, baseline.mean_rps)

    def _evaluate_global(self, timestamp_epoch: float) -> None:
        baseline = self.baseline_manager.get_snapshot("global")
        if baseline is None:
            return
        current_rate = self.state.latest_global_rate
        zscore = self._zscore(current_rate, baseline.mean_rps, baseline.stddev_rps)
        now = datetime.fromtimestamp(timestamp_epoch, tz=timezone.utc)
        last_alert = self.state.last_global_alert_at
        if last_alert and (now - last_alert).total_seconds() < self.thresholds.global_alert_cooldown_seconds:
            return

        condition = None
        if zscore > self.thresholds.zscore:
            condition = f"global-zscore>{self.thresholds.zscore:.1f}"
        elif current_rate > baseline.mean_rps * self.thresholds.rate_multiplier:
            condition = f"global-rate>{self.thresholds.rate_multiplier:.1f}x"

        if condition:
            self.state.last_global_alert_at = now
            self.audit_logger.write("GLOBAL_ALERT", "global", condition, current_rate, baseline.mean_rps, "n/a")
            self.notifier.send(
                "Global Traffic Anomaly",
                self._format_alert(
                    condition=condition,
                    ip_address="global",
                    current_rate=current_rate,
                    baseline=baseline.mean_rps,
                    timestamp=now.isoformat(),
                    duration="alert-only",
                ),
            )

    def _ban_ip(self, timestamp_epoch: float, source_ip: str, condition: str, current_rate: float, baseline_mean: float) -> None:
        now = datetime.fromtimestamp(timestamp_epoch, tz=timezone.utc)
        last_alert = self.state.last_ip_alert_at.get(source_ip)
        if last_alert and (now - last_alert).total_seconds() < self.thresholds.ip_alert_cooldown_seconds:
            return

        blocked = self.blocker.block_ip(source_ip)
        if not blocked:
            return

        self.state.last_ip_alert_at[source_ip] = now
        ban = self.state.mark_banned(source_ip, condition, current_rate, baseline_mean)
        duration = f"{ban.duration_minutes}m" if ban.duration_minutes is not None else "permanent"
        self.audit_logger.write("BAN", source_ip, condition, current_rate, baseline_mean, duration)
        self.notifier.send(
            "IP Anomaly Blocked",
            self._format_alert(
                condition=condition,
                ip_address=source_ip,
                current_rate=current_rate,
                baseline=baseline_mean,
                timestamp=now.isoformat(),
                duration=duration,
            ),
        )

    def process_unban(self, ip_address: str) -> BanRecord | None:
        if not self.blocker.unblock_ip(ip_address):
            return None
        record = self.state.unban(ip_address)
        if record is None:
            return None
        self.audit_logger.write("UNBAN", ip_address, record.reason, record.current_rate, record.baseline_mean, "released")
        self.notifier.send(
            "IP Unbanned",
            self._format_alert(
                condition=record.reason,
                ip_address=ip_address,
                current_rate=record.current_rate,
                baseline=record.baseline_mean,
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
                duration="released",
            ),
        )
        return record

    @staticmethod
    def _zscore(current_rate: float, mean: float, stddev: float) -> float:
        if stddev <= 0:
            return 0.0
        return (current_rate - mean) / stddev

    @staticmethod
    def _format_alert(condition: str, ip_address: str, current_rate: float, baseline: float, timestamp: str, duration: str) -> str:
        return (
            f"condition: {condition}\n"
            f"ip: {ip_address}\n"
            f"current_rate: {current_rate:.3f} req/s\n"
            f"baseline_mean: {baseline:.3f} req/s\n"
            f"timestamp: {timestamp}\n"
            f"ban_duration: {duration}"
        )
