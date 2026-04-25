from __future__ import annotations

import logging
import os
import threading
import time

from detector.audit import AuditLogger
from detector.baseline import BaselineManager
from detector.blocker import Blocker
from detector.config import load_config
from detector.dashboard import DashboardServer
from detector.detector import AnomalyDetector, DetectionThresholds
from detector.monitor import LogMonitor
from detector.notifier import Notifier
from detector.state import RuntimeState
from detector.unbanner import Unbanner


def main() -> None:
    config = load_config(os.environ.get("DETECTOR_CONFIG", "/app/detector/config.yaml"))
    logging.basicConfig(level=getattr(logging, config.logging["level"], logging.INFO))
    audit_logger = AuditLogger(config.logging["audit_log_path"])

    state = RuntimeState(
        sliding_window_seconds=config.windows["sliding_window_seconds"],
        ban_durations=config.blocking["durations_minutes"],
    )
    baseline_manager = BaselineManager(
        baseline_window_seconds=config.windows["baseline_window_seconds"],
        min_hour_samples=config.windows["min_hour_samples"],
        minimum_mean_rps=config.thresholds["minimum_mean_rps"],
        minimum_stddev_rps=config.thresholds["minimum_stddev_rps"],
        minimum_error_rate=config.thresholds["minimum_error_rate"],
    )
    blocker = Blocker(chain=config.blocking["chain"], action=config.blocking["action"])
    notifier = Notifier(
        webhook_url=config.notifications["slack_webhook_url"],
        enabled=config.notifications["enabled"],
        timeout_seconds=config.notifications["timeout_seconds"],
    )
    detector = AnomalyDetector(
        state=state,
        baseline_manager=baseline_manager,
        blocker=blocker,
        notifier=notifier,
        audit_logger=audit_logger,
        thresholds=DetectionThresholds(
            zscore=config.thresholds["zscore"],
            rate_multiplier=config.thresholds["rate_multiplier"],
            error_surge_multiplier=config.thresholds["error_surge_multiplier"],
            tightened_zscore=config.thresholds["tightened_zscore"],
            tightened_rate_multiplier=config.thresholds["tightened_rate_multiplier"],
            global_alert_cooldown_seconds=config.thresholds["global_alert_cooldown_seconds"],
            ip_alert_cooldown_seconds=config.thresholds["ip_alert_cooldown_seconds"],
        ),
    )
    dashboard = DashboardServer(state=state, baseline_manager=baseline_manager)
    monitor = LogMonitor(
        log_path=config.monitor["log_path"],
        poll_interval_seconds=config.monitor["poll_interval_seconds"],
    )
    unbanner = Unbanner(state=state, detector=detector)

    def handle_record(record: dict[str, object]) -> None:
        logging.info(
            "event source_ip=%s method=%s path=%s status=%s",
            record.get("source_ip"),
            record.get("method"),
            record.get("path"),
            record.get("status"),
        )
        detector.on_request(
            timestamp_epoch=float(record["timestamp_epoch"]),
            source_ip=str(record["source_ip"]),
            status_code=int(record["status"]),
        )

    def baseline_loop() -> None:
        interval = config.windows["recalc_interval_seconds"]
        while True:
            time.sleep(interval)
            now_epoch = time.time()
            state.refresh_windows(now_epoch)
            for key, snapshot in baseline_manager.recalculate(now_epoch):
                detector.on_baseline_recalculated(key, snapshot)

    threads = [
        threading.Thread(target=baseline_loop, name="baseline-loop", daemon=True),
        threading.Thread(target=unbanner.run, name="unbanner", daemon=True),
        threading.Thread(
            target=dashboard.run,
            kwargs={"host": config.server["metrics_host"], "port": config.server["metrics_port"]},
            name="dashboard",
            daemon=True,
        ),
    ]

    for thread in threads:
        thread.start()

    logging.info("detector starting; monitoring %s", config.monitor["log_path"])
    monitor.follow(handle_record)


if __name__ == "__main__":
    main()
