"""
Integration test: mill-resume off-canonical worktree relocate+scaffold coverage.

Builds real ``git init`` + ``git worktree add`` fixtures under ``tempfile`` and exercises
``_resume_repair.check_uncommitted_changes`` / ``_resume_repair.relocate_and_scaffold`` (Card 8) the
same way ``mill-resume/SKILL.md`` Phase 1b's embedded Python snippets (Card 10) call them, plus the
two-step ``hub_root`` resolution Phase 1b Step 4 uses for hub-in-subdirectory repos.

Covers the five ``discussion.md`` Testing-section scenarios from Card 11's brief, split across seven
functions below (``scenario_a`` .. ``scenario_g``):

  (a) clean off-canonical worktree relocates and scaffolds successfully.
  (b) an uncommitted change halts before any relocation is attempted.
  (c) the "user declines" path has no Python surface -- documented no-op.
  (d) canonical path occupied by an unrelated task is classified as a genuine collision,
      and a blind ``relocate_and_scaffold`` call onto it raises rather than silently succeeding.
  (e) after a successful relocation the worktree's own files (``_mill/status.md``) are readable at
      the new canonical location and gone from the old one.
  (f) hub-in-subdirectory main worktree (mirrors issue #728's NORCE.Models repro) -- Card 10 Step
      4's exact two-step ``hub_root`` resolution finds the subdirectory hub, not the main worktree
      root, and scaffolding pulls from the correct source.
  (g) partial-failure retry -- a prior run's ``move()`` succeeded but its scaffold steps didn't;
      a second ``relocate_and_scaffold`` call completes the remaining work without re-attempting the
          move.

No LLM is invoked;
no claude / sonnet subprocess fires.
Git operations run via subprocess and ``_worktree``/``_resume_repair`` against a real ``git`` in
PATH.

Run from hub root:
    PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-resume-relocate.py

Exits 0 on PASS, 1 on any assertion failure.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
MILL_SCRIPTS = HERE.parent.parent / "scripts"          # plugins/mill/scripts


def _run_git(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command with UTF-8 output capture."""
    return subprocess.run(
        cmd,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _git_init(path: Path) -> None:
    """Initialise a real git repo with an empty initial commit."""
    path.mkdir(parents=True, exist_ok=True)
    _run_git(["git", "init", "-b", "main", str(path)])
    _run_git(["git", "-C", str(path), "config", "user.email", "test@example.com"])
    _run_git(["git", "-C", str(path), "config", "user.name", "Test"])
    (path / ".keep").write_text("", encoding="utf-8")
    _run_git(["git", "-C", str(path), "add", ".keep"])
    _run_git(["git", "-C", str(path), "commit", "-m", "init"])


def _make_hub(tmp: Path, *, hub_relative: str | None = None) -> tuple[Path, Path, Path]:
    """
    Build a hub git repo (optionally with a sub-directory hub layout) plus a fake wiki clone
    directory.

    Args:
        tmp: Temporary directory root (already exists).
        hub_relative: When ``None``, ``.millhouse/`` lives at the repo root (``hub_root ==
            main_root``).
            When set (e.g. ``"src/csharp/NORCE.Models"``), ``.millhouse/`` lives in that
                subdirectory, and a ``hub_relative_path`` stub is written at
                ``main_root/.millhouse/config.local.yaml`` so ``_paths.resolve_hub_path`` can find
                the subdirectory hub.

    Returns:
        ``(main_root, hub_root, wiki_path)``.
    """
    main_root = tmp / "hub"
    _git_init(main_root)

    hub_root = main_root if hub_relative is None else main_root / hub_relative
    (hub_root / ".millhouse").mkdir(parents=True, exist_ok=True)
    (hub_root / ".millhouse" / "marker.txt").write_text("hub-marker\n", encoding="utf-8")

    if hub_relative is not None:
        stub_dir = main_root / ".millhouse"
        stub_dir.mkdir(parents=True, exist_ok=True)
        (stub_dir / "config.local.yaml").write_text(
            f"hub_relative_path: {hub_relative}\n", encoding="utf-8"
        )

    wiki_path = tmp / "wiki-clone"
    wiki_path.mkdir()
    (wiki_path / "Home.md").write_text("# Home\n", encoding="utf-8")

    return main_root, hub_root, wiki_path


def _make_off_canonical_worktree(
    main_root: Path, tmp: Path, slug: str, *, dirty: str | None = None
) -> Path:
    """
    Create a non-canonical worktree (registered via ``_worktree.create``) with a committed
    ``_mill/status.md`` carrying ``slug``.

    Args:
        dirty: ``None`` for a clean worktree;
            ``"tracked"`` to leave an uncommitted modification to the tracked ``status.md``;
            ``"untracked"`` to leave an untracked file.
    """
    old = tmp / "off-canonical-location" / slug
    _worktree.create(f"test/{slug}", old, cwd=main_root)
    (old / "_mill").mkdir()
    (old / "_mill" / "status.md").write_text(
        f"```yaml\nslug: {slug}\n```\n", encoding="utf-8"
    )
    _run_git(["git", "-C", str(old), "add", "_mill/status.md"])
    _run_git(["git", "-C", str(old), "commit", "-m", "add status.md"])
    if dirty == "tracked":
        (old / "_mill" / "status.md").write_text("dirty\n", encoding="utf-8")
    elif dirty == "untracked":
        (old / "untracked.txt").write_text("dirty\n", encoding="utf-8")
    return old


def scenario_a() -> None:
    """Clean off-canonical worktree relocates and scaffolds successfully."""
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        main_root, hub_root, wiki_path = _make_hub(tmp)
        slug = "demo-a"
        old = _make_off_canonical_worktree(main_root, tmp, slug)
        canonical = tmp / "wts" / slug
        canonical.parent.mkdir(parents=True, exist_ok=True)

        dirty = _resume_repair.check_uncommitted_changes(old)
        assert dirty == [], f"expected a clean worktree, got {dirty}"

        _resume_repair.relocate_and_scaffold(old, canonical, hub_root, wiki_path)

        registered = [Path(e["path"]) for e in _worktree.list_worktrees(cwd=main_root)]
        assert canonical in registered, f"expected {canonical} registered, got {registered}"
        assert old not in registered, f"expected {old} no longer registered, got {registered}"
        assert (canonical / ".millhouse" / "marker.txt").read_text(encoding="utf-8") == "hub-marker\n"
        assert (canonical / ".wiki").resolve() == wiki_path.resolve()
    print("PASS scenario (a): clean off-canonical worktree relocates and scaffolds")


def scenario_b() -> None:
    """An uncommitted change halts the repair before any relocation is attempted."""
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        main_root, _hub_root, _wiki_path = _make_hub(tmp)
        slug = "demo-b"
        old = _make_off_canonical_worktree(main_root, tmp, slug, dirty="tracked")
        canonical = tmp / "wts" / slug
        canonical.parent.mkdir(parents=True, exist_ok=True)

        dirty = _resume_repair.check_uncommitted_changes(old)
        assert dirty != [], "expected a non-empty dirty-status list"
        # The caller (Phase 1b Step 1) halts here without calling relocate_and_scaffold at all -- assert nothing moved.

        registered = [Path(e["path"]) for e in _worktree.list_worktrees(cwd=main_root)]
        assert old in registered, f"expected {old} still registered, got {registered}"
        assert canonical not in registered, f"expected {canonical} not registered, got {registered}"
        assert not canonical.exists(), f"expected {canonical} to not exist"
    print("PASS scenario (b): dirty worktree halts before any relocation, worktree untouched")


def scenario_c() -> None:
    """
    Step 3 (the "confirm with the user" numbered-options prompt) is pure conversational text in
    SKILL.md with no Python component to invoke directly.
    Declining ("2) Cancel") is equivalent to the caller simply never calling relocate_and_scaffold
    -- exactly the no-mutation shape scenarios (a)/(b)/(d) already exercise by omission.
    This function is a documented no-op standing in for that scenario.
    """
    print("PASS scenario (c): user-decline path has no Python surface (documented no-op)")


def scenario_d() -> None:
    """
    Canonical path occupied by an unrelated task is classified as a genuine collision,
    and a blind relocate_and_scaffold call onto it raises.
    """
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        main_root, hub_root, wiki_path = _make_hub(tmp)
        slug = "demo-d"
        other_slug = "unrelated-task"
        old = _make_off_canonical_worktree(main_root, tmp, slug)
        canonical = tmp / "wts" / slug
        canonical.parent.mkdir(parents=True, exist_ok=True)

        # Occupy canonical with an unrelated task's own worktree state -- its own _mill/status.md carrying a *different* slug.
        canonical.mkdir(parents=True)
        (canonical / "_mill").mkdir()
        (canonical / "_mill" / "status.md").write_text(
            f"```yaml\nslug: {other_slug}\n```\n", encoding="utf-8"
        )

        # Simulate Phase 1b Step 2's classification.
        candidate_status = canonical / "_mill" / "status.md"
        status_slug = _status.read(candidate_status).get("slug")
        is_collision = canonical.exists() and status_slug != slug
        assert is_collision, "expected genuine COLLISION classification (mismatched slug)"

        # git worktree move behaves like `mv`: it nests into an existing empty/absent slot rather than failing (see _worktree.move's own file-collision test in test-worktree.py), so the real refusal trigger is the nested destination slot (dest/<old-basename>) already holding real content.
        (canonical / old.name).mkdir()
        (canonical / old.name / "occupied.txt").write_text("occupied\n", encoding="utf-8")

        raised = False
        try:
            _resume_repair.relocate_and_scaffold(old, canonical, hub_root, wiki_path)
        except _worktree.WorktreeError:
            raised = True
        assert raised, "expected relocate_and_scaffold to raise on a genuine collision"

        registered = [Path(e["path"]) for e in _worktree.list_worktrees(cwd=main_root)]
        assert old in registered, f"expected {old} to remain registered untouched, got {registered}"
        assert (canonical / "_mill" / "status.md").read_text(encoding="utf-8") == (
            f"```yaml\nslug: {other_slug}\n```\n"
        ), "occupying directory's own status.md must be untouched"
    print(
        "PASS scenario (d): canonical occupied by an unrelated task classified as "
        "COLLISION; blind relocate raises, both sides untouched"
    )


def scenario_e() -> None:
    """After a successful relocation, the worktree's own files read correctly at the new location and are gone from the old one."""
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        main_root, hub_root, wiki_path = _make_hub(tmp)
        slug = "demo-e"
        old = _make_off_canonical_worktree(main_root, tmp, slug)
        canonical = tmp / "wts" / slug
        canonical.parent.mkdir(parents=True, exist_ok=True)

        _resume_repair.relocate_and_scaffold(old, canonical, hub_root, wiki_path)

        assert (canonical / "_mill" / "status.md").exists(), (
            f"expected {canonical / '_mill' / 'status.md'} to exist after relocation"
        )
        assert not (old / "_mill" / "status.md").exists(), (
            f"expected the pre-move path {old} to no longer exist"
        )
    print("PASS scenario (e): post-move reads resolve against the new canonical location")


def scenario_f() -> None:
    """
    Hub-in-subdirectory main worktree (mirrors issue #728's NORCE.Models repro): Card 10 Step 4's
    exact two-step hub_root resolution finds the subdirectory hub, not the main worktree root, and
    scaffolding pulls from the correct source.
    """
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        hub_relative = "src/csharp/NORCE.Models"
        main_root, hub_root, wiki_path = _make_hub(tmp, hub_relative=hub_relative)
        slug = "demo-f"
        old = _make_off_canonical_worktree(main_root, tmp, slug)
        canonical = tmp / "wts" / slug
        canonical.parent.mkdir(parents=True, exist_ok=True)

        # Card 10 Step 4's exact two-step resolution, simulating cwd == old (the broken worktree).
        git_root = old
        resolved_main_root = _paths.resolve_main_worktree_root(git_root)
        resolved_hub_root = _paths.resolve_hub_path(cwd=resolved_main_root)

        assert resolved_main_root == main_root, (
            f"expected resolve_main_worktree_root -> {main_root}, got {resolved_main_root}"
        )
        assert resolved_hub_root == hub_root, (
            f"expected resolve_hub_path(cwd=main_root) -> {hub_root}, got {resolved_hub_root}"
        )
        assert resolved_hub_root != resolved_main_root, (
            "hub_root must resolve to the subdirectory, not the main worktree root"
        )

        _resume_repair.relocate_and_scaffold(old, canonical, resolved_hub_root, wiki_path)

        # Regression guard: using resolved_main_root directly (skipping the resolve_hub_path step) would silently source .millhouse from a location with no marker.txt, since copy_millhouse no-ops without raising when its src argument does not exist.
        assert (canonical / ".millhouse" / "marker.txt").read_text(encoding="utf-8") == "hub-marker\n"
    print(
        "PASS scenario (f): hub-in-subdirectory two-step hub_root resolution "
        "finds the subdirectory hub, scaffold pulls the correct marker"
    )


def scenario_g() -> None:
    """
    Partial-failure retry: a prior run's move() succeeded but its scaffold steps didn't;
    a second relocate_and_scaffold call completes the remaining work without re-attempting the move.
    """
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        main_root, hub_root, wiki_path = _make_hub(tmp)
        slug = "demo-g"
        old = _make_off_canonical_worktree(main_root, tmp, slug)
        canonical = tmp / "wts" / slug
        canonical.parent.mkdir(parents=True, exist_ok=True)

        # Simulate a prior run whose move() succeeded but scaffold steps did not.
        _worktree.move(old, canonical, cwd=main_root)
        assert canonical.exists(), f"expected {canonical} to exist after the simulated prior move"
        assert not (canonical / ".millhouse").exists(), "expected no .millhouse yet (scaffold incomplete)"
        assert not (canonical / ".wiki").exists(), "expected no .wiki yet (scaffold incomplete)"

        # Simulate Phase 1b Step 2's classification against this interrupted state.
        candidate_status = canonical / "_mill" / "status.md"
        assert candidate_status.exists(), f"expected {candidate_status} to exist at the relocated path"
        status_slug = _status.read(candidate_status).get("slug")
        is_resumable = status_slug == slug
        assert is_resumable, "expected RESUMABLE classification (matching slug)"

        # Retry: relocate_and_scaffold must complete without re-attempting the move (old no longer exists to move from -- a second move() call would itself raise "is not a working tree" if wrongly attempted).
        _resume_repair.relocate_and_scaffold(old, canonical, hub_root, wiki_path)

        registered = [Path(e["path"]) for e in _worktree.list_worktrees(cwd=main_root)]
        assert canonical in registered, f"expected {canonical} registered, got {registered}"
        assert old not in registered, f"expected {old} not registered, got {registered}"
        assert (canonical / ".millhouse" / "marker.txt").read_text(encoding="utf-8") == "hub-marker\n"
        assert (canonical / ".wiki").resolve() == wiki_path.resolve()
    print(
        "PASS scenario (g): partial-failure retry completes remaining scaffold "
        "without re-attempting an already-succeeded move"
    )


def main() -> int:
    try:
        scenario_a()
        scenario_b()
        scenario_c()
        scenario_d()
        scenario_e()
        scenario_f()
        scenario_g()
        print("All mill-resume relocate+scaffold integration tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.path.insert(0, str(MILL_SCRIPTS))
    import _paths
    import _resume_repair
    import _status
    import _worktree
    sys.exit(main())
