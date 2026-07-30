"""
Shared building blocks for the mill-go/mill-plan entry-gate blocking wait.

The entry-gate wait lets an orchestrator SKILL.md block on a status.md
``phase:`` transition (e.g. mill-go waiting for mill-plan to reach
``planned``) instead of returning control to the operator and requiring a
manual re-invocation. This module is pure string-building and predicate
logic only -- it performs no file I/O, network access, or subprocess call
of its own. The caller is responsible for actually running the returned
poll script (via the harness ``Monitor`` tool) and for reading
``status.md``.

Public API:
    build_wait_command(status_path, ready_phase, poll_interval_s, giveup_s) -> str
        Render a bash poll script that watches ``status_path`` for
        ``phase: <ready_phase>`` or ``phase: blocked``, giving up after
        ``giveup_s`` seconds.
    matches_wait_trigger(phase, exact, regex_patterns) -> bool
        Return whether ``phase`` should trigger entry into the wait, per an
        exact-match set and a list of full-match regex patterns.
"""
from __future__ import annotations

import re
from pathlib import Path


def build_wait_command(
    status_path: Path,
    ready_phase: str,
    poll_interval_s: int,
    giveup_s: int,
) -> str:
    """
    Render a bash script that polls ``status_path`` until it reaches
    ``ready_phase``, detects a terminal ``blocked`` phase, or times out.

    The returned string is safe to pass verbatim as the ``command``
    argument to the harness ``Monitor`` tool. On each poll iteration it:

    1. Checks whether ``status_path``'s ``phase:`` line already equals
       ``ready_phase``; if so, prints ``READY`` and exits 0.
    2. Otherwise checks whether ``phase:`` is ``blocked``; if so, extracts
       the ``blocked_reason:`` value (via ``grep``/``head``/bash parameter
       expansion -- never ``sed``, per this repo's project convention),
       prints ``BLOCKED: <reason>``, and exits 1.
    3. Otherwise, once accumulated ``elapsed`` seconds reach ``giveup_s``,
       prints a ``TIMEOUT after ...`` message and exits 2.
    4. Otherwise sleeps ``poll_interval_s`` seconds and loops.

    Every read of ``status_path`` is piped through ``tr -d '\\r'`` before
    ``grep`` ever sees it. ``_status.py``'s writers (``update_field`` /
    ``append_phase`` / ``set_blocked``) write via ``Path.write_text`` with
    no ``newline=`` override, so a Windows-authored ``status.md`` can carry
    CRLF line endings; GNU/POSIX ``grep``'s trailing ``$`` anchor does not
    match immediately before a ``\\r``, so an un-piped ``grep`` would never
    see ``READY``/``blocked`` on such a file and the wait would silently run
    out the full ``giveup_s`` clock. Stripping ``\\r`` first makes the
    trailing-``$`` anchor reliable regardless of which platform wrote the
    file. Both ``grep`` patterns are anchored with a trailing ``$`` as
    defensive future-proofing against a hypothetical future phase value
    that string-prefix-extends an existing target (e.g. a future
    ``planned-v2`` falsely matching an unanchored ``grep "^phase: planned"``).

    This function never reads or knows about
    ``pipeline.entry_wait_timeout_minutes`` -- the minutes-to-seconds
    conversion, and the choice of ``poll_interval_s``, are the caller's job.

    Args:
        status_path: Absolute path to the task's ``status.md`` file. Always
            substituted wrapped in double quotes so a path containing
            spaces stays safe.
        ready_phase: The single-word phase value to wait for (always one of
            the literal values ``planned`` / ``discussed`` in this
            codebase, never attacker- or user-supplied). Substituted
            verbatim, with no additional quoting or escaping.
        poll_interval_s: Seconds to sleep between polls. Substituted as a
            plain integer.
        giveup_s: Total seconds to wait before giving up. Substituted as a
            plain integer; this function performs no unit conversion.

    Returns:
        A bash script, as a single string, printing exactly one of
        ``READY`` / ``BLOCKED: <reason>`` / ``TIMEOUT after ...`` and
        exiting with the corresponding code (0 / 1 / 2).
    """
    quoted_path = f'"{status_path}"'
    return (
        "elapsed=0\n"
        "while true; do\n"
        f"  if tr -d '\\r' < {quoted_path} | grep -q \"^phase: {ready_phase}$\"; then\n"
        '    echo "READY"\n'
        "    exit 0\n"
        "  fi\n"
        f"  if tr -d '\\r' < {quoted_path} | grep -q \"^phase: blocked$\"; then\n"
        f"    reason_line=$(tr -d '\\r' < {quoted_path} | grep \"^blocked_reason:\" | head -1)\n"
        '    reason=${reason_line#blocked_reason: }\n'
        "    reason=${reason#\\'}\n"
        "    reason=${reason%\\'}\n"
        '    echo "BLOCKED: ${reason}"\n'
        "    exit 1\n"
        "  fi\n"
        f'  if [ "$elapsed" -ge {int(giveup_s)} ]; then\n'
        f'    echo "TIMEOUT after ${{elapsed}}s waiting for phase: {ready_phase}"\n'
        "    exit 2\n"
        "  fi\n"
        f"  sleep {int(poll_interval_s)}\n"
        f"  elapsed=$((elapsed + {int(poll_interval_s)}))\n"
        "done\n"
    )


def matches_wait_trigger(
    phase: str, exact: set[str], regex_patterns: list[str]
) -> bool:
    """
    Return whether ``phase`` should trigger entry into the entry-gate wait.

    ``phase`` matches if it is a member of ``exact``, or if it full-matches
    (via ``re.fullmatch``, never ``str.startswith``) any pattern in
    ``regex_patterns``. The parameter is named ``regex_patterns`` rather
    than ``prefix_patterns`` because the values it holds in this codebase's
    actual usage (``^plan-review-r\\d+$``, ``^plan-fix-r\\d+$``) are
    fully-anchored full-match regexes, not string prefixes.

    Args:
        phase: The current ``phase:`` value read from ``status.md``.
        exact: Set of phase values that match by exact equality.
        regex_patterns: List of fully-anchored regex patterns; ``phase``
            matches if it full-matches any one of them.

    Returns:
        ``True`` if ``phase`` matches ``exact`` or any ``regex_patterns``
        entry; ``False`` otherwise.
    """
    if phase in exact:
        return True
    return any(re.fullmatch(pattern, phase) for pattern in regex_patterns)
