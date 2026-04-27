#!/usr/bin/env bash

set -euo pipefail

SERVER_IP="${SERVER_IP:-3.237.26.140}"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/external_attack.sh <command> [options]

Commands:
  light [count] [delay_seconds]
      Send light traffic sequentially.
      Defaults: count=20 delay=0.2

  burst [count]
      Send a one-shot concurrent burst from this client IP.
      Default: count=400

  rounds [rounds] [count] [sleep_seconds]
      Send multiple concurrent bursts with pauses between rounds.
      Defaults: rounds=3 count=300 sleep=3

Examples:
  ./scripts/external_attack.sh light
  ./scripts/external_attack.sh light 30 0.1
  ./scripts/external_attack.sh burst
  ./scripts/external_attack.sh burst 600
  ./scripts/external_attack.sh rounds 5 250 2

Environment overrides:
  SERVER_IP=3.237.26.140
EOF
}

request_once() {
  curl -s -o /dev/null "http://$SERVER_IP/"
}

cmd_light() {
  local count="${1:-20}"
  local delay="${2:-0.2}"

  for _ in $(seq 1 "$count"); do
    request_once
    sleep "$delay"
  done

  echo "Sent $count light requests to http://$SERVER_IP/"
}

cmd_burst() {
  local count="${1:-400}"

  for _ in $(seq 1 "$count"); do
    request_once &
  done
  wait

  echo "Sent burst of $count concurrent requests to http://$SERVER_IP/"
}

cmd_rounds() {
  local rounds="${1:-3}"
  local count="${2:-300}"
  local sleep_seconds="${3:-3}"

  for round in $(seq 1 "$rounds"); do
    echo "Round $round/$rounds: sending $count requests"
    for _ in $(seq 1 "$count"); do
      request_once &
    done
    wait
    if [[ "$round" -lt "$rounds" ]]; then
      sleep "$sleep_seconds"
    fi
  done

  echo "Completed $rounds rounds against http://$SERVER_IP/"
}

main() {
  local command="${1:-}"
  shift || true

  case "$command" in
    light) cmd_light "$@" ;;
    burst) cmd_burst "$@" ;;
    rounds) cmd_rounds "$@" ;;
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
