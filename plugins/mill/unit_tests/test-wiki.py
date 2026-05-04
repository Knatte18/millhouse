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

    print(f"\n{passed} passed, {failed} failed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
