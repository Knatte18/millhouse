"""Unit tests for _wiki.py lock subsystem.

Tests the wiki_lock context manager, re-entrancy counter, stale-self-lock
detection, and automatic acquire/release inside sync_pull/write_commit_push.
Uses tempfile.TemporaryDirectory for the wiki dir; patches _subprocess_util.run
for all git operations so no real git activity occurs.
"""
from __future__ import annotations

import datetime
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _paths  # noqa: E402
import _wiki  # noqa: E402


def _ok_result(**kwargs):
    r = MagicMock()
    r.returncode = kwargs.get("returncode", 0)
    r.stdout = kwargs.get("stdout", "")
    r.stderr = kwargs.get("stderr", "")
    return r


def _ok_run(*args, **kwargs):
    return _ok_result()


def _fail_on_add(*args, **kwargs):
    cmd = args[0] if args else []
    if "add" in cmd:
        return _ok_result(returncode=1, stderr="error: add failed")
    return _ok_result()


def main() -> int:
    passed = 0
    failed = 0

    def ok(name: str) -> None:
        nonlocal passed
        passed += 1
        msg = f"PASS: {name}\n"
        sys.stdout.buffer.write(msg.encode("utf-8", errors="backslashreplace"))
        sys.stdout.buffer.flush()

    def fail(name: str, exc: Exception) -> None:
        nonlocal failed
        failed += 1
        msg = f"FAIL: {name}: {exc}\n"
        sys.stderr.buffer.write(msg.encode("utf-8", errors="backslashreplace"))
        sys.stderr.buffer.flush()

    # --- (a) trivial acquire + release ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            wiki = Path(tmp_str)
            lock_path = wiki / ".mill-lock"
            with _wiki.wiki_lock(wiki, "slug-a"):
                assert lock_path.exists(), "lockfile must exist inside context"
            assert not lock_path.exists(), "lockfile must be gone after context exits"
        ok("wiki_lock: trivial acquire + release")
    except Exception as exc:
        fail("wiki_lock: trivial acquire + release", exc)

    # --- (b) re-entrancy ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            wiki = Path(tmp_str)
            lock_path = wiki / ".mill-lock"
            resolved = wiki.resolve()
            with _wiki.wiki_lock(wiki, "slug-b"):
                assert _wiki._held_locks.get(resolved) == 1
                with _wiki.wiki_lock(wiki, "slug-b"):
                    assert _wiki._held_locks.get(resolved) == 2
                    assert lock_path.exists(), "lockfile must persist inside inner block"
                assert _wiki._held_locks.get(resolved) == 1, "counter must drop to 1 after inner exit"
                assert lock_path.exists(), "lockfile must persist until outer exits"
            assert resolved not in _wiki._held_locks, "counter entry must be removed after outer exits"
            assert not lock_path.exists(), "lockfile must be gone after outer exits"
        ok("wiki_lock: re-entrancy — nested calls do not deadlock, file persists until outer exits")
    except Exception as exc:
        fail("wiki_lock: re-entrancy", exc)

    # --- (c) sync_pull + write_commit_push skip re-acquire inside wiki_lock ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            wiki = Path(tmp_str)
            resolved = wiki.resolve()
            with patch.object(_wiki._subprocess_util, "run", side_effect=_ok_run):
                with _wiki.wiki_lock(wiki, "slug-c"):
                    assert _wiki._held_locks.get(resolved) == 1
                    _wiki.sync_pull(wiki, slug="slug-c")
                    assert _wiki._held_locks.get(resolved) == 1, \
                        "sync_pull must not increment counter when lock already held"
                    _wiki.write_commit_push(wiki, ["Home.md"], "msg", slug="slug-c")
                    assert _wiki._held_locks.get(resolved) == 1, \
                        "write_commit_push must not increment counter when lock already held"
        ok("sync_pull + write_commit_push skip re-acquire inside wiki_lock")
    except Exception as exc:
        fail("sync_pull + write_commit_push skip re-acquire inside wiki_lock", exc)

    # --- (d) sync_pull acquires/releases on its own outside wiki_lock ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            wiki = Path(tmp_str)
            lock_path = wiki / ".mill-lock"
            resolved = wiki.resolve()
            with patch.object(_wiki._subprocess_util, "run", side_effect=_ok_run):
                _wiki.sync_pull(wiki, slug="slug-d")
            assert not lock_path.exists(), "lockfile must be gone after standalone sync_pull"
            assert _wiki._held_locks.get(resolved, 0) == 0, "counter must be 0 after standalone sync_pull"
        ok("sync_pull: acquires/releases lock on its own outside wiki_lock")
    except Exception as exc:
        fail("sync_pull: standalone acquire/release", exc)

    # --- (e) stale-self-lock detection ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            wiki = Path(tmp_str)
            lock_path = wiki / ".mill-lock"
            # Use a recent timestamp (30 s ago) so the lock is NOT stale-by-age
            # (age << 5 min threshold). Only the self-lock branch can trigger here.
            recent_ts = (
                datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=30)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            lock_path.write_text(f"my-slug\n{recent_ts}\n", encoding="utf-8")
            # With timeout_seconds=1 a real wait would take 1 s; self-lock must return immediately.
            _wiki._acquire(wiki, "my-slug", timeout_seconds=1)
            content = lock_path.read_text(encoding="utf-8")
            lines = content.strip().splitlines()
            assert lines[0] == "my-slug", f"holder mismatch: {lines[0]!r}"
            assert lines[1] != recent_ts, "timestamp must be refreshed on reclaim (not the old value)"
            _wiki._release(wiki)  # clean up for next test
        ok("_acquire: stale-self-lock reclaimed immediately, timestamp updated")
    except Exception as exc:
        fail("_acquire: stale-self-lock", exc)

    # --- (f) lockfile released on WikiPushError ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            wiki = Path(tmp_str)
            lock_path = wiki / ".mill-lock"
            with patch.object(_wiki._subprocess_util, "run", side_effect=_fail_on_add):
                raised = False
                try:
                    _wiki.write_commit_push(wiki, ["Home.md"], "msg", slug="slug-f")
                except _wiki.WikiPushError:
                    raised = True
                assert raised, "WikiPushError must propagate"
            assert not lock_path.exists(), "lockfile must be released even after WikiPushError"
        ok("write_commit_push: lockfile released on WikiPushError")
    except Exception as exc:
        fail("write_commit_push: lockfile released on WikiPushError", exc)

    # --- clone_or_init tests ---

    # (1) clone with explicit branch that exists on remote
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            dest = tmp / "wiki"
            url = "https://example.com/repo.git"
            branch = "docs"
            calls: list = []

            def _run_branch_exists(argv, **kwargs):
                calls.append(argv)
                if argv[0:3] == ["git", "ls-remote", "--heads"]:
                    return _ok_result(stdout="abc123\trefs/heads/docs\n")
                return _ok_result()

            with patch("_wiki._subprocess_util.run", side_effect=_run_branch_exists):
                result = _wiki.clone_or_init(url, branch, dest)

            assert result == {"action": "cloned", "branch_existed_on_remote": True}
            assert len(calls) == 2, f"Expected 2 calls, got {len(calls)}: {calls}"
            assert calls[0] == ["git", "ls-remote", "--heads", url, branch]
            assert calls[1] == ["git", "clone", "-b", branch, "--single-branch", url, str(dest)]
        ok("clone_or_init: clone with explicit branch exists on remote")
    except Exception as exc:
        fail("clone_or_init: clone with explicit branch exists on remote", exc)

    # (2) init orphan when branch missing from remote
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            dest = tmp / "wiki"
            url = "https://example.com/repo.git"
            branch = "mill-wiki"
            calls: list = []

            def _run_orphan(argv, **kwargs):
                calls.append(argv)
                return _ok_result()  # ls-remote returns empty stdout (branch absent)

            with patch("_wiki._subprocess_util.run", side_effect=_run_orphan):
                result = _wiki.clone_or_init(url, branch, dest)

            assert result == {"action": "initialized", "branch_existed_on_remote": False}
            assert calls[0] == ["git", "ls-remote", "--heads", url, branch]
            assert calls[1] == ["git", "init", str(dest)]
            assert calls[2] == ["git", "-C", str(dest), "remote", "add", "origin", url]
            assert calls[3] == ["git", "-C", str(dest), "checkout", "--orphan", branch]
            assert calls[4] == ["git", "-C", str(dest), "config", f"branch.{branch}.remote", "origin"]
            assert calls[5] == ["git", "-C", str(dest), "config", f"branch.{branch}.merge", f"refs/heads/{branch}"]
            assert len(calls) == 6, f"Expected 6 calls, got {len(calls)}: {calls}"
        ok("clone_or_init: init orphan when branch missing from remote")
    except Exception as exc:
        fail("clone_or_init: init orphan when branch missing from remote", exc)

    # (3) clone without branch (remote HEAD)
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            dest = tmp / "wiki"
            url = "https://example.com/repo.git"
            calls: list = []

            def _run_no_branch(argv, **kwargs):
                calls.append(argv)
                return _ok_result()

            with patch("_wiki._subprocess_util.run", side_effect=_run_no_branch):
                result = _wiki.clone_or_init(url, None, dest)

            assert result == {"action": "cloned", "branch_existed_on_remote": None}
            assert len(calls) == 1, f"Expected 1 call, got {len(calls)}: {calls}"
            assert calls[0] == ["git", "clone", url, str(dest)]
        ok("clone_or_init: clone without branch (remote HEAD)")
    except Exception as exc:
        fail("clone_or_init: clone without branch (remote HEAD)", exc)

    # (4) pull existing repo with matching url and branch
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            dest = tmp / "wiki"
            dest.mkdir()
            (dest / ".git").mkdir()
            url = "https://example.com/repo.git"
            branch = "main"
            calls: list = []

            def _run_pull_existing(argv, **kwargs):
                calls.append(argv)
                if "get-url" in argv:
                    return _ok_result(stdout=url + "\n")
                if "--show-current" in argv:
                    return _ok_result(stdout=branch + "\n")
                return _ok_result()

            with patch("_wiki._subprocess_util.run", side_effect=_run_pull_existing):
                result = _wiki.clone_or_init(url, branch, dest)

            assert result == {"action": "pulled", "branch_existed_on_remote": None}
            assert calls[-1] == ["git", "-C", str(dest), "pull", "--ff-only"]
        ok("clone_or_init: pull existing repo with matching url and branch")
    except Exception as exc:
        fail("clone_or_init: pull existing repo with matching url and branch", exc)

    # (5) halt when dest exists but is not a git repo
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            dest = tmp / "wiki"
            dest.mkdir()
            # no .git dir — not a repo
            raised = False
            try:
                _wiki.clone_or_init("https://example.com/repo.git", None, dest)
            except _wiki.WikiSetupError as exc:
                raised = True
                assert str(dest) in str(exc), f"dest missing from message: {exc}"
                assert "not a git repository" in str(exc), f"phrase missing: {exc}"
            assert raised, "WikiSetupError must be raised"
        ok("clone_or_init: halt when dest exists but not a git repo")
    except Exception as exc:
        fail("clone_or_init: halt when dest exists but not a git repo", exc)

    # (6) halt on origin URL mismatch
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            dest = tmp / "wiki"
            dest.mkdir()
            (dest / ".git").mkdir()
            url = "https://example.com/expected.git"
            actual_url = "https://example.com/other.git"
            calls: list = []

            def _run_url_mismatch(argv, **kwargs):
                calls.append(argv)
                if "get-url" in argv:
                    return _ok_result(stdout=actual_url + "\n")
                return _ok_result()

            raised = False
            try:
                with patch("_wiki._subprocess_util.run", side_effect=_run_url_mismatch):
                    _wiki.clone_or_init(url, None, dest)
            except _wiki.WikiSetupError as exc:
                raised = True
                assert url in str(exc) and actual_url in str(exc), f"Both URLs must appear: {exc}"
            assert raised, "WikiSetupError must be raised"
            # no further calls after the mismatch
            assert len(calls) == 1, f"Expected 1 call after mismatch, got {len(calls)}: {calls}"
        ok("clone_or_init: halt on origin URL mismatch")
    except Exception as exc:
        fail("clone_or_init: halt on origin URL mismatch", exc)

    # (7) halt on branch mismatch
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            dest = tmp / "wiki"
            dest.mkdir()
            (dest / ".git").mkdir()
            url = "https://example.com/repo.git"
            branch = "expected-branch"
            actual_branch = "other-branch"
            calls: list = []

            def _run_branch_mismatch(argv, **kwargs):
                calls.append(argv)
                if "get-url" in argv:
                    return _ok_result(stdout=url + "\n")
                if "--show-current" in argv:
                    return _ok_result(stdout=actual_branch + "\n")
                return _ok_result()

            raised = False
            try:
                with patch("_wiki._subprocess_util.run", side_effect=_run_branch_mismatch):
                    _wiki.clone_or_init(url, branch, dest)
            except _wiki.WikiSetupError as exc:
                raised = True
                assert branch in str(exc) and actual_branch in str(exc), f"Both branches must appear: {exc}"
            assert raised, "WikiSetupError must be raised"
            # no pull call after the mismatch
            pull_calls = [c for c in calls if "pull" in c]
            assert not pull_calls, f"No pull call should happen after branch mismatch: {calls}"
        ok("clone_or_init: halt on branch mismatch")
    except Exception as exc:
        fail("clone_or_init: halt on branch mismatch", exc)

    # (8) reachability failure — ls-remote returns non-zero
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            dest = tmp / "wiki"
            url = "https://example.com/repo.git"
            branch = "docs"

            def _run_ls_remote_fail(argv, **kwargs):
                return _ok_result(returncode=128, stderr="fatal: unable to access 'https://...'")

            raised = False
            try:
                with patch("_wiki._subprocess_util.run", side_effect=_run_ls_remote_fail):
                    _wiki.clone_or_init(url, branch, dest)
            except _wiki.WikiSetupError:
                raised = True
            assert raised, "WikiSetupError must be raised on ls-remote failure"
        ok("clone_or_init: reachability failure from ls-remote")
    except Exception as exc:
        fail("clone_or_init: reachability failure from ls-remote", exc)

    # --- (g) health_check passes when mill-config.yaml present ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_hub = Path(tmp_str)
            (tmp_hub / "mill-config.yaml").write_text("repo: test\n", encoding="utf-8")
            result = _wiki.health_check(tmp_hub)
            assert result is None, f"health_check must return None, got {result!r}"
        ok("health_check: returns None when mill-config.yaml present")
    except Exception as exc:
        fail("health_check: returns None when mill-config.yaml present", exc)

    # --- (h) health_check raises when neither mill-config.yaml nor wiki config exists ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_hub = Path(tmp_str)
            raised = False
            # Mock _paths.resolve_wiki_path to raise SystemExit (wiki lookup fails)
            import _paths
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit("wiki not found")):
                try:
                    _wiki.health_check(tmp_hub)
                except _wiki.WikiHealthError as whe:
                    raised = True
                    assert "mill-config.yaml" in str(whe), \
                        f"mill-config.yaml missing from message: {whe}"
            if not raised:
                raise AssertionError("health_check did not raise for missing configs")
        ok("health_check: raises when neither mill-config.yaml nor wiki config exists")
    except Exception as exc:
        fail("health_check: raises when neither mill-config.yaml nor wiki config exists", exc)

    # --- (i) health_check raises when hub dir missing ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            nonexistent = Path(tmp_str) / "nonexistent-hub"
            raised = False
            try:
                _wiki.health_check(nonexistent)
            except _wiki.WikiHealthError as whe:
                raised = True
                assert str(nonexistent) in str(whe), \
                    f"hub path missing from message: {whe}"
                assert whe.wiki_path == nonexistent, \
                    f"wiki_path attribute mismatch: {whe.wiki_path!r} != {nonexistent!r}"
            if not raised:
                raise AssertionError("health_check did not raise for missing hub dir")
        ok("health_check: raises when hub dir missing")
    except Exception as exc:
        fail("health_check: raises when hub dir missing", exc)

    # --- (j) read_junctions from mill-config.yaml ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_hub = Path(tmp_str)
            mill_cfg = {
                "junctions": {
                    ".wiki": "<WIKI_PATH>",
                    ".portals": "../portals"
                }
            }
            import yaml as yaml_module
            (tmp_hub / "mill-config.yaml").write_text(yaml_module.dump(mill_cfg), encoding="utf-8")
            result = _wiki.read_junctions(tmp_hub)
            assert ".wiki" in result and ".portals" in result, \
                f"expected junctions missing from result: {result}"
            assert result[".wiki"] == "<WIKI_PATH>", \
                f"junction value mismatch: {result['.wiki']}"
        ok("read_junctions: reads from mill-config.yaml")
    except Exception as exc:
        fail("read_junctions: reads from mill-config.yaml", exc)

    # --- (k) read_junctions falls back to wiki config ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_hub = Path(tmp_str)
            # No mill-config.yaml at hub; mock wiki path resolution
            wiki_cfg = {
                "junctions": {
                    ".wiki": "<WIKI_PATH>"
                }
            }
            import yaml as yaml_module
            with tempfile.TemporaryDirectory() as wiki_str:
                wiki_dir = Path(wiki_str)
                (wiki_dir / "config.yaml").write_text(yaml_module.dump(wiki_cfg), encoding="utf-8")
                with patch.object(_paths, "resolve_wiki_path", return_value=wiki_dir):
                    result = _wiki.read_junctions(tmp_hub)
                    assert ".wiki" in result, f"junction missing from fallback: {result}"
        ok("read_junctions: falls back to wiki config.yaml")
    except Exception as exc:
        fail("read_junctions: falls back to wiki config.yaml", exc)

    # --- (l) health_check passes when wiki config present (legacy) ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_hub = Path(tmp_str)
            # No mill-config.yaml; legacy wiki config exists
            with tempfile.TemporaryDirectory() as wiki_str:
                wiki_dir = Path(wiki_str)
                (wiki_dir / "config.yaml").write_text("repo: test\n", encoding="utf-8")
                with patch.object(_paths, "resolve_wiki_path", return_value=wiki_dir):
                    result = _wiki.health_check(tmp_hub)
                    assert result is None, f"health_check must return None, got {result!r}"
        ok("health_check: passes when wiki config.yaml present (legacy)")
    except Exception as exc:
        fail("health_check: passes when wiki config.yaml present (legacy)", exc)

    # --- (m) health_check raises when both sources missing ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_hub = Path(tmp_str)
            raised = False
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit("wiki not found")):
                try:
                    _wiki.health_check(tmp_hub)
                except _wiki.WikiHealthError:
                    raised = True
            assert raised, "health_check must raise when both configs missing"
        ok("health_check: raises when both mill-config.yaml and wiki config missing")
    except Exception as exc:
        fail("health_check: raises when both configs missing", exc)

    print(f"\n{passed} passed, {failed} failed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
