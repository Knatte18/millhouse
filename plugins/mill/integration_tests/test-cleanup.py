"""
Integration test for millpy-cleanup.py.

Seeds a full hub+wiki fixture under .scratch/ with six slug scenarios
(done, abandoned, live, orphan-worktree, orphan-active, malformed-status).
Asserts dry-run plan output, then asserts --apply produces the correct
artefact removals and one wiki commit.

Run from hub root:
    python plugins/mill/integration_tests/test-cleanup.py

Exits 0 on PASS, 1 on any failure (scratch dir preserved for inspection).
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
PLUGIN_ROOT = HUB / "plugins" / "mill"
SCRATCH = HUB / ".scratch"

sys.path.insert(0, str(SCRIPTS))

import _safe_rmtree  # noqa: E402


def _run(cmd: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Invoke cmd in cwd with UTF-8 output capture."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def _git_init(repo: Path) -> None:
    """Initialise a real git repo with an empty initial commit."""
    _run(["git", "init", "-b", "main", str(repo)], cwd=repo.parent)
    # Fallback for Git < 2.28 which does not support -b
    _run(["git", "-C", str(repo), "symbolic-ref", "HEAD", "refs/heads/main"], cwd=repo, check=False)
    _run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], cwd=repo)
    _run(["git", "-C", str(repo), "config", "user.name", "Test"], cwd=repo)
    (repo / ".keep").write_text("", encoding="utf-8")
    _run(["git", "-C", str(repo), "add", ".keep"], cwd=repo)
    _run(["git", "-C", str(repo), "commit", "-m", "init"], cwd=repo)


def _write_status_md(path: Path, phase: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"```yaml\nphase: {phase}\n```\n", encoding="utf-8")


def _setup_fixture(container: Path) -> tuple[Path, Path, Path]:
    """Build the hub+wiki pair and seed all six scenarios.

    Returns (hub, wiki, worktrees_dir).
    """
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

    # Seed six scenarios in wiki
    # 1. done-slug
    _write_status_md(wiki / "active" / "done-slug" / "status.md", "done")

    # 2. abandoned-slug
    _write_status_md(wiki / "active" / "abandoned-slug" / "status.md", "abandoned")

    # 3. live-slug
    _write_status_md(wiki / "active" / "live-slug" / "status.md", "implementing")

    # 4. orphan-wt-slug — worktree only, no active/ dir
    # (no status.md created)

    # 5. orphan-active-slug — active/ dir only, no Home.md [active] entry
    _write_status_md(wiki / "active" / "orphan-active-slug" / "status.md", "implementing")

    # 6. malformed-slug — invalid YAML
    (wiki / "active" / "malformed-slug").mkdir(parents=True, exist_ok=True)
    (wiki / "active" / "malformed-slug" / "status.md").write_text(
        "```yaml\nphase: [unclosed bracket\n```\n", encoding="utf-8"
    )

    # Home.md — entries for done, abandoned, live only (orphan-active has no [active])
    home_md = (
        "# Tasks\n\n"
        "## Done task [done-slug] [done]\n\n"
        "## Abandoned task [abandoned-slug] [active]\n\n"
        "## Live task [live-slug] [active]\n\n"
        "## Malformed task [malformed-slug]\n\n"
    )
    (wiki / "Home.md").write_text(home_md, encoding="utf-8")
    (wiki / "_Sidebar.md").write_text("### Navigation\n\n- [Home](Home)\n", encoding="utf-8")

    # mill-config.yaml at hub root
    (hub / "mill-config.yaml").write_text(
        "junctions:\n"
        "  .millhouse/wiki: <WIKI_PATH>\n"
        "  .active: <WIKI_PATH>/active/<SLUG>/\n",
        encoding="utf-8",
    )

    _run(["git", "-C", str(wiki), "add", "."], cwd=wiki)
    _run(["git", "-C", str(wiki), "commit", "-m", "seed"], cwd=wiki)
    _run(["git", "-C", str(wiki), "push", "origin", "main"], cwd=wiki)

    # Real worktrees in hub
    _run(["git", "-C", str(hub), "worktree", "add", "-b", "impl/done-slug",
          str(worktrees_dir / "done-slug")], cwd=hub)
    _run(["git", "-C", str(hub), "worktree", "add", "-b", "impl/abandoned-slug",
          str(worktrees_dir / "abandoned-slug")], cwd=hub)
    _run(["git", "-C", str(hub), "worktree", "add", "-b", "impl/live-slug",
          str(worktrees_dir / "live-slug")], cwd=hub)
    _run(["git", "-C", str(hub), "worktree", "add", "-b", "impl/orphan-wt-slug",
          str(worktrees_dir / "orphan-wt-slug")], cwd=hub)

    # .millhouse junction + config
    millhouse = hub / ".millhouse"
    millhouse.mkdir(exist_ok=True)
    if sys.platform == "win32":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(millhouse / "wiki"), str(wiki)],
            check=True, capture_output=True,
        )
    else:
        os.symlink(str(wiki), str(millhouse / "wiki"))

    (millhouse / "config.local.yaml").write_text(
        f"paths:\n  wiki: {wiki.as_posix()}\n", encoding="utf-8"
    )

    return hub, wiki, worktrees_dir


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    container = SCRATCH / f"cleanup-test-{uuid.uuid4().hex[:8]}"
    failed = False
    try:
        hub, wiki, worktrees_dir = _setup_fixture(container)
        print(f"[test-cleanup] container: {container}", file=sys.stderr)

        # --- Test 1: dry-run ---
        result = _run(
            ["uv", "run", "--project", str(PLUGIN_ROOT), str(SCRIPTS / "millpy-cleanup.py")],
            cwd=hub, check=False,
        )
        print(f"--- dry-run stdout ---\n{result.stdout}", file=sys.stderr)
        print(f"--- dry-run stderr ---\n{result.stderr}", file=sys.stderr)
        assert result.returncode == 0, f"dry-run exit={result.returncode}\n{result.stdout}\n{result.stderr}"
        assert "REMOVE (done):      done-slug" in result.stdout, "missing REMOVE (done): done-slug"
        assert "REMOVE (abandoned): abandoned-slug" in result.stdout, "missing REMOVE (abandoned): abandoned-slug"
        assert "Dry-run" in result.stdout, "missing Dry-run message"
        assert "REPORT:" in result.stdout, "missing REPORT: lines"
        assert "orphan-wt-slug" in result.stdout, "missing orphan-wt-slug in output"
        assert "orphan-active-slug" in result.stdout, "missing orphan-active-slug in output"
        assert "malformed-slug" in result.stdout, "missing malformed-slug in output"
        remove_lines = [line for line in result.stdout.splitlines() if line.startswith("REMOVE")]
        assert not any("live-slug" in line for line in remove_lines), "live-slug must not appear in REMOVE lines"
        assert (worktrees_dir / "done-slug").exists(), "dry-run must not remove done-slug worktree"
        assert (worktrees_dir / "abandoned-slug").exists(), "dry-run must not remove abandoned-slug worktree"
        print("PASS dry-run: plan output contains correct REMOVE and REPORT lines")

        # --- Test 2: --apply ---
        result = _run(
            ["uv", "run", "--project", str(PLUGIN_ROOT), str(SCRIPTS / "millpy-cleanup.py"), "--apply"],
            cwd=hub, check=False,
        )
        print(f"--- apply stdout ---\n{result.stdout}", file=sys.stderr)
        print(f"--- apply stderr ---\n{result.stderr}", file=sys.stderr)
        assert result.returncode == 0, f"--apply exit={result.returncode}\n{result.stdout}\n{result.stderr}"

        # Worktree assertions
        assert not (worktrees_dir / "done-slug").exists(), "done-slug worktree should be removed"
        assert not (worktrees_dir / "abandoned-slug").exists(), "abandoned-slug worktree should be removed"
        assert (worktrees_dir / "live-slug").exists(), "live-slug worktree must be untouched"
        assert (worktrees_dir / "orphan-wt-slug").exists(), "orphan-wt-slug is report-only, not removed"

        # Branch assertions
        branch_out = _run(["git", "branch"], cwd=hub).stdout
        assert "impl/done-slug" not in branch_out, "impl/done-slug branch should be deleted"
        assert "impl/abandoned-slug" not in branch_out, "impl/abandoned-slug branch should be deleted"
        assert "impl/live-slug" in branch_out, "impl/live-slug branch must remain"

        # Wiki active-dir assertions (from wiki clone)
        assert not (wiki / "active" / "done-slug").exists(), "done-slug active dir should be removed"
        assert not (wiki / "active" / "abandoned-slug").exists(), "abandoned-slug active dir should be removed"
        assert (wiki / "active" / "live-slug").exists(), "live-slug active dir must remain"
        assert (wiki / "active" / "orphan-active-slug").exists(), "orphan-active-slug is report-only, not removed"

        # Home.md assertions
        home_text = (wiki / "Home.md").read_text("utf-8")
        assert "[active]" not in home_text.split("abandoned-slug")[1].split("\n")[0], \
            "abandoned-slug should have [active] marker cleared"
        assert "[done]" in home_text.split("done-slug")[0].split("\n")[-1] or \
            "[done]" in home_text.split("done-slug")[1][:20], \
            "done-slug [done] marker should be untouched"
        assert "live-slug" in home_text, "live-slug heading must still be present"
        live_line = next(line for line in home_text.splitlines() if "live-slug" in line)
        assert "[active]" in live_line, f"live-slug [active] must be untouched: {live_line!r}"

        # Wiki commit assertion
        log = _run(["git", "log", "--oneline", "-3"], cwd=wiki).stdout
        assert "chore: cleanup" in log, f"expected 'chore: cleanup' in git log, got: {log!r}"

        print("PASS --apply: correct worktree removals, wiki commit, Home.md resets")

    except (AssertionError, subprocess.CalledProcessError, Exception) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        print(f"Fixture preserved at {container}", file=sys.stderr)
        failed = True

    if not failed:
        _safe_rmtree.safe_rmtree(container, allowed_root=container, ignore_errors=True)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
