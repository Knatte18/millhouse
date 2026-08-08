"""
Static plan pre-validator.

Checks plan files for structural issues BEFORE invoking the LLM reviewer.
Used by millpy-validate-plan.py (standalone CLI) and by millpy-review-plan.py (auto-run gate before
each review round).

Public API:
    run(plan_dir, project_root, *, root=None, wiki_root=None, git_root=None, skip_checks=frozenset()) -> list[dict]
    Validate plan files in plan_dir. Returns a sorted list of error dicts.
    Each error dict has keys: {check, batch, card, path, message}.

Checks performed (check keys):
    non-existent-path — (#10 check 1) Context:/Edits:/Creates: refs that don't exist on disk and are
        not Creates:/Moves: targets
    card-missing-field — (#10 check 2) Cards missing one of the required fields (Context, Edits,
        Creates, Deletes, Moves, Requirements, Commit)
    card-numbering — (#10 check 3) Non-sequential or cross-batch-duplicate card numbers
    depends-on-unknown — (#10 check 4) depends-on entries referencing unknown batch names
    depends-on-batch-mismatch — per-batch file's depends-on disagrees with overview Batch Index
        depends-on for the same batch
    parallel-modifies-overlap — (#10 check 5) Parallel-eligible batches both modifying the same file
        (includes Move endpoints)
    reads-not-backtick-path — (#10 check 6) Context:/Edits:/Creates: entries not in backtick-only
        format (exempts bare 'none')
    all-files-touched-mismatch — (#10 check 8) Mismatch between overview's All Files Touched section
        and cards' Edits:/Creates:/Moves: targets
    verify-not-isolated — per-batch or overview-level verify: command does not start with
        PYTHONPATH= reset prefix
    verify-full-suite — per-batch or overview-level verify: invokes run-all.py without a -k/--only
        filter
    verify-malformed-cwd — verify: mapping fails to parse via _plan_dag.parse_verify_field (bad cwd
        or missing command)
    verify-mixed-cwd — batches in the plan resolve the {cwd, command} mapping form to more than one
        distinct cwd
    verify-unrelated-test-file — verify: --only test-file token untouched by its own batch and
        byte-identical to the parent branch
    verify-excludes-edited-tagged-test — Go-specific (gated on go.mod presence);
        discovers each edited _test.go file's custom tag(s) from its own //go:build expression via
        denylist (GOOS/GOARCH/reserved-word/release-version tags excluded), and flags every edited
        tagged file independently whose batch verify: command lacks a matching -tags flag
    wiki-config-mutation — batch Edits:/Creates: contains mill-config.yaml (self-applying layout
        risk)
    plugin-manifest-context-missing — batch Creates:/Edits:/Deletes: touches plugins/mill/agents/
        but plugin.json is not in that batch's Context: or Edits:
    context-completeness — a card's Requirements: references a resolvable file-path-shaped backtick
        token absent from that card's own Context:/Edits:/Creates:/Deletes:/Moves:-source
    requirements-quote-indent-drift — a card's Requirements: fenced block quoting exact source text
        that only byte-matches its own Edits: file(s) after stripping a fixed per-line indent
        (list-continuation-indentation bug signature)
    move-format — Moves: sub-bullet does not match the `src` -> `dst` grammar
    move-redundant — a path is both a Move endpoint and in Creates:/Deletes: of the same batch
    move-source-missing — Move source does not exist on disk and is not created/relocated by an
        earlier batch
    move-target-collision — Move target already exists, is targeted by multiple batches, or collides
        with a Creates: in another batch
    move-mechanic-missing — batch has non-empty Moves: but is missing a '## Rename mechanic' section
    commit-none-with-content — a card's Commit: is the literal 'none' sentinel but its
        Edits:/Creates:/Deletes:/Moves: has non-none content
"""
from __future__ import annotations

import os
import re
import yaml
from pathlib import Path

import _plan_dag
import _subprocess_util
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

# Matches the Moves: header bullet (kept separate from _RE_REFS_HEADER because Moves sub-bullets use a two-path grammar that the reads-not-backtick-path validator rejects when mixed into the single-path fields above).
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

# Captures the body of a fenced code block (```<lang>\n<body>```), non-greedy across multiple lines.
# Used by requirements-quote-indent-drift to pull the literal quoted text out of a Requirements: field's fence(s).
_RE_FENCE_BODY = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)

# Captures everything after "--only " in a verify: command string, so the candidate test-file tokens can be split off the flag's argument list.
_RE_VERIFY_ONLY = re.compile(r"--only\s+(.+)$")

# A bare basename ending in .py or .go -- the shape a test-file token in a verify: --only list takes.
# Naturally stops before the next --flag-shaped token since flags don't match this pattern.
_RE_TEST_FILE_TOKEN = re.compile(r"^[\w.-]+\.(py|go)$")

# Required card fields. "Moves" sits after "Deletes" and before "Requirements" per the moves-grammar Shared Decision.
_REQUIRED_CARD_FIELDS = ["Context", "Edits", "Creates", "Deletes", "Moves", "Requirements", "Commit"]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_cards(batch_text: str) -> list[tuple[int, list[str]]]:
    """Return list of (card_number, card_lines) pairs.

    Each card block starts at a ``### Card N:`` line and ends just before the next ``### `` heading
    or at EOF.
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
    but restricted to ``- **Edits:**`` headers.
    Filters ``none`` (case-insensitive) per the existing convention.
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
    but restricted to ``- **Creates:**`` headers.
    Filters ``none`` (case-insensitive) per the existing convention.
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
    but restricted to ``- **Deletes:**`` headers.
    Filters ``none`` (case-insensitive) per the existing convention.
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


def _parse_context_only(batch_path: Path) -> set[str]:
    """Extract raw path tokens from a batch file's Context: lines only.

    Same single-line / multi-line logic as parse_batch_refs in _review_common,
    but restricted to ``- **Context:**`` headers.
    Filters ``none`` (case-insensitive) per the existing convention.
    """
    text = batch_path.read_text(encoding="utf-8")
    tokens: set[str] = set()
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = _RE_REFS_HEADER.match(lines[i])
        if m and m.group(1) == "Context":
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

    Scans every ``- **Moves:**`` header in each batch file.
    An inline ``none`` (case-insensitive) is silently accepted.
    For all other headers each sub-bullet is compared against ``_RE_MOVE_PAIR`` (`` `src` -> `dst`
    ``).
    A sub-bullet that is missing the arrow, has only one backtick path, or carries prose yields an
    error dict with ``check="move-format"``.

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

    For each batch file, collects every Move source and target via ``parse_moves``, then intersects
    with the batch's own ``Creates:`` and ``Deletes:`` tokens.
    An identical path appearing in both a ``Moves:`` field and a ``Creates:``/``Deletes:`` field
    within the SAME batch is redundant -- the implementer should use one or the other, not both.

    Only an exact-token match triggers the error.
    A ``Moves:`` target that is a DIFFERENT path from any ``Creates:`` entry (the canonical
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

    Modelled on the Deletes branch of ``_check_non_existent_path``: a Move source that is missing on
    disk is only an error when it cannot be explained by an earlier batch creating it
    (``creates_union``) or an earlier Move relocating a different file to that path
    (``moves_targets``).
    Both suppression sets are plan-wide, so chained moves (batch A moves X to Y; batch B moves Y to
    Z) do not generate a false positive for batch B's source Y.

    Error dict shape: ``{check, batch, card, path, message}``.

    Args:
        batch_files: Sorted list of batch file paths to validate.
        project_root: Root of the project (worktree root).
        root: Optional root subfolder for source refs (threaded to ``resolve_existing_paths``).
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
            # Suppress when an earlier batch creates the file or moves something else to this path, making it available before this Move runs.
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
    3. The target appears as a ``Creates:`` token in a DIFFERENT batch (cross-batch collision).
        Same-batch overlap is ``move-redundant``'s responsibility;
        this check intentionally skips it to avoid double-reporting.

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
    # Build per-batch move-target sets and per-batch creates sets for accurate cross-batch collision detection.
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
            # Same-batch overlap is move-redundant's job;
            # skip it here.
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

    The ``plan-batch.md`` template includes this section to guide the implementer on the correct
    ``git mv`` + surgical-edit workflow.
    When a batch declares at least one non-empty ``Moves:`` pair via ``parse_moves``, the batch file
    text must contain a heading line matching ``^##\\s+Rename mechanic\\b`` (the canonical section
    name).
    Batches where every ``Moves:`` field carries the ``none`` sentinel produce an empty
    ``parse_moves`` result and are skipped.

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
    - ``deletes_union``: paths that will be deleted are not flagged for general refs (the file may
    disappear before this batch runs).
    - ``moves_targets``: paths that are Moves: destinations are not flagged because they will be
    created by the rename step (a downstream card editing a Move target must not raise
    non-existent-path).

    Move-source existence is NOT checked here;
    that is solely ``_check_move_source_missing``'s responsibility (card 6).
    This function continues to operate only on the general Context/Edits/Creates and Deletes tokens
    that ``parse_batch_refs`` already parses (it does not parse Moves: bullets).

    Error dict shape: ``{check, batch, card, path, message}``.
    """
    errors: list[dict] = []
    for batch_path in batch_files:
        raw_refs = parse_batch_refs(batch_path)
        deletes_only = _parse_deletes_only(batch_path)
        general_refs = set(raw_refs) - deletes_only

        # General refs (Context/Edits/Creates): missing on disk is suppressed when the token is in creates_union, deletes_union, OR moves_targets.
        # The moves_targets suppression prevents false errors on downstream cards that reference a not-yet-existing Move destination in their Context:/Edits:.
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

        # Deletes refs: missing on disk is suppressed only if in creates_union (cross-batch: an earlier batch creates it, this card deletes it).
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


def _card_field_is_none(card_text: str, field: str) -> bool:
    """Return True if ``field:`` in a single card's text has zero content.

    ``field`` is one of ``"Edits"``, ``"Creates"``, ``"Deletes"`` (matched via ``_RE_REFS_HEADER``)
    or ``"Moves"`` (matched via ``_RE_MOVES_HEADER``, since its sub-bullets use the two-path ``src``
    -> ``dst`` grammar rather than the other fields' bare-path grammar).
    Mirrors ``_parse_edits_only``'s single-line-vs-multi-line sub-bullet logic,
    but scoped to one already-extracted card's text rather than a whole batch file.

    A field counts as "all none" when its inline value is the literal ``none`` (case-insensitive).
    Any other inline value,
    or any sub-bullet at all under an empty inline value, counts as content.
    A card with no matching header line at all also counts as "all none" here -- a missing field is
    ``_check_card_missing_field``'s concern, not this helper's.
    """
    lines = card_text.splitlines()
    i = 0
    while i < len(lines):
        if field == "Moves":
            m = _RE_MOVES_HEADER.match(lines[i])
        else:
            m = _RE_REFS_HEADER.match(lines[i])
            if m and m.group(1) != field:
                m = None
        if m:
            inline = m.group("inline").strip()
            if inline:
                return inline.lower() == "none"
            # Empty inline value: content (if any) lives in sub-bullets.
            # The "none" sentinel is always written inline, never as a sub-bullet, so any sub-bullet at all means non-none content.
            j = i + 1
            has_sub_bullet = _RE_REFS_SUB.match(lines[j]) is not None if j < len(lines) else False
            return not has_sub_bullet
        i += 1
    return True


# ---------------------------------------------------------------------------
# Check 2b — commit-none-with-content
# ---------------------------------------------------------------------------

def _check_commit_none_with_content(batch_files: list[Path]) -> list[dict]:
    """
    Reject `Commit: none` cards that still declare real Edits/Creates/Deletes/Moves.

    `Commit: none` marks a verification-only card (issue #664) whose sole job is confirming earlier
    work (e.g.
    a grep confirming an earlier card's edits landed) -- it must produce zero diff of its own.
    For each batch file, ``_plan_dag.parse_commit_none_card_ids`` finds the cards declaring `Commit:
    none`;
    for each such card, this check re-parses the card's own text via ``_parse_cards`` and inspects
    its Edits:/Creates:/Deletes:/Moves: fields, scoped to just that card via
    ``_card_field_is_none``.
    Any field with non-none content yields one error per offending field, matching
    ``_check_card_missing_field``'s one-error-per-offense convention.

    Error dict shape: ``{check, batch, card, path, message}``.

    Args:
        batch_files: Sorted list of batch file paths to validate.

    Returns:
        List of error dicts, one per offending field on a `Commit: none` card.
    """
    errors: list[dict] = []
    for batch_path in batch_files:
        text = batch_path.read_text(encoding="utf-8")
        none_card_ids = _plan_dag.parse_commit_none_card_ids(text)
        if not none_card_ids:
            continue
        cards_by_num = dict(_parse_cards(text))
        for card_num in sorted(none_card_ids):
            card_lines = cards_by_num.get(card_num)
            if card_lines is None:
                continue
            card_text = "\n".join(card_lines)
            for field in ("Edits", "Creates", "Deletes", "Moves"):
                if not _card_field_is_none(card_text, field):
                    errors.append({
                        "check": "commit-none-with-content",
                        "batch": batch_path.stem,
                        "card": card_num,
                        "path": None,
                        "message": (
                            f"card {card_num} has Commit: none but non-none {field}: "
                            f"-- verification-only cards must have zero diff"
                        ),
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
    # Both Move endpoints count as touched for overlap detection because the implementer reads the source and writes the target during a rename.
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
                # Emit one finding per (path, sorted-pair);
                # if a_name < b_name the condition is always True here because names is sorted.
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
# plugin-manifest-context-missing check
# ---------------------------------------------------------------------------

# Directory prefix identifying an agent-definition file.
# Any batch whose Creates:/Edits:/Deletes: touches a path under this prefix must also bulk the plugin manifest so a bulk-mode reviewer can verify platform claims about agent registration (issue #714).
_AGENTS_DIR_PREFIX = "plugins/mill/agents/"

# The plugin manifest declaring the agents array.
# A batch that registers or removes an agent typically edits this file directly;
# it must be reachable in the reviewer's bulked context either way.
_PLUGIN_MANIFEST_PATH = "plugins/mill/.claude-plugin/plugin.json"


def _check_plugin_manifest_context_missing(batch_files: list[Path]) -> list[dict]:
    """
    Require the plugin manifest in Context:/Edits: for batches touching agents/.

    A bulk-mode plan reviewer cannot fetch files on its own -- it only sees what the backend bulks
    into its prompt from each batch's Context: and Edits: fields.
    When a batch's Creates:/Edits:/Deletes: touches a file under ``plugins/mill/agents/``
    (registering, editing, or removing an agent definition), the reviewer needs ``plugin.json`` in
    context to verify the corresponding platform claim (e.g.
    that the agent is correctly wired into the manifest's ``agents`` array).
    This check flags a batch that touches ``plugins/mill/agents/`` but omits the manifest from both
    ``Context:`` and ``Edits:``.

    Error dict shape: ``{check, batch, card, path, message}``.

    Args:
        batch_files: Sorted list of batch file paths to validate.

    Returns:
        List of error dicts, one per offending batch.
    """
    errors: list[dict] = []
    for batch_path in batch_files:
        touched = (
            _parse_creates_only(batch_path)
            | _parse_edits_only(batch_path)
            | _parse_deletes_only(batch_path)
        )
        if not any(t.startswith(_AGENTS_DIR_PREFIX) for t in touched):
            continue
        context = _parse_context_only(batch_path)
        edits = _parse_edits_only(batch_path)
        if _PLUGIN_MANIFEST_PATH not in context and _PLUGIN_MANIFEST_PATH not in edits:
            errors.append({
                "check": "plugin-manifest-context-missing",
                "batch": batch_path.stem,
                "card": None,
                "path": _PLUGIN_MANIFEST_PATH,
                "message": (
                    f"batch touches a file under '{_AGENTS_DIR_PREFIX}' but "
                    f"'{_PLUGIN_MANIFEST_PATH}' is not in Context: or Edits:"
                ),
            })
    return errors


# ---------------------------------------------------------------------------
# context-completeness check (#742)
# ---------------------------------------------------------------------------

# Prohibition-marker substrings: a Requirements: sentence containing one of these (lowercased) names a file the card must NOT act on, not an unlisted read dependency, so a backtick token on that line is exempt from flagging.
_PROHIBITION_MARKERS = (
    "forbid",
    "never touch",
    "must not touch",
    "do not touch",
    "not touch",
)

# A backtick-quoted token counts as path-candidate-shaped when it contains a path separator or ends with one of these extensions; anything else (a JSON key, a function name, a sentinel string) is silently ignored.
_PATH_CANDIDATE_EXTENSIONS = (".py", ".go", ".cs", ".ts", ".md", ".yaml", ".yml", ".json")


def _extract_requirements_text(card_text: str) -> str | None:
    """Return the body text of a card's ``Requirements:`` field, or ``None``.

    Locates the ``- **Requirements:**`` header line and collects that line's trailing text plus
    every subsequent line up to (but not including) the next ``- **<Field>:**`` header or the end of
    ``card_text``.
    Returns ``None`` when no ``Requirements:`` header line is found at all -- a missing field is
    ``card-missing-field``'s concern, not this check's.
    """
    lines = card_text.splitlines()
    header_re = re.compile(r"^-\s*\*\*Requirements:\*\*")
    any_field_header_re = re.compile(r"^-\s*\*\*[A-Za-z]+:\*\*")

    for i, line in enumerate(lines):
        if header_re.match(line):
            collected = [line]
            j = i + 1
            while j < len(lines) and not any_field_header_re.match(lines[j]):
                collected.append(lines[j])
                j += 1
            return "\n".join(collected)
    return None


def _card_own_reference_set(card_text: str) -> set[str]:
    """Return the union of backtick tokens this card declares as its own.

    Combines every backtick-wrapped token found under this card's Context:/Edits:/Creates:/Deletes:
    headers (single-line or multi-line sub-bullet form) with the source-only half of its Moves:
    pairs (the destination half is deliberately excluded -- a Requirements: reference to a
    not-yet-existing Move target is not "already declared").
    """
    tokens: set[str] = set()
    lines = card_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _RE_REFS_HEADER.match(line)
        if m:
            inline = m.group("inline").strip()
            if inline:
                tokens.update(re.findall(r"`([^`]+)`", inline))
                i += 1
                continue
            j = i + 1
            while j < len(lines):
                sm = _RE_REFS_SUB.match(lines[j])
                if not sm:
                    break
                tokens.update(re.findall(r"`([^`]+)`", sm.group(1)))
                j += 1
            i = j
            continue
        i += 1

    for idx, line in enumerate(lines):
        m_moves = _RE_MOVES_HEADER.match(line)
        if not m_moves:
            continue
        inline = m_moves.group("inline").strip()
        if inline:
            # Inline "none" (or any other inline value) has no sub-bullets to walk.
            continue
        k = idx + 1
        while k < len(lines):
            sm = _RE_REFS_SUB.match(lines[k])
            if not sm:
                break
            pair_m = _RE_MOVE_PAIR.match(sm.group(1).strip())
            if pair_m:
                tokens.add(pair_m.group(1))
            k += 1

    return tokens


def _check_context_completeness(
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
    Flag a card's Requirements: prose citing a file absent from its own refs.

    A ``Requirements:`` field frequently prose-references a file the implementer must read or reason
    about;
    when that file is a genuine dependency it belongs in the card's own ``Context:``/``Edits:`` (or
    ``Creates:``/``Deletes:``/``Moves:``) so a bulk-mode reviewer actually sees it.
    This check heuristically detects the gap: for each card, every backtick-quoted, path-shaped
    token in ``Requirements:`` that independently resolves to a real file (on disk, or a plan-wide
    ``Creates:``/``Deletes:``/Moves-target reference) must also appear in that same card's own
    Context:/Edits:/Creates:/Deletes:/Moves:-source set.
    Two exemptions prevent false positives:

    1. Prohibition-marker sentences (e.g. "forbid touching `x.py`") name a file the card must NOT
    act on, not an unlisted dependency.
    2. Non-path-shaped or unresolvable tokens (JSON keys, function names, sentinel strings) are
    never flagged -- only genuine file references that this validator can independently confirm
    exist.

    Note: markdown's double-backtick-escape convention (`` `path` ``) is not detected by this regex;
    future citations needing that format should be aware they won't be checked by
    context-completeness.

    Error dict shape: ``{check, batch, card, path, message, line}``.

    Args:
        batch_files: Sorted list of batch file paths to validate.
        project_root: Root of the project (typically the worktree root).
        root: Optional root subfolder for source refs.
        creates_union: Plan-wide union of Creates: targets.
        deletes_union: Plan-wide union of Deletes: targets.
        moves_targets: Plan-wide union of Moves: destination paths.
        wiki_root: Optional wiki root path for wiki/-prefixed refs.
        git_root: Optional repo root for git_root-relative resolution.

    Returns:
        List of error dicts, one per unresolvable-elsewhere Requirements: reference.
    """
    errors: list[dict] = []
    backtick_re = re.compile(r"`([^`]+)`")

    for batch_path in batch_files:
        text = batch_path.read_text(encoding="utf-8")
        cards = _parse_cards(text)
        for card_num, card_lines in cards:
            card_text = "\n".join(card_lines)
            requirements_text = _extract_requirements_text(card_text)
            if requirements_text is None:
                continue

            requirements_lines = requirements_text.splitlines()
            own_refs: set[str] | None = None  # lazily computed per card

            for line in requirements_lines:
                for token in backtick_re.findall(line):
                    # Path-candidate shape only: contains a separator or ends with a recognized source-file extension.
                    if "/" not in token and not token.endswith(_PATH_CANDIDATE_EXTENSIONS):
                        continue

                    # Prohibition-marker exemption: the line naming this token forbids acting on it, so it is not an unlisted read dependency.
                    lowered_line = line.lower()
                    if any(marker in lowered_line for marker in _PROHIBITION_MARKERS):
                        continue

                    # Strip a trailing line-range suffix before testing resolvability and matching;
                    # the ORIGINAL token is kept for the emitted error's "path" field.
                    stripped_token = _RE_LINE_RANGE.sub("", token)

                    existing = resolve_existing_paths(
                        [stripped_token], project_root, root,
                        wiki_root=wiki_root, git_root=git_root,
                    )
                    existing_files = [p for p in existing if p.is_file()]
                    resolvable = (
                        bool(existing_files)
                        or stripped_token in creates_union
                        or stripped_token in deletes_union
                        or stripped_token in moves_targets
                    )
                    if not resolvable:
                        continue

                    if own_refs is None:
                        own_refs = _card_own_reference_set(card_text)

                    if stripped_token in own_refs:
                        continue
                    if "/" not in stripped_token and any(
                        Path(stripped_token).name == Path(entry).name for entry in own_refs
                    ):
                        continue

                    errors.append({
                        "check": "context-completeness",
                        "batch": batch_path.stem,
                        "card": card_num,
                        "path": token,
                        "message": (
                            f"card {card_num}'s Requirements: references '{token}' "
                            f"which is not in this card's "
                            f"Context:/Edits:/Creates:/Deletes:/Moves:"
                        ),
                        "line": line.strip(),
                    })

    return errors


def _strip_n_leading_spaces(text: str, n: int) -> str:
    """Strip up to ``n`` leading space characters from every line of ``text``.

    For each line (split via ``.splitlines()``), remove exactly ``n`` leading space characters when
    the line has at least that many;
    otherwise strip only however many leading spaces the line actually has (no error on short/blank
    lines).
    This is a FIXED per-line strip, not ``textwrap.dedent``'s common-minimum-strip -- per
    ``_mill/discussion.md``'s ``trigger-heuristic-near-miss`` Decision, ``textwrap.dedent`` silently
    misses drift when the true source excerpt has nonzero baseline indentation of its own.
    """
    stripped_lines = []
    for line in text.splitlines():
        leading = len(line) - len(line.lstrip(" "))
        strip_count = min(n, leading)
        stripped_lines.append(line[strip_count:])
    return "\n".join(stripped_lines)


def _card_edits_tokens(card_text: str) -> list[str]:
    """Return this card's own ``Edits:`` backtick tokens, in declaration order.

    Walks ``card_text``'s lines matching ``_RE_REFS_HEADER`` where the field name is ``Edits``,
    extracting either the inline value's backtick tokens or the following ``_RE_REFS_SUB``
    sub-bullets' tokens -- mirroring ``_card_own_reference_set``'s inline/sub-bullet walk, but
    scoped to the ``Edits`` field only and returned as an ordered list (not a set), since
    declaration order is load-bearing for requirements-quote-indent-drift's first-match tie-break.
    """
    tokens: list[str] = []
    lines = card_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _RE_REFS_HEADER.match(line)
        if m and m.group(1) == "Edits":
            inline = m.group("inline").strip()
            if inline:
                # An inline "none" naturally yields zero tokens, since "none" is not backtick-wrapped.
                tokens.extend(re.findall(r"`([^`]+)`", inline))
                i += 1
                continue
            j = i + 1
            while j < len(lines):
                sm = _RE_REFS_SUB.match(lines[j])
                if not sm:
                    break
                tokens.extend(re.findall(r"`([^`]+)`", sm.group(1)))
                j += 1
            i = j
            continue
        i += 1
    return tokens


def _requirements_fence_aware_body(card_lines: list[str]) -> str | None:
    """Return the full, fence-aware body of a card's ``Requirements:`` field.

    Locates the ``- **Requirements:**`` header line directly against ``card_lines`` (does NOT call
    ``_extract_requirements_text`` for this -- per ``_mill/discussion.md``'s
    ``fence-aware-boundary-detection`` Decision, that function returns a joined string, not an
    index).
    Returns ``None`` when no such header line exists.

    The header line itself unconditionally seeds the result (it also matches the stop-condition
    regex used below, so re-testing it would make the scan a permanent no-op).
    From the line after the header, walks forward over the ORIGINAL (untruncated) ``card_lines``,
    tracking a boolean ``in_fence`` that toggles on every line starting with ``` ``` ```. Collection
    stops at the first line matching a ``- **Field:**``-shaped header while ``in_fence`` is
    ``False``, or at the end of ``card_lines``. This re-scan exists so a fence quoting another
    SKILL.md's ``### Phase: X`` heading or ``- **Field:**``-shaped bullet is not mistaken for this
    field's own boundary, which would truncate the fence body.
    """
    header_re = re.compile(r"^-\s*\*\*Requirements:\*\*")
    any_field_header_re = re.compile(r"^-\s*\*\*[A-Za-z]+:\*\*")

    start = None
    for i, line in enumerate(card_lines):
        if header_re.match(line):
            start = i
            break
    if start is None:
        return None

    collected = [card_lines[start]]
    in_fence = False
    j = start + 1
    while j < len(card_lines):
        line = card_lines[j]
        if not in_fence and any_field_header_re.match(line):
            break
        if line.startswith("```"):
            in_fence = not in_fence
        collected.append(line)
        j += 1

    return "\n".join(collected)


def _check_requirements_quote_indent_drift(
    batch_files: list[Path],
    project_root: Path,
    root: str | None,
    *,
    wiki_root: Path | None = None,
    git_root: Path | None = None,
) -> list[dict]:
    """
    Flag a card's Requirements: fence that only byte-matches its own Edits: file(s) after stripping
    a fixed per-line indent.

    This is the list-continuation-indentation bug's exact signature: a ``Requirements:`` fence meant
    to quote exact source text as Edit-tool ``old_string`` bait silently picks up a uniform per-line
    indent from the surrounding Markdown list-continuation nesting, so the quoted text no longer
    byte-matches the real source file even though it "looks right" to a human or LLM reviewer.

    For each card with a non-empty Edits: field and a Requirements: field containing at least one
    fenced code block: for each fence, if the raw (unstripped) fence content is already a literal
    substring of some resolved Edits: file's content, the fence is clean -- no error.
    If not, search ascending strip amounts N = 1..40 (a fixed per-line leading-space strip, NOT
    textwrap.dedent's common-minimum-strip -- see _strip_n_leading_spaces) for the first N whose
    stripped fence content IS a literal substring of some resolved Edits: file (walked in the card's
    own Edits: declaration order, first match wins on ties).
    The first match wins and stops the search;
    a fence matching no N in range is an illustrative snippet showing new/desired-state code, not a
    drifted quote, and is silently skipped -- never flagged.

    Per _mill/discussion.md's match-target-edits-only Decision, only a card's own Edits: files are
    compared against (never Context:, Creates:, or other cards' files) -- those files already exist
    on disk by definition, so no creates_union/deletes_union/moves_targets threading is needed here
    (contrast _check_context_completeness).

    Error dict shape: ``{check, batch, card, path, message}``.

    Args:
        batch_files: Sorted list of batch file paths to validate.
        project_root: Root of the project (typically the worktree root).
        root: Optional root subfolder for source refs.
        wiki_root: Optional wiki root path for wiki/-prefixed refs.
        git_root: Optional repo root for git_root-relative resolution.

    Returns:
        List of error dicts, one per drifted fence.
    """
    errors: list[dict] = []

    for batch_path in batch_files:
        text = batch_path.read_text(encoding="utf-8")
        cards = _parse_cards(text)
        for card_num, card_lines in cards:
            card_text = "\n".join(card_lines)
            edits_tokens = _card_edits_tokens(card_text)
            if not edits_tokens:
                continue

            requirements_text = _requirements_fence_aware_body(card_lines)
            if requirements_text is None:
                continue

            fence_bodies = _RE_FENCE_BODY.findall(requirements_text)
            if not fence_bodies:
                continue

            # Resolve this card's own Edits: tokens to real on-disk files, preserving declaration order for the tie-break below.
            # Tokens that don't resolve (e.g.
            # a stale/typo'd Edits: entry) are silently dropped -- that's non-existent-path's concern, not this check's.
            resolved_contents: dict[str, str] = {}
            ordered_resolved_tokens: list[str] = []
            for token in edits_tokens:
                existing = resolve_existing_paths(
                    [token], project_root, root,
                    wiki_root=wiki_root, git_root=git_root,
                )
                if not existing:
                    continue
                # Python's read_text(newline=None) already performs universal newline translation, converting all line-ending styles to LF.
                content = existing[0].read_text(encoding="utf-8")
                resolved_contents[token] = content
                ordered_resolved_tokens.append(token)

            if not ordered_resolved_tokens:
                continue

            for fence_idx, fence_body in enumerate(fence_bodies, start=1):
                fence_body = re.sub(r"\n[ \t]*\Z", "", fence_body)
                # Already byte-exact -- nothing to flag.
                # This also correctly no-ops for a fence with zero leading whitespace, since every N >= 1 strip on such a fence is a no-op that reduces to this same already-checked raw content.
                if any(
                    fence_body in resolved_contents[t]
                    for t in ordered_resolved_tokens
                ):
                    continue

                for n in range(1, 41):
                    stripped = _strip_n_leading_spaces(fence_body, n)
                    matched_token = None
                    for token in ordered_resolved_tokens:
                        if stripped in resolved_contents[token]:
                            matched_token = token
                            break
                    if matched_token is not None:
                        errors.append({
                            "check": "requirements-quote-indent-drift",
                            "batch": batch_path.stem,
                            "card": card_num,
                            "path": matched_token,
                            "message": (
                                f"card {card_num}'s Requirements: fence {fence_idx} "
                                f"matches '{matched_token}' after stripping {n} "
                                f"leading spaces per line (found N={n})"
                            ),
                        })
                        break

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
    # Deletes: tokens and Move sources are excluded per issue #494 and the move-endpoint-accounting Shared Decision (sources disappear like Deletes; targets appear like Creates and must be listed in All Files Touched).
    cards_set: set[str] = set()
    for batch_path in batch_files:
        cards_set |= _parse_edits_only(batch_path)
    # Add Creates: tokens via compute_creates_union.
    cards_set |= compute_creates_union(overview_path.parent)
    # Add Move targets: they behave like Creates: tokens (new files appear after the rename step) and must appear in the overview's All Files Touched section.
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
                f"but not in any card's Edits:/Creates:/Moves: target"
            ),
        })
    for p in sorted(cards_set - overview_set):
        errors.append({
            "check": "all-files-touched-mismatch",
            "batch": None,
            "card": None,
            "path": p,
            "message": (
                f"path '{p}' in card Edits:/Creates:/Moves: target but missing "
                f"from overview's All Files Touched"
            ),
        })
    return errors


# ---------------------------------------------------------------------------
# verify-not-isolated check
# ---------------------------------------------------------------------------

def _check_verify_not_isolated(
    batch_files: list[Path],
    project_root: Path,
    overview_path: Path,
) -> list[dict]:
    """
    Flag verify: commands that skip the PYTHONPATH= isolation reset.

    Applies to every batch file's frontmatter plus the overview's own module-wide ``verify:``
    (previously batch-file-only, missing the overview-level command entirely). ``verify:`` may be
    authored as a plain string or as a ``{cwd, command}`` mapping;
    both forms are normalized via ``_plan_dag.parse_verify_field`` (both roots passed as
    ``project_root`` because only the extracted command string is needed here, not the resolved
    cwd).
    A malformed mapping raises ``ValueError`` from the normalizer -- this function silently skips
    that batch/overview because ``_check_verify_malformed_cwd`` is the sole reporter for that
    finding; duplicating it here would double-report the same authoring bug.

    Error dict shape: ``{check, batch, card, path, message}``.
    Overview-level findings use ``batch=None``, matching the convention already used by
    ``_check_all_files_touched_mismatch`` for overview-scoped errors.

    Args:
        batch_files: Sorted list of batch file paths to validate.
        project_root: Root of the project;
            also doubles as the hub_root argument to ``parse_verify_field`` since only the command
                string is needed, not the resolved cwd.
        overview_path: Path to the plan's ``00-overview.md``, whose own frontmatter ``verify:`` is
            checked alongside the per-batch loop.

    Returns:
        List of error dicts, one per non-compliant verify command.
    """
    # Python-project detection is a one-time lookup shared across every batch and the overview -- markers live at the project root or in the plugins/mill/ subdirectory used by this repo's own dogfood layout.
    is_python_project = (
        (project_root / "pyproject.toml").exists()
        or (project_root / "setup.py").exists()
        or (project_root / "setup.cfg").exists()
        or (project_root / "plugins" / "mill" / "pyproject.toml").exists()
    )

    def _check_frontmatter(frontmatter: dict, batch_label: str | None) -> dict | None:
        try:
            command, _cwd = _plan_dag.parse_verify_field(frontmatter, project_root, project_root)
        except ValueError:
            # _check_verify_malformed_cwd is the sole reporter for this.
            return None
        if command is None:
            return None
        # Only require the PYTHONPATH= prefix for Python projects;
        # native test runners (go test, dotnet test, ...)
        # have no such isolation concern.
        if is_python_project and not command.startswith("PYTHONPATH="):
            return {
                "check": "verify-not-isolated",
                "batch": batch_label,
                "card": None,
                "path": command,
                "message": "verify command missing PYTHONPATH= prefix",
            }
        return None

    errors: list[dict] = []
    for batch_path in batch_files:
        finding = _check_frontmatter(
            _plan_dag._read_batch_frontmatter(batch_path), batch_path.stem
        )
        if finding is not None:
            errors.append(finding)

    if overview_path.exists():
        finding = _check_frontmatter(
            _plan_dag._read_batch_frontmatter(overview_path), None
        )
        if finding is not None:
            errors.append(finding)

    return errors


# ---------------------------------------------------------------------------
# verify-excludes-edited-tagged-test check
# ---------------------------------------------------------------------------

# Matches a Go build-constraint comment line: "//go:build <expr>".
# The captured expression's identifiers are extracted and filtered against the denylist below to discover custom tags.
_RE_GO_BUILD_CONSTRAINT = re.compile(r"^//go:build\s+(?P<expr>.*)$")

# Matches a -tags flag (space or = separated) and its value, which may be a quoted (comma/space-separated) list or a single bare (comma-separated) token.
_RE_VERIFY_TAGS_FLAG = re.compile(r"-tags[= ]+(\"[^\"]*\"|'[^']*'|\S+)")

# Safety net bounding the //go:build header-comment scan well above real-world license-header lengths (Apache-2.0 ~15 lines, BSD-3-Clause ~25-27 lines), so a long copyright header never causes an unbounded scan.
_GO_BUILD_TAG_SCAN_LINES = 40

# Standard Go build tags that are never "custom" -- discovering a GOOS/GOARCH/reserved/
# release-version identifier in a //go:build expression must not require a matching -tags
# flag (those tags are satisfied automatically, never via -tags).
_GO_BUILD_DENYLIST_GOOS = frozenset({
    "aix", "android", "darwin", "dragonfly", "freebsd", "hurd", "illumos", "ios", "js",
    "linux", "nacl", "netbsd", "openbsd", "plan9", "solaris", "wasip1", "windows", "zos",
})
_GO_BUILD_DENYLIST_GOARCH = frozenset({
    "386", "amd64", "amd64p32", "arm", "armbe", "arm64", "arm64be", "loong64", "mips",
    "mipsle", "mips64", "mips64le", "mips64p32", "mips64p32le", "ppc", "ppc64", "ppc64le",
    "riscv", "riscv64", "s390", "s390x", "sparc", "sparc64", "wasm",
})
_GO_BUILD_DENYLIST_RESERVED = frozenset({
    "cgo", "race", "msan", "asan", "unix", "boringcrypto", "gc", "gccgo", "purego", "ignore",
})
# Release-version tags (e.g. "go1.21") are also never custom.
_RE_GO_RELEASE_VERSION_TAG = re.compile(r"^go[1-9]\d*\.\d+$")

# Deliberate divergence from _implementer_common.py's _GO_BUILD_TAG_GOOS/_GO_BUILD_TAG_GOARCH
# (lines 1014-1017 there): that smaller set is safe only because its caller
# (_go_build_tag_retiering_stuck) runs `go build -tags <tag>` downstream, so a
# misclassified real GOOS/GOARCH value fails the compile and surfaces as stuck_type: verify
# (fails closed). This check has no downstream compile step -- a misclassified value here
# would silently create a new, never-corrected false positive, so it intentionally uses a
# larger, more complete denylist and must not share a constant with that smaller set.


def _go_file_custom_tags(path: Path) -> set[str]:
    """
    Return the set of custom build tags discovered in a Go source file's leading //go:build line.

    Scans from the top of the file, skipping blank lines and `//`-comment lines (a license/copyright
    header may precede the build-constraint line);
    the first line that is neither blank nor a `//`-comment ends the scan (e.g. `package foo` or a
    `/*` block comment opener).
    Bounded to the first `_GO_BUILD_TAG_SCAN_LINES` lines.
    On the first scanned `//go:build` line, every identifier in its constraint expression is
    extracted and the ones NOT in `_GO_BUILD_DENYLIST_GOOS`, `_GO_BUILD_DENYLIST_GOARCH`,
    `_GO_BUILD_DENYLIST_RESERVED`, and not matching `_RE_GO_RELEASE_VERSION_TAG` (a
    custom tag discovered from the file's own `//go:build` expression, GOOS/GOARCH/
    reserved-word/release-version tags excluded via denylist) are returned.

    Args:
        path: Path to an existing Go source file on disk.

    Returns:
        The set[str] of custom tags found on the first scanned `//go:build` line; empty when no such
        line is found before the scan ends.
    """
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines()[:_GO_BUILD_TAG_SCAN_LINES]:
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("//"):
            break
        m = _RE_GO_BUILD_CONSTRAINT.match(stripped)
        if m:
            identifiers = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", m.group("expr"))
            return {
                ident for ident in identifiers
                if ident not in _GO_BUILD_DENYLIST_GOOS
                and ident not in _GO_BUILD_DENYLIST_GOARCH
                and ident not in _GO_BUILD_DENYLIST_RESERVED
                and not _RE_GO_RELEASE_VERSION_TAG.match(ident)
            }
    return set()


def _verify_command_has_any_tag(command: str, tags: set[str]) -> bool:
    """
    Return True if a verify: command's -tags flag value includes any of `tags`.

    Matches `-tags <tag>`, `-tags=<tag>`, and a quoted or bare comma-separated value like
    `-tags "<tag>,other"` or `-tags <tag>,other`.
    A value that merely contains a tag as a substring (e.g. `integrationtest` for tag
    `integration`) does not count -- the match requires an exact comma/whitespace-split token,
    not a substring.

    Args:
        command: The verify: command string (already normalized via `_plan_dag.parse_verify_field`).
        tags: The set of custom tags to match against; the check passes if ANY of them appears.

    Returns:
        True if any `-tags` flag in the command carries at least one of `tags` as one of its
        comma/whitespace-split values.
    """
    for m in _RE_VERIFY_TAGS_FLAG.finditer(command):
        value = m.group(1).strip("\"'")
        tokens = re.split(r"[,\s]+", value)
        if set(tokens) & tags:
            return True
    return False


def _check_verify_excludes_edited_tagged_test(
    batch_files: list[Path],
    project_root: Path,
    root: str | None,
    *,
    wiki_root: Path | None = None,
    git_root: Path | None = None,
) -> list[dict]:
    """
    Flag a batch whose verify: command silently skips an edited custom-tagged Go test.

    Go-specific: gated on `(project_root / "go.mod").exists()`, fail-open for every non-Go project
    -- mirrors `_check_verify_not_isolated`'s `is_python_project` gate.

    For each batch, collects `Edits:`-only tokens ending in `_test.go` (via `_parse_edits_only`,
    filtered to that suffix). `Creates:` tokens are deliberately excluded from this collection: a
    `Creates:` target does not exist on disk at plan-validation time (this codebase's established
    convention), so `resolve_existing_paths` would never confirm it as custom-tagged anyway -- an
    accepted, documented limitation, not a bug (see the Card 6 `(h)` regression scenario).

    Each resolved edited test file is scanned via `_go_file_custom_tags`, which discovers custom
    tags from the file's own `//go:build` expression (GOOS/GOARCH/reserved-word/release-version
    tags excluded via denylist). Every edited tagged file is checked independently -- not just the
    first -- so a batch editing multiple custom-tagged test files gets one finding per untested
    file. The batch's `verify:` command (normalized once per batch via `_plan_dag.parse_verify_field`;
    a malformed `{cwd, command}` mapping raises `ValueError` -- caught and skipped here since
    `_check_verify_malformed_cwd` is the sole reporter for that) must carry a `-tags` flag whose
    value includes at least one of a file's discovered tags (`_verify_command_has_any_tag`);
    otherwise this check reports one finding for that file, naming the alphabetically-first
    (`sorted(tags)[0]`) discovered tag for determinism.

    Error dict shape: ``{check, batch, card, path, message}``.

    Args:
        batch_files: Sorted list of batch file paths to validate.
        project_root: Root of the project (worktree root);
            also the `go.mod` presence-check root.
        root: Optional root subfolder for source refs, threaded to `resolve_existing_paths` exactly
            like sibling checks (`_check_non_existent_path`, `_check_move_source_missing`,
            `_check_batch_oversized`) so a nested-layout Go project still resolves `_test.go` tokens
            correctly.
        wiki_root: Optional wiki root path, threaded to `resolve_existing_paths`.
        git_root: Optional repo root, threaded to `resolve_existing_paths`.

    Returns:
        List of error dicts, one per edited custom-tagged test file whose batch verify: command
        lacks a matching -tags flag.
    """
    if not (project_root / "go.mod").exists():
        return []

    errors: list[dict] = []
    for batch_path in batch_files:
        edited_test_tokens = sorted(
            t for t in _parse_edits_only(batch_path) if t.endswith("_test.go")
        )
        if not edited_test_tokens:
            continue

        try:
            frontmatter = _plan_dag._read_batch_frontmatter(batch_path)
            command, _cwd = _plan_dag.parse_verify_field(
                frontmatter, project_root, project_root,
            )
        except ValueError:
            # _check_verify_malformed_cwd is the sole reporter for this.
            continue

        for token in edited_test_tokens:
            resolved = resolve_existing_paths(
                [token], project_root, root, wiki_root=wiki_root, git_root=git_root,
            )
            if not resolved:
                continue
            tags = _go_file_custom_tags(resolved[0])
            if not tags:
                continue
            if command is None or not _verify_command_has_any_tag(command, tags):
                errors.append({
                    "check": "verify-excludes-edited-tagged-test",
                    "batch": batch_path.stem,
                    "card": None,
                    "path": token,
                    "message": (
                        f"batch '{batch_path.stem}' edits custom-tagged test '{token}' but its "
                        f"verify: command lacks a matching -tags flag naming '{sorted(tags)[0]}'"
                    ),
                })

    return errors


# ---------------------------------------------------------------------------
# verify-full-suite check
# ---------------------------------------------------------------------------

def _check_verify_full_suite(
    batch_files: list[Path],
    project_root: Path,
    overview_path: Path,
) -> list[dict]:
    """
    Flag verify: commands that invoke run-all.py without a scoping filter.

    Applies to every batch file's frontmatter plus the overview's own module-wide ``verify:``,
    mirroring ``_check_verify_not_isolated``'s string-vs-mapping handling and malformed-mapping
    silence (see that function's docstring for the shared rationale).

    Error dict shape: ``{check, batch, card, path, message}``.
    Overview-level findings use ``batch=None``.

    Args:
        batch_files: Sorted list of batch file paths to validate.
        project_root: Root of the project;
            also doubles as the hub_root argument to ``parse_verify_field`` since only the command
                string is needed, not the resolved cwd.
        overview_path: Path to the plan's ``00-overview.md``, whose own frontmatter ``verify:`` is
            checked alongside the per-batch loop.

    Returns:
        List of error dicts, one per unscoped run-all.py invocation.
    """
    def _check_frontmatter(frontmatter: dict, batch_label: str | None) -> dict | None:
        try:
            command, _cwd = _plan_dag.parse_verify_field(frontmatter, project_root, project_root)
        except ValueError:
            # _check_verify_malformed_cwd is the sole reporter for this.
            return None
        if command is None:
            return None
        if "run-all.py" in command and "-k " not in command and "--only " not in command:
            return {
                "check": "verify-full-suite",
                "batch": batch_label,
                "card": None,
                "path": command,
                "message": (
                    "verify command invokes run-all.py without a filter (-k pattern); "
                    "use '-k <pattern>' or '--only <files>' to scope the run"
                ),
            }
        return None

    errors: list[dict] = []
    for batch_path in batch_files:
        finding = _check_frontmatter(
            _plan_dag._read_batch_frontmatter(batch_path), batch_path.stem
        )
        if finding is not None:
            errors.append(finding)

    if overview_path.exists():
        finding = _check_frontmatter(
            _plan_dag._read_batch_frontmatter(overview_path), None
        )
        if finding is not None:
            errors.append(finding)

    return errors


# ---------------------------------------------------------------------------
# verify-malformed-cwd check
# ---------------------------------------------------------------------------

def _check_verify_malformed_cwd(
    batch_files: list[Path],
    overview_path: Path,
    project_root: Path,
) -> list[dict]:
    """
    Flag verify: fields that fail to parse via _plan_dag.parse_verify_field.

    The verify cwd field schema (Shared Decision, plan 00-overview.md) allows ``verify:`` to be a
    plain string or a ``{cwd: hub|git_root, command: ...}`` mapping. ``parse_verify_field`` raises
    ``ValueError`` when the mapping is missing ``command``, names an unrecognized ``cwd``, or
    ``verify`` is some other type entirely -- a plan-authoring bug that must surface as a normal
    finding rather than an uncaught exception crashing the validator.

    This is the **sole** reporter for malformed-mapping findings: ``_check_verify_not_isolated`` and
    ``_check_verify_full_suite`` catch the same ``ValueError`` and silently skip the batch/overview,
    so one malformed mapping produces exactly one finding here, never a duplicate.

    Error dict shape: ``{check, batch, card, path, message}``.
    Overview-level findings use ``batch=None`` and ``path`` set to the overview path.

    Args:
        batch_files: Sorted list of batch file paths to validate.
        overview_path: Path to the plan's ``00-overview.md``, whose own frontmatter ``verify:`` is
            checked alongside the per-batch loop.
        project_root: Root of the project;
            also doubles as the hub_root argument to ``parse_verify_field`` since only whether
                parsing raises matters here, not the resolved cwd.

    Returns:
        List of error dicts, one per malformed verify: field.
    """
    errors: list[dict] = []

    def _check_frontmatter(frontmatter: dict, batch_label: str | None, path: Path) -> None:
        try:
            _plan_dag.parse_verify_field(frontmatter, project_root, project_root)
        except ValueError as exc:
            errors.append({
                "check": "verify-malformed-cwd",
                "batch": batch_label,
                "card": None,
                "path": str(path),
                "message": str(exc),
            })

    for batch_path in batch_files:
        _check_frontmatter(
            _plan_dag._read_batch_frontmatter(batch_path), batch_path.stem, batch_path
        )

    if overview_path.exists():
        _check_frontmatter(
            _plan_dag._read_batch_frontmatter(overview_path), None, overview_path
        )

    return errors


# ---------------------------------------------------------------------------
# verify-mixed-cwd check
# ---------------------------------------------------------------------------

def _check_verify_mixed_cwd(
    batch_files: list[Path],
    overview_text: str,
    project_root: Path,
    git_root: Path,
) -> list[dict]:
    """
    Flag a plan whose batches resolve the verify cwd mapping to more than one root.

    Mirrors ``_plan_dag.iter_batch_verifies``'s DAG-order traversal: every batch whose ``verify:``
    is authored as a ``{cwd, command}`` mapping resolves to either ``project_root`` (hub) or
    ``git_root``.
    Mixing the two across batches in the same plan is the exact runtime conflict that a
    holistic-scope verify replay must reject -- a merge-in or fixer stage that concatenates commands
    from batches pinned to different roots would run at least one of them in the wrong directory.
    Catching the conflict here, at plan-review time, means a bad plan never reaches that runtime
    check at all.

    Batches whose ``verify:`` is the plain-string form (cwd ``None``, "use the caller's default") do
    not participate in the conflict -- only batches with an explicit, resolved cwd can disagree with
    each other.

    Error dict shape: ``{check, batch, card, path, message}``, one finding per conflicting batch so
    every offender is individually visible in sorted output.

    Args:
        batch_files: Sorted list of batch file paths to validate.
        overview_text: Full text of ``00-overview.md`` (source of the Batch Index DAG used to
        enumerate batches in dependency order).
        project_root: The mill project root (hub_root), passed through to ``parse_verify_field`` for
        ``cwd: hub`` resolution.
        git_root: The git repository toplevel, passed through to ``parse_verify_field`` for ``cwd:
        git_root`` resolution.

    Returns:
        List of error dicts, one per batch participating in a mixed-cwd conflict.
        Empty when zero or one distinct cwd value appears.
    """
    try:
        batches = extract_batch_index(overview_text)
    except PlanDAGError:
        # batch-index-parse (Check 4's sibling) already recorded this failure.
        return []

    try:
        order = _plan_dag.topo_order(batches)
    except PlanDAGError:
        return []
    except KeyError:
        # topo_order indexes its adjacency map directly by depends-on name, so a depends-on entry naming an unknown batch raises KeyError rather than PlanDAGError. _check_depends_on_unknown already reports that dangling reference as its own finding;
        # treat it as "nothing to check" here rather than crashing the whole validator.
        return []

    file_by_name = {entry["name"]: entry.get("file") for entry in batches}
    stem_to_path = {bf.stem: bf for bf in batch_files}

    # Resolve each batch's verify cwd.
    # Batches with the plain-string form (or no verify: at all) resolve to cwd=None and do not participate in the conflict;
    # a malformed mapping is reported solely by _check_verify_malformed_cwd, so it is silently skipped here too.
    cwd_by_batch: dict[str, Path] = {}
    for name in order:
        file_ref = file_by_name.get(name)
        if not file_ref:
            continue
        batch_path = stem_to_path.get(Path(file_ref).stem)
        if batch_path is None:
            continue
        frontmatter = _plan_dag._read_batch_frontmatter(batch_path)
        try:
            _command, cwd = _plan_dag.parse_verify_field(frontmatter, project_root, git_root)
        except ValueError:
            continue
        if cwd is not None:
            cwd_by_batch[name] = cwd

    distinct_cwds = set(cwd_by_batch.values())
    if len(distinct_cwds) <= 1:
        return []

    conflicting_names = sorted(cwd_by_batch.keys())
    errors: list[dict] = []
    for name in conflicting_names:
        errors.append({
            "check": "verify-mixed-cwd",
            "batch": name,
            "card": None,
            "path": None,
            "message": (
                f"batch '{name}' resolves verify cwd to {cwd_by_batch[name]}, "
                f"conflicting with other batches in the plan resolving to a "
                f"different cwd: {conflicting_names}"
            ),
        })
    return errors


# ---------------------------------------------------------------------------
# verify-unrelated-test-file check
# ---------------------------------------------------------------------------

def _check_verify_unrelated_test_files(
    batch_files: list[Path],
    project_root: Path,
    git_root: Path,
    parent_branch: str | None,
) -> list[dict]:
    """
    Flag verify: --only test-file tokens unrelated to their own batch.

    Fixes #638: a batch's ``verify:`` ``--only`` test-file list can accidentally include a test file
    that has nothing to do with that batch's own cards.
    When such a stray token is also byte-identical to the task's resolved parent branch, running it
    replays a pre-existing (possibly already-failing) test unrelated to the batch, which can falsely
    block a fully-correct batch with ``stuck_type: verify``.

    Applies to every batch file's frontmatter, mirroring ``_check_verify_not_isolated``'s
    string-vs-mapping handling and malformed-mapping silence (see that function's docstring for the
    shared rationale -- ``_check_verify_malformed_cwd`` is the sole reporter for a malformed
    ``verify:`` mapping).

    Fail-safe per the "never raise from a new gate/check function" Shared Decision:
    ``parent_branch=None`` short-circuits to ``[]`` immediately for every batch (no parent resolved,
    nothing to diff against -- never guess or fall back to a literal branch name like ``"main"``),
    and any subprocess or resolution failure for an individual token is treated as "cannot confirm
    identical, don't flag" rather than a crash.

    Error dict shape: ``{check, batch, card, path, message}``.

    Args:
        batch_files: Sorted list of batch file paths to validate.
        project_root: Root of the project;
            also doubles as the hub_root argument to ``parse_verify_field`` since only the command
                string is needed here, not the resolved cwd (mirrors
                ``_check_verify_not_isolated``'s own call shape).
        git_root: Repository toplevel used to resolve candidate tokens on
        disk (via ``resolve_existing_paths``) and as the ``-C`` root
        for the ``git diff`` subprocess call.
        parent_branch: The task's resolved parent branch name (e.g. ``hanf/linux-port-more``),
            or ``None`` when unresolved.

    Returns:
        List of error dicts, one per stray ``--only`` token confirmed byte-identical to the parent
        branch.
    """
    if parent_branch is None:
        return []

    errors: list[dict] = []
    for batch_path in batch_files:
        try:
            frontmatter = _plan_dag._read_batch_frontmatter(batch_path)
            command, _cwd = _plan_dag.parse_verify_field(
                frontmatter, project_root, project_root
            )
        except ValueError:
            # _check_verify_malformed_cwd is the sole reporter for this.
            continue
        except Exception:
            # Never raise -- treat any other unexpected parse failure as "nothing to check" for this batch.
            continue
        if command is None:
            continue

        m = _RE_VERIFY_ONLY.search(command)
        if not m:
            continue
        candidates = [
            tok for tok in m.group(1).split() if _RE_TEST_FILE_TOKEN.match(tok)
        ]
        if not candidates:
            continue

        try:
            touched = (
                _parse_edits_only(batch_path)
                | _parse_creates_only(batch_path)
                | {dst for _, dst in parse_moves(batch_path)}
            )
        except Exception:
            touched = set()
        touched_basenames = {Path(t).name for t in touched}

        for token in candidates:
            if Path(token).name in touched_basenames:
                continue
            try:
                resolved = resolve_existing_paths(
                    [token], project_root, None, wiki_root=None, git_root=git_root,
                )
            except Exception:
                continue
            if len(resolved) != 1:
                continue
            try:
                diff_result = _subprocess_util.run(
                    ["git", "-C", str(git_root), "diff", parent_branch, "--", str(resolved[0])],
                )
            except Exception:
                continue
            if diff_result.returncode != 0:
                continue
            if diff_result.stdout.strip():
                continue
            errors.append({
                "check": "verify-unrelated-test-file",
                "batch": batch_path.stem,
                "card": None,
                "path": token,
                "message": (
                    f"verify command includes '{token}', which is untouched by this "
                    f"batch's own Files Touched and unchanged vs. parent branch "
                    f"'{parent_branch}' -- likely an unrelated pre-existing test"
                ),
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
    parent_branch: str | None = None,
) -> list[dict]:
    """Validate plan files in plan_dir.

    Returns a sorted list of error dicts with keys: {check, batch, card, path, message}.

    Checks 1, 2, 3, 4, 5, 6, 8 from issue #10, plus wiki-config-mutation,
    plugin-manifest-context-missing, verify-not-isolated, verify-full-suite, verify-malformed-cwd,
    verify-mixed-cwd, verify-unrelated-test-file, out-of-worktree-target, batch-oversized,
    commit-none-with-content, and five Move-specific checks (move-format, move-redundant,
    move-source-missing, move-target-collision, move-mechanic-missing).

    Args:
        plan_dir: Directory containing the plan files (00-overview.md + batch files).
        project_root: Root of the project (typically the worktree root).
        root: Optional root subfolder for source refs (e.g. "subproject1");
            when set, refs resolve to git_root/root/raw first, then project_root/root/raw.
        wiki_root: Optional wiki root path;
            when provided, refs starting with "wiki/" are resolved against wiki_root instead of
                project_root.
        git_root: Optional repo root;
            when provided, refs resolve to git_root/root/raw before falling back to
                project_root-based candidates (addresses #471 layout).
        skip_checks: Set of check names to skip (e.g. {"wiki-config-mutation"}).
        max_cards_per_batch: Maximum cards per batch before batch-oversized is raised.
        max_batch_context_tokens: Maximum context token estimate before batch-oversized is raised.
        parent_branch: The task's resolved parent branch name, threaded to
            verify-unrelated-test-file. ``None`` (the default) makes that check a no-op -- callers
            that cannot resolve a parent branch (e.g.
            the standalone millpy-validate-plan.py CLI) simply skip it.
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
    # verify-mixed-cwd needs a concrete git_root to distinguish "cwd: hub" from "cwd: git_root" resolutions;
    # in a flat layout (no git_root supplied) the two roots collapse to the same Path, which correctly reports zero conflicts since there is nothing to mix.
    effective_git_root = git_root if git_root is not None else project_root

    errors: list[dict] = []

    errors.extend(_check_non_existent_path(
        batch_files, project_root, effective_root, creates_union, deletes_union, moves_targets,
        wiki_root=wiki_root,
        git_root=git_root,
    ))
    errors.extend(_check_card_missing_field(batch_files))
    errors.extend(_check_commit_none_with_content(batch_files))
    errors.extend(_check_card_numbering(batch_files))
    errors.extend(_check_depends_on_unknown(overview_text, overview_path))
    errors.extend(_check_depends_on_batch_mismatch(batch_files, overview_text))
    errors.extend(_check_parallel_modifies_overlap(batch_files, overview_text))
    errors.extend(_check_ref_not_backtick_path(batch_files))
    errors.extend(_check_verify_not_isolated(batch_files, project_root, overview_path))
    errors.extend(_check_verify_full_suite(batch_files, project_root, overview_path))
    errors.extend(_check_verify_malformed_cwd(batch_files, overview_path, project_root))
    errors.extend(_check_verify_mixed_cwd(batch_files, overview_text, project_root, effective_git_root))
    errors.extend(_check_verify_unrelated_test_files(
        batch_files, project_root, effective_git_root, parent_branch,
    ))
    errors.extend(_check_verify_excludes_edited_tagged_test(
        batch_files, project_root, effective_root,
        wiki_root=wiki_root,
        git_root=git_root,
    ))
    errors.extend(_check_wiki_config_mutation(batch_files))
    errors.extend(_check_plugin_manifest_context_missing(batch_files))
    errors.extend(_check_context_completeness(
        batch_files, project_root, effective_root, creates_union, deletes_union, moves_targets,
        wiki_root=wiki_root,
        git_root=git_root,
    ))
    errors.extend(_check_requirements_quote_indent_drift(
        batch_files, project_root, effective_root,
        wiki_root=wiki_root,
        git_root=git_root,
    ))
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
