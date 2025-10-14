#!/usr/bin/env python3
"""
Claude Code Server Sync Tool
Syncs .jsonl files between server and macOS with path transformation
"""

import json
import re
import subprocess
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple

CONFIG_FILE = "config.json"
TEMP_DIR = "/tmp/claude-sync"


def load_config() -> Dict:
    """Load configuration from config.json or config.example.json"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    elif os.path.exists("config.example.json"):
        print(f"⚠️  Using config.example.json. Copy to {CONFIG_FILE} to customize.")
        with open("config.example.json") as f:
            return json.load(f)
    else:
        print("❌ No config file found. Create config.json or config.example.json")
        sys.exit(1)


def get_project_by_name(config: Dict, name: str) -> Dict:
    """Find project configuration by name"""
    for project in config["projects"]:
        if project["name"] == name and project.get("enabled", True):
            return project
    print(f"❌ Project '{name}' not found or disabled")
    sys.exit(1)


def build_replacements(config: Dict, direction: str) -> List[Tuple[str, str]]:
    """Build path replacement patterns based on sync direction"""
    paths = config["paths"]

    if direction == "server-to-mac":
        return [
            # Escaped paths (project names)
            (paths["server"]["temp_escaped"], paths["macos"]["temp_escaped"]),
            # Absolute paths
            (paths["server"]["temp_base"], paths["macos"]["temp_base"]),
            (paths["server"]["claude_projects"], paths["macos"]["claude_projects"]),
        ]
    else:  # mac-to-server
        return [
            # Escaped paths (project names)
            (paths["macos"]["temp_escaped"], paths["server"]["temp_escaped"]),
            # Absolute paths
            (paths["macos"]["temp_base"], paths["server"]["temp_base"]),
            (paths["macos"]["claude_projects"], paths["server"]["claude_projects"]),
        ]


def transform_jsonl_content(content: str, replacements: List[Tuple[str, str]]) -> str:
    """Transform paths in JSONL content"""
    result = content
    for old_path, new_path in replacements:
        # Escape special regex characters
        old_escaped = re.escape(old_path)
        result = re.sub(old_escaped, new_path, result)
    return result


def sync_pull(config: Dict, project: Dict):
    """Pull project from server to macOS"""
    print(f"📥 Pulling '{project['name']}' from server...")

    ssh_alias = config["ssh_alias"]
    server_path = f"{config['paths']['server']['claude_projects']}/{project['server_dir']}"
    local_path = f"{config['paths']['macos']['claude_projects']}/{project['macos_dir']}"

    # Create temp directory
    temp_dir = f"{TEMP_DIR}/{project['name']}"
    os.makedirs(temp_dir, exist_ok=True)

    # Step 1: rsync from server to temp
    print(f"  → rsync {ssh_alias}:{server_path}")
    cmd = ["rsync", "-avz", f"{ssh_alias}:{server_path}/", temp_dir]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ rsync failed: {result.stderr}")
        sys.exit(1)

    # Step 2: Transform paths in all .jsonl files
    print(f"  → Transforming paths...")
    replacements = build_replacements(config, "server-to-mac")
    jsonl_files = list(Path(temp_dir).glob("*.jsonl"))

    for jsonl_file in jsonl_files:
        with open(jsonl_file, 'r') as f:
            content = f.read()

        transformed = transform_jsonl_content(content, replacements)

        with open(jsonl_file, 'w') as f:
            f.write(transformed)

    print(f"  ✓ Transformed {len(jsonl_files)} files")

    # Step 3: Copy to final location
    os.makedirs(local_path, exist_ok=True)
    cmd = ["rsync", "-av", f"{temp_dir}/", local_path]
    subprocess.run(cmd, check=True, capture_output=True)

    print(f"✅ Synced to {local_path}")


def sync_push(config: Dict, project: Dict):
    """Push project from macOS to server"""
    if project["sync"] == "server-to-mac":
        print(f"⚠️  Project '{project['name']}' is configured as read-only (server-to-mac)")
        confirm = input("Push anyway? (yes/no): ")
        if confirm.lower() != "yes":
            print("Cancelled.")
            return

    print(f"📤 Pushing '{project['name']}' to server...")

    ssh_alias = config["ssh_alias"]
    local_path = f"{config['paths']['macos']['claude_projects']}/{project['macos_dir']}"
    server_path = f"{config['paths']['server']['claude_projects']}/{project['server_dir']}"

    # Create temp directory
    temp_dir = f"{TEMP_DIR}/{project['name']}-push"
    os.makedirs(temp_dir, exist_ok=True)

    # Step 1: Copy local to temp
    cmd = ["rsync", "-av", f"{local_path}/", temp_dir]
    subprocess.run(cmd, check=True, capture_output=True)

    # Step 2: Transform paths
    print(f"  → Transforming paths...")
    replacements = build_replacements(config, "mac-to-server")
    jsonl_files = list(Path(temp_dir).glob("*.jsonl"))

    for jsonl_file in jsonl_files:
        with open(jsonl_file, 'r') as f:
            content = f.read()

        transformed = transform_jsonl_content(content, replacements)

        with open(jsonl_file, 'w') as f:
            f.write(transformed)

    print(f"  ✓ Transformed {len(jsonl_files)} files")

    # Step 3: rsync to server
    print(f"  → rsync to {ssh_alias}:{server_path}")
    cmd = ["rsync", "-avz", f"{temp_dir}/", f"{ssh_alias}:{server_path}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ rsync failed: {result.stderr}")
        sys.exit(1)

    print(f"✅ Pushed to server")


def cmd_list(config: Dict):
    """List all configured projects"""
    print("\n📋 Configured Projects:\n")
    for project in config["projects"]:
        status = "✓" if project.get("enabled", True) else "✗"
        sync_mode = project["sync"]
        print(f"  {status} {project['name']:<20} [{sync_mode}]")
        print(f"    Server: {project['server_dir']}")
        print(f"    MacOS:  {project['macos_dir']}\n")


def cmd_test():
    """Test path transformation on sample file"""
    print("\n🧪 Testing path transformation...\n")

    if not os.path.exists("test_sample.jsonl"):
        print("❌ test_sample.jsonl not found")
        sys.exit(1)

    config = load_config()

    with open("test_sample.jsonl") as f:
        original = f.read()

    print("Original (server paths):")
    print(original)

    # Transform server → mac
    replacements_to_mac = build_replacements(config, "server-to-mac")
    transformed = transform_jsonl_content(original, replacements_to_mac)

    print("\n→ Transformed to macOS:")
    print(transformed)

    # Transform mac → server (roundtrip test)
    replacements_to_server = build_replacements(config, "mac-to-server")
    roundtrip = transform_jsonl_content(transformed, replacements_to_server)

    print("\n→ Roundtrip back to server:")
    print(roundtrip)

    if original == roundtrip:
        print("\n✅ Roundtrip test PASSED - transformations are reversible")
    else:
        print("\n⚠️  Roundtrip test FAILED - check your path mappings")
        print("\nDifferences:")
        import difflib
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            roundtrip.splitlines(keepends=True),
            fromfile='original',
            tofile='roundtrip'
        )
        print(''.join(diff))


def main():
    if len(sys.argv) < 2:
        print("""
Claude Code Server Sync

Usage:
  sync.py pull <project-name>    Pull from server → macOS
  sync.py push <project-name>    Push from macOS → server (manual approve)
  sync.py list                   List configured projects
  sync.py test                   Test path transformation

Examples:
  sync.py pull vibe-orchestrator
  sync.py push memory-monorepo
  sync.py test
        """)
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        config = load_config()
        cmd_list(config)

    elif command == "test":
        cmd_test()

    elif command == "pull":
        if len(sys.argv) < 3:
            print("❌ Usage: sync.py pull <project-name>")
            sys.exit(1)

        config = load_config()
        project = get_project_by_name(config, sys.argv[2])
        sync_pull(config, project)

    elif command == "push":
        if len(sys.argv) < 3:
            print("❌ Usage: sync.py push <project-name>")
            sys.exit(1)

        config = load_config()
        project = get_project_by_name(config, sys.argv[2])
        sync_push(config, project)

    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
