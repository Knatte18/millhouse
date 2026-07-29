"""Unit tests for plugins/mill/scripts/_resume_repair.py."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _worktree  # noqa: E402
from _resume_repair import check_uncommitted_changes, relocate_and_scaffold  # noqa: E402


def _git_init(path: Path) -> None:
    """Initialise a real git repo with an empty initial commit."""
    subprocess.run(["git", "init", "-b", "main", str(path)], check=False, capture_output=True)
    # Fallback for Git < 2.28 which does not support -b
    subprocess.run(
        ["git", "-C", str(path), "symbolic-ref", "HEAD", "refs/heads/main"],
        check=False, capture_output=True,
    )
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True, capture_output=True)
    (path / ".keep").write_text("", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", ".keep"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "init"], check=True, capture_output=True)


def main() -> int:
    try:
        # --- check_uncommitted_changes: clean worktree -> [] ---
        with tempfile.TemporaryDirectory() as tmp:
            wt = Path(tmp) / "wt"
            wt.mkdir()
            _git_init(wt)
            result = check_uncommitted_changes(wt)
            assert result == [], f"expected [] for clean worktree, got {result}"
            print("PASS check_uncommitted_changes — clean worktree returns []")

        # --- check_uncommitted_changes: modified tracked file -> non-empty ---
        with tempfile.TemporaryDirectory() as tmp:
            wt = Path(tmp) / "wt"
            wt.mkdir()
            _git_init(wt)
            (wt / ".keep").write_text("modified", encoding="utf-8")
            result = check_uncommitted_changes(wt)
            assert result != [], "expected non-empty list for a modified tracked file"
            print("PASS check_uncommitted_changes — modified tracked file returns non-empty list")

        # --- check_uncommitted_changes: untracked file -> non-empty ---
        with tempfile.TemporaryDirectory() as tmp:
            wt = Path(tmp) / "wt"
            wt.mkdir()
            _git_init(wt)
            (wt / "untracked.txt").write_text("new", encoding="utf-8")
            result = check_uncommitted_changes(wt)
            assert result != [], "expected non-empty list for an untracked file"
            print("PASS check_uncommitted_changes — untracked file returns non-empty list")

        # --- relocate_and_scaffold: end-to-end against real tempdir fixtures ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # Fake hub with a .millhouse/ marker file plus wiki/active alias subdirs.
            hub = tmp_path / "hub"
            hub.mkdir()
            _git_init(hub)
            (hub / ".millhouse").mkdir()
            (hub / ".millhouse" / "config.local.yaml").write_text("marker: yes\n", encoding="utf-8")
            (hub / ".millhouse" / "wiki").mkdir()
            (hub / ".millhouse" / "wiki" / "decoy.txt").write_text("wiki-alias", encoding="utf-8")
            (hub / ".millhouse" / "active").mkdir()
            (hub / ".millhouse" / "active" / "decoy.txt").write_text("active-alias", encoding="utf-8")

            # Fake wiki clone directory.
            wiki_path = tmp_path / "wiki-clone"
            wiki_path.mkdir()
            (wiki_path / "Home.md").write_text("# Home\n", encoding="utf-8")

            # "Old" worktree at a non-canonical path, registered via _worktree.create().
            old_worktree = tmp_path / "old-location"
            _worktree.create("repair-branch", old_worktree, cwd=hub)

            canonical = tmp_path / "canonical-location"

            relocate_and_scaffold(old_worktree, canonical, hub, wiki_path)

            registered = _worktree.list_worktrees(cwd=hub)
            registered_paths = [Path(e["path"]) for e in registered]
            assert canonical in registered_paths, (
                f"expected {canonical} registered after relocate_and_scaffold, got {registered_paths}"
            )
            assert old_worktree not in registered_paths, (
                f"expected {old_worktree} no longer registered, got {registered_paths}"
            )

            assert (canonical / ".millhouse" / "config.local.yaml").read_text(encoding="utf-8") == "marker: yes\n"
            assert not (canonical / ".millhouse" / "wiki").exists(), "wiki junction alias must not be copied"
            assert not (canonical / ".millhouse" / "active").exists(), "active junction alias must not be copied"

            wiki_link = canonical / ".wiki"
            assert wiki_link.exists(), "expected .wiki junction/symlink to exist at canonical location"
            assert wiki_link.resolve() == wiki_path.resolve(), (
                f"expected .wiki to resolve to {wiki_path}, got {wiki_link.resolve()}"
            )
            print("PASS relocate_and_scaffold — end-to-end move + .millhouse copy + .wiki junction")

        print("All _resume_repair unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
