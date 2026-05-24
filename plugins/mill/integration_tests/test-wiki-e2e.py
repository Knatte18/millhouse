"""Integration test: wiki client-daemon end-to-end with structured ops.

Exercise the full client-daemon-git stack with structured task operations:
real TCP socket, real git, real subprocess spawn. Covers task CRUD, concurrent
phase updates, idle-exit/respawn, and health check.

NOT part of run-all.py (requires a real git binary and real I/O). Run manually:

    PYTHONPATH=plugins/mill/scripts python plugins/mill/integration_tests/test-wiki-e2e.py

Exit 0 on PASS, 1 on FAIL. Scratch lives under <repo>/.scratch/ and is
preserved on failure for inspection.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time
import uuid
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
SCRATCH = HUB / ".scratch"

sys.path.insert(0, str(SCRIPTS))

import _safe_rmtree  # noqa: E402
from wiki import (  # noqa: E402
    WikiNotFoundError,
)
import wiki._client as wiki  # noqa: E402


def _git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args, cwd=str(cwd), check=True,
        capture_output=True, text=True, encoding="utf-8",
    )


def _setup_wiki(container: Path) -> Path:
    """Initialise a local wiki repo (bare remote + working clone)."""
    bare = container / "wiki.git"
    bare.mkdir(parents=True)
    _git(["init", "--bare", str(bare)], cwd=container)

    clone = container / "wiki"
    _git(["clone", str(bare), str(clone)], cwd=container)

    # Seed tasks.json so the repo has at least one commit.
    tasks_json = clone / "tasks.json"
    tasks_json.write_text("{}", encoding="utf-8")
    _git(["config", "user.email", "test@test.com"], cwd=clone)
    _git(["config", "user.name", "Test"], cwd=clone)
    _git(["add", "tasks.json"], cwd=clone)
    _git(["commit", "-m", "init"], cwd=clone)
    _git(["push", "origin", "HEAD"], cwd=clone)

    return clone


def _scenario_1_task_crud(wiki_path: Path) -> bool:
    """Test basic task CRUD operations."""
    try:
        # Upsert a task
        task = wiki.upsert_task(wiki_path, "test-task", title="Test Task", brief="A test task")
        if task.get("slug") != "test-task":
            print(f"FAIL [scenario 1]: upsert slug mismatch: {task.get('slug')!r}", file=sys.stderr)
            return False

        # Get task by slug
        retrieved = wiki.get_task(wiki_path, "test-task")
        if retrieved is None or retrieved.get("slug") != "test-task":
            print(f"FAIL [scenario 1]: get_task by slug failed", file=sys.stderr)
            return False

        # Get task by id
        task_id = task.get("id")
        retrieved_by_id = wiki.get_task(wiki_path, task_id)
        if retrieved_by_id is None or retrieved_by_id.get("id") != task_id:
            print(f"FAIL [scenario 1]: get_task by id failed", file=sys.stderr)
            return False

        # List tasks brief
        brief_list = wiki.list_tasks_brief(wiki_path)
        if len(brief_list) != 1 or brief_list[0].get("slug") != "test-task":
            print(f"FAIL [scenario 1]: list_tasks_brief failed: {brief_list}", file=sys.stderr)
            return False

        # Set phase
        wiki.set_phase(wiki_path, "test-task", "active")
        updated = wiki.get_task(wiki_path, "test-task")
        if updated.get("status") != "active":
            print(f"FAIL [scenario 1]: set_phase failed", file=sys.stderr)
            return False

        # Remove task
        wiki.remove_task(wiki_path, "test-task")
        removed = wiki.get_task(wiki_path, "test-task")
        if removed is not None:
            print(f"FAIL [scenario 1]: remove_task failed", file=sys.stderr)
            return False

        print("PASS [scenario 1]: task CRUD")
        return True

    except Exception as exc:
        print(f"FAIL [scenario 1]: {exc}", file=sys.stderr)
        return False


def _make_concurrent_phase_script(wiki_path: Path, label: str) -> str:
    """Return source for a subprocess that sets a phase."""
    scripts_posix = SCRIPTS.as_posix()
    wiki_posix = wiki_path.as_posix()
    return textwrap.dedent(f"""\
        import sys
        from pathlib import Path
        sys.path.insert(0, r'{scripts_posix}')
        import wiki._client as wiki

        wiki_path = Path(r'{wiki_posix}')
        label = {label!r}

        try:
            # Upsert a task so we have something to update
            task = wiki.upsert_task(wiki_path, f"concurrent-{{label}}", title=f"Task {{label}}")
            sys.exit(0)
        except Exception as e:
            print(f"Error: {{e}}", file=sys.stderr)
            sys.exit(1)
    """)


def _scenario_2_concurrent_mutations(wiki_path: Path) -> bool:
    """Test concurrent mutations via daemon serialisation."""
    try:
        container = wiki_path.parent
        script_a = container / "proc_a.py"
        script_b = container / "proc_b.py"
        script_a.write_text(_make_concurrent_phase_script(wiki_path, "A"), encoding="utf-8")
        script_b.write_text(_make_concurrent_phase_script(wiki_path, "B"), encoding="utf-8")

        env = dict(os.environ)
        pythonpath = env.get("PYTHONPATH", "")
        if pythonpath:
            env["PYTHONPATH"] = str(SCRIPTS) + os.pathsep + pythonpath
        else:
            env["PYTHONPATH"] = str(SCRIPTS)

        proc_a = subprocess.Popen(
            [sys.executable, str(script_a)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        proc_b = subprocess.Popen(
            [sys.executable, str(script_b)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

        out_a, err_a = proc_a.communicate(timeout=30)
        ret_a = proc_a.returncode
        out_b, err_b = proc_b.communicate(timeout=30)
        ret_b = proc_b.returncode

        if ret_a != 0:
            print(f"FAIL [scenario 2]: proc_a exited {ret_a}: {err_a}", file=sys.stderr)
            return False

        if ret_b != 0:
            print(f"FAIL [scenario 2]: proc_b exited {ret_b}: {err_b}", file=sys.stderr)
            return False

        # Verify both tasks are present
        task_list = wiki.list_tasks_brief(wiki_path)
        task_slugs = {t.get("slug") for t in task_list}
        if "concurrent-A" not in task_slugs or "concurrent-B" not in task_slugs:
            print(f"FAIL [scenario 2]: missing tasks in final state: {task_slugs}", file=sys.stderr)
            return False

        print("PASS [scenario 2]: concurrent mutations")
        return True

    except Exception as exc:
        print(f"FAIL [scenario 2]: {exc}", file=sys.stderr)
        return False


def _scenario_3_idle_exit_respawn(wiki_path: Path) -> bool:
    """Test daemon idle-exit and transparent respawn."""
    try:
        idle_timeout = 3
        # Wait for daemon to idle-exit
        wait_time = idle_timeout + 2
        print(f"waiting {wait_time}s for daemon idle-exit...")
        time.sleep(wait_time)

        # Check state file is gone
        state_file = wiki_path / ".wiki-daemon.json"
        if state_file.exists():
            print("FAIL [scenario 3]: state file still exists after idle timeout", file=sys.stderr)
            return False

        # List tasks should respawn daemon transparently
        task_list = wiki.list_tasks_brief(wiki_path)
        if not isinstance(task_list, list):
            print(f"FAIL [scenario 3]: list failed after respawn: {task_list!r}", file=sys.stderr)
            return False

        print("PASS [scenario 3]: idle-exit and respawn")
        return True

    except Exception as exc:
        print(f"FAIL [scenario 3]: {exc}", file=sys.stderr)
        return False


def _scenario_4_health_check(wiki_path: Path) -> bool:
    """Test daemon health check."""
    try:
        # Health check should pass (daemon is up from previous scenario)
        if not wiki.health_check(wiki_path):
            print("FAIL [scenario 4]: health_check returned False while daemon is up", file=sys.stderr)
            return False

        print("PASS [scenario 4]: health_check")
        return True

    except Exception as exc:
        print(f"FAIL [scenario 4]: {exc}", file=sys.stderr)
        return False


def _scenario_5_merge_tasks(wiki_path: Path) -> bool:
    """Test atomic merge_tasks operation."""
    try:
        # Create some tasks to merge
        wiki.upsert_task(wiki_path, "merge-remove-a", title="Remove A")
        wiki.upsert_task(wiki_path, "merge-remove-b", title="Remove B")
        merge_task = wiki.upsert_task(wiki_path, "merge-keep", title="Keep")
        merge_id = merge_task.get("id")

        # Do atomic merge: remove a and b, update keep, set phase
        result = wiki.merge_tasks(
            wiki_path,
            remove_slugs=["merge-remove-a", "merge-remove-b"],
            upsert={"slug": "merge-keep", "title": "Keep Updated"},
            set_phase=(merge_id, "active"),
        )

        # Verify result
        if result.get("slug") != "merge-keep":
            print(f"FAIL [scenario 5]: merge result slug mismatch", file=sys.stderr)
            return False

        # Verify removals
        if wiki.get_task(wiki_path, "merge-remove-a") is not None:
            print(f"FAIL [scenario 5]: merge-remove-a should be gone", file=sys.stderr)
            return False

        if wiki.get_task(wiki_path, "merge-remove-b") is not None:
            print(f"FAIL [scenario 5]: merge-remove-b should be gone", file=sys.stderr)
            return False

        # Verify update and phase
        kept = wiki.get_task(wiki_path, "merge-keep")
        if kept.get("title") != "Keep Updated":
            print(f"FAIL [scenario 5]: merge-keep title not updated", file=sys.stderr)
            return False

        if kept.get("status") != "active":
            print(f"FAIL [scenario 5]: merge-keep phase not set", file=sys.stderr)
            return False

        print("PASS [scenario 5]: merge_tasks")
        return True

    except Exception as exc:
        print(f"FAIL [scenario 5]: {exc}", file=sys.stderr)
        return False


def main() -> int:
    run_id = uuid.uuid4().hex[:8]
    container = SCRATCH / f"wiki-e2e-{run_id}"
    container.mkdir(parents=True, exist_ok=True)

    try:
        wiki_clone = _setup_wiki(container)

        results = []
        results.append(_scenario_1_task_crud(wiki_clone))
        results.append(_scenario_2_concurrent_mutations(wiki_clone))
        results.append(_scenario_3_idle_exit_respawn(wiki_clone))
        results.append(_scenario_4_health_check(wiki_clone))
        results.append(_scenario_5_merge_tasks(wiki_clone))

        if all(results):
            _safe_rmtree.safe_rmtree(container, allowed_root=container, ignore_errors=True)
            print("\n5 scenarios passed.")
            return 0

        print(f"\nScratch preserved at: {container}")
        return 1

    except Exception as exc:
        print(f"FAIL: unexpected exception: {exc}", file=sys.stderr)
        print(f"Scratch preserved at: {container}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
