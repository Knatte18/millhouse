"""Unit tests for wiki daemon health-check: git-validity, cross-machine staleness, debounced pull,
hard/soft failure classification, and the liveness-only exemption.

Covers `_handle_health()` (wiki/_server.py) and `health_check()`/`_ensure_daemon()`'s reuse-probe
(wiki/_client.py).
Uses real tempfile git repos (bare origin + clone) for the git-validity and staleness cases,
and mocks for the debounce/soft-warning call-count assertions.

This file overrides `_test_helpers.py`'s WIKI_DAEMON_SKIP_GIT=1 default -- most of this suite is
specifically about real git behavior (verify_git_repo, pull), so it needs the daemon to actually
invoke git.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Real git behavior is the point of this test file -- override the suite-wide WIKI_DAEMON_SKIP_GIT=1 default before _test_helpers (and wiki._client) import, mirroring the documented override pattern (see test-spawn-core.py).
os.environ["WIKI_DAEMON_SKIP_GIT"] = ""

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _safe_rmtree  # noqa: E402
from wiki import _client as wiki, FIELD_OK, FIELD_OP, OP_HEALTH, PROTOCOL_VERSION  # noqa: E402
from _test_helpers import safe_temp_dir  # noqa: E402


def _run_git(args: list[str], cwd: Path) -> None:
    """Run a git command, raising AssertionError with captured output on failure."""
    result = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"


def _init_origin_and_clone(tmp: Path, name: str) -> tuple[Path, Path]:
    """Create a bare "origin" repo seeded with one commit, plus a real clone of it.

    Returns (origin_path, local_clone_path).
    The clone is a full working checkout with user.email/user.name configured, ready for git pull.
    """
    origin = tmp / f"{name}-origin.git"
    local = tmp / f"{name}-local"

    _run_git(["git", "init", "--bare", "-b", "main", str(origin)], tmp)

    # Seed the bare origin with an initial commit via a throwaway clone -- a bare repo has no working tree to commit into directly.
    seed = tmp / f"{name}-seed"
    _run_git(["git", "clone", str(origin), str(seed)], tmp)
    _run_git(["git", "-C", str(seed), "config", "user.email", "test@test.com"], tmp)
    _run_git(["git", "-C", str(seed), "config", "user.name", "Test"], tmp)
    (seed / "tasks.json").write_text('{"_default": {}}', encoding="utf-8")
    _run_git(["git", "-C", str(seed), "add", "tasks.json"], tmp)
    _run_git(["git", "-C", str(seed), "commit", "-m", "init"], tmp)
    _run_git(["git", "-C", str(seed), "push", "origin", "main"], tmp)

    _run_git(["git", "clone", str(origin), str(local)], tmp)
    _run_git(["git", "-C", str(local), "config", "user.email", "test@test.com"], tmp)
    _run_git(["git", "-C", str(local), "config", "user.name", "Test"], tmp)

    return origin, local


def _advance_origin(origin: Path, tmp: Path, name: str, filename: str, content: str) -> None:
    """Push one new commit to the bare "origin" repo via a throwaway pusher clone."""
    pusher = tmp / f"{name}-pusher"
    _run_git(["git", "clone", str(origin), str(pusher)], tmp)
    _run_git(["git", "-C", str(pusher), "config", "user.email", "test@test.com"], tmp)
    _run_git(["git", "-C", str(pusher), "config", "user.name", "Test"], tmp)
    (pusher / filename).write_text(content, encoding="utf-8")
    _run_git(["git", "-C", str(pusher), "add", filename], tmp)
    _run_git(["git", "-C", str(pusher), "commit", "-m", f"advance {filename}"], tmp)
    _run_git(["git", "-C", str(pusher), "push", "origin", "main"], tmp)


def main() -> int:
    passed = 0
    failed = 0

    def ok(name: str) -> None:
        nonlocal passed
        passed += 1
        print(f"PASS: {name}")

    def fail(name: str, exc: Exception) -> None:
        nonlocal failed
        failed += 1
        print(f"FAIL: {name}: {exc}", file=sys.stderr)

    # --- (a) wiki dir with no .git at all -> health_check() returns False, logs reason ---
    try:
        with safe_temp_dir() as tmp:
            wiki_path = tmp / "no-git-wiki"
            wiki_path.mkdir(parents=True, exist_ok=True)
            wiki.use_inprocess(wiki_path)

            fake_stderr = io.StringIO()
            with patch("sys.stderr", fake_stderr):
                result = wiki.health_check(wiki_path)

            assert result is False, f"expected False for a non-git wiki dir, got {result}"
            stderr_text = fake_stderr.getvalue()
            assert "[wiki] health check failed:" in stderr_text, \
                f"expected failure reason on stderr, got: {stderr_text!r}"
            ok("no .git at all -> health_check() returns False and logs the reason")
    except Exception as exc:
        fail("no .git at all -> health_check() returns False and logs the reason", exc)

    # --- (b) local clone behind origin by one commit -> health_check() fast-forwards ---
    try:
        with safe_temp_dir() as tmp:
            origin, local = _init_origin_and_clone(tmp, "ff")
            # Register before advancing origin: use_inprocess()'s own _ensure_gitignore() commits+pushes a .gitignore -- doing that while local and origin are still in sync keeps it a clean fast-forward push instead of a rebase that would silently resync local ahead of the staleness we're about to create.
            wiki.use_inprocess(local)
            _advance_origin(origin, tmp, "ff", "new.md", "new content\n")
            result = wiki.health_check(local)
            assert result is True, f"expected True after a clean fast-forward, got {result}"

            origin_tip = subprocess.run(
                ["git", "-C", str(origin), "rev-parse", "main"],
                capture_output=True, text=True,
            ).stdout.strip()
            local_head = subprocess.run(
                ["git", "-C", str(local), "rev-parse", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()
            assert local_head == origin_tip, \
                f"local HEAD {local_head!r} should match origin tip {origin_tip!r} after health_check()"
            ok("local clone behind origin -> health_check() fast-forwards it")
    except Exception as exc:
        fail("local clone behind origin -> health_check() fast-forwards it", exc)

    # --- (c) two health_check() calls within the TTL window trigger only one pull() ---
    try:
        with safe_temp_dir() as tmp:
            _origin, local = _init_origin_and_clone(tmp, "debounce")
            wiki.use_inprocess(local)

            # Patched onto wiki._server.pull specifically: _server.py does "from wiki._sync import pull", binding a local name in its own module namespace, so only patching that already-bound reference actually intercepts the call inside _handle_health.
            with patch("wiki._server.pull", return_value=False) as mock_pull:
                first = wiki.health_check(local)
                second = wiki.health_check(local)

            assert first is True and second is True, \
                f"both calls should report healthy, got {first!r}, {second!r}"
            assert mock_pull.call_count == 1, \
                f"expected exactly one pull() within the TTL window, got {mock_pull.call_count}"
            ok("two health_check() calls within TTL window debounce to one pull()")
    except Exception as exc:
        fail("two health_check() calls within TTL window debounce to one pull()", exc)

    # --- (d) diverged local wiki -> health_check() returns False (hard failure) ---
    try:
        with safe_temp_dir() as tmp:
            origin, local = _init_origin_and_clone(tmp, "diverged")
            # Same registration-before-divergence ordering as (b): register while still in sync so use_inprocess()'s own gitignore commit doesn't get auto-resolved via commit_push's rebase retry, which would silently erase the divergence we're about to set up.
            wiki.use_inprocess(local)
            _advance_origin(origin, tmp, "diverged", "origin-only.md", "origin content\n")
            (local / "local-only.md").write_text("local content\n", encoding="utf-8")
            _run_git(["git", "-C", str(local), "add", "local-only.md"], tmp)
            _run_git(["git", "-C", str(local), "commit", "-m", "local only"], tmp)

            fake_stderr = io.StringIO()
            with patch("sys.stderr", fake_stderr):
                result = wiki.health_check(local)

            assert result is False, f"expected False for a diverged local wiki, got {result}"
            assert "[wiki] health check failed:" in fake_stderr.getvalue(), \
                f"expected failure reason on stderr, got: {fake_stderr.getvalue()!r}"
            ok("diverged local wiki -> health_check() returns False (hard failure)")
    except Exception as exc:
        fail("diverged local wiki -> health_check() returns False (hard failure)", exc)

    # --- (e) network-timeout pull() failure -> health_check() still returns True (soft warning) ---
    try:
        with safe_temp_dir() as tmp:
            _origin, local = _init_origin_and_clone(tmp, "timeout")
            wiki.use_inprocess(local)

            server = wiki._inprocess_server(local)
            assert server is not None, "expected an in-process server to be registered"
            last_pull_before = server._last_pull

            timeout_error = wiki.WikiPushError(
                "git command timed out after 30s: git -C <path> pull --ff-only -- "
                "the remote may be unreachable or waiting on credentials"
            )
            # Same patch target as (c): the already-bound "pull" name inside wiki._server, not wiki._sync.pull.
            with patch("wiki._server.pull", side_effect=timeout_error):
                result = wiki.health_check(local)

            assert result is True, f"a network-timeout pull() failure should be a soft warning, got {result}"
            assert server._last_pull == last_pull_before, \
                "a failed pull attempt must not update _last_pull (so the next check retries)"
            ok("network-timeout pull() failure -> health_check() still returns True (soft warning)")
    except Exception as exc:
        fail("network-timeout pull() failure -> health_check() still returns True (soft warning)", exc)

    # --- (f1) liveness-only probe against a no-.git wiki skips verify_git_repo/pull entirely ---
    try:
        with safe_temp_dir() as tmp:
            wiki_path = tmp / "liveness-wiki"
            wiki_path.mkdir(parents=True, exist_ok=True)
            wiki.use_inprocess(wiki_path)
            server = wiki._inprocess_server(wiki_path)

            with patch("wiki._server.verify_git_repo") as mock_verify, \
                 patch("wiki._server.pull") as mock_pull:
                resp = server.handle_request({FIELD_OP: OP_HEALTH, "payload": {"liveness_only": True}})

            assert resp == {FIELD_OK: True}, f"liveness-only probe should report healthy, got {resp}"
            assert mock_verify.call_count == 0, \
                f"liveness-only probe must not call verify_git_repo, called {mock_verify.call_count} times"
            assert mock_pull.call_count == 0, \
                f"liveness-only probe must not call pull, called {mock_pull.call_count} times"
            ok("liveness-only probe against a no-.git wiki skips verify_git_repo/pull entirely")
    except Exception as exc:
        fail("liveness-only probe against a no-.git wiki skips verify_git_repo/pull entirely", exc)

    # --- (f2) _ensure_daemon's reuse-probe payload is tagged liveness_only=True ---
    try:
        tmp = Path(tempfile.mkdtemp())
        try:
            wiki_path = tmp / "reuse-probe-wiki"
            wiki_path.mkdir(parents=True, exist_ok=True)

            state_file = wiki_path / ".wiki-daemon.json"
            state = {
                "protocol_version": PROTOCOL_VERSION,
                "pid": os.getpid() + 999999,
                "host": "127.0.0.1",
                "port": 9999,
                "token": "test-token",
            }
            state_file.write_text(json.dumps(state), encoding="utf-8")

            with patch("wiki._client.socket.create_connection") as mock_create_conn, \
                 patch("wiki._client._connect_send_recv") as mock_send_recv, \
                 patch("wiki._client._spawn_server") as mock_spawn:
                mock_create_conn.return_value = MagicMock(close=MagicMock())
                mock_send_recv.return_value = {FIELD_OK: True}

                wiki._ensure_daemon(wiki_path)

                assert mock_send_recv.called, "expected _connect_send_recv to be called for the reuse probe"
                assert mock_spawn.call_count == 0, "a healthy reuse probe should not trigger a respawn"
                call_args = mock_send_recv.call_args.args
                sent_msg = call_args[2]
                assert sent_msg.get("payload") == {"liveness_only": True}, \
                    f"reuse-probe payload should be tagged liveness_only=True, got: {sent_msg.get('payload')!r}"
            ok("_ensure_daemon's reuse-probe payload is tagged liveness_only=True")
        finally:
            _safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)
    except Exception as exc:
        fail("_ensure_daemon's reuse-probe payload is tagged liveness_only=True", exc)

    print("", file=sys.stderr)
    if failed:
        print(f"FAIL -- {failed} of {passed + failed}", file=sys.stderr)
        return 1
    print(f"PASS -- all {passed} tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
