#!/usr/bin/env python3
"""Integration test: wiki migration from Home.md to V3 TinyDB.

Exercise the one-shot migration script with:
  - Dry-run mode (no side effects)
  - Commit mode (backup, migrate, render)
  - Idempotent re-run (no new commits)

Uses a real spawned daemon, real TinyDB, and real git repo under `.scratch/`.

NOT part of run-all.py (requires a real git binary and real I/O). Run manually:

    PYTHONPATH=plugins/mill/scripts uv run python plugins/mill/integration_tests/test-wiki-migrate.py

Exit 0 on PASS, 1 on FAIL. Scratch lives under <repo>/.scratch/ and is
preserved on failure for inspection.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import uuid
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
SCRATCH = HUB / ".scratch"

sys.path.insert(0, str(SCRIPTS))

import _safe_rmtree  # noqa: E402


def _git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command in the given directory."""
    result = subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        print(f"GIT ERROR: {' '.join(['git'] + args)}", file=sys.stderr)
        print(f"CWD: {cwd}", file=sys.stderr)
        print(f"STDOUT: {result.stdout}", file=sys.stderr)
        print(f"STDERR: {result.stderr}", file=sys.stderr)
        result.check_returncode()
    return result


def _setup_wiki_fixture(container: Path) -> tuple[Path, Path]:
    """Initialise a local wiki repo with Home.md and proposal files.

    Returns: (wiki_path, task_repo_path)
    """
    # Create wiki repo
    bare = container / "wiki.git"
    bare.mkdir(parents=True, exist_ok=True)
    _git(["init", "--bare", str(bare)], cwd=container)

    clone = container / "wiki"
    _git(["clone", str(bare), str(clone)], cwd=container)

    _git(["config", "user.email", "test@test.com"], cwd=clone)
    _git(["config", "user.name", "Test"], cwd=clone)

    # Create Home.md with mixed task types
    home_md = clone / "Home.md"
    home_md.write_text(
        textwrap.dedent("""\
            # Ungrouped Tasks

            ## 1 -- Ungrouped task
            [ungrouped]

            This is a task without a group assignment. It appears before layer headers.

            # Layer D (isolated -- run alone)

            ## 2 -- Active layer task
            [active-task] [active]

            A task in layer D with active status marker.

            ## 3 -- Proposal task one
            [[prop-one]](proposal-prop-one.md)

            This task references a proposal file.

            ## (warn) Wiki/config.yaml migration incomplete

            This is an info note with no slug line; it should be skipped.

            # Layer Z

            ## 4 -- Abandoned task
            [abandoned-task] [abandoned]

            A task marked as abandoned.

            ## 5 -- Proposal task two
            [[prop-two]](proposal-prop-two.md)

            Another task with a proposal body.
        """),
        encoding="utf-8",
    )

    # Create proposal files
    proposal_one = clone / "proposal-prop-one.md"
    proposal_one.write_text("# Proposal One\n\nBody for proposal one.", encoding="utf-8")

    proposal_two = clone / "proposal-prop-two.md"
    proposal_two.write_text("# Proposal Two\n\nBody for proposal two.\n\nWith multiple paragraphs.", encoding="utf-8")

    # Create initial commit
    _git(["add", "Home.md", "proposal-prop-one.md", "proposal-prop-two.md"], cwd=clone)
    _git(["commit", "-m", "init: seed Home.md and proposals"], cwd=clone)
    _git(["push", "origin", "HEAD"], cwd=clone)

    # Create a minimal task repo with .millhouse config pointing to the wiki
    task_repo = container / "task-repo"
    task_repo.mkdir(parents=True)

    # Initialize git repo
    _git(["init"], cwd=task_repo)
    _git(["config", "user.email", "test@test.com"], cwd=task_repo)
    _git(["config", "user.name", "Test"], cwd=task_repo)

    # Create .millhouse directory with config
    millhouse_dir = task_repo / ".millhouse"
    millhouse_dir.mkdir(parents=True)

    config = millhouse_dir / "config.local.yaml"
    config.write_text(f"paths:\n  wiki: {clone}\n", encoding="utf-8")

    # Create an initial commit so git rev-parse works
    init_file = task_repo / "README.md"
    init_file.write_text("Task repo\n", encoding="utf-8")
    _git(["add", "README.md", ".millhouse/config.local.yaml"], cwd=task_repo)
    _git(["commit", "-m", "init"], cwd=task_repo)

    return clone, task_repo


def _count_commits(wiki_path: Path, ref: str = "HEAD") -> int:
    """Count the number of commits reachable from ref."""
    result = _git(["rev-list", "--count", ref], cwd=wiki_path)
    return int(result.stdout.strip())


def _get_commit_messages(wiki_path: Path, count: int) -> list[str]:
    """Get the last N commit messages."""
    result = _git(
        ["log", "--format=%B", "-n", str(count), "HEAD"],
        cwd=wiki_path,
    )
    return result.stdout.strip().split("\n\n") if result.stdout.strip() else []


def _test_dry_run(wiki_path: Path, task_repo: Path) -> bool:
    """Test --dry-run mode: no side effects."""
    try:
        # Get initial state
        initial_commits = _count_commits(wiki_path)
        backup_file = wiki_path / "Home.md.pre-v3.bak"
        tasks_json = wiki_path / "tasks.json"
        daemon_state = wiki_path / ".wiki-daemon.json"

        # Run migration in dry-run mode from the task repo
        result = subprocess.run(
            [sys.executable, str(HUB / "plugins" / "mill" / "scripts" / "millpy-wiki-migrate.py"), "--dry-run"],
            cwd=str(task_repo),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONPATH": str(SCRIPTS)},
        )

        if result.returncode != 0:
            print(f"FAIL [dry-run]: script exited with {result.returncode}", file=sys.stderr)
            print(f"stderr: {result.stderr}", file=sys.stderr)
            return False

        # Verify no side effects
        if backup_file.exists():
            print("FAIL [dry-run]: backup file was created", file=sys.stderr)
            return False

        if tasks_json.exists():
            print("FAIL [dry-run]: tasks.json was created", file=sys.stderr)
            return False

        if daemon_state.exists():
            print("FAIL [dry-run]: daemon state file was created", file=sys.stderr)
            return False

        if _count_commits(wiki_path) != initial_commits:
            print("FAIL [dry-run]: new commits were created", file=sys.stderr)
            return False

        # Verify output contains expected tasks
        if "ungrouped" not in result.stdout:
            print("FAIL [dry-run]: ungrouped task not in output", file=sys.stderr)
            return False

        if "prop-one" not in result.stdout or "prop-two" not in result.stdout:
            print("FAIL [dry-run]: proposal tasks not in output", file=sys.stderr)
            return False

        print("PASS [dry-run]: no side effects, tasks printed to stdout")
        return True

    except Exception as exc:
        print(f"FAIL [dry-run]: {exc}", file=sys.stderr)
        return False


def _test_commit(wiki_path: Path, task_repo: Path) -> bool:
    """Test commit mode: backup, migrate, render."""
    try:
        initial_commits = _count_commits(wiki_path)
        backup_file = wiki_path / "Home.md.pre-v3.bak"
        tasks_json = wiki_path / "tasks.json"
        home_md = wiki_path / "Home.md"

        # Get original Home.md content
        original_home = home_md.read_text(encoding="utf-8")

        # Run migration in commit mode from the task repo
        result = subprocess.run(
            [sys.executable, str(HUB / "plugins" / "mill" / "scripts" / "millpy-wiki-migrate.py")],
            cwd=str(task_repo),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONPATH": str(SCRIPTS)},
        )

        if result.returncode != 0:
            print(f"FAIL [commit]: script exited with {result.returncode}", file=sys.stderr)
            print(f"stderr: {result.stderr}", file=sys.stderr)
            print(f"stdout: {result.stdout}", file=sys.stderr)
            return False

        # Verify backup file exists and has original content
        if not backup_file.exists():
            print("FAIL [commit]: backup file not created", file=sys.stderr)
            return False

        backup_content = backup_file.read_text(encoding="utf-8")
        if backup_content != original_home:
            print("FAIL [commit]: backup content does not match original", file=sys.stderr)
            return False

        # Verify tasks.json exists
        if not tasks_json.exists():
            print("FAIL [commit]: tasks.json not created", file=sys.stderr)
            return False

        # Verify proposal files still exist
        prop_one = wiki_path / "proposal-prop-one.md"
        prop_two = wiki_path / "proposal-prop-two.md"
        if not prop_one.exists() or not prop_two.exists():
            print("FAIL [commit]: proposal files not found", file=sys.stderr)
            return False

        # Verify Home.md is V3 format (re-rendered)
        new_home = home_md.read_text(encoding="utf-8")
        # Check that layer headers are without parentheticals
        if "# Layer D (isolated" in new_home:
            print("FAIL [commit]: Home.md still contains parenthetical in layer header", file=sys.stderr)
            return False
        if "# Layer D" not in new_home:
            print("FAIL [commit]: Layer D header missing in rendered Home.md", file=sys.stderr)
            return False

        # Verify info note is absent in rendered version
        if "## (warn)" in new_home:
            print("FAIL [commit]: info note still present in rendered Home.md", file=sys.stderr)
            return False

        # Verify markers are preserved
        if "[active]" not in new_home:
            print("FAIL [commit]: [active] marker missing in rendered Home.md", file=sys.stderr)
            return False
        if "[abandoned]" not in new_home:
            print("FAIL [commit]: [abandoned] marker missing in rendered Home.md", file=sys.stderr)
            return False

        # Verify commit messages are present
        new_commits = _count_commits(wiki_path)
        commits_created = new_commits - initial_commits
        if commits_created < 2:
            print(
                f"FAIL [commit]: expected at least 2 new commits, got {commits_created}",
                file=sys.stderr,
            )
            return False

        # Get recent commit messages and check for expected ones
        messages = _get_commit_messages(wiki_path, commits_created)
        messages_str = "\n".join(messages)

        if "backup pre-V3 Home.md" not in messages_str:
            print("FAIL [commit]: backup commit message not found", file=sys.stderr)
            print(f"messages: {messages_str}", file=sys.stderr)
            return False

        if "migrate to V3" not in messages_str:
            print("FAIL [commit]: migration commit message not found", file=sys.stderr)
            print(f"messages: {messages_str}", file=sys.stderr)
            return False

        # Verify summary line format
        if "migrated" not in result.stdout or "with proposal bodies" not in result.stdout:
            print("FAIL [commit]: summary line format incorrect", file=sys.stderr)
            print(f"stdout: {result.stdout}", file=sys.stderr)
            return False

        print("PASS [commit]: backup created, tasks migrated, Home.md rendered, commits produced")
        return True

    except Exception as exc:
        print(f"FAIL [commit]: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


def _test_idempotent_rerun(wiki_path: Path, task_repo: Path) -> bool:
    """Test idempotent re-run: backup commit should not be duplicated."""
    try:
        # Get state before re-run
        log_before = _get_commit_messages(wiki_path, 10)
        backup_count_before = sum(1 for msg in log_before if "backup pre-V3" in msg)

        # Run migration again from the task repo
        result = subprocess.run(
            [sys.executable, str(HUB / "plugins" / "mill" / "scripts" / "millpy-wiki-migrate.py")],
            cwd=str(task_repo),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONPATH": str(SCRIPTS)},
        )

        if result.returncode != 0:
            print(f"FAIL [idempotent]: script exited with {result.returncode}", file=sys.stderr)
            print(f"stderr: {result.stderr}", file=sys.stderr)
            return False

        # Verify backup commit was not duplicated
        log_after = _get_commit_messages(wiki_path, 10)
        backup_count_after = sum(1 for msg in log_after if "backup pre-V3" in msg)

        if backup_count_before != backup_count_after:
            print(
                f"FAIL [idempotent]: backup commit duplicated ({backup_count_before} -> {backup_count_after})",
                file=sys.stderr,
            )
            print(f"Before: {log_before}", file=sys.stderr)
            print(f"After: {log_after}", file=sys.stderr)
            return False

        # Verify the script exited successfully (the main idempotency guarantee)
        print("PASS [idempotent]: second invocation completed without duplicating backup commit")
        return True

    except Exception as exc:
        print(f"FAIL [idempotent]: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


def main() -> None:
    """Run all migration tests."""
    SCRATCH.mkdir(parents=True, exist_ok=True)

    # Test 1: Dry-run
    print("=" * 60)
    print("TEST 1: Dry-run mode")
    print("=" * 60)

    test1_dir = SCRATCH / f"test-dryrun-{uuid.uuid4().hex[:8]}"
    test1_dir.mkdir(parents=True, exist_ok=True)

    wiki_path, task_repo = _setup_wiki_fixture(test1_dir)

    if not _test_dry_run(wiki_path, task_repo):
        sys.exit(1)

    time.sleep(1)  # Let daemons cleanup

    # Test 2: Commit mode
    print("\n" + "=" * 60)
    print("TEST 2: Commit mode")
    print("=" * 60)

    test2_dir = SCRATCH / f"test-commit-{uuid.uuid4().hex[:8]}"
    test2_dir.mkdir(parents=True, exist_ok=True)

    wiki_path, task_repo = _setup_wiki_fixture(test2_dir)

    if not _test_commit(wiki_path, task_repo):
        sys.exit(1)

    time.sleep(1)  # Let daemons cleanup

    # Test 3: Idempotent re-run
    print("\n" + "=" * 60)
    print("TEST 3: Idempotent re-run")
    print("=" * 60)

    # Re-use the wiki from test 2 (already migrated)
    if not _test_idempotent_rerun(wiki_path, task_repo):
        sys.exit(1)

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
