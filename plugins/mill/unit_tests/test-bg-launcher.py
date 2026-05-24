"""Unit tests for millpy-bg.py launcher cwd-validation paths."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import _test_helpers  # noqa: E402

MILLPY_BG_PATH = _HERE.parent / "scripts" / "millpy-bg.py"


def _make_container_form_worktree(
    tmp: Path,
    slug: str,
    title: str,
    *,
    branch_prefix: str = "hanf/",
) -> tuple[Path, Path]:
    """Create a container-form git repo and wiki for testing resolve_wiki_path.

    Container-form layout: tmp/wts/<repo-name>/ (worktree) and tmp/wiki/ (wiki).

    Args:
        tmp: Temporary directory root.
        slug: Task slug for branch and Home.md.
        title: Human-readable task title.
        branch_prefix: Branch prefix to use (default "hanf/").

    Returns:
        (worktree_path, wiki_path) absolute Paths.
    """
    wts_dir = tmp / "wts"
    wts_dir.mkdir(parents=True, exist_ok=True)
    worktree_path = wts_dir / "test-repo"
    wiki_path = tmp / "wiki"

    worktree_path.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["git", "init", "--initial-branch=main", str(worktree_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        subprocess.run(
            ["git", "init", str(worktree_path)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(worktree_path), "checkout", "-b", "main"],
            capture_output=True,
        )

    subprocess.run(
        ["git", "-C", str(worktree_path), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(worktree_path), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )

    (worktree_path / ".keep").write_text("", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(worktree_path), "add", ".keep"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(worktree_path), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )

    task_branch = f"{branch_prefix}{slug}"
    subprocess.run(
        ["git", "-C", str(worktree_path), "checkout", "-b", task_branch],
        check=True,
        capture_output=True,
    )

    wiki_path.mkdir(parents=True, exist_ok=True)
    home_body = f"## {title}\n[[{slug}]] [active]\n\n_body_\n"
    (wiki_path / "Home.md").write_text(home_body, encoding="utf-8")

    if f"[[{slug}]]" not in home_body:
        raise AssertionError(f"slug {slug!r} not found in generated Home.md")

    _test_helpers.seed_wiki_config(wiki_path, include_roles=False)

    return (worktree_path, wiki_path)


def test_launcher_rejects_non_task_worktree() -> None:
    """Test that launcher rejects a non-task worktree (main branch, no slug in Home.md)."""
    with _test_helpers.safe_temp_dir() as tmp:
        worktree_path, wiki_path = _make_container_form_worktree(
            tmp, "test-task", "Test Task", branch_prefix="hanf/"
        )

        subprocess.run(
            ["git", "-C", str(worktree_path), "checkout", "main"],
            check=True,
            capture_output=True,
        )

        result = subprocess.run(
            [
                sys.executable,
                str(MILLPY_BG_PATH),
                "--slug",
                "test",
                "--",
                sys.executable,
                "-c",
                "pass",
            ],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 1:
            raise AssertionError(
                f"expected exit code 1, got {result.returncode}. "
                f"stderr={result.stderr!r}"
            )
        if "cwd appears to be a non-task worktree" not in result.stderr:
            raise AssertionError(
                f"expected 'cwd appears to be a non-task worktree' in stderr, "
                f"got: {result.stderr!r}"
            )

    print("PASS: test_launcher_rejects_non_task_worktree")


def test_launcher_rejects_invalid_cwd_with_clean_error() -> None:
    """Test that launcher rejects cwd with invalid config path (no wiki)."""
    with _test_helpers.safe_temp_dir() as tmp:

        isolated_git = tmp / "isolated"
        isolated_git.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            ["git", "init", "--initial-branch=main", str(isolated_git)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            subprocess.run(
                ["git", "init", str(isolated_git)],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(isolated_git), "checkout", "-b", "main"],
                capture_output=True,
            )

        subprocess.run(
            ["git", "-C", str(isolated_git), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(isolated_git), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
        )

        (isolated_git / ".keep").write_text("", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(isolated_git), "add", ".keep"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(isolated_git), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )

        result = subprocess.run(
            [
                sys.executable,
                str(MILLPY_BG_PATH),
                "--slug",
                "test",
                "--",
                sys.executable,
                "-c",
                "pass",
            ],
            cwd=isolated_git,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 1:
            raise AssertionError(
                f"expected exit code 1, got {result.returncode}. "
                f"stderr={result.stderr!r}"
            )
        if "cannot validate cwd" not in result.stderr:
            raise AssertionError(
                f"expected 'cannot validate cwd' in stderr, got: {result.stderr!r}"
            )

    print("PASS: test_launcher_rejects_invalid_cwd_with_clean_error")


def test_launcher_accepts_valid_task_worktree() -> None:
    """Test that launcher accepts valid task worktree and executes command."""
    with _test_helpers.safe_temp_dir() as tmp:
        worktree_path, wiki_path = _make_container_form_worktree(
            tmp, "test-task", "Test Task", branch_prefix="hanf/"
        )

        result = subprocess.run(
            [
                sys.executable,
                str(MILLPY_BG_PATH),
                "--slug",
                "test",
                "--",
                sys.executable,
                "-c",
                "pass",
            ],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise AssertionError(
                f"expected exit code 0, got {result.returncode}. "
                f"stdout={result.stdout!r}, stderr={result.stderr!r}"
            )
        if "pid=" not in result.stdout:
            raise AssertionError(
                f"expected 'pid=' in stdout, got: {result.stdout!r}"
            )
        if "log=" not in result.stdout:
            raise AssertionError(
                f"expected 'log=' in stdout, got: {result.stdout!r}"
            )

    print("PASS: test_launcher_accepts_valid_task_worktree")


def main() -> int:
    """Run all tests."""
    failures: list[str] = []

    for test_func in [
        test_launcher_rejects_non_task_worktree,
        test_launcher_rejects_invalid_cwd_with_clean_error,
        test_launcher_accepts_valid_task_worktree,
    ]:
        try:
            test_func()
        except AssertionError as exc:
            failures.append(f"FAIL: {test_func.__name__}: {exc}")
        except Exception as exc:
            failures.append(
                f"FAIL: {test_func.__name__} ({type(exc).__name__}): {exc}"
            )

    if failures:
        for msg in failures:
            print(msg, file=sys.stderr)
        return 1

    print("All bg-launcher unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
