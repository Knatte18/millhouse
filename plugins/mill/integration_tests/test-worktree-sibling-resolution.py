"""
Integration test: cross-resolver worktree-context regression guard.

Creates real ``git init`` + ``git worktree add`` fixtures under ``tempfile``
and asserts that ``_paths.resolve_wiki_path``,
``_paths.resolve_worktrees_dir``, and codeguide's
``resolve._sibling_anchor_default`` return identical paths whether called
from the main worktree's cwd or from a child worktree's cwd.

Run for both hub-form (repo dir named ``"hub"``) and prefix-form (arbitrary
repo name) layouts.

A regression in the walk-up logic — e.g. dropping the
``git rev-parse --git-common-dir`` call — flips the four worktree-form
assertions from PASS to FAIL.

Local-dev only. Requires a working ``git`` in PATH. No network, no claude CLI.

Run from the hub root:
    python plugins/mill/integration_tests/test-worktree-sibling-resolution.py

Exits 0 on PASS, 1 on any assertion failure.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
MILL_SCRIPTS = HERE.parent.parent / "scripts"          # plugins/mill/scripts
CODEGUIDE_SCRIPTS = HERE.parent.parent.parent / "codeguide" / "scripts"  # plugins/codeguide/scripts


def _run_git(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command with UTF-8 output capture."""
    return subprocess.run(
        cmd,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _make_fixture(tmp: Path, repo_dir_name: str) -> tuple[Path, Path]:
    """Create a minimal hub + linked worktree fixture under ``tmp``.

    Args:
        tmp: Temporary directory root (already exists).
        repo_dir_name: Name for the hub directory.  Pass ``"hub"`` for
            hub-form layout, anything else for prefix-form.

    Returns:
        ``(hub_root, worktree_root)`` — both are real git checkout roots.
    """
    hub_root = tmp / repo_dir_name
    hub_root.mkdir()

    _run_git(["git", "init", "-b", "main", str(hub_root)])
    _run_git(["git", "-C", str(hub_root), "config", "user.email", "test@example.com"])
    _run_git(["git", "-C", str(hub_root), "config", "user.name", "Test"])

    (hub_root / "README.md").write_text("hub test\n", encoding="utf-8")
    _run_git(["git", "-C", str(hub_root), "add", "README.md"])
    _run_git(["git", "-C", str(hub_root), "commit", "-m", "init"])

    if repo_dir_name == "hub":
        worktree_root = tmp / "worktrees" / "feat"
    else:
        worktree_root = tmp / f"{repo_dir_name}.worktrees" / "feat"

    worktree_root.parent.mkdir(parents=True, exist_ok=True)
    _run_git([
        "git", "-C", str(hub_root),
        "worktree", "add", str(worktree_root), "-b", "feat-branch",
    ])

    return hub_root, worktree_root


def _assert_resolvers_match(
    hub_root: Path,
    worktree_root: Path,
    expected_wiki: Path,
    expected_worktrees: Path,
    expected_codeguide: Path,
) -> None:
    """Run six resolver assertions: three from hub root, three from worktree root.

    Imports ``_paths`` and ``resolve`` (codeguide) lazily so ``sys.path`` is
    guaranteed to be fully set before any import occurs.
    """
    import _paths
    import resolve as codeguide_resolve

    # 1. Wiki path from hub root.
    result = _paths.resolve_wiki_path(hub_root)
    assert result == expected_wiki, (
        f"resolve_wiki_path(hub_root): {result!r} != {expected_wiki!r}"
    )
    print(f"PASS: resolve_wiki_path(hub_root) == {expected_wiki}")

    # 2. Wiki path from worktree root — regression guard.
    result = _paths.resolve_wiki_path(worktree_root)
    assert result == expected_wiki, (
        f"resolve_wiki_path(worktree_root): {result!r} != {expected_wiki!r}"
    )
    print(f"PASS: resolve_wiki_path(worktree_root) == {expected_wiki}")

    # 3. Worktrees container from hub root.
    result = _paths.resolve_worktrees_dir({}, hub_root)
    assert result == expected_worktrees, (
        f"resolve_worktrees_dir(hub_root): {result!r} != {expected_worktrees!r}"
    )
    print(f"PASS: resolve_worktrees_dir(hub_root) == {expected_worktrees}")

    # 4. Worktrees container from worktree root — regression guard.
    result = _paths.resolve_worktrees_dir({}, worktree_root)
    assert result == expected_worktrees, (
        f"resolve_worktrees_dir(worktree_root): {result!r} != {expected_worktrees!r}"
    )
    print(f"PASS: resolve_worktrees_dir(worktree_root) == {expected_worktrees}")

    # 5. Codeguide sibling anchor from hub root.
    result = codeguide_resolve._sibling_anchor_default(hub_root)
    assert result == expected_codeguide, (
        f"_sibling_anchor_default(hub_root): {result!r} != {expected_codeguide!r}"
    )
    print(f"PASS: _sibling_anchor_default(hub_root) == {expected_codeguide}")

    # 6. Codeguide sibling anchor from worktree root — codeguide regression guard.
    result = codeguide_resolve._sibling_anchor_default(worktree_root)
    assert result == expected_codeguide, (
        f"_sibling_anchor_default(worktree_root): {result!r} != {expected_codeguide!r}"
    )
    print(f"PASS: _sibling_anchor_default(worktree_root) == {expected_codeguide}")


def main() -> int:
    try:
        # ── Scenario A: hub-form ──────────────────────────────────────────────
        print("[Scenario A: hub-form]")
        with tempfile.TemporaryDirectory() as _tmp_a:
            tmp_a = Path(_tmp_a)
            hub_root_a, worktree_root_a = _make_fixture(tmp_a, "hub")
            expected_wiki_a = tmp_a / "wiki"
            expected_worktrees_a = tmp_a / "worktrees"
            expected_codeguide_a = tmp_a / "codeguide"
            try:
                _assert_resolvers_match(
                    hub_root_a, worktree_root_a,
                    expected_wiki_a, expected_worktrees_a, expected_codeguide_a,
                )
            finally:
                # Release worktree locks before tempdir cleanup (Windows).
                try:
                    _run_git([
                        "git", "-C", str(hub_root_a),
                        "worktree", "remove", "--force", str(worktree_root_a),
                    ], check=False)
                except Exception:
                    pass

        # ── Scenario B: prefix-form ───────────────────────────────────────────
        print("[Scenario B: prefix-form]")
        with tempfile.TemporaryDirectory() as _tmp_b:
            tmp_b = Path(_tmp_b)
            hub_root_b, worktree_root_b = _make_fixture(tmp_b, "foo")
            expected_wiki_b = tmp_b / "foo.wiki"
            expected_worktrees_b = tmp_b / "foo.worktrees"
            expected_codeguide_b = tmp_b / "foo.codeguide"
            try:
                _assert_resolvers_match(
                    hub_root_b, worktree_root_b,
                    expected_wiki_b, expected_worktrees_b, expected_codeguide_b,
                )
            finally:
                # Release worktree locks before tempdir cleanup (Windows).
                try:
                    _run_git([
                        "git", "-C", str(hub_root_b),
                        "worktree", "remove", "--force", str(worktree_root_b),
                    ], check=False)
                except Exception:
                    pass

        print("All worktree-sibling-resolution integration tests passed.")
        return 0

    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.path.insert(0, str(MILL_SCRIPTS))
    sys.path.insert(0, str(CODEGUIDE_SCRIPTS))
    sys.exit(main())
