"""
mill-go builder lock — per-worktree mutex.

The design rule for mill-v2 is exactly one active task per worktree. The
orchestrator still needs a runtime check: the user could re-invoke
``/mill-go`` from a second Claude tab while the first is mid-batch, or
they could restart mill-go after a crash and we need to tell a stale
lock from a live one.

Lock file: ``<mill_dir>/builder.lock``. Contents: a fenced-yaml block
with ``timestamp: <UTC iso>`` and ``slug: <task-slug>``. We do not
include a PID: on Windows there is no reliable cross-process check that
generalises, and the 5-minute stale window makes PID-tracking
unnecessary for our workload (a single implementer run plus a single
reviewer run fits comfortably).

Stale detection: a lock whose ``timestamp`` is older than
``STALE_WINDOW_SEC`` is considered orphaned and may be overwritten.
Callers use :func:`acquire` which does this check automatically.

Public API:
    LockBusy     — raised when the lock is held by a non-stale holder
    acquire(...) — take the lock or raise
    release(...) — remove the lock (tolerates already-gone)
    read(...)    — inspect who currently holds the lock
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

LOCK_FILENAME = "builder.lock"
STALE_WINDOW_SEC = 5 * 60


class LockBusy(Exception):
    """Raised by :func:`acquire` when a non-stale lock is already held."""


@dataclass(frozen=True)
class LockInfo:
    """In-memory view of a lock file's contents."""

    slug: str
    timestamp: str  # ISO-8601 UTC, ``Z``-suffixed.


def _lock_path(mill_dir: Path) -> Path:
    return mill_dir / LOCK_FILENAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(ts: str) -> datetime:
    """Parse the ``Z``-suffixed ISO timestamp the lock writer produces.

    Raising ``ValueError`` here is fine — callers treat a malformed lock
    as "ignore the timestamp, prefer a fresh acquire" via the stale path.
    """
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def read(mill_dir: Path) -> LockInfo | None:
    """Return the current holder, or ``None`` if the lock is free.

    Malformed contents → ``None``. We deliberately never raise from
    ``read()``: the caller uses it to decide whether to complain or
    proceed, and a corrupted lock is functionally the same as a missing
    one for that decision.
    """
    lp = _lock_path(mill_dir)
    if not lp.exists():
        return None
    try:
        text = lp.read_text(encoding="utf-8")
    except OSError:
        return None

    # Hand-parse two ``key: value`` rows. Avoiding yaml.safe_load here is
    # deliberate: PyYAML auto-converts an ISO timestamp to a datetime
    # object, which breaks the `str`-typed LockInfo contract and forces
    # a normalisation layer the lock does not need.
    slug: str | None = None
    ts: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped in ("```yaml", "```"):
            continue
        if stripped.startswith("slug:"):
            slug = stripped[len("slug:"):].strip().strip('"').strip("'")
        elif stripped.startswith("timestamp:"):
            ts = stripped[len("timestamp:"):].strip().strip('"').strip("'")
    if not slug or not ts:
        return None
    return LockInfo(slug=slug, timestamp=ts)


def _is_stale(info: LockInfo) -> bool:
    """Return True when the lock's timestamp is outside the stale window.

    A malformed timestamp counts as stale — a lock we can't dateparse
    is safer to reclaim than to leave holding the worktree hostage.
    """
    try:
        ts = _parse_iso(info.timestamp)
    except ValueError:
        return True
    age = (datetime.now(timezone.utc) - ts).total_seconds()
    return age > STALE_WINDOW_SEC


def acquire(mill_dir: Path, slug: str) -> LockInfo:
    """Take the builder lock for ``slug`` or raise ``LockBusy``.

    Behaviour:
    - No existing lock → write a fresh one and return the new info.
    - Existing lock held by the same ``slug`` → refresh timestamp and
      return. Idempotent by design: a crashed mill-go restarting against
      the same task should not have to manually clear its own lock.
    - Existing lock held by a different slug → check staleness. Stale →
      overwrite. Fresh → raise ``LockBusy`` with the existing holder's
      slug and timestamp in the message.

    The lock file is written atomically via ``Path.write_text`` which on
    Windows/Python implements a create-truncate-write that is adequate
    for this single-writer, single-reader scenario.
    """
    mill_dir.mkdir(parents=True, exist_ok=True)
    existing = read(mill_dir)
    if existing is not None and existing.slug != slug and not _is_stale(existing):
        raise LockBusy(
            f"Builder lock held by {existing.slug!r} at {existing.timestamp}; "
            f"not stale (window = {STALE_WINDOW_SEC}s). "
            f"Either wait, close the other mill-go, or manually delete "
            f"{_lock_path(mill_dir)} if you are certain no mill-go is running."
        )
    new = LockInfo(slug=slug, timestamp=_now_iso())
    body = f"```yaml\nslug: {new.slug}\ntimestamp: {new.timestamp}\n```\n"
    _lock_path(mill_dir).write_text(body, encoding="utf-8")
    return new


def release(mill_dir: Path) -> None:
    """Remove the lock file if present. Tolerates absence silently.

    Callers typically put this in a ``finally:`` clause; a release call
    against a not-yet-acquired lock must not raise or we defeat the
    whole cleanup pattern.
    """
    lp = _lock_path(mill_dir)
    try:
        lp.unlink()
    except FileNotFoundError:
        pass
