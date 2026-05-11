"""
Shared test fixtures for mill unit tests.

Public API:
    _make_task_worktree(tmp, slug, title, *, branch_prefix="", phase="active")
        Create a minimal git repo on a task branch plus a wiki stub.
        Returns (worktree_path, wiki_path).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import _tasks_md  # noqa: E402


def _make_task_worktree(
    tmp: Path,
    slug: str,
    title: str,
    *,
    branch_prefix: str = "",
    phase: str = "active",
) -> tuple[Path, Path]:
    """Create a minimal git repo on a task branch and a wiki stub.

    Args:
        tmp: Directory under which worktree/ and wiki/ are created.
        slug: Task slug (used as branch suffix and Home.md slug).
        title: Human-readable task title for Home.md.
        branch_prefix: Optional branch prefix prepended to slug.
        phase: Phase marker written in Home.md. Pass "none" to write the
            slug line without any phase marker (task.phase will be None).

    Returns:
        (worktree_path, wiki_path) — absolute Paths.
    """
    worktree_path = tmp / "worktree"
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
    if phase == "none":
        home_body = f"## {title}\n[[{slug}]]\n\n_body_\n"
    else:
        home_body = f"## {title}\n[[{slug}]] [{phase}]\n\n_body_\n"

    (wiki_path / "Home.md").write_text(home_body, encoding="utf-8")

    parsed = _tasks_md.parse(home_body)
    found = next((t for t in parsed if t.slug == slug), None)
    if found is None:
        raise AssertionError(f"slug {slug!r} not found in generated Home.md")
    expected_phase = None if phase == "none" else phase
    if found.phase != expected_phase:
        raise AssertionError(
            f"expected phase={expected_phase!r} for slug {slug!r}, got {found.phase!r}"
        )

    return (worktree_path, wiki_path)


def seed_wiki_config(wiki_root: Path, *, include_roles: bool = False) -> None:
    """Write a minimal wiki config.yaml that _review_common.load_config requires.

    Creates wiki_root/config.yaml with the paths: and spawn: blocks. Review-flow
    test fixtures that use a container-form layout need this file in the wiki
    directory so load_config does not raise ReviewError(Missing config). Pass
    include_roles=True to also write a roles: block with stub test_stub reviewer
    entries for discussion-review, plan-review, and code-review.
    """
    content = (
        "paths:\n"
        "  discussion_file: discussion.md\n"
        "  plan_dir: plan/\n"
        "  reviews_dir: reviews/\n"
        "spawn:\n"
        "  branch_prefix: \"hanf/\"\n"
    )
    if include_roles:
        content += (
            "roles:\n"
            "  discussion-review:\n"
            "    holistic: {rounds: 1, reviewer: test_stub}\n"
            "  plan-review:\n"
            "    batch: {rounds: 1, reviewer: test_stub}\n"
            "    holistic: {rounds: 1, reviewer: test_stub}\n"
            "  code-review:\n"
            "    batch: {rounds: 1, reviewer: test_stub}\n"
            "    holistic: {rounds: 1, reviewer: test_stub}\n"
        )
    (wiki_root / "config.yaml").write_text(content, encoding="utf-8")
