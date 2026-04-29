#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SERVER_IP="${SERVER_IP:-54.90.137.142}"
OUT_DIR="${OUT_DIR:-$PROJECT_DIR/artifacts/$(date +%Y%m%d-%H%M%S)}"
AUDIT_LOG="${AUDIT_LOG:-$PROJECT_DIR/detector/audit.log}"

mkdir -p "$OUT_DIR"

docker compose -f "$PROJECT_DIR/docker-compose.yml" logs --tail=200 detector > "$OUT_DIR/detector.log" || true
docker exec hng-detector iptables -L INPUT -n --line-numbers > "$OUT_DIR/iptables.txt" || true
tail -n 100 "$AUDIT_LOG" > "$OUT_DIR/audit.log" || true
curl -s "http://$SERVER_IP:8081/api/metrics" > "$OUT_DIR/metrics.json" || true
grep 'BAN ' "$AUDIT_LOG" > "$OUT_DIR/ban-events.log" || true
grep 'UNBAN ' "$AUDIT_LOG" > "$OUT_DIR/unban-events.log" || true
grep 'GLOBAL_ALERT ' "$AUDIT_LOG" > "$OUT_DIR/global-alerts.log" || true

echo "Evidence captured in $OUT_DIR"
