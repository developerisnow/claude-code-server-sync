#!/usr/bin/env python3
"""Simple rsync-based synchronizer for Claude Code projects."""

from __future__ import annotations

import argparse
import json
import posixpath
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Sequence, Tuple

SCRIPT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = SCRIPT_ROOT / "config.json"
EXAMPLE_CONFIG = SCRIPT_ROOT / "examples" / "config.example.json"
VALID_MODES = {"pull", "push", "both"}


class SyncConfigError(RuntimeError):
    """Raised when the config file is missing or invalid."""


def load_config(config_path: Path) -> Dict:
    """Load config.json or fall back to the example configuration."""
    candidates: Sequence[Path] = [
        config_path.expanduser(),
        DEFAULT_CONFIG,
        EXAMPLE_CONFIG,
    ]

    for candidate in candidates:
        if candidate.exists():
            with candidate.open("r", encoding="utf-8") as handle:
                config = json.load(handle)
            validate_config(config)
            if candidate == EXAMPLE_CONFIG:
                print(
                    "⚠️  Using examples/config.example.json. "
                    "Copy it to config.json to customise projects.",
                    file=sys.stderr,
                )
            return config

    raise SyncConfigError(
        "No config.json found. Copy examples/config.example.json and update it."
    )


def validate_config(config: Dict) -> None:
    """Validate the minimal schema we rely on."""
    for key in ("ssh_alias", "paths", "projects"):
        if key not in config:
            raise SyncConfigError(f"Missing top-level key '{key}' in config.")

    paths = config["paths"]
    for key in ("macos_root", "server_root"):
        if key not in paths:
            raise SyncConfigError(f"Missing paths.{key} in config.")

    projects = config["projects"]
    if not isinstance(projects, list) or not projects:
        raise SyncConfigError("config.projects must contain at least one project.")

    seen_names = set()
    for project in projects:
        for required in ("name", "server_dir", "macos_dir"):
            if required not in project:
                raise SyncConfigError(
                    f"Project entry is missing '{required}': {project!r}"
                )

        mode = project.get("mode", "pull")
        if mode not in VALID_MODES:
            raise SyncConfigError(
                f"Invalid mode '{mode}' for project '{project['name']}'. "
                "Use pull, push or both."
            )

        if project["name"] in seen_names:
            raise SyncConfigError(f"Duplicate project name '{project['name']}'.")
        seen_names.add(project["name"])

    for rule in config.get("rewrite_rules", []):
        if "server" not in rule or "mac" not in rule:
            raise SyncConfigError(
                f"rewrite_rules entries require 'server' and 'mac': {rule!r}"
            )


def find_project(config: Dict, name: str) -> Dict:
    """Return a project dict by name."""
    for project in config["projects"]:
        if project["name"] == name:
            return project
    raise SyncConfigError(f"Project '{name}' not found in config.")


def project_paths(config: Dict, project: Dict) -> Tuple[Path, str]:
    """Return (local_path, server_path) for the project."""
    mac_root = Path(config["paths"]["macos_root"]).expanduser()
    server_root = config["paths"]["server_root"].rstrip("/")

    mac_path = mac_root / project["macos_dir"]
    server_path = posixpath.join(server_root, project["server_dir"].lstrip("/"))

    return mac_path, server_path


def iter_rules(
    rules: Iterable[Dict[str, str]], direction: str
) -> Iterator[Tuple[str, str]]:
    """Yield (source, destination) tuples sorted by source length."""
    if direction not in {"server_to_mac", "mac_to_server"}:
        raise ValueError(f"Unknown direction: {direction}")

    source_key = "server" if direction == "server_to_mac" else "mac"
    target_key = "mac" if direction == "server_to_mac" else "server"

    sorted_rules = sorted(
        rules,
        key=lambda item: len(item.get(source_key, "")),
        reverse=True,
    )

    for rule in sorted_rules:
        source = rule.get(source_key, "")
        target = rule.get(target_key, "")
        if not source or not target or source == target:
            continue
        yield source, target


def apply_rewrites(text: str, rules: Iterable[Dict[str, str]], direction: str) -> str:
    """Apply rewrite rules to a JSONL string."""
    updated = text
    for source, target in iter_rules(rules, direction):
        updated = updated.replace(source, target)
    return updated


def rewrite_jsonl_files(
    root: Path, rules: Iterable[Dict[str, str]], direction: str
) -> int:
    """Rewrite every *.jsonl file under root. Returns file count."""
    if not rules:
        return 0

    count = 0
    for jsonl_path in root.rglob("*.jsonl"):
        try:
            original = jsonl_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"⚠️  Skipping non-UTF8 file: {jsonl_path}", file=sys.stderr)
            continue

        transformed = apply_rewrites(original, rules, direction)
        if transformed != original:
            jsonl_path.write_text(transformed, encoding="utf-8")
        count += 1

    return count


def with_trailing_slash(value: str) -> str:
    """Ensure the path ends with a slash for rsync semantics."""
    return value if value.endswith("/") else f"{value}/"


def run_cmd(command: Sequence[str]) -> None:
    """Run a subprocess and raise on failure."""
    print("$ " + " ".join(shlex.quote(arg) for arg in command))
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: "
            f"{' '.join(shlex.quote(arg) for arg in command)}"
        )


def pull_project(config: Dict, project: Dict, dry_run: bool = False) -> None:
    """Sync server → mac for a single project."""
    mode = project.get("mode", "pull")
    if mode not in {"pull", "both"}:
        raise SyncConfigError(
            f"Project '{project['name']}' is configured as push-only."
        )

    mac_path, server_path = project_paths(config, project)
    ssh_alias = config["ssh_alias"]

    mac_path.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=f"claude-sync-{project['name']}-pull-"))
    try:
        remote_src = f"{ssh_alias}:{with_trailing_slash(server_path)}"
        local_temp = with_trailing_slash(str(temp_dir))

        pull_cmd = ["rsync", "-az", "--delete", remote_src, local_temp]
        if dry_run:
            pull_cmd.insert(1, "--dry-run")
        run_cmd(pull_cmd)

        transformed = rewrite_jsonl_files(
            temp_dir, config.get("rewrite_rules", []), "server_to_mac"
        )
        print(f"→ transformed {transformed} .jsonl file(s)")

        local_dest = with_trailing_slash(str(mac_path))
        push_cmd = ["rsync", "-a", "--delete", local_temp, local_dest]
        if dry_run:
            push_cmd.insert(1, "--dry-run")
        run_cmd(push_cmd)

        print(f"✓ pull complete: {project['name']} → {mac_path}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def push_project(
    config: Dict,
    project: Dict,
    *,
    confirm: bool = True,
    dry_run: bool = False,
) -> None:
    """Sync mac → server for a single project."""
    mode = project.get("mode", "pull")
    if mode not in {"push", "both"}:
        raise SyncConfigError(
            f"Project '{project['name']}' is configured as pull-only."
        )

    if confirm and not dry_run:
        response = input(
            f"Push local changes for '{project['name']}' to the server? [y/N]: "
        ).strip()
        if response.lower() not in {"y", "yes"}:
            print("Cancelled.")
            return

    mac_path, server_path = project_paths(config, project)
    if not mac_path.exists():
        raise SyncConfigError(
            f"Local directory for '{project['name']}' not found: {mac_path}"
        )

    ssh_alias = config["ssh_alias"]
    temp_dir = Path(tempfile.mkdtemp(prefix=f"claude-sync-{project['name']}-push-"))
    try:
        local_src = with_trailing_slash(str(mac_path))
        local_temp = with_trailing_slash(str(temp_dir))

        stage_cmd = ["rsync", "-a", "--delete", local_src, local_temp]
        if dry_run:
            stage_cmd.insert(1, "--dry-run")
        run_cmd(stage_cmd)

        transformed = rewrite_jsonl_files(
            temp_dir, config.get("rewrite_rules", []), "mac_to_server"
        )
        print(f"→ transformed {transformed} .jsonl file(s)")

        remote_dest = f"{ssh_alias}:{with_trailing_slash(server_path)}"
        push_cmd = ["rsync", "-az", "--delete", local_temp, remote_dest]
        if dry_run:
            push_cmd.insert(1, "--dry-run")
        run_cmd(push_cmd)

        print(f"✓ push complete: {project['name']} → {remote_dest}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def list_projects(config: Dict) -> None:
    """Print configured projects."""
    print("Configured projects:")
    for project in config["projects"]:
        mode = project.get("mode", "pull")
        mac_path, server_path = project_paths(config, project)
        print(f"- {project['name']} [{mode}]")
        print(f"  server: {server_path}")
        print(f"  mac:    {mac_path}")


def sync_all(config: Dict, dry_run: bool = False, include_push: bool = False) -> None:
    """Pull every project configured for pull/both. Optionally push bidirectional ones."""
    failures: List[Tuple[str, Exception]] = []

    for project in config["projects"]:
        if project.get("mode", "pull") not in {"pull", "both"}:
            continue
        try:
            pull_project(config, project, dry_run=dry_run)
        except Exception as exc:  # noqa: BLE001 - collect all failures
            failures.append((project["name"], exc))

    if include_push:
        for project in config["projects"]:
            if project.get("mode", "pull") != "both":
                continue
            try:
                push_project(config, project, confirm=False, dry_run=dry_run)
            except Exception as exc:  # noqa: BLE001 - collect all failures
                failures.append((project["name"], exc))

    if failures:
        print("⚠️  sync-all completed with errors:", file=sys.stderr)
        for name, exc in failures:
            print(f"  - {name}: {exc}", file=sys.stderr)
        raise RuntimeError("sync-all failed for one or more projects.")


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Sync Claude Code projects between macOS and server using rsync."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to config.json (defaults to repo config.json or the example).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pass --dry-run to rsync commands.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List configured projects.")

    pull_parser = subparsers.add_parser(
        "pull", help="Pull a project from the server to macOS."
    )
    pull_parser.add_argument("project", help="Project name defined in config.json.")

    push_parser = subparsers.add_parser(
        "push", help="Push a project from macOS to the server."
    )
    push_parser.add_argument("project", help="Project name defined in config.json.")
    push_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt.",
    )

    sync_all_parser = subparsers.add_parser(
        "sync-all", help="Pull every project configured for pull/both."
    )
    sync_all_parser.add_argument(
        "--include-push",
        action="store_true",
        help="After pulling, also push bidirectional projects.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point used by CLI and tests."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except SyncConfigError as err:
        print(f"❌ {err}", file=sys.stderr)
        return 1

    try:
        if args.command == "list":
            list_projects(config)
        elif args.command == "pull":
            project = find_project(config, args.project)
            pull_project(config, project, dry_run=args.dry_run)
        elif args.command == "push":
            project = find_project(config, args.project)
            push_project(
                config,
                project,
                confirm=not (args.yes or args.dry_run),
                dry_run=args.dry_run,
            )
        elif args.command == "sync-all":
            sync_all(
                config,
                dry_run=args.dry_run,
                include_push=getattr(args, "include_push", False),
            )
        else:  # pragma: no cover
            parser.error("Unknown command.")
    except SyncConfigError as err:
        print(f"❌ {err}", file=sys.stderr)
        return 2
    except RuntimeError as err:
        print(f"❌ {err}", file=sys.stderr)
        return 3

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
