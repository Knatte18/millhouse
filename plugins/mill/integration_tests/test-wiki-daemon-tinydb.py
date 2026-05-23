"""Integration test for wiki daemon with TinyDB persistence.

Tests the full client-daemon-git stack: real subprocess, real TinyDB,
real Home.md parsing/rendering. Covers read/write, task.json persistence,
and daemon restart recovery.

Uses .scratch/test-wiki-daemon-tinydb/ as fixture directory.
Exit 0 on all PASS, 1 on first FAIL.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
SCRATCH = HUB / ".scratch"

sys.path.insert(0, str(SCRIPTS))

import wiki._client as _client  # noqa: E402


def _git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
    """Run git command and return result."""
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _setup_wiki(container: Path) -> Path:
    """Initialize a real wiki repo (bare remote + working clone)."""
    bare = container / "wiki.git"
    bare.mkdir(parents=True, exist_ok=True)
    _git(["init", "--bare", str(bare)], cwd=container)

    clone = container / "wiki"
    clone.mkdir(parents=True, exist_ok=True)
    _git(["init", str(clone)], cwd=clone)

    _git(["config", "user.email", "test@test.com"], cwd=clone)
    _git(["config", "user.name", "Test User"], cwd=clone)

    _git(["remote", "add", "origin", str(bare)], cwd=clone)

    home_content = "# Tasks\n\n## My Task\n[my-task]\n\n"
    (clone / "Home.md").write_text(home_content, encoding="utf-8")

    config_content = "version: 1\n"
    (clone / "config.yaml").write_text(config_content, encoding="utf-8")

    _git(["add", "Home.md", "config.yaml"], cwd=clone)
    _git(["commit", "-m", "init"], cwd=clone)
    _git(["push", "-u", "origin", "main"], cwd=clone)

    return clone


def _kill_daemon(wiki_path: Path) -> None:
    """Kill daemon by removing state file and taskkill."""
    state_file = wiki_path / ".wiki-daemon.json"
    if state_file.exists():
        import json
        try:
            state = json.loads(state_file.read_text("utf-8"))
            pid = state.get("pid")
            if pid and sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True,
                )
        except Exception:
            pass
        state_file.unlink(missing_ok=True)


def main() -> int:
    container = SCRATCH / "test-wiki-daemon-tinydb"

    if container.exists():
        shutil.rmtree(container, ignore_errors=True)

    try:
        container.mkdir(parents=True, exist_ok=True)

        wiki_path = _setup_wiki(container)

        # Set PYTHONPATH for subprocess calls
        env = dict(os.environ)
        pythonpath = env.get("PYTHONPATH", "")
        if pythonpath:
            env["PYTHONPATH"] = str(SCRIPTS) + os.pathsep + pythonpath
        else:
            env["PYTHONPATH"] = str(SCRIPTS)

        # --- Test case 1: Read Home.md via client ---
        try:
            content, hash_ = _client.read(wiki_path, "Home.md", idle_timeout=3)
            assert content is not None, "Content should not be None"
            assert "## My Task" in content, f"Content should contain task title, got: {content!r}"
            print("PASS: Read Home.md via client")
        except Exception as exc:
            print(f"FAIL: Read Home.md via client: {exc}", file=sys.stderr)
            return 1

        # --- Test case 2: Write Home.md and verify tasks.json committed ---
        try:
            content, base_hash = _client.read(wiki_path, "Home.md", idle_timeout=3)
            modified_content = content.replace("[my-task]", "[my-task] [active]")

            _client.write_commit_push(
                wiki_path,
                {"Home.md": (modified_content, base_hash)},
                "test write",
                idle_timeout=3,
            )

            tasks_json = wiki_path / "tasks.json"
            assert tasks_json.exists(), "tasks.json should exist after write"

            result = subprocess.run(
                ["git", "-C", str(wiki_path), "show", "--name-only", "HEAD"],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            assert "tasks.json" in result.stdout, "tasks.json should be in latest commit"
            print("PASS: Write Home.md and verify tasks.json committed")
        except Exception as exc:
            print(f"FAIL: Write Home.md and verify tasks.json: {exc}", file=sys.stderr)
            return 1

        # --- Test case 3: Phase marker round-trip ---
        try:
            content, _ = _client.read(wiki_path, "Home.md", idle_timeout=3)
            assert "[active]" in content, f"Phase marker should be present, got: {content!r}"
            print("PASS: Phase marker round-trip")
        except Exception as exc:
            print(f"FAIL: Phase marker round-trip: {exc}", file=sys.stderr)
            return 1

        # --- Test case 4: Daemon restart preserves task state ---
        try:
            _kill_daemon(wiki_path)

            time.sleep(0.5)

            content, _ = _client.read(wiki_path, "Home.md", idle_timeout=3)
            assert "[active]" in content, f"Phase marker should persist after restart, got: {content!r}"
            print("PASS: Daemon restart preserves task state")
        except Exception as exc:
            print(f"FAIL: Daemon restart preserves task state: {exc}", file=sys.stderr)
            return 1

        print("", file=sys.stderr)
        print("PASS -- all 4 integration tests", file=sys.stderr)
        return 0

    finally:
        if container.exists():
            shutil.rmtree(container, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
