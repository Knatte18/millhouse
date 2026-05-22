"""Integration test: wiki client-daemon end-to-end.

Exercise the full client-daemon-git stack: real TCP socket, real git, real
subprocess spawn. Covers basic read/write, concurrent CAS, idle-exit/respawn,
and health check.

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
import wiki._client as _client  # noqa: E402


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

    # Seed Home.md so the repo has at least one commit.
    home = clone / "Home.md"
    home.write_text("# Home\n", encoding="utf-8")
    _git(["config", "user.email", "test@test.com"], cwd=clone)
    _git(["config", "user.name", "Test"], cwd=clone)
    _git(["add", "Home.md"], cwd=clone)
    _git(["commit", "-m", "init"], cwd=clone)
    _git(["push", "origin", "HEAD"], cwd=clone)

    return clone


def _scenario_1_basic_read_write(wiki_path: Path) -> bool:
    """Test basic read and write operations."""
    try:
        # Read initial Home.md
        content, hash_ = _client.read(wiki_path, "Home.md", idle_timeout=3)
        if content != "# Home\n":
            print(f"FAIL [scenario 1]: initial content mismatch: {content!r}", file=sys.stderr)
            return False

        # Write new content
        _client.write_commit_push(
            wiki_path,
            {"Home.md": (f"{content}Line 2\n", hash_)},
            "add line 2",
            idle_timeout=3,
        )

        # Read updated content
        content, _ = _client.read(wiki_path, "Home.md", idle_timeout=3)
        if content != "# Home\nLine 2\n":
            print(f"FAIL [scenario 1]: updated content mismatch: {content!r}", file=sys.stderr)
            return False

        # Read missing file
        try:
            _client.read(wiki_path, "missing.md", idle_timeout=3)
            print("FAIL [scenario 1]: should have raised WikiNotFoundError", file=sys.stderr)
            return False
        except WikiNotFoundError:
            pass  # Expected

        print("PASS [scenario 1]: basic read-write")
        return True

    except Exception as exc:
        print(f"FAIL [scenario 1]: {exc}", file=sys.stderr)
        return False


def _make_concurrent_cas_script(wiki_path: Path, label: str) -> str:
    """Return source for a subprocess that does read-modify-write with retry."""
    scripts_posix = SCRIPTS.as_posix()
    wiki_posix = wiki_path.as_posix()
    return textwrap.dedent(f"""\
        import sys
        from pathlib import Path
        sys.path.insert(0, r'{scripts_posix}')
        from wiki import WikiConflictError
        import wiki._client as _client

        wiki_path = Path(r'{wiki_posix}')
        label = {label!r}
        max_retries = 5

        for attempt in range(max_retries):
            try:
                content, hash_ = _client.read(wiki_path, "Home.md", idle_timeout=3)
                new_content = content + label + "\\n"
                _client.write_commit_push(
                    wiki_path,
                    {{"Home.md": (new_content, hash_)}},
                    f"add {{label}}",
                    idle_timeout=3,
                )
                sys.exit(0)
            except WikiConflictError:
                if attempt < max_retries - 1:
                    continue
                raise
        sys.exit(1)
    """)


def _scenario_2_concurrent_cas(wiki_path: Path) -> bool:
    """Test concurrent compare-and-swap with conflict handling."""
    try:
        container = wiki_path.parent
        script_a = container / "proc_a.py"
        script_b = container / "proc_b.py"
        script_a.write_text(_make_concurrent_cas_script(wiki_path, "[A]"), encoding="utf-8")
        script_b.write_text(_make_concurrent_cas_script(wiki_path, "[B]"), encoding="utf-8")

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

        ret_a = proc_a.wait(timeout=30)
        ret_b = proc_b.wait(timeout=30)

        if ret_a != 0:
            out, err = proc_a.communicate()
            print(f"FAIL [scenario 2]: proc_a exited {ret_a}: {err}", file=sys.stderr)
            return False

        if ret_b != 0:
            out, err = proc_b.communicate()
            print(f"FAIL [scenario 2]: proc_b exited {ret_b}: {err}", file=sys.stderr)
            return False

        # Verify both lines are present
        content, _ = _client.read(wiki_path, "Home.md", idle_timeout=3)
        if "[A]" not in content or "[B]" not in content:
            print(f"FAIL [scenario 2]: missing lines in final content: {content!r}", file=sys.stderr)
            return False

        print("PASS [scenario 2]: concurrent CAS")
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

        # Read should respawn daemon transparently
        content, _ = _client.read(wiki_path, "Home.md", idle_timeout=idle_timeout)
        if not content.startswith("# Home"):
            print(f"FAIL [scenario 3]: content corrupted after respawn: {content!r}", file=sys.stderr)
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
        if not _client.health_check(wiki_path):
            print("FAIL [scenario 4]: health_check returned False while daemon is up", file=sys.stderr)
            return False

        print("PASS [scenario 4]: health_check")
        return True

    except Exception as exc:
        print(f"FAIL [scenario 4]: {exc}", file=sys.stderr)
        return False


def main() -> int:
    run_id = uuid.uuid4().hex[:8]
    container = SCRATCH / f"wiki-e2e-{run_id}"
    container.mkdir(parents=True, exist_ok=True)

    try:
        wiki = _setup_wiki(container)

        results = []
        results.append(_scenario_1_basic_read_write(wiki))
        results.append(_scenario_2_concurrent_cas(wiki))
        results.append(_scenario_3_idle_exit_respawn(wiki))
        results.append(_scenario_4_health_check(wiki))

        if all(results):
            _safe_rmtree.safe_rmtree(container, allowed_root=container, ignore_errors=True)
            print("\n4 scenarios passed.")
            return 0

        print(f"\nScratch preserved at: {container}")
        return 1

    except Exception as exc:
        print(f"FAIL: unexpected exception: {exc}", file=sys.stderr)
        print(f"Scratch preserved at: {container}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
