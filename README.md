# HNG Stage 3: cloud.ng Anomaly Detection Engine

This project deploys a Nextcloud stack on AWS with Nginx in front, then runs a Python daemon that tails JSON access logs in real time, learns normal request behavior, and reacts to anomalies by alerting to Slack and blocking abusive IPs with `iptables`.

Server IP: `REPLACE_WITH_AWS_EIP`

Metrics dashboard URL: `https://metrics.example.com`

Blog post: `REPLACE_WITH_PUBLIC_BLOG_LINK`

GitHub repo: `REPLACE_WITH_PUBLIC_GITHUB_LINK`

## Why Python

I used Python because the detector has multiple IO-heavy tasks that are straightforward to compose: log tailing, deque-based sliding windows, rolling baseline math, Slack notifications, and a small live dashboard. Python also made it practical to keep the detection logic readable and heavily commented.

## Architecture

- `nginx/` contains the reverse proxy configuration with JSON access logs written to `/var/log/nginx/hng-access.log`.
- `detector/` contains the daemon, detector modules, and dashboard.
- `docker-compose.yml` starts Nextcloud from the required DockerHub image, Nginx, and the detector sidecar.
- `HNG-nginx-logs` is a named Docker volume shared across containers. Nginx writes to it. Nextcloud and the detector mount it read-only.

## Sliding Window Design

The detector uses deque-based sliding windows over the last 60 seconds:

- `global_requests`: one deque holding all request timestamps from the last minute.
- `ip_requests[source_ip]`: one deque per IP holding only that IP's timestamps from the last minute.
- `ip_errors[source_ip]`: one deque per IP for 4xx/5xx timestamps.

Each new request appends its timestamp. Old timestamps are evicted from the left side whenever they are older than `now - 60 seconds`. That means the live rate is always computed from actual events currently inside the window, not from a coarse per-minute bucket.

## Baseline Design

The baseline learns from live traffic rather than a fixed threshold:

- Per-second request counts are recorded continuously.
- A rolling 30-minute history is maintained.
- Baselines are recalculated every 60 seconds.
- Counts are also stored inside per-hour slots.
- If the current hour has enough samples (`min_hour_samples`), that hour slot is preferred.
- If it does not, the detector falls back to the rolling 30-minute history.
- Floor values protect against dividing by zero or unrealistically tiny baselines:
  - `minimum_mean_rps`
  - `minimum_stddev_rps`
  - `minimum_error_rate`

## Detection Logic

For both per-IP and global traffic, the daemon checks two conditions:

- z-score > `3.0`
- current rate > `5x` baseline mean

Whichever fires first triggers the anomaly.

For IPs, there is an extra error-surge rule:

- If the IP's 4xx/5xx rate is at least `3x` its learned baseline error rate, thresholds tighten automatically.
- Tightened values are controlled in `detector/config.yaml`.

Per-IP anomalies trigger:

- `iptables` DROP rule
- Slack ban alert within the monitoring loop
- Structured audit entry

Global anomalies trigger:

- Slack alert only
- Structured audit entry

## Auto-Unban Schedule

Ban duration escalates by repeat offense:

1. First ban: 10 minutes
2. Second ban: 30 minutes
3. Third ban: 2 hours
4. Fourth ban onward: permanent

Every unban sends a Slack notification and writes an audit record.

## Audit Log Format

All baseline recalculations, bans, and unbans are written as structured lines:

```text
[timestamp] ACTION ip | condition | rate | baseline | duration
```

Example:

```text
[2026-04-25T12:00:00+00:00] BAN 203.0.113.10 | ip-zscore>3.0 | rate=5.500 | baseline=0.700 | duration=10m
```

## Live Dashboard

The dashboard refreshes every 3 seconds and shows:

- banned IPs
- global requests per second
- top 10 source IPs
- CPU usage
- memory usage
- effective mean and stddev
- uptime
- hourly effective mean slots for the baseline graph screenshot

By default it runs on port `8081` inside the detector container. In production on AWS, place it behind a DNS record such as `metrics.example.com`.

## Repository Layout

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
docs/
  architecture.png
screenshots/
README.md
docker-compose.yml
```

## Fresh AWS VPS Setup

These steps assume an Ubuntu 24.04 EC2 instance with at least 2 vCPU and 2 GB RAM.

1. Launch an EC2 instance and attach an Elastic IP.
2. Open inbound security group rules for:
   - `80/tcp` for Nextcloud by IP
   - `443/tcp` if you terminate TLS in front of the dashboard with a separate reverse proxy
   - `8081/tcp` temporarily if you expose the dashboard directly during testing
3. Install Docker and Compose:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

4. Clone the repository and update:
   - `README.md` placeholders
   - `detector/config.yaml` with the real Slack webhook
   - dashboard DNS/proxy settings if using a custom domain
5. Start the stack:

```bash
docker compose up -d --build
```

6. Check the detector:

```bash
docker compose logs -f detector
curl http://SERVER_IP:8081/api/metrics
docker exec -it hng-detector iptables -L -n
```

## Required Screenshot Checklist

Capture these after deployment:

1. `screenshots/Tool-running.png`
2. `screenshots/Ban-slack.png`
3. `screenshots/Unban-slack.png`
4. `screenshots/Global-alert-slack.png`
5. `screenshots/Iptables-banned.png`
6. `screenshots/Audit-log.png`
7. `screenshots/Baseline-graph.png`

## Notes for Submission

- Keep the EC2 instance running for the required 12-hour window.
- Submit the live server IP and live metrics dashboard URL.
- Do not replace the `kefaslungu/hng-nextcloud` image.
- All thresholds live in `detector/config.yaml`.
- The detector code is custom and does not use Fail2Ban or rate-limiting libraries.
