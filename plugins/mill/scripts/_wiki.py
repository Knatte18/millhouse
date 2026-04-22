"""
Wiki-clone advisory lock and commit/push helpers.

The wiki clone is shared by every worktree on a developer's machine
(``.millhouse/wiki`` is a junction to a single checkout). Two writers
racing to append to ``Home.md`` or to ``active/<slug>/status.md`` would
produce a merge conflict at push time; this module serialises writers
via an advisory lockfile at ``<wiki>/.mill-lock``.

Locking model:
    * Acquisition is atomic via ``O_CREAT | O_EXCL``. No filesystem
      flock/fcntl — the wiki may live on a network or OneDrive-backed
      path where range locks misbehave.
    * The lockfile contains the holder's slug and an ISO-8601 UTC
      timestamp. Locks older than 5 minutes are considered stale and
      overwritten without waiting. That duration is the longest we've
      ever observed a legitimate wiki write taking; any older lock is a
      crash we need to step over.
    * ``acquire_lock`` polls every 500 ms up to ``timeout_seconds`` and
      raises ``LockBusy`` on timeout with the current holder + age.

Commit/push uses a single rebase retry on non-fast-forward rejection.
If the rebase itself fails (e.g. a genuine conflict), we abort the
rebase and raise ``WikiPushError`` — unlike v1, there is no automatic
conflict resolution. Auto-resolve code lived in v1's
``auto_resolve_merge`` and was coupled to ``regenerate_sidebar``;
resurrecting it is out of scope for the M1.x layer.

Public API:
    acquire_lock(wiki_path, slug, timeout_seconds=30)
        Atomically acquire the wiki advisory lock; raise LockBusy if
        held for longer than ``timeout_seconds``.
    release_lock(wiki_path)
        Idempotently remove the wiki advisory lock.
    sync_pull(wiki_path)
        git pull --ff-only — refresh wiki before reading Home.md.
    write_commit_push(wiki_path, relative_paths, commit_msg)
        Stage, commit and push the named paths with one rebase retry.

Exceptions:
    LockBusy        — raised by ``acquire_lock`` on timeout. Carries
                      ``holder`` (slug) and ``age_seconds`` for diagnostics.
    WikiPushError   — raised by ``write_commit_push`` on any
                      unrecoverable git failure (add/commit/rebase/push).
"""
from __future__ import annotations

import datetime
import os
import sys
import time
from pathlib import Path

import yaml

import _subprocess_util

_STALE_SECONDS = 5 * 60  # 5 minutes

_JUNCTION_DEFAULTS: dict[str, str] = {
    ".millhouse/wiki": "<WIKI_PATH>",
    ".active": "<WIKI_PATH>/active/<SLUG>/",
}


def read_junctions(wiki_root: Path) -> dict[str, str]:
    """Read the ``junctions:`` block from ``<wiki_root>/config.yaml``.

    Returns an ordered dict mapping junction-path → unresolved target
    template. Tokens in the target are NOT substituted here — callers pass
    the raw template through ``_junction.resolve_target`` with the token
    map appropriate to their scope (mill-setup lacks ``<SLUG>``, mill-spawn
    has it).

    Missing config file or missing ``junctions:`` block falls back to
    ``_JUNCTION_DEFAULTS``.
    """
    cfg_path = wiki_root / "config.yaml"
    if not cfg_path.exists():
        return dict(_JUNCTION_DEFAULTS)
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    raw = cfg.get("junctions")
    if not raw:
        return dict(_JUNCTION_DEFAULTS)
    return {str(k): str(v) for k, v in raw.items()}


class WikiPushError(RuntimeError):
    """
    Raised by ``write_commit_push`` on any unrecoverable git failure.

    Covers ``git add`` errors, commit errors that are not "nothing to
    commit", rebase failures during the non-fast-forward retry, and push
    failures that are not rebase-recoverable. The message includes the
    underlying stderr for diagnostics.
    """


class LockBusy(RuntimeError):
    """
    Raised by ``acquire_lock`` on timeout.

    The exception carries the current holder's slug and the approximate
    age of the lock in seconds so that callers (and mill-status) can
    show a useful diagnostic instead of a bare "lock held".

    Instance variables:
        holder: Slug written into the lockfile by the blocking writer.
        age_seconds: Seconds since the lockfile's ISO timestamp.
    """

    def __init__(self, holder: str, age_seconds: int) -> None:
        self.holder = holder
        self.age_seconds = age_seconds
        super().__init__(
            f"Wiki lock held by {holder!r} (age {age_seconds}s); timed out waiting"
        )


def acquire_lock(wiki_path: Path, slug: str, timeout_seconds: int = 30) -> None:
    """
    Acquire the advisory lockfile at ``<wiki_path>/.mill-lock`` atomically.

    The lockfile is created via ``os.open`` with ``O_CREAT | O_EXCL`` so
    two concurrent callers cannot both win. On contention the function
    polls every 500 ms and inspects the existing lock: if its timestamp
    is older than 5 minutes the lock is treated as stale (the previous
    holder likely crashed) and overwritten without waiting.

    Args:
        wiki_path: Directory containing the wiki clone. The lockfile is
            placed at ``wiki_path / '.mill-lock'``.
        slug: Identifier written into the lockfile so a blocked caller
            can report who is holding it.
        timeout_seconds: Maximum wall time to wait for a non-stale lock
            before raising ``LockBusy``. Default 30 seconds.

    Raises:
        LockBusy: A non-stale lock held by a different writer was still
            present when ``timeout_seconds`` elapsed. The exception
            carries the current holder's slug and approximate age.
    """
    lock_path = wiki_path / ".mill-lock"
    deadline = time.monotonic() + timeout_seconds

    while True:
        ts_now = datetime.datetime.now(datetime.timezone.utc)
        ts_str = ts_now.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(f"{slug}\n{ts_str}\n")
            print(f"[wiki] acquire_lock: acquired by {slug!r}", file=sys.stderr)
            return
        except FileExistsError:
            pass

        try:
            content = lock_path.read_text(encoding="utf-8")
            lines = content.strip().splitlines()
            holder = lines[0] if lines else "<unknown>"
            lock_ts_str = lines[1] if len(lines) > 1 else ""
            try:
                lock_ts = datetime.datetime.strptime(
                    lock_ts_str, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=datetime.timezone.utc)
                age_seconds = int((ts_now - lock_ts).total_seconds())
            except ValueError:
                age_seconds = _STALE_SECONDS + 1
                holder = "<unknown>"

            if age_seconds > _STALE_SECONDS:
                print(f"[wiki] acquire_lock: overwriting stale lock (age={age_seconds}s)", file=sys.stderr)
                lock_path.write_text(f"{slug}\n{ts_str}\n", encoding="utf-8")
                return

            if time.monotonic() >= deadline:
                raise LockBusy(holder, age_seconds)
        except (OSError, IndexError):
            pass

        time.sleep(0.5)


def sync_pull(wiki_path: Path) -> None:
    """
    Fetch + fast-forward the wiki clone so local state matches origin.

    Runs ``git pull --ff-only``. Non-fast-forward (i.e. the wiki clone has
    local commits not yet on origin) raises ``WikiPushError`` — this function
    never performs a merge or rebase. Callers that want merge semantics go
    through ``write_commit_push``.

    Called by mill-spawn before reading Home.md so task-pick decisions run
    against the latest task state.

    Args:
        wiki_path: Directory containing the wiki clone.

    Raises:
        WikiPushError: ``git pull --ff-only`` failed (network error,
            non-fast-forward state, etc).
    """
    result = _subprocess_util.run(
        ["git", "-C", str(wiki_path), "pull", "--ff-only"]
    )
    if result.returncode != 0:
        raise WikiPushError(f"git pull --ff-only failed: {result.stderr.strip()!r}")
    print(f"[wiki] sync_pull: fast-forwarded {wiki_path}", file=sys.stderr)


def release_lock(wiki_path: Path) -> None:
    """
    Delete the advisory lockfile at ``<wiki_path>/.mill-lock``.

    Idempotent: missing lockfile is a no-op, because cleanup paths call
    this unconditionally regardless of whether a prior ``acquire_lock``
    actually succeeded.

    Args:
        wiki_path: Directory containing the wiki clone.
    """
    lock_path = wiki_path / ".mill-lock"
    if lock_path.exists():
        lock_path.unlink()
        print("[wiki] release_lock: released", file=sys.stderr)


def write_commit_push(
    wiki_path: Path,
    relative_paths: list[str],
    commit_msg: str,
) -> None:
    """
    Stage the named paths, commit with ``commit_msg``, and push.

    The sequence is ``git add -- <paths>`` → ``git commit -m <msg>`` →
    ``git push``. On a non-fast-forward rejection we run
    ``git pull --rebase`` and retry the push exactly once. If the rebase
    fails (genuine conflict), we run ``git rebase --abort`` and raise
    ``WikiPushError`` — v2 does not attempt automatic conflict resolution.

    A commit that would produce "nothing to commit" is treated as success
    and returns without pushing; this lets callers idempotently re-run a
    write without special-casing it.

    Args:
        wiki_path: Directory containing the wiki clone.
        relative_paths: Paths (relative to ``wiki_path``) to stage. Passed
            literally after ``git add --`` to avoid option parsing on
            paths that start with a dash.
        commit_msg: Commit message.

    Raises:
        WikiPushError: ``git add``, ``git commit``, ``git rebase``, or
            ``git push`` failed in a way that the one-shot rebase retry
            could not recover from.
    """
    print(f"[wiki] write_commit_push: wiki={wiki_path} paths={relative_paths!r}", file=sys.stderr)

    add = _subprocess_util.run(
        ["git", "-C", str(wiki_path), "add", "--"] + list(relative_paths)
    )
    if add.returncode != 0:
        raise WikiPushError(f"git add failed: {add.stderr.strip()!r}")

    commit = _subprocess_util.run(
        ["git", "-C", str(wiki_path), "commit", "-m", commit_msg]
    )
    if commit.returncode != 0:
        combined = (commit.stdout or "") + (commit.stderr or "")
        if "nothing to commit" in combined:
            print("[wiki] write_commit_push: nothing to commit, skip push", file=sys.stderr)
            return
        raise WikiPushError(f"git commit failed: {commit.stderr.strip()!r}")

    for attempt in range(2):
        push = _subprocess_util.run(["git", "-C", str(wiki_path), "push"])
        if push.returncode == 0:
            print("[wiki] write_commit_push: pushed successfully", file=sys.stderr)
            return

        if "non-fast-forward" in push.stderr or "rejected" in push.stderr:
            print(f"[wiki] write_commit_push: push rejected on attempt {attempt + 1}, rebasing", file=sys.stderr)
            rebase = _subprocess_util.run(
                ["git", "-C", str(wiki_path), "pull", "--rebase"]
            )
            if rebase.returncode == 0:
                continue
            _subprocess_util.run(["git", "-C", str(wiki_path), "rebase", "--abort"])
            raise WikiPushError(f"git pull --rebase failed: {rebase.stderr.strip()!r}")

        raise WikiPushError(f"git push failed: {push.stderr.strip()!r}")

    raise WikiPushError("push still failing after rebase retry")


if __name__ == "__main__":
    print("Usage: import _wiki; _wiki.acquire_lock(wiki_path, slug); _wiki.release_lock(wiki_path); _wiki.write_commit_push(wiki_path, paths, msg)", file=sys.stderr)
    sys.exit(0)
