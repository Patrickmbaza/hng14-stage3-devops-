#!/usr/bin/env bash

set -euo pipefail

SERVER_IP="${SERVER_IP:-3.237.26.140}"
PROJECT_DIR="${PROJECT_DIR:-$HOME/hng14-stage3-devops-}"
AUDIT_LOG="${AUDIT_LOG:-$PROJECT_DIR/detector/audit.log}"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/run_validation.sh <command>

Commands:
  status            Show detector logs, iptables, audit tail hint, and metrics
  light-traffic     Generate light traffic from this machine to warm the baseline
  burst             Generate a local burst from this machine
  metrics           Print dashboard API output
  audit             Show last 50 audit log lines
  iptables          Show INPUT chain rules from detector container
  watch-iptables    Watch INPUT chain rules live
  watch-metrics     Watch metrics endpoint live
  watch-audit       Tail audit log live
  watch-logs        Follow detector logs live
  grep-ip <ip>      Grep audit log entries for a specific IP

Notes:
  - For real single-IP ban testing, run traffic from an external client, not this EC2 box.
  - For global anomaly testing, run bursts from multiple external clients at the same time.
EOF
}

require_project() {
  if [[ ! -d "$PROJECT_DIR" ]]; then
    echo "Project directory not found: $PROJECT_DIR" >&2
    exit 1
  fi
}

compose() {
  docker compose -f "$PROJECT_DIR/docker-compose.yml" "$@"
}

cmd_status() {
  require_project
  echo "== detector logs (last 40) =="
  compose logs --tail=40 detector
  echo
  echo "== iptables INPUT chain =="
  docker exec hng-detector iptables -L INPUT -n --line-numbers
  echo
  echo "== audit log (last 20) =="
  tail -n 20 "$AUDIT_LOG" || true
  echo
  echo "== metrics =="
  curl -s "http://$SERVER_IP:8081/api/metrics"
  echo
}

cmd_light_traffic() {
  for _ in $(seq 1 20); do
    curl -s -o /dev/null "http://$SERVER_IP/"
    sleep 0.2
  done
  echo "Light traffic sent to http://$SERVER_IP/"
}

cmd_burst() {
  for _ in $(seq 1 400); do
    curl -s -o /dev/null "http://$SERVER_IP/" &
  done
  wait
  echo "Burst traffic sent to http://$SERVER_IP/"
}

cmd_metrics() {
  curl -s "http://$SERVER_IP:8081/api/metrics"
  echo
}

cmd_audit() {
  tail -n 50 "$AUDIT_LOG"
}

cmd_iptables() {
  docker exec hng-detector iptables -L INPUT -n --line-numbers
}

cmd_watch_iptables() {
  watch -n 1 "docker exec hng-detector iptables -L INPUT -n --line-numbers"
}

cmd_watch_metrics() {
  watch -n 1 "curl -s http://$SERVER_IP:8081/api/metrics"
}

cmd_watch_audit() {
  tail -f "$AUDIT_LOG"
}

cmd_watch_logs() {
  require_project
  compose logs -f detector
}

cmd_grep_ip() {
  if [[ $# -ne 1 ]]; then
    echo "Usage: ./scripts/run_validation.sh grep-ip <ip>" >&2
    exit 1
  fi
  grep "$1" "$AUDIT_LOG" || true
}

main() {
  local command="${1:-}"
  shift || true

  case "$command" in
    status) cmd_status ;;
    light-traffic) cmd_light_traffic ;;
    burst) cmd_burst ;;
    metrics) cmd_metrics ;;
    audit) cmd_audit ;;
    iptables) cmd_iptables ;;
    watch-iptables) cmd_watch_iptables ;;
    watch-metrics) cmd_watch_metrics ;;
    watch-audit) cmd_watch_audit ;;
    watch-logs) cmd_watch_logs ;;
    grep-ip) cmd_grep_ip "$@" ;;
    ""|-h|--help|help) usage ;;
    *)
      echo "Unknown command: $command" >&2
      echo
      usage
      exit 1
      ;;
  esac
}

main "$@"
