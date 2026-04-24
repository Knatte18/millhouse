"""
Integration test for mill-spawn.

Builds an isolated hub+wiki pair under ``.scratch/`` and runs
``mill-spawn.py`` against it. Asserts the end-to-end artefacts:

    - Home.md heading for the seeded task switches to ``[active]``.
    - A new worktree directory exists at ``<container>/worktrees/<slug>``
      (hub-form default, via _sibling.resolve_path).
    - The task's branch exists with the expected name.
    - ``wiki/active/<slug>/status.md`` exists with the expected title.
    - ``<worktree>/.vscode/settings.json`` has a non-green colour.
    - ``<worktree>/.millhouse/wiki`` is a working junction to the wiki clone.

Local-dev only. Requires a working ``git`` in PATH. No network — the wiki
uses a local bare repo as origin so push/pull stays on the filesystem.

Run from hub root:
    python plugins/mill/integration_tests/test-spawn.py

Exits 0 on PASS, 1 on any assertion failure (scratch dir preserved for
post-mortem).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
SCRATCH = HUB / ".scratch"


def _run(cmd: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Invoke ``cmd`` in ``cwd`` with UTF-8 output capture."""
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _setup_pair(container: Path) -> tuple[Path, Path, Path]:
    """
    Construct a minimal hub + wiki pair under ``container``.

    Layout mirrors real use:
        <container>/wiki.git                  — bare "remote"
        <container>/wiki                      — working clone of the bare
        <container>/hub                       — working hub repo
        <container>/hub/.millhouse/wiki       — junction to wiki clone

    Returns ``(hub, wiki, worktrees_dir)``.
    """
    container.mkdir(parents=True, exist_ok=True)
    bare = container / "wiki.git"
    wiki = container / "wiki"
    hub = container / "hub"
    worktrees_dir = container / "worktrees"

    # Bare wiki + clone. The bare acts as origin so mill-spawn's
    # sync_pull/write_commit_push paths exercise real push/pull.
    _run(["git", "init", "--bare", str(bare), "-b", "main"], cwd=container)
    _run(["git", "clone", str(bare), str(wiki)], cwd=container)
    _run(["git", "-C", str(wiki), "config", "user.email", "test@example.com"], cwd=container)
    _run(["git", "-C", str(wiki), "config", "user.name", "Test"], cwd=container)

    # Seed Home.md with one spawn-ready task so pick_task hits fast-path.
    (wiki / "Home.md").write_text(
        "# Tasks\n\n"
        "## Demo task [demo-task] [s]\n\n"
        "Seed task for the mill-spawn integration test.\n",
        encoding="utf-8",
    )
    (wiki / "_Sidebar.md").write_text(
        "### Navigation\n\n- [Home](Home)\n\n### Tasks\n\n- Demo task\n",
        encoding="utf-8",
    )
    (wiki / "config.yaml").write_text(
        "junctions:\n"
        "  .millhouse/wiki: <WIKI_PATH>\n"
        "  .active: <WIKI_PATH>/active/<SLUG>/\n"
        "\n"
        "spawn:\n"
        "  branch_prefix: test\n",
        encoding="utf-8",
    )
    _run(["git", "-C", str(wiki), "add", "."], cwd=container)
    _run(["git", "-C", str(wiki), "commit", "-m", "seed"], cwd=container)
    _run(["git", "-C", str(wiki), "push", "origin", "main"], cwd=container)

    # Hub repo — any non-empty git history is fine; mill-spawn only needs
    # the toplevel to be resolvable.
    hub.mkdir()
    _run(["git", "init", str(hub), "-b", "main"], cwd=container)
    _run(["git", "-C", str(hub), "config", "user.email", "test@example.com"], cwd=container)
    _run(["git", "-C", str(hub), "config", "user.name", "Test"], cwd=container)
    (hub / "README.md").write_text("hub test\n", encoding="utf-8")
    _run(["git", "-C", str(hub), "add", "README.md"], cwd=container)
    _run(["git", "-C", str(hub), "commit", "-m", "init"], cwd=container)

    # .millhouse/ with wiki junction + config.local.yaml (spawn overlay).
    millhouse = hub / ".millhouse"
    millhouse.mkdir()
    if sys.platform == "win32":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(millhouse / "wiki"), str(wiki)],
            check=True,
            capture_output=True,
        )
    else:
        os.symlink(str(wiki), str(millhouse / "wiki"))
    # Empty local overlay is fine — wiki/config.yaml carries everything.
    (millhouse / "config.local.yaml").write_text("", encoding="utf-8")

    return hub, wiki, worktrees_dir


def _cleanup_worktree_sibling(wt: Path) -> None:
    """Best-effort removal of a worktree dir (junctions + read-only files)."""
    if wt.exists():
        # On Windows some junction/readonly files resist shutil. Use git's
        # worktree remove when available, then fall back to shutil.
        shutil.rmtree(str(wt), ignore_errors=True)


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _run_spawn(hub: Path) -> subprocess.CompletedProcess:
    """Run mill-spawn against ``hub`` with --slug to avoid stdin."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "mill-spawn.py"), "--slug", "demo-task"],
        cwd=str(hub),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    container = SCRATCH / f"spawn-test-{uuid.uuid4().hex[:8]}"
    failed = False
    try:
        hub, wiki, worktrees_dir = _setup_pair(container)
        print(f"[test-spawn] container: {container}", file=sys.stderr)

        proc = _run_spawn(hub)
        print(f"--- mill-spawn stdout ---\n{proc.stdout}", file=sys.stderr)
        print(f"--- mill-spawn stderr ---\n{proc.stderr}", file=sys.stderr)
        _assert(proc.returncode == 0, f"mill-spawn exit={proc.returncode}")

        worktree = worktrees_dir / "demo-task"
        _assert(worktree.exists(), f"worktree dir missing: {worktree}")

        # Branch name should be test/demo-task (branch_prefix in seeded config.yaml).
        branches = _run(
            ["git", "-C", str(worktree), "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=container,
        ).stdout.strip()
        _assert(branches == "test/demo-task", f"branch={branches!r}")

        # Home.md flipped to [active].
        home_text = (wiki / "Home.md").read_text(encoding="utf-8")
        _assert(
            "[demo-task] [active]" in home_text,
            f"Home.md did not flip to [active]:\n{home_text}",
        )

        # status.md written with parent branch recorded.
        status_path = wiki / "active" / "demo-task" / "status.md"
        _assert(status_path.exists(), f"status.md missing: {status_path}")
        status_text = status_path.read_text(encoding="utf-8")
        _assert(
            "Demo task" in status_text and "phase: discussing" in status_text,
            f"status.md content unexpected:\n{status_text}",
        )
        _assert(
            "parent: main" in status_text,
            f"status.md missing parent branch:\n{status_text}",
        )

        # Per-worktree marker file written by mill-spawn.
        marker_path = worktree / ".millhouse" / "active.slug.md"
        _assert(marker_path.exists(), f"active.slug.md missing: {marker_path}")
        marker_text = marker_path.read_text(encoding="utf-8")
        _assert(
            "slug: demo-task" in marker_text and "branch: test/demo-task" in marker_text,
            f"active.slug.md content unexpected:\n{marker_text}",
        )

        # vscode settings with non-green colour.
        vscode_path = worktree / ".vscode" / "settings.json"
        _assert(vscode_path.exists(), f"vscode settings missing: {vscode_path}")
        vscode = json.loads(vscode_path.read_text(encoding="utf-8"))
        color = vscode.get("workbench.colorCustomizations", {}).get(
            "titleBar.activeBackground"
        )
        _assert(color is not None, f"colour missing in {vscode_path}")
        _assert(
            color.lower() != "#2d7d46",
            f"worktree got the hub-reserved green: {color}",
        )

        # Wiki junction in new worktree.
        wiki_junction = worktree / ".millhouse" / "wiki"
        _assert(
            wiki_junction.exists() and wiki_junction.is_dir(),
            f"wiki junction missing: {wiki_junction}",
        )
        _assert(
            (wiki_junction / "Home.md").exists(),
            "wiki junction does not resolve to the wiki clone",
        )

        print("PASS — mill-spawn end-to-end", file=sys.stderr)
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        failed = True
        return 1
    except Exception as exc:  # noqa: BLE001 — want full surface on unexpected
        print(f"FAIL (unexpected): {type(exc).__name__}: {exc}", file=sys.stderr)
        failed = True
        return 1
    finally:
        if failed:
            print(
                f"Scratch dir preserved for inspection: {container}",
                file=sys.stderr,
            )
        else:
            # Remove worktree registration BEFORE deleting the dir so git's
            # worktree bookkeeping stays consistent on repeated runs.
            try:
                _run(
                    ["git", "worktree", "remove", "--force", str(container / "worktrees" / "demo-task")],
                    cwd=container / "hub",
                    check=False,
                )
            except Exception:
                pass
            shutil.rmtree(str(container), ignore_errors=True)


if __name__ == "__main__":
    sys.path.insert(0, str(SCRIPTS))
    sys.exit(main())
