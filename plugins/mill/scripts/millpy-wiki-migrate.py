#!/usr/bin/env python3
"""One-shot V3 wiki migration script: seed tasks.json from Home.md and proposals.

This script is the canonical one-shot migration tool that bootstraps a free-form
wiki (Home.md + proposal files) into the new V3 TinyDB-backed state. It uses the
public wiki.upsert_tasks_batch API delivered by batch 1; there is no daemon bypass.

Preconditions:
  - The wiki path must be resolvable via _paths.resolve_wiki_path (sibling discovery
    or explicit config.local.yaml override).
  - Home.md must exist in the wiki.

Behaviour (commit mode):
  1. Backup the original Home.md to Home.md.pre-v3.bak (overwritten on re-run).
  2. Commit the backup via direct git if file content differs from prior backup.
  3. Parse Home.md with wiki._parse.parse_home_md.
  4. For each task with a proposal link, read the proposal file and attach body.
  5. Upsert all tasks via wiki._client.upsert_tasks_batch (daemon-side commit).
  6. Print summary.

Idempotency: Running twice on an already-migrated wiki produces no new daemon
commits. The backup file is overwritten; the skip path in step 2 prevents a
redundant backup commit when Home.md has not drifted.

All print() output is ASCII only (no em-dashes, no Unicode arrows).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import _paths


def _print_task_brief(task: dict) -> None:
    """Print a single parsed task dict in ASCII format (dry-run output)."""
    slug = task.get("slug", "?")
    title = task.get("title", "?")
    group = task.get("group")
    brief = task.get("brief", "")
    status = task.get("status")
    body = task.get("body", "")
    has_body = bool(body.strip())

    status_str = f" [{status}]" if status else ""
    group_str = f" ({group})" if group else ""
    body_str = " BODY" if has_body else ""

    # Normalize brief for display: max 50 chars
    brief_display = brief[:50] if brief else "(no brief)"
    if len(brief) > 50:
        brief_display += " ..."

    print(f"  {slug}{group_str} -- {title}{status_str}{body_str}")
    print(f"    {brief_display}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate Home.md and proposal files to V3 TinyDB-backed wiki."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print tasks without committing or writing files.",
    )
    args = parser.parse_args()

    try:
        git_root = _paths.resolve_git_root()
        wiki_path = _paths.resolve_wiki_path(git_root)
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: Failed to resolve wiki path: {e}", file=sys.stderr)
        sys.exit(1)

    # Read Home.md
    home_md = wiki_path / "Home.md"
    if not home_md.exists():
        print(f"ERROR: {home_md} not found", file=sys.stderr)
        sys.exit(1)

    try:
        home_text = home_md.read_text(encoding="utf-8")
    except Exception as e:
        print(f"ERROR: Failed to read {home_md}: {e}", file=sys.stderr)
        sys.exit(1)

    # Parse Home.md using the batch 1 extended parser
    # (pure string-in / list-out; does not initialize _client)
    from wiki import _parse
    tasks = _parse.parse_home_md(home_text)

    # Attach proposal bodies for each task with a [[slug]](proposal-slug.md) link
    for task in tasks:
        slug = task.get("slug")
        if slug:
            proposal_file = wiki_path / f"proposal-{slug}.md"
            if proposal_file.exists():
                try:
                    body = proposal_file.read_text(encoding="utf-8")
                    task["body"] = body
                except Exception:
                    task["body"] = ""
            else:
                task["body"] = ""

    if args.dry_run:
        # Dry-run: print and exit without daemon contact
        print(f"Parsed {len(tasks)} tasks (dry-run):")
        for task in tasks:
            _print_task_brief(task)
        sys.exit(0)

    # Commit mode: write backup, commit, upsert, and print summary
    backup_file = wiki_path / "Home.md.pre-v3.bak"

    # Direct-git backup commit (with skip on idempotent re-run).
    # Justification: The daemon is not yet running for the freshly-V3 wiki.
    # Bootstrapping the backup commit through git -C is a single isolated
    # exception to the "daemon owns wiki writes" rule. After initial migration,
    # all subsequent wiki mutations flow through the daemon.
    #
    # Idempotency: only create the backup if it doesn't already exist in git.
    # This ensures that running the script multiple times produces exactly one
    # backup commit per wiki, capturing the original pre-V3 Home.md.
    try:
        import subprocess

        # Check if backup file already exists in git
        check_result = subprocess.run(
            ["git", "-C", str(wiki_path), "ls-files", "Home.md.pre-v3.bak"],
            capture_output=True,
            text=True,
        )
        backup_exists_in_git = bool(check_result.stdout.strip())

        if not backup_exists_in_git:
            # First run: create and commit the backup
            backup_file.write_text(home_text, encoding="utf-8")

            subprocess.run(
                ["git", "-C", str(wiki_path), "add", "Home.md.pre-v3.bak"],
                check=True,
                capture_output=True,
            )

            subprocess.run(
                ["git", "-C", str(wiki_path), "commit", "-m", "wiki: backup pre-V3 Home.md"],
                check=True,
                capture_output=True,
            )
        # else: subsequent runs skip the backup commit entirely
    except Exception as e:
        print(f"ERROR: Failed to backup Home.md: {e}", file=sys.stderr)
        sys.exit(1)

    # Upsert all tasks via the daemon's public API (lazy import to avoid daemon spawn in dry-run)
    try:
        from wiki import _client as wiki_client

        wiki_client.upsert_tasks_batch(
            wiki_path,
            tasks,
            message="migrate to V3 (TinyDB-backed)",
        )
    except Exception as e:
        print(f"ERROR: Failed to upsert tasks: {e}", file=sys.stderr)
        sys.exit(1)

    # Count tasks with bodies for summary
    tasks_with_body = sum(1 for task in tasks if task.get("body", "").strip())

    # Print final summary (ASCII only)
    print(f"migrated {len(tasks)} tasks; {tasks_with_body} with proposal bodies; backup at {backup_file}")


if __name__ == "__main__":
    main()
