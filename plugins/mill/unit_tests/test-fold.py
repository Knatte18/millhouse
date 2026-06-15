"""Unit tests for mill-fold helpers: _tasks_md additions (batch 1) and millpy-fold.main (batch 2)."""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

os.environ.setdefault("WIKI_DAEMON_IDLE_TIMEOUT", "1")
os.environ.setdefault("WIKI_DAEMON_SKIP_GIT", "1")
os.environ.setdefault("WIKI_DAEMON_INPROCESS", "1")

import _safe_rmtree  # noqa: E402
import _gh_issues  # noqa: E402
from wiki import _client as wiki, WikiPushError  # noqa: E402

millpy_fold = importlib.import_module("millpy-fold")

_HOME_MD_FIXTURE = (
    "# Tasks\n\n"
    "## Spawn Ready Task\n"
    "[spawn-ready] [s]\n"
    "\n"
    "This task is ready to spawn.\n"
    "\n"
    "## Active Task\n"
    "[active-task] [active]\n"
    "\n"
    "This task is currently active.\n"
    "\n"
    "## Done Task\n"
    "[done-task] [done]\n"
    "\n"
    "This task is already done.\n"
)


# ---------------------------------------------------------------------------
# Test helpers for millpy-fold.main (batch 2)
# ---------------------------------------------------------------------------

def _setup_tempfile_wiki(home_md_content: str, tasks: list[dict] = None) -> tempfile.TemporaryDirectory:
    """Create a throwaway git repo in a TemporaryDirectory with Home.md and _Sidebar.md.

    Sets up a bare sibling repo as origin so git push works in commit_push.
    If tasks is supplied, seeds tasks.json via daemon upsert_task calls for each task dict.
    Returns a wrapper with .cleanup() that handles daemon file locking on Windows.
    """
    td = tempfile.TemporaryDirectory()
    wiki_path = Path(td.name)

    (wiki_path / "Home.md").write_text(home_md_content, encoding="utf-8")
    (wiki_path / "_Sidebar.md").write_text("", encoding="utf-8")

    # Under WIKI_DAEMON_SKIP_GIT (default in this test file) the server never
    # invokes git, so the git init/remote/commit/push dance below is dead
    # weight — ~1 s per test on Windows just from subprocess spawn. Skip it.
    # When SKIP_GIT is off, set up a real repo + bare origin so commit_push
    # has somewhere to push to.
    if os.environ.get("WIKI_DAEMON_SKIP_GIT") != "1":
        bare_path = wiki_path / "bare.git"
        git_env = os.environ.copy()
        git_env.update({
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@test.com",
        })
        subprocess.run(["git", "init", "--bare", str(bare_path)], check=True, capture_output=True, env=git_env)
        subprocess.run(["git", "init", str(wiki_path)], check=True, capture_output=True, env=git_env)
        subprocess.run(["git", "-C", str(wiki_path), "config", "user.email", "test@test.com"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(wiki_path), "config", "user.name", "Test"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(wiki_path), "remote", "add", "origin", str(bare_path)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(wiki_path), "add", "--", "Home.md", "_Sidebar.md"], check=True, capture_output=True, env=git_env)
        subprocess.run(["git", "-C", str(wiki_path), "commit", "-m", "init"], check=True, capture_output=True, env=git_env)
        branch_res = subprocess.run(
            ["git", "-C", str(wiki_path), "branch", "--show-current"],
            check=True, capture_output=True, text=True, env=git_env,
        )
        branch_name = branch_res.stdout.strip() or "main"
        subprocess.run(
            ["git", "-C", str(wiki_path), "push", "--set-upstream", "origin", branch_name],
            check=True, capture_output=True, env=git_env,
        )

    # Register an in-process server for this wiki_path so subsequent client ops
    # don't pay the daemon subprocess spawn cost. Each test gets a fresh path
    # so registrations don't collide.
    wiki.use_inprocess(wiki_path)

    if tasks:
        for task in tasks:
            wiki.upsert_task(wiki_path, **task)

    # Cleanup: unregister the in-process server (releases any file handles
    # before tempdir removal), then remove the tempdir. ignore_errors fallback
    # is kept in case a stale daemon from an earlier run holds locks.
    original_cleanup = td.cleanup
    def safe_cleanup():
        try:
            wiki.stop_inprocess(wiki_path)
        except Exception:
            pass
        try:
            original_cleanup()
        except (OSError, PermissionError):
            try:
                _safe_rmtree.safe_rmtree(Path(td.name), allowed_root=Path(td.name), ignore_errors=True)
            except Exception:
                pass

    td.cleanup = safe_cleanup
    return td


def _patch_resolve_paths(wiki_path: Path) -> tuple:
    """Swap millpy_fold's resolve_git_root and resolve_wiki_path to return wiki_path.

    Returns (orig_resolve_git_root, orig_resolve_wiki_path) so the caller can
    restore them in a finally block.
    """
    orig_rg = millpy_fold.resolve_git_root
    orig_rwp = millpy_fold.resolve_wiki_path
    millpy_fold.resolve_git_root = lambda: wiki_path
    millpy_fold.resolve_wiki_path = lambda _git_top: wiki_path
    return orig_rg, orig_rwp


def _make_fake_fetch_one(state: str = "OPEN", title: str = "fake issue", number: int = 42):
    """Return a callable that simulates _gh_issues.fetch_one.

    Returns a dict for OPEN issues; raises GhError for other states.
    """
    def fake_fetch_one(n, **kwargs):
        if state == "OPEN":
            return {
                "number": n,
                "title": title,
                "body": "",
                "state": state,
                "labels": [],
                "createdAt": "2026-05-12T00:00:00Z",
            }
        raise _gh_issues.GhError(f"issue #{n} is {state}; only OPEN issues can be folded")
    return fake_fetch_one


def _make_fake_close_with_comment() -> tuple:
    """Return (callable, captured_calls) pair for testing GH close behavior."""
    captured_calls: list[tuple[int, str]] = []

    def fake_close(number, comment, **kwargs):
        captured_calls.append((number, comment))

    return fake_close, captured_calls


def _suppress_stdin_isatty():
    """Patch sys.stdin.isatty to return False. Returns original for restoration."""
    orig = sys.stdin.isatty
    sys.stdin.isatty = lambda: False
    return orig


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------

def main() -> int:
    # --- append to task body via daemon round-trip ---
    try:
        home_content = "# Tasks\n\n## Spawn Ready Task\n[spawn-ready]\n\nInitial body.\n\n## Active Task\n[active-task]\n\nOther task.\n"
        td = _setup_tempfile_wiki(
            home_content,
            tasks=[
                {"slug": "spawn-ready", "title": "Spawn Ready Task", "brief": "Initial body.", "status": None},
                {"slug": "active-task", "title": "Active Task", "brief": "Other task.", "status": None},
            ],
        )
        wiki_path = Path(td.name)
        try:
            # Append new line to spawn-ready task
            task = wiki.get_task(wiki_path, "spawn-ready")
            wiki.upsert_task(wiki_path, slug="spawn-ready", brief=task["brief"] + "\n- Sources: #99 -- example")
            # Verify the append
            updated = wiki.get_task(wiki_path, "spawn-ready")
            assert "- Sources: #99 -- example" in updated["brief"], (
                f"Expected appended line in brief, got: {updated['brief']!r}"
            )
            print("PASS: append to task body via daemon round-trip")
        finally:
            td.cleanup()
    except (AssertionError, Exception) as exc:
        print(f"FAIL: append to task body via daemon round-trip: {exc}")
        return 1

    # --- append to EOF task ---
    try:
        home_content = "# Tasks\n\n## Done Task\n[done-task]\n\nBody.\n"
        td = _setup_tempfile_wiki(
            home_content,
            tasks=[
                {"slug": "done-task", "title": "Done Task", "brief": "Body.", "status": "done"},
            ],
        )
        wiki_path = Path(td.name)
        try:
            task = wiki.get_task(wiki_path, "done-task")
            wiki.upsert_task(wiki_path, slug="done-task", brief=task["brief"] + "\n- Sources: #100 -- final")
            updated = wiki.get_task(wiki_path, "done-task")
            assert "- Sources: #100 -- final" in updated["brief"], (
                f"Expected appended line in brief, got: {updated['brief']!r}"
            )
            print("PASS: append to EOF task")
        finally:
            td.cleanup()
    except (AssertionError, Exception) as exc:
        print(f"FAIL: append to EOF task: {exc}")
        return 1

    # --- append to empty task body ---
    try:
        home_content = "# Tasks\n\n## Empty Task\n[empty-task]\n"
        td = _setup_tempfile_wiki(
            home_content,
            tasks=[
                {"slug": "empty-task", "title": "Empty Task", "brief": "", "status": None},
            ],
        )
        wiki_path = Path(td.name)
        try:
            task = wiki.get_task(wiki_path, "empty-task")
            wiki.upsert_task(wiki_path, slug="empty-task", brief=task["brief"] + "\n- note" if task["brief"] else "- note")
            updated = wiki.get_task(wiki_path, "empty-task")
            assert updated["brief"] == "- note", (
                f"Expected brief to be '- note', got: {updated['brief']!r}"
            )
            print("PASS: append to empty task body")
        finally:
            td.cleanup()
    except (AssertionError, Exception) as exc:
        print(f"FAIL: append to empty task body: {exc}")
        return 1

    # -----------------------------------------------------------------------
    # millpy-fold.main end-to-end tests (batch 2, card 5)
    # -----------------------------------------------------------------------

    # --- locked phase active refused ---
    try:
        home_content = "# Tasks\n\n## Locked Task\n[locked-task] [active]\n\nBody.\n"
        td = _setup_tempfile_wiki(
            home_content,
            tasks=[
                {"slug": "locked-task", "title": "Locked Task", "brief": "Body.", "status": "active"},
            ],
        )
        wiki_path = Path(td.name)
        orig_rg, orig_rwp = _patch_resolve_paths(wiki_path)
        try:
            pre_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            raised = False
            try:
                millpy_fold.main(["locked-task", "--scope", "x"])
            except SystemExit:
                raised = True
            assert raised, "Expected SystemExit for locked [active] phase"
            post_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            assert post_home == pre_home, "Home.md was mutated despite phase guard"
            print("PASS: locked phase active refused")
        finally:
            millpy_fold.resolve_git_root = orig_rg
            millpy_fold.resolve_wiki_path = orig_rwp
            td.cleanup()
    except (AssertionError, Exception) as exc:
        print(f"FAIL: locked phase active refused: {exc}")
        return 1

    # --- locked phase ready-to-merge refused ---
    try:
        home_content = "# Tasks\n\n## Locked Task\n[locked-task] [ready-to-merge]\n\nBody.\n"
        td = _setup_tempfile_wiki(
            home_content,
            tasks=[
                {"slug": "locked-task", "title": "Locked Task", "brief": "Body.", "status": "ready-to-merge"},
            ],
        )
        wiki_path = Path(td.name)
        orig_rg, orig_rwp = _patch_resolve_paths(wiki_path)
        try:
            pre_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            raised = False
            try:
                millpy_fold.main(["locked-task", "--scope", "x"])
            except SystemExit:
                raised = True
            assert raised, "Expected SystemExit for locked [ready-to-merge] phase"
            post_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            assert post_home == pre_home, "Home.md was mutated despite phase guard"
            print("PASS: locked phase ready-to-merge refused")
        finally:
            millpy_fold.resolve_git_root = orig_rg
            millpy_fold.resolve_wiki_path = orig_rwp
            td.cleanup()
    except (AssertionError, Exception) as exc:
        print(f"FAIL: locked phase ready-to-merge refused: {exc}")
        return 1

    # --- locked phase pr-pending refused ---
    try:
        home_content = "# Tasks\n\n## Locked Task\n[locked-task] [pr-pending]\n\nBody.\n"
        td = _setup_tempfile_wiki(
            home_content,
            tasks=[
                {"slug": "locked-task", "title": "Locked Task", "brief": "Body.", "status": "pr-pending"},
            ],
        )
        wiki_path = Path(td.name)
        orig_rg, orig_rwp = _patch_resolve_paths(wiki_path)
        try:
            pre_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            raised = False
            try:
                millpy_fold.main(["locked-task", "--scope", "x"])
            except SystemExit:
                raised = True
            assert raised, "Expected SystemExit for locked [pr-pending] phase"
            post_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            assert post_home == pre_home, "Home.md was mutated despite phase guard"
            print("PASS: locked phase pr-pending refused")
        finally:
            millpy_fold.resolve_git_root = orig_rg
            millpy_fold.resolve_wiki_path = orig_rwp
            td.cleanup()
    except (AssertionError, Exception) as exc:
        print(f"FAIL: locked phase pr-pending refused: {exc}")
        return 1

    # --- unmarked target accepts scope fold ---
    try:
        home_content = "# Tasks\n\n## My Task\n[my-task]\n\nTask body.\n"
        td = _setup_tempfile_wiki(
            home_content,
            tasks=[
                {"slug": "my-task", "title": "My Task", "brief": "Task body.", "status": None},
            ],
        )
        wiki_path = Path(td.name)
        orig_rg, orig_rwp = _patch_resolve_paths(wiki_path)
        try:
            rc = millpy_fold.main(["my-task", "--scope", "edge case X"])
            assert rc == 0, f"Expected return 0, got {rc}"
            post_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            lines = post_home.rstrip("\n").splitlines()
            last_non_blank = next(line for line in reversed(lines) if line.strip())
            assert last_non_blank == "- Folded in: edge case X", (
                f"Expected fold bullet as last non-blank line, got: {last_non_blank!r}"
            )
            print("PASS: unmarked target accepts scope fold")
        finally:
            millpy_fold.resolve_git_root = orig_rg
            millpy_fold.resolve_wiki_path = orig_rwp
            td.cleanup()
    except (AssertionError, Exception) as exc:
        print(f"FAIL: unmarked target accepts scope fold: {exc}")
        return 1

    # --- spawn-ready target accepts scope fold ---
    try:
        home_content = "# Tasks\n\n## Ready Task\n[ready-task] [s]\n\nBody.\n"
        td = _setup_tempfile_wiki(
            home_content,
            tasks=[
                {"slug": "ready-task", "title": "Ready Task", "brief": "Body.", "status": None},
            ],
        )
        wiki_path = Path(td.name)
        orig_rg, orig_rwp = _patch_resolve_paths(wiki_path)
        try:
            rc = millpy_fold.main(["ready-task", "--scope", "spawn ready fold"])
            assert rc == 0, f"Expected return 0, got {rc}"
            post_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            assert "- Folded in: spawn ready fold" in post_home, (
                "Fold bullet not found in Home.md"
            )
            print("PASS: spawn-ready target accepts scope fold")
        finally:
            millpy_fold.resolve_git_root = orig_rg
            millpy_fold.resolve_wiki_path = orig_rwp
            td.cleanup()
    except (AssertionError, Exception) as exc:
        print(f"FAIL: spawn-ready target accepts scope fold: {exc}")
        return 1

    # --- done phase refused ---
    try:
        home_content = "# Tasks\n\n## Done Task\n[done-task] [done]\n\nBody.\n"
        td = _setup_tempfile_wiki(
            home_content,
            tasks=[
                {"slug": "done-task", "title": "Done Task", "brief": "Body.", "status": "done"},
            ],
        )
        wiki_path = Path(td.name)
        orig_rg, orig_rwp = _patch_resolve_paths(wiki_path)
        try:
            pre_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            raised = False
            try:
                millpy_fold.main(["done-task", "--scope", "done fold"])
            except SystemExit:
                raised = True
            assert raised, "Expected SystemExit for done phase"
            post_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            assert post_home == pre_home, "Home.md was mutated despite done phase guard"
            print("PASS: done phase refused")
        finally:
            millpy_fold.resolve_git_root = orig_rg
            millpy_fold.resolve_wiki_path = orig_rwp
            td.cleanup()
    except (AssertionError, Exception) as exc:
        print(f"FAIL: done phase refused: {exc}")
        return 1

    # --- abandoned phase refused ---
    try:
        home_content = "# Tasks\n\n## Abandoned Task\n[abandoned-task] [abandoned]\n\nBody.\n"
        td = _setup_tempfile_wiki(
            home_content,
            tasks=[
                {"slug": "abandoned-task", "title": "Abandoned Task", "brief": "Body.", "status": "abandoned"},
            ],
        )
        wiki_path = Path(td.name)
        orig_rg, orig_rwp = _patch_resolve_paths(wiki_path)
        try:
            pre_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            raised = False
            try:
                millpy_fold.main(["abandoned-task", "--scope", "abandoned fold"])
            except SystemExit:
                raised = True
            assert raised, "Expected SystemExit for abandoned phase"
            post_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            assert post_home == pre_home, "Home.md was mutated despite abandoned phase guard"
            print("PASS: abandoned phase refused")
        finally:
            millpy_fold.resolve_git_root = orig_rg
            millpy_fold.resolve_wiki_path = orig_rwp
            td.cleanup()
    except (AssertionError, Exception) as exc:
        print(f"FAIL: abandoned phase refused: {exc}")
        return 1

    # --- unclaimed backlog accepts fold ---
    try:
        home_content = "# Tasks\n\n## Backlog Task\n[backlog-task]\n\nBacklog body.\n"
        td = _setup_tempfile_wiki(
            home_content,
            tasks=[
                {"slug": "backlog-task", "title": "Backlog Task", "brief": "Backlog body.", "status": None},
            ],
        )
        wiki_path = Path(td.name)
        orig_rg, orig_rwp = _patch_resolve_paths(wiki_path)
        try:
            rc = millpy_fold.main(["backlog-task", "--scope", "unclaimed fold"])
            assert rc == 0, f"Expected return 0, got {rc}"
            post_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            assert "- Folded in: unclaimed fold" in post_home, "Fold bullet not found in Home.md"
            print("PASS: unclaimed backlog accepts fold")
        finally:
            millpy_fold.resolve_git_root = orig_rg
            millpy_fold.resolve_wiki_path = orig_rwp
            td.cleanup()
    except (AssertionError, Exception) as exc:
        print(f"FAIL: unclaimed backlog accepts fold: {exc}")
        return 1

    # --- blocked status refused ---
    try:
        home_content = "# Tasks\n\n## Blocked Task\n[blocked-task] [blocked]\n\nBody.\n"
        td = _setup_tempfile_wiki(
            home_content,
            tasks=[
                {"slug": "blocked-task", "title": "Blocked Task", "brief": "Body.", "status": "blocked"},
            ],
        )
        wiki_path = Path(td.name)
        orig_rg, orig_rwp = _patch_resolve_paths(wiki_path)
        try:
            pre_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            raised = False
            try:
                millpy_fold.main(["blocked-task", "--scope", "blocked fold"])
            except SystemExit:
                raised = True
            assert raised, "Expected SystemExit for blocked status"
            post_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            assert post_home == pre_home, "Home.md was mutated despite blocked status guard"
            print("PASS: blocked status refused")
        finally:
            millpy_fold.resolve_git_root = orig_rg
            millpy_fold.resolve_wiki_path = orig_rwp
            td.cleanup()
    except (AssertionError, Exception) as exc:
        print(f"FAIL: blocked status refused: {exc}")
        return 1

    # --- deferred task refused ---
    try:
        home_content = "# Tasks\n\n## Deferred Task\n[deferred-task]\n\nBody.\n"
        td = _setup_tempfile_wiki(
            home_content,
            tasks=[
                {"slug": "deferred-task", "title": "Deferred Task", "brief": "Body.", "status": None, "deferred": True},
            ],
        )
        wiki_path = Path(td.name)
        orig_rg, orig_rwp = _patch_resolve_paths(wiki_path)
        try:
            pre_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            raised = False
            try:
                millpy_fold.main(["deferred-task", "--scope", "deferred fold"])
            except SystemExit:
                raised = True
            assert raised, "Expected SystemExit for deferred task"
            post_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            assert post_home == pre_home, "Home.md was mutated despite deferred guard"
            print("PASS: deferred task refused")
        finally:
            millpy_fold.resolve_git_root = orig_rg
            millpy_fold.resolve_wiki_path = orig_rwp
            td.cleanup()
    except (AssertionError, Exception) as exc:
        print(f"FAIL: deferred task refused: {exc}")
        return 1

    # --- --issue path against refused target raises SystemExit and skips GH close ---
    try:
        home_content = "# Tasks\n\n## Done Task\n[done-task] [done]\n\nBody.\n"
        td = _setup_tempfile_wiki(
            home_content,
            tasks=[
                {"slug": "done-task", "title": "Done Task", "brief": "Body.", "status": "done"},
            ],
        )
        wiki_path = Path(td.name)
        orig_rg, orig_rwp = _patch_resolve_paths(wiki_path)
        close_fn, captured_calls = _make_fake_close_with_comment()
        orig_isatty = _suppress_stdin_isatty()
        try:
            pre_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            raised = False
            try:
                millpy_fold.main(
                    ["done-task", "--issue", "99"],
                    _fetch_one=_make_fake_fetch_one(state="OPEN", title="issue X", number=99),
                    _close_with_comment=close_fn,
                )
            except SystemExit:
                raised = True
            assert raised, "Expected SystemExit for --issue fold into done task"
            post_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            assert post_home == pre_home, "Home.md was mutated despite done phase guard"
            assert captured_calls == [], f"Expected no GH close calls for refused --issue fold, got {captured_calls}"
            print("PASS: --issue path against refused target raises SystemExit and skips GH close")
        finally:
            millpy_fold.resolve_git_root = orig_rg
            millpy_fold.resolve_wiki_path = orig_rwp
            sys.stdin.isatty = orig_isatty
            td.cleanup()
    except (AssertionError, Exception) as exc:
        print(f"FAIL: --issue path against refused target raises SystemExit and skips GH close: {exc}")
        return 1

    # --- missing slug errors ---
    try:
        home_content = "# Tasks\n\n## Some Task\n[some-task]\n\nBody.\n"
        td = _setup_tempfile_wiki(
            home_content,
            tasks=[
                {"slug": "some-task", "title": "Some Task", "brief": "Body.", "status": None},
            ],
        )
        wiki_path = Path(td.name)
        orig_rg, orig_rwp = _patch_resolve_paths(wiki_path)
        try:
            pre_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            raised = False
            try:
                millpy_fold.main(["nonexistent-slug", "--scope", "x"])
            except SystemExit:
                raised = True
            assert raised, "Expected SystemExit for missing slug"
            post_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            assert post_home == pre_home, "Home.md was mutated despite missing slug"
            print("PASS: missing slug errors")
        finally:
            millpy_fold.resolve_git_root = orig_rg
            millpy_fold.resolve_wiki_path = orig_rwp
            td.cleanup()
    except (AssertionError, Exception) as exc:
        print(f"FAIL: missing slug errors: {exc}")
        return 1

    # --- invalid slug format errors ---
    try:
        orig_rg, orig_rwp = _patch_resolve_paths(Path("/fake/wiki"))
        try:
            raised = False
            try:
                millpy_fold.main(["Invalid-Slug", "--scope", "x"])
            except SystemExit as exc:
                raised = True
                assert "Invalid slug" in str(exc), (
                    f"Expected 'Invalid slug' in SystemExit message, got: {exc}"
                )
            assert raised, "Expected SystemExit for invalid slug format"
            print("PASS: invalid slug format errors")
        finally:
            millpy_fold.resolve_git_root = orig_rg
            millpy_fold.resolve_wiki_path = orig_rwp
    except (AssertionError, Exception) as exc:
        print(f"FAIL: invalid slug format errors: {exc}")
        return 1

    # --- closed GH issue refused ---
    try:
        home_content = "# Tasks\n\n## My Task\n[my-task]\n\nTask body.\n"
        td = _setup_tempfile_wiki(
            home_content,
            tasks=[
                {"slug": "my-task", "title": "My Task", "brief": "Task body.", "status": None},
            ],
        )
        wiki_path = Path(td.name)
        orig_rg, orig_rwp = _patch_resolve_paths(wiki_path)
        close_fn, captured_calls = _make_fake_close_with_comment()
        orig_isatty = _suppress_stdin_isatty()
        try:
            pre_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            raised = False
            try:
                millpy_fold.main(
                    ["my-task", "--issue", "42"],
                    _fetch_one=_make_fake_fetch_one(state="CLOSED"),
                    _close_with_comment=close_fn,
                )
            except SystemExit:
                raised = True
            assert raised, "Expected SystemExit for closed GH issue"
            post_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            assert post_home == pre_home, "Home.md was mutated despite closed-issue guard"
            assert captured_calls == [], f"Expected no close calls, got {captured_calls}"
            print("PASS: closed GH issue refused")
        finally:
            millpy_fold.resolve_git_root = orig_rg
            millpy_fold.resolve_wiki_path = orig_rwp
            sys.stdin.isatty = orig_isatty
            td.cleanup()
    except (AssertionError, Exception) as exc:
        print(f"FAIL: closed GH issue refused: {exc}")
        return 1

    # --- open GH issue accepted ---
    try:
        target = "my-task"
        home_content = "# Tasks\n\n## My Task\n[my-task]\n\nTask body.\n"
        td = _setup_tempfile_wiki(
            home_content,
            tasks=[
                {"slug": "my-task", "title": "My Task", "brief": "Task body.", "status": None},
            ],
        )
        wiki_path = Path(td.name)
        orig_rg, orig_rwp = _patch_resolve_paths(wiki_path)
        close_fn, captured_calls = _make_fake_close_with_comment()
        orig_isatty = _suppress_stdin_isatty()
        try:
            rc = millpy_fold.main(
                [target, "--issue", "42"],
                _fetch_one=_make_fake_fetch_one(state="OPEN", title="bug X", number=42),
                _close_with_comment=close_fn,
            )
            assert rc == 0, f"Expected return 0, got {rc}"
            post_home = (wiki_path / "Home.md").read_text(encoding="utf-8")
            assert "- Sources: #42 — bug X" in post_home, (
                f"Fold bullet not found in Home.md:\n{post_home}"
            )
            expected_close = [(42, f"Folded into wiki task: {target}")]
            assert captured_calls == expected_close, (
                f"Expected close calls {expected_close}, got {captured_calls}"
            )
            print("PASS: open GH issue accepted")
        finally:
            millpy_fold.resolve_git_root = orig_rg
            millpy_fold.resolve_wiki_path = orig_rwp
            sys.stdin.isatty = orig_isatty
            td.cleanup()
    except (AssertionError, Exception) as exc:
        print(f"FAIL: open GH issue accepted: {exc}")
        return 1

    # --- wiki commit failure skips GH close ---
    try:
        home_content = "# Tasks\n\n## My Task\n[my-task]\n\nTask body.\n"
        td = _setup_tempfile_wiki(
            home_content,
            tasks=[
                {"slug": "my-task", "title": "My Task", "brief": "Task body.", "status": None},
            ],
        )
        wiki_path = Path(td.name)
        orig_rg, orig_rwp = _patch_resolve_paths(wiki_path)
        close_fn, captured_calls = _make_fake_close_with_comment()
        orig_isatty = _suppress_stdin_isatty()
        try:
            raised = False
            with patch.object(millpy_fold.wiki, "upsert_task", side_effect=WikiPushError("simulated push failure")):
                try:
                    millpy_fold.main(
                        ["my-task", "--issue", "42"],
                        _fetch_one=_make_fake_fetch_one(state="OPEN"),
                        _close_with_comment=close_fn,
                    )
                except (SystemExit, WikiPushError):
                    raised = True
            assert raised, "Expected exception (SystemExit or WikiPushError) from wiki push failure"
            assert captured_calls == [], (
                f"Expected no close calls after push failure, got {captured_calls}"
            )
            print("PASS: wiki commit failure skips GH close")
        finally:
            millpy_fold.resolve_git_root = orig_rg
            millpy_fold.resolve_wiki_path = orig_rwp
            sys.stdin.isatty = orig_isatty
            td.cleanup()
    except (AssertionError, Exception) as exc:
        print(f"FAIL: wiki commit failure skips GH close: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
