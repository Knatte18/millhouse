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

Two further scenarios run after the flat-hub flow above, both against
nested-hub-layout fixtures (``hub_root != git_root``, see the plan's
"nested-hub-layout terminology" Shared Decision):

    - The `_setup_nested_hub_scenario` case (#497 bug 2) verifies the
      parent's own `_mill/status.md` survives a squash-merge untouched.
    - The `_setup_nested_verify_plan` case (#604) verifies
      `_plan_dag.iter_batch_verifies` resolves a batch's
      ``verify: {cwd: hub, command: ...}`` mapping to `hub_root`, and
      that replaying the command at that resolved cwd — not a fixed
      "worktree root" — is what makes it succeed.
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
import _status  # noqa: E402
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
    """
    Build hub + wiki + worktree trio with a seeded done task.

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

    # Upsert task in wiki via client so set_phase works later.
    wiki.upsert_task(
        wiki_path,
        slug,
        title="Demo merge",
        brief="Seed task for mill-merge integration test.",
        body="# Demo merge\n\nSeed task for mill-merge integration test.\n",
        status=None,
    )

    # Hub: one-commit init.
    _run(["git", "init", str(hub), "-b", "main"], cwd=container)
    _run(["git", "-C", str(hub), "config", "user.email", "test@example.com"], cwd=container)
    _run(["git", "-C", str(hub), "config", "user.name", "Test"], cwd=container)
    (hub / "README.md").write_text("hub test\n", encoding="utf-8")
    _run(["git", "-C", str(hub), "add", "README.md"], cwd=container)
    _run(["git", "-C", str(hub), "commit", "-m", "init"], cwd=container)

    # Bare origin remote for the hub, mirroring the wiki's bare + push pattern
    # above. Without this, the hub repo has no origin at all, and the
    # mill-merge-in no-op check's `git fetch origin` can never exercise the
    # fetch-succeeds branch of its MERGE_REF resolution.
    hub_origin = container / "hub-origin.git"
    _run(["git", "init", "--bare", str(hub_origin), "-b", "main"], cwd=container)
    _run(["git", "-C", str(hub), "remote", "add", "origin", str(hub_origin)], cwd=container)
    _run(["git", "-C", str(hub), "push", "origin", "main"], cwd=container)

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


def _setup_nested_hub_scenario(
    container: Path,
) -> tuple[Path, Path, Path, Path, str, str]:
    """
    Build a nested-hub scenario where parent branch tracks its own _mill/status.md.

    Creates:
    - Outer repo with hub at <repo>/src/hub (nested layout).
    - Parent branch with its own <hub>/_mill/status.md belonging to a different task.
    - Child branch with its own task state and a production file, then cleaned up.
    - Returns (repo, hub, wiki, parent_branch, child_branch, other_task_slug) for assertions.

    The test verifies that mill-merge's restore step (reset + checkout) preserves
    the parent's own _mill/status.md when squashing the child's cleanup commit.
    """
    container.mkdir(parents=True, exist_ok=True)
    parent_slug = "other-task"
    child_slug = "nested-merge"
    bare = container / "wiki.git"
    wiki_path = container / "wiki"
    outer_repo = container / "nested-repo"
    hub = outer_repo / "src" / "hub"

    # Initialize bare wiki and clone.
    _run(["git", "init", "--bare", str(bare), "-b", "main"], cwd=container)
    _run(["git", "clone", str(bare), str(wiki_path)], cwd=container)
    _run(["git", "-C", str(wiki_path), "config", "user.email", "test@example.com"], cwd=container)
    _run(["git", "-C", str(wiki_path), "config", "user.name", "Test"], cwd=container)

    # Seed wiki: config only (tasks will be upserted separately).
    (wiki_path / "config.yaml").write_text(
        "junctions:\n"
        "  .millhouse/wiki: <WIKI_PATH>\n"
        "  .active: <WIKI_PATH>/active/<SLUG>/\n"
        "\n"
        "spawn:\n"
        "  branch_prefix: test\n",
        encoding="utf-8",
    )
    (wiki_path / "Home.md").write_text("# Tasks\n\n", encoding="utf-8")
    _run(["git", "-C", str(wiki_path), "add", "."], cwd=container)
    _run(["git", "-C", str(wiki_path), "commit", "-m", "seed wiki config"], cwd=container)
    _run(["git", "-C", str(wiki_path), "push", "origin", "main"], cwd=container)

    # Initialize outer repo with hub subfolder structure.
    outer_repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", str(outer_repo), "-b", "main"], cwd=container)
    _run(["git", "-C", str(outer_repo), "config", "user.email", "test@example.com"], cwd=container)
    _run(["git", "-C", str(outer_repo), "config", "user.name", "Test"], cwd=container)

    # Create hub subfolder with mill-config.
    hub.mkdir(parents=True, exist_ok=True)
    (hub / "mill-config.yaml").write_text(
        "spawn:\n"
        '  branch_prefix: "test"\n'
        "paths:\n"
        "  status_md: _mill/status.md\n"
        "  discussion_file: _mill/discussion.md\n"
        "  reviews_dir: _mill/reviews\n",
        encoding="utf-8",
    )

    # Create initial production file at hub.
    (hub / "feature.py").write_text("def feature():\n    return 1\n", encoding="utf-8")
    _run(
        ["git", "-C", str(outer_repo), "add", "src/hub/mill-config.yaml", "src/hub/feature.py"],
        cwd=container,
    )
    _run(["git", "-C", str(outer_repo), "commit", "-m", "init hub"], cwd=container)

    # === Create parent branch (parent-feature) ===
    _run(
        ["git", "-C", str(outer_repo), "checkout", "-b", "parent-feature"],
        cwd=container,
    )

    # On parent branch: add parent's own _mill/status.md for a different task (other-task).
    task_dir = hub / "_mill"
    task_dir.mkdir(exist_ok=True)
    (task_dir / "status.md").write_text(
        "# Status\n"
        "\n"
        "```yaml\n"
        f"phase: done\n"
        f"task: Other task\n"
        f"parent: main\n"
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
    # Add a parent-side production file to distinguish the commit.
    (hub / "parent-file.py").write_text("def parent_func():\n    return 42\n", encoding="utf-8")
    _run(
        ["git", "-C", str(outer_repo), "add", "src/hub/_mill/status.md", "src/hub/parent-file.py"],
        cwd=container,
    )
    _run(
        ["git", "-C", str(outer_repo), "commit", "-m", "parent: add task state"],
        cwd=container,
    )

    # Store parent branch's status.md content for later assertion.
    parent_status_content = (task_dir / "status.md").read_text(encoding="utf-8")

    # === Create child branch from parent ===
    _run(
        ["git", "-C", str(outer_repo), "checkout", "-b", f"test/{child_slug}"],
        cwd=container,
    )

    # Child adds its own _mill/status.md (for nested-merge task, not other-task).
    (task_dir / "status.md").write_text(
        "# Status\n"
        "\n"
        "```yaml\n"
        f"phase: done\n"
        f"task: Nested merge\n"
        f"parent: parent-feature\n"
        "```\n"
        "\n"
        "## Timeline\n"
        "\n"
        "```text\n"
        "discussing  2026-04-22T13:00:00Z\n"
        "done        2026-04-22T15:00:00Z\n"
        "```\n",
        encoding="utf-8",
    )
    # Child adds its own production file.
    (hub / "child-feature.py").write_text("def child_func():\n    return 99\n", encoding="utf-8")
    _run(
        ["git", "-C", str(outer_repo), "add", "src/hub/_mill/status.md", "src/hub/child-feature.py"],
        cwd=container,
    )
    _run(
        ["git", "-C", str(outer_repo), "commit", "-m", "child: add task state and feature"],
        cwd=container,
    )

    # === Child cleanup commit (mirror mill-merge Step 4) ===
    # Remove _mill directory and commit.
    _run(
        ["git", "-C", str(outer_repo), "rm", "-r", "src/hub/_mill"],
        cwd=container,
    )
    _run(
        ["git", "-C", str(outer_repo), "commit", "-m", "chore: pre-merge cleanup"],
        cwd=container,
    )

    # Return paths and metadata for the test scenario.
    return (
        outer_repo,
        hub,
        wiki_path,
        "parent-feature",
        f"test/{child_slug}",
        parent_slug,
        parent_status_content,
    )


def _setup_nested_verify_plan(container: Path) -> tuple[Path, Path, Path]:
    """
    Build a minimal nested-hub plan directory for the merge-in Verify-cwd case.

    Creates a git repo at ``<container>/nested-verify-repo`` (the
    ``git_root``) with a hub subdirectory at ``src/hub`` (the
    ``hub_root``, a plain directory rather than its own git repo --
    a nested-hub-layout is a hub living in a subdirectory of a single
    git repo, per the "nested-hub-layout terminology" Shared Decision).
    The hub directory carries a marker file that exists only there, not
    at ``git_root``.

    The plan directory (nested under the hub, mirroring where a real
    task's ``_mill/plan/`` lives) declares one batch whose ``verify:``
    is the mapping form ``{cwd: hub, command: ...}``. The command
    checks for the hub-only marker file relative to its own cwd, so it
    only exits zero when actually run from ``hub_root`` -- proving that
    a merge-in replay honors the resolved cwd instead of always running
    at a fixed "worktree root" (the #604 bug being regression-tested
    here).

    Returns ``(git_root, hub_root, plan_dir)``.
    """
    container.mkdir(parents=True, exist_ok=True)
    git_root = container / "nested-verify-repo"
    hub_root = git_root / "src" / "hub"
    hub_root.mkdir(parents=True, exist_ok=True)

    _run(["git", "init", str(git_root), "-b", "main"], cwd=container)
    _run(["git", "-C", str(git_root), "config", "user.email", "test@example.com"], cwd=container)
    _run(["git", "-C", str(git_root), "config", "user.name", "Test"], cwd=container)

    # Hub-only marker: present at hub_root but absent at git_root, so
    # the verify command below distinguishes the two roots by its exit
    # code alone.
    (hub_root / "hub-marker.txt").write_text("hub\n", encoding="utf-8")
    _run(["git", "-C", str(git_root), "add", "src/hub/hub-marker.txt"], cwd=container)
    _run(["git", "-C", str(git_root), "commit", "-m", "seed nested hub"], cwd=container)

    plan_dir = hub_root / "_mill" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    verify_command = (
        'python -c "import pathlib,sys;'
        "sys.exit(0 if pathlib.Path('hub-marker.txt').exists() else 1)\""
    )
    (plan_dir / "00-overview.md").write_text(
        "# Plan: Nested verify-cwd\n"
        "\n"
        "```yaml\n"
        "task: Nested verify-cwd\n"
        "slug: nested-verify-cwd\n"
        "approved: true\n"
        "started: 20260706-120000\n"
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
        f"    verify:\n"
        f"      cwd: hub\n"
        f"      command: {verify_command}\n"
        "```\n",
        encoding="utf-8",
    )
    (plan_dir / "01-only.md").write_text(
        "# Batch: only\n\n"
        "```yaml\n"
        "batch: only\n"
        "cards: 1\n"
        "depends-on: []\n"
        "verify:\n"
        "  cwd: hub\n"
        f"  command: {verify_command}\n"
        "```\n",
        encoding="utf-8",
    )
    return git_root, hub_root, plan_dir


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    container = SCRATCH / f"merge-test-{uuid.uuid4().hex[:8]}"
    failed = False
    child_branch = None
    try:
        # === Run flat-hub scenario (existing test) ===
        hub, wiki_path, worktree, slug = _setup_trio(container)
        child_branch = f"test/{slug}"
        print(f"[test-merge] flat-hub scenario container: {container}", file=sys.stderr)

        # --- parent resolution ---
        status_path = wiki_path / "active" / slug / "status.md"
        parent = _parent_branch.resolve(status_path, interactive=False)
        _assert(parent == "main", f"parent resolved to {parent!r}")
        print(f"PASS: _parent_branch.resolve -> {parent!r}")

        # --- batch verify iteration (all null in seed -> empty list) ---
        # Flat-layout fixture: hub_root == git_root == hub, matching the
        # invariant established by the "nested-hub-layout terminology"
        # Shared Decision. The all-null case is unaffected by the
        # tuple-shape change (still an empty list either way), but the
        # call must type-check against the batch-3 signature.
        verifies = _plan_dag.iter_batch_verifies(wiki_path / "active" / slug / "plan", hub, hub)
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

        # --- mill-merge-in no-op check: fetch + resolve MERGE_REF, then diff HEAD..MERGE_REF ---
        # Replicates SKILL.md's step 1 sequence exactly: fetch origin, prefer
        # origin/<parent-branch> when it exists and local <parent-branch> is
        # not ahead of it, else fall back to the local <parent-branch>.
        _run(["git", "-C", str(worktree), "fetch", "origin", parent], cwd=container, check=False)
        rev_parse = _run(
            ["git", "-C", str(worktree), "rev-parse", "--verify", "--quiet",
             f"refs/remotes/origin/{parent}"],
            cwd=container, check=False,
        )
        if rev_parse.returncode == 0:
            ancestor_check = _run(
                ["git", "-C", str(worktree), "merge-base", "--is-ancestor",
                 parent, f"origin/{parent}"],
                cwd=container, check=False,
            )
            merge_ref = f"origin/{parent}" if ancestor_check.returncode == 0 else parent
        else:
            merge_ref = parent
        # The hub's origin remote is freshly pushed and local main has not
        # advanced since (see _setup_trio), so this must resolve to
        # origin/main -- proving the test exercises the fetch-succeeds
        # branch of MERGE_REF resolution, not just the local-ref fallback.
        _assert(merge_ref == "origin/main",
                f"expected MERGE_REF to resolve to origin/main, got {merge_ref!r}")
        result = _run(
            ["git", "-C", str(worktree), "log", f"HEAD..{merge_ref}", "--oneline"],
            cwd=container, check=False,
        )
        _assert(result.returncode == 0 and not result.stdout.strip(),
                f"expected empty no-op check, got {result.stdout!r}")
        print(f"PASS: mill-merge-in no-op check empty (MERGE_REF={merge_ref!r}, "
              f"parent has no new commits)")

        # --- seed hub's own _mill/status.md on main (true worktree-mode #648 fixture) ---
        # hub and worktree here are genuinely separate directories -- the true
        # worktree-mode layout #648 was reported against, unlike
        # _setup_nested_hub_scenario's same-directory branch-switching. hub has
        # no _mill/ at all on main yet, and a bare `git checkout -- <pathspec>`
        # fails with "pathspec ... did not match any file(s) known to git" when
        # the target ref has nothing there -- independent of the worktree-mode
        # bug this scenario targets -- so we seed a trivial, distinguishable
        # status.md here, committed on main BEFORE the squash, so the restore
        # commands below have something real to act on and to protect.
        hub_mill_dir = hub / "_mill"
        hub_mill_dir.mkdir()
        hub_status_content = "phase: done\ntask: Unrelated hub task\n"
        (hub_mill_dir / "status.md").write_text(hub_status_content, encoding="utf-8")
        _run(["git", "-C", str(hub), "add", "_mill/status.md"], cwd=container)
        _run(
            ["git", "-C", str(hub), "commit", "-m", "hub: seed own _mill/status.md"],
            cwd=container,
        )

        # --- dirty-parent-worktree preflight (#705) ---
        # Proves the underlying `git status --porcelain --untracked-files=no`
        # check mill-merge/SKILL.md's Step 5 now documents actually flags
        # both halt scenarios from the operator-facing message (independent
        # uncommitted edit, and a mid-Step-5-retry partially-applied squash)
        # and ignores untracked-only noise. None of the three cases needs a
        # wiki, worktree, or junctions -- a plain two-branch git repo is
        # enough -- so each gets its own lightweight fixture directly at a
        # fresh container path, instead of a `_setup_trio()` spin-up.

        # Scenario (a): independent uncommitted edit in the parent worktree.
        container_dirty = SCRATCH / f"merge-test-dirty-{uuid.uuid4().hex[:8]}"
        _run(["git", "init", str(container_dirty), "-b", "main"], cwd=SCRATCH)
        _run(["git", "-C", str(container_dirty), "config", "user.email", "test@example.com"], cwd=SCRATCH)
        _run(["git", "-C", str(container_dirty), "config", "user.name", "Test"], cwd=SCRATCH)
        (container_dirty / "README.md").write_text("dirty test\n", encoding="utf-8")
        _run(["git", "-C", str(container_dirty), "add", "README.md"], cwd=SCRATCH)
        _run(["git", "-C", str(container_dirty), "commit", "-m", "init"], cwd=SCRATCH)

        uncommitted_content = "dirty test\nuncommitted edit\n"
        (container_dirty / "README.md").write_text(uncommitted_content, encoding="utf-8")
        dirty_status = _run(
            ["git", "-C", str(container_dirty), "status", "--porcelain", "--untracked-files=no"],
            cwd=SCRATCH,
        )
        _assert(
            dirty_status.stdout.strip() != "",
            f"expected non-empty status for independent uncommitted edit, got {dirty_status.stdout!r}",
        )
        _assert(
            (container_dirty / "README.md").read_text(encoding="utf-8") == uncommitted_content,
            "expected the uncommitted edit to remain untouched -- proving the documented halt "
            "means the squash step is never attempted",
        )
        dirty_log = _run(
            ["git", "-C", str(container_dirty), "log", "--oneline", "-n", "1"],
            cwd=SCRATCH,
        )
        _assert(
            "squash" not in dirty_log.stdout.lower(),
            f"expected no squash-merge commit on top of the uncommitted edit, got {dirty_log.stdout!r}",
        )
        print("PASS: dirty-parent-worktree preflight flags an independent uncommitted edit (#705)")

        # Scenario (b): mid-Step-5-retry -- merge --squash staged but never committed.
        container_retry = SCRATCH / f"merge-test-retry-{uuid.uuid4().hex[:8]}"
        _run(["git", "init", str(container_retry), "-b", "main"], cwd=SCRATCH)
        _run(["git", "-C", str(container_retry), "config", "user.email", "test@example.com"], cwd=SCRATCH)
        _run(["git", "-C", str(container_retry), "config", "user.name", "Test"], cwd=SCRATCH)
        (container_retry / "README.md").write_text("retry test\n", encoding="utf-8")
        _run(["git", "-C", str(container_retry), "add", "README.md"], cwd=SCRATCH)
        _run(["git", "-C", str(container_retry), "commit", "-m", "init"], cwd=SCRATCH)

        _run(["git", "-C", str(container_retry), "checkout", "-b", "feature-branch"], cwd=SCRATCH)
        (container_retry / "feature.txt").write_text("feature\n", encoding="utf-8")
        _run(["git", "-C", str(container_retry), "add", "feature.txt"], cwd=SCRATCH)
        _run(["git", "-C", str(container_retry), "commit", "-m", "feature"], cwd=SCRATCH)
        _run(["git", "-C", str(container_retry), "checkout", "main"], cwd=SCRATCH)
        # Simulates a Step 5 that failed between `merge --squash` and `commit`:
        # the squash content is staged, but the commit that would land it never ran.
        _run(["git", "-C", str(container_retry), "merge", "--squash", "feature-branch"], cwd=SCRATCH)

        retry_status = _run(
            ["git", "-C", str(container_retry), "status", "--porcelain", "--untracked-files=no"],
            cwd=SCRATCH,
        )
        _assert(
            retry_status.stdout.strip() != "",
            f"expected non-empty status for a partially-applied squash (staged, not committed), "
            f"got {retry_status.stdout!r}",
        )
        print(
            "PASS: dirty-parent-worktree preflight flags a mid-Step-5-retry partially-applied "
            "squash identically to an independent edit (#705) -- this is exactly why the halt "
            "message documents two scenarios rather than auto-distinguishing them in the check"
        )

        # Scenario (c) negative check: untracked-only noise must NOT trip the check.
        container_untracked = SCRATCH / f"merge-test-untracked-{uuid.uuid4().hex[:8]}"
        _run(["git", "init", str(container_untracked), "-b", "main"], cwd=SCRATCH)
        _run(["git", "-C", str(container_untracked), "config", "user.email", "test@example.com"], cwd=SCRATCH)
        _run(["git", "-C", str(container_untracked), "config", "user.name", "Test"], cwd=SCRATCH)
        (container_untracked / "README.md").write_text("untracked test\n", encoding="utf-8")
        _run(["git", "-C", str(container_untracked), "add", "README.md"], cwd=SCRATCH)
        _run(["git", "-C", str(container_untracked), "commit", "-m", "init"], cwd=SCRATCH)

        (container_untracked / "scratch-note.txt").write_text("untracked\n", encoding="utf-8")
        untracked_status = _run(
            ["git", "-C", str(container_untracked), "status", "--porcelain", "--untracked-files=no"],
            cwd=SCRATCH,
        )
        _assert(
            untracked_status.stdout.strip() == "",
            f"expected empty status for untracked-only noise (--untracked-files=no scoping), "
            f"got {untracked_status.stdout!r}",
        )
        print("PASS: dirty-parent-worktree preflight ignores untracked-only noise (#705)")

        # --- direct squash-merge child -> parent ---
        _run(["git", "-C", str(hub), "merge", "--squash", child_branch], cwd=container)

        # --- Repro #648 first: OLD absolute, child-worktree-anchored pathspec ---
        # An out-of-repo absolute pathspec is rejected by git before any
        # pathspec-match check runs, so this reproduces the failure regardless
        # of the seeded content above -- proving the fixture actually
        # reproduces #648's failure before proving the fix resolves it. Both
        # commands fail without touching hub's index/working tree, so no
        # cleanup of hub's state is needed before the fix sub-step.
        repro_reset = _run(
            ["git", "-C", str(hub), "reset", "-q", "HEAD", "--", str(worktree / "_mill")],
            cwd=container, check=False,
        )
        repro_checkout = _run(
            ["git", "-C", str(hub), "checkout", "--", str(worktree / "_mill")],
            cwd=container, check=False,
        )
        repro_combined = (
            repro_reset.stdout + repro_reset.stderr
            + repro_checkout.stdout + repro_checkout.stderr
        )
        _assert(
            repro_reset.returncode != 0 and repro_checkout.returncode != 0,
            f"expected both OLD absolute-pathspec restore commands to fail, "
            f"got reset rc={repro_reset.returncode} checkout rc={repro_checkout.returncode}",
        )
        _assert(
            "outside repository" in repro_combined,
            f"expected 'outside repository' in restore-command output, got:\n{repro_combined}",
        )
        print(
            "PASS: repro -- OLD absolute worktree-anchored pathspec fails "
            "with 'outside repository' (#648)"
        )

        # --- Prove the fix: corrected repo-relative pathspec (Batch 3 Card 8) ---
        fix_reset = _run(["git", "-C", str(hub), "reset", "-q", "HEAD", "--", "_mill"], cwd=container)
        fix_checkout = _run(["git", "-C", str(hub), "checkout", "--", "_mill"], cwd=container)
        _assert(
            fix_reset.returncode == 0 and fix_checkout.returncode == 0,
            f"expected corrected repo-relative restore commands to succeed, "
            f"got reset rc={fix_reset.returncode} checkout rc={fix_checkout.returncode}",
        )
        print("PASS: fix -- repo-relative pathspec restores hub's own _mill/ (#648)")

        _run(["git", "-C", str(hub), "commit", "-m", "Demo merge"], cwd=container)

        # --- hub's own _mill/status.md survives the squash byte-identical ---
        # Mirrors _setup_nested_hub_scenario's existing "parent's own
        # status.md survives the squash" assertion, but this time in the true
        # separate-worktree layout that assertion never actually covered.
        hub_status_after = (hub / "_mill" / "status.md").read_text(encoding="utf-8")
        _assert(
            hub_status_after == hub_status_content,
            f"hub's own _mill/status.md was not preserved by the squash restore.\n"
            f"Expected:\n{hub_status_content}\n\nGot:\n{hub_status_after}",
        )
        print("PASS: hub's own _mill/status.md preserved byte-identical (true worktree-mode #648)")

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
        wiki.set_phase(wiki_path, slug, "done")
        home_after = (wiki_path / "Home.md").read_text(encoding="utf-8")
        _assert(
            "[done]" in home_after and slug in home_after,
            f"Home.md did not flip to [done]:\n{home_after}",
        )
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

        print("PASS -- mill-merge end-to-end (flat-hub scenario)")

        # === Phase-gate slug-mismatch fallback sub-scenario (#656/#659/#662) ===
        # Simulates the post-Step-3-corruption state mill-finalize's restore
        # path produces (this task's Batch 2 fix): a status.md belonging to a
        # DIFFERENT, foreign task left behind at the worktree's _mill/ path --
        # mirroring _setup_nested_hub_scenario's existing "other-task" foreign
        # status.md pattern.
        foreign_mill_dir = worktree / "_mill"
        foreign_mill_dir.mkdir(exist_ok=True)
        (foreign_mill_dir / "status.md").write_text(
            "# Status\n"
            "\n"
            "```yaml\n"
            "slug: other-task\n"
            "phase: discussing\n"
            "parent: main\n"
            "```\n"
            "\n"
            "## Timeline\n"
            "\n"
            "```text\n"
            "discussing  2026-04-22T12:00:00Z\n"
            "```\n",
            encoding="utf-8",
        )

        # Mirror mill-merge's corrected Entry Step 5 phase-gate logic directly
        # as plain test code (this logic is orchestration prose in SKILL.md,
        # not an importable function, so the test replicates the same
        # two-call sequence Batch 3 Card 7 documents). Read the raw `slug:`
        # field -- NOT `_status.read_slug`, which falls back to the parent
        # directory name (always literally "_mill" here) when the field is
        # absent, so it can never distinguish "absent" from "present and
        # different" the way this check needs to.
        raw_slug = _status.read_full(foreign_mill_dir / "status.md")["yaml"].get("slug")
        _assert(raw_slug is not None, "expected foreign status.md to carry a slug: field")
        _assert(
            raw_slug != slug,
            f"expected foreign status.md's slug {raw_slug!r} to differ from {slug!r}",
        )
        print("PASS: raw slug: field detected as present and mismatched")

        # On mismatch, the phase gate falls through to the wiki-lookup path
        # instead of trusting the corrupted file's phase:/parent: fields --
        # proving the documented wiki-fallback path resolves demo-merge's
        # real state (flipped to "done" earlier in this scenario), not the
        # foreign task's phase: discussing.
        task = wiki.get_task(wiki_path, slug)
        _assert(
            task is not None and task.get("status") == "done",
            f"expected wiki fallback to report demo-merge's real status 'done', got {task!r}",
        )
        print("PASS: wiki-fallback resolves demo-merge's real status, not foreign phase: discussing")

        print("PASS -- mill-merge phase-gate slug-mismatch fallback (#656/#659/#662)")

        # === Run nested-hub scenario (new test for #497 bug 2) ===
        print(f"\n[test-merge] nested-hub scenario starting", file=sys.stderr)
        container_nested = SCRATCH / f"merge-test-nested-{uuid.uuid4().hex[:8]}"
        (
            outer_repo,
            nested_hub,
            nested_wiki_path,
            parent_branch,
            nested_child_branch,
            parent_task_slug,
            parent_status_content,
        ) = _setup_nested_hub_scenario(container_nested)
        print(f"[test-merge] nested-hub container: {container_nested}", file=sys.stderr)

        # --- Perform squash-merge with restore step (mill-merge Step 5) ---
        # On parent branch, run the squash-merge sequence verbatim.
        _run(
            ["git", "-C", str(outer_repo), "checkout", parent_branch],
            cwd=container_nested,
        )
        task_dir_name = "src/hub/_mill"
        _run(
            ["git", "-C", str(outer_repo), "merge", "--squash", nested_child_branch],
            cwd=container_nested,
        )
        # Restore step: reset and checkout the parent's own _mill from HEAD.
        _run(
            ["git", "-C", str(outer_repo), "reset", "-q", "HEAD", "--", task_dir_name],
            cwd=container_nested,
        )
        _run(
            ["git", "-C", str(outer_repo), "checkout", "--", task_dir_name],
            cwd=container_nested,
        )
        # Commit the squash (without the restored _mill changes staged).
        _run(
            ["git", "-C", str(outer_repo), "commit", "-m", "Nested merge"],
            cwd=container_nested,
        )

        # --- Assertion (a): parent's _mill/status.md is byte-identical to original ---
        parent_status_after = (nested_hub / "_mill" / "status.md").read_text(
            encoding="utf-8"
        )
        _assert(
            parent_status_after == parent_status_content,
            f"parent _mill/status.md was modified by squash.\n"
            f"Expected:\n{parent_status_content}\n\n"
            f"Got:\n{parent_status_after}",
        )
        print("PASS: parent's _mill/status.md preserved byte-identical")

        # --- Assertion (b): squash commit stat does NOT contain _mill paths ---
        stat_result = _run(
            ["git", "-C", str(outer_repo), "show", "--stat", "HEAD"],
            cwd=container_nested,
        )
        stat_output = stat_result.stdout
        _assert(
            "_mill" not in stat_output and ".mill" not in stat_output,
            f"squash commit stat contains _mill paths:\n{stat_output}",
        )
        print("PASS: squash commit stat does not contain _mill paths")

        # --- Assertion (c): archived child commit still has cleanup state ---
        # Create archive tag on the nested child branch.
        _run(
            ["git", "-C", str(outer_repo), "tag", f"archive/{parent_task_slug}-nested", nested_child_branch],
            cwd=container_nested,
        )
        # Verify the tag resolves to a commit.
        tag_verify = _run(
            ["git", "-C", str(outer_repo), "rev-list", "-n", "1", f"archive/{parent_task_slug}-nested"],
            cwd=container_nested,
        )
        _assert(
            tag_verify.stdout.strip() != "",
            f"archive tag archive/{parent_task_slug}-nested did not resolve",
        )
        # Verify the archive tag's tree does not contain _mill (the cleanup commit removed it).
        tree_files = _run(
            ["git", "-C", str(outer_repo), "ls-tree", "-r", "--name-only", f"archive/{parent_task_slug}-nested"],
            cwd=container_nested,
        )
        _assert(
            "_mill" not in tree_files.stdout and ".mill" not in tree_files.stdout,
            f"archived tag tree contains _mill paths, cleanup not preserved:\n{tree_files.stdout}",
        )
        print("PASS: archive tag resolves and preserves child cleanup state (no _mill)")

        print("PASS -- mill-merge nested-hub scenario (preserves parent _mill/status.md)")

        # === Run nested verify-cwd scenario (new test for #604 merge-in replay) ===
        print("\n[test-merge] nested verify-cwd scenario starting", file=sys.stderr)
        container_verify = SCRATCH / f"merge-test-verify-{uuid.uuid4().hex[:8]}"
        verify_git_root, verify_hub_root, verify_plan_dir = _setup_nested_verify_plan(
            container_verify
        )
        print(f"[test-merge] nested verify-cwd container: {container_verify}", file=sys.stderr)

        # --- iter_batch_verifies resolves the mapping-form cwd to hub_root ---
        verify_triples = _plan_dag.iter_batch_verifies(
            verify_plan_dir, verify_hub_root, verify_git_root
        )
        _assert(
            len(verify_triples) == 1,
            f"expected exactly one verify triple, got {verify_triples}",
        )
        _verify_name, verify_cmd, verify_cwd = verify_triples[0]
        _assert(
            verify_cwd == verify_hub_root,
            f"expected mapping-form cwd to resolve to hub_root {verify_hub_root}, got {verify_cwd}",
        )
        print("PASS: iter_batch_verifies resolves {cwd: hub, command: ...} to hub_root")

        # --- mirror mill-merge-in's Step 4 cwd resolution rule: hub_root
        #     for cwd == hub_root, git_root for cwd == git_root, hub_root
        #     for cwd is None (the string-form default) ---
        if verify_cwd == verify_git_root:
            resolved_cwd = verify_git_root
        else:
            resolved_cwd = verify_hub_root

        # --- replaying the command at the resolved hub_root succeeds ---
        replay_result = subprocess.run(
            verify_cmd, shell=True, cwd=str(resolved_cwd), capture_output=True, text=True,
        )
        _assert(
            replay_result.returncode == 0,
            f"replayed verify command failed at resolved hub_root cwd "
            f"(stdout={replay_result.stdout!r} stderr={replay_result.stderr!r})",
        )
        print("PASS: replayed verify command succeeds when run at resolved hub_root")

        # --- the same command fails at git_root, confirming this fixture
        #     actually distinguishes hub_root from git_root -- and that a
        #     regression back to a fixed "worktree root" would be caught ---
        wrong_cwd_result = subprocess.run(
            verify_cmd, shell=True, cwd=str(verify_git_root), capture_output=True, text=True,
        )
        _assert(
            wrong_cwd_result.returncode != 0,
            "verify command unexpectedly succeeded at git_root -- fixture cannot "
            "distinguish hub_root from git_root",
        )
        print("PASS: same command fails at git_root, confirming the fixture distinguishes cwd")

        print("PASS -- mill-merge-in Verify step replays nested-layout batch at resolved hub_root")
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
            if "container_nested" in locals():
                print(f"Scratch preserved: {container_nested}", file=sys.stderr)
            if "container_verify" in locals():
                print(f"Scratch preserved: {container_verify}", file=sys.stderr)
            if "container_dirty" in locals():
                print(f"Scratch preserved: {container_dirty}", file=sys.stderr)
            if "container_retry" in locals():
                print(f"Scratch preserved: {container_retry}", file=sys.stderr)
            if "container_untracked" in locals():
                print(f"Scratch preserved: {container_untracked}", file=sys.stderr)
        else:
            _safe_rmtree.safe_rmtree(container, allowed_root=container, ignore_errors=True)
            if "container_nested" in locals():
                _safe_rmtree.safe_rmtree(
                    container_nested,
                    allowed_root=container_nested,
                    ignore_errors=True,
                )
            if "container_verify" in locals():
                _safe_rmtree.safe_rmtree(
                    container_verify,
                    allowed_root=container_verify,
                    ignore_errors=True,
                )
            if "container_dirty" in locals():
                _safe_rmtree.safe_rmtree(
                    container_dirty,
                    allowed_root=container_dirty,
                    ignore_errors=True,
                )
            if "container_retry" in locals():
                _safe_rmtree.safe_rmtree(
                    container_retry,
                    allowed_root=container_retry,
                    ignore_errors=True,
                )
            if "container_untracked" in locals():
                _safe_rmtree.safe_rmtree(
                    container_untracked,
                    allowed_root=container_untracked,
                    ignore_errors=True,
                )


if __name__ == "__main__":
    sys.exit(main())
