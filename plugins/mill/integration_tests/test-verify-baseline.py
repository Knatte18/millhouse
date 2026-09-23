"""
Integration test for `_verify_baseline.compute_baseline`.

`compute_baseline` inherently exercises real subprocess verify commands -- something unit tests may
not use per CLAUDE.md's repo-layout convention ("`unit_tests/` -- in-memory/tempfile fixtures; no
real git/LLM. `integration_tests/` -- invokes real git and optionally real claude; uses `.scratch/`
for fixtures.").
This is the dedicated real-subprocess coverage `_mill/discussion.md`'s Testing section calls for.

Layout mirrors `test-merge.py`, minus anything that only made sense for the deleted checkout
mechanism:

    <container>/remote.git bare "remote" for the fixture repo
    <container>/hub hub clone -- also the `cwd` every case's `compute_baseline` call runs against;
        no second, per-case worktree is needed since `compute_baseline` no longer checks anything
        out
    <container>/scripts/*.py tiny verify-command fixture scripts `compute_baseline` runs verbatim

Five cases, each calling the real (unmocked) `compute_baseline` function against `hub` as `cwd`:

    1. Clean baseline: a verify command that always passes -> "clean".
    2. Confirmed pre-existing failure: a verify command that always fails -> "pre-existing-failures"
        after exactly the 2-run flakiness-guard algorithm (asserted via an invocation counter) --
        not the deleted 3-run corroboration.
    3. Flaky-then-passes: a verify command that fails once then passes -> "clean" via retry
        corroboration; asserted invoked more than once.
    4. Timeout propagation: a verify command that sleeps past `timeout_seconds` ->
        `subprocess.TimeoutExpired` propagates to the caller.
    5. No git subprocess call: `compute_baseline` never spawns a `git` process -- the end-to-end
        guard against the checkout mechanism creeping back in, checked against real subprocess
        invocation history rather than a mock.

Exits 0 on PASS, 1 on any failure;
scratch is preserved on failure for inspection.
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
    Build a bare "remote" + a working `hub` clone with one commit on `main`.

    Returns the `hub` clone path -- the `cwd` every case's `compute_baseline` call runs against
    directly, since `compute_baseline` no longer checks anything out.
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
    return hub


def _write_script(scripts_dir: Path, name: str, body: str) -> Path:
    """Write a small verify-command fixture script and return its path."""
    path = scripts_dir / name
    path.write_text(body, encoding="utf-8")
    return path


def _verify_cmd(python_exe: str, script_path: Path) -> str:
    """
    Build a `module_wide_verify_cmd` string in the project's standard shape -- literal empty
    `PYTHONPATH=` prefix (CLAUDE.md's "Verify command shape" convention) followed by the absolute
    interpreter and script paths, forward-slashed and quoted so it survives `bash -c` on Windows
    (compute_baseline routes POSIX-shaped verify commands through bash via
    `_implementer_common._posix_shell_run_args`).
    """
    posix_python = str(python_exe).replace("\\", "/")
    posix_script = str(script_path).replace("\\", "/")
    return f'PYTHONPATH= "{posix_python}" "{posix_script}"'


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


def _sleep_script(seconds: float) -> str:
    """Sleeps for `seconds` before exiting 0 -- used to force a timeout."""
    return f"import time\ntime.sleep({seconds})\n"


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
        pass_script = _write_script(scripts_dir, "clean_pass.py", "import sys\nsys.exit(0)\n")
        clean_cmd = _verify_cmd(python_exe, pass_script)
        result1, signatures1 = _verify_baseline.compute_baseline(hub, clean_cmd)
        _assert(result1 == "clean", f"case1: expected 'clean', got {result1!r}")
        _assert(signatures1 == [], f"case1: expected no signatures, got {signatures1!r}")
        print("PASS: case 1 -- clean baseline returns 'clean'")

        # --- Case 2: confirmed pre-existing failure (2-run flakiness-guard algorithm) ---
        counter2 = container / "case2-counter.txt"
        fail_cmd = _verify_cmd(
            python_exe, _write_script(scripts_dir, "always_fail.py", _counting_fail_script(counter2))
        )
        result2, _signatures2 = _verify_baseline.compute_baseline(hub, fail_cmd)
        _assert(
            result2 == "pre-existing-failures",
            f"case2: expected 'pre-existing-failures', got {result2!r}",
        )
        invocations2 = int(counter2.read_text())
        _assert(
            invocations2 == 2,
            f"case2: expected exactly 2 invocations (the 2-run flakiness-guard algorithm, no 3rd "
            f"control run), got {invocations2}",
        )
        print(
            "PASS: case 2 -- confirmed pre-existing failure after exactly 2 runs, "
            "no 3rd control run"
        )

        # --- Case 3: flaky-then-passes (retry corroboration) ---
        marker3 = container / "case3-marker.txt"
        counter3 = container / "case3-counter.txt"
        flaky_cmd = _verify_cmd(
            python_exe,
            _write_script(scripts_dir, "flaky.py", _flaky_script(marker3, counter3)),
        )
        result3, _signatures3 = _verify_baseline.compute_baseline(hub, flaky_cmd)
        _assert(result3 == "clean", f"case3: expected 'clean', got {result3!r}")
        invocations3 = int(counter3.read_text())
        _assert(invocations3 > 1, f"case3: expected >1 invocation, got {invocations3}")
        print("PASS: case 3 -- flaky-then-passes retry corroboration returns 'clean'")

        # --- Case 4: timeout propagation ---
        sleep_cmd = _verify_cmd(
            python_exe, _write_script(scripts_dir, "sleepy.py", _sleep_script(5.0))
        )
        raised: Exception | None = None
        try:
            _verify_baseline.compute_baseline(hub, sleep_cmd, timeout_seconds=0.5)
        except subprocess.TimeoutExpired as exc:
            raised = exc
        _assert(
            raised is not None,
            "case4: compute_baseline did not raise subprocess.TimeoutExpired",
        )
        print("PASS: case 4 -- a run exceeding timeout_seconds propagates TimeoutExpired")

        # --- Case 5: no git subprocess call ---
        # A wrapper around the real subprocess.run records every invocation this process makes
        # while compute_baseline runs, without altering behavior -- a spy against real subprocess
        # history, not a mock.
        spawned_argv: list[list[str]] = []
        real_run = subprocess.run

        def _recording_run(*args, **kwargs):
            argv = args[0] if args else kwargs.get("args")
            if isinstance(argv, list):
                spawned_argv.append(argv)
            elif isinstance(argv, str):
                spawned_argv.append([argv])
            return real_run(*args, **kwargs)

        _verify_baseline.subprocess.run = _recording_run
        try:
            result5, _signatures5 = _verify_baseline.compute_baseline(hub, clean_cmd)
        finally:
            _verify_baseline.subprocess.run = real_run
        _assert(result5 == "clean", f"case5: expected 'clean', got {result5!r}")
        git_calls = [argv for argv in spawned_argv if any("git" in str(token) for token in argv)]
        _assert(
            git_calls == [],
            f"case5: compute_baseline spawned a git process: {git_calls!r}",
        )
        print("PASS: case 5 -- compute_baseline spawns no git subprocess of any kind")

        print("PASS -- compute_baseline end-to-end (5/5 cases)")
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
