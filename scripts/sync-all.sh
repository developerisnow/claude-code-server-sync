#!/bin/bash
# Sync all server-to-mac projects automatically
# Used by LaunchAgent for scheduled sync

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[$(date)] Starting automatic sync..."

# Get list of projects with server-to-mac sync mode
python3 sync.py list | grep -E "\[server-to-mac\]|\[bidirectional\]" | awk '{print $2}' | while read -r project; do
    if [ -n "$project" ]; then
        echo "  → Syncing $project..."
        python3 sync.py pull "$project" 2>&1
    fi
done

echo "[$(date)] Sync completed"
