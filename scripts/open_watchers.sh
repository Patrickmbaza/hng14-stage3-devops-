#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SESSION_NAME="${SESSION_NAME:-hng-watchers}"
SERVER_IP="${SERVER_IP:-3.237.26.140}"
AUDIT_LOG="${AUDIT_LOG:-$PROJECT_DIR/detector/audit.log}"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is required. Install it first." >&2
  exit 1
fi

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "Session already exists: $SESSION_NAME"
  echo "Attach with: tmux attach -t $SESSION_NAME"
  exit 0
fi

tmux new-session -d -s "$SESSION_NAME" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION_NAME":0.0 "docker compose logs -f detector" C-m

tmux split-window -h -t "$SESSION_NAME":0 -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION_NAME":0.1 "watch -n 1 'docker exec hng-detector iptables -L INPUT -n --line-numbers'" C-m

tmux split-window -v -t "$SESSION_NAME":0.0 -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION_NAME":0.2 "watch -n 1 'curl -s http://$SERVER_IP:8081/api/metrics | jq .'" C-m

tmux split-window -v -t "$SESSION_NAME":0.1 -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION_NAME":0.3 "tail -f '$AUDIT_LOG'" C-m

tmux select-layout -t "$SESSION_NAME":0 tiled

echo "Watcher session created: $SESSION_NAME"
echo "Attach with: tmux attach -t $SESSION_NAME"
