"""
Integration test for millpy-abandon.py.

Builds a hub+wiki fixture under .scratch/ with a real bare git repo and a
wiki clone.  Tests the happy path, hub guard, and double-abandon guard.

Run from hub root:
    python plugins/mill/integration_tests/test-abandon.py

Exits 0 on PASS, 1 on any failure (scratch dir preserved for inspection).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
SCRATCH = HUB / ".scratch"

sys.path.insert(0, str(SCRIPTS))
import _status
import _active


def _run(cmd: list[str], *, cwd: Path, check: bool = True,
         stdin_input: str = "") -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        check=check,
        input=stdin_input,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def _git_init(repo: Path) -> None:
    _run(["git", "init", "-b", "main", str(repo)], cwd=repo.parent)
    _run(["git", "-C", str(repo), "symbolic-ref", "HEAD", "refs/heads/main"],
         cwd=repo, check=False)
    _run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], cwd=repo)
    _run(["git", "-C", str(repo), "config", "user.name", "Test"], cwd=repo)
    (repo / ".keep").write_text("", encoding="utf-8")
    _run(["git", "-C", str(repo), "add", ".keep"], cwd=repo)
    _run(["git", "-C", str(repo), "commit", "-m", "init"], cwd=repo)


def _setup_fixture(container: Path) -> tuple[Path, Path, Path, str]:
    """Build hub+wiki fixture.  Returns (hub, wiki_clone, worktree, slug)."""
    container.mkdir(parents=True, exist_ok=True)
    bare = container / "wiki.git"
    wiki = container / "wiki"
    hub = container / "hub"
    worktrees_dir = container / "worktrees"
    worktrees_dir.mkdir()

    # Bare wiki + clone
    _run(["git", "init", "--bare", str(bare), "-b", "main"], cwd=container)
    _run(["git", "clone", str(bare), str(wiki)], cwd=container)
    _run(["git", "-C", str(wiki), "config", "user.email", "test@example.com"], cwd=container)
    _run(["git", "-C", str(wiki), "config", "user.name", "Test"], cwd=container)

    # Hub repo
    hub.mkdir()
    _git_init(hub)

    slug = "test-abandon-task"

    # Seed status.md in wiki
    status_path = wiki / "active" / slug / "status.md"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    content = _status.render_initial(
        task_title="Test abandon task",
        task_description="A task for the abandon integration test.",
        timestamp="2026-04-24T10:00:00Z",
        parent_branch="main",
        slug="my-slug",
        branch="hanf/my-slug",
    )
    status_path.write_text(content, encoding="utf-8")
    _run(["git", "-C", str(wiki), "add", "."], cwd=wiki)
    _run(["git", "-C", str(wiki), "commit", "-m", "seed"], cwd=wiki)
    _run(["git", "-C", str(wiki), "push", "origin", "main"], cwd=wiki)

    # Create worktree from hub
    wt_path = worktrees_dir / slug
    _run(["git", "-C", str(hub), "worktree", "add", "-b", f"impl/{slug}", str(wt_path)],
         cwd=hub)

    # Seed .millhouse in worktree
    mill_dir = wt_path / ".millhouse"
    mill_dir.mkdir(exist_ok=True)
    _active.write(mill_dir, slug=slug, task_title="Test abandon task",
                  branch=f"impl/{slug}", spawned_at="2026-04-24T10:00:00Z")

    # Hub .millhouse config pointing to wiki clone
    hub_mill = hub / ".millhouse"
    hub_mill.mkdir(exist_ok=True)
    (hub_mill / "config.local.yaml").write_text(
        f"paths:\n  wiki: {wiki.as_posix()}\n", encoding="utf-8"
    )
    # Worktree .millhouse also needs wiki config
    (mill_dir / "config.local.yaml").write_text(
        f"paths:\n  wiki: {wiki.as_posix()}\n", encoding="utf-8"
    )

    return hub, wiki, wt_path, slug


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    container = SCRATCH / f"test-abandon-{uuid.uuid4().hex[:8]}"
    failed = False

    try:
        hub, wiki, worktree, slug = _setup_fixture(container)
        print(f"[test-abandon] container: {container}", file=sys.stderr)

        script = SCRIPTS / "millpy-abandon.py"

        # --- Scenario A: happy path ---
        result = _run([sys.executable, str(script), "--force"], cwd=worktree, check=False)
        print(f"--- A stdout ---\n{result.stdout}", file=sys.stderr)
        print(f"--- A stderr ---\n{result.stderr}", file=sys.stderr)
        assert result.returncode == 0, (
            f"Scenario A: expected exit 0, got {result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        assert slug in result.stdout, f"Scenario A: slug not in stdout: {result.stdout!r}"
        assert "mill-cleanup" in result.stdout, "Scenario A: expected mill-cleanup hint"

        # Verify status.md has phase=abandoned and a timeline row
        status_path = wiki / "active" / slug / "status.md"
        info = _status.read_status(status_path)
        assert info["phase"] == "abandoned", (
            f"Scenario A: expected phase=abandoned, got {info['phase']!r}"
        )
        assert info["last_timeline_entry"] is not None and "abandoned" in info["last_timeline_entry"], (
            f"Scenario A: expected abandoned in timeline: {info['last_timeline_entry']!r}"
        )

        # Verify git commit was made in wiki
        log = _run(["git", "log", "--oneline", "-3"], cwd=wiki).stdout
        assert f"abandon {slug}" in log, f"Scenario A: expected abandon commit in log: {log!r}"

        print("PASS Scenario A: happy path — status.md updated, wiki committed")

        # --- Scenario B: hub guard ---
        result = _run([sys.executable, str(script), "--force"], cwd=hub, check=False)
        print(f"--- B stdout ---\n{result.stdout}", file=sys.stderr)
        print(f"--- B stderr ---\n{result.stderr}", file=sys.stderr)
        assert result.returncode != 0, (
            f"Scenario B: expected non-zero exit from hub, got {result.returncode}"
        )
        print("PASS Scenario B: hub guard — non-zero exit when run from hub")

        # --- Scenario C: double-abandon guard ---
        result = _run([sys.executable, str(script), "--force"], cwd=worktree, check=False)
        print(f"--- C stdout ---\n{result.stdout}", file=sys.stderr)
        print(f"--- C stderr ---\n{result.stderr}", file=sys.stderr)
        assert result.returncode != 0, (
            f"Scenario C: expected non-zero exit on second abandon, got {result.returncode}"
        )
        print("PASS Scenario C: double-abandon guard — second invocation exits non-zero")

        print("All test-abandon assertions passed.")

    except (AssertionError, subprocess.CalledProcessError, Exception) as exc:
        import traceback
        print(f"FAIL: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print(f"Fixture preserved at {container}", file=sys.stderr)
        failed = True

    if not failed:
        shutil.rmtree(container, ignore_errors=True)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
