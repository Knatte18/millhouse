"""
UTC timestamp helpers shared across mill scripts and skills.

Claude Code cannot be trusted to produce accurate timestamps — it often
guesses at dates. Any mill artefact that records "when" (status
transitions, fixer-report filenames, plan frontmatter ``started:`` field)
goes through this module so the value comes from the OS clock, not the
LLM.

We use ``datetime.now(timezone.utc)`` directly rather than shelling out
to ``date -u``; Python already knows the wall clock and there is no
reason to pay subprocess overhead. All outputs are UTC — local time is
never emitted.

Public API:
    now_utc_compact() -> "YYYYMMDD-HHMMSS"
        Filename-safe compact form. Used for fixer-report filenames,
        plan ``started:`` field, any path component that sorts
        chronologically.
    now_utc_iso() -> "YYYY-MM-DDTHH:MM:SSZ"
        ISO-8601 with trailing ``Z``. Used for human-readable timeline
        rows in status.md and anywhere a standard datetime string is
        expected.
"""
from __future__ import annotations

from datetime import datetime, timezone


def now_utc_compact() -> str:
    """Return current UTC time as ``YYYYMMDD-HHMMSS``.

    Designed for filenames and fields that need to sort chronologically
    without special parsing: ``20260422-143205-plan-fix-r1.md``.
    Second-resolution is fine — two invocations in the same second are
    not expected in the mill workflow, and the downstream filename
    writer is responsible for collision handling if it ever happens.
    """
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def now_utc_iso() -> str:
    """Return current UTC time as ``YYYY-MM-DDTHH:MM:SSZ``.

    Used for the timeline rows in status.md and other human-facing
    surfaces. ``Z`` suffix rather than ``+00:00`` because the
    status.md template and every status.md already written uses that
    form — keep the corpus consistent.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    import re

    compact = now_utc_compact()
    assert re.fullmatch(r"\d{8}-\d{6}", compact), f"bad compact form: {compact!r}"
    print(f"PASS: now_utc_compact() -> {compact}")

    iso = now_utc_iso()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", iso), f"bad iso: {iso!r}"
    print(f"PASS: now_utc_iso() -> {iso}")

    # Same-invocation sanity: both should represent approximately the
    # same moment (within a second). We don't enforce exact equality —
    # two strftime calls can straddle a second boundary.
    print("All _timestamp smoke tests passed.")
