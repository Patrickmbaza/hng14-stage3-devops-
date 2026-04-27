#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ENV_FILE="${ENV_FILE:-$PROJECT_DIR/.env}"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

usage() {
  cat <<'EOF'
Usage:
  ./scripts/deploy_stack.sh <command>

Commands:
  up        Build and start the stack
  down      Stop the stack
  restart   Rebuild and restart the stack
  ps        Show container status
  logs      Follow detector logs
  metrics   Fetch dashboard metrics
EOF
}

cmd_up() {
  compose up -d --build
}

cmd_down() {
  compose down
}

cmd_restart() {
  compose down
  compose up -d --build
}

cmd_ps() {
  compose ps
}

cmd_logs() {
  compose logs -f detector
}

cmd_metrics() {
  curl -s "http://${SERVER_IP}:8081/api/metrics"
  echo
}

case "${1:-}" in
  up) cmd_up ;;
  down) cmd_down ;;
  restart) cmd_restart ;;
  ps) cmd_ps ;;
  logs) cmd_logs ;;
  metrics) cmd_metrics ;;
  ""|-h|--help|help) usage ;;
  *)
    echo "Unknown command: ${1:-}" >&2
    usage
    exit 1
    ;;
esac
