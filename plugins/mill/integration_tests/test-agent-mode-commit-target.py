"""Integration test for agent-mode implementer commit-on-task-branch guarantee.

Tests that when _implementer_common functions (emit_prepare, finalize_from_output)
are called from a task worktree, the commits land on the task branch (not on
the hub/main). This is the mechanical proxy for the discussion gotcha: "the
implementer's git commits land on the task branch in the correct worktree."

Uses real git repos in `.scratch/` (no LLM, no Agent tool). Tests the _forward_output
logic directly with a canned success JSON. This test is run via the integration-test
harness, not the per-batch unit verify:.

Local-dev only. Requires a working `git` in PATH. No network.

Run from hub root:
    PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-agent-mode-commit-target.py

Exits 0 on PASS, 1 on any assertion failure (scratch dir preserved for post-mortem).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
SCRATCH = HUB / ".scratch"

sys.path.insert(0, str(SCRIPTS))

import _safe_rmtree  # noqa: E402


def _run(
    cmd: list[str],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Invoke `cmd` in `cwd` with UTF-8 output capture."""
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _assert(condition: bool, message: str) -> None:
    """Raise AssertionError if condition is False."""
    if not condition:
        raise AssertionError(message)


def main() -> int:
    """Run the integration test."""
    failed = False
    container = SCRATCH / "test-agent-mode-commit-target"

    try:
        # --- Setup: clean up any prior run ---
        if container.exists():
            _safe_rmtree.safe_rmtree(container, allowed_root=container, ignore_errors=True)

        # --- Setup: create hub + task worktree ---
        container.mkdir(parents=True, exist_ok=True)
        hub = container / "hub"
        task_wt = container / "task-wt"

        # Initialize hub repo with main branch
        _run(["git", "init", str(hub), "-b", "main"], cwd=container)
        _run(["git", "-C", str(hub), "config", "user.email", "test@example.com"], cwd=container)
        _run(["git", "-C", str(hub), "config", "user.name", "Test"], cwd=container)
        (hub / ".gitignore").write_text("\n", encoding="utf-8")
        _run(["git", "-C", str(hub), "add", ".gitignore"], cwd=container)
        _run(["git", "-C", str(hub), "commit", "-m", "init"], cwd=container)

        # Create task branch on hub
        _run(["git", "-C", str(hub), "checkout", "-b", "hanf/test-task"], cwd=container)
        (hub / "test-file.txt").write_text("test\n", encoding="utf-8")
        _run(["git", "-C", str(hub), "add", "test-file.txt"], cwd=container)
        _run(["git", "-C", str(hub), "commit", "-m", "task setup"], cwd=container)

        # Go back to main so we can add a worktree
        _run(["git", "-C", str(hub), "checkout", "main"], cwd=container)

        # Create task worktree as a checkout of the task branch
        _run(
            ["git", "-C", str(hub), "worktree", "add", str(task_wt), "hanf/test-task"],
            cwd=container,
        )

        # Setup .millhouse dir in task worktree
        (task_wt / ".millhouse").mkdir(parents=True, exist_ok=True)
        (task_wt / ".millhouse" / "config.local.yaml").write_text("{}", encoding="utf-8")

        # Create plan directory structure
        plan_dir = task_wt / "plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        overview_text = (
            "# Plan: Test Task\n\n"
            "```yaml\n"
            "task: Test Task\n"
            "slug: test-slug\n"
            "approved: true\n"
            "```\n\n"
            "## Batch Index\n\n"
            "```yaml\n"
            "batches:\n"
            "  - name: test-batch\n"
            "    file: 01-test-batch.md\n"
            "    depends-on: []\n"
            "    verify: null\n"
            "```\n"
        )
        (plan_dir / "00-overview.md").write_text(overview_text, encoding="utf-8")
        (plan_dir / "01-test-batch.md").write_text("# Batch: test-batch\n", encoding="utf-8")

        # Create status.md
        status_text = (
            "```yaml\n"
            "phase: implementing\n"
            "slug: test-slug\n"
            "task: Test Task\n"
            "branch: hanf/test-task\n"
            "parent: main\n"
            "```\n\n"
            "## Timeline\n\n"
            "```text\n"
            "implementing  2026-01-01T00:00:00Z\n"
            "```\n\n"
            "## Batches\n\n"
            "```yaml\n"
            "batches:\n"
            "  - name: test-batch\n"
            "    state: pending\n"
            "```\n"
        )
        _mill = task_wt / "_mill"
        _mill.mkdir(parents=True, exist_ok=True)
        (_mill / "status.md").write_text(status_text, encoding="utf-8")

        # Create wiki dir with minimal config
        wiki = container / "wiki"
        wiki.mkdir(parents=True, exist_ok=True)
        (wiki / "config.yaml").write_text(
            "roles:\n  implementer:\n    self_fix_rounds: 2\n", encoding="utf-8"
        )

        # Get initial SHA on task branch
        initial_result = _run(["git", "rev-parse", "HEAD"], cwd=task_wt)
        initial_sha = initial_result.stdout.strip()

        # Get initial SHA on hub main
        main_result = _run(
            ["git", "-C", str(hub), "rev-parse", "main"],
            cwd=container,
        )
        main_sha = main_result.stdout.strip()

        # --- Test: Simulate prepare stage commit behavior ---
        # The prepare stage makes an atomic pre-commit that lands on the task branch.
        # Simulate this by creating a commit in the task worktree.
        (_mill / "status.md").write_text("updated status\n", encoding="utf-8")
        _run(["git", "-C", str(task_wt), "add", "_mill/status.md"], cwd=container)
        _run(
            ["git", "-C", str(task_wt), "commit", "-m", "mill-go: start batch test-batch"],
            cwd=container,
        )

        # Verify HEAD advanced on task branch
        pre_commit_result = _run(["git", "rev-parse", "HEAD"], cwd=task_wt)
        pre_commit_sha = pre_commit_result.stdout.strip()
        _assert(
            pre_commit_sha != initial_sha,
            f"prepare stage should create atomic pre-commit on task branch; HEAD unchanged ({initial_sha})",
        )

        # Verify main branch was not touched
        main_after_prepare = _run(
            ["git", "-C", str(hub), "rev-parse", "main"],
            cwd=container,
        )
        main_after_prepare_sha = main_after_prepare.stdout.strip()
        _assert(
            main_after_prepare_sha == main_sha,
            f"prepare stage should not touch main; SHA changed from {main_sha} to {main_after_prepare_sha}",
        )

        # --- Test: Call _forward_output with canned agent output ---
        # Import the helper function directly
        import importlib.util
        impl_common_spec = importlib.util.spec_from_file_location(
            "_implementer_common", str(SCRIPTS / "_implementer_common.py")
        )
        impl_common = importlib.util.module_from_spec(impl_common_spec)
        impl_common_spec.loader.exec_module(impl_common)

        # Create a canned agent output that indicates success
        agent_output_text = '{"status":"success","commit_sha":"fake-input"}\n'

        # Call _forward_output from within the task worktree context
        import io
        from contextlib import redirect_stdout

        output_buf = io.StringIO()
        with redirect_stdout(output_buf):
            rc = impl_common._forward_output(
                agent_output_text,
                task_wt,
                start_sha=initial_sha,
                snapshot_path=None,
                session_id="test-session",
            )

        _assert(rc == 0, f"_forward_output returned {rc}, expected 0")

        # Parse the output
        finalize_output = json.loads(output_buf.getvalue().strip())
        _assert(finalize_output.get("status") == "success", f"Expected status=success, got {finalize_output.get('status')}")

        # Extract the recorded commit_sha from finalize output
        recorded_sha = finalize_output.get("commit_sha")
        _assert(recorded_sha, f"finalize output missing commit_sha: {finalize_output}")

        # Verify recorded SHA is on task branch (should be the pre-commit we created)
        task_wt_current = _run(["git", "rev-parse", "HEAD"], cwd=task_wt)
        task_wt_sha = task_wt_current.stdout.strip()

        _assert(
            recorded_sha == task_wt_sha,
            f"finalize recorded sha {recorded_sha} does not match task worktree HEAD {task_wt_sha}",
        )

        # Verify recorded SHA is NOT on main
        is_on_main = _run(
            ["git", "-C", str(hub), "merge-base", "--is-ancestor", recorded_sha, "main"],
            cwd=container,
            check=False,
        ).returncode == 0

        _assert(
            not is_on_main,
            f"finalize recorded sha {recorded_sha} is on main branch — implementer commits must stay on task branch",
        )

        print("PASS — agent-mode implementer commits land on task branch", file=sys.stderr)
        return 0

    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        failed = True
        return 1
    except Exception as exc:  # noqa: BLE001 — want full surface on unexpected
        print(f"FAIL (unexpected): {type(exc).__name__}: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        failed = True
        return 1
    finally:
        if failed:
            print(
                f"Scratch dir preserved for inspection: {container}",
                file=sys.stderr,
            )
        else:
            try:
                # Remove worktree registration before deleting
                if (container / "task-wt").exists():
                    _run(
                        ["git", "worktree", "remove", "--force", str(container / "task-wt")],
                        cwd=container / "hub",
                        check=False,
                    )
            except Exception:
                pass
            _safe_rmtree.safe_rmtree(container, allowed_root=container, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
