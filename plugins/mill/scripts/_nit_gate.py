"""
Detect approved scopes with unfixed nits.

This module provides a gate to prevent tasks from completing when approved
scopes have pending nits. It reads the status timeline to find all approved
scopes, checks whether their final code-review files contain NIT headings,
and verifies that nits-fixed markers are present in the timeline.

Public API:
    compute_unfixed_nits(worktree, reviews_dir, status_path) -> list[str]
        Returns a list of approved scope names that have nits in their final
        review file but lack a nits-fixed-<scope> marker in the timeline.
"""
from __future__ import annotations

import re
from pathlib import Path

import _review_common
import _status


def compute_unfixed_nits(
    worktree: Path,
    reviews_dir: Path,
    status_path: Path,
) -> list[str]:
    """
    Compute the list of approved scopes with unfixed nits.

    Reads the status timeline to find all approved scopes (per-batch scopes
    from `approved-<batch>` rows and `holistic` from `holistic-approved` rows).
    For each approved scope, locates the latest-timestamp code-review file
    matching RE_BATCH (per-batch) or RE_SIMPLE (holistic) patterns, counts
    `### [NIT]` headings via parse_blocking_count, and includes the scope
    in the result when nit_count > 0 AND no nits-fixed-<scope> row exists
    in the timeline.

    Args:
        worktree: Path to the worktree root (unused; accepted for API consistency).
        reviews_dir: Path to the directory containing review files
            (typically _mill/reviews/).
        status_path: Path to the status.md file.

    Returns:
        A list of scope names (strings) that have unfixed nits. Returns an
        empty list when every nitted scope has a marker.
    """
    # Read the status file to extract the timeline
    try:
        full = _status.read_full(status_path)
        timeline = full["timeline"]
    except Exception:
        # On any read error, return empty list (gate passes)
        return []

    # Extract all approved scopes from the timeline
    approved_scopes = set()
    for line in timeline:
        # Each line is "<phase>  <timestamp>"
        parts = line.split()
        if not parts:
            continue
        phase = parts[0]
        # Match approved-<batch> pattern
        if phase.startswith("approved-"):
            scope = phase[len("approved-"):]
            approved_scopes.add(scope)
        # Match holistic-approved
        elif phase == "holistic-approved":
            approved_scopes.add("holistic")

    # Extract all nits-fixed markers from the timeline
    nits_fixed_scopes = set()
    for line in timeline:
        parts = line.split()
        if not parts:
            continue
        phase = parts[0]
        # Match nits-fixed-<scope> pattern
        if phase.startswith("nits-fixed-"):
            scope = phase[len("nits-fixed-"):]
            nits_fixed_scopes.add(scope)

    unfixed = []
    for scope in approved_scopes:
        # Skip if this scope already has a nits-fixed marker
        if scope in nits_fixed_scopes:
            continue

        # Locate the final code-review file for this scope
        final_review_text = _find_final_code_review(reviews_dir, scope)
        if final_review_text is None:
            # No review file found for this scope; skip it
            continue

        # Count nits in the final review
        nit_count = _review_common.parse_blocking_count(
            final_review_text,
            severity="NIT",
        )
        if nit_count > 0:
            unfixed.append(scope)

    return sorted(unfixed)


def _find_final_code_review(reviews_dir: Path, scope: str) -> str | None:
    """
    Find the latest code-review file for the given scope.

    For per-batch scopes, searches for files matching RE_BATCH with
    type=code and batch=<scope>. For holistic scope, searches for files
    matching RE_SIMPLE with type=code. Returns the file contents of the
    latest-timestamp match, or None if no match is found.

    Args:
        reviews_dir: Path to the reviews directory.
        scope: Scope name ("holistic" or batch name).

    Returns:
        The text contents of the final review file, or None if not found.
    """
    if not reviews_dir.exists():
        return None

    candidate_files = []
    for file_path in sorted(reviews_dir.iterdir()):
        if not file_path.is_file() or not file_path.suffix == ".md":
            continue

        filename = file_path.name
        # Holistic scope uses RE_SIMPLE
        if scope == "holistic":
            match = _review_common.RE_SIMPLE.match(filename)
            if match and match.group("type") == "code":
                # Extract timestamp from filename for sorting
                timestamp = filename[:15]  # YYYYMMDD-HHMMSS
                candidate_files.append((timestamp, file_path))
        else:
            # Per-batch scope uses RE_BATCH
            match = _review_common.RE_BATCH.match(filename)
            if match and match.group("type") == "code" and match.group("batch") == scope:
                timestamp = filename[:15]  # YYYYMMDD-HHMMSS
                candidate_files.append((timestamp, file_path))

    if not candidate_files:
        return None

    # Sort by timestamp (descending) and take the latest
    candidate_files.sort(reverse=True)
    latest_file = candidate_files[0][1]
    try:
        return latest_file.read_text(encoding="utf-8")
    except Exception:
        return None
