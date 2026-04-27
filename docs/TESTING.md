# Traffic Testing Cheat Sheet

This file contains simple copy-paste commands for generating HTTP traffic against the detector using either `curl` or Apache Benchmark (`ab`).

Target used below:

- `http://mbaza.duckdns.org/`

Important:

- Do not run per-IP attack traffic from your whitelisted admin IP.
- Use another public IP for burst testing if you want per-IP bans.

## Option 1: curl

### Warm the baseline

```bash
for i in $(seq 1 20); do curl -s -o /dev/null http://mbaza.duckdns.org/; sleep 1; done
```

### Wait for baseline recalculation

```bash
sleep 70
```

### Small per-IP burst

```bash
for i in $(seq 1 120); do curl -s -o /dev/null http://mbaza.duckdns.org/ & done; wait
```

### Stronger per-IP burst

```bash
for i in $(seq 1 200); do curl -s -o /dev/null http://mbaza.duckdns.org/ & done; wait
```

### Global spike pattern

Run this from one or more non-whitelisted public IPs:

```bash
for round in $(seq 1 3); do
  for i in $(seq 1 150); do curl -s -o /dev/null http://mbaza.duckdns.org/ & done
  wait
  sleep 2
done
```

## Option 2: Apache Benchmark

Install:

```bash
sudo apt-get update
sudo apt-get install -y apache2-utils
```

### Warm the baseline

```bash
ab -n 20 -c 1 http://mbaza.duckdns.org/
```

### Wait for baseline recalculation

```bash
sleep 70
```

### Per-IP burst

```bash
ab -n 120 -c 20 http://mbaza.duckdns.org/
```

### Stronger burst

```bash
ab -n 200 -c 30 http://mbaza.duckdns.org/
```

### Global spike

Run from multiple public IPs if possible:

```bash
ab -n 150 -c 20 http://mbaza.duckdns.org/
```

## Server-Side Evidence Checks

Run these on the server immediately after a burst:

```bash
tail -n 20 detector/audit.log
tail -n 50 detector/iptables_snapshot.log
docker exec -it hng-detector iptables -L INPUT -n --line-numbers
curl -s http://mbaza.duckdns.org:8081/api/metrics
```

## What You Want To See

- `BAN ...` in `detector/audit.log`
- `GLOBAL_ALERT ...` in `detector/audit.log` for global spikes
- `ACTION=BAN IP=...` in `detector/iptables_snapshot.log`
- `DROP` rule in live `iptables`
- Slack ban / unban / global alert notifications
