"""Unit tests for plugins/mill/scripts/_pygit2_util.py."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import _pygit2_util  # noqa: E402


def _init_repo(repo_path: Path) -> None:
    """Initialize a real git repo with an initial commit."""
    repo_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", str(repo_path)],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.email", "test@test.com"],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.name", "Test"],
        capture_output=True,
        check=True,
    )
    (repo_path / ".keep").write_text("", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo_path), "add", ".keep"],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "commit", "-m", "init"],
        capture_output=True,
        check=True,
    )


def test_discover_workdir_happy_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _init_repo(tmp)
        result = _pygit2_util.discover_workdir(tmp)
        if result != tmp.resolve():
            raise AssertionError(f"expected {tmp.resolve()}, got {result}")
    print("PASS: test_discover_workdir_happy_path")


def test_discover_workdir_non_repo() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        nonexistent = tmp / "nonexistent"
        try:
            _pygit2_util.discover_workdir(nonexistent)
            raise AssertionError("expected GitOpsError, got none")
        except _pygit2_util.GitOpsError:
            pass
    print("PASS: test_discover_workdir_non_repo")


def test_resolve_common_dir_parent_main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _init_repo(tmp)
        result = _pygit2_util.resolve_common_dir_parent(tmp)
        if result != tmp.resolve():
            raise AssertionError(f"expected {tmp.resolve()}, got {result}")
    print("PASS: test_resolve_common_dir_parent_main")


def test_resolve_common_dir_parent_linked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _init_repo(tmp)
        linked_path = tmp / "linked"
        subprocess.run(
            ["git", "-C", str(tmp), "worktree", "add", str(linked_path), "-b", "linked-branch"],
            capture_output=True,
            check=True,
        )
        result = _pygit2_util.resolve_common_dir_parent(linked_path)
        if result != tmp.resolve():
            raise AssertionError(f"expected {tmp.resolve()}, got {result}")
    print("PASS: test_resolve_common_dir_parent_linked")


def test_head_sha_happy_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _init_repo(tmp)
        result = _pygit2_util.head_sha(tmp)
        if not isinstance(result, str) or len(result) != 40:
            raise AssertionError(f"expected 40-char hex string, got {result!r}")
        if not all(c in "0123456789abcdef" for c in result):
            raise AssertionError(f"expected lowercase hex string, got {result!r}")
        git_sha = subprocess.run(
            ["git", "-C", str(tmp), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if result != git_sha:
            raise AssertionError(f"expected {git_sha}, got {result}")
    print("PASS: test_head_sha_happy_path")


def test_current_branch_named() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _init_repo(tmp)
        result = _pygit2_util.current_branch(tmp)
        if result is None:
            raise AssertionError("expected branch name, got None")
        git_branch = subprocess.run(
            ["git", "-C", str(tmp), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if result != git_branch:
            raise AssertionError(f"expected {git_branch}, got {result}")
    print("PASS: test_current_branch_named")


def test_current_branch_detached() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _init_repo(tmp)
        sha = subprocess.run(
            ["git", "-C", str(tmp), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "-C", str(tmp), "checkout", sha],
            capture_output=True,
            check=True,
        )
        result = _pygit2_util.current_branch(tmp)
        if result is not None:
            raise AssertionError(f"expected None for detached HEAD, got {result!r}")
    print("PASS: test_current_branch_detached")


def test_status_porcelain_clean() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _init_repo(tmp)
        result = _pygit2_util.status_porcelain(tmp)
        if result != []:
            raise AssertionError(f"expected empty list, got {result!r}")
    print("PASS: test_status_porcelain_clean")


def test_status_porcelain_modified() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _init_repo(tmp)
        (tmp / ".keep").write_text("modified", encoding="utf-8")
        result = _pygit2_util.status_porcelain(tmp)
        if len(result) != 1:
            raise AssertionError(f"expected 1 status line, got {len(result)}")
        if not result[0].startswith(" M "):
            raise AssertionError(f"expected ' M ' status, got {result[0]!r}")
    print("PASS: test_status_porcelain_modified")


def test_status_porcelain_staged() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _init_repo(tmp)
        (tmp / "newfile.txt").write_text("new", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(tmp), "add", "newfile.txt"],
            capture_output=True,
            check=True,
        )
        result = _pygit2_util.status_porcelain(tmp)
        if len(result) != 1:
            raise AssertionError(f"expected 1 status line, got {len(result)}")
        if not result[0].startswith("A  "):
            raise AssertionError(f"expected 'A  ' status, got {result[0]!r}")
    print("PASS: test_status_porcelain_staged")


def test_status_porcelain_untracked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _init_repo(tmp)
        (tmp / "untracked.txt").write_text("untracked", encoding="utf-8")
        result_with_untracked = _pygit2_util.status_porcelain(tmp, include_untracked=True)
        if len(result_with_untracked) != 1:
            raise AssertionError(f"expected 1 status line with untracked, got {len(result_with_untracked)}")
        if not result_with_untracked[0].startswith("??"):
            raise AssertionError(f"expected '??' status, got {result_with_untracked[0]!r}")
        result_without_untracked = _pygit2_util.status_porcelain(tmp, include_untracked=False)
        if result_without_untracked != []:
            raise AssertionError(f"expected empty list without untracked, got {result_without_untracked!r}")
    print("PASS: test_status_porcelain_untracked")


def test_list_worktrees_single() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _init_repo(tmp)
        result = _pygit2_util.list_worktrees(tmp)
        if len(result) != 1:
            raise AssertionError(f"expected 1 worktree, got {len(result)}")
        main_wt = result[0]
        if main_wt["path"] != tmp.resolve().as_posix():
            raise AssertionError(
                f"expected path {tmp.resolve().as_posix()}, got {main_wt['path']!r}"
            )
        if main_wt["branch"] is None:
            raise AssertionError("expected branch name, got None")
    print("PASS: test_list_worktrees_single")


def test_list_worktrees_with_linked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _init_repo(tmp)
        linked_path = tmp / "linked"
        subprocess.run(
            ["git", "-C", str(tmp), "worktree", "add", str(linked_path), "-b", "wt-branch"],
            capture_output=True,
            check=True,
        )
        result = _pygit2_util.list_worktrees(tmp)
        if len(result) != 2:
            raise AssertionError(f"expected 2 worktrees, got {len(result)}")
        main_wt = result[0]
        linked_wt = result[1]
        if main_wt["path"] != tmp.resolve().as_posix():
            raise AssertionError(f"expected main path {tmp.resolve().as_posix()}, got {main_wt['path']!r}")
        if linked_wt["path"] != linked_path.resolve().as_posix():
            raise AssertionError(
                f"expected linked path {linked_path.resolve().as_posix()}, got {linked_wt['path']!r}"
            )
        if linked_wt["branch"] != "wt-branch":
            raise AssertionError(f"expected branch 'wt-branch', got {linked_wt['branch']!r}")
    print("PASS: test_list_worktrees_with_linked")


def test_is_ancestor_real_chain() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _init_repo(tmp)
        ancestor_sha = subprocess.run(
            ["git", "-C", str(tmp), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        (tmp / "file2.txt").write_text("file2", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(tmp), "add", "file2.txt"],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp), "commit", "-m", "commit 2"],
            capture_output=True,
            check=True,
        )
        descendant_sha = subprocess.run(
            ["git", "-C", str(tmp), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if not _pygit2_util.is_ancestor(tmp, ancestor_sha, descendant_sha):
            raise AssertionError(f"expected {ancestor_sha} to be ancestor of {descendant_sha}")
    print("PASS: test_is_ancestor_real_chain")


def test_is_ancestor_unrelated() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _init_repo(tmp)
        first_sha = subprocess.run(
            ["git", "-C", str(tmp), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "-C", str(tmp), "checkout", "--orphan", "other-branch"],
            capture_output=True,
            check=True,
        )
        (tmp / ".keep").write_text("other", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(tmp), "add", ".keep"],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp), "commit", "-m", "other"],
            capture_output=True,
            check=True,
        )
        other_sha = subprocess.run(
            ["git", "-C", str(tmp), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if _pygit2_util.is_ancestor(tmp, first_sha, other_sha):
            raise AssertionError(f"expected {first_sha} NOT to be ancestor of {other_sha}")
    print("PASS: test_is_ancestor_unrelated")


def test_is_ancestor_identical_sha() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _init_repo(tmp)
        sha = subprocess.run(
            ["git", "-C", str(tmp), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if not _pygit2_util.is_ancestor(tmp, sha, sha):
            raise AssertionError(f"expected identical SHAs to return True")
    print("PASS: test_is_ancestor_identical_sha")


def test_is_ancestor_invalid_sha() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _init_repo(tmp)
        try:
            _pygit2_util.is_ancestor(tmp, "0000000000000000000000000000000000000000", "invalid_sha_12345")
            raise AssertionError("expected GitOpsError for invalid SHA")
        except _pygit2_util.GitOpsError:
            pass
    print("PASS: test_is_ancestor_invalid_sha")


def run_all() -> int:
    tests = [
        test_discover_workdir_happy_path,
        test_discover_workdir_non_repo,
        test_resolve_common_dir_parent_main,
        test_resolve_common_dir_parent_linked,
        test_head_sha_happy_path,
        test_current_branch_named,
        test_current_branch_detached,
        test_status_porcelain_clean,
        test_status_porcelain_modified,
        test_status_porcelain_staged,
        test_status_porcelain_untracked,
        test_list_worktrees_single,
        test_list_worktrees_with_linked,
        test_is_ancestor_real_chain,
        test_is_ancestor_unrelated,
        test_is_ancestor_identical_sha,
        test_is_ancestor_invalid_sha,
    ]

    failures: list[str] = []
    for test_fn in tests:
        try:
            test_fn()
        except AssertionError as exc:
            print(f"FAIL [{test_fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(test_fn.__name__)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR [{test_fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(test_fn.__name__)

    print()
    if failures:
        print(f"FAIL -- {len(failures)} of {len(tests)} tests: {failures}", file=sys.stderr)
        return 1
    print(f"All {len(tests)} _pygit2_util unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(run_all())
