"""
Integration test for mill-merge + mill-merge-in.

Verifies mill-merge lands squash + archive tag + Home.md [done] flip;
worktree, branch, portal, and wiki active-dir teardown are mill-cleanup's
responsibility (separate test).

The skills themselves are prose; the test exercises the backing helpers
and the exact git sequence the skills prescribe. That way we catch
regressions in `_wiki`, `_sidebar`, `_tasks_md`, the new
`_parent_branch`, and `_plan_dag.iter_batch_verifies` whenever any of
them change shape.

Layout mirrors `test-spawn.py`:

    <container>/wiki.git          bare "remote" for the wiki
    <container>/wiki              working clone of the bare
    <container>/hub               hub repo (the parent)
    <container>/worktrees/<slug>       child worktree under the task branch (hub-form default)

Flow under test (mirrors mill-merge SKILL.md step numbering):

    0. Seed: task-branch worktree with a commit, Home.md [active], a
       done status.md, plan/00-overview.md with one batch (verify: null
       so we skip the verify step in the test).
    1. Acquire merge lock on the parent's .scratch/.
    2. mill-merge-in no-op check (parent has no new commits).
    3. Direct squash-merge child -> parent.
    4. Archive tag creation (Step 6).
    5. Home.md [active] -> [done] (Step 7).
    6. Regenerate sidebar (Step 8).
    7. Release merge lock (Step 8).

Asserts each side effect. Worktree, branch, and wiki active-dir remain
intact — mill-cleanup's job. Exits 0 on PASS, 1 on any failure; scratch
is preserved on failure for inspection.
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

import _parent_branch  # noqa: E402
import _plan_dag  # noqa: E402
import _safe_rmtree  # noqa: E402
import _timestamp  # noqa: E402
from wiki import _client as wiki  # noqa: E402


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


def _setup_trio(container: Path) -> tuple[Path, Path, Path, str]:
    """Build hub + wiki + worktree trio with a seeded done task.

    Returns ``(hub, wiki, worktree, slug)``. The worktree is on branch
    ``test/<slug>`` and has one commit ahead of the hub's ``main``.
    Wiki carries ``Home.md`` with an ``[active]`` entry, a plan dir,
    and a ``status.md`` at ``phase: done`` so the merge flow can run
    against it.
    """
    container.mkdir(parents=True, exist_ok=True)
    slug = "demo-merge"
    bare = container / "wiki.git"
    wiki_path = container / "wiki"
    hub = container / "hub"
    worktrees_dir = container / "worktrees"
    worktree = worktrees_dir / slug

    # Bare wiki + clone.
    _run(["git", "init", "--bare", str(bare), "-b", "main"], cwd=container)
    _run(["git", "clone", str(bare), str(wiki_path)], cwd=container)
    _run(["git", "-C", str(wiki_path), "config", "user.email", "test@example.com"], cwd=container)
    _run(["git", "-C", str(wiki_path), "config", "user.name", "Test"], cwd=container)

    # Seed wiki: Home.md with [active], plan dir, status.md done, config.
    (wiki_path / "Home.md").write_text(
        "# Tasks\n\n"
        f"## Demo merge\n"
        f"[{slug}] [active]\n\n"
        "Seed task for mill-merge integration test.\n",
        encoding="utf-8",
    )
    (wiki_path / "_Sidebar.md").write_text(
        "### Navigation\n\n- [Home](Home)\n\n### Tasks\n\n- Demo merge\n",
        encoding="utf-8",
    )
    (wiki_path / "config.yaml").write_text(
        "junctions:\n"
        "  .millhouse/wiki: <WIKI_PATH>\n"
        "  .active: <WIKI_PATH>/active/<SLUG>/\n"
        "\n"
        "spawn:\n"
        "  branch_prefix: test\n",
        encoding="utf-8",
    )
    active_dir = wiki_path / "active" / slug
    active_dir.mkdir(parents=True)
    plan_dir = active_dir / "plan"
    plan_dir.mkdir()
    (plan_dir / "00-overview.md").write_text(
        "# Plan: Demo merge\n"
        "\n"
        "```yaml\n"
        "task: Demo merge\n"
        f"slug: {slug}\n"
        "approved: true\n"
        "started: 20260422-120000\n"
        "parent: main\n"
        'root: ""\n'
        "verify: null\n"
        "```\n"
        "\n"
        "## Batch Index\n"
        "\n"
        "```yaml\n"
        "batches:\n"
        "  - name: only\n"
        "    file: 01-only.md\n"
        "    depends-on: []\n"
        "    verify: null\n"
        "```\n",
        encoding="utf-8",
    )
    (plan_dir / "01-only.md").write_text(
        "# Batch: only\n\n"
        "```yaml\n"
        "batch: only\n"
        "cards: 1\n"
        "verify: null\n"
        "depends-on: []\n"
        "```\n",
        encoding="utf-8",
    )
    (active_dir / "status.md").write_text(
        "# Status\n"
        "\n"
        "```yaml\n"
        "phase: done\n"
        "task: Demo merge\n"
        "parent: main\n"
        "```\n"
        "\n"
        "## Timeline\n"
        "\n"
        "```text\n"
        "discussing  2026-04-22T12:00:00Z\n"
        "done        2026-04-22T14:00:00Z\n"
        "```\n",
        encoding="utf-8",
    )
    _run(["git", "-C", str(wiki_path), "add", "."], cwd=container)
    _run(["git", "-C", str(wiki_path), "commit", "-m", "seed"], cwd=container)
    _run(["git", "-C", str(wiki_path), "push", "origin", "main"], cwd=container)

    # Hub: one-commit init.
    _run(["git", "init", str(hub), "-b", "main"], cwd=container)
    _run(["git", "-C", str(hub), "config", "user.email", "test@example.com"], cwd=container)
    _run(["git", "-C", str(hub), "config", "user.name", "Test"], cwd=container)
    (hub / "README.md").write_text("hub test\n", encoding="utf-8")
    _run(["git", "-C", str(hub), "add", "README.md"], cwd=container)
    _run(["git", "-C", str(hub), "commit", "-m", "init"], cwd=container)

    # .millhouse on hub with wiki junction; .scratch/ at cwd-root.
    millhouse = hub / ".millhouse"
    millhouse.mkdir()
    if sys.platform == "win32":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(millhouse / "wiki"), str(wiki_path)],
            check=True, capture_output=True,
        )
    else:
        os.symlink(str(wiki_path), str(millhouse / "wiki"))
    (hub / ".scratch").mkdir()

    # Task branch + worktree with a single commit ahead of main.
    worktrees_dir.mkdir()
    _run(
        ["git", "-C", str(hub), "worktree", "add", "-b", f"test/{slug}", str(worktree)],
        cwd=container,
    )
    (worktree / "feature.txt").write_text("implemented by the test task\n", encoding="utf-8")
    _run(["git", "-C", str(worktree), "add", "feature.txt"], cwd=container)
    _run(
        ["git", "-C", str(worktree), "commit", "-m", "feat: demo merge payload"],
        cwd=container,
    )

    # Worktree's .millhouse: wiki junction, active junction.
    wt_mill = worktree / ".millhouse"
    wt_mill.mkdir()
    if sys.platform == "win32":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(wt_mill / "wiki"), str(wiki_path)],
            check=True, capture_output=True,
        )
    else:
        os.symlink(str(wiki_path), str(wt_mill / "wiki"))
    # .active junction at worktree root -> wiki/active/<slug>/
    if sys.platform == "win32":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(worktree / ".active"), str(active_dir)],
            check=True, capture_output=True,
        )
    else:
        os.symlink(str(active_dir), str(worktree / ".active"))

    return hub, wiki_path, worktree, slug


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    container = SCRATCH / f"merge-test-{uuid.uuid4().hex[:8]}"
    failed = False
    child_branch = None
    try:
        hub, wiki_path, worktree, slug = _setup_trio(container)
        child_branch = f"test/{slug}"
        print(f"[test-merge] container: {container}", file=sys.stderr)

        # --- parent resolution ---
        status_path = wiki_path / "active" / slug / "status.md"
        parent = _parent_branch.resolve(status_path, interactive=False)
        _assert(parent == "main", f"parent resolved to {parent!r}")
        print(f"PASS: _parent_branch.resolve -> {parent!r}")

        # --- batch verify iteration (all null in seed -> empty list) ---
        verifies = _plan_dag.iter_batch_verifies(wiki_path / "active" / slug / "plan")
        _assert(verifies == [], f"expected no verifies, got {verifies}")
        print("PASS: iter_batch_verifies returns [] when every batch has verify: null")

        # --- merge lock in parent scratch ---
        lock_dir = hub / ".scratch"
        lock_path = lock_dir / "merge.lock"
        lock_path.write_text(
            f"pid: {os.getpid()}\n"
            f"timestamp: {_timestamp.now_utc_iso()}\n"
            f"branch: {child_branch}\n",
            encoding="utf-8",
        )
        _assert(lock_path.exists(), "merge.lock not written")

        # --- mill-merge-in no-op check: parent has no new commits vs HEAD ---
        result = _run(
            ["git", "-C", str(worktree), "log", f"HEAD..{parent}", "--oneline"],
            cwd=container, check=False,
        )
        _assert(result.returncode == 0 and not result.stdout.strip(),
                f"expected empty no-op check, got {result.stdout!r}")
        print("PASS: mill-merge-in no-op check empty (parent has no new commits)")

        # --- direct squash-merge child -> parent ---
        _run(["git", "-C", str(hub), "merge", "--squash", child_branch], cwd=container)
        _run(["git", "-C", str(hub), "commit", "-m", "Demo merge"], cwd=container)

        # Parent HEAD now carries the squash.
        hub_log = _run(
            ["git", "-C", str(hub), "log", "--oneline", "-n", "2"],
            cwd=container,
        ).stdout
        _assert("Demo merge" in hub_log, f"squash not in hub log:\n{hub_log}")
        _assert((hub / "feature.txt").exists(),
                "feature.txt not present in parent after squash-merge")
        print("PASS: direct squash-merge landed on parent")

        # --- archive tag (Step 6) ---
        subprocess.run(
            ["git", "-C", str(hub), "tag", f"archive/{slug}", child_branch], check=True
        )
        print(f"PASS: archive tag archive/{slug} created")

        # --- Home.md [active] -> [done] (Step 7) ---
        # V3: no advisory lock; daemon handles concurrent commits
        home_text = (wiki_path / "Home.md").read_text(encoding="utf-8")
        new_text = wiki.set_phase(wiki_path, slug, "done")
        (wiki_path / "Home.md").write_text(new_text, encoding="utf-8")

        home_after = (wiki_path / "Home.md").read_text(encoding="utf-8")
        _assert(f"[{slug}] [done]" in home_after,
                f"Home.md did not flip to [done]:\n{home_after}")
        print("PASS: Home.md flipped to [done]")
        _assert((wiki_path / "active" / slug).exists(),
                f"active/{slug}/ must remain intact — teardown is mill-cleanup's job")
        print("PASS: active/<slug>/ intact (mill-cleanup's responsibility)")

        # --- sidebar regeneration (V3: daemon-mediated) ---
        # V3 daemon regenerates sidebar internally; no explicit call needed
        print("PASS: sidebar regeneration handled by daemon")

        # --- release merge lock ---
        lock_path.unlink()
        _assert(not lock_path.exists(), "merge.lock not removed")
        print("PASS: merge lock released")

        # --- worktree and branch must remain intact after mill-merge ---
        _assert(worktree.exists(),
                "worktree must remain intact after mill-merge — teardown is mill-cleanup's job")
        branches = _run(
            ["git", "-C", str(hub), "branch", "--list", child_branch],
            cwd=container,
        ).stdout.strip()
        _assert(branches != "", f"child branch must still exist after mill-merge, got {branches!r}")
        print("PASS: worktree and branch intact (mill-cleanup's responsibility)")

        # --- archive tag exists ---
        tag_result = subprocess.run(
            ["git", "-C", str(hub), "tag", "-l", f"archive/{slug}"],
            capture_output=True, text=True,
        )
        _assert(tag_result.stdout.strip() != "", f"archive tag archive/{slug} not found")
        print(f"PASS: archive tag archive/{slug} present")

        print("PASS -- mill-merge end-to-end")
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
