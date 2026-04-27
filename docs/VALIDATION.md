# Validation Runbook

This file gives you one place to run the detector validation commands during testing and screenshot capture.

## File Added

- `scripts/run_validation.sh`
- `scripts/external_attack.sh`
- `scripts/bootstrap_ubuntu.sh`
- `scripts/deploy_stack.sh`
- `scripts/open_watchers.sh`
- `scripts/capture_evidence.sh`
- `scripts/full_runbook.sh`

## Before You Start

Make sure:

1. the stack is running
2. the detector container is healthy
3. Slack webhook is configured if you want alert screenshots

Start the stack if needed:

```bash
cd ~/hng14-stage3-devops-
cp .env.example .env
nano .env
./scripts/deploy_stack.sh up
```

## Make The Script Executable

```bash
cd ~/hng14-stage3-devops-
chmod +x scripts/run_validation.sh
chmod +x scripts/external_attack.sh
chmod +x scripts/bootstrap_ubuntu.sh
chmod +x scripts/deploy_stack.sh
chmod +x scripts/open_watchers.sh
chmod +x scripts/capture_evidence.sh
chmod +x scripts/full_runbook.sh
```

## Basic Usage

```bash
./scripts/run_validation.sh help
```

For external traffic generation from your laptop or another machine:

```bash
./scripts/external_attack.sh help
```

For the end-to-end server workflow:

```bash
./scripts/full_runbook.sh
```

## Useful Commands

Show a quick status snapshot:

```bash
./scripts/run_validation.sh status
```

Send light baseline traffic from the current machine:

```bash
./scripts/run_validation.sh light-traffic
```

Send a burst from the current machine:

```bash
./scripts/run_validation.sh burst
```

Print current dashboard metrics:

```bash
./scripts/run_validation.sh metrics
```

Show last 50 audit log lines:

```bash
./scripts/run_validation.sh audit
```

Show current INPUT chain rules:

```bash
./scripts/run_validation.sh iptables
```

Watch INPUT rules live:

```bash
./scripts/run_validation.sh watch-iptables
```

Watch metrics live:

```bash
./scripts/run_validation.sh watch-metrics
```

Follow audit log live:

```bash
./scripts/run_validation.sh watch-audit
```

Follow detector logs live:

```bash
./scripts/run_validation.sh watch-logs
```

Find all audit entries for one IP:

```bash
./scripts/run_validation.sh grep-ip 102.90.99.80
```

## Recommended Screenshot Workflow

Open four terminals on the server.

Fastest option:

```bash
cd ~/hng14-stage3-devops-
./scripts/open_watchers.sh
tmux attach -t hng-watchers
```

Manual option:

Terminal 1:

```bash
cd ~/hng14-stage3-devops-
./scripts/run_validation.sh watch-logs
```

Terminal 2:

```bash
cd ~/hng14-stage3-devops-
./scripts/run_validation.sh watch-iptables
```

Terminal 3:

```bash
cd ~/hng14-stage3-devops-
./scripts/run_validation.sh watch-metrics
```

Terminal 4:

```bash
cd ~/hng14-stage3-devops-
./scripts/run_validation.sh watch-audit
```

Then run traffic from an external client.

If you copied this repository to your laptop or another VPS, you can use the helper script there too.

### Light Traffic

Use this first to warm the baseline:

```bash
./scripts/external_attack.sh light
```

### Single-IP Burst

Run this from one external IP to trigger a ban:

```bash
./scripts/external_attack.sh burst
```

### Global Spike

Run the same burst from multiple external machines at the same time to trigger a global anomaly.

Example:

```bash
./scripts/external_attack.sh rounds 5 300 2
```

Run it on multiple clients in parallel for a stronger global spike.

## Capture Evidence Files

To dump logs, INPUT rules, audit lines, and metrics into a timestamped folder:

```bash
cd ~/hng14-stage3-devops-
./scripts/capture_evidence.sh
```

Output goes to:

```text
artifacts/YYYYMMDD-HHMMSS/
```

## Important Note

For real grading evidence, use an external client.

If you generate attack traffic from the EC2 instance itself, the source IP may appear as the server's own public IP, which is not ideal for demonstrating per-client blocking.

## Expected Evidence

During a live per-IP anomaly, you should see:

- detector log entries in Terminal 1
- the blocked IP appear in `iptables` in Terminal 2
- `banned_ips` become non-empty in Terminal 3
- a `BAN` line in the audit log in Terminal 4
- a Slack ban alert if configured

Later, after the backoff duration:

- the IP disappears from `iptables`
- a `UNBAN` line appears in the audit log
- a Slack unban alert appears
