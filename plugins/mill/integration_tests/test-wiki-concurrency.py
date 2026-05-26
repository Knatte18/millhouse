"""Integration test: concurrent wiki lock serialisation.

Regression gate for the 2026-04-28 bug where two overlapping mill-* invocations
both ran `git pull --ff-only` against the same wiki clone, producing
"Cannot fast-forward to multiple branches" and leaving one operation without a
lock. This test verifies that `_wiki.sync_pull` in two concurrent subprocesses
serialises correctly via the advisory lockfile — the second call waits for the
first's lock, then succeeds.

NOT part of run-all.py (requires a real git binary and real I/O). Run manually:

    python plugins/mill/integration_tests/test-wiki-concurrency.py

Exit 0 on PASS, 1 on FAIL. Scratch lives under <repo>/.scratch/ and is
preserved on failure for inspection.
"""
from __future__ import annotations

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


def _make_sync_pull_script(wiki_path: Path, slug: str) -> str:
    """Return source for a subprocess script that calls _wiki.sync_pull."""
    scripts_posix = SCRIPTS.as_posix()
    wiki_posix = wiki_path.as_posix()
    return textwrap.dedent(f"""\
        import sys
        from pathlib import Path
        sys.path.insert(0, r'{scripts_posix}')
        import _wiki
        _wiki.sync_pull(Path(r'{wiki_posix}'), slug={slug!r})
        print("done:{slug}")
    """)


def main() -> int:
    # SKIP: V2 advisory lock model (_wiki.sync_pull) removed in V3
    # V3 uses daemon-mediated lazy refresh; concurrency model is different
    # See #<github-issue-pending> for V3 concurrency design
    print("SKIP: V2 advisory lock concurrency test; see #<github-issue-pending>")
    return 0

    run_id = uuid.uuid4().hex[:8]
    container = SCRATCH / f"wiki-concurrency-{run_id}"
    container.mkdir(parents=True, exist_ok=True)

    try:
        wiki = _setup_wiki(container)

        script_a = container / "proc_a.py"
        script_b = container / "proc_b.py"
        script_a.write_text(_make_sync_pull_script(wiki, "proc-A"), encoding="utf-8")
        script_b.write_text(_make_sync_pull_script(wiki, "proc-B"), encoding="utf-8")

        # Launch both subprocesses simultaneously.
        t0 = time.monotonic()
        proc_a = subprocess.Popen(
            [sys.executable, str(script_a)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8",
        )
        proc_b = subprocess.Popen(
            [sys.executable, str(script_b)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8",
        )

        out_a, err_a = proc_a.communicate(timeout=30)
        out_b, err_b = proc_b.communicate(timeout=30)
        elapsed = time.monotonic() - t0

        ok = True

        if proc_a.returncode != 0:
            print(f"FAIL: proc-A exited {proc_a.returncode}\nstderr: {err_a}", file=sys.stderr)
            ok = False
        else:
            print(f"PASS: proc-A succeeded (stdout: {out_a.strip()!r})")

        if proc_b.returncode != 0:
            print(f"FAIL: proc-B exited {proc_b.returncode}\nstderr: {err_b}", file=sys.stderr)
            ok = False
        else:
            print(f"PASS: proc-B succeeded (stdout: {out_b.strip()!r})")

        lock_path = wiki / ".mill-lock"
        if lock_path.exists():
            print(f"FAIL: lockfile still present after both procs finished: {lock_path}", file=sys.stderr)
            ok = False
        else:
            print("PASS: lockfile cleaned up after both procs")

        print(f"Wall time: {elapsed:.2f}s")

        if ok:
            _safe_rmtree.safe_rmtree(container, allowed_root=container, ignore_errors=True)
            print("\n1 scenario passed.")
            return 0

        print(f"\nScratch preserved at: {container}")
        return 1

    except Exception as exc:
        print(f"FAIL: unexpected exception: {exc}", file=sys.stderr)
        print(f"Scratch preserved at: {container}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
