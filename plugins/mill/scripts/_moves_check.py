"""
Pure rename-finding helper for the code-review backend.

git does not record renames: rename detection is a similarity-based
heuristic applied at diff time using ``git diff --find-renames``.  This
module therefore acts as a surgical-edit-vs-rewrite proxy, not proof of
a rename.  A planned move that is not detected as a rename may be a
legitimate low-similarity extraction (seam split, kernel extraction) --
the LLM code-review criterion is the layer that escalates genuine
rewrites to BLOCKING.

Per the ``mechanical-rename-check-advisory`` Shared Decision, every
finding emitted here is NIT severity only.  The NIT advises the reviewer
to confirm that ``git mv`` was used; it never automatically escalates to
BLOCKING.

Public API:
    planned_rename_findings(name_status_text, moves) -> list[str]
        Compare planned (src, dst) move pairs against git diff
        --name-status output and return advisory NIT finding blocks for
        any pair that did not land as a detected rename.
"""
from __future__ import annotations


def planned_rename_findings(
    name_status_text: str,
    moves: list[tuple[str, str]],
) -> list[str]:
    """
    Compare planned move pairs against git rename-detection output.

    Parses name_status_text (output of ``git diff --name-status
    --find-renames``), builds the set of ``(old, new)`` pairs that git
    detected as renames (status lines whose first column starts with
    ``R``), and for each planned ``(src, dst)`` pair in ``moves`` that is
    NOT present in that rename set, returns one advisory NIT finding block.

    Finding block format (review-code-batch schema):

    .. code-block::

        ### [NIT] Planned move `src` -> `dst` not detected as git rename
        **Location:** `src` -> `dst`
        **Issue:** git diff --find-renames did not report this pair as a rename
                   (R status); it may have landed as separate add+delete.
        **Fix:** Confirm ``git mv`` was used with surgical edits to preserve
                 history; a full rewrite would warrant BLOCKING by the LLM reviewer.

    Args:
        name_status_text: Raw output of ``git diff --name-status
            --find-renames=<N>%``.  May be LF- or CRLF-terminated; any
            trailing ``\\r`` is stripped per line before tab-splitting so
            Windows subprocess stdout is handled transparently.
        moves: List of ``(source, destination)`` path string pairs from
            the batch plan's ``Moves:`` field.  An empty list returns
            ``[]`` immediately without parsing the diff text.

    Returns:
        List of NIT finding block strings, one per planned move pair that
        was not detected as a git rename.  Returns ``[]`` when all
        planned moves were detected as renames, when ``moves`` is empty,
        or when ``name_status_text`` is blank/malformed.
    """
    if not moves:
        return []

    # Build the set of rename pairs that git detected.
    # Each rename line has a status code starting with 'R' followed by an
    # optional similarity percentage (e.g. 'R100', 'R030'), then two tab-
    # separated path columns: old path and new path.
    detected_renames: set[tuple[str, str]] = set()
    for raw_line in name_status_text.splitlines():
        # Strip trailing \r so CRLF-terminated Windows output is handled
        # identically to LF-terminated output.
        line = raw_line.rstrip("\r")
        if not line:
            continue
        parts = line.split("\t")
        # A valid rename line has at least three tab-separated fields:
        # status code, old path, and new path.
        if len(parts) >= 3 and parts[0].startswith("R"):
            old_path = parts[1].strip()
            new_path = parts[2].strip()
            detected_renames.add((old_path, new_path))

    # For each planned move not found among detected renames, produce one
    # advisory NIT finding block.  The NIT is purely informational: it
    # surfaces when the planned move's similarity fell below git's
    # threshold (which can happen legitimately for seam extractions) and
    # prompts the LLM reviewer to confirm ``git mv`` was used.
    findings: list[str] = []
    for src, dst in moves:
        if (src, dst) not in detected_renames:
            block = (
                f"### [NIT] Planned move `{src}` -> `{dst}` not detected as git rename\n"
                f"**Location:** `{src}` -> `{dst}`\n"
                f"**Issue:** git diff --find-renames did not report this pair as a rename "
                f"(R status); it may have landed as separate add+delete entries.\n"
                f"**Fix:** Confirm `git mv` was used with surgical edits to preserve "
                f"file history; a full rewrite would warrant BLOCKING by the LLM reviewer."
            )
            findings.append(block)

    return findings
