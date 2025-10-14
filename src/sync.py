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

SCRIPT_DIR = Path(__file__).parent.parent
CONFIG_FILE = SCRIPT_DIR / "config.json"
CONFIG_EXAMPLE = SCRIPT_DIR / "examples" / "config.example.json"
TEMP_DIR = "/tmp/claude-sync"


def load_config() -> Dict:
    """Load configuration from config.json or config.example.json"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    elif CONFIG_EXAMPLE.exists():
        print(f"⚠️  Using config.example.json. Copy to {CONFIG_FILE} to customize.")
        with open(CONFIG_EXAMPLE) as f:
            return json.load(f)
    else:
        print("❌ No config file found. Run 'sync.py setup' to create one")
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


def cmd_scan_server(config: Dict):
    """Scan server for available Claude projects"""
    print("\n🔍 Scanning server for Claude projects...\n")

    ssh_alias = config["ssh_alias"]
    server_path = config["paths"]["server"]["claude_projects"]

    cmd = ["ssh", ssh_alias, f"ls -1 {server_path}"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ Failed to scan server: {result.stderr}")
        sys.exit(1)

    projects = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]

    print(f"Found {len(projects)} projects on server:\n")
    for i, project in enumerate(projects, 1):
        print(f"  {i:2d}. {project}")

    return projects


def cmd_scan_local(config: Dict):
    """Scan local macOS for available Claude projects"""
    print("\n🔍 Scanning local macOS for Claude projects...\n")

    local_path = Path(config["paths"]["macos"]["claude_projects"])

    if not local_path.exists():
        print(f"❌ Path not found: {local_path}")
        sys.exit(1)

    projects = [p.name for p in local_path.iterdir() if p.is_dir() and not p.name.startswith('.')]
    projects.sort()

    print(f"Found {len(projects)} projects locally:\n")
    for i, project in enumerate(projects, 1):
        print(f"  {i:2d}. {project}")

    return projects


def cmd_setup():
    """Interactive setup wizard to create config.json"""
    print("\n🔧 Claude Code Sync - Setup Wizard\n")

    # Load example config as template
    if not CONFIG_EXAMPLE.exists():
        print(f"❌ Example config not found: {CONFIG_EXAMPLE}")
        sys.exit(1)

    with open(CONFIG_EXAMPLE) as f:
        config = json.load(f)

    print("Step 1: SSH Configuration")
    ssh_alias = input(f"  SSH alias [{config['ssh_alias']}]: ").strip() or config['ssh_alias']
    config['ssh_alias'] = ssh_alias

    # Test SSH connection
    print(f"\n  Testing connection to {ssh_alias}...")
    result = subprocess.run(["ssh", ssh_alias, "echo OK"], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ⚠️  SSH test failed. Make sure '{ssh_alias}' is configured in ~/.ssh/config")
    else:
        print("  ✓ SSH connection OK")

    print("\nStep 2: Scan Projects")
    print("\n  Scanning server...")
    server_projects = cmd_scan_server(config)

    print("\n  Scanning local macOS...")
    local_projects = cmd_scan_local(config)

    print("\nStep 3: Create Project Mappings")
    print("  Match server projects to local projects\n")

    config['projects'] = []

    for server_proj in server_projects:
        print(f"\n→ Server project: {server_proj}")
        print("  Options:")
        print("    [s] Skip")
        print("    [1-N] Match with local project number")
        print("    [m] Manually enter local project name")

        choice = input("  Choice: ").strip().lower()

        if choice == 's':
            continue
        elif choice == 'm':
            local_proj = input("  Enter local project name: ").strip()
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(local_projects):
                local_proj = local_projects[idx]
            else:
                print("  Invalid number, skipping")
                continue
        else:
            print("  Invalid choice, skipping")
            continue

        name = input(f"  Project nickname [{server_proj[:20]}]: ").strip() or server_proj[:20]

        sync_mode = input("  Sync mode (server-to-mac/mac-to-server/bidirectional) [server-to-mac]: ").strip() or "server-to-mac"

        config['projects'].append({
            "name": name,
            "server_dir": server_proj,
            "macos_dir": local_proj,
            "sync": sync_mode,
            "enabled": True
        })

        print(f"  ✓ Added: {name}")

    # Save config
    print(f"\n💾 Saving config to {CONFIG_FILE}...")
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"✅ Config created with {len(config['projects'])} projects")
    print(f"\nNext steps:")
    print(f"  1. Review: cat {CONFIG_FILE}")
    print(f"  2. Test: python3 src/sync.py list")
    print(f"  3. Pull: python3 src/sync.py pull <project-name>")


def cmd_test():
    """Test path transformation (removed - not needed in production)"""
    print("❌ Test command removed. Use 'setup' and 'pull' instead.")
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("""
Claude Code Server Sync

Usage:
  sync.py setup                    Interactive setup wizard (first time)
  sync.py scan server              Scan server for available projects
  sync.py scan local               Scan local macOS for projects
  sync.py list                     List configured projects
  sync.py pull <project-name>      Pull from server → macOS
  sync.py push <project-name>      Push from macOS → server (manual approve)

Examples:
  sync.py setup                    # First-time setup
  sync.py scan server              # List server projects
  sync.py list                     # List configured
  sync.py pull vibe-orchestrator   # Pull project
        """)
        sys.exit(1)

    command = sys.argv[1]

    if command == "setup":
        cmd_setup()

    elif command == "scan":
        if len(sys.argv) < 3 or sys.argv[2] not in ['server', 'local']:
            print("❌ Usage: sync.py scan [server|local]")
            sys.exit(1)

        config = load_config() if CONFIG_FILE.exists() else json.load(open(CONFIG_EXAMPLE))

        if sys.argv[2] == "server":
            cmd_scan_server(config)
        else:
            cmd_scan_local(config)

    elif command == "list":
        config = load_config()
        cmd_list(config)

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
        print("Run 'sync.py' without arguments for usage")
        sys.exit(1)


if __name__ == "__main__":
    main()
