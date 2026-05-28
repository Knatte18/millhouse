"""
Shared test fixtures for mill unit tests.

Public API:
    _make_task_worktree(tmp, slug, title, *, branch_prefix="", phase="active", layout="prefix", seed_task=False)
        Create a minimal git repo on a task branch plus a wiki stub.
        Returns (worktree_path, wiki_path).
    wait_for_daemon_exit(wiki_path, *, timeout=5.0) -> None
        Poll for wiki daemon state file removal; return on disappearance or timeout.
    init_wiki_repo(wiki_path) -> None
        Initialize a git repo with bare origin at a wiki_path.
    safe_temp_dir() -> ContextManager[Path]
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Literal

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

os.environ.setdefault("WIKI_DAEMON_IDLE_TIMEOUT", "1")
# Test mode (cheap):
# - SKIP_GIT: no pull/commit/push at all. Renders files in-place; no git history.
#   Use this default — most tests don't assert on git state.
# - INPROCESS: route every wiki._client op to an in-process WikiServer instead
#   of spawning a Python subprocess. Saves ~1.5 s of interpreter startup per test.
# A test that needs commit log behaviour overrides SKIP_GIT before importing
# this module and sets WIKI_DAEMON_SKIP_PUSH=1 instead (commits, no push).
os.environ.setdefault("WIKI_DAEMON_SKIP_GIT", "1")
os.environ.setdefault("WIKI_DAEMON_INPROCESS", "1")

import pygit2  # noqa: E402
import _safe_rmtree  # noqa: E402
from wiki import _client as wiki  # noqa: E402
from wiki._parse import parse_home_md  # noqa: E402


def init_minimal_git_repo(path: Path, *, branch: str = "main") -> "pygit2.Repository":
    """Create a git repo at ``path`` with an empty initial commit on ``branch``.

    Uses pygit2 directly (no subprocess) — ~60 ms vs ~600 ms for the
    equivalent subprocess git init + config + add + commit chain on
    Windows. Drop-in replacement for the four-or-five-call subprocess
    pattern that pre-dates this helper.

    Args:
        path: Repo root. Created if missing.
        branch: Initial branch name (default ``"main"``).

    Returns:
        pygit2.Repository object for the new repo.
    """
    path.mkdir(parents=True, exist_ok=True)
    repo = pygit2.init_repository(str(path), initial_head=f"refs/heads/{branch}")
    cfg = repo.config
    cfg["user.email"] = "test@test.com"
    cfg["user.name"] = "Test"
    (path / ".keep").write_text("", encoding="utf-8")
    index = repo.index
    index.add(".keep")
    index.write()
    tree = index.write_tree()
    sig = pygit2.Signature("Test", "test@test.com")
    repo.create_commit(f"refs/heads/{branch}", sig, sig, "init", tree, [])
    return repo


def checkout_new_branch(repo: "pygit2.Repository", branch: str) -> None:
    """Create and check out ``branch`` from the current HEAD via pygit2."""
    head = repo.head
    commit = repo[head.target]
    ref = repo.branches.local.create(branch, commit)
    repo.set_head(ref.name)


def wait_for_daemon_exit(wiki_path: Path, *, timeout: float = 5.0) -> None:
    """Poll for wiki daemon state file removal.

    Args:
        wiki_path: Path to wiki directory.
        timeout: Seconds to poll before returning (default 5.0).
    """
    state_file = wiki_path / ".wiki-daemon.json"
    if not state_file.exists():
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not state_file.exists():
            return
        time.sleep(0.05)


def init_wiki_repo(wiki_path: Path) -> None:
    """Initialize a git repo with bare origin.

    Under WIKI_DAEMON_SKIP_GIT (test mode default), the wiki server never
    invokes git, so the init/remote/commit/push dance is dead weight (~1 s
    per test on Windows). Just create the directory and return.

    Args:
        wiki_path: Path where wiki repo will be created.
    """
    wiki_path.mkdir(parents=True, exist_ok=True)

    if os.environ.get("WIKI_DAEMON_SKIP_GIT") == "1":
        return

    result = subprocess.run(
        ["git", "init", "--initial-branch=main", str(wiki_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        subprocess.run(
            ["git", "init", str(wiki_path)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(wiki_path), "checkout", "-b", "main"],
            capture_output=True,
        )

    subprocess.run(
        ["git", "-C", str(wiki_path), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(wiki_path), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )

    (wiki_path / ".keep").write_text("", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(wiki_path), "add", ".keep"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(wiki_path), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )

    bare_path = wiki_path.parent / f"{wiki_path.name}.git"
    subprocess.run(
        ["git", "init", "--bare", str(bare_path)],
        check=True,
        capture_output=True,
    )

    subprocess.run(
        ["git", "-C", str(wiki_path), "remote", "add", "origin", str(bare_path)],
        check=True,
        capture_output=True,
    )

    subprocess.run(
        ["git", "-C", str(wiki_path), "push", "--set-upstream", "origin", "main"],
        check=True,
        capture_output=True,
    )


def _make_task_worktree(
    tmp: Path,
    slug: str,
    title: str,
    *,
    branch_prefix: str = "",
    phase: str = "active",
    layout: Literal["prefix", "container"] = "prefix",
    seed_task: bool = False,
) -> tuple[Path, Path]:
    """Create a minimal git repo on a task branch and a wiki stub.

    Args:
        tmp: Directory under which worktree/ and wiki/ are created.
        slug: Task slug (used as branch suffix and Home.md slug).
        title: Human-readable task title for Home.md.
        branch_prefix: Optional branch prefix prepended to slug.
        phase: Phase marker written in Home.md. Pass "none" to write the
            slug line without any phase marker (task.phase will be None).
        layout: Path layout mode: "prefix" (default, worktree at tmp/worktree)
            or "container" (worktree at tmp/wts/slug).
        seed_task: If True, initialize wiki as a real git repo with bare origin
            and upsert the task to tasks.json via the wiki client.

    Returns:
        (worktree_path, wiki_path) — absolute Paths.
    """
    if layout == "container":
        worktree_path = tmp / "wts" / slug
    else:
        worktree_path = tmp / "worktree"
    wiki_path = tmp / "wiki"

    # Build worktree git repo via pygit2 (no subprocess overhead).
    repo = init_minimal_git_repo(worktree_path, branch="main")
    task_branch = f"{branch_prefix}{slug}"
    checkout_new_branch(repo, task_branch)

    if seed_task:
        init_wiki_repo(wiki_path)
    else:
        wiki_path.mkdir(parents=True, exist_ok=True)

    if phase == "none":
        home_body = f"## {title}\n[{slug}]\n\n_body_\n"
    else:
        home_body = f"## {title}\n[{slug}] [{phase}]\n\n_body_\n"

    (wiki_path / "Home.md").write_text(home_body, encoding="utf-8")

    if seed_task:
        wiki.upsert_task(wiki_path, slug, title=title, status=(None if phase == "none" else phase))

    parsed = parse_home_md(home_body)
    found = next((t for t in parsed if t["slug"] == slug), None)
    if found is None:
        raise AssertionError(f"slug {slug!r} not found in generated Home.md")
    expected_status = None if phase == "none" else phase
    if found["status"] != expected_status:
        raise AssertionError(
            f"expected status={expected_status!r} for slug {slug!r}, got {found['status']!r}"
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


@contextlib.contextmanager
def safe_temp_dir():
    """Context manager for safe temp directory with daemon-exit wait.

    Yields a temporary directory; on exit, waits for any wiki daemons
    to exit before cleaning up with safe_rmtree.
    """
    tmp = Path(tempfile.mkdtemp())
    try:
        yield tmp
    finally:
        try:
            import wiki._client as _wc

            tmp_resolved = str(tmp.resolve()).lower()
            for key in list(_wc._INPROCESS_SERVERS.keys()):
                if key.lower().startswith(tmp_resolved):
                    _wc.stop_inprocess(Path(key))
        except Exception:
            pass
        try:
            for state_file in list(tmp.rglob(".wiki-daemon.json")):
                wait_for_daemon_exit(state_file.parent, timeout=5.0)
        except OSError:
            pass
        _safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)
