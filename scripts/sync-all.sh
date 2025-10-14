#!/bin/bash
# Wrapper executed by a LaunchAgent to pull every configured project.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"

echo "[$TIMESTAMP] claude-code-sync :: starting pull cycle"

python3 "${REPO_ROOT}/src/sync.py" sync-all "$@"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] claude-code-sync :: done"
