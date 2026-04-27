# HNG Stage 3 DevSecOps Project

## Real-Time HTTP Anomaly Detection Engine for cloud.ng

This project deploys Nextcloud behind Nginx and adds a custom Python anomaly detection daemon that monitors HTTP traffic in real time, learns baseline behavior, detects anomalous request patterns, blocks abusive IPs with `iptables`, sends Slack alerts, and exposes a live metrics dashboard.

The supplied Nextcloud image was used exactly as required:

- `kefaslungu/hng-nextcloud`

It was not modified or replaced.

## Live Submission Details

- Server IP: `54.90.137.142`
- Metrics dashboard URL: `http://54.90.137.142:8081`
- Language used: `Python`
- GitHub repository: https://github.com/Patrickmbaza/hng14-stage3-devops-
- Blog post: https://dev.to/goteh_mbaza_e513bdbf1871a/-how-i-built-a-real-time-http-anomaly-detector-for-cloudng-with-python-nginx-docker-and-1d01

## Repository Structure

```text
detector/
  main.py
  monitor.py
  baseline.py
  detector.py
  blocker.py
  unbanner.py
  notifier.py
  dashboard.py
  config.py
  config.yaml
  requirements.txt
nginx/
  nginx.conf
scripts/
docs/
screenshots/
docker-compose.yml
README.md
```

## Architecture Summary

The stack has three main runtime services:

1. `nginx`
2. `nextcloud`
3. `detector`

Traffic flow:

```text
Client -> Nginx -> Nextcloud
              \
               -> JSON access logs -> Detector -> iptables / Slack / Dashboard
```

Shared named volume:

- `HNG-nginx-logs`

Purpose:

- Nginx writes JSON access logs into the shared volume
- Nextcloud mounts the volume read-only
- Detector mounts the volume read-only and tails the log continuously

## Why Python

Python was chosen because the detector is mostly IO-bound and stateful:

- continuous log tailing
- in-memory deque tracking
- periodic baseline recalculation
- Slack webhook notifications
- a lightweight metrics dashboard

That made Python a practical choice for fast development and readable logic.

## What the Detector Does

For every request in the Nginx access log, the daemon extracts:

- `source_ip`
- `timestamp`
- `method`
- `path`
- `status`
- `response_size`

It then:

- updates a 60-second global request window
- updates a 60-second per-IP request window
- updates per-IP error windows for `4xx` and `5xx`
- feeds the baseline manager
- compares current rates to learned baselines
- blocks anomalous IPs with `iptables`
- sends Slack alerts
- automatically unbans IPs on a backoff schedule
- writes audit logs
- updates the dashboard

## Step-by-Step Setup Guide

### Step 1: Launch the Server

Create an Ubuntu VPS or EC2 instance with at least:

- `2 vCPU`
- `2 GB RAM`

For more stable burst testing, a larger instance is recommended.

Open these ports:

- `80/tcp` for Nginx / Nextcloud
- `8081/tcp` for the dashboard

### Step 2: Clone the Repository

```bash
git clone https://github.com/Patrickmbaza/hng14-stage3-devops-
cd hng14-stage3-devops-
```

### Step 3: Install Docker and Utilities

```bash
chmod +x scripts/*.sh
sudo ./scripts/bootstrap_ubuntu.sh
sudo usermod -aG docker $USER
newgrp docker
```

### Step 4: Create the Environment File

```bash
cp .env.example .env
nano .env
```

Set:

```env
SERVER_IP=54.90.137.142
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/replace/me
DETECTOR_NOTIFICATIONS_ENABLED=true
PROJECT_DIR=/home/ubuntu/hng14-stage3-devops-
```

### Step 5: Review Detector Configuration

Main runtime config:

- `detector/config.yaml`

Current tuned thresholds used for reliable evidence capture:

```yaml
thresholds:
  zscore: 2.0
  rate_multiplier: 3.0
  error_surge_multiplier: 2.0
  tightened_zscore: 1.5
  tightened_rate_multiplier: 2.0
```

Other notable settings:

- `sliding_window_seconds: 60`
- `baseline_window_seconds: 1800`
- `recalc_interval_seconds: 60`
- `durations_minutes: [10, 30, 120]`

### Step 6: Start the Stack

```bash
./scripts/deploy_stack.sh up
docker compose ps
docker compose logs --tail=20 detector
```

You should see the detector start cleanly and the dashboard bind to port `8081`.

### Step 7: Verify Slack Wiring

```bash
docker exec -i hng-detector python - <<'PY'
import os
import requests

url = os.environ.get("SLACK_WEBHOOK_URL")
enabled = os.environ.get("DETECTOR_NOTIFICATIONS_ENABLED")

print("webhook set:", bool(url))
print("enabled:", enabled)

if url:
    r = requests.post(url, json={"text": "HNG detector Slack test"}, timeout=10)
    print("status:", r.status_code)
    print("body:", r.text)
PY
```

### Step 8: Verify Metrics

```bash
SERVER_IP=54.90.137.142 ./scripts/deploy_stack.sh metrics
```

The dashboard API should return JSON with:

- `global_rps`
- `global_baseline`
- `top_ips`
- `banned_ips`
- `hourly_slots`

## Nginx Reverse Proxy and JSON Logs

Nginx is configured in:

- `nginx/nginx.conf`

It:

- proxies requests to Nextcloud
- trusts `X-Forwarded-For`
- forwards real client IP information
- writes structured JSON access logs to:

```text
/var/log/nginx/hng-access.log
```

Minimum required log fields are present:

- `source_ip`
- `timestamp`
- `method`
- `path`
- `status`
- `response_size`

## Sliding Window Design

The detector uses real deque-based sliding windows, not a fixed per-minute counter.

Tracked windows:

- one global deque for all requests in the last 60 seconds
- one deque per IP for requests in the last 60 seconds
- one deque per IP for error responses in the last 60 seconds

Eviction rule:

```text
while timestamp < now - 60 seconds: pop from left
```

This keeps the calculated rate aligned with the latest moving 60-second interval.

## Rolling Baseline Design

The detector learns traffic behavior from live request data.

It stores:

- per-second request counts
- per-second error counts
- rolling 30-minute history
- hour-based baseline slots

Recalculation interval:

- every `60 seconds`

Preference order:

1. current hour slot if enough samples exist
2. fallback to rolling 30-minute history

Floor values protect the model from unstable math:

- `minimum_mean_rps`
- `minimum_stddev_rps`
- `minimum_error_rate`

Idle seconds are included so the baseline reflects real quiet periods.

## Detection Logic

### Per-IP anomaly conditions

An IP is treated as anomalous if either condition fires first:

- z-score exceeds threshold
- current IP rate exceeds the configured multiplier of baseline mean

Current demo thresholds:

- `zscore > 2.0`
- `rate > 3.0x baseline`

### Global anomaly conditions

Global traffic is treated as anomalous if:

- global z-score exceeds threshold
- global request rate exceeds multiplier of global mean

Global anomalies generate Slack alerts only.

### Error surge tightening

If an IP’s `4xx/5xx` error rate becomes much worse than its normal baseline, thresholds are tightened automatically.

## Blocking and Unbanning

When a per-IP anomaly is confirmed, the detector inserts:

```bash
iptables -I INPUT -s <ip> -j DROP
```

Unban schedule:

1. first offense: `10 minutes`
2. second offense: `30 minutes`
3. third offense: `2 hours`
4. fourth offense onward: permanent

## Whitelist Support

To prevent admin lockout, the detector supports:

```yaml
blocking:
  whitelist_ips:
    - "102.90.100.200"
```

Any IP in this list is excluded from per-IP banning. Global alerts still work.

## Audit Logging

Audit log path:

- `detector/audit.log`

Format:

```text
[timestamp] ACTION ip | condition | rate | baseline | duration
```

Examples:

```text
[2026-04-27T09:25:51.470829+00:00] BAN 3.89.119.100 | ip-rate>3.0x | 0.617 | 0.200 | 10m
[2026-04-27T09:35:51.650012+00:00] UNBAN 3.89.119.100 | ip-rate>3.0x | 0.617 | 0.200 | released
[2026-04-27T09:25:51.545036+00:00] GLOBAL_ALERT global | global-rate>3.0x | 0.617 | 0.200 | n/a
```

## iptables Snapshot Logging

To make ban evidence easier to capture, the detector also writes automatic `iptables` snapshots to:

- `detector/iptables_snapshot.log`

This records:

- `ACTION=BAN IP=...`
- `ACTION=UNBAN IP=...`
- the exact `iptables -L INPUT -n --line-numbers` output at that time

## Dashboard

Dashboard URL:

- `http://54.90.137.142:8081`

It shows:

- global requests per second
- CPU usage
- memory usage
- uptime
- top source IPs
- banned IPs
- effective baseline
- hourly baseline graph

## Validation Workflow Used

### Warm baseline lightly

```bash
SERVER_IP=54.90.137.142 ./scripts/external_attack.sh light 10 1
sleep 70
```

### Trigger a per-IP anomaly

```bash
SERVER_IP=54.90.137.142 ./scripts/external_attack.sh burst 120
```

### Trigger a global anomaly

```bash
SERVER_IP=54.90.137.142 ./scripts/external_attack.sh rounds 3 150 2
```

### Capture ban state

```bash
tail -n 20 detector/audit.log
tail -n 50 detector/iptables_snapshot.log
docker exec -it hng-detector iptables -L INPUT -n --line-numbers
```

## Required Screenshots

These are present in `screenshots/`:

1. `Tool-running.png`
2. `Ban-slack.png`
3. `Unban-slack.png`
4. `Global-alert-slack.png`
5. `Iptables-banned.png`
6. `Audit-log.png`
7. `Baseline-graph.png`

## Verification Summary

Verified in the repository:

- `README.md`
- `docker-compose.yml`
- `nginx/nginx.conf`
- `detector/config.yaml`
- `screenshots/Tool-running.png`
- `screenshots/Ban-slack.png`
- `screenshots/Unban-slack.png`
- `screenshots/Global-alert-slack.png`
- `screenshots/Iptables-banned.png`
- `screenshots/Audit-log.png`
- `screenshots/Baseline-graph.png`

Not yet valid for submission:

- `docs/architecture.png`

Current state of `docs/architecture.png`:

- placeholder 1x1 PNG

It must be replaced with a real architecture diagram before submission.

## Useful Commands

Start the stack:

```bash
./scripts/deploy_stack.sh up
```

Restart the stack:

```bash
./scripts/deploy_stack.sh restart
```

Show detector metrics:

```bash
SERVER_IP=54.90.137.142 ./scripts/deploy_stack.sh metrics
```

Show runtime status:

```bash
./scripts/run_validation.sh status
```

Find events for one IP:

```bash
./scripts/run_validation.sh grep-ip 3.89.119.100
```

## Final Submission Checklist

- Replace `REPLACE_WITH_PUBLIC_GITHUB_REPO`
- Replace `REPLACE_WITH_BLOG_POST_LINK`
- Replace `docs/architecture.png` with a real diagram
- Ensure all screenshots remain in `screenshots/`
- Keep `54.90.137.142` reachable during grading
- Keep `http://54.90.137.142:8081` reachable during grading
- Rotate the Slack webhook after submission because it was exposed during testing
