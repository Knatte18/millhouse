"""
Static plan pre-validator.

Checks plan files for structural issues BEFORE invoking the LLM reviewer.
Used by millpy-validate-plan.py (standalone CLI) and by millpy-review-plan.py
(auto-run gate before each review round).

Public API:
    run(plan_dir, project_root, *, root=None, wiki_root=None, git_root=None, skip_checks=frozenset()) -> list[dict]
        Validate plan files in plan_dir. Returns a sorted list of error dicts.
        Each error dict has keys: {check, batch, card, path, message}.

Checks performed (check keys):
    non-existent-path        — (#10 check 1) Context:/Edits:/Creates: refs that
                               don't exist on disk and are not Creates:/Moves: targets
    card-missing-field       — (#10 check 2) Cards missing one of the required
                               fields (Context, Edits, Creates, Deletes, Moves,
                               Requirements, Commit)
    card-numbering           — (#10 check 3) Non-sequential or cross-batch-duplicate
                               card numbers
    depends-on-unknown       — (#10 check 4) depends-on entries referencing unknown
                               batch names
    depends-on-batch-mismatch — per-batch file's depends-on disagrees with overview
                               Batch Index depends-on for the same batch
    parallel-modifies-overlap — (#10 check 5) Parallel-eligible batches both
                               modifying the same file (includes Move endpoints)
    reads-not-backtick-path  — (#10 check 6) Context:/Edits:/Creates: entries not
                               in backtick-only format (exempts bare 'none')
    all-files-touched-mismatch — (#10 check 8) Mismatch between overview's
                               All Files Touched section and cards' Edits:/Creates:/Moves: targets
    verify-not-isolated      — per-batch frontmatter verify: command does not start with PYTHONPATH= reset prefix
    wiki-config-mutation     — batch Edits:/Creates: contains mill-config.yaml (self-applying layout risk)
    move-format              — Moves: sub-bullet does not match the `src` -> `dst` grammar
    move-redundant           — a path is both a Move endpoint and in Creates:/Deletes: of the same batch
    move-source-missing      — Move source does not exist on disk and is not created/relocated by an earlier batch
    move-target-collision    — Move target already exists, is targeted by multiple batches, or collides with a Creates: in another batch
    move-mechanic-missing    — batch has non-empty Moves: but is missing a '## Rename mechanic' section
"""
from __future__ import annotations

import os
import re
import yaml
from pathlib import Path

from _plan_dag import PlanDAGError, extract_batch_index, resolve_deps_as_names
from _review_common import (
    _load_root_from_overview,
    compute_creates_union,
    compute_deletes_union,
    compute_moves_union,
    parse_batch_refs,
    parse_moves,
    resolve_existing_paths,
)

# ---------------------------------------------------------------------------
# Module-level regex helpers
# ---------------------------------------------------------------------------

# Matches Context/Edits/Creates/Deletes header bullets.
_RE_REFS_HEADER = re.compile(
    r"^-\s*\*\*(Context|Edits|Creates|Deletes):\*\*(?P<inline>.*)$"
)

# Matches the Moves: header bullet (kept separate from _RE_REFS_HEADER because
# Moves sub-bullets use a two-path grammar that the reads-not-backtick-path
# validator rejects when mixed into the single-path fields above).
_RE_MOVES_HEADER = re.compile(r"^-\s*\*\*Moves:\*\*(?P<inline>.*)$")

# Matches a well-formed move sub-bullet: exactly `src` -> `dst`.
# The separator must be the ASCII literal " -> " (space-hyphen-greater-space).
# Any sub-bullet that does not match this pattern is considered malformed.
_RE_MOVE_PAIR = re.compile(r"^`([^`]+)` -> `([^`]+)`$")

# Matches sub-bullets under multi-line header bullets.
_RE_REFS_SUB = re.compile(r"^\s+-\s*(.+)$")

# Line-range suffix inside a backtick token: e.g. "path/a:55-65"
_RE_LINE_RANGE = re.compile(r":\d+-\d+$")

# Matches the "## Rename mechanic" heading in a batch that has non-empty Moves.
_RE_MECHANIC_HEADING = re.compile(r"^##\s+Rename mechanic\b", re.MULTILINE)

# Required card fields.
# "Moves" sits after "Deletes" and before "Requirements" per the moves-grammar Shared Decision.
_REQUIRED_CARD_FIELDS = ["Context", "Edits", "Creates", "Deletes", "Moves", "Requirements", "Commit"]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_cards(batch_text: str) -> list[tuple[int, list[str]]]:
    """Return list of (card_number, card_lines) pairs.

    Each card block starts at a ``### Card N:`` line and ends just before
    the next ``### `` heading or at EOF.
    """
    lines = batch_text.splitlines()
    cards: list[tuple[int, list[str]]] = []
    current_num: int | None = None
    current_lines: list[str] = []

    for line in lines:
        m = re.match(r"^###\s+Card\s+(\d+)\s*:", line)
        if m:
            if current_num is not None:
                cards.append((current_num, current_lines))
            current_num = int(m.group(1))
            current_lines = [line]
        elif current_num is not None:
            # Any other ### heading terminates the current card block.
            if line.startswith("### "):
                cards.append((current_num, current_lines))
                current_num = None
                current_lines = []
            else:
                current_lines.append(line)

    if current_num is not None:
        cards.append((current_num, current_lines))

    return cards


def _parse_edits_only(batch_path: Path) -> set[str]:
    """Extract raw path tokens from a batch file's Edits: lines only.

    Same single-line / multi-line logic as parse_batch_refs in _review_common,
    but restricted to ``- **Edits:**`` headers. Filters ``none``
    (case-insensitive) per the existing convention.
    """
    text = batch_path.read_text(encoding="utf-8")
    tokens: set[str] = set()
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = _RE_REFS_HEADER.match(lines[i])
        if m and m.group(1) == "Edits":
            inline = m.group("inline").strip()
            if inline:
                backtick_tokens = re.findall(r"`([^`]+)`", inline)
                batch_tokens = backtick_tokens if backtick_tokens else [
                    t.strip() for t in inline.split(",") if t.strip()
                ]
            else:
                batch_tokens = []
                j = i + 1
                while j < len(lines):
                    sm = _RE_REFS_SUB.match(lines[j])
                    if not sm:
                        break
                    rest = sm.group(1).strip()
                    bt = re.findall(r"`([^`]+)`", rest)
                    if bt:
                        batch_tokens.extend(bt)
                    j += 1
            for t in batch_tokens:
                if t.lower() != "none":
                    tokens.add(t)
        i += 1
    return tokens


def _parse_creates_only(batch_path: Path) -> set[str]:
    """Extract raw path tokens from a batch file's Creates: lines only.

    Same single-line / multi-line logic as parse_batch_refs in _review_common,
    but restricted to ``- **Creates:**`` headers. Filters ``none``
    (case-insensitive) per the existing convention.
    """
    text = batch_path.read_text(encoding="utf-8")
    tokens: set[str] = set()
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = _RE_REFS_HEADER.match(lines[i])
        if m and m.group(1) == "Creates":
            inline = m.group("inline").strip()
            if inline:
                backtick_tokens = re.findall(r"`([^`]+)`", inline)
                batch_tokens = backtick_tokens if backtick_tokens else [
                    t.strip() for t in inline.split(",") if t.strip()
                ]
            else:
                batch_tokens = []
                j = i + 1
                while j < len(lines):
                    sm = _RE_REFS_SUB.match(lines[j])
                    if not sm:
                        break
                    rest = sm.group(1).strip()
                    bt = re.findall(r"`([^`]+)`", rest)
                    if bt:
                        batch_tokens.extend(bt)
                    j += 1
            for t in batch_tokens:
                if t.lower() != "none":
                    tokens.add(t)
        i += 1
    return tokens


def _parse_deletes_only(batch_path: Path) -> set[str]:
    """Extract raw path tokens from a batch file's Deletes: lines only.

    Same single-line / multi-line logic as parse_batch_refs in _review_common,
    but restricted to ``- **Deletes:**`` headers. Filters ``none``
    (case-insensitive) per the existing convention.
    """
    text = batch_path.read_text(encoding="utf-8")
    tokens: set[str] = set()
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = _RE_REFS_HEADER.match(lines[i])
        if m and m.group(1) == "Deletes":
            inline = m.group("inline").strip()
            if inline:
                backtick_tokens = re.findall(r"`([^`]+)`", inline)
                batch_tokens = backtick_tokens if backtick_tokens else [
                    t.strip() for t in inline.split(",") if t.strip()
                ]
            else:
                batch_tokens = []
                j = i + 1
                while j < len(lines):
                    sm = _RE_REFS_SUB.match(lines[j])
                    if not sm:
                        break
                    rest = sm.group(1).strip()
                    bt = re.findall(r"`([^`]+)`", rest)
                    if bt:
                        batch_tokens.extend(bt)
                    j += 1
            for t in batch_tokens:
                if t.lower() != "none":
                    tokens.add(t)
        i += 1
    return tokens


# ---------------------------------------------------------------------------
# move-format check
# ---------------------------------------------------------------------------

def _check_move_format(batch_files: list[Path]) -> list[dict]:
    """
    Check that every non-none Moves: sub-bullet matches the canonical grammar.

    Scans every ``- **Moves:**`` header in each batch file.  An inline ``none``
    (case-insensitive) is silently accepted.  For all other headers each
    sub-bullet is compared against ``_RE_MOVE_PAIR`` (`` `src` -> `dst` ``).
    A sub-bullet that is missing the arrow, has only one backtick path, or
    carries prose yields an error dict with ``check="move-format"``.

    Error dict shape: ``{check, batch, card, path, message}``.

    Args:
        batch_files: Sorted list of batch file paths to validate.

    Returns:
        List of error dicts, one per malformed sub-bullet found.
    """
    errors: list[dict] = []
    for batch_path in batch_files:
        text = batch_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        current_card: int | None = None
        i = 0
        while i < len(lines):
            line = lines[i]

            # Track the enclosing card number so errors carry the right card.
            m_card = re.match(r"^###\s+Card\s+(\d+)\s*:", line)
            if m_card:
                current_card = int(m_card.group(1))

            m_header = _RE_MOVES_HEADER.match(line)
            if m_header:
                inline = m_header.group("inline").strip()

                # Inline "none" sentinel: no moves declared, nothing to check.
                if inline.lower() == "none":
                    i += 1
                    continue

                # Any other inline value (or empty): scan the following sub-bullets.
                j = i + 1
                while j < len(lines):
                    sm = _RE_REFS_SUB.match(lines[j])
                    if not sm:
                        # No longer in a sub-bullet block; stop.
                        break
                    sub_content = sm.group(1).strip()
                    pm = _RE_MOVE_PAIR.match(sub_content)
                    if not pm:
                        # Sub-bullet does not match the two-backtick-path grammar.
                        errors.append({
                            "check": "move-format",
                            "batch": batch_path.stem,
                            "card": current_card,
                            "path": sub_content,
                            "message": (
                                "Moves: sub-bullet does not match "
                                f"'`src` -> `dst`' grammar: {sub_content!r}"
                            ),
                        })
                    j += 1

                # Skip past the consumed sub-bullet block.
                i = j
                continue

            i += 1

    return errors


# ---------------------------------------------------------------------------
# move-redundant check
# ---------------------------------------------------------------------------

def _check_move_redundant(batch_files: list[Path]) -> list[dict]:
    """
    Flag Move endpoints that are also declared in Creates: or Deletes:.

    For each batch file, collects every Move source and target via
    ``parse_moves``, then intersects with the batch's own ``Creates:``
    and ``Deletes:`` tokens.  An identical path appearing in both a
    ``Moves:`` field and a ``Creates:``/``Deletes:`` field within the
    SAME batch is redundant -- the implementer should use one or the
    other, not both.

    Only an exact-token match triggers the error.  A ``Moves:`` target
    that is a DIFFERENT path from any ``Creates:`` entry (the canonical
    rename-plus-extraction pattern) is explicitly allowed.

    Error dict shape: ``{check, batch, card, path, message}``.

    Args:
        batch_files: Sorted list of batch file paths to validate.

    Returns:
        List of error dicts, one per redundant path found.
    """
    errors: list[dict] = []
    for batch_path in batch_files:
        moves = parse_moves(batch_path)
        if not moves:
            continue

        # Build the complete set of Move endpoints for this batch.
        move_endpoints: set[str] = set()
        for src, dst in moves:
            move_endpoints.add(src)
            move_endpoints.add(dst)

        # Paths declared in Creates: or Deletes: within the same batch.
        creates = _parse_creates_only(batch_path)
        deletes = _parse_deletes_only(batch_path)
        conflicting = move_endpoints & (creates | deletes)

        # Emit one error per conflicting path in deterministic order.
        for path in sorted(conflicting):
            errors.append({
                "check": "move-redundant",
                "batch": batch_path.stem,
                "card": None,
                "path": path,
                "message": (
                    f"path '{path}' is a Moves: endpoint and also appears in "
                    "Creates:/Deletes: of the same batch; "
                    "use Moves: or Creates:/Deletes:, not both"
                ),
            })

    return errors


# ---------------------------------------------------------------------------
# move-source-missing check
# ---------------------------------------------------------------------------

def _check_move_source_missing(
    batch_files: list[Path],
    project_root: Path,
    root: str | None,
    creates_union: set[str],
    moves_targets: set[str],
    *,
    wiki_root: Path | None = None,
    git_root: Path | None = None,
) -> list[dict]:
    """
    Flag Moves: sources that do not exist and are not created or relocated earlier.

    Modelled on the Deletes branch of ``_check_non_existent_path``: a Move source
    that is missing on disk is only an error when it cannot be explained by an
    earlier batch creating it (``creates_union``) or an earlier Move relocating a
    different file to that path (``moves_targets``).  Both suppression sets are
    plan-wide, so chained moves (batch A moves X to Y; batch B moves Y to Z) do
    not generate a false positive for batch B's source Y.

    Error dict shape: ``{check, batch, card, path, message}``.

    Args:
        batch_files: Sorted list of batch file paths to validate.
        project_root: Root of the project (worktree root).
        root: Optional root subfolder for source refs (threaded to
            ``resolve_existing_paths``).
        creates_union: Union of all ``Creates:`` tokens across the plan.
        moves_targets: Union of all ``Moves:`` destination tokens across the plan.
        wiki_root: Optional wiki root path (threaded to ``resolve_existing_paths``).
        git_root: Optional repo root (threaded to ``resolve_existing_paths``).

    Returns:
        List of error dicts, one per missing Move source.
    """
    errors: list[dict] = []
    for batch_path in batch_files:
        moves = parse_moves(batch_path)
        for src, _ in moves:
            existing = resolve_existing_paths(
                [src], project_root, root,
                wiki_root=wiki_root, git_root=git_root,
            )
            # Suppress when an earlier batch creates the file or moves something
            # else to this path, making it available before this Move runs.
            if not existing and src not in creates_union and src not in moves_targets:
                errors.append({
                    "check": "move-source-missing",
                    "batch": batch_path.stem,
                    "card": None,
                    "path": src,
                    "message": (
                        f"Moves: source '{src}' does not exist on disk and is not "
                        "created or relocated by an earlier batch"
                    ),
                })

    return errors


# ---------------------------------------------------------------------------
# move-target-collision check
# ---------------------------------------------------------------------------

def _check_move_target_collision(
    batch_files: list[Path],
    project_root: Path,
    root: str | None,
    *,
    wiki_root: Path | None = None,
    git_root: Path | None = None,
) -> list[dict]:
    """
    Flag Moves: targets that collide with existing files or other plan entries.

    Three collision conditions are checked (OR semantics):

    1. The target already exists on disk before the plan runs.
    2. More than one batch across the plan names the same destination path.
    3. The target appears as a ``Creates:`` token in a DIFFERENT batch (cross-batch
       collision).  Same-batch overlap is ``move-redundant``'s responsibility; this
       check intentionally skips it to avoid double-reporting.

    Error dict shape: ``{check, batch, card, path, message}``.

    Args:
        batch_files: Sorted list of batch file paths to validate.
        project_root: Root of the project (worktree root).
        root: Optional root subfolder (threaded to ``resolve_existing_paths``).
        wiki_root: Optional wiki root path.
        git_root: Optional repo root.

    Returns:
        List of error dicts in deterministic sorted order.
    """
    # Build per-batch move-target sets and per-batch creates sets for
    # accurate cross-batch collision detection.
    batch_targets: dict[str, set[str]] = {}
    batch_creates: dict[str, set[str]] = {}
    for batch_path in batch_files:
        stem = batch_path.stem
        batch_targets[stem] = {dst for _, dst in parse_moves(batch_path)}
        batch_creates[stem] = _parse_creates_only(batch_path)

    # Count how many batches target each destination path (plan-wide).
    target_batch_count: dict[str, int] = {}
    for targets in batch_targets.values():
        for dst in targets:
            target_batch_count[dst] = target_batch_count.get(dst, 0) + 1

    errors: list[dict] = []

    for batch_path in sorted(batch_files):
        stem = batch_path.stem
        for dst in sorted(batch_targets[stem]):
            # Condition 1: target file already exists on disk.
            existing = resolve_existing_paths(
                [dst], project_root, root,
                wiki_root=wiki_root, git_root=git_root,
            )
            if existing:
                errors.append({
                    "check": "move-target-collision",
                    "batch": stem,
                    "card": None,
                    "path": dst,
                    "message": f"Moves: target '{dst}' already exists on disk",
                })
                continue

            # Condition 2: more than one batch targets the same destination.
            if target_batch_count.get(dst, 0) > 1:
                errors.append({
                    "check": "move-target-collision",
                    "batch": stem,
                    "card": None,
                    "path": dst,
                    "message": (
                        f"Moves: target '{dst}' is named by more than one batch across the plan"
                    ),
                })
                continue

            # Condition 3: cross-batch Creates: collision.
            # Same-batch overlap is move-redundant's job; skip it here.
            for other_stem, other_creates in sorted(batch_creates.items()):
                if other_stem == stem:
                    continue
                if dst in other_creates:
                    errors.append({
                        "check": "move-target-collision",
                        "batch": stem,
                        "card": None,
                        "path": dst,
                        "message": (
                            f"Moves: target '{dst}' collides with "
                            f"Creates: in batch '{other_stem}'"
                        ),
                    })
                    break

    return errors


# ---------------------------------------------------------------------------
# move-mechanic-missing check
# ---------------------------------------------------------------------------

def _check_move_mechanic_missing(batch_files: list[Path]) -> list[dict]:
    """
    Require a '## Rename mechanic' section in any batch that declares Moves:.

    The ``plan-batch.md`` template includes this section to guide the implementer
    on the correct ``git mv`` + surgical-edit workflow.  When a batch declares at
    least one non-empty ``Moves:`` pair via ``parse_moves``, the batch file text
    must contain a heading line matching ``^##\\s+Rename mechanic\\b`` (the
    canonical section name).  Batches where every ``Moves:`` field carries the
    ``none`` sentinel produce an empty ``parse_moves`` result and are skipped.

    Error dict shape: ``{check, batch, card, path, message}``.

    Args:
        batch_files: Sorted list of batch file paths to validate.

    Returns:
        List of error dicts, one per batch that is missing the heading.
    """
    errors: list[dict] = []
    for batch_path in batch_files:
        # parse_moves returns [] when all Moves: headers are "none"; skip those.
        moves = parse_moves(batch_path)
        if not moves:
            continue

        text = batch_path.read_text(encoding="utf-8")
        if not _RE_MECHANIC_HEADING.search(text):
            errors.append({
                "check": "move-mechanic-missing",
                "batch": batch_path.stem,
                "card": None,
                "path": None,
                "message": (
                    f"batch '{batch_path.stem}' has Moves: entries but is missing "
                    "a '## Rename mechanic' section"
                ),
            })

    return errors


# ---------------------------------------------------------------------------
# Check 1 — non-existent-path
# ---------------------------------------------------------------------------

def _check_non_existent_path(
    batch_files: list[Path],
    project_root: Path,
    root: str | None,
    creates_union: set[str],
    deletes_union: set[str],
    moves_targets: set[str],
    *,
    wiki_root: Path | None = None,
    git_root: Path | None = None,
) -> list[dict]:
    """
    Check that all Context/Edits/Creates/Deletes path refs resolve to existing files.

    Suppression rules mirror the move-endpoint-accounting Shared Decision:
    - ``creates_union``: paths that will be created by some batch are not flagged.
    - ``deletes_union``: paths that will be deleted are not flagged for general refs
      (the file may disappear before this batch runs).
    - ``moves_targets``: paths that are Moves: destinations are not flagged because
      they will be created by the rename step (a downstream card editing a Move
      target must not raise non-existent-path).

    Move-source existence is NOT checked here; that is solely
    ``_check_move_source_missing``'s responsibility (card 6).  This function
    continues to operate only on the general Context/Edits/Creates and Deletes
    tokens that ``parse_batch_refs`` already parses (it does not parse Moves: bullets).

    Error dict shape: ``{check, batch, card, path, message}``.
    """
    errors: list[dict] = []
    for batch_path in batch_files:
        raw_refs = parse_batch_refs(batch_path)
        deletes_only = _parse_deletes_only(batch_path)
        general_refs = set(raw_refs) - deletes_only

        # General refs (Context/Edits/Creates): missing on disk is suppressed when
        # the token is in creates_union, deletes_union, OR moves_targets.  The
        # moves_targets suppression prevents false errors on downstream cards that
        # reference a not-yet-existing Move destination in their Context:/Edits:.
        for t in general_refs:
            if t.lower() == "none":
                continue
            existing = resolve_existing_paths([t], project_root, root, wiki_root=wiki_root, git_root=git_root)
            if not existing and t not in creates_union and t not in deletes_union and t not in moves_targets:
                errors.append({
                    "check": "non-existent-path",
                    "batch": batch_path.stem,
                    "card": None,
                    "path": t,
                    "message": (
                        f"path '{t}' does not exist on disk and is not a "
                        f"Creates: target in any batch"
                    ),
                })

        # Deletes refs: missing on disk is suppressed only if in creates_union
        # (cross-batch: an earlier batch creates it, this card deletes it).
        for t in deletes_only:
            if t.lower() == "none":
                continue
            existing = resolve_existing_paths([t], project_root, root, wiki_root=wiki_root, git_root=git_root)
            if not existing and t not in creates_union:
                errors.append({
                    "check": "non-existent-path",
                    "batch": batch_path.stem,
                    "card": None,
                    "path": t,
                    "message": (
                        f"Deletes: token '{t}' does not exist on disk and is not a "
                        f"Creates: target in any batch"
                    ),
                })

    return errors


# ---------------------------------------------------------------------------
# Check 2 — card-missing-field
# ---------------------------------------------------------------------------

def _check_card_missing_field(batch_files: list[Path]) -> list[dict]:
    errors: list[dict] = []
    for batch_path in batch_files:
        text = batch_path.read_text(encoding="utf-8")
        cards = _parse_cards(text)
        for card_num, card_lines in cards:
            card_text = "\n".join(card_lines)
            for field in _REQUIRED_CARD_FIELDS:
                pattern = re.compile(
                    r"^-\s*\*\*" + re.escape(field) + r":\*\*", re.MULTILINE
                )
                if not pattern.search(card_text):
                    errors.append({
                        "check": "card-missing-field",
                        "batch": batch_path.stem,
                        "card": card_num,
                        "path": None,
                        "message": f"card {card_num} missing required field: {field}:",
                    })
    return errors


# ---------------------------------------------------------------------------
# Check 3 — card-numbering
# ---------------------------------------------------------------------------

def _check_card_numbering(batch_files: list[Path]) -> list[dict]:
    errors: list[dict] = []

    # Collect per-batch card lists and a global list for cross-batch checks.
    per_batch: dict[str, list[int]] = {}
    all_cards: list[tuple[str, int]] = []

    for batch_path in batch_files:
        text = batch_path.read_text(encoding="utf-8")
        cards = _parse_cards(text)
        stem = batch_path.stem
        nums = [n for n, _ in cards]
        per_batch[stem] = nums
        for n in nums:
            all_cards.append((stem, n))

    # Within-batch: no duplicates, sequential (no gaps).
    for stem, nums in per_batch.items():
        if not nums:
            continue
        # Duplicate check.
        seen_count: dict[int, int] = {}
        for n in nums:
            seen_count[n] = seen_count.get(n, 0) + 1
        for n, count in sorted(seen_count.items()):
            if count > 1:
                errors.append({
                    "check": "card-numbering",
                    "batch": stem,
                    "card": n,
                    "path": None,
                    "message": f"card {n} breaks sequential numbering within batch {stem}",
                })
        # Gap check on unique numbers.
        unique_sorted = sorted(seen_count.keys())
        for i in range(1, len(unique_sorted)):
            if unique_sorted[i] != unique_sorted[i - 1] + 1:
                # The gap starts after unique_sorted[i-1]; report at the missing number.
                missing = unique_sorted[i - 1] + 1
                errors.append({
                    "check": "card-numbering",
                    "batch": stem,
                    "card": missing,
                    "path": None,
                    "message": (
                        f"card {missing} breaks sequential numbering within batch {stem}"
                    ),
                })

    # Cross-batch uniqueness: a card number in two different batches.
    card_to_batches: dict[int, set[str]] = {}
    for stem, n in all_cards:
        card_to_batches.setdefault(n, set()).add(stem)
    for n, batch_set in sorted(card_to_batches.items()):
        if len(batch_set) > 1:
            for stem in sorted(batch_set):
                errors.append({
                    "check": "card-numbering",
                    "batch": stem,
                    "card": n,
                    "path": None,
                    "message": (
                        f"card {n} breaks sequential numbering within batch {stem}"
                    ),
                })

    return errors


# ---------------------------------------------------------------------------
# Check 4 — depends-on-unknown
# ---------------------------------------------------------------------------

def _check_depends_on_unknown(
    overview_text: str,
    overview_path: Path,
) -> list[dict]:
    try:
        batches = extract_batch_index(overview_text)
    except PlanDAGError as exc:
        return [{
            "check": "batch-index-parse",
            "batch": None,
            "card": None,
            "path": str(overview_path),
            "message": f"batch index unparseable: {exc}",
        }]
    known_names = {entry["name"] for entry in batches}
    known_numbers = {entry["number"] for entry in batches if "number" in entry}
    errors: list[dict] = []
    for entry in batches:
        for dep in entry.get("depends-on", []):
            if isinstance(dep, int):
                if dep not in known_numbers:
                    errors.append({
                        "check": "depends-on-unknown",
                        "batch": entry["name"],
                        "card": None,
                        "path": None,
                        "message": f"depends-on references unknown batch number {dep}",
                    })
            else:
                if dep not in known_names:
                    errors.append({
                        "check": "depends-on-unknown",
                        "batch": entry["name"],
                        "card": None,
                        "path": None,
                        "message": f"depends-on references unknown batch '{dep}'",
                    })
    return errors


# ---------------------------------------------------------------------------
# Check 5 — parallel-modifies-overlap
# ---------------------------------------------------------------------------

def _compute_transitive_ancestors(batches: list[dict]) -> dict[str, set[str]]:
    """Return {batch_name: set_of_all_ancestor_names} via BFS for each batch."""
    deps_map = resolve_deps_as_names(batches)
    ancestors: dict[str, set[str]] = {}
    for entry in batches:
        name = entry["name"]
        visited: set[str] = set()
        queue = list(deps_map.get(name, []))
        while queue:
            n = queue.pop()
            if n in visited:
                continue
            visited.add(n)
            queue.extend(deps_map.get(n, []))
        ancestors[name] = visited
    return ancestors


def _check_parallel_modifies_overlap(
    batch_files: list[Path],
    overview_text: str,
) -> list[dict]:
    try:
        batches = extract_batch_index(overview_text)
    except PlanDAGError:
        # Check 4 has already recorded the parse error; don't double-report.
        return []

    ancestors = _compute_transitive_ancestors(batches)

    # Map batch name → batch file path via the index's `file:` field.
    stem_to_path: dict[str, Path] = {bf.stem: bf for bf in batch_files}
    batch_name_to_path: dict[str, Path] = {}
    for entry in batches:
        file_ref = entry.get("file", "")
        stem = Path(file_ref).stem
        if stem in stem_to_path:
            batch_name_to_path[entry["name"]] = stem_to_path[stem]

    # Compute "touched" sets: Edits: paths plus all Move sources and targets.
    # Both Move endpoints count as touched for overlap detection because the
    # implementer reads the source and writes the target during a rename.
    batch_edits: dict[str, set[str]] = {}
    for name, path in batch_name_to_path.items():
        touched = _parse_edits_only(path)
        for src, dst in parse_moves(path):
            touched.add(src)
            touched.add(dst)
        batch_edits[name] = touched

    errors: list[dict] = []
    names = sorted(batch_name_to_path.keys())  # stable order for deterministic output

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a_name = names[i]
            b_name = names[j]

            # Parallel-eligible iff neither is a transitive ancestor of the other.
            if b_name in ancestors.get(a_name, set()):
                continue
            if a_name in ancestors.get(b_name, set()):
                continue

            overlap = batch_edits.get(a_name, set()) & batch_edits.get(b_name, set())
            for path in sorted(overlap):
                # Emit one finding per (path, sorted-pair); if a_name < b_name the
                # condition is always True here because names is sorted.
                if a_name < b_name:
                    errors.append({
                        "check": "parallel-modifies-overlap",
                        "batch": a_name,
                        "card": None,
                        "path": path,
                        "message": (
                            f"path '{path}' in Edits: of parallel-eligible "
                            f"batches '{a_name}' and '{b_name}'"
                        ),
                    })

    return errors


# ---------------------------------------------------------------------------
# Check 5b — depends-on-batch-mismatch
# ---------------------------------------------------------------------------

def _check_depends_on_batch_mismatch(
    batch_files: list[Path],
    overview_text: str,
) -> list[dict]:
    try:
        batches = extract_batch_index(overview_text)
    except PlanDAGError:
        # Check 4 has already recorded the parse error; don't double-report.
        return []

    number_to_name = {
        entry["number"]: entry["name"]
        for entry in batches
        if "number" in entry
    }

    # Map batch name -> batch file path via the index's `file:` field.
    stem_to_path: dict[str, Path] = {bf.stem: bf for bf in batch_files}
    batch_name_to_path: dict[str, Path] = {}
    for entry in batches:
        file_ref = entry.get("file", "")
        stem = Path(file_ref).stem
        if stem in stem_to_path:
            batch_name_to_path[entry["name"]] = stem_to_path[stem]

    # Parse per-batch depends-on from batch files.
    batch_side_deps: dict[str, list[str]] = {}
    for name, path in batch_name_to_path.items():
        try:
            text = path.read_text(encoding="utf-8")
            # Extract YAML block between ``` ```yaml ``` and the next ``` ```.
            lines = text.splitlines()
            start_idx = None
            end_idx = None
            for i, line in enumerate(lines):
                if line.strip() == "```yaml":
                    start_idx = i
                elif start_idx is not None and line.strip() == "```":
                    end_idx = i
                    break
            if start_idx is not None and end_idx is not None:
                yaml_text = "\n".join(lines[start_idx + 1:end_idx])
                parsed = yaml.safe_load(yaml_text) or {}
            else:
                parsed = {}
            deps = parsed.get("depends-on", [])
            # Normalize: translate ints to names, pass strings through.
            normalized: list[str] = []
            for dep in deps:
                if isinstance(dep, int):
                    resolved = number_to_name.get(dep)
                    if resolved is not None:
                        normalized.append(resolved)
                else:
                    normalized.append(dep)
            batch_side_deps[name] = normalized
        except Exception:
            # If batch file parsing fails, skip (other checks will catch it).
            batch_side_deps[name] = []

    # Get overview-side normalized depends-on.
    overview_side_deps = resolve_deps_as_names(batches)

    errors: list[dict] = []
    for name in batch_name_to_path.keys():
        batch_deps = set(batch_side_deps.get(name, []))
        overview_deps = set(overview_side_deps.get(name, []))
        if batch_deps != overview_deps:
            errors.append({
                "check": "depends-on-batch-mismatch",
                "batch": name,
                "card": None,
                "path": None,
                "message": (
                    f"per-batch file depends-on={sorted(batch_deps)} "
                    f"disagrees with overview Batch Index "
                    f"depends-on={sorted(overview_deps)}"
                ),
            })

    return errors


# ---------------------------------------------------------------------------
# Check 6 — reads-not-backtick-path
# ---------------------------------------------------------------------------

def _check_ref_not_backtick_path(batch_files: list[Path]) -> list[dict]:
    errors: list[dict] = []

    for batch_path in batch_files:
        text = batch_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        current_card: int | None = None

        i = 0
        while i < len(lines):
            line = lines[i]

            # Track enclosing card number.
            m_card = re.match(r"^###\s+Card\s+(\d+)\s*:", line)
            if m_card:
                current_card = int(m_card.group(1))

            m_header = _RE_REFS_HEADER.match(line)
            if m_header:
                inline = m_header.group("inline").strip()
                if inline:
                    # Single-line form.
                    if inline.lower() == "none":
                        i += 1
                        continue  # exempt

                    # Check for line-range suffixes in backtick tokens.
                    backtick_tokens = re.findall(r"`([^`]+)`", inline)
                    for tok in backtick_tokens:
                        if _RE_LINE_RANGE.search(tok):
                            errors.append({
                                "check": "reads-not-backtick-path",
                                "batch": batch_path.stem,
                                "card": current_card,
                                "path": tok,
                                "message": (
                                    f"path token has line-range suffix: `{tok}`"
                                ),
                            })

                    # Check for prose alongside backtick tokens.
                    cleaned = re.sub(r"`[^`]+`", "", inline).replace(",", "").strip()
                    if cleaned:
                        errors.append({
                            "check": "reads-not-backtick-path",
                            "batch": batch_path.stem,
                            "card": current_card,
                            "path": inline,
                            "message": (
                                f"Context/Edits/Creates inline value contains prose "
                                f"alongside backtick path: {inline!r}"
                            ),
                        })

                    i += 1
                    continue

                # Multi-line form — consume sub-bullets.
                j = i + 1
                while j < len(lines):
                    sm = _RE_REFS_SUB.match(lines[j])
                    if not sm:
                        break
                    sub_content = sm.group(1).strip()
                    bt_matches = re.findall(r"`[^`]+`", sub_content)

                    if not bt_matches:
                        errors.append({
                            "check": "reads-not-backtick-path",
                            "batch": batch_path.stem,
                            "card": current_card,
                            "path": sub_content,
                            "message": (
                                f"sub-bullet has no backtick-wrapped path: {sub_content!r}"
                            ),
                        })
                    elif len(bt_matches) > 1:
                        errors.append({
                            "check": "reads-not-backtick-path",
                            "batch": batch_path.stem,
                            "card": current_card,
                            "path": sub_content,
                            "message": (
                                f"sub-bullet contains multiple backtick paths: {sub_content!r}"
                            ),
                        })
                    else:
                        tok = bt_matches[0][1:-1]  # strip surrounding backticks
                        if _RE_LINE_RANGE.search(tok):
                            errors.append({
                                "check": "reads-not-backtick-path",
                                "batch": batch_path.stem,
                                "card": current_card,
                                "path": tok,
                                "message": (
                                    f"path token has line-range suffix: `{tok}`"
                                ),
                            })
                        # Check for prose alongside the single backtick token.
                        cleaned_sub = re.sub(r"`[^`]+`", "", sub_content).strip()
                        if cleaned_sub:
                            errors.append({
                                "check": "reads-not-backtick-path",
                                "batch": batch_path.stem,
                                "card": current_card,
                                "path": sub_content,
                                "message": (
                                    f"sub-bullet contains prose alongside backtick path: "
                                    f"{sub_content!r}"
                                ),
                            })
                    j += 1

                i = j  # skip consumed sub-bullets
                continue

            i += 1

    return errors


# ---------------------------------------------------------------------------
# wiki-config-mutation check
# ---------------------------------------------------------------------------

def _check_wiki_config_mutation(batch_files: list[Path]) -> list[dict]:
    errors: list[dict] = []
    for batch_path in batch_files:
        writes = _parse_edits_only(batch_path) | _parse_creates_only(batch_path)
        if "mill-config.yaml" in writes:
            errors.append({
                "check": "wiki-config-mutation",
                "batch": batch_path.stem,
                "card": None,
                "path": "mill-config.yaml",
                "message": (
                    "batch edits or creates mill-config.yaml — self-applying layout change risk; "
                    "use --skip-check wiki-config-mutation if a bootstrap card is present"
                ),
            })
    return errors


# ---------------------------------------------------------------------------
# Check 8 — all-files-touched-mismatch
# ---------------------------------------------------------------------------

def _check_all_files_touched_mismatch(
    overview_path: Path,
    batch_files: list[Path],
) -> list[dict]:
    text = overview_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Locate the ## All Files Touched heading.
    heading_idx: int | None = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+All Files Touched", line):
            heading_idx = i
            break

    if heading_idx is None:
        return []  # Section is optional; silent skip.

    # Parse bullet list under the heading.
    overview_set: set[str] = set()
    for line in lines[heading_idx + 1:]:
        if line.startswith("## "):
            break
        m = re.match(r"^\s*-\s+`([^`]+)`", line)
        if m:
            overview_set.add(m.group(1))

    # Compute cards_set = union of Edits: + Creates: + Move targets across all cards.
    # Deletes: tokens and Move sources are excluded per issue #494 and the
    # move-endpoint-accounting Shared Decision (sources disappear like Deletes;
    # targets appear like Creates and must be listed in All Files Touched).
    cards_set: set[str] = set()
    for batch_path in batch_files:
        cards_set |= _parse_edits_only(batch_path)
    # Add Creates: tokens via compute_creates_union.
    cards_set |= compute_creates_union(overview_path.parent)
    # Add Move targets: they behave like Creates: tokens (new files appear after
    # the rename step) and must appear in the overview's All Files Touched section.
    _, move_targets = compute_moves_union(overview_path.parent)
    cards_set |= move_targets

    errors: list[dict] = []
    for p in sorted(overview_set - cards_set):
        errors.append({
            "check": "all-files-touched-mismatch",
            "batch": None,
            "card": None,
            "path": p,
            "message": (
                f"path '{p}' listed in overview's All Files Touched "
                f"but not in any card's Edits: or Creates:"
            ),
        })
    for p in sorted(cards_set - overview_set):
        errors.append({
            "check": "all-files-touched-mismatch",
            "batch": None,
            "card": None,
            "path": p,
            "message": (
                f"path '{p}' in card Edits:/Creates: but missing "
                f"from overview's All Files Touched"
            ),
        })
    return errors


# ---------------------------------------------------------------------------
# verify-not-isolated check
# ---------------------------------------------------------------------------

def _check_verify_not_isolated(batch_files: list[Path], project_root: Path) -> list[dict]:
    errors: list[dict] = []
    for batch_path in batch_files:
        text = batch_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        start_idx = None
        end_idx = None
        for i, line in enumerate(lines):
            if line.strip() == "```yaml":
                start_idx = i
            elif start_idx is not None and line.strip() == "```":
                end_idx = i
                break
        if start_idx is None or end_idx is None:
            continue
        yaml_text = "\n".join(lines[start_idx + 1:end_idx])
        try:
            parsed = yaml.safe_load(yaml_text) or {}
        except Exception:
            continue
        verify = parsed.get("verify")
        if verify is None or not isinstance(verify, str):
            continue
        verify_stripped = verify.strip()
        if not verify_stripped:
            continue

        # Check if this is a Python project by looking for markers at the project root
        # or in plugins/mill/ subdirectory.
        is_python_project = (
            (project_root / "pyproject.toml").exists()
            or (project_root / "setup.py").exists()
            or (project_root / "setup.cfg").exists()
            or (project_root / "plugins" / "mill" / "pyproject.toml").exists()
        )

        # Only require PYTHONPATH= prefix for Python projects.
        if is_python_project and not verify_stripped.startswith("PYTHONPATH="):
            errors.append({
                "check": "verify-not-isolated",
                "batch": batch_path.stem,
                "card": None,
                "path": verify,
                "message": "verify command missing PYTHONPATH= prefix",
            })
    return errors


# ---------------------------------------------------------------------------
# verify-full-suite check
# ---------------------------------------------------------------------------

def _check_verify_full_suite(batch_files: list[Path]) -> list[dict]:
    errors: list[dict] = []
    for batch_path in batch_files:
        text = batch_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        start_idx = None
        end_idx = None
        for i, line in enumerate(lines):
            if line.strip() == "```yaml":
                start_idx = i
            elif start_idx is not None and line.strip() == "```":
                end_idx = i
                break
        if start_idx is None or end_idx is None:
            continue
        yaml_text = "\n".join(lines[start_idx + 1:end_idx])
        try:
            parsed = yaml.safe_load(yaml_text) or {}
        except Exception:
            continue
        verify = parsed.get("verify")
        if verify is None or not isinstance(verify, str):
            continue
        verify_stripped = verify.strip()
        if not verify_stripped:
            continue
        if "run-all.py" in verify_stripped and "-k " not in verify_stripped and "--only " not in verify_stripped:
            errors.append({
                "check": "verify-full-suite",
                "batch": batch_path.stem,
                "card": None,
                "path": verify,
                "message": "verify command invokes run-all.py without a filter (-k pattern); use '-k <pattern>' or '--only <files>' to scope the run",
            })
    return errors


# ---------------------------------------------------------------------------
# Check 9 — out-of-worktree-target
# ---------------------------------------------------------------------------

def _check_out_of_worktree_target(
    batch_files: list[Path],
    project_root: Path,
) -> list[dict]:
    errors: list[dict] = []
    wt = project_root.resolve()

    for batch_path in batch_files:
        edits = _parse_edits_only(batch_path)
        creates = _parse_creates_only(batch_path)
        tokens = edits | creates

        for token in tokens:
            if token.lower() == "none":
                continue

            # Expand ~ and resolve to absolute path
            expanded = os.path.expanduser(token)
            candidate = Path(expanded)
            if not candidate.is_absolute():
                candidate = project_root / expanded
            resolved = candidate.resolve()

            # Check if resolved path is inside worktree
            if resolved != wt and wt not in resolved.parents:
                errors.append({
                    "check": "out-of-worktree-target",
                    "batch": batch_path.stem,
                    "card": None,
                    "path": token,
                    "message": (
                        f"Edits/Creates target '{token}' resolves outside the worktree root; "
                        "home-dir and absolute targets must be handled manually, not by the implementer"
                    ),
                })

    return errors


# ---------------------------------------------------------------------------
# Check 10 — batch-oversized (note: check 9 above)
# ---------------------------------------------------------------------------

def _check_batch_oversized(
    batch_files: list[Path],
    project_root: Path,
    root: str | None,
    *,
    max_cards: int,
    max_context_tokens: int,
    wiki_root: Path | None = None,
    git_root: Path | None = None,
) -> list[dict]:
    errors: list[dict] = []
    for batch_path in batch_files:
        text = batch_path.read_text(encoding="utf-8")
        cards = _parse_cards(text)
        card_count = len(cards)

        # Check 1: card count
        if card_count > max_cards:
            errors.append({
                "check": "batch-oversized",
                "batch": batch_path.stem,
                "card": None,
                "path": None,
                "message": f"batch has {card_count} cards (cap {max_cards})",
            })

        # Check 2: context size (token estimate)
        # Collect Context/Edits/Creates tokens from the batch
        all_refs = parse_batch_refs(batch_path)
        deletes = _parse_deletes_only(batch_path)

        # Move sources exist pre-implementation and are read by the implementer;
        # add them to the estimate even when they are not listed in Context:/Edits:.
        # Move targets do not exist yet (mirroring how Creates: targets are excluded);
        # subtract them so they never inflate the estimate.
        moves = parse_moves(batch_path)
        move_sources = {src for src, _ in moves}
        move_targets = {dst for _, dst in moves}

        # Subtract deleted and move-target tokens, then add move sources.
        context_tokens = (set(all_refs) - deletes - move_targets) | move_sources

        # Resolve existing paths, skipping those that don't exist (like Creates targets)
        if context_tokens:
            resolved = resolve_existing_paths(
                list(context_tokens),
                project_root,
                root,
                wiki_root=wiki_root,
                git_root=git_root,
            )

            # Sum byte sizes and divide by 4 for token estimate
            total_bytes = sum(p.stat().st_size for p in resolved)
            token_estimate = total_bytes // 4

            if token_estimate > max_context_tokens:
                errors.append({
                    "check": "batch-oversized",
                    "batch": batch_path.stem,
                    "card": None,
                    "path": None,
                    "message": (
                        f"batch context ~{token_estimate} tokens (cap {max_context_tokens})"
                    ),
                })

    return errors


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run(
    plan_dir: Path,
    project_root: Path,
    *,
    root: str | None = None,
    wiki_root: Path | None = None,
    git_root: Path | None = None,
    skip_checks: frozenset[str] = frozenset(),
    max_cards_per_batch: int = 10,
    max_batch_context_tokens: int = 120000,
) -> list[dict]:
    """Validate plan files in plan_dir.

    Returns a sorted list of error dicts with keys:
    {check, batch, card, path, message}.

    Checks 1, 2, 3, 4, 5, 6, 8 from issue #10, plus wiki-config-mutation,
    verify-not-isolated, out-of-worktree-target, batch-oversized, and five
    Move-specific checks (move-format, move-redundant, move-source-missing,
    move-target-collision, move-mechanic-missing).

    Args:
        plan_dir: Directory containing the plan files (00-overview.md + batch files).
        project_root: Root of the project (typically the worktree root).
        root: Optional root subfolder for source refs (e.g. "subproject1"); when set,
            refs resolve to git_root/root/raw first, then project_root/root/raw.
        wiki_root: Optional wiki root path; when provided, refs starting with "wiki/"
            are resolved against wiki_root instead of project_root.
        git_root: Optional repo root; when provided, refs resolve to git_root/root/raw
            before falling back to project_root-based candidates (addresses #471 layout).
        skip_checks: Set of check names to skip (e.g. {"wiki-config-mutation"}).
        max_cards_per_batch: Maximum cards per batch before batch-oversized is raised.
        max_batch_context_tokens: Maximum context token estimate before batch-oversized is raised.
    """
    overview_path = plan_dir / "00-overview.md"
    if not overview_path.exists():
        return [{
            "check": "missing-overview",
            "batch": None,
            "card": None,
            "path": str(overview_path),
            "message": "00-overview.md not found",
        }]

    root_from_overview = _load_root_from_overview(overview_path)
    effective_root = root if root is not None else root_from_overview

    batch_files = sorted(
        p for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"
    )
    overview_text = overview_path.read_text(encoding="utf-8")
    creates_union = compute_creates_union(plan_dir)
    deletes_union = compute_deletes_union(plan_dir)
    # Move sources behave like Deletes (disappear) and targets like Creates (appear).
    # Computed once here and threaded into the checks that need them.
    moves_sources, moves_targets = compute_moves_union(plan_dir)

    errors: list[dict] = []

    errors.extend(_check_non_existent_path(
        batch_files, project_root, effective_root, creates_union, deletes_union, moves_targets,
        wiki_root=wiki_root,
        git_root=git_root,
    ))
    errors.extend(_check_card_missing_field(batch_files))
    errors.extend(_check_card_numbering(batch_files))
    errors.extend(_check_depends_on_unknown(overview_text, overview_path))
    errors.extend(_check_depends_on_batch_mismatch(batch_files, overview_text))
    errors.extend(_check_parallel_modifies_overlap(batch_files, overview_text))
    errors.extend(_check_ref_not_backtick_path(batch_files))
    errors.extend(_check_verify_not_isolated(batch_files, project_root))
    errors.extend(_check_verify_full_suite(batch_files))
    errors.extend(_check_wiki_config_mutation(batch_files))
    errors.extend(_check_all_files_touched_mismatch(overview_path, batch_files))
    errors.extend(_check_out_of_worktree_target(batch_files, project_root))
    errors.extend(_check_batch_oversized(
        batch_files, project_root, effective_root,
        max_cards=max_cards_per_batch,
        max_context_tokens=max_batch_context_tokens,
        wiki_root=wiki_root,
        git_root=git_root,
    ))
    # Move-specific checks (added by batch validator-move-checks).
    errors.extend(_check_move_format(batch_files))
    errors.extend(_check_move_redundant(batch_files))
    errors.extend(_check_move_source_missing(
        batch_files, project_root, effective_root, creates_union, moves_targets,
        wiki_root=wiki_root,
        git_root=git_root,
    ))
    errors.extend(_check_move_target_collision(
        batch_files, project_root, effective_root,
        wiki_root=wiki_root,
        git_root=git_root,
    ))
    errors.extend(_check_move_mechanic_missing(batch_files))

    errors.sort(key=lambda e: (e["batch"] or "", e["card"] or 0, e["check"]))
    if skip_checks:
        errors = [e for e in errors if e["check"] not in skip_checks]
    return errors
