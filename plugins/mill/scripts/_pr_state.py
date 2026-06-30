"""
Shared helper for resolving the state of a GitHub PR associated with a branch.

Provides a single function, ``resolve_pr_state``, that queries the GitHub CLI
and normalises the result into a stable dict. Both ``millpy-cleanup.py`` (for
pr-reap teardown) and the ``mill-merge`` skill (to detect pre-merged or
pre-closed PRs) use this helper, ensuring identical precedence logic and
fallback behaviour across both callers.

Precedence rule when a branch has multiple PRs: MERGED > OPEN > CLOSED.
Any condition that prevents a definitive answer (gh absent, non-zero exit,
empty or malformed output) returns ``state="none"`` without raising.
"""
from __future__ import annotations

import json
from pathlib import Path

import _subprocess_util


def resolve_pr_state(branch: str, cwd: "Path | str") -> dict:
    """
    Query GitHub for all PRs whose head branch matches ``branch`` and return
    a normalised state dict.

    The function calls:
        gh pr list --head <branch> --state all --json state,mergeCommit,number,url

    The full JSON array is parsed (no ``--jq`` filter) so that when a branch
    has accumulated multiple PRs the precedence rule MERGED > OPEN > CLOSED is
    applied: the "highest priority" state wins regardless of array order. The
    winning PR object supplies ``number``, ``url``, and ``mergeCommit``.

    The ``merge_commit`` value is kept as the raw gh ``mergeCommit`` object
    (a dict with at minimum an ``"oid"`` key when the PR was merged), NOT a
    flattened string. This lets callers use ``(merge_commit or {}).get("oid")``
    safely.

    All error conditions collapse to ``state="none"`` without raising:
    - ``_subprocess_util.run`` raises (e.g. ``FileNotFoundError`` when gh is absent)
    - non-zero exit code
    - empty stdout
    - ``json.loads`` fails or yields a non-list
    - the parsed list is empty
    - no PR object matches any known state

    Args:
        branch: The head branch name to query (e.g. ``"hanf/my-task"``).
        cwd: Absolute path to the git/hub root passed to the gh subprocess.
            The caller always supplies this; the helper never defaults to the
            process cwd.

    Returns:
        A dict with keys:
        - ``"state"``: one of ``"merged"``, ``"open"``, ``"closed"``, ``"none"``.
        - ``"number"``: the PR number as an ``int``, or ``None``.
        - ``"url"``: the PR URL as a ``str``, or ``None``.
        - ``"merge_commit"``: the raw gh ``mergeCommit`` object (dict), or ``None``.
    """
    # Sentinel returned whenever no definitive state can be determined.
    _none_result = {"state": "none", "number": None, "url": None, "merge_commit": None}

    # Run the gh query, catching any exception (e.g. FileNotFoundError when
    # gh is not installed) and mapping it to the "none" fallback.
    try:
        result = _subprocess_util.run(
            [
                "gh", "pr", "list",
                "--head", branch,
                "--state", "all",
                "--json", "state,mergeCommit,number,url",
            ],
            cwd=cwd,
        )
    except Exception:
        return dict(_none_result)

    # Non-zero exit or empty stdout both signal "cannot determine state".
    if result.returncode != 0 or not result.stdout.strip():
        return dict(_none_result)

    # Parse the JSON array; any parse error or unexpected type -> "none".
    try:
        pr_list = json.loads(result.stdout)
    except Exception:
        return dict(_none_result)

    if not isinstance(pr_list, list) or not pr_list:
        return dict(_none_result)

    # Apply precedence MERGED > OPEN > CLOSED across all PR objects in the
    # array. A branch with a MERGED PR must never be masked by a stale CLOSED
    # PR that appears earlier in the list.
    _priority = {"MERGED": 2, "OPEN": 1, "CLOSED": 0}
    winning_obj = None
    winning_priority = -1

    for obj in pr_list:
        raw_state = obj.get("state", "")
        priority = _priority.get(raw_state, -1)
        if priority > winning_priority:
            winning_priority = priority
            winning_obj = obj

    if winning_obj is None or winning_priority < 0:
        return dict(_none_result)

    # Map the uppercase gh state to the lowercase normalised form.
    raw_winning_state = winning_obj.get("state", "")
    state_map = {"MERGED": "merged", "OPEN": "open", "CLOSED": "closed"}
    normalised_state = state_map.get(raw_winning_state)
    if normalised_state is None:
        return dict(_none_result)

    return {
        "state": normalised_state,
        "number": winning_obj.get("number"),
        "url": winning_obj.get("url"),
        # Keep the raw mergeCommit object so callers can do
        # (merge_commit or {}).get("oid") without extra unwrapping.
        "merge_commit": winning_obj.get("mergeCommit"),
    }
