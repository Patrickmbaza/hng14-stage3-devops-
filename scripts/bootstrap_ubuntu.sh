#!/usr/bin/env bash

set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo ./scripts/bootstrap_ubuntu.sh" >&2
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl gnupg tmux jq
install -m 0755 -d /etc/apt/keyrings

if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
fi

if [[ ! -f /etc/apt/sources.list.d/docker.list ]]; then
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
fi

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "Bootstrap complete."
echo "Next:"
echo "  1. sudo usermod -aG docker <your-user>"
echo "  2. log out and back in"
echo "  3. cp .env.example .env"
echo "  4. edit .env and set SLACK_WEBHOOK_URL"
echo "  5. ./scripts/deploy_stack.sh up"
