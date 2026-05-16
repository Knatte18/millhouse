"""
Wiki-clone advisory lock and commit/push helpers.

The wiki clone is shared by every worktree on a developer's machine
(``.millhouse/wiki`` is a junction to a single checkout). Two writers
racing to append to ``Home.md`` would produce a merge conflict at push
time; this module serialises writers via an advisory lockfile at
``<wiki>/.mill-lock``.

Locking model:
    * Acquisition is atomic via ``O_CREAT | O_EXCL``. No filesystem
      flock/fcntl — the wiki may live on a network or OneDrive-backed
      path where range locks misbehave.
    * The lockfile contains the holder's slug and an ISO-8601 UTC
      timestamp. Locks older than 5 minutes are considered stale and
      overwritten without waiting. That duration is the longest we've
      ever observed a legitimate wiki write taking; any older lock is a
      crash we need to step over.
    * ``_acquire`` polls every 500 ms up to ``timeout_seconds`` and
      raises ``LockBusy`` on timeout with the current holder + age.
    * Stale-self-lock: if the existing lockfile's holder slug equals
      the caller's slug, the lock is reclaimed immediately (overwrite +
      warn) instead of waiting for the timeout.
    * Module-level ``_held_locks`` counter enables re-entrancy: nested
      ``wiki_lock`` calls on the same path do not deadlock.

Commit/push uses a single rebase retry on non-fast-forward rejection.
If the rebase itself fails (e.g. a genuine conflict), we abort the
rebase and raise ``WikiPushError`` — unlike v1, there is no automatic
conflict resolution. Auto-resolve code lived in v1's
``auto_resolve_merge`` and was coupled to ``regenerate_sidebar``;
resurrecting it is out of scope for the M1.x layer.

Public API:
    wiki_lock(wiki_path, slug)
        Context manager. Acquires the wiki advisory lock for the
        duration of the block. Re-entrant: nested calls on the same
        path skip the inner acquire/release. Use for multi-op windows.
    sync_pull(wiki_path, *, slug)
        git pull --ff-only — refresh wiki before reading Home.md.
        Acquires/releases the wiki lock internally; no-op acquire if
        already held via ``wiki_lock``.
    health_check(wiki_path)
        Verify the wiki clone is present and contains config.yaml.
        Raises WikiHealthError on failure; returns None on success.
    write_commit_push(wiki_path, relative_paths, commit_msg, *, slug)
        Stage, commit and push the named paths with one rebase retry.
        Acquires/releases the wiki lock internally; no-op acquire if
        already held via ``wiki_lock``.
    clone_or_init(url, branch, dest)
        Clone, init-orphan, or pull an existing wiki clone at dest.
        Returns a status dict with "action" and "branch_existed_on_remote".
        Does not acquire the wiki lock (dest is not yet a live wiki).

Exceptions:
    LockBusy        — raised by ``_acquire`` on timeout. Carries
                      ``holder`` (slug) and ``age_seconds`` for
                      diagnostics.
    WikiPushError   — raised by ``write_commit_push`` and the pull path
                      of ``clone_or_init`` on any unrecoverable git
                      failure (add/commit/rebase/push/pull).
    WikiSetupError  — raised by ``clone_or_init`` on unrecoverable
                      clone/init/mismatch failures (URL mismatch, branch
                      mismatch, dest-exists-but-not-git, ls-remote
                      failure, clone/init failure).
    WikiHealthError — raised by ``health_check`` when the wiki directory
                      does not exist or config.yaml is missing. Carries
                      the ``wiki_path`` attribute for diagnostics.
"""
from __future__ import annotations

import datetime
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import yaml

import _subprocess_util

_STALE_SECONDS = 5 * 60  # 5 minutes

_JUNCTION_DEFAULTS: dict[str, str] = {
    ".wiki": "<WIKI_PATH>",
}

_HARDLINK_DEFAULTS: dict[str, str] = {}  # no hardlinks unless configured


def read_junctions(hub_root: Path) -> dict[str, str]:
    """Read the ``junctions:`` block from ``<hub_root>/mill-config.yaml`` or legacy wiki ``config.yaml``.

    Returns an ordered dict mapping junction-path → unresolved target
    template. Tokens in the target are NOT substituted here — callers pass
    the raw template through ``_junction.resolve_target`` with the token
    map appropriate to their scope (mill-setup lacks ``<SLUG>``, mill-spawn
    has it).

    Precedence (first source wins):
    1. ``<hub_root>/mill-config.yaml`` if it exists.
    2. Legacy ``<wiki_root>/config.yaml`` (resolved via _paths.resolve_wiki_path).
    3. ``_JUNCTION_DEFAULTS`` fallback.
    """
    import _paths

    # Try hub mill-config.yaml first
    mill_cfg_path = hub_root / "mill-config.yaml"
    if mill_cfg_path.exists():
        cfg = yaml.safe_load(mill_cfg_path.read_text(encoding="utf-8")) or {}
        raw = cfg.get("junctions")
        if raw:
            return {str(k): str(v) for k, v in raw.items()}
        return dict(_JUNCTION_DEFAULTS)

    # Fall back to legacy wiki config.yaml
    try:
        wiki_root = _paths.resolve_wiki_path(hub_root)
    except SystemExit:
        wiki_root = None

    if wiki_root is not None:
        wiki_cfg_path = wiki_root / "config.yaml"
        if wiki_cfg_path.exists():
            cfg = yaml.safe_load(wiki_cfg_path.read_text(encoding="utf-8")) or {}
            raw = cfg.get("junctions")
            if raw:
                return {str(k): str(v) for k, v in raw.items()}

    return dict(_JUNCTION_DEFAULTS)


def read_hardlinks(hub_root: Path) -> dict[str, str]:
    """Read the ``hardlinks:`` block from ``<hub_root>/mill-config.yaml`` or legacy wiki ``config.yaml``.

    Returns an ordered dict mapping link-path → unresolved target template.
    Tokens in the target are NOT substituted here — callers pass the raw
    template through ``_junction.resolve_target`` with the appropriate token
    map.

    Precedence (first source wins):
    1. ``<hub_root>/mill-config.yaml`` if it exists.
    2. Legacy ``<wiki_root>/config.yaml`` (resolved via _paths.resolve_wiki_path).
    3. Empty dict (no hardlinks configured).

    Also returns an empty dict when the block is explicitly null (hardlinks: null),
    since yaml.safe_load yields None for an explicit-null and the falsy check
    collapses both cases. Callers (e.g. _setup.create_hub_links) must tolerate
    an empty result.
    """
    import _paths

    # Try hub mill-config.yaml first
    mill_cfg_path = hub_root / "mill-config.yaml"
    if mill_cfg_path.exists():
        cfg = yaml.safe_load(mill_cfg_path.read_text(encoding="utf-8")) or {}
        raw = cfg.get("hardlinks")
        if raw:
            return {str(k): str(v) for k, v in raw.items()}
        return dict(_HARDLINK_DEFAULTS)

    # Fall back to legacy wiki config.yaml
    try:
        wiki_root = _paths.resolve_wiki_path(hub_root)
    except SystemExit:
        wiki_root = None

    if wiki_root is not None:
        wiki_cfg_path = wiki_root / "config.yaml"
        if wiki_cfg_path.exists():
            cfg = yaml.safe_load(wiki_cfg_path.read_text(encoding="utf-8")) or {}
            raw = cfg.get("hardlinks")
            if raw:
                return {str(k): str(v) for k, v in raw.items()}

    return dict(_HARDLINK_DEFAULTS)


class WikiSetupError(Exception):
    """
    Raised by ``clone_or_init`` on any unrecoverable clone/init/mismatch failure.

    Covers URL mismatch, branch mismatch, dest-exists-but-not-git,
    ls-remote failure, clone/init failure, and remote-add/config failures.
    The message includes enough context for the caller (mill-setup Phase 2/3)
    to surface a clear user-facing error.
    """


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
    Raised by ``_acquire`` on timeout.

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


class WikiHealthError(Exception):
    """Raised by ``health_check`` when the wiki clone appears missing or corrupted.

    Instance variables:
        wiki_path: The ``Path`` that was checked, for use in caller error messages.
    """

    def __init__(self, wiki_path: Path, message: str) -> None:
        self.wiki_path = wiki_path
        super().__init__(message)


_held_locks: dict[Path, int] = {}


def _acquire(wiki_path: Path, slug: str, timeout_seconds: int = 30) -> None:
    lock_path = wiki_path / ".mill-lock"
    deadline = time.monotonic() + timeout_seconds

    while True:
        ts_now = datetime.datetime.now(datetime.timezone.utc)
        ts_str = ts_now.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(f"{slug}\n{ts_str}\n")
            print(f"[wiki] _acquire: acquired by {slug!r}", file=sys.stderr)
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

            if holder == slug:
                print(
                    f"[wiki] _acquire: reclaiming self-lock held by {slug!r} (age {age_seconds}s)",
                    file=sys.stderr,
                )
                lock_path.write_text(f"{slug}\n{ts_str}\n", encoding="utf-8")
                return

            if age_seconds > _STALE_SECONDS:
                print(f"[wiki] _acquire: overwriting stale lock (age={age_seconds}s)", file=sys.stderr)
                lock_path.write_text(f"{slug}\n{ts_str}\n", encoding="utf-8")
                return

            if time.monotonic() >= deadline:
                raise LockBusy(holder, age_seconds)
        except (OSError, IndexError):
            pass

        time.sleep(0.5)


def _release(wiki_path: Path) -> None:
    lock_path = wiki_path / ".mill-lock"
    if lock_path.exists():
        lock_path.unlink()
        print("[wiki] _release: released", file=sys.stderr)


@contextmanager
def wiki_lock(wiki_path: Path, slug: str):
    """Context manager that acquires and releases the wiki advisory lock.

    Re-entrant: nested calls on the same resolved wiki_path increment a
    counter and skip the inner acquire/release. The lock is only acquired
    on the first entry and released when the outermost block exits.
    """
    resolved = wiki_path.resolve()
    count = _held_locks.get(resolved, 0)
    if count == 0:
        _acquire(wiki_path, slug)
    _held_locks[resolved] = count + 1
    try:
        yield
    finally:
        _held_locks[resolved] -= 1
        if _held_locks[resolved] == 0:
            del _held_locks[resolved]
            _release(wiki_path)


def sync_pull(wiki_path: Path, *, slug: str) -> None:
    """
    Fetch + fast-forward the wiki clone so local state matches origin.

    Acquires the wiki advisory lock internally. When called inside a
    ``wiki_lock`` block the acquire is a no-op (re-entrancy counter).

    Runs ``git pull --ff-only``. Non-fast-forward raises ``WikiPushError``.

    Args:
        wiki_path: Directory containing the wiki clone.
        slug: Caller's slug; written into the lockfile for diagnostics.

    Raises:
        WikiPushError: ``git pull --ff-only`` failed (network error,
            non-fast-forward state, etc).
    """
    resolved = wiki_path.resolve()
    held = _held_locks.get(resolved, 0) > 0
    if not held:
        _acquire(wiki_path, slug)
    try:
        result = _subprocess_util.run(
            ["git", "-C", str(wiki_path), "pull", "--ff-only"]
        )
        if result.returncode != 0:
            raise WikiPushError(f"git pull --ff-only failed: {result.stderr.strip()!r}")
        print(f"[wiki] sync_pull: fast-forwarded {wiki_path}", file=sys.stderr)
    finally:
        if not held:
            _release(wiki_path)


def health_check(wiki_path: Path) -> None:
    """Verify the wiki clone is present and contains ``config.yaml``.

    A lightweight pre-flight check intended to be called at the start of
    each mill-go batch iteration and each holistic review round. Raises
    ``WikiHealthError`` so callers can catch and surface a clean error
    without parsing stderr or letting downstream code produce a confusing
    "Missing config" message.

    Args:
        wiki_path: Directory expected to contain the wiki clone.

    Returns:
        None on success.

    Raises:
        WikiHealthError: ``wiki_path`` does not exist, with message
            ``"wiki directory does not exist at <wiki_path>"``.
        WikiHealthError: ``wiki_path/config.yaml`` does not exist, with
            message ``"wiki/config.yaml missing at <wiki_path/config.yaml>"``.
    """
    if not wiki_path.exists():
        raise WikiHealthError(wiki_path, f"wiki directory does not exist at {wiki_path}")
    if not (wiki_path / "config.yaml").exists():
        raise WikiHealthError(
            wiki_path,
            f"wiki/config.yaml missing at {wiki_path / 'config.yaml'}",
        )


def write_commit_push(
    wiki_path: Path,
    relative_paths: list[str],
    commit_msg: str,
    *,
    slug: str,
) -> None:
    """
    Stage the named paths, commit with ``commit_msg``, and push.

    Acquires the wiki advisory lock internally. When called inside a
    ``wiki_lock`` block the acquire is a no-op (re-entrancy counter).

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
        slug: Caller's slug; written into the lockfile for diagnostics.

    Raises:
        WikiPushError: ``git add``, ``git commit``, ``git rebase``, or
            ``git push`` failed in a way that the one-shot rebase retry
            could not recover from.
    """
    resolved = wiki_path.resolve()
    held = _held_locks.get(resolved, 0) > 0
    if not held:
        _acquire(wiki_path, slug)
    try:
        _write_commit_push_body(wiki_path, relative_paths, commit_msg)
    finally:
        if not held:
            _release(wiki_path)


def _write_commit_push_body(
    wiki_path: Path,
    relative_paths: list[str],
    commit_msg: str,
) -> None:
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


def clone_or_init(url: str, branch: str | None, dest: Path) -> dict:
    """Clone, init-orphan, or pull an existing wiki clone at dest.

    Four code paths:

    Path A — dest exists and dest/.git exists:
        Verifies origin URL matches url; if branch is not None, verifies
        current branch matches branch; then runs git pull --ff-only.
        Returns {"action": "pulled", "branch_existed_on_remote": None}.

    Path B — dest exists but dest/.git is missing:
        Raises WikiSetupError (dest is not a git repo).

    Path C — dest does not exist, branch is None:
        Runs git clone <url> <dest> (remote HEAD).
        Returns {"action": "cloned", "branch_existed_on_remote": None}.

    Path D — dest does not exist, branch is not None:
        Checks remote branch existence via git ls-remote --heads.
        Branch exists  → git clone -b <branch> --single-branch <url> <dest>.
                         Returns {"action": "cloned", "branch_existed_on_remote": True}.
        Branch missing → git init <dest>, git remote add origin <url>,
                         git checkout --orphan <branch>, git config
                         branch.<branch>.remote/merge so the first
                         write_commit_push pushes upstream-cleanly.
                         Returns {"action": "initialized", "branch_existed_on_remote": False}.

    This helper does NOT log or print — the caller shapes all user-facing messages.
    All subprocess calls go through _subprocess_util.run; argv lists are explicit.

    Args:
        url:    Remote wiki URL.
        branch: Branch name to pin, or None to use the remote default.
        dest:   Filesystem path where the wiki clone should live.

    Returns:
        dict with keys:
          "action": "cloned" | "pulled" | "initialized"
          "branch_existed_on_remote": True | False | None

    Raises:
        WikiSetupError: Unrecoverable clone/init/mismatch failure.
        WikiPushError:  git pull --ff-only failed on an existing repo (Path A).
    """
    if dest.exists():
        if not (dest / ".git").exists():
            raise WikiSetupError(
                f"{dest} exists but is not a git repository; move or remove it and re-run"
            )
        # Path A — existing git repo
        get_url = _subprocess_util.run(
            ["git", "-C", str(dest), "remote", "get-url", "origin"]
        )
        if get_url.returncode != 0:
            raise WikiSetupError(
                f"git -C {dest} remote get-url origin failed: {get_url.stderr}"
            )
        actual_url = get_url.stdout.strip()
        if actual_url != url:
            raise WikiSetupError(
                f"wiki at {dest} has origin {actual_url!r}, expected {url!r};"
                " remove or fix the wiki dir manually"
            )
        if branch is not None:
            show = _subprocess_util.run(
                ["git", "-C", str(dest), "branch", "--show-current"]
            )
            if show.returncode != 0:
                raise WikiSetupError(
                    f"git -C {dest} branch --show-current failed: {show.stderr}"
                )
            actual_branch = show.stdout.strip()
            if actual_branch != branch:
                raise WikiSetupError(
                    f"wiki at {dest} is on branch {actual_branch!r}, expected {branch!r};"
                    " remove or fix the wiki dir manually"
                )
        pull = _subprocess_util.run(
            ["git", "-C", str(dest), "pull", "--ff-only"]
        )
        if pull.returncode != 0:
            raise WikiPushError(f"git pull --ff-only failed: {pull.stderr}")
        return {"action": "pulled", "branch_existed_on_remote": None}

    # dest does not exist
    if branch is None:
        # Path C — clone without branch
        result = _subprocess_util.run(["git", "clone", url, str(dest)])
        if result.returncode != 0:
            raise WikiSetupError(
                f"git clone {url} {dest} failed: {result.stderr}"
            )
        return {"action": "cloned", "branch_existed_on_remote": None}

    # Path D — dest missing, branch specified
    ls = _subprocess_util.run(["git", "ls-remote", "--heads", url, branch])
    if ls.returncode != 0:
        raise WikiSetupError(
            f"git ls-remote --heads {url} {branch} failed: {ls.stderr}"
        )
    if ls.stdout.strip():
        # branch exists on remote
        result = _subprocess_util.run(
            ["git", "clone", "-b", branch, "--single-branch", url, str(dest)]
        )
        if result.returncode != 0:
            raise WikiSetupError(
                f"git clone -b {branch} --single-branch {url} {dest} failed: {result.stderr}"
            )
        return {"action": "cloned", "branch_existed_on_remote": True}

    # branch missing — init orphan
    init = _subprocess_util.run(["git", "init", str(dest)])
    if init.returncode != 0:
        raise WikiSetupError(f"git init {dest} failed: {init.stderr}")

    remote = _subprocess_util.run(
        ["git", "-C", str(dest), "remote", "add", "origin", url]
    )
    if remote.returncode != 0:
        raise WikiSetupError(
            f"git -C {dest} remote add origin {url} failed: {remote.stderr}"
        )

    orphan = _subprocess_util.run(
        ["git", "-C", str(dest), "checkout", "--orphan", branch]
    )
    if orphan.returncode != 0:
        raise WikiSetupError(
            f"git -C {dest} checkout --orphan {branch} failed: {orphan.stderr}"
        )

    cfg_remote = _subprocess_util.run(
        ["git", "-C", str(dest), "config", f"branch.{branch}.remote", "origin"]
    )
    if cfg_remote.returncode != 0:
        raise WikiSetupError(
            f"git -C {dest} config branch.{branch}.remote failed: {cfg_remote.stderr}"
        )

    cfg_merge = _subprocess_util.run(
        ["git", "-C", str(dest), "config", f"branch.{branch}.merge", f"refs/heads/{branch}"]
    )
    if cfg_merge.returncode != 0:
        raise WikiSetupError(
            f"git -C {dest} config branch.{branch}.merge failed: {cfg_merge.stderr}"
        )

    return {"action": "initialized", "branch_existed_on_remote": False}
