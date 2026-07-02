"""
Integration test for `_verify_baseline.compute_baseline`.

`compute_baseline` inherently exercises real `git worktree add`/`remove`,
real junction creation, and real subprocess verify commands -- none of
which unit tests may use per CLAUDE.md's repo-layout convention
("`unit_tests/` -- in-memory/tempfile fixtures; no real git/LLM.
`integration_tests/` -- invokes real git and optionally real claude; uses
`.scratch/` for fixtures."). This is the dedicated real-git coverage
`_mill/discussion.md`'s Testing section calls for.

Layout mirrors `test-merge.py`:

    <container>/remote.git             bare "remote" for the fixture repo
    <container>/hub                    hub clone (parent branch "main" +
                                        a "collision-branch" used only by
                                        case 6)
    <container>/case<N>                one task-branch worktree per case,
                                        each playing the role of
                                        `project_root`/`git_root` for a
                                        single `compute_baseline` call
    <container>/scripts/*.py           tiny verify-command fixture scripts
                                        `compute_baseline` runs verbatim

Six cases, matching `06-baseline-integration-test.md` Card 13's
Requirements exactly, each calling the real (unmocked) `compute_baseline`
function:

    1. Clean baseline: a verify command that always passes -> "clean",
       transient worktree cleaned up.
    2. Confirmed pre-existing failure: a verify command that always fails
       -> "pre-existing-failures" only after both the transient-worktree
       retry and the task-worktree control run have been exercised
       (asserted via an invocation counter).
    3. Flaky-then-passes: a verify command that fails once then passes ->
       "clean" via retry corroboration; asserted invoked more than once.
    4. Path-sensitive deterministic failure: a verify command that fails
       specifically at the transient worktree's path but passes at the
       task worktree's path -> "clean" via control-run corroboration.
    5. Dependency-junction reuse: a `.venv`-shaped marker directory at the
       task worktree's top level is junctioned into the transient
       worktree and read successfully; the real marker directory in the
       task worktree survives cleanup untouched.
    6. Cleanup on exception: `compute_baseline` is forced to raise
       (junction-creation collision -- the parent branch itself tracks a
       `.venv` path, so junctioning the task worktree's real `.venv` into
       the freshly-checked-out transient worktree collides) and the
       transient worktree is still torn down.

Exits 0 on PASS, 1 on any failure; scratch is preserved on failure for
inspection.
"""
from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
SCRATCH = HUB / ".scratch"

sys.path.insert(0, str(SCRIPTS))

import _safe_rmtree  # noqa: E402
import _verify_baseline  # noqa: E402


def _run(cmd: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _setup_hub(container: Path) -> Path:
    """
    Build a bare "remote" + a working `hub` clone with one commit on
    `main`, plus a second `collision-branch` whose tip tracks a real
    `.venv/tracked.txt` file -- used only by case 6 to force a
    junction-creation collision inside `compute_baseline`'s transient
    worktree.

    Returns the `hub` clone path. Every case's task worktree is created
    as a linked `git worktree` off this same repo (via `_new_worktree`),
    so `compute_baseline`'s internal `git -C <git_root> rev-parse` /
    `worktree add` calls always resolve against the same ref namespace.
    """
    bare = container / "remote.git"
    hub = container / "hub"
    _run(["git", "init", "--bare", str(bare), "-b", "main"], cwd=container)
    _run(["git", "clone", str(bare), str(hub)], cwd=container)
    _run(["git", "-C", str(hub), "config", "user.email", "test@example.com"], cwd=container)
    _run(["git", "-C", str(hub), "config", "user.name", "Test"], cwd=container)
    (hub / "README.md").write_text("verify-baseline integration test hub\n", encoding="utf-8")
    _run(["git", "-C", str(hub), "add", "README.md"], cwd=container)
    _run(["git", "-C", str(hub), "commit", "-m", "init"], cwd=container)
    _run(["git", "-C", str(hub), "push", "origin", "main"], cwd=container)

    # collision-branch: tracks a real .venv/tracked.txt so its tree already
    # contains ".venv" when checked out into a transient worktree. Case 6
    # combines this with a real .venv/ at the task worktree's top level so
    # _junction.create's link-path-already-exists guard fires.
    _run(["git", "-C", str(hub), "checkout", "-b", "collision-branch"], cwd=container)
    venv_dir = hub / ".venv"
    venv_dir.mkdir()
    (venv_dir / "tracked.txt").write_text("tracked venv placeholder\n", encoding="utf-8")
    _run(["git", "-C", str(hub), "add", ".venv/tracked.txt"], cwd=container)
    _run(["git", "-C", str(hub), "commit", "-m", "collision: track .venv"], cwd=container)
    _run(["git", "-C", str(hub), "push", "origin", "collision-branch"], cwd=container)
    _run(["git", "-C", str(hub), "checkout", "main"], cwd=container)

    return hub


def _new_worktree(hub: Path, container: Path, name: str, start_point: str) -> Path:
    """Create a linked `git worktree` for `hub` on a fresh `wt-<name>` branch."""
    target = container / name
    _run(
        ["git", "-C", str(hub), "worktree", "add", "-b", f"wt-{name}", str(target), start_point],
        cwd=container,
    )
    return target


def _write_script(scripts_dir: Path, name: str, body: str) -> Path:
    """Write a small verify-command fixture script and return its path."""
    path = scripts_dir / name
    path.write_text(body, encoding="utf-8")
    return path


def _verify_cmd(python_exe: str, script_path: Path) -> str:
    """
    Build a `module_wide_verify_cmd` string in the project's standard shape
    -- literal empty `PYTHONPATH=` prefix (CLAUDE.md's "Verify command
    shape" convention) followed by the absolute interpreter and script
    paths, forward-slashed and quoted so it survives `bash -c` on Windows
    (compute_baseline routes POSIX-shaped verify commands through bash via
    `_implementer_common._posix_shell_run_args`).
    """
    posix_python = str(python_exe).replace("\\", "/")
    posix_script = str(script_path).replace("\\", "/")
    return f'PYTHONPATH= "{posix_python}" "{posix_script}"'


def _scratch_snapshot(project_root: Path) -> set[str]:
    """Names of any leftover `verify-baseline-*` transient worktree dirs."""
    scratch = project_root / ".scratch"
    if not scratch.exists():
        return set()
    return {p.name for p in scratch.glob("verify-baseline-*")}


def _counting_fail_script(counter_path: Path) -> str:
    """Always exits 1; increments a counter file on every invocation."""
    posix_counter = str(counter_path).replace("\\", "/")
    return (
        "import pathlib, sys\n"
        f"p = pathlib.Path('{posix_counter}')\n"
        "n = int(p.read_text()) if p.exists() else 0\n"
        "p.write_text(str(n + 1))\n"
        "sys.exit(1)\n"
    )


def _flaky_script(marker_path: Path, counter_path: Path) -> str:
    """Fails on its first invocation, passes on every subsequent one."""
    posix_marker = str(marker_path).replace("\\", "/")
    posix_counter = str(counter_path).replace("\\", "/")
    return (
        "import pathlib, sys\n"
        f"marker = pathlib.Path('{posix_marker}')\n"
        f"counter = pathlib.Path('{posix_counter}')\n"
        "n = int(counter.read_text()) if counter.exists() else 0\n"
        "counter.write_text(str(n + 1))\n"
        "if marker.exists():\n"
        "    sys.exit(0)\n"
        "else:\n"
        "    marker.write_text('x')\n"
        "    sys.exit(1)\n"
    )


def _path_sensitive_script(task_worktree_dirname: str) -> str:
    """Passes only when run with a cwd whose basename matches `task_worktree_dirname`."""
    return (
        "import pathlib, sys\n"
        f"sys.exit(0 if pathlib.Path.cwd().name == {task_worktree_dirname!r} else 1)\n"
    )


def _sentinel_script() -> str:
    """Passes iff `.venv/sentinel.txt` is readable from the process's own cwd."""
    return (
        "import pathlib, sys\n"
        "p = pathlib.Path.cwd() / '.venv' / 'sentinel.txt'\n"
        "sys.exit(0 if p.exists() and p.read_text() == 'sentinel-content-xyz' else 1)\n"
    )


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    container = SCRATCH / f"verify-baseline-test-{uuid.uuid4().hex[:8]}"
    scripts_dir = container / "scripts"
    failed = False
    try:
        container.mkdir(parents=True, exist_ok=True)
        scripts_dir.mkdir(parents=True, exist_ok=True)
        hub = _setup_hub(container)
        print(f"[test-verify-baseline] container: {container}", file=sys.stderr)
        python_exe = sys.executable

        # --- Case 1: clean baseline ---
        wt1 = _new_worktree(hub, container, "case1", "main")
        pass_script = _write_script(scripts_dir, "clean_pass.py", "import sys\nsys.exit(0)\n")
        clean_cmd = _verify_cmd(python_exe, pass_script)
        before1 = _scratch_snapshot(wt1)
        result1 = _verify_baseline.compute_baseline(wt1, wt1, "main", clean_cmd)
        _assert(result1 == "clean", f"case1: expected 'clean', got {result1!r}")
        after1 = _scratch_snapshot(wt1)
        _assert(
            before1 == set() and after1 == set(),
            f"case1: transient worktree not cleaned up (before={before1}, after={after1})",
        )
        print("PASS: case 1 -- clean baseline returns 'clean' and transient worktree cleaned up")

        # --- Case 2: confirmed pre-existing failure ---
        wt2 = _new_worktree(hub, container, "case2", "main")
        counter2 = container / "case2-counter.txt"
        fail_cmd = _verify_cmd(
            python_exe, _write_script(scripts_dir, "always_fail.py", _counting_fail_script(counter2))
        )
        result2 = _verify_baseline.compute_baseline(wt2, wt2, "main", fail_cmd)
        _assert(
            result2 == "pre-existing-failures",
            f"case2: expected 'pre-existing-failures', got {result2!r}",
        )
        invocations2 = int(counter2.read_text())
        _assert(
            invocations2 == 3,
            f"case2: expected 3 invocations (2 transient + 1 control), got {invocations2}",
        )
        after2 = _scratch_snapshot(wt2)
        _assert(after2 == set(), f"case2: transient worktree not cleaned up: {after2}")
        print(
            "PASS: case 2 -- confirmed pre-existing failure only after retry + "
            "control run both fail"
        )

        # --- Case 3: flaky-then-passes (retry corroboration) ---
        wt3 = _new_worktree(hub, container, "case3", "main")
        marker3 = container / "case3-marker.txt"
        counter3 = container / "case3-counter.txt"
        flaky_cmd = _verify_cmd(
            python_exe,
            _write_script(scripts_dir, "flaky.py", _flaky_script(marker3, counter3)),
        )
        result3 = _verify_baseline.compute_baseline(wt3, wt3, "main", flaky_cmd)
        _assert(result3 == "clean", f"case3: expected 'clean', got {result3!r}")
        invocations3 = int(counter3.read_text())
        _assert(invocations3 > 1, f"case3: expected >1 invocation, got {invocations3}")
        after3 = _scratch_snapshot(wt3)
        _assert(after3 == set(), f"case3: transient worktree not cleaned up: {after3}")
        print("PASS: case 3 -- flaky-then-passes retry corroboration returns 'clean'")

        # --- Case 4: path-sensitive deterministic failure (control-run corroboration) ---
        wt4 = _new_worktree(hub, container, "case4", "main")
        path_cmd = _verify_cmd(
            python_exe,
            _write_script(scripts_dir, "path_sensitive.py", _path_sensitive_script(wt4.name)),
        )
        result4 = _verify_baseline.compute_baseline(wt4, wt4, "main", path_cmd)
        _assert(
            result4 == "clean",
            f"case4: expected 'clean' (task-worktree control run overrides), got {result4!r}",
        )
        after4 = _scratch_snapshot(wt4)
        _assert(after4 == set(), f"case4: transient worktree not cleaned up: {after4}")
        print("PASS: case 4 -- path-sensitive failure overridden by task-worktree control run")

        # --- Case 5: dependency-junction reuse ---
        wt5 = _new_worktree(hub, container, "case5", "main")
        venv5 = wt5 / ".venv"
        venv5.mkdir()
        (venv5 / "sentinel.txt").write_text("sentinel-content-xyz", encoding="utf-8")
        sentinel_cmd = _verify_cmd(
            python_exe, _write_script(scripts_dir, "sentinel_check.py", _sentinel_script())
        )
        result5 = _verify_baseline.compute_baseline(wt5, wt5, "main", sentinel_cmd)
        _assert(
            result5 == "clean",
            f"case5: expected 'clean' (dependency junction reused), got {result5!r}",
        )
        _assert(venv5.exists(), "case5: task worktree's .venv was removed by junction cleanup")
        _assert(
            (venv5 / "sentinel.txt").read_text(encoding="utf-8") == "sentinel-content-xyz",
            "case5: task worktree's .venv/sentinel.txt was altered by junction cleanup",
        )
        after5 = _scratch_snapshot(wt5)
        _assert(after5 == set(), f"case5: transient worktree not cleaned up: {after5}")
        print(
            "PASS: case 5 -- dependency-junction reuse passes and leaves the task "
            "worktree's real .venv/ untouched"
        )

        # --- Case 6: cleanup on exception ---
        wt6 = _new_worktree(hub, container, "case6", "main")
        venv6 = wt6 / ".venv"
        venv6.mkdir()
        (venv6 / "marker.txt").write_text("case6-marker\n", encoding="utf-8")
        raised: Exception | None = None
        try:
            _verify_baseline.compute_baseline(wt6, wt6, "collision-branch", clean_cmd)
        except Exception as exc:  # noqa: BLE001 -- we assert on the type below
            raised = exc
        _assert(raised is not None, "case6: compute_baseline did not raise on junction collision")
        _assert(
            isinstance(raised, ValueError),
            f"case6: expected ValueError from junction-creation collision, got "
            f"{type(raised).__name__}: {raised}",
        )
        after6 = _scratch_snapshot(wt6)
        _assert(
            after6 == set(),
            f"case6: transient worktree not cleaned up after exception: {after6}",
        )
        print("PASS: case 6 -- transient worktree cleaned up even when compute_baseline raises")

        print("PASS -- compute_baseline end-to-end (6/6 cases)")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        failed = True
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL (unexpected): {type(exc).__name__}: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        failed = True
        return 1
    finally:
        if failed:
            print(f"Scratch preserved: {container}", file=sys.stderr)
        else:
            _safe_rmtree.safe_rmtree(container, allowed_root=container, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
