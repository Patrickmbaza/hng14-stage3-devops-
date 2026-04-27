#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

cat <<EOF
Automated Runbook

1. Bootstrap a fresh Ubuntu VPS:
   sudo $PROJECT_DIR/scripts/bootstrap_ubuntu.sh

2. Create your environment file:
   cp $PROJECT_DIR/.env.example $PROJECT_DIR/.env
   edit $PROJECT_DIR/.env

3. Start or restart the stack:
   $PROJECT_DIR/scripts/deploy_stack.sh up
   $PROJECT_DIR/scripts/deploy_stack.sh restart

4. Open the four live watcher panes:
   $PROJECT_DIR/scripts/open_watchers.sh
   tmux attach -t hng-watchers

5. From an external machine, generate traffic:
   SERVER_IP=3.237.26.140 $PROJECT_DIR/scripts/external_attack.sh light
   SERVER_IP=3.237.26.140 $PROJECT_DIR/scripts/external_attack.sh burst
   SERVER_IP=3.237.26.140 $PROJECT_DIR/scripts/external_attack.sh rounds 5 300 2

6. Capture proof files:
   $PROJECT_DIR/scripts/capture_evidence.sh

7. Check the output directory:
   ls -la $PROJECT_DIR/artifacts

Notes:
 - Use burst from one external machine for a per-IP block test.
 - Use rounds from multiple external machines at the same time for a global spike test.
 - Slack screenshots and browser screenshots still need to be captured manually.
EOF
