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
import tempfile
import time
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
SCRATCH = HUB / ".scratch"

sys.path.insert(0, str(SCRIPTS))

import wiki._client as _client  # noqa: E402


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run git command."""
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _setup_wiki(tmp_dir: Path) -> Path:
    """Initialize a real wiki repo (bare remote + working clone)."""
    bare = tmp_dir / "wiki.git"
    _run_git(["init", "--bare", "-b", "main", str(bare)], tmp_dir)

    clone = tmp_dir / "wiki"
    _run_git(["clone", str(bare), str(clone)], tmp_dir)

    _run_git(["config", "user.email", "test@test.com"], clone)
    _run_git(["config", "user.name", "Test User"], clone)

    home_content = "# Tasks\n\n## My Task\n[my-task]\n\n"
    (clone / "Home.md").write_text(home_content, encoding="utf-8")

    config_content = "version: 1\n"
    (clone / "config.yaml").write_text(config_content, encoding="utf-8")

    _run_git(["add", "Home.md", "config.yaml"], clone)
    _run_git(["commit", "-m", "init"], clone)
    _run_git(["push", "origin", "HEAD"], clone)

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
    tmp_dir = Path(tempfile.mkdtemp(prefix="mill-wiki-test-"))

    try:
        wiki_path = _setup_wiki(tmp_dir)

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

            result = _run_git(["show", "--name-only", "HEAD"], wiki_path)
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
        _kill_daemon(tmp_dir / "wiki")
        time.sleep(0.3)

        def _on_rm_error(func, path, _exc):
            import stat
            os.chmod(path, stat.S_IWRITE)
            func(path)

        shutil.rmtree(tmp_dir, onerror=_on_rm_error)


if __name__ == "__main__":
    sys.exit(main())
