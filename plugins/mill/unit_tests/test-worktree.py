"""Unit tests for plugins/mill/scripts/_worktree.py."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _worktree import WorktreeError, copy_millhouse, list_worktrees, remove  # noqa: E402


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
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / ".millhouse"
            src.mkdir()
            (src / "keep").mkdir()
            (src / "keep" / "file.txt").write_text("hello", encoding="utf-8")
            (src / "wiki").mkdir()
            (src / "wiki" / "decoy.txt").write_text("wiki-alias", encoding="utf-8")
            (src / "active").mkdir()
            (src / "active" / "decoy.txt").write_text("active-alias", encoding="utf-8")
            (src / "plainfile.txt").write_text("top-level", encoding="utf-8")

            dst = tmp_path / "worktree" / ".millhouse"
            copy_millhouse(src, dst, exclude={"wiki", "active"})

            assert (dst / "keep" / "file.txt").read_text(encoding="utf-8") == "hello"
            assert (dst / "plainfile.txt").read_text(encoding="utf-8") == "top-level"
            assert not (dst / "wiki").exists(), "wiki junction alias must not be copied"
            assert not (dst / "active").exists(), "active junction alias must not be copied"
            print("PASS: copy_millhouse propagates non-excluded entries (excludes junction aliases)")

        # --- list_worktrees: single main worktree ---
        with tempfile.TemporaryDirectory() as tmp:
            hub = Path(tmp)
            _git_init(hub)
            wt_result = list_worktrees(hub)
            assert len(wt_result) == 1, f"expected 1 worktree, got {len(wt_result)}"
            assert Path(wt_result[0]["path"]) == hub, f"expected path={hub!s}, got {wt_result[0]['path']!r}"
            assert wt_result[0]["branch"] == "main", f"expected branch='main', got {wt_result[0]['branch']!r}"
            print("PASS list_worktrees — single main worktree")

        # --- list_worktrees: two worktrees ---
        with tempfile.TemporaryDirectory() as tmp:
            hub = Path(tmp) / "hub"
            hub.mkdir()
            _git_init(hub)
            wt_path = Path(tmp) / "wt"
            subprocess.run(
                ["git", "-C", str(hub), "worktree", "add", "-b", "wt-branch", str(wt_path)],
                check=True, capture_output=True,
            )
            wt_result = list_worktrees(hub)
            assert len(wt_result) == 2, f"expected 2 worktrees, got {len(wt_result)}"
            assert wt_result[1]["branch"] == "wt-branch", f"expected wt-branch, got {wt_result[1]['branch']!r}"
            assert Path(wt_result[1]["path"]) == wt_path, f"expected path={wt_path!s}, got {wt_result[1]['path']!r}"
            print("PASS list_worktrees — two worktrees")

        # --- list_worktrees: detached HEAD ---
        with tempfile.TemporaryDirectory() as tmp:
            hub = Path(tmp) / "hub"
            hub.mkdir()
            _git_init(hub)
            detached_path = Path(tmp) / "detached"
            subprocess.run(
                ["git", "-C", str(hub), "worktree", "add", "--detach", str(detached_path), "HEAD"],
                check=True, capture_output=True,
            )
            wt_result = list_worktrees(hub)
            detached_entries = [e for e in wt_result if Path(e["path"]) == detached_path]
            assert len(detached_entries) == 1, "detached worktree not found"
            assert detached_entries[0]["branch"] is None, f"expected None branch, got {detached_entries[0]['branch']!r}"
            print("PASS list_worktrees — detached HEAD branch is None")

        # --- remove: worktree removed from git and disk ---
        with tempfile.TemporaryDirectory() as tmp:
            hub = Path(tmp) / "hub"
            hub.mkdir()
            _git_init(hub)
            wt_path = Path(tmp) / "wt"
            subprocess.run(
                ["git", "-C", str(hub), "worktree", "add", "-b", "remove-branch", str(wt_path)],
                check=True, capture_output=True,
            )
            remove(wt_path, cwd=hub)
            wt_result = list_worktrees(hub)
            assert len(wt_result) == 1, f"expected 1 worktree after remove, got {len(wt_result)}"
            assert not wt_path.exists(), f"worktree dir still exists at {wt_path}"
            print("PASS remove — worktree removed from git and disk")

        # --- remove: nonexistent path raises WorktreeError ---
        with tempfile.TemporaryDirectory() as tmp:
            hub = Path(tmp)
            _git_init(hub)
            raised = False
            try:
                remove(hub / "nonexistent", cwd=hub, force=True)
            except WorktreeError:
                raised = True
            assert raised, "expected WorktreeError for nonexistent path"
            print("PASS remove — nonexistent path raises WorktreeError")

        print("All _worktree unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
