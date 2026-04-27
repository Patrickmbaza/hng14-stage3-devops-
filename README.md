# HNG Stage 3 DevSecOps Project

## Real-Time HTTP Anomaly Detection Engine for cloud.ng

This project deploys Nextcloud behind Nginx and adds a custom Python daemon that monitors Nginx access logs in real time, learns normal traffic patterns, detects anomalies, blocks abusive IPs with `iptables`, sends Slack alerts, and exposes a live metrics dashboard.

The supplied Nextcloud image is used exactly as required:

- `kefaslungu/hng-nextcloud`

## Live Details

- Server IP: `3.237.26.140`
- Metrics dashboard: `http://3.237.26.140:8081`
- Language: `Python`
- GitHub repository: `REPLACE_WITH_PUBLIC_GITHUB_REPO`
- Blog post: `REPLACE_WITH_BLOG_POST_LINK`

## Project Structure

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
```

## What The Detector Does

The detector continuously tails `/var/log/nginx/hng-access.log` and processes:

- source IP
- timestamp
- method
- path
- status code
- response size

It then:

- maintains deque-based 60-second sliding windows
- recalculates a rolling 30-minute baseline every 60 seconds
- prefers the current hour's baseline when enough samples exist
- detects anomalies using z-score and rate multiplier thresholds
- tightens thresholds when error rate surges
- blocks anomalous IPs with `iptables`
- unbans IPs on backoff intervals
- sends Slack alerts
- writes audit logs
- serves a live dashboard

## Step-By-Step Setup Guide

### Step 1: Launch Your AWS Server

Create an Ubuntu VPS or EC2 instance with at least:

- 2 vCPU
- 2 GB RAM

Open these ports in your security group:

- `80/tcp` for Nextcloud through Nginx
- `8081/tcp` for the live metrics dashboard

Attach a public IP or Elastic IP.

### Step 2: Clone The Repository

SSH into the server and clone the repository:

```bash
git clone REPLACE_WITH_PUBLIC_GITHUB_REPO
cd hng14-stage3-devops-
```

### Step 3: Bootstrap Docker And Helper Tools

Run the bootstrap script:

```bash
chmod +x scripts/*.sh
sudo ./scripts/bootstrap_ubuntu.sh
```

After that:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Step 4: Create The Environment File

Copy the example environment file:

```bash
cp .env.example .env
```

Open it:

```bash
nano .env
```

Update these values:

```env
SERVER_IP=3.237.26.140
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/replace/me
DETECTOR_NOTIFICATIONS_ENABLED=true
PROJECT_DIR=/home/ubuntu/hng14-stage3-devops-
```

### Step 5: Review Detector Configuration

Main detector settings are in:

- `detector/config.yaml`

This file contains:

- sliding window size
- rolling baseline window
- recalculation interval
- z-score threshold
- rate multiplier threshold
- error surge threshold
- block durations
- dashboard port
- Slack settings

Current key settings:

- sliding window: `60 seconds`
- baseline window: `30 minutes`
- recalculation interval: `60 seconds`
- z-score threshold: `3.0`
- rate multiplier threshold: `5.0x`

### Step 6: Start The Stack

Deploy the stack with:

```bash
./scripts/deploy_stack.sh up
```

This starts:

- `nextcloud`
- `nginx`
- `detector`

Check container status:

```bash
./scripts/deploy_stack.sh ps
```

### Step 7: Verify The Detector

Follow detector logs:

```bash
./scripts/deploy_stack.sh logs
```

Check the metrics API:

```bash
./scripts/deploy_stack.sh metrics
```

You can also test directly:

```bash
curl http://3.237.26.140:8081/api/metrics
```

### Step 8: Understand The Shared Nginx Log Volume

The required named Docker volume is:

```text
HNG-nginx-logs
```

It is mounted like this:

- Nginx writes logs to it
- Nextcloud mounts it read-only
- Detector mounts it read-only

Nginx writes JSON access logs to:

```text
/var/log/nginx/hng-access.log
```

### Step 9: Warm The Baseline

Before attack testing, send a little normal traffic from an external machine:

```bash
SERVER_IP=3.237.26.140 ./scripts/external_attack.sh light
```

Then check metrics:

```bash
./scripts/run_validation.sh metrics
```

You want to see:

- `global_baseline` populated
- `sample_count` increasing
- `hourly_slots` present

### Step 10: Open Live Watcher Panes

Start the automated watcher session:

```bash
./scripts/open_watchers.sh
tmux attach -t hng-watchers
```

This opens a 4-pane layout showing:

- detector logs
- `iptables` INPUT rules
- dashboard metrics
- audit log

### Step 11: Run A Single-IP Attack Test

From your laptop or another external machine, run:

```bash
SERVER_IP=3.237.26.140 ./scripts/external_attack.sh burst
```

What should happen:

- detector logs show repeated events
- the source IP appears in `iptables`
- audit log records a `BAN`
- Slack receives a ban alert
- dashboard shows the IP in `banned_ips`

### Step 12: Run A Global Spike Test

From multiple external machines at the same time, run:

```bash
SERVER_IP=3.237.26.140 ./scripts/external_attack.sh rounds 5 300 2
```

What should happen:

- global request rate spikes
- detector compares current rate against global baseline
- Slack receives a global anomaly alert
- audit log records `GLOBAL_ALERT`

Global anomalies send alerts only. They do not trigger bulk blocking.

### Step 13: Observe Auto-Unban

The unban schedule is:

1. first ban: `10 minutes`
2. second ban: `30 minutes`
3. third ban: `2 hours`
4. fourth offense onward: `permanent`

When an IP is released:

- the `iptables` rule is removed
- the audit log records `UNBAN`
- Slack receives an unban notification

### Step 14: Capture Evidence Files

To collect logs and runtime state into timestamped files:

```bash
./scripts/capture_evidence.sh
```

Files will be written to:

```text
artifacts/YYYYMMDD-HHMMSS/
```

This captures:

- detector logs
- `iptables` output
- recent audit log lines
- current metrics JSON
- extracted ban events
- extracted unban events
- extracted global alert events

### Step 15: Capture Required Screenshots

You still need to capture browser and Slack screenshots manually.

Required screenshots:

1. `Tool-running.png`
2. `Ban-slack.png`
3. `Unban-slack.png`
4. `Global-alert-slack.png`
5. `Iptables-banned.png`
6. `Audit-log.png`
7. `Baseline-graph.png`

Store them in:

- `screenshots/`

### Step 16: Replace Final Placeholders

Before submission, update:

- GitHub repo link in this README
- blog post link in this README
- dashboard URL if you later place it behind a domain
- `docs/architecture.png` with a real diagram

## How The Sliding Window Works

The detector uses real deque-based windows, not fixed per-minute buckets.

Data structures:

- `global_requests`
- `ip_requests[source_ip]`
- `ip_errors[source_ip]`

Each request timestamp is appended to a deque. Old values are evicted while:

```text
timestamp < now - 60 seconds
```

That means the calculated rate always reflects the most recent 60-second period.

## How The Baseline Works

The baseline is learned from live traffic and recalculated every 60 seconds.

It uses:

- per-second request counts
- per-second error counts
- a rolling 30-minute history
- hour-slot preference

The detector prefers the current hour's baseline when it has enough data. If not, it falls back to the rolling 30-minute window.

Floor values protect against unstable calculations:

- `minimum_mean_rps`
- `minimum_stddev_rps`
- `minimum_error_rate`

Idle seconds are included in the baseline so averages stay realistic.

## How Detection Decisions Are Made

Per-IP anomaly triggers:

- z-score > `3.0`
- current IP rate > `5x` baseline mean

Global anomaly triggers:

- z-score > `3.0`
- current global rate > `5x` global mean

Error surge tightening:

- if an IP's `4xx/5xx` rate becomes `3x` its baseline error rate, thresholds tighten automatically

## How Blocking Works

When an IP is anomalous, the detector inserts:

```bash
iptables -I INPUT -s <ip> -j DROP
```

When the ban period expires, the detector removes the rule automatically.

## Audit Log Format

Audit records are written as:

```text
[timestamp] ACTION ip | condition | rate | baseline | duration
```

Examples:

```text
[2026-04-25T16:22:14.153935+00:00] UNBAN 102.90.99.80 | ip-rate>5.0x | 1.500 | 0.297 | released
```

## Useful Commands

Show overall status:

```bash
./scripts/run_validation.sh status
```

Watch detector logs:

```bash
./scripts/run_validation.sh watch-logs
```

Watch `iptables`:

```bash
./scripts/run_validation.sh watch-iptables
```

Watch metrics:

```bash
./scripts/run_validation.sh watch-metrics
```

Watch audit log:

```bash
./scripts/run_validation.sh watch-audit
```

Find all events for one IP:

```bash
./scripts/run_validation.sh grep-ip 102.90.99.80
```

Print the full runbook summary:

```bash
./scripts/full_runbook.sh
```

## Submission Checklist

- Nextcloud image unchanged
- Docker Compose deployment works
- Nginx reverse proxy enabled
- JSON logs enabled
- named volume `HNG-nginx-logs` present
- real client IP forwarded with `X-Forwarded-For`
- daemon continuously tails logs
- deque-based sliding windows implemented
- rolling baseline implemented
- hour-slot preference implemented
- anomaly detection implemented
- automatic `iptables` blocking implemented
- auto-unban schedule implemented
- Slack alerts implemented
- live metrics dashboard implemented
- audit log implemented
- screenshots captured
- blog post published

