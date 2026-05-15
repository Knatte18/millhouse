"""Unit tests for plugins/mill/scripts/_spawn_core.py."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _spawn_core import (  # noqa: E402
    BacklogEmpty,
    capture_parent_branch,
    claim_in_wiki,
    discover_active_worktrees,
    multi_select_groom_then_claim,
    pick_task_single,
    pick_task_single_or_multi,
    prompt_merged_entry,
    recreate_active_junction,
    write_initial_status,
)
import _tasks_md  # noqa: E402
from _test_helpers import safe_temp_dir  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HOME_MD = """\
# Home

## Fix login bug
[fix-login]

## Add dark mode
[dark-mode] [s]

## Update docs
[update-docs] [active]

## Old feature
[old-feature] [done]
"""

_HOME_MD_EMPTY = """\
# Home

## Active only
[active-only] [active]
"""

_HOME_MD_UNMARKED_ONLY = """\
# Home

## Task one
[task-one]

## Task two
[task-two]
"""

_HOME_MD_THREE_TASKS = """\
# Home

## Task Alpha
[task-alpha]

## Task Beta
[task-beta]

## Task Gamma
[task-gamma]
"""


def _make_wiki(tmp: str, home_text: str) -> Path:
    """Initialise a wiki working clone backed by a local bare remote.

    Creates:
      - ``<tmp>/wiki-bare/`` — bare repo acting as the "origin" remote.
      - ``<tmp>/wiki/`` — working clone with Home.md and _Sidebar.md
        committed and pushed to the bare remote.

    The working clone is returned. ``_wiki.write_commit_push`` can push
    to the bare remote without a network connection.
    """
    # Bare "remote"
    bare = Path(tmp) / "wiki-bare"
    bare.mkdir()
    subprocess.run(
        ["git", "-C", str(bare), "init", "--bare"],
        check=True,
        capture_output=True,
    )

    # Working clone
    wiki = Path(tmp) / "wiki"
    subprocess.run(
        ["git", "clone", str(bare), str(wiki)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(wiki), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(wiki), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    (wiki / "Home.md").write_text(home_text, encoding="utf-8")
    (wiki / "_Sidebar.md").write_text("", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(wiki), "add", "."],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(wiki), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(wiki), "push", "-u", "origin", "HEAD"],
        check=True,
        capture_output=True,
    )
    return wiki


def _make_git_repo(tmp: str, branch: str = "main") -> Path:
    """Initialise a minimal git repo on ``branch`` backed by a local bare remote."""
    repo = Path(tmp) / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    (repo / "README.md").write_text("# repo\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )
    # git init creates "master" or "main" depending on git config;
    # rename to the desired branch if needed.
    current = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if current != branch:
        subprocess.run(
            ["git", "-C", str(repo), "branch", "-m", current, branch],
            check=True,
            capture_output=True,
        )
    # Bare remote so push succeeds without network.
    bare = Path(tmp) / "repo-bare"
    bare.mkdir()
    subprocess.run(["git", "-C", str(bare), "init", "--bare"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", str(bare)],
        check=True,
        capture_output=True,
    )
    return repo


# ---------------------------------------------------------------------------
# pick_task_single — slug mode
# ---------------------------------------------------------------------------


def test_pick_task_single_slug_matching_unmarked() -> None:
    tasks = _tasks_md.parse(_HOME_MD)
    picked = pick_task_single(tasks, slug="fix-login")
    if picked.slug != "fix-login":
        raise AssertionError(f"expected fix-login, got {picked.slug!r}")
    print("PASS: pick_task_single with --slug matching unmarked task")


def test_pick_task_single_slug_matching_s() -> None:
    tasks = _tasks_md.parse(_HOME_MD)
    picked = pick_task_single(tasks, slug="dark-mode")
    if picked.slug != "dark-mode":
        raise AssertionError(f"expected dark-mode, got {picked.slug!r}")
    print("PASS: pick_task_single with --slug matching [s] task")


def test_pick_task_single_slug_already_done_raises() -> None:
    tasks = _tasks_md.parse(_HOME_MD)
    try:
        pick_task_single(tasks, slug="old-feature")
    except ValueError:
        print("PASS: pick_task_single with --slug matching [done] raises ValueError")
    else:
        raise AssertionError("expected ValueError for done slug")


def test_pick_task_single_slug_not_found_raises() -> None:
    tasks = _tasks_md.parse(_HOME_MD)
    try:
        pick_task_single(tasks, slug="nonexistent-slug")
    except ValueError:
        print("PASS: pick_task_single with --slug matching no task raises ValueError")
    else:
        raise AssertionError("expected ValueError for nonexistent slug")


# ---------------------------------------------------------------------------
# pick_task_single — fast-path ([s] marker)
# ---------------------------------------------------------------------------


def test_pick_task_single_fast_path_s() -> None:
    tasks = _tasks_md.parse(_HOME_MD)
    picked = pick_task_single(tasks)
    if picked.slug != "dark-mode":
        raise AssertionError(f"expected dark-mode (only [s] task), got {picked.slug!r}")
    print("PASS: pick_task_single fast-path returns first [s] task without prompt")


# ---------------------------------------------------------------------------
# pick_task_single — empty backlog
# ---------------------------------------------------------------------------


def test_pick_task_single_empty_backlog_raises() -> None:
    tasks = _tasks_md.parse(_HOME_MD_EMPTY)
    try:
        pick_task_single(tasks)
    except BacklogEmpty:
        print("PASS: pick_task_single raises BacklogEmpty when no pickable tasks exist")
    else:
        raise AssertionError("expected BacklogEmpty")


# ---------------------------------------------------------------------------
# pick_task_single — numbered picker path (stdin injection)
# ---------------------------------------------------------------------------


def test_pick_task_single_numbered_path() -> None:
    """Inject synthetic stdin so the numbered picker returns task-two."""
    tasks = _tasks_md.parse(_HOME_MD_UNMARKED_ONLY)
    import io
    original_stdin = sys.stdin
    sys.stdin = io.StringIO("2\n")
    try:
        picked = pick_task_single(tasks)
    finally:
        sys.stdin = original_stdin
    if picked.slug != "task-two":
        raise AssertionError(f"expected task-two, got {picked.slug!r}")
    print("PASS: pick_task_single numbered-picker path returns chosen task")


def test_pick_task_single_numbered_path_invalid_choice() -> None:
    """Out-of-range numbered input causes ValueError (no task selected)."""
    tasks = _tasks_md.parse(_HOME_MD_UNMARKED_ONLY)
    import io
    original_stdin = sys.stdin
    sys.stdin = io.StringIO("99\n")
    try:
        pick_task_single(tasks)
    except ValueError:
        print("PASS: pick_task_single numbered-picker out-of-range raises ValueError")
    else:
        raise AssertionError("expected ValueError for out-of-range choice")
    finally:
        sys.stdin = original_stdin


# ---------------------------------------------------------------------------
# claim_in_wiki
# ---------------------------------------------------------------------------


def test_claim_in_wiki() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        wiki = _make_wiki(tmp, _HOME_MD_UNMARKED_ONLY)
        claim_in_wiki(wiki, "task-one")

        home_text = (wiki / "Home.md").read_text(encoding="utf-8")
        if "[active]" not in home_text:
            raise AssertionError("Home.md should contain [active] after claim")
        tasks = _tasks_md.parse(home_text)
        task_one = next((t for t in tasks if t.slug == "task-one"), None)
        if task_one is None or task_one.phase != "active":
            raise AssertionError(f"task-one phase should be active, got {task_one!r}")

        if not (wiki / "_Sidebar.md").exists():
            raise AssertionError("_Sidebar.md should exist after claim")

        # Verify commit landed
        log = subprocess.run(
            ["git", "-C", str(wiki), "log", "--oneline"],
            capture_output=True,
            text=True,
        )
        if "task: claim task-one" not in log.stdout:
            raise AssertionError(
                f"expected claim commit in log, got:\n{log.stdout}"
            )
    print("PASS: claim_in_wiki marks [active], regenerates sidebar, commits")


# ---------------------------------------------------------------------------
# capture_parent_branch
# ---------------------------------------------------------------------------


def test_capture_parent_branch_returns_branch_name() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _make_git_repo(tmp, branch="main")
        branch = capture_parent_branch(repo)
        if branch != "main":
            raise AssertionError(f"expected main, got {branch!r}")
    print("PASS: capture_parent_branch returns correct branch name")


def test_capture_parent_branch_on_non_repo_raises() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        non_repo = Path(tmp) / "not-a-repo"
        non_repo.mkdir()
        try:
            capture_parent_branch(non_repo)
        except RuntimeError:
            print("PASS: capture_parent_branch raises RuntimeError on non-repo path")
        else:
            raise AssertionError("expected RuntimeError")


# ---------------------------------------------------------------------------
# write_initial_status
# ---------------------------------------------------------------------------


def test_write_initial_status() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _make_git_repo(tmp, branch="main")
        subprocess.run(
            ["git", "-C", str(repo), "checkout", "-b", "hanf/task-one"],
            check=True,
            capture_output=True,
        )
        status_path = write_initial_status(
            worktree_path=repo,
            slug="task-one",
            title="Task One",
            ts="2026-04-26T10:00:00Z",
            parent_branch="main",
            branch="hanf/task-one",
            cfg={"paths": {"status_md": "_mill/status.md"}},
        )
        # status.md must be at _mill/status.md under the worktree root
        if status_path != repo / "_mill" / "status.md":
            raise AssertionError(
                f"status.md must be at _mill/ subdir; expected {repo / '_mill' / 'status.md'}, "
                f"got {status_path}"
            )
        if not status_path.exists():
            raise AssertionError(f"status.md not written at {status_path}")
        text = status_path.read_text(encoding="utf-8")
        if "Task One" not in text:
            raise AssertionError("title not in status.md")
        if "parent: main" not in text:
            raise AssertionError("parent_branch not in status.md")
        if "task-one" not in text:
            raise AssertionError("slug not in status.md")

        # git log for just task/status.md must show one commit with the expected message
        log = subprocess.run(
            ["git", "-C", str(repo), "log", "--oneline", "_mill/status.md"],
            capture_output=True,
            text=True,
        )
        if "spawn: init status for task-one" not in log.stdout:
            raise AssertionError(
                f"expected status commit in log, got:\n{log.stdout}"
            )
        # Return value should be the absolute path
        if not status_path.is_absolute():
            raise AssertionError("write_initial_status should return an absolute path")
    print("PASS: write_initial_status writes status.md at worktree root, commits on task branch, returns abs path")


def test_write_initial_status_forced_failure_raises_runtime_error() -> None:
    """Forcing git add to fail (via index lock) must raise RuntimeError with stderr."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = _make_git_repo(tmp, branch="main")
        # Create an index lock file — git add will fail with
        # "Unable to create '...index.lock': File exists."
        (repo / ".git" / "index.lock").write_text("", encoding="utf-8")
        try:
            write_initial_status(
                worktree_path=repo,
                slug="task-one",
                title="Task One",
                ts="2026-04-26T10:00:00Z",
                parent_branch="main",
                branch="hanf/task-one",
                cfg={"paths": {"status_md": "_mill/status.md"}},
            )
        except RuntimeError as exc:
            msg = str(exc)
            if "git add _mill/status.md failed" not in msg:
                raise AssertionError(
                    f"RuntimeError message missing expected prefix; got: {msg!r}"
                )
            # The message must include the subprocess stderr.
            if not msg.strip().endswith("'"):
                # It ends with repr(...) of stderr so just check it's non-empty
                pass
        else:
            raise AssertionError(
                "write_initial_status must raise RuntimeError when git add fails"
            )
    print("PASS: write_initial_status raises RuntimeError with stderr when git add fails")


def test_write_initial_status_push_failure_raises_runtime_error() -> None:
    """No origin remote -> push fails -> RuntimeError mentioning git push --set-upstream origin."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo-no-origin"
        repo.mkdir()
        subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
        )
        (repo / "README.md").write_text("# repo\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "checkout", "-b", "hanf/task-one"],
            check=True,
            capture_output=True,
        )
        try:
            write_initial_status(
                worktree_path=repo,
                slug="task-one",
                title="Task One",
                ts="2026-04-26T10:00:00Z",
                parent_branch="main",
                branch="hanf/task-one",
                cfg={"paths": {"status_md": "_mill/status.md"}},
            )
        except RuntimeError as exc:
            msg = str(exc)
            if "git push --set-upstream origin" not in msg:
                raise AssertionError(
                    f"RuntimeError message should contain 'git push --set-upstream origin'; "
                    f"got: {msg!r}"
                )
        else:
            raise AssertionError(
                "write_initial_status must raise RuntimeError when push fails (no origin)"
            )
    print("PASS: write_initial_status raises RuntimeError when push fails (no origin)")


# ---------------------------------------------------------------------------
# recreate_active_junction
# ---------------------------------------------------------------------------


def test_recreate_active_junction_creates_link() -> None:
    """New signature: recreate_active_junction(slug, hub_root, container_path).
    Target is container_path / "portals" / slug; link is hub_root / ".active"."""
    with safe_temp_dir() as tmp:
        container_path = tmp / "container"
        portals = container_path / "portals"
        portals.mkdir(parents=True)
        mill_dir = Path(tmp) / "worktree" / ".millhouse"
        mill_dir.mkdir(parents=True)

        recreate_active_junction("my-task", mill_dir.parent, container_path)

        link_path = mill_dir.parent / ".active"
        target = container_path / "portals" / "my-task"
        if not target.exists():
            raise AssertionError(f"target dir should have been created at {target}")
        if not (link_path.exists() or link_path.is_symlink()):
            raise AssertionError(f"junction not created at {link_path}")
    print("PASS: recreate_active_junction creates junction pointing to portals/<slug>")


def test_recreate_active_junction_idempotent() -> None:
    """Calling twice must result in a valid junction pointing at the right target."""
    with safe_temp_dir() as tmp:
        container_path = tmp / "container"
        (container_path / "portals").mkdir(parents=True)
        mill_dir = Path(tmp) / "worktree" / ".millhouse"
        mill_dir.mkdir(parents=True)

        recreate_active_junction("my-task", mill_dir.parent, container_path)
        recreate_active_junction("my-task", mill_dir.parent, container_path)

        link_path = mill_dir.parent / ".active"
        if not (link_path.exists() or link_path.is_symlink()):
            raise AssertionError(f"junction not present after two calls at {link_path}")
    print("PASS: recreate_active_junction is idempotent (second call keeps link valid)")


# ---------------------------------------------------------------------------
# pick_task_single_or_multi — single number
# ---------------------------------------------------------------------------


def test_pick_task_single_or_multi_single_number() -> None:
    """Single number from numbered prompt -> mode='single'."""
    tasks = _tasks_md.parse(_HOME_MD_UNMARKED_ONLY)
    import io
    original_stdin = sys.stdin
    sys.stdin = io.StringIO("1\n")
    try:
        mode, picked, candidates = pick_task_single_or_multi(tasks)
    finally:
        sys.stdin = original_stdin
    if mode != "single":
        raise AssertionError(f"expected mode=single, got {mode!r}")
    if picked.slug != "task-one":
        raise AssertionError(f"expected task-one, got {picked.slug!r}")
    if candidates != []:
        raise AssertionError(f"expected candidates=[], got {candidates!r}")
    print("PASS: pick_task_single_or_multi single number -> mode=single")


# ---------------------------------------------------------------------------
# pick_task_single_or_multi — multi numbers
# ---------------------------------------------------------------------------


def test_pick_task_single_or_multi_multi_numbers() -> None:
    """Comma-separated numbers -> mode='multi' with correct tasks."""
    tasks = _tasks_md.parse(_HOME_MD_THREE_TASKS)
    import io
    original_stdin = sys.stdin
    sys.stdin = io.StringIO("1, 3\n")
    try:
        mode, picked, candidates = pick_task_single_or_multi(tasks)
    finally:
        sys.stdin = original_stdin
    if mode != "multi":
        raise AssertionError(f"expected mode=multi, got {mode!r}")
    if not isinstance(picked, list) or len(picked) != 2:
        raise AssertionError(f"expected list of 2, got {picked!r}")
    slugs = [t.slug for t in picked]
    if slugs != ["task-alpha", "task-gamma"]:
        raise AssertionError(f"expected [task-alpha, task-gamma], got {slugs!r}")
    print("PASS: pick_task_single_or_multi comma-separated -> mode=multi")


def test_pick_task_single_or_multi_dedup() -> None:
    """Repeated indices are de-duplicated silently."""
    tasks = _tasks_md.parse(_HOME_MD_THREE_TASKS)
    import io
    original_stdin = sys.stdin
    sys.stdin = io.StringIO("1, 1, 2\n")
    try:
        mode, picked, candidates = pick_task_single_or_multi(tasks)
    finally:
        sys.stdin = original_stdin
    if mode != "multi":
        raise AssertionError(f"expected mode=multi, got {mode!r}")
    slugs = [t.slug for t in picked]
    if slugs != ["task-alpha", "task-beta"]:
        raise AssertionError(f"expected [task-alpha, task-beta], got {slugs!r}")
    print("PASS: pick_task_single_or_multi de-duplicates 1,1,2 -> [task-alpha, task-beta]")


# ---------------------------------------------------------------------------
# pick_task_single_or_multi — retry logic
# ---------------------------------------------------------------------------


def test_pick_task_single_or_multi_out_of_range_then_valid() -> None:
    """Out-of-range on first attempt, valid on second -> succeeds."""
    tasks = _tasks_md.parse(_HOME_MD_UNMARKED_ONLY)
    import io
    original_stdin = sys.stdin
    sys.stdin = io.StringIO("99\n1\n")
    try:
        mode, picked, candidates = pick_task_single_or_multi(tasks)
    finally:
        sys.stdin = original_stdin
    if mode != "single":
        raise AssertionError(f"expected mode=single, got {mode!r}")
    if picked.slug != "task-one":
        raise AssertionError(f"expected task-one, got {picked.slug!r}")
    print("PASS: pick_task_single_or_multi out-of-range then valid -> mode=single")


def test_pick_task_single_or_multi_three_bad_attempts_raises() -> None:
    """Three non-numeric attempts exhaust retries and raise ValueError."""
    tasks = _tasks_md.parse(_HOME_MD_UNMARKED_ONLY)
    import io
    original_stdin = sys.stdin
    sys.stdin = io.StringIO("abc\ndef\nghi\n")
    try:
        pick_task_single_or_multi(tasks)
    except ValueError:
        print("PASS: pick_task_single_or_multi three bad attempts -> ValueError")
    else:
        raise AssertionError("expected ValueError after 3 bad attempts")
    finally:
        sys.stdin = original_stdin


# ---------------------------------------------------------------------------
# pick_task_single_or_multi — empty / slug / fast-path
# ---------------------------------------------------------------------------


def test_pick_task_single_or_multi_empty_backlog() -> None:
    """No unmarked tasks -> mode='empty', picked=None."""
    tasks = _tasks_md.parse(_HOME_MD_EMPTY)
    mode, picked, candidates = pick_task_single_or_multi(tasks)
    if mode != "empty":
        raise AssertionError(f"expected mode=empty, got {mode!r}")
    if picked is not None:
        raise AssertionError(f"expected picked=None, got {picked!r}")
    print("PASS: pick_task_single_or_multi no candidates -> mode=empty")


def test_pick_task_single_or_multi_slug_bypass() -> None:
    """--slug bypass always yields mode='single', no prompt."""
    tasks = _tasks_md.parse(_HOME_MD)
    mode, picked, candidates = pick_task_single_or_multi(tasks, slug="fix-login")
    if mode != "single":
        raise AssertionError(f"expected mode=single, got {mode!r}")
    if picked.slug != "fix-login":
        raise AssertionError(f"expected fix-login, got {picked.slug!r}")
    print("PASS: pick_task_single_or_multi --slug -> mode=single, no prompt")


def test_pick_task_single_or_multi_fast_path_s() -> None:
    """[s] fast-path always yields mode='single', no prompt."""
    tasks = _tasks_md.parse(_HOME_MD)
    mode, picked, candidates = pick_task_single_or_multi(tasks)
    if mode != "single":
        raise AssertionError(f"expected mode=single for [s] fast-path, got {mode!r}")
    if picked.slug != "dark-mode":
        raise AssertionError(f"expected dark-mode, got {picked.slug!r}")
    print("PASS: pick_task_single_or_multi [s] fast-path -> mode=single")


# ---------------------------------------------------------------------------
# multi_select_groom_then_claim
# ---------------------------------------------------------------------------


def test_multi_select_groom_then_claim_basic() -> None:
    """Removes all 3 sources, appends merged entry [active], sidebar regenerated, commit message matches."""
    with tempfile.TemporaryDirectory() as tmp:
        wiki = _make_wiki(tmp, _HOME_MD_THREE_TASKS)
        task = multi_select_groom_then_claim(
            wiki_path=wiki,
            source_slugs=["task-alpha", "task-beta", "task-gamma"],
            merged_title="Merged Task",
            merged_slug="merged-task",
            merged_body="Combined work.",
        )

        home_text = (wiki / "Home.md").read_text(encoding="utf-8")
        tasks = _tasks_md.parse(home_text)
        if len(tasks) != 1:
            raise AssertionError(
                f"expected 1 task remaining, got {len(tasks)}: {[t.slug for t in tasks]}"
            )
        if tasks[0].slug != "merged-task":
            raise AssertionError(f"expected merged-task, got {tasks[0].slug!r}")
        if tasks[0].phase != "active":
            raise AssertionError(f"expected active phase, got {tasks[0].phase!r}")

        if not (wiki / "_Sidebar.md").exists():
            raise AssertionError("_Sidebar.md should exist after groom-and-claim")

        log = subprocess.run(
            ["git", "-C", str(wiki), "log", "--oneline"],
            capture_output=True,
            text=True,
        )
        expected_msg = (
            "task: groom-and-claim 3->1 "
            "(merged-task; absorbed task-alpha, task-beta, task-gamma)"
        )
        if expected_msg not in log.stdout:
            raise AssertionError(
                f"expected commit msg {expected_msg!r} in:\n{log.stdout}"
            )

        if task.slug != "merged-task":
            raise AssertionError(f"expected returned task slug=merged-task, got {task.slug!r}")
        if task.phase != "active":
            raise AssertionError(f"expected returned task phase=active, got {task.phase!r}")
    print("PASS: multi_select_groom_then_claim basic flow")


def test_multi_select_groom_then_claim_with_proposal() -> None:
    """With has_proposal=True + proposal_body, writes proposal-<slug>.md."""
    with tempfile.TemporaryDirectory() as tmp:
        wiki = _make_wiki(tmp, _HOME_MD_THREE_TASKS)
        multi_select_groom_then_claim(
            wiki_path=wiki,
            source_slugs=["task-alpha", "task-beta"],
            merged_title="Merged With Proposal",
            merged_slug="merged-proposal",
            merged_body="See [proposal-merged-proposal.md](proposal-merged-proposal.md).",
            has_proposal=True,
            proposal_body="# Proposal\n\nDetailed content here.",
        )
        proposal_path = wiki / "proposal-merged-proposal.md"
        if not proposal_path.exists():
            raise AssertionError(f"proposal file not written at {proposal_path}")
        content = proposal_path.read_text(encoding="utf-8")
        if "Detailed content here." not in content:
            raise AssertionError("proposal body content not written correctly")
    print("PASS: multi_select_groom_then_claim writes proposal file when has_proposal=True")


# ---------------------------------------------------------------------------
# prompt_merged_entry
# ---------------------------------------------------------------------------


def test_prompt_merged_entry_happy_path_no_proposal() -> None:
    """Happy path without proposal: returns title, slug, typed body, False, None."""
    tasks = _tasks_md.parse(_HOME_MD_THREE_TASKS)
    source = [t for t in tasks if t.slug in ("task-alpha", "task-beta")]
    import io
    original_stdin = sys.stdin
    sys.stdin = io.StringIO(
        "My Merged Title\n"   # Merged title
        "my-merged-slug\n"    # Merged slug
        "N\n"                 # Extract to proposal? -> No
        "- bullet one\n"      # Body line 1
        "- bullet two\n"      # Body line 2
        "END\n"               # Sentinel
    )
    try:
        result = prompt_merged_entry(source)
    finally:
        sys.stdin = original_stdin

    merged_title, merged_slug, body_for_home, has_proposal, proposal_body = result
    if merged_title != "My Merged Title":
        raise AssertionError(f"unexpected merged_title: {merged_title!r}")
    if merged_slug != "my-merged-slug":
        raise AssertionError(f"unexpected merged_slug: {merged_slug!r}")
    if "bullet one" not in body_for_home:
        raise AssertionError(f"body_for_home missing content: {body_for_home!r}")
    if has_proposal is not False:
        raise AssertionError(f"has_proposal should be False, got {has_proposal!r}")
    if proposal_body is not None:
        raise AssertionError(f"proposal_body should be None, got {proposal_body!r}")
    print("PASS: prompt_merged_entry happy path without proposal")


def test_prompt_merged_entry_with_proposal() -> None:
    """With proposal: body_for_home is wiki link form; proposal_body holds typed body."""
    tasks = _tasks_md.parse(_HOME_MD_THREE_TASKS)
    source = [t for t in tasks if t.slug in ("task-alpha", "task-beta")]
    import io
    original_stdin = sys.stdin
    sys.stdin = io.StringIO(
        "Proposal Title\n"     # Merged title
        "proposal-slug\n"      # Merged slug
        "y\n"                  # Extract to proposal? -> Yes
        "- detail line\n"      # Body line
        "END\n"                # Sentinel
    )
    try:
        result = prompt_merged_entry(source)
    finally:
        sys.stdin = original_stdin

    merged_title, merged_slug, body_for_home, has_proposal, proposal_body = result
    if has_proposal is not True:
        raise AssertionError(f"has_proposal should be True, got {has_proposal!r}")
    if "proposal-proposal-slug.md" not in body_for_home:
        raise AssertionError(f"body_for_home missing link: {body_for_home!r}")
    if proposal_body is None or "detail line" not in proposal_body:
        raise AssertionError(f"proposal_body wrong: {proposal_body!r}")
    print("PASS: prompt_merged_entry with proposal extracts link form and proposal_body")


def test_prompt_merged_entry_bad_title_raises() -> None:
    """Three empty title attempts raise ValueError."""
    tasks = _tasks_md.parse(_HOME_MD_THREE_TASKS)
    source = [t for t in tasks if t.slug == "task-alpha"]
    import io
    original_stdin = sys.stdin
    sys.stdin = io.StringIO("\n\n\n")  # Three empty lines
    try:
        prompt_merged_entry(source)
    except ValueError:
        print("PASS: prompt_merged_entry raises ValueError after 3 empty titles")
    else:
        raise AssertionError("expected ValueError for 3 empty title attempts")
    finally:
        sys.stdin = original_stdin


def test_prompt_merged_entry_bad_slug_raises() -> None:
    """Three invalid slug attempts raise ValueError."""
    tasks = _tasks_md.parse(_HOME_MD_THREE_TASKS)
    source = [t for t in tasks if t.slug == "task-alpha"]
    import io
    original_stdin = sys.stdin
    sys.stdin = io.StringIO(
        "Valid Title\n"         # Good title
        "INVALID\nBAD SLUG\n123\n"  # Three bad slugs
    )
    try:
        prompt_merged_entry(source)
    except ValueError:
        print("PASS: prompt_merged_entry raises ValueError after 3 bad slugs")
    else:
        raise AssertionError("expected ValueError for 3 invalid slug attempts")
    finally:
        sys.stdin = original_stdin


# ---------------------------------------------------------------------------
# discover_active_worktrees
# ---------------------------------------------------------------------------


def _make_parent_with_worktree(tmp: Path, wt_name: str, branch: str) -> tuple[Path, Path]:
    """Init a parent repo + add a git worktree at wts/<wt_name> on `branch`.

    Returns (parent_repo, wts_dir).
    """
    parent = tmp / "parent"
    parent.mkdir()
    subprocess.run(["git", "init", str(parent)], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(parent), "config", "user.email", "t@t.com"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(parent), "config", "user.name", "T"], capture_output=True, check=True)
    (parent / ".keep").write_text("", encoding="utf-8")
    subprocess.run(["git", "-C", str(parent), "add", ".keep"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(parent), "commit", "-m", "init"], capture_output=True, check=True)
    wts_dir = tmp / "wts"
    wts_dir.mkdir()
    entry = wts_dir / wt_name
    subprocess.run(
        ["git", "-C", str(parent), "worktree", "add", "-b", branch, str(entry)],
        capture_output=True, check=True,
    )
    return parent, wts_dir


def test_discover_active_worktrees_standard_layout() -> None:
    """Standard layout: worktree on task branch is found via git worktree list."""
    with tempfile.TemporaryDirectory() as tmp:
        parent, wts_dir = _make_parent_with_worktree(Path(tmp), "my-task", "hanf/my-task")
        entry = (wts_dir / "my-task").resolve()

        home_md = "# Home\n\n## My Task\n[[my-task]] [active]\n"
        home_tasks = _tasks_md.parse(home_md)

        results = discover_active_worktrees(wts_dir, home_tasks, "hanf/", cwd=parent)

        if len(results) != 1:
            raise AssertionError(f"expected 1 result, got {len(results)}: {results}")
        path, slug, title = results[0]
        if path != entry:
            raise AssertionError(f"expected entry {entry}, got {path}")
        if slug != "my-task":
            raise AssertionError(f"expected slug='my-task', got {slug!r}")
    print("PASS: discover_active_worktrees standard layout finds worktree via porcelain")


def test_discover_active_worktrees_subfolder_install() -> None:
    """Subfolder-install layout: worktree git root is the entry dir regardless of hub_subpath."""
    with tempfile.TemporaryDirectory() as tmp:
        parent, wts_dir = _make_parent_with_worktree(Path(tmp), "my-task", "hanf/my-task")
        entry = (wts_dir / "my-task").resolve()

        home_md = "# Home\n\n## My Subfolder Task\n[[my-task]] [active]\n"
        home_tasks = _tasks_md.parse(home_md)

        results = discover_active_worktrees(wts_dir, home_tasks, "hanf/", cwd=parent)

        if len(results) != 1:
            raise AssertionError(f"expected 1 result, got {len(results)}: {results}")
        path, slug, title = results[0]
        if path != entry:
            raise AssertionError(f"expected entry {entry}, got {path}")
        if slug != "my-task":
            raise AssertionError(f"expected slug='my-task', got {slug!r}")
    print("PASS: discover_active_worktrees subfolder-install layout finds worktree via porcelain")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def main() -> int:
    tests = [
        test_pick_task_single_slug_matching_unmarked,
        test_pick_task_single_slug_matching_s,
        test_pick_task_single_slug_already_done_raises,
        test_pick_task_single_slug_not_found_raises,
        test_pick_task_single_fast_path_s,
        test_pick_task_single_empty_backlog_raises,
        test_pick_task_single_numbered_path,
        test_pick_task_single_numbered_path_invalid_choice,
        test_pick_task_single_or_multi_single_number,
        test_pick_task_single_or_multi_multi_numbers,
        test_pick_task_single_or_multi_dedup,
        test_pick_task_single_or_multi_out_of_range_then_valid,
        test_pick_task_single_or_multi_three_bad_attempts_raises,
        test_pick_task_single_or_multi_empty_backlog,
        test_pick_task_single_or_multi_slug_bypass,
        test_pick_task_single_or_multi_fast_path_s,
        test_multi_select_groom_then_claim_basic,
        test_multi_select_groom_then_claim_with_proposal,
        test_prompt_merged_entry_happy_path_no_proposal,
        test_prompt_merged_entry_with_proposal,
        test_prompt_merged_entry_bad_title_raises,
        test_prompt_merged_entry_bad_slug_raises,
        test_claim_in_wiki,
        test_capture_parent_branch_returns_branch_name,
        test_capture_parent_branch_on_non_repo_raises,
        test_write_initial_status,
        test_write_initial_status_forced_failure_raises_runtime_error,
        test_write_initial_status_push_failure_raises_runtime_error,
        test_recreate_active_junction_creates_link,
        test_recreate_active_junction_idempotent,
        test_discover_active_worktrees_standard_layout,
        test_discover_active_worktrees_subfolder_install,
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
    print(f"All {len(tests)} _spawn_core unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
