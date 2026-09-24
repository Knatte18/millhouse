"""
Static plan pre-validator.

Checks plan files for structural issues BEFORE invoking the LLM reviewer.
Used by millpy-validate-plan.py (standalone CLI) and by millpy-review-plan.py (auto-run gate before
each review round).

Public API:
    run(plan_dir, project_root, *, root=None, wiki_root=None, git_root=None, skip_checks=frozenset(),
        max_cards_per_batch=10, max_batch_context_tokens=120000, parent_branch=None,
        done_gate=None) -> list[dict]
    Validate plan files in plan_dir. Returns a sorted list of error dicts.
    Each error dict has keys: {check, batch, card, path, message}.
    compute_next_card_number(plan_dir, target_batch_file) -> int
    Compute the next unused card number for a target batch, before that card is written to disk.
    renumber_after_collision(plan_dir, colliding_number) -> None
    Shift every card numbered >= colliding_number, across every batch file in the plan, up by one,
    to resolve a compute_next_card_number collision on a self-resolve card-insertion retry.

Checks performed (check keys):
    non-existent-path — (#10 check 1) Context:/Edits:/Creates: refs that don't exist on disk and are
        not Creates:/Moves: targets
    card-missing-field — (#10 check 2) Cards missing one of the required fields (Context, Edits,
        Creates, Deletes, Moves, Requirements, Commit)
    card-numbering — (#10 check 3) Non-sequential or cross-batch-duplicate card numbers
    depends-on-unknown — (#10 check 4) depends-on entries referencing unknown batch names
    depends-on-batch-mismatch — per-batch file's depends-on disagrees with overview Batch Index
        depends-on for the same batch
    verify-batch-mismatch — a batch's overview Batch Index verify: disagrees with that batch file's
        own frontmatter verify: (command or cwd)
    parallel-modifies-overlap — (#10 check 5) Parallel-eligible batches both modifying the same file
        (includes Move endpoints)
    reads-not-backtick-path — (#10 check 6) Context:/Edits:/Creates: entries not in backtick-only
        format (exempts bare 'none')
    all-files-touched-mismatch — (#10 check 8) Mismatch between overview's All Files Touched section
        and cards' Edits:/Creates:/Moves: targets
    verify-not-isolated — per-batch or overview-level verify: command does not start with
        PYTHONPATH= reset prefix
    verify-full-suite — per-batch or overview-level verify: invokes one of four unscoped full-suite
        runners: run-all.py without -k/--only, go test ./... without -run, dotnet test with no
        project target or a solution target and no --filter, bare pytest
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
    verify-untested-tag-in-touched-package — Go-specific (gated on go.mod presence); flags an
        untouched, differently-build-tagged Go test file co-located in a package some batch's
        non-test Edits:/Creates: touched, when no batch's verify: command exercises that tag
        against that package. Distinct from verify-excludes-edited-tagged-test, which only fires
        when a batch itself edits the tagged test file.
    wiki-config-mutation — batch Edits:/Creates: contains mill-config.yaml (self-applying layout
        risk)
    plugin-manifest-context-missing — batch Creates:/Edits:/Deletes: touches plugins/mill/agents/
        but plugin.json is not in that batch's Context: or Edits:
    context-completeness — a card's Requirements: references a resolvable file-path-shaped or
        symbol-shaped backtick token absent from that card's own Context:/Edits:/Creates:/Deletes:/
        Moves:-source
    requirements-quote-indent-drift — a card's Requirements: fenced block quoting exact source text
        that only byte-matches its own Edits: file(s) after stripping OR adding a fixed per-line
        indent, in either direction (list-continuation-indentation bug signature)
    move-format — Moves: sub-bullet does not match the `src` -> `dst` grammar
    move-redundant — a path is both a Move endpoint and in Creates:/Deletes: of the same batch
    move-source-missing — Move source does not exist on disk and is not created/relocated by an
        earlier batch
    move-target-collision — Move target already exists, is targeted by multiple batches, or collides
        with a Creates: in another batch
    move-mechanic-missing — batch has non-empty Moves: but is missing a '## Rename mechanic' section
    commit-none-with-content — a card's Commit: is the literal 'none' sentinel but its
        Edits:/Creates:/Deletes:/Moves: has non-none content
    cross-batch-creates-no-depends-on — a card's Context:/Edits: references a file another batch's
        Creates: produces, with no depends-on edge (direct or transitive) from the referencing batch to the
        creating batch
    cross-batch-build-break — a batch's Requirements: rename/remove a symbol while a
        later-or-unordered batch's own Requirements: still reference the old symbol name, gated on
        the overview's top-level verify: field being non-null
"""
from __future__ import annotations

import bisect
import os
import re
import shlex
import yaml
from pathlib import Path

import _plan_dag
import _subprocess_util
from _plan_dag import PlanDAGError, extract_batch_index, resolve_deps_as_names
from _review_common import (
    ReviewError,
    _load_root_from_overview,
    compute_creates_union,
    compute_deletes_union,
    compute_moves_union,
    parse_moves,
    resolve_existing_paths,
    resolve_ref_paths,
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

# Matches a Windows drive-letter root (e.g. "C:/" or "C:\") or a UNC root (a doubled leading
# backslash, e.g. "\\server\share"). Used by context-completeness's out-of-repo-literal exemption
# to recognize an absolute-looking token without compiling this pattern per token.
_RE_WINDOWS_ABS_ROOT = re.compile(r"^(?:[A-Za-z]:[/\\]|\\\\)")

# Clause-boundary punctuation: comma, semicolon, colon, period. Used by the negation-phrase and
# contrast-citation exemptions below to keep a phrase match from reaching across an unrelated
# clause in the same Requirements: line.
_RE_CLAUSE_BOUNDARY = re.compile(r"[,;:.]")

# Required card fields. "Moves" sits after "Deletes" and before "Requirements" per the moves-grammar Shared Decision.
_REQUIRED_CARD_FIELDS = ["Context", "Edits", "Creates", "Deletes", "Moves", "Requirements", "Commit"]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_cards(batch_text: str) -> list[tuple[int, list[str]]]:
    """Return list of (card_number, card_lines) pairs; see ``_parse_cards_positioned``."""
    return [(number, lines) for number, lines, _ in _parse_cards_positioned(batch_text)]


def _parse_cards_positioned(batch_text: str) -> list[tuple[int, list[str], int]]:
    """Return list of (card_number, card_lines, start_line) triples.

    ``start_line`` is the 1-based batch-file line of the card's ``### Card N:`` heading.

    Each card block starts at a ``### Card N:`` line and ends just before the next ``### ``
    heading or at EOF. A ``### `` line inside a fenced code block (delimited by lines whose
    stripped-of-leading-whitespace prefix is ``` ``` ```, toggled per
    ``_requirements_fence_aware_body``'s convention) never starts or ends a card block.
    """
    lines = batch_text.splitlines()
    cards: list[tuple[int, list[str], int]] = []
    current_num: int | None = None
    current_lines: list[str] = []
    current_start_line = 0
    in_fence = False

    for index, line in enumerate(lines):
        m = re.match(r"^###\s+Card\s+(\d+)\s*:", line) if not in_fence else None
        if m:
            if current_num is not None:
                cards.append((current_num, current_lines, current_start_line))
            current_num = int(m.group(1))
            current_lines = [line]
            current_start_line = index + 1
        elif current_num is not None:
            if not in_fence and line.startswith("### "):
                cards.append((current_num, current_lines, current_start_line))
                current_num = None
                current_lines = []
            else:
                current_lines.append(line)
        if line.lstrip().startswith("```"):
            in_fence = not in_fence

    if current_num is not None:
        cards.append((current_num, current_lines, current_start_line))

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
    moves_sources: set[str],
    *,
    wiki_root: Path | None = None,
    git_root: Path | None = None,
) -> list[dict]:
    """
    Flag Moves: targets that collide with existing files or other plan entries.

    Three collision conditions are checked (OR semantics):

    1. The target already exists on disk before the plan runs.
        Suppressed when the target is itself a plan-wide ``Moves:`` source -- it currently exists
        on disk only because it is about to be vacated by another ``Moves:`` pair in the plan (an
        intra-plan rename chain, e.g. ``a.go -> b.go`` followed by ``b.go -> c.go``).
    2. More than one batch across the plan names the same destination path.
    3. The target appears as a ``Creates:`` token in a DIFFERENT batch (cross-batch collision).
        Same-batch overlap is ``move-redundant``'s responsibility;
        this check intentionally skips it to avoid double-reporting.

    Error dict shape: ``{check, batch, card, path, message}``.

    Args:
        batch_files: Sorted list of batch file paths to validate.
        project_root: Root of the project (worktree root).
        root: Optional root subfolder (threaded to ``resolve_existing_paths``).
        moves_sources: Plan-wide union of ``Moves:`` source tokens (from ``compute_moves_union``),
            used to suppress condition 1 on an intra-plan rename chain's intermediate path.
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
            if existing and dst not in moves_sources:
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

    - ``Context:`` refs additionally soft-fail when confirmed git-ignored (via
    ``resolve_ref_paths(..., soft_fail_gitignored=True)``) -- a ``Context:``-only reference to a
    not-yet-existing, gitignored runtime artefact (e.g. a build/run-output file an earlier batch
    produces at runtime, under a ``.gitignore``d directory) is not flagged, matching the LLM
    reviewer's own existing leniency for ``Context:`` refs (``_review_plan.py``, #733/#808).
    ``Edits:``/``Creates:``/``Deletes:`` refs receive NO such leniency -- those name files the
    batch is expected to produce or touch, a hard requirement.

    Error dict shape: ``{check, batch, card, path, message}``.
    """
    errors: list[dict] = []
    for batch_path in batch_files:
        deletes_only = _parse_deletes_only(batch_path)
        context_tokens = _parse_context_only(batch_path)
        edits_creates_tokens = (
            _parse_edits_only(batch_path) | _parse_creates_only(batch_path)
        ) - deletes_only

        # Edits:/Creates: loop (unchanged behavior): missing on disk is suppressed when the token
        # is in creates_union, deletes_union, OR moves_targets.
        # The moves_targets suppression prevents false errors on downstream cards that reference a not-yet-existing Move destination in their Context:/Edits:.
        for t in edits_creates_tokens:
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

        # Context: loop (new gitignore-aware behavior): same union suppression up front, then a
        # soft-fail resolve that additionally tolerates a confirmed-gitignored missing path.
        for t in context_tokens:
            if t.lower() == "none":
                continue
            if t in creates_union or t in deletes_union or t in moves_targets:
                continue
            try:
                resolve_ref_paths(
                    [t], project_root, root,
                    wiki_root=wiki_root, git_root=git_root, soft_fail_gitignored=True,
                )
            except ReviewError:
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

    # Starts-at-1: the lowest card number across the plan must be 1.
    if all_cards:
        min_stem, min_card = min(all_cards, key=lambda t: (t[1], t[0]))
        if min_card != 1:
            errors.append({
                "check": "card-numbering",
                "batch": min_stem,
                "card": 1,
                "path": None,
                "message": (
                    f"card 1 breaks sequential numbering within batch {min_stem} "
                    f"(numbering starts at {min_card}, not 1)"
                ),
            })

    return errors


def compute_next_card_number(plan_dir: Path, target_batch_file: str) -> int:
    """
    Compute the next unused card number for a target batch, before that card
    is ever written to disk.

    Unlike ``_check_card_numbering``, which can only ever detect a duplicate
    number that already exists on disk, this is a pure read-only computation
    over the already-written batch files that a caller can run *before*
    appending a new card -- so a self-resolve flow can safely pick the next
    number without risking a collision with another batch's numeric range.

    Args:
        plan_dir: Directory containing the ``NN-<batch-slug>.md`` batch files
            (and ``00-overview.md``, which is excluded from consideration).
        target_batch_file: The batch file's stem (e.g. ``01-alpha``, matching
            ``Path(...).stem`` -- no ``.md`` suffix and no directory).

    Returns:
        The next unused card number for ``target_batch_file`` (one past the
        highest card number already present in that batch), guaranteed not
        to collide with any other batch's card numbers.
    """
    batch_files = sorted(p for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md")

    used_numbers: dict[str, set[int]] = {}
    for batch_path in batch_files:
        text = batch_path.read_text(encoding="utf-8")
        cards = _parse_cards(text)
        used_numbers[batch_path.stem] = {n for n, _ in cards}

    if target_batch_file not in used_numbers:
        raise PlanDAGError(f"batch file stem {target_batch_file!r} not found under {plan_dir}")

    candidate = max(used_numbers[target_batch_file], default=0) + 1

    for stem, nums in used_numbers.items():
        if stem != target_batch_file and candidate in nums:
            raise PlanDAGError(
                f"card {candidate} already used by batch {stem!r}; "
                f"{target_batch_file!r} and {stem!r} occupy overlapping numeric ranges"
            )

    return candidate


def renumber_after_collision(plan_dir: Path, colliding_number: int) -> None:
    """
    Shift every card numbered >= colliding_number, across every batch file in the plan, up by one.

    Card numbers are global and each batch occupies a contiguous, disjoint numeric range (this
    file's own established convention), so shifting every colliding-or-later card up by exactly one
    preserves every batch's own internal ordering and every batch's contiguous range relative to its
    neighbors -- this is simpler than re-deriving ``topo_order`` and needs only each batch's own
    file-local card numbers.

    This function performs no numbering-collision re-validation of its own and never touches any
    batch's ``cards:`` frontmatter count (shifting labels never changes how many cards a batch owns)
    -- the caller is responsible for retrying ``compute_next_card_number`` afterward and for the
    post-write ``_check_card_numbering`` re-check the self-resolve step already runs.

    Safe to call only when the caller has already confirmed every renumbered batch has not yet been
    dispatched (no commit anywhere references its old card numbers) -- mill-go's own
    strictly-sequential ``topo_order`` execution guarantees this for the self-resolve caller, but
    this function itself does not verify it.

    Known limitation, accepted rather than engineered around: the regex only rewrites ``### Card N:``
    heading lines, never a card's own prose that names another card by number. After an
    auto-renumber, such an in-plan textual cross-reference can go stale even though every
    execution-relevant piece of state (``card_ids``, ``_check_card_numbering``'s own re-validation)
    stays correct -- heading numbers are the only thing mill-go's own machinery reads.

    Args:
        plan_dir: Directory containing the ``NN-<batch-slug>.md`` batch files (and
            ``00-overview.md``, which is excluded from consideration).
        colliding_number: The card number that ``compute_next_card_number`` reported as already
            used; every card numbered at or above this value is shifted up by one.
    """
    batch_files = sorted(
        p for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"
    )
    to_shift: list[tuple[Path, int]] = []
    for batch_path in batch_files:
        text = batch_path.read_text(encoding="utf-8")
        for num, _lines in _parse_cards(text):
            if num >= colliding_number:
                to_shift.append((batch_path, num))
    # Descending order: shift the highest numbers first so no intermediate write
    # collides with a not-yet-shifted number in the same file.
    for batch_path, num in sorted(to_shift, key=lambda pair: pair[1], reverse=True):
        text = batch_path.read_text(encoding="utf-8")
        heading_re = re.compile(rf"^(###\s+Card\s+){num}(\s*:)", re.MULTILINE)
        text = heading_re.sub(rf"\g<1>{num + 1}\g<2>", text, count=1)
        batch_path.write_text(text, encoding="utf-8")


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
# cross-batch-creates-no-depends-on check (#887)
# ---------------------------------------------------------------------------

def _check_cross_batch_creates_no_depends_on(
    batch_files: list[Path],
    overview_text: str,
) -> list[dict]:
    """
    Flag a Context:/Edits: reference to another batch's Creates: target with no depends-on edge.

    A card that names a file another batch produces via Creates: implicitly relies on that batch
    having already run.
    Without a depends-on edge (direct or transitive) from the referencing batch to the creating
    batch, the plan's DAG does not guarantee that ordering, so the reference may resolve to a
    file that does not exist yet at runtime.

    Error dict shape: ``{check, batch, card, path, message}``.

    Args:
        batch_files: Sorted list of batch file paths to validate.
        overview_text: Full text of ``00-overview.md`` (source of the Batch Index DAG).

    Returns:
        List of error dicts, one per (referencing batch, token) pair missing the required edge.
    """
    try:
        batches = extract_batch_index(overview_text)
    except PlanDAGError:
        # Check 4 has already recorded the parse error; don't double-report.
        return []

    ancestors = _compute_transitive_ancestors(batches)

    # Map batch name -> batch file path via the index's `file:` field.
    stem_to_path: dict[str, Path] = {bf.stem: bf for bf in batch_files}
    batch_name_to_path: dict[str, Path] = {}
    for entry in batches:
        file_ref = entry.get("file", "")
        stem = Path(file_ref).stem
        if stem in stem_to_path:
            batch_name_to_path[entry["name"]] = stem_to_path[stem]

    batch_creates: dict[str, set[str]] = {
        name: _parse_creates_only(path) for name, path in batch_name_to_path.items()
    }
    # Deliberately Context:+Edits: only, never Creates: -- a batch's own Creates: tokens must
    # never be scanned against other batches' creates sets.
    batch_context_edits: dict[str, set[str]] = {
        name: _parse_context_only(path) | _parse_edits_only(path)
        for name, path in batch_name_to_path.items()
    }

    errors: list[dict] = []
    for name_b, tokens in batch_context_edits.items():
        for token in tokens:
            if token.lower() == "none":
                continue
            for name_c, creates in batch_creates.items():
                if name_c == name_b:
                    continue
                if token in creates and name_c not in ancestors.get(name_b, set()):
                    errors.append({
                        "check": "cross-batch-creates-no-depends-on",
                        "batch": batch_name_to_path[name_b].stem,
                        "card": None,
                        "path": token,
                        "message": (
                            f"'{token}' is created by batch '{name_c}' but batch '{name_b}' "
                            f"(file {batch_name_to_path[name_b].name}) has no depends-on edge "
                            f"to '{name_c}'"
                        ),
                    })
                    # Stop after the first matching creator for this token -- defensive
                    # against two batches both declaring the same Creates: target, which is a
                    # separate, pre-existing structural error other checks already catch.
                    break

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
# Check 5c — verify-batch-mismatch
# ---------------------------------------------------------------------------

def _check_verify_batch_mismatch(
    batch_files: list[Path],
    overview_text: str,
    project_root: Path,
) -> list[dict]:
    """
    Flag a batch whose overview Batch Index ``verify:`` disagrees with its own frontmatter ``verify:``.

    Mirrors ``_check_depends_on_batch_mismatch``'s structure, but compares the ``verify:`` field
    instead of ``depends-on:``. A malformed ``verify:`` mapping is reported by exactly one of the two
    sides, never both:

    - On the overview side, this check IS the sole reporter -- ``_check_verify_malformed_cwd``
    inspects batch-file and overview *frontmatter* only, never Batch Index entries, so a malformed
    ``verify:`` on an index entry would otherwise go unreported.
    - On the batch-file side, ``_check_verify_malformed_cwd`` is already the documented sole
    reporter, so this check silently skips a batch-side parse failure to avoid double-reporting.

    Each side's raw ``cwd:`` key (the un-resolved string, not the normalizer's resolved ``Path``) is
    compared independently of the normalized command, because both root arguments are passed as
    ``project_root`` here -- passing the same value for both roots means ``cwd: hub`` and ``cwd:
    git_root`` would otherwise resolve to the identical ``Path``, silently hiding a real drift between
    the two spellings. Absent, explicit-null, and blank-string ``verify:`` all normalize to ``None``
    through the shared normalizer, so those three spellings compare equal to one another and produce
    no finding.

    Error dict shape: ``{check, batch, card, path, message}``.

    Args:
        batch_files: Sorted list of batch file paths to validate.
        overview_text: Full text of ``00-overview.md`` (source of the Batch Index DAG).
        project_root: Root of the project;
            passed as both the ``hub_root`` and ``git_root`` argument to
                ``_plan_dag.parse_verify_field`` since only the command/cwd-key pair matters here,
                never the resolved ``Path``.

    Returns:
        List of error dicts, one per batch whose two `verify:` sides disagree.
    """
    try:
        batches = extract_batch_index(overview_text)
    except PlanDAGError:
        # Check 4 has already recorded the parse error; don't double-report.
        return []

    stem_to_path: dict[str, Path] = {bf.stem: bf for bf in batch_files}

    errors: list[dict] = []
    for entry in batches:
        stem = Path(entry.get("file", "")).stem
        batch_path = stem_to_path.get(stem)
        if batch_path is None:
            continue

        try:
            overview_command, _ = _plan_dag.parse_verify_field(entry, project_root, project_root)
        except ValueError as exc:
            errors.append({
                "check": "verify-batch-mismatch",
                "batch": entry["name"],
                "card": None,
                "path": None,
                "message": f"overview Batch Index verify: is malformed: {exc}",
            })
            continue
        raw_overview_verify = entry.get("verify")
        overview_cwd_key = (
            raw_overview_verify.get("cwd") if isinstance(raw_overview_verify, dict) else None
        )

        batch_frontmatter = _plan_dag._read_batch_frontmatter(batch_path)
        try:
            batch_command, _ = _plan_dag.parse_verify_field(
                batch_frontmatter, project_root, project_root
            )
        except ValueError:
            # _check_verify_malformed_cwd is the sole reporter for this.
            continue
        raw_batch_verify = batch_frontmatter.get("verify")
        batch_cwd_key = raw_batch_verify.get("cwd") if isinstance(raw_batch_verify, dict) else None

        if (overview_command, overview_cwd_key) != (batch_command, batch_cwd_key):
            errors.append({
                "check": "verify-batch-mismatch",
                "batch": entry["name"],
                "card": None,
                "path": None,
                "message": (
                    f"per-batch file verify: command={batch_command!r} cwd={batch_cwd_key!r} "
                    f"disagrees with overview Batch Index "
                    f"verify: command={overview_command!r} cwd={overview_cwd_key!r}"
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

# Negation words/phrases (lowercased, word-boundary matched): a Requirements: sentence needs at
# least one of these AND at least one verb form from _PROHIBITION_VERB_FORMS to be
# prohibition-exempt.
# Note: "do not", "does not", "must not", and "shall not" each contain the standalone word "not"
# and so are logically subsumed by the bare "not" entry below -- they are kept anyway, spelled
# out in full, purely for self-documentation (so this tuple reads as a list of real phrasings,
# not just an algebra of parts).
_PROHIBITION_NEGATIONS = (
    "do not", "don't",
    "does not", "doesn't",
    "never",
    "must not",
    "cannot", "can't",
    "shall not",
    "won't",
    "forbid", "forbids", "forbidden",
    "not",
)

# Verb base forms mapped to their full inflected-form set (base, third-person, past, gerund, plus
# hand-added irregulars) -- a Requirements: sentence pairs one of these forms with a negation from
# _PROHIBITION_NEGATIONS to be prohibition-exempt. Silent-e-drop (change/use/reference/include/
# update/remove/delete/rename/move/create/cite), y->i (modify), sibilant -es (touch), and write's
# fully suppletive forms (wrote/written) are derived by hand per standard English orthography, not
# by naive suffix concatenation. "read" collapses to 3 forms (base/-s/-ing) since its past tense is
# spelled identically to its base form -- "readed" is not a word.
_PROHIBITION_VERB_FORMS = {
    "touch": ("touch", "touches", "touched", "touching"),
    "change": ("change", "changes", "changed", "changing"),
    "modify": ("modify", "modifies", "modified", "modifying"),
    "edit": ("edit", "edits", "edited", "editing"),
    "add": ("add", "adds", "added", "adding"),
    "link": ("link", "links", "linked", "linking"),
    "read": ("read", "reads", "reading"),
    "use": ("use", "uses", "used", "using"),
    "reference": ("reference", "references", "referenced", "referencing"),
    "include": ("include", "includes", "included", "including"),
    "update": ("update", "updates", "updated", "updating"),
    "remove": ("remove", "removes", "removed", "removing"),
    "delete": ("delete", "deletes", "deleted", "deleting"),
    "alter": ("alter", "alters", "altered", "altering"),
    "rename": ("rename", "renames", "renamed", "renaming"),
    "move": ("move", "moves", "moved", "moving"),
    "create": ("create", "creates", "created", "creating"),
    "write": ("write", "writes", "wrote", "writing", "written"),
    "mention": ("mention", "mentions", "mentioned", "mentioning"),
    "cite": ("cite", "cites", "cited", "citing"),
}

_PROHIBITION_NEGATION_RE = re.compile(
    "|".join(r"\b" + re.escape(w) + r"\b" for w in _PROHIBITION_NEGATIONS)
)
_PROHIBITION_VERB_RE = re.compile(
    "|".join(
        r"\b" + re.escape(form) + r"\b"
        for forms in _PROHIBITION_VERB_FORMS.values()
        for form in forms
    )
)


def _is_prohibition_exempt(lowered_line: str) -> bool:
    """Return True when ``lowered_line`` (already lowercased) pairs a negation word/phrase from
    _PROHIBITION_NEGATIONS with a verb form from _PROHIBITION_VERB_FORMS anywhere on the line
    (line-wide match, not positionally adjacent -- same granularity as the citation-marker check).

    Known limitations (not handled -- see _mill/discussion.md):
    - Nested-bullet/multi-line prohibitions (negation on a parent bullet, path on a child bullet)
      are not detected -- this check is scoped to a single physical line.
    - Double-negative phrasing ("do not skip touching `foo.py`", "do not forget to read `bar.py`")
      is misdetected as exempt even though the path SHOULD be touched/read -- this is a lexical
      word-set match, not a semantic parse.
    """
    return bool(_PROHIBITION_NEGATION_RE.search(lowered_line)) and bool(
        _PROHIBITION_VERB_RE.search(lowered_line)
    )


def _clause_bounds(
    lowered_line: str, start: int, end: int, *, extra_boundaries: list[int] | None = None,
) -> tuple[int, int]:
    """Return the (start, end) offsets of the clause containing the ``[start, end)`` span in
    ``lowered_line``.

    A clause is delimited by comma/semicolon/colon/period (``_RE_CLAUSE_BOUNDARY``) on either side,
    or by the line's own edges when no such punctuation exists on that side.
    Shared by the negation-phrase and contrast-citation exemptions so neither reaches across an
    unrelated clause on the same Requirements: line.

    ``extra_boundaries`` (a sorted list of offsets, used by the line-join-refactor Decision to cap a
    clause at the current run's own physical-line boundaries) additionally stops the clause-start
    search at the highest entry ``<= start`` and the clause-end search at the lowest entry ``>=
    end``, each compared against the punctuation-based candidate on its own side -- whichever
    candidate is CLOSER to ``start``/``end`` wins on each side independently. ``None`` (the default)
    leaves behavior byte-for-byte identical to before this parameter existed.
    """
    clause_start = 0
    for boundary in _RE_CLAUSE_BOUNDARY.finditer(lowered_line[:start]):
        clause_start = boundary.end()
    boundary_after = _RE_CLAUSE_BOUNDARY.search(lowered_line, end)
    clause_end = boundary_after.start() if boundary_after else len(lowered_line)

    if extra_boundaries:
        line_boundary_start = max(
            (b for b in extra_boundaries if b <= start), default=None,
        )
        if line_boundary_start is not None and line_boundary_start > clause_start:
            clause_start = line_boundary_start
        line_boundary_end = min(
            (b for b in extra_boundaries if b >= end), default=None,
        )
        if line_boundary_end is not None and line_boundary_end < clause_end:
            clause_end = line_boundary_end

    return clause_start, clause_end


_RE_NEGATION_NO_WORD = re.compile(r"\bno\b")
_RE_NEGATION_IS_INVOLVED = re.compile(r"\bis involved\b")
_RE_NEGATION_WITHOUT_IMMEDIATE = re.compile(r"\bwithout\s*`?\s*$")
_RE_NEGATION_IS_NOT_VERB = re.compile(r"\bis not\b.*\b(?:involved|needed|required|used)\b")


def _is_non_dependency_negation_exempt(
    lowered_line: str, token_start: int, token_end: int, line_boundaries: list[int] | None = None,
) -> bool:
    """
    Return True when the token occurrence at ``[token_start, token_end)`` in ``lowered_line`` is
    positioned by the surrounding prose as explicitly NOT a dependency, rather than merely
    mentioned near a negation word anywhere on the line.

    Supports three phrase templates, each clause-scoped via ``_clause_bounds`` so intervening words
    are allowed but never across a comma/semicolon/colon/period:
    1. the token preceded by "no" and followed by "is involved" (e.g. "no `x.py` is involved"),
    2. the token immediately preceded by "without" (e.g. "without `x.py`"), with no intervening
       words -- unlike the other two templates, "without" only reads as a dependency-negating
       preposition when it sits right next to the token,
    3. the token followed by "is not" plus one of "involved"/"needed"/"required"/"used".

    This exemption exists as a separate, positional check rather than widening
    ``_is_prohibition_exempt``'s word-set with "no" plus the verbs "involve"/"need"/"require"/
    "exist": ``_is_prohibition_exempt`` matches line-wide with no positional requirement, so a bare
    "no" paired with any of its roughly twenty existing verb forms anywhere on the line would exempt
    a large share of ordinary Requirements prose that has nothing to do with the token being
    checked.

    ``line_boundaries`` (line-join-refactor Decision) is forwarded straight through to
    ``_clause_bounds``'s ``extra_boundaries`` keyword, capping the clause at the current run's own
    physical-line boundaries when ``lowered_line`` spans more than one joined physical line.
    """
    clause_start, clause_end = _clause_bounds(
        lowered_line, token_start, token_end, extra_boundaries=line_boundaries,
    )
    before = lowered_line[clause_start:token_start]
    after = lowered_line[token_end:clause_end]

    if _RE_NEGATION_NO_WORD.search(before) and _RE_NEGATION_IS_INVOLVED.search(after):
        return True
    if _RE_NEGATION_WITHOUT_IMMEDIATE.search(before):
        return True
    return bool(_RE_NEGATION_IS_NOT_VERB.search(after))


# Contrast markers: naming a rejected alternative alongside the chosen one (e.g. "`new.py` rather
# than `old.py`"). Unlike the narrow existing _CITATION_MARKERS entries ("e.g.", "signature
# inlined"), "rather than" and "instead of" are ordinary connective English that also appears in
# genuine dependency prose ("read `config.py` instead of hardcoding the value"), so a line-wide
# substring match would wrongly exempt real dependencies -- these are matched only with the
# clause-scoped adjacency requirement in ``_is_contrast_citation_exempt`` below, never folded into
# _CITATION_MARKERS.
_CONTRAST_MARKERS = ("rather than", "instead of")


def _is_contrast_citation_exempt(
    lowered_line: str, token_start: int, token_end: int, line_boundaries: list[int] | None = None,
) -> bool:
    """
    Return True when a contrast marker (``_CONTRAST_MARKERS``) shares the token occurrence's
    clause, per ``_clause_bounds``.

    Sharing a clause covers both directions the motivating phrasing takes -- the token can be the
    chosen alternative appearing before the marker, or the rejected one appearing after it -- since
    a clause by definition has no comma/semicolon/colon/period between its ends.

    ``line_boundaries`` (line-join-refactor Decision) is forwarded straight through to
    ``_clause_bounds``'s ``extra_boundaries`` keyword, capping the clause at the current run's own
    physical-line boundaries when ``lowered_line`` spans more than one joined physical line.
    """
    clause_start, clause_end = _clause_bounds(
        lowered_line, token_start, token_end, extra_boundaries=line_boundaries,
    )
    clause_text = lowered_line[clause_start:clause_end]
    return any(marker in clause_text for marker in _CONTRAST_MARKERS)


# Citation-marker substrings: a Requirements: sentence containing one of these (lowercased) names a file as an illustrative example or citation, not as an unlisted read dependency, so a backtick token on that line is exempt from flagging. "signature inlined" and "no file read needed" additionally cover the case where a Requirements: line inlines a cited symbol's full signature and therefore needs no file read, which is why naming the defining file on that line is not an unlisted read dependency. "mentioned, not read" is the planner's explicit escape hatch for a mention that no structural or phrasing rule below reaches -- a bare line-wide substring match is correct for it, exactly like "signature inlined" and "no file read needed", because the phrase is unambiguous and would not appear by accident.
_CITATION_MARKERS = (
    "as an example",
    "as examples",
    "for example",
    "e.g.",
    "such as",
    "cited as",
    "citing",
    "signature inlined",
    "no file read needed",
    "mentioned, not read",
)

# A backtick-quoted token counts as path-candidate-shaped when it contains a path separator or ends with one of these extensions; anything else (a JSON key, a function name, a sentinel string) is silently ignored. Shared by every path-vs-symbol classification in this module (context-completeness's own check, its literal-enumeration exemption, and cross-batch-build-break's rename/removal candidate filter) so the extension list can never silently drift between checks (#1056 plan-review round 2 finding).
_PATH_CANDIDATE_EXTENSIONS = (
    ".py", ".go", ".cs", ".ts", ".md", ".yaml", ".yml", ".json", ".js", ".txt", ".sh",
    ".rs", ".java", ".rb", ".toml", ".cfg", ".ini", ".html", ".css",
)

# Source-code extensions searched when resolving a symbol-shaped (not path-shaped) backtick token.
# A standalone tuple rather than a slice of _PATH_CANDIDATE_EXTENSIONS, so this list never silently
# drifts if that constant's ordering or membership changes for unrelated (path-branch) reasons.
_SYMBOL_SEARCH_EXTENSIONS = (".py", ".go", ".cs", ".ts")


# Per-line backtick-token matcher, promoted from a local variable inside
# _check_context_completeness so _is_literal_enumeration_exempt can reuse the identical pattern.
_BACKTICK_RE = re.compile(r"`([^`]+)`")

# Matches an inline `modifier+ identifier = value` declaration (e.g. "private const double
# StepDurationS = 10.0") that has no surrounding parens/braces for _compute_declared_symbols_union's
# existing candidate-span detection to find. Requires at least one preceding whitespace-separated
# token before the captured identifier, so a bare "identifier = value" span with nothing in front of
# the identifier never matches -- that shape is ordinary prose citing an existing symbol's current
# value, not a new declaration (#1119).
_RE_INLINE_ASSIGN_DECLARATION = re.compile(r"^(?:\S+\s+)+([A-Za-z_]\w*)\s*=")

# Ownership-attribution verb forms (lowercased, word-boundary matched, hand-spelled per verb --
# base/3rd-person/past/gerund, "rewrite" given the same irregular 5-form treatment "write" gets
# in _PROHIBITION_VERB_FORMS): a same-line "batch|card <N> <verb>" phrase names another card/batch
# as the owner of the token, not a dependency this card itself reads.
_OWNERSHIP_VERB_FORMS = {
    "own": ("own", "owns", "owned", "owning"),
    "fix": ("fix", "fixes", "fixed", "fixing"),
    "correct": ("correct", "corrects", "corrected", "correcting"),
    "rewrite": ("rewrite", "rewrites", "rewrote", "rewriting", "rewritten"),
    "address": ("address", "addresses", "addressed", "addressing"),
    "handle": ("handle", "handles", "handled", "handling"),
    "resolve": ("resolve", "resolves", "resolved", "resolving"),
    "cover": ("cover", "covers", "covered", "covering"),
    "edit": ("edit", "edits", "edited", "editing"),
    "update": ("update", "updates", "updated", "updating"),
}

_OWNERSHIP_RE = re.compile(
    r"\b(?:batch|card)\s+\d+(?:'s)?\s+(?:"
    + "|".join(
        re.escape(form)
        for forms in _OWNERSHIP_VERB_FORMS.values()
        for form in forms
    )
    + r")\b"
)


def _is_cross_card_ownership_exempt(lowered_line: str) -> bool:
    """Return True when ``lowered_line`` (already lowercased) contains a same-line
    "batch|card <N> <ownership-verb>" phrase (optionally possessive, e.g. "batch 8's fix"),
    independent of the token's own position -- mirrors ``_is_prohibition_exempt``'s line-wide (not
    clause-scoped) granularity, not ``_is_contrast_citation_exempt``'s clause-wide one, because the
    motivating real-world phrasing ("...`x.cs`, which batch 8 fixes.") puts a comma between the
    token and the ownership phrase, which `_clause_bounds` would treat as a clause boundary.
    Accepted tradeoff: an unrelated "batch N fixes" mention elsewhere on an unusually long
    Requirements: line exempts every backtick token on that line, not just the one the phrase
    refers to -- the same false-negative-adjacent tradeoff `_is_prohibition_exempt`'s own
    line-wide match already accepts.
    """
    return bool(_OWNERSHIP_RE.search(lowered_line))


def _is_literal_enumeration_exempt(line: str, token_start: int, token_end: int) -> bool:
    """Return True when the token occurrence at ``[token_start, token_end)`` in ``line`` sits on a
    line carrying 3 or more backtick-quoted tokens total, where non-shaped tokens are a STRICT
    majority of the line's backtick tokens (self-inclusive tally: the tested occurrence counts
    toward both the total and its own shape classification) -- the signal that the whole line lists
    literal test-input values, not dependencies.

    Every match in the line (the tested occurrence included) is classified as shaped
    (``"/" in token or token.endswith(_PATH_CANDIDATE_EXTENSIONS)`` OR ``_symbol_candidate_shape``
    is not ``None``) or non-shaped; ``non_shaped_count`` must exceed ``shaped_count`` for the
    exemption to fire. An exact tie is NOT a majority and does not exempt (literal-enumeration-
    majority Decision, #1116/#1122). A genuine multi-file dependency enumeration ("reads `a.py`,
    `b.py`, and `c.py`") contains only path-shaped tokens (0 non-shaped) and never trips this rule.
    The 3-token threshold sits safely above ordinary 2-token contrastive prose ("`x.py` and
    `y.py`"), which is common in genuine dependency sentences and must never be swept in.

    Accepted tradeoff: a genuine dependency line whose non-path/non-symbol literals (e.g. CLI flags
    or sentinel strings) outnumber its real file/symbol tokens is wrongly swept in and its real
    tokens suppressed -- the same kind of tradeoff `_is_prohibition_exempt`'s and
    `_CITATION_MARKERS`' own docstrings already accept for their own line-wide mechanisms.
    """
    matches = list(_BACKTICK_RE.finditer(line))
    if len(matches) < 3:
        return False
    shaped_count = 0
    non_shaped_count = 0
    for m in matches:
        other = m.group(1)
        other_is_path_shaped = "/" in other or other.endswith(_PATH_CANDIDATE_EXTENSIONS)
        if other_is_path_shaped or _symbol_candidate_shape(other) is not None:
            shaped_count += 1
        else:
            non_shaped_count += 1
    return non_shaped_count > shaped_count


# Output/rendering verb forms (lowercased, word-boundary matched, hand-spelled per verb --
# base/3rd-person/past/gerund, same shape as _PROHIBITION_VERB_FORMS): a line naming a
# rendered/emitted/printed/displayed/output value describes that string as a described program
# output, not a file the card reads.
_OUTPUT_VERB_FORMS = {
    "emit": ("emit", "emits", "emitted", "emitting"),
    "render": ("render", "renders", "rendered", "rendering"),
    "output": ("output", "outputs", "outputted", "outputting"),
    "print": ("print", "prints", "printed", "printing"),
    "display": ("display", "displays", "displayed", "displaying"),
}

_OUTPUT_VERB_RE = re.compile(
    "|".join(
        r"\b" + re.escape(form) + r"\b"
        for forms in _OUTPUT_VERB_FORMS.values()
        for form in forms
    )
)


def _is_illustrative_output_exempt(lowered_line: str) -> bool:
    """Return True when ``lowered_line`` (already lowercased) contains any `_OUTPUT_VERB_FORMS`
    form anywhere on the line, independent of the token's own position -- structurally a
    single-marker line-wide presence test, like the `_CITATION_MARKERS` substring check, not a
    two-set AND-pairing like `_is_prohibition_exempt`'s negation-word-plus-verb-form gate. Exists
    because a line such as "an answer emitting the bare `README.md`, never `./README.md`" names
    the token as the function's rendered *output value*, not a file it reads.
    """
    return bool(_OUTPUT_VERB_RE.search(lowered_line))


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
    headers (single-line or multi-line sub-bullet form) with BOTH halves of its Moves: pairs --
    the card declaring a rename is exactly the one whose Requirements: legitimately describes what
    happens to the destination, so a not-yet-existing Move target it names is still "already
    declared" for that card's own purposes.
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
                tokens.add(pair_m.group(2))
            k += 1

    return tokens


# Trailing balanced-bracket groups stripped (repeatedly, from the end) when detecting a symbol-shaped
# token's call/generic suffix -- e.g. "GetItems<T>()" strips to "GetItems" via two passes (the "()"
# group, then the "<T>" group).
_RE_TRAILING_PAREN_GROUP = re.compile(r"\([^()]*\)$")
_RE_TRAILING_BRACKET_GROUP = re.compile(r"\[[^\[\]]*\]$")
_RE_TRAILING_ANGLE_GROUP = re.compile(r"<[^<>]*>$")
_RE_TRAILING_GROUPS = (
    _RE_TRAILING_PAREN_GROUP,
    _RE_TRAILING_BRACKET_GROUP,
    _RE_TRAILING_ANGLE_GROUP,
)

# A bare-or-dotted identifier shape: one or two dot-separated `\w`-segments, each starting with a
# letter or underscore. Matched AFTER line-range and call/generic-suffix stripping.
_RE_SYMBOL_SHAPE = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)?$")

# Matches an optional leading `identifier(: Type)? = ` assignment-target prefix (e.g. "x = " or
# "x: mod.Type = ") stripped once, unconditionally, from a symbol candidate token's base -- a no-op
# when the token has no `=` (#1115).
_RE_LEADING_ASSIGN_PREFIX = re.compile(r"^[A-Za-z_]\w*\s*(?::\s*[A-Za-z_][\w<>\[\], .]*)?\s*=\s*")


def _symbol_candidate_shape(token: str) -> tuple[str, str | None] | None:
    """Return the symbol search key (and dotted qualifier, if any) for a NOT-path-shaped
    Requirements: backtick token, or None.

    ``token`` is an original backtick-quoted token the caller has already confirmed is not
    path-shaped (no ``/``, doesn't end in a recognized source extension) -- this function does not
    re-check that.
    Strips a trailing ``:line-range`` suffix and any trailing call/generic suffix (one or more
    trailing balanced ``()``/``[...]``/``<...>`` groups, e.g. ``GetItems<T>()`` -> ``GetItems``),
    then strips an optional leading ``identifier(: Type)? = `` assignment-target prefix once (e.g.
    ``x = mod.get_value`` -> ``mod.get_value``, #1115), then requires what remains to look like a
    bare identifier (``SaveState``) or a dotted qualifier.identifier pair (``reedengine.New``).
    A bare or trailing-segment identifier only "qualifies" as a symbol candidate -- as opposed to an
    ordinary lowercase English word like ``config`` -- when it is longer than one character AND
    either not entirely lowercase (contains an uppercase letter, including possibly its first
    character) or contains an underscore; a length-1 identifier never qualifies regardless of
    case/underscore content, since single-letter receiver/loop/parameter variables are near-
    universal convention across Go/C#/TS/Python and essentially never disambiguate a real
    project-specific symbol.
    For a dotted pair, only the trailing (second) segment's own qualification matters, since the
    trailing segment is the only part ever used as the filesystem search key -- but a dotted token
    whose QUALIFIER segment (the first segment, e.g. ``t`` in ``t.Cleanup``) is length 1 is not
    symbol-shaped AT ALL (the whole token returns ``None``), not merely exempt from qualifier-based
    disambiguation downstream -- a single-letter qualifier is essentially always a stdlib/BCL-
    receiver-shaped convention (Go's idiomatic ``*testing.T`` receiver name ``t``, for example),
    never a project-specific package/namespace worth resolving through.

    Returns:
        ``None`` when the token is not symbol-shaped (or doesn't qualify).
        Otherwise a ``(search_key, qualifier)`` tuple: ``search_key`` is the bare identifier, or the
        dotted pair's trailing segment -- exactly what this function used to return on its own;
        ``qualifier`` is the dotted pair's leading segment (``segments[0]``) for a two-segment token,
        else ``None`` for a bare-identifier token.
    """
    base = _RE_LINE_RANGE.sub("", token)
    while True:
        stripped_any = False
        for group_re in _RE_TRAILING_GROUPS:
            match = group_re.search(base)
            if match:
                base = base[: match.start()]
                stripped_any = True
                break
        if not stripped_any:
            break

    # Strip an optional leading "identifier(: Type)? = " assignment-target prefix once -- a no-op
    # when the token has no "=" (#1115). Every downstream qualifies()/qualifier/dotted-pair check
    # below operates on the resulting `base`, unmodified otherwise.
    base = _RE_LEADING_ASSIGN_PREFIX.sub("", base, count=1)

    if not _RE_SYMBOL_SHAPE.match(base):
        return None

    segments = base.split(".")

    def qualifies(segment: str) -> bool:
        return len(segment) > 1 and (segment != segment.lower() or "_" in segment)

    if len(segments) == 1:
        return (base, None) if qualifies(base) else None

    trailing_segment = segments[-1]
    qualifier = segments[0]
    if len(qualifier) <= 1:
        return None
    return (trailing_segment, qualifier) if qualifies(trailing_segment) else None


_RE_CS_TEST_STEM = re.compile(r"Tests?$")


def _is_conventional_test_file(path: Path) -> bool:
    """
    Return True when `path` follows a conventional test-file naming pattern for its own language.

    `.go`: stem ends with `_test` (Go's own test-file convention, e.g. `cleanup_test.go`).
    `.py`: stem starts with `test_` or ends with `_test` (pytest/unittest conventions).
    `.cs`: stem ends with `Test` or `Tests` (xUnit/NUnit/MSTest convention, e.g. `FooTests.cs`).
    `.ts`: stem ends with `.test` or `.spec` (Jest/Jasmine convention -- `Path("foo.test.ts").stem`
    is `"foo.test"`, so this checks the stem's own suffix, not a second `.suffix` lookup).

    A symbol declared ONLY in a test file must never be surfaced by `_resolve_symbol_files` as a
    dependency a card should add to its read-only `Context:` -- a bulk-mode reviewer would never
    expect another package's test file there.
    """
    stem = path.stem
    suffix = path.suffix
    if suffix == ".go":
        return stem.endswith("_test")
    if suffix == ".py":
        return stem.startswith("test_") or stem.endswith("_test")
    if suffix == ".cs":
        return bool(_RE_CS_TEST_STEM.search(stem))
    # suffix == ".ts" (the only remaining member of _SYMBOL_SEARCH_EXTENSIONS)
    return stem.endswith((".test", ".spec"))


def _resolve_symbol_files(
    search_key: str,
    candidate_files: list[Path],
    cache: dict[str, list[Path]],
) -> list[Path]:
    """Resolve ``search_key`` to its declaring file(s) among ``candidate_files`` only.

    ``candidate_files`` is the caller-supplied, already-resolved file set to search -- the plan-wide
    union of files cited somewhere in the plan (``_compute_plan_wide_cited_files``), per the
    resolution-scope-rework Decision. This function does no filesystem walking of its own and takes
    no ``project_root``/``root``/``git_root`` -- narrowing *where* the search looks is the caller's
    job now, not this function's.

    For each file in ``candidate_files`` whose suffix is in ``_SYMBOL_SEARCH_EXTENSIONS`` and that
    ``_is_conventional_test_file`` does not identify as a conventional test file (a symbol declared
    only in a test file is never surfaced as a dependency), checks whether any line of its text
    matches a declaration-form pattern for that extension (a top-level or grouped-block declaration
    for ``.go``, a type/member declaration for ``.cs``, a ``def``/``class``/module-level-assignment
    for ``.py``, or a function/class/interface/type/enum/const/let/var declaration for ``.ts``) -- a
    bare usage site, comment, or string/template-literal occurrence of ``search_key`` no longer
    counts.

    Memoized via ``cache`` (keyed by ``search_key``): a repeated call with the same key returns the
    cached result without re-reading any file, since a symbol name commonly recurs across many
    cards/batches in one ``run()`` invocation.

    Returns:
        The list of matching file paths (from ``candidate_files``, in their original order) --
        ``[]`` when none of ``candidate_files`` declares ``search_key``.
    """
    if search_key in cache:
        return cache[search_key]

    sym = re.escape(search_key)

    # .go: a top-level `func`/`type`/`const`/`var` declaration line, or a member line inside an
    # unclosed `const (` / `var (` / `type (` grouped-declaration block.
    go_top_level_re = re.compile(
        r"^(?:func\s+(?:\([^)]*\)\s*)?" + sym + r"\s*[(\[]|(?:type|const|var)\s+" + sym + r"\b)"
    )
    go_group_open_re = re.compile(r"^(const|var|type)\s*\($")
    go_group_close_re = re.compile(r"^\)\s*$")
    go_group_member_re = re.compile(r"^\s*" + sym + r"\b")

    # .cs: a type-level declaration, or a member-level declaration guarded by an access modifier.
    # A literal `new` keyword between the modifier and the symbol is unambiguously a construction
    # expression (e.g. `throw new InvalidOperationException(...)`, `= new Foo();`), never a member
    # declaration, so it is excluded from matching.
    cs_type_re = re.compile(r"\b(?:class|struct|interface|enum|record)\s+" + sym + r"\b")
    cs_member_re = re.compile(
        r"\b(?:public|private|protected|internal)\b(?:(?!\bnew\b).)*?\b" + sym + r"\b\s*[({;=]"
    )

    # .py: a `def`/`class` declaration, or a module-level (column-0) assignment/annotation.
    py_def_re = re.compile(r"^\s*(?:def|class)\s+" + sym + r"\b")
    py_module_assign_re = re.compile(r"^" + sym + r"\s*(?::\s*\S.*)?=")

    # .ts: a type-level declaration, or an (optionally exported) const/let/var declaration.
    ts_type_re = re.compile(r"\b(?:function|class|interface|type|enum)\s+" + sym + r"\b")
    ts_var_re = re.compile(r"\b(?:export\s+)?(?:const|let|var)\s+" + sym + r"\b")

    def _has_declaration(file_path: Path, content: str) -> bool:
        """Return True when at least one line of ``content`` is a declaration-form match.

        Which pattern(s) apply is determined by ``file_path``'s suffix.
        """
        suffix = file_path.suffix
        if suffix == ".go":
            in_go_group = False
            for line in content.splitlines():
                if go_top_level_re.match(line):
                    return True
                if go_group_open_re.match(line):
                    in_go_group = True
                    continue
                if in_go_group and go_group_close_re.match(line):
                    in_go_group = False
                    continue
                if in_go_group and go_group_member_re.match(line):
                    return True
            return False
        if suffix == ".cs":
            return any(
                cs_type_re.search(line) or cs_member_re.search(line)
                for line in content.splitlines()
            )
        if suffix == ".py":
            return any(
                py_def_re.match(line) or py_module_assign_re.match(line)
                for line in content.splitlines()
            )
        # suffix == ".ts" (the only remaining member of _SYMBOL_SEARCH_EXTENSIONS)
        return any(
            ts_type_re.search(line) or ts_var_re.search(line) for line in content.splitlines()
        )

    matches: list[Path] = []
    for file_path in candidate_files:
        if file_path.suffix not in _SYMBOL_SEARCH_EXTENSIONS:
            continue
        if _is_conventional_test_file(file_path):
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            # Broken symlink, permission-denied, or any other unreadable-file condition under an
            # arbitrary real-world project tree -- skip it, don't crash the run.
            continue
        if _has_declaration(file_path, content):
            matches.append(file_path)

    cache[search_key] = matches
    return cache[search_key]


# Package/namespace-declaration line, per extension, used by _filter_matches_by_qualifier: group 1
# captures the declared package/namespace name. .py has no such construct -- a .py candidate never
# has a qualifier-declaring line and is therefore never added to package_matches.
_RE_GO_PACKAGE = re.compile(r"^package\s+(\w+)$")
_RE_NAMESPACE = re.compile(r"^namespace\s+([\w.]+)")


def _filter_matches_by_qualifier(matches: list[Path], qualifier: str) -> list[Path]:
    """Narrow an ambiguous multi-file symbol match down using a dotted token's qualifier segment.

    Called by ``_check_context_completeness`` only when a dotted Requirements: token
    (``qualifier.SymbolName``) resolved to more than one candidate file -- ``_resolve_symbol_files``
    itself never applies this filtering, so its cache stays qualifier-independent.

    First tries a package/namespace match: for each candidate, reads its first
    ``package <name>`` line (``.go``) or ``namespace <name>`` line (``.cs``/``.ts``, compared against
    the LAST dot-separated segment of the captured name), and keeps candidates whose declared
    package/namespace equals ``qualifier``. A ``.py`` candidate, or a ``.go``/``.cs``/``.ts``
    candidate with no such line, is never counted as a package/namespace match.
    When exactly one candidate survives this pass, returns it.

    Otherwise falls back to directory-basename matching over the ORIGINAL ``matches`` list: keeps
    every candidate whose parent directory's name case-insensitively equals ``qualifier``.
    This fallback result is returned regardless of its length (0, 1, or more than 1) -- the caller's
    existing ``len(...) != 1`` guard already treats those outcomes correctly.

    Returns:
        The package/namespace-narrowed list when it has exactly one entry, else the
        directory-basename-narrowed list (which may be empty, a singleton, or still ambiguous).
    """
    package_matches: list[Path] = []
    for candidate in matches:
        if candidate.suffix == ".py":
            continue
        try:
            content = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            # Unreadable since the original walk populated `matches` -- exclude, not an error.
            continue
        declared = None
        if candidate.suffix == ".go":
            for line in content.splitlines():
                match = _RE_GO_PACKAGE.match(line)
                if match:
                    declared = match.group(1)
                    break
        else:  # .cs or .ts
            for line in content.splitlines():
                match = _RE_NAMESPACE.match(line)
                if match:
                    declared = match.group(1).split(".")[-1]
                    break
        if declared == qualifier:
            package_matches.append(candidate)

    if len(package_matches) == 1:
        return package_matches

    return [p for p in matches if p.parent.name.lower() == qualifier.lower()]


def _covered_by_own_refs(candidate: str, own_refs: set[str], moves_sources: set[str]) -> bool:
    """Return True when ``candidate`` is already covered by a card's own declared refs.

    Covered when ``candidate`` is in ``own_refs`` directly, is a plan-wide ``Moves:`` source, or (for
    a bare filename with no ``/``) shares its basename with some entry in ``own_refs``.
    """
    return (
        candidate in own_refs
        or candidate in moves_sources
        or (
            "/" not in candidate
            and any(Path(candidate).name == Path(entry).name for entry in own_refs)
        )
    )


def _is_confirmed_git_ignored(
    candidate: Path,
    project_root: Path,
    git_root: Path | None,
    wiki_root: Path | None,
    ignore_memo: dict[Path, bool],
) -> bool:
    """
    Return True when ``candidate`` (an existing, resolvable Requirements: path reference) is
    confirmed git-ignored under its own source repository root.

    ``candidate`` arrives unresolved from ``resolve_existing_paths`` and ``Path.is_relative_to`` is
    a lexical prefix comparison that does not collapse parent-directory segments, so both
    ``candidate`` and each root are ``.resolve()``-d before comparison -- the same reasoning the
    out-of-repo-literal exemption's second half applies.
    The candidate's own source root is the first of ``git_root``, ``project_root``, ``wiki_root`` (in
    that order, skipping any that is ``None``) it is relative to;
    when none matches, the candidate is out-of-repo and this returns False without running any
    subprocess -- the out-of-repo-literal exemption has already handled that case upstream.
    Otherwise runs ``git -C <source_root> check-ignore -q <candidate>`` (with ``quiet_nonzero=True``,
    since exit 1 -- "not ignored" -- is this probe's own routine, non-error outcome) and treats
    returncode 0 as ignored;
    any exception whatsoever, including a non-git source root, is swallowed and treated as
    not-confirmed-ignored, mirroring the ``soft_fail_gitignored`` branch of ``resolve_ref_paths`` in
    ``_review_common.py``.
    That pairing cannot simply be reused here because ``resolve_existing_paths`` returns a flat list
    of paths with no source-root attribution, unlike ``resolve_ref_paths``, which carries
    candidate-and-root pairs.

    Memoized in ``ignore_memo`` (created once per ``_check_context_completeness`` call) by the
    resolved candidate path, so a path recurring across cards costs one subprocess call, not one per
    occurrence.
    """
    resolved_candidate = candidate.resolve()
    if resolved_candidate in ignore_memo:
        return ignore_memo[resolved_candidate]

    source_root: Path | None = None
    for root_candidate in (git_root, project_root, wiki_root):
        if root_candidate is None:
            continue
        resolved_root = root_candidate.resolve()
        if resolved_candidate.is_relative_to(resolved_root):
            source_root = resolved_root
            break

    if source_root is None:
        ignore_memo[resolved_candidate] = False
        return False

    try:
        result = _subprocess_util.run(
            ["git", "-C", str(source_root), "check-ignore", "-q", str(resolved_candidate)],
            quiet_nonzero=True,
        )
        ignored = result.returncode == 0
    except Exception:
        # Any failure whatsoever -- including source_root not being a git repository -- means
        # "not confirmed ignored"; this check never propagates.
        ignored = False

    ignore_memo[resolved_candidate] = ignored
    return ignored


def _card_creates_tokens(card_text: str) -> list[str]:
    """Return this card's own ``Creates:`` backtick tokens, in declaration order.

    Mirrors ``_card_edits_tokens``'s inline/sub-bullet walk via ``_RE_REFS_HEADER``/``_RE_REFS_SUB``,
    scoped to the ``Creates`` field only.
    """
    tokens: list[str] = []
    lines = card_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _RE_REFS_HEADER.match(line)
        if m and m.group(1) == "Creates":
            inline = m.group("inline").strip()
            if inline:
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


def _card_context_tokens(card_text: str) -> list[str]:
    """Return this card's own ``Context:`` backtick tokens, in declaration order.

    Mirrors ``_card_edits_tokens``'s and ``_card_creates_tokens``'s inline/sub-bullet walk via
    ``_RE_REFS_HEADER``/``_RE_REFS_SUB``, scoped to the ``Context`` field only.
    """
    tokens: list[str] = []
    lines = card_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _RE_REFS_HEADER.match(line)
        if m and m.group(1) == "Context":
            inline = m.group("inline").strip()
            if inline:
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


def _card_deletes_tokens(card_text: str) -> list[str]:
    """Return this card's own ``Deletes:`` backtick tokens, in declaration order.

    Mirrors ``_card_edits_tokens``'s and ``_card_creates_tokens``'s inline/sub-bullet walk via
    ``_RE_REFS_HEADER``/``_RE_REFS_SUB``, scoped to the ``Deletes`` field only.
    """
    tokens: list[str] = []
    lines = card_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _RE_REFS_HEADER.match(line)
        if m and m.group(1) == "Deletes":
            inline = m.group("inline").strip()
            if inline:
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


def _card_moves_tokens(card_text: str) -> list[tuple[str, str]]:
    """Return this card's own ``Moves:`` ``(src, dst)`` pairs, in declaration order.

    Mirrors the module-level ``_RE_MOVES_HEADER``/``_RE_MOVE_PAIR`` inline-vs-multi-line-sub-bullet
    walk (see ``_check_move_format``), scoped to one card's ``card_text``.
    A sub-bullet that does not match ``_RE_MOVE_PAIR`` is skipped -- malformed-``Moves:`` reporting
    stays ``move-format``'s job, not this helper's.
    """
    pairs: list[tuple[str, str]] = []
    lines = card_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _RE_MOVES_HEADER.match(line)
        if m:
            inline = m.group("inline").strip()
            if inline:
                # Inline "none" (or any other inline value) has no sub-bullets to walk.
                i += 1
                continue
            j = i + 1
            while j < len(lines):
                sm = _RE_REFS_SUB.match(lines[j])
                if not sm:
                    break
                pm = _RE_MOVE_PAIR.match(sm.group(1).strip())
                if pm:
                    pairs.append((pm.group(1), pm.group(2)))
                j += 1
            i = j
            continue
        i += 1
    return pairs


def _build_creates_declaring_card_map(batch_files: list[Path]) -> dict[str, tuple[int, int]]:
    """
    Return a plan-wide map from each ``Creates:`` token to the composite key of the card declaring
    it: a ``(batch_index, card_number)`` two-tuple, where ``batch_index`` is the token's declaring
    batch file's index in ``batch_files`` (which callers pass already sorted).
    Composite keys compare lexicographically, so this map lets a caller test cross-batch ordering
    without assuming card numbers are monotonic across batches -- ``_check_card_numbering`` enforces
    only within-batch sequencing and cross-batch uniqueness, never cross-batch monotonicity.

    When one token is declared by more than one card (a plan-authoring irregularity that other
    checks may separately flag), the lowest composite key wins.
    """
    declaring: dict[str, tuple[int, int]] = {}
    for batch_index, batch_path in enumerate(batch_files):
        text = batch_path.read_text(encoding="utf-8")
        for card_num, card_lines in _parse_cards(text):
            card_text = "\n".join(card_lines)
            key = (batch_index, card_num)
            for token in _card_creates_tokens(card_text):
                if token not in declaring or key < declaring[token]:
                    declaring[token] = key
    return declaring


def _compute_plan_wide_cited_files(
    batch_files: list[Path],
    project_root: Path,
    root: str | None,
    *,
    wiki_root: Path | None = None,
    git_root: Path | None = None,
) -> dict[str, Path]:
    """
    Return the plan-wide map of every already-cited raw token to its resolved, on-disk file.

    For every batch file in ``batch_files`` (the caller-filtered, sorted, non-overview list
    ``run()`` builds), for every ``(card_num, card_lines)`` pair returned by ``_parse_cards``, unions
    ``_card_own_reference_set(card_text)``'s tokens into one plan-wide ``raw_tokens`` set -- every
    card's ``Context:``/``Edits:``/``Creates:``/``Deletes:``/``Moves:`` token, across every batch.
    For each token in ``sorted(raw_tokens)``, resolves it via ``resolve_existing_paths``; when that
    returns exactly one path and the path is a file, adds ``token -> path`` to the returned dict. A
    token resolving to zero paths (not yet on disk -- an unbuilt ``Creates:``/``Moves:``-target
    token) or to a directory is silently omitted -- no fallback, matching the resolution-scope-rework
    Decision's "unresolvable, never flagged" contract.

    This is ``_resolve_symbol_files``'s new search space: the symbol branch of
    ``_check_context_completeness`` no longer walks the whole repo tree, only the files this map's
    values already name.

    Args:
        batch_files: Sorted list of batch file paths (00-overview.md excluded).
        project_root: Root of the project (typically the worktree root).
        root: Optional root subfolder for source refs.
        wiki_root: Optional wiki root path for wiki/-prefixed refs.
        git_root: Optional repo root for git_root-relative resolution.

    Returns:
        Dict mapping each resolvable raw token to its single resolved on-disk file path.
    """
    raw_tokens: set[str] = set()
    for batch_path in batch_files:
        text = batch_path.read_text(encoding="utf-8")
        for _card_num, card_lines in _parse_cards(text):
            card_text = "\n".join(card_lines)
            raw_tokens.update(_card_own_reference_set(card_text))

    cited: dict[str, Path] = {}
    for token in sorted(raw_tokens):
        resolved = resolve_existing_paths(
            [token], project_root, root, wiki_root=wiki_root, git_root=git_root,
        )
        if len(resolved) == 1 and resolved[0].is_file():
            cited[token] = resolved[0]
    return cited


def _compute_declared_symbols_union(plan_dir: Path) -> set[str]:
    """
    Return the plan-wide union of identifiers declared inside a signature- or struct-literal-shaped
    backtick token anywhere in any card's Requirements: text.

    For every card in the plan (via `_parse_cards` on every `??-*.md` batch file except
    `00-overview.md`), scans its Requirements: text (via `_requirements_fence_aware_body`, the same
    fence-aware extraction `_check_context_completeness` itself uses) for every backtick token
    matching `_BACKTICK_RE` that contains a balanced `(...)` or `{...}` span. For each such token,
    when both a `(...)` and a `{...}` span are present (e.g. a struct-literal token whose field type
    itself contains a function type, `` `type Deps struct { Acquire func() error }` ``), picks
    whichever pair's outermost span is WIDER -- an inner, narrower span (the empty `()` in `func()`
    here) would otherwise win by being checked first and yield an empty, useless `inner` substring.
    Takes the substring between that pair's first opening delimiter and its last closing delimiter,
    splits it on `,`/`;`, and for each non-empty clause adds BOTH its first and its last
    whitespace-separated word to the result set when that word matches `^[A-Za-z_]\\w*$` -- the first
    word covers a Go/Rust-style `name Type` parameter order, the last word covers a C#/TS-style
    `Type name` order.

    When a token has no `(...)`/`{...}` span at all, it is instead tried against
    `_RE_INLINE_ASSIGN_DECLARATION` (a `modifier+ identifier = value` shape, e.g. `` `private const
    double StepDurationS = 10.0` ``) and, on a match, the captured identifier is added directly (#1119).

    This is context-completeness's symbol-branch equivalent of `compute_creates_union`'s path-branch
    plan-wide union: a token this set contains is a symbol the PLAN ITSELF is introducing (a new
    parameter name, a new struct field) rather than a pre-existing repo symbol, so a bare reference
    to it elsewhere in the plan's prose must not be treated as an unlisted dependency.

    Args:
        plan_dir: Directory containing the plan files (00-overview.md + batch files).

    Returns:
        The set[str] of candidate declared-symbol names found across the whole plan. Returns an
        empty set when `plan_dir` does not exist or contains no qualifying tokens.
    """
    if not plan_dir.exists():
        return set()

    declared: set[str] = set()
    bare_word_re = re.compile(r"^[A-Za-z_]\w*$")

    for batch_path in sorted(plan_dir.glob("??-*.md")):
        if batch_path.name == "00-overview.md":
            continue
        text = batch_path.read_text(encoding="utf-8")
        for _card_num, card_lines in _parse_cards(text):
            requirements_text = _requirements_fence_aware_body(card_lines)
            if requirements_text is None:
                continue
            for match in _BACKTICK_RE.finditer(requirements_text):
                token = match.group(1)
                candidate_spans = []
                if "(" in token and ")" in token:
                    candidate_spans.append((token.find("("), token.rfind(")")))
                if "{" in token and "}" in token:
                    candidate_spans.append((token.find("{"), token.rfind("}")))
                if not candidate_spans:
                    # No paren/brace span: try the inline "modifier+ identifier = value" shape
                    # instead (e.g. "private const double StepDurationS = 10.0") before giving up.
                    inline_match = _RE_INLINE_ASSIGN_DECLARATION.match(token)
                    if inline_match:
                        declared.add(inline_match.group(1))
                    continue
                start, end = max(candidate_spans, key=lambda span: span[1] - span[0])
                if end <= start:
                    continue
                inner = token[start + 1:end]
                for clause in re.split(r"[;,]", inner):
                    words = clause.split()
                    if not words:
                        continue
                    for word in (words[0], words[-1]):
                        if bare_word_re.match(word):
                            declared.add(word)

    return declared


def _check_context_completeness(
    batch_files: list[Path],
    project_root: Path,
    root: str | None,
    creates_union: set[str],
    deletes_union: set[str],
    moves_sources: set[str],
    moves_targets: set[str],
    *,
    wiki_root: Path | None = None,
    git_root: Path | None = None,
    creates_declaring_card_map: dict[str, tuple[int, int]] | None = None,
    declared_symbols: set[str] | None = None,
    cited_files_map: dict[str, Path] | None = None,
) -> list[dict]:
    """
    Flag a card's Requirements: prose citing a file or symbol absent from its own refs.

    A ``Requirements:`` field frequently prose-references a file (or a symbol declared in exactly
    one file) the implementer must read or reason about;
    when that file is a genuine dependency it belongs in the card's own ``Context:``/``Edits:`` (or
    ``Creates:``/``Deletes:``/``Moves:``) so a bulk-mode reviewer actually sees it.
    This check heuristically detects the gap in two branches:

    Path branch (unchanged): for each card, every backtick-quoted, path-shaped token in
    ``Requirements:`` (contains ``/`` or ends with a recognized source extension) that
    independently resolves to a real file (on disk, or a plan-wide ``Creates:``/``Deletes:``/
    Moves-target reference) must also appear in that same card's own
    Context:/Edits:/Creates:/Deletes:/Moves:-source set.

    Symbol branch: a backtick token that is NOT path-shaped is first gated by
    ``_symbol_candidate_shape`` -- it must look like a bare or dotted identifier (``SaveState``,
    ``reedengine.New``) that is not just an ordinary lowercase English word, else it is silently
    ignored (same as today's behavior for non-path tokens).
    A token that passes the shape gate is resolved via ``_resolve_symbol_files`` against the
    plan-wide cited-files set (``cited_files_map``'s values, per the resolution-scope-rework
    Decision): memoized per ``run()`` call, it finds every already-cited file containing a
    declaration-form occurrence of the search key. There is no repo-wide fallback -- a symbol whose
    declaring file is not cited anywhere in the plan yet is unresolvable and never flagged.
    A dotted token's qualifier segment (``reedengine`` in ``reedengine.New``) then participates in
    disambiguation: when the resolution above (fresh or cache hit) yields more than one candidate,
    ``_filter_matches_by_qualifier`` narrows it by package/namespace match, falling back to
    directory-basename match, on the caller side -- after every ``_resolve_symbol_files`` call or
    cache hit, never inside ``_resolve_symbol_files`` itself. A bare token (no qualifier) skips this
    filtering unchanged.
    Zero or more-than-one matching file (after any qualifier filtering) means the reference is
    unresolvable-with-confidence and is never flagged;
    exactly one match is canonicalized back to a root-relative path and checked against the card's
    own refs exactly like the path branch.
    The emitted ``message`` for a symbol-branch finding has a fixed format --
    ``"...which resolves to '<path>' -- not in this card's ..."`` -- that a downstream fixer-doc
    check (batch 2 of this task) parses to distinguish the symbol case from the path case;
    this wording must not drift.

    The following exemptions prevent false positives. Unless noted otherwise, an exemption applies
    to both branches:

    1. Prohibition-marker sentences (e.g. "forbid touching `x.py`") name a file the card must NOT
    act on, not an unlisted dependency.
    2. Citation-marker sentences (e.g. naming `x.py` as an example) cite a file for illustration,
    not as an unlisted read dependency.
    This also covers a Requirements: line that inlines a cited symbol's full signature (e.g.
    "signature inlined" or "no file read needed") -- naming the defining file on that line is not
    an unlisted read dependency, since no file read is needed to act on the inlined signature.
    "mentioned, not read" is the planner's explicit escape hatch for a mention that no structural
    or phrasing rule below reaches.
    3. A token matching the plan-wide ``moves_sources`` set is exempt in any later card's
    ``Requirements:``, not just the declaring card's own -- mirrors how ``creates_union``/
    ``deletes_union`` are already plan-wide.
    4. Directory-intent (path branch only): a path-shaped token whose stripped form ends with ``/``
    is an unambiguous authorial statement of directory intent -- a directory can never be a
    ``Context:`` entry.
    5. Out-of-repo path literal (path branch only): a token that is absolute-looking (leading ``/``
    or ``~``, a Windows drive-letter root, or a UNC root) and not ``wiki/``-prefixed, or whose
    resolved existing file(s) are not relative to any in-scope root (``project_root``, ``git_root``,
    ``wiki_root``), cites a file elsewhere on disk rather than a project dependency.
    6. Gitignored path (path branch only): every resolved existing file confirmed git-ignored
    (``git check-ignore``) under its own source root is exempt -- an ignored file cannot be a
    ``Context:``/``Edits:`` entry a bulk-mode reviewer would ever see.
    7. Forward cross-card Creates (path branch only): a not-yet-existing token that some later card
    (by composite ``(batch_index, card_number)`` key) declares in its own ``Creates:`` is exempt --
    the earlier card is reading about a file that will exist once the plan finishes, not citing an
    unlisted dependency of its own.
    8. Non-dependency negation phrasing: the token is positioned by the line as explicitly
    not-involved (e.g. "no `x.py` is involved", "without `x.py`", "`x.py` is not needed").
    9. Contrast-citation: the token shares a clause with "rather than" or "instead of", naming it as
    the chosen or rejected half of an explicit comparison.
    10. Quoted material: the token appears inside a fenced code block or on a blockquote (``>``)
    line within Requirements: -- quoted prose or docs excerpts, not the card's own claims.
    11. Cross-card ownership: a same-line phrase naming another card/batch as the owner of this
    token (e.g. "batch 8 fixes `x.py`", "card 23 corrects ... `y.py`") is not a dependency the card
    itself reads.
    12. Literal-value enumeration (path branch and symbol branch): a line with 3+ backtick tokens
    where non-shaped tokens strictly outnumber path-/symbol-shaped tokens is treated as a literal
    test-input enumeration, not a dependency list.
    13. Illustrative-output framing: a line naming a rendered/emitted/printed/displayed/output value
    (e.g. "emitting the bare `x.md`") cites the string as a described output, not a read dependency.
    14. Same-plan declared symbol (symbol branch only): a search key that some card's Requirements:
    declares as a new function-signature parameter or struct-literal field (extracted from a
    parenthesized/braced backtick token) is a symbol the plan itself is introducing, not an existing
    dependency to resolve.

    Not-shaped-at-all or unresolvable tokens (JSON keys, ordinary lowercase words, sentinel strings)
    are never flagged -- only genuine file/symbol references that this validator can independently
    confirm exist.

    Note: markdown's double-backtick-escape convention (`` `path` ``) is not detected by this regex;
    future citations needing that format should be aware they won't be checked by
    context-completeness.

    Error dict shape: ``{check, batch, card, path, message, line}``.
    The emitted ``message`` wording (both the path-branch and symbol-branch formats) must not drift,
    since a downstream fixer-doc check parses it to distinguish the two cases.

    Args:
        batch_files: Sorted list of batch file paths to validate.
        project_root: Root of the project (typically the worktree root).
        root: Optional root subfolder for source refs.
        creates_union: Plan-wide union of Creates: targets.
        deletes_union: Plan-wide union of Deletes: targets.
        moves_sources: Plan-wide union of Moves: source paths.
        moves_targets: Plan-wide union of Moves: destination paths.
        wiki_root: Optional wiki root path for wiki/-prefixed refs.
        git_root: Optional repo root for git_root-relative resolution.
        creates_declaring_card_map: Plan-wide map from a Creates: token to the composite
            ``(batch_index, card_number)`` key of the card declaring it, used by exemption 7.
            Defaults to ``None`` and is materialized to an empty dict on entry (a mutable default
            argument is never used directly in the signature) -- an empty map yields no forward
            exemptions, which is the correct no-op default.
        declared_symbols: Plan-wide set from ``_compute_declared_symbols_union``, used by exemption
            14. Defaults to ``None`` and is materialized to an empty set on entry (a mutable default
            argument is never used directly in the signature) -- an empty set is the correct no-op
            default.
        cited_files_map: Plan-wide map from ``_compute_plan_wide_cited_files``, the symbol branch's
            search space (resolution-scope-rework Decision). Defaults to ``None`` and is
            materialized to an empty dict on entry (a mutable default argument is never used
            directly in the signature) -- an empty map yields an empty candidate-files set, so the
            symbol branch never resolves anything, the correct no-op default.

    Returns:
        List of error dicts, one per unresolvable-elsewhere Requirements: reference.
    """
    if creates_declaring_card_map is None:
        creates_declaring_card_map = {}
    if declared_symbols is None:
        declared_symbols = set()
    if cited_files_map is None:
        cited_files_map = {}
    errors: list[dict] = []
    backtick_re = _BACKTICK_RE
    # One symbol-resolution cache per run() call, shared across every batch/card, so a search key
    # recurring across the plan is only walked once (see _resolve_symbol_files's memoization).
    search_cache: dict[str, list[Path]] = {}
    # One git-ignore confirmation cache per run() call, keyed by resolved candidate path, so a path
    # recurring across cards costs one `git check-ignore` subprocess, not one per occurrence.
    ignore_memo: dict[Path, bool] = {}
    # The symbol branch's search space: every already-cited file, in a stable (first-citing-token
    # order) sequence. dict.fromkeys de-duplicates while preserving that order.
    candidate_files = list(dict.fromkeys(cited_files_map.values()))
    # Reverse map for canonicalizing a resolved match back to the token that cited it -- since
    # cited_files_map is itself built by iterating sorted(raw_tokens), setdefault keeps whichever
    # citing token sorts alphabetically first among duplicate-path spellings on a rare collision.
    path_to_token: dict[Path, str] = {}
    for token, path in cited_files_map.items():
        path_to_token.setdefault(path, token)

    for batch_index, batch_path in enumerate(batch_files):
        text = batch_path.read_text(encoding="utf-8")
        cards = _parse_cards(text)
        for card_num, card_lines in cards:
            card_text = "\n".join(card_lines)
            # Fence-aware extraction (rather than _extract_requirements_text) so a fence quoting a
            # field-header-shaped line does not truncate the Requirements: body before the
            # quoted-material exemption below ever sees the remainder -- exactly the docs-quoting
            # scenario that exemption exists to fix. _requirements_fence_aware_body is already what
            # the sibling requirements-quote-indent-drift check uses, so both checks now agree about
            # what a fence means.
            requirements_text = _requirements_fence_aware_body(card_lines)
            if requirements_text is None:
                continue

            requirements_lines = requirements_text.splitlines()
            own_refs: set[str] | None = None  # lazily computed per card
            current_card_key = (batch_index, card_num)

            # Line-join-refactor: build maximal runs of contiguous non-quoted physical lines. A
            # quoted region (fenced or blockquoted) always starts a new run, so a backtick match can
            # never span across one -- this is what keeps joined-text tokenization from bridging a
            # dangling backtick across an elided quoted region. A fence-delimiter line itself is
            # EXCLUDED from every run (both the opening and closing delimiter), a deliberate
            # departure from the toggle-only judgment above: a delimiter's own literal backticks
            # must never enter any run's joined_text, where a dangling/odd backtick on an adjacent
            # included line could otherwise spuriously pair with one of them.
            runs: list[list[tuple[int, str]]] = []
            current_run: list[tuple[int, str]] = []
            in_fence = False
            for line_idx, line in enumerate(requirements_lines):
                lstripped = line.lstrip()
                is_fence_marker = lstripped.startswith("```")
                excluded = is_fence_marker or in_fence or lstripped.startswith(">")
                if is_fence_marker:
                    in_fence = not in_fence
                if excluded:
                    if current_run:
                        runs.append(current_run)
                        current_run = []
                    continue
                current_run.append((line_idx, line))
            if current_run:
                runs.append(current_run)

            for run in runs:
                joined_text = "\n".join(line_text for _, line_text in run)
                lowered_joined = joined_text.lower()
                line_starts: list[int] = []
                offset = 0
                for _, line_text in run:
                    line_starts.append(offset)
                    offset += len(line_text) + 1  # +1 accounts for the "\n" joiner between lines
                # extra_boundaries for the two clause-bounded helpers: every boundary except offset
                # 0, which needs no marker (it is already the run's own start).
                clause_line_boundaries = line_starts[1:]

                for match in backtick_re.finditer(joined_text):
                    token = match.group(1)
                    # Locate the run line(s) this match's [start, end) span falls within -- normally
                    # i == j (the common single-line case), but a token whose backtick span crosses
                    # a physical line break inside this run yields j > i.
                    i = bisect.bisect_right(line_starts, match.start(1)) - 1
                    j = bisect.bisect_right(line_starts, match.end(1) - 1) - 1
                    local_text = "\n".join(line_text for _, line_text in run[i : j + 1])
                    local_offset_base = line_starts[i]
                    lowered_local = local_text.lower()
                    local_start = match.start(1) - local_offset_base
                    local_end = match.end(1) - local_offset_base
                    # Shape gate: path-shaped tokens fall through unconditionally; non-path tokens
                    # fall through only when they look like a bare/dotted symbol candidate.
                    is_path_shaped = "/" in token or token.endswith(_PATH_CANDIDATE_EXTENSIONS)
                    if not is_path_shaped:
                        shape_result = _symbol_candidate_shape(token)
                        if shape_result is None:
                            continue
                        search_key, qualifier = shape_result

                        # Same-plan declared-symbol exemption (symbol branch only): a search key
                        # some card's Requirements: declares as a new function-signature parameter
                        # or struct-literal field is not resolved as an unlisted dependency.
                        if search_key in declared_symbols:
                            continue

                    # Prohibition-marker exemption: the line naming this token forbids acting on it, so it is not an unlisted read dependency.
                    if _is_prohibition_exempt(lowered_local):
                        continue

                    # Non-dependency negation phrasing exemption: the line positions this specific
                    # occurrence of the token as explicitly not-involved. This runs immediately
                    # after the prohibition-marker check and before the citation-marker check
                    # (rather than alongside it) so that it matches the exemption's own numbered
                    # enumeration order in the docstring above. Clause-bounded, so it runs against
                    # the whole run's own joined text (never a different run's), capped at this
                    # run's own physical-line boundaries.
                    if _is_non_dependency_negation_exempt(
                        lowered_joined, match.start(1), match.end(1), clause_line_boundaries,
                    ):
                        continue

                    # Citation-marker exemption: the line names this token as an illustrative example or citation, so it is not an unlisted read dependency.
                    if any(marker in lowered_local for marker in _CITATION_MARKERS):
                        continue

                    # Contrast-citation exemption: this occurrence shares a clause with "rather
                    # than"/"instead of", naming it as the chosen or rejected half of a comparison.
                    # Clause-bounded, same run-scoping as the negation-phrasing exemption above.
                    if _is_contrast_citation_exempt(
                        lowered_joined, match.start(1), match.end(1), clause_line_boundaries,
                    ):
                        continue

                    # Cross-card ownership exemption: the line names another card/batch as the
                    # owner of this token, not a dependency this card itself reads.
                    if _is_cross_card_ownership_exempt(lowered_local):
                        continue

                    # Literal-value enumeration exemption: 3+ backtick tokens on this line, at
                    # least one neither path- nor symbol-shaped, marks the whole line as a literal
                    # test-input enumeration rather than a dependency list.
                    if _is_literal_enumeration_exempt(local_text, local_start, local_end):
                        continue

                    # Illustrative-output exemption: the line describes a rendered/emitted output
                    # value, not a file read dependency.
                    if _is_illustrative_output_exempt(lowered_local):
                        continue

                    if is_path_shaped:
                        # Strip a trailing line-range suffix before testing resolvability and matching;
                        # the ORIGINAL token is kept for the emitted error's "path" field.
                        stripped_token = _RE_LINE_RANGE.sub("", token)

                        # Directory-intent exemption: a trailing slash is an unambiguous authorial
                        # statement of directory intent, and a directory can never be a Context:
                        # entry. This test is deliberately filesystem-independent (it never touches
                        # disk) because in a linked git worktree the repository's own `.git` is a
                        # regular file, not a directory, so the existing `is_file()` filter a few
                        # lines below does not suppress a `.git/` token there. It does not remove or
                        # weaken that filter -- this exemption is additive.
                        if stripped_token.endswith("/"):
                            continue

                        # Out-of-repo path literal exemption, first half: an absolute-looking token
                        # (leading "/" or "~", a Windows drive-letter root, or a UNC root) cites a
                        # file elsewhere on disk, not a project dependency -- except a "wiki/"-
                        # prefixed token, which resolve_existing_paths routes to wiki_root, a
                        # legitimate sibling-clone dependency that must not be exempted here.
                        if not stripped_token.startswith("wiki/") and (
                            stripped_token.startswith(("/", "~"))
                            or _RE_WINDOWS_ABS_ROOT.match(stripped_token)
                        ):
                            continue

                        existing = resolve_existing_paths(
                            [stripped_token], project_root, root,
                            wiki_root=wiki_root, git_root=git_root,
                        )
                        existing_files = [p for p in existing if p.is_file()]

                        # Out-of-repo path literal exemption, second half: resolve_existing_paths
                        # builds its candidates by joining the raw token onto a root and never calls
                        # .resolve() itself, and Path.is_relative_to is a pure lexical prefix
                        # comparison that does not collapse parent-directory segments -- so an
                        # uncollapsed ".." prefix would still carry a root's parts as a literal
                        # prefix and be wrongly judged in-repo. Both the candidate and each in-scope
                        # root are .resolve()-d before comparison. wiki_root is one of the in-scope
                        # roots, so this half needs no separate wiki/ carve-out -- omitting either
                        # guard would exempt a legitimate wiki dependency and convert a fixed false
                        # positive into a silent false negative.
                        if existing_files:
                            in_scope_roots = [
                                r.resolve() for r in (project_root, git_root, wiki_root)
                                if r is not None
                            ]
                            if not any(
                                f.resolve().is_relative_to(scope_root)
                                for f in existing_files
                                for scope_root in in_scope_roots
                            ):
                                continue

                        # Gitignored-path exemption: every resolved existing file confirmed
                        # git-ignored under its own source root is not a candidate a bulk-mode
                        # reviewer could ever be shown, so it is not an unlisted dependency.
                        if existing_files and all(
                            _is_confirmed_git_ignored(f, project_root, git_root, wiki_root, ignore_memo)
                            for f in existing_files
                        ):
                            continue

                        resolvable = (
                            bool(existing_files)
                            or stripped_token in creates_union
                            or stripped_token in deletes_union
                            or stripped_token in moves_targets
                        )
                        if not resolvable:
                            continue

                        # Forward cross-card Creates exemption: a not-yet-existing token that some
                        # LATER card (by composite (batch_index, card_number) key, not bare card
                        # number -- _check_card_numbering enforces only within-batch sequencing and
                        # cross-batch uniqueness, never cross-batch monotonicity, so a plan whose
                        # first batch holds cards 4-6 and second batch holds cards 1-3 validates
                        # today, and a bare card-number test would misfire into a false negative on
                        # such a plan) declares in its own Creates: is exempt. The existing_files-
                        # empty clause is required because nothing prevents a Creates: target from
                        # already existing on disk -- an earlier card naming the path may genuinely
                        # be reading the file's current content before a later card replaces it.
                        if (
                            not existing_files
                            and stripped_token in creates_declaring_card_map
                            and creates_declaring_card_map[stripped_token] > current_card_key
                        ):
                            continue

                        if own_refs is None:
                            own_refs = _card_own_reference_set(card_text)

                        if _covered_by_own_refs(stripped_token, own_refs, moves_sources):
                            continue

                        errors.append({
                            "check": "context-completeness",
                            "batch": batch_path.stem,
                            "card": card_num,
                            "path": token,
                            "message": (
                                f"card {card_num}'s Requirements: references '{token}' "
                                f"which is not in this card's "
                                f"Context:/Edits:/Creates:/Deletes:/Moves:-source"
                            ),
                            "line": run[i][1].strip(),
                        })
                    else:
                        # Check the shared cache before calling into _resolve_symbol_files at all --
                        # a recurring search_key across cards/batches then costs one function call
                        # (the actual filesystem walk), not one call per occurrence.
                        if search_key in search_cache:
                            matches = search_cache[search_key]
                        else:
                            matches = _resolve_symbol_files(
                                search_key, candidate_files, search_cache
                            )
                        # Qualifier-based disambiguation: applied on this (caller) side, after the
                        # cache hit or fresh resolution above -- _resolve_symbol_files's own cache
                        # stays qualifier-independent (keyed by search_key alone). A bare token
                        # (qualifier is None) or an already-unambiguous result is left untouched.
                        if qualifier is not None and len(matches) > 1:
                            matches = _filter_matches_by_qualifier(matches, qualifier)
                        if len(matches) != 1:
                            continue

                        canonical = path_to_token[matches[0]]

                        if own_refs is None:
                            own_refs = _card_own_reference_set(card_text)

                        if _covered_by_own_refs(canonical, own_refs, moves_sources):
                            continue

                        errors.append({
                            "check": "context-completeness",
                            "batch": batch_path.stem,
                            "card": card_num,
                            "path": token,
                            "message": (
                                f"card {card_num}'s Requirements: references symbol '{token}', "
                                f"which resolves to '{canonical}' -- not in this card's "
                                f"Context:/Edits:/Creates:/Deletes:/Moves:-source"
                            ),
                            "line": run[i][1].strip(),
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


def _add_n_leading_spaces(text: str, n: int, *, include_blank: bool = False) -> str:
    """Prepend exactly ``n`` space characters to every line of ``text``.

    This is the exact inverse of ``_strip_n_leading_spaces`` -- a fixed per-line add, not a
    re-indent.
    For each line (split via ``.splitlines()``), ``n`` space characters are prepended and the
    lines are rejoined with ``"\\n"``.

    When ``include_blank`` is ``False`` (the default), a line whose ``.strip()`` is empty is
    emitted unchanged rather than padded: a real nested source excerpt usually has genuinely empty
    separator lines, since editors strip trailing whitespace, so the default reproduces the true
    source.
    ``include_blank=True`` covers the less common case of a source that keeps whitespace-only
    indented lines instead of collapsing them to empty ones.
    """
    added_lines = []
    for line in text.splitlines():
        if not include_blank and not line.strip():
            added_lines.append(line)
        else:
            added_lines.append(" " * n + line)
    return "\n".join(added_lines)


def _first_nonblank_line_indent(text: str) -> int | None:
    """Return the leading-space count of the first non-blank line in `text`, or `None` if every
    line is blank.

    Mirrors `_strip_n_leading_spaces`/`_add_n_leading_spaces`'s "skip blank lines" convention -- a
    fence's own baseline indentation is measured from its first line that actually has content.
    """
    for line in text.splitlines():
        if line.strip():
            return len(line) - len(line.lstrip(" "))
    return None


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
    span = _requirements_fence_aware_span(card_lines)
    if span is None:
        return None
    start, end = span
    return "\n".join(card_lines[start:end])


def _requirements_fence_aware_span(card_lines: list[str]) -> tuple[int, int] | None:
    """Return ``(header_index, end_index_exclusive)`` of the Requirements: body in ``card_lines``.

    Same scan as ``_requirements_fence_aware_body`` (which documents the fence-aware stop
    condition); returns ``None`` when no ``- **Requirements:**`` header line exists.
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

    in_fence = False
    j = start + 1
    while j < len(card_lines):
        line = card_lines[j]
        if not in_fence and any_field_header_re.match(line):
            break
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        j += 1

    return start, j


def _requirements_fence_open_lines(card_lines: list[str], card_start_line: int) -> list[int]:
    """
    Return the 1-based batch-file line of each fence's opening delimiter in the Requirements: body.

    Element k-1 is the line of fence k's opening delimiter; ``card_start_line`` is the batch-file
    line of the card's ``### Card N:`` heading (``card_lines[0]``).
    """
    span = _requirements_fence_aware_span(card_lines)
    if span is None:
        return []
    start, end = span
    open_lines: list[int] = []
    in_fence = False
    for index in range(start + 1, end):
        if card_lines[index].lstrip().startswith("```"):
            in_fence = not in_fence
            if in_fence:
                open_lines.append(card_start_line + index)
    return open_lines


def _line_locator(line: int | None, suffix: str | None = None) -> str:
    """
    Render the ``(line L)`` message fragment, or an empty string when ``line`` is unknown.

    A non-empty result carries a trailing space so it splices between message words;
    ``suffix`` (e.g. ``new/replacement code``) is appended inside the parentheses after a comma.
    """
    if line is None:
        return f"({suffix}) " if suffix else ""
    inner = f"line {line}, {suffix}" if suffix else f"line {line}"
    return f"({inner}) "


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
    or adding a fixed per-line indent.

    This is the list-continuation-indentation bug's exact signature: a ``Requirements:`` fence meant
    to quote exact source text as Edit-tool ``old_string`` bait silently picks up (or loses) a
    uniform per-line indent from the surrounding Markdown list-continuation nesting, so the quoted
    text no longer byte-matches the real source file even though it "looks right" to a human or LLM
    reviewer.
    Drift can go either direction: the fence may carry MORE indent than the source (over-indent, the
    strip case) or LESS indent than the source (under-indent, the add case).

    For each card with a non-empty Edits: field and a Requirements: field containing at least one
    fenced code block: for each fence, if the raw (unstripped) fence content is already a literal
    substring of some resolved Edits: file's content, the fence is clean -- no error.
    Otherwise the strip pass runs first: search ascending strip amounts N = 1..40 (a fixed per-line
    leading-space strip, NOT textwrap.dedent's common-minimum-strip -- see _strip_n_leading_spaces)
    for the first N whose stripped fence content IS a literal substring of some resolved Edits: file
    (walked in the card's own Edits: declaration order, first match wins on ties).
    The strip pass runs before the add pass because a fence cannot legitimately match both
    directions at once, so preserving the incumbent strip-first ordering keeps every
    currently-emitted message byte-for-byte stable.
    Only when the strip pass finds nothing does the add pass run, over the same ascending N = 1..40
    range: for each N, ``_add_n_leading_spaces(fence_body, n)`` (blank lines left unpadded) is tried
    first across every resolved Edits: file in declaration order, and only if that fails is
    ``_add_n_leading_spaces(fence_body, n, include_blank=True)`` (blank lines padded too) tried the
    same way -- the non-blank-then-all-lines ordering matches the common case (editors strip
    trailing whitespace from blank lines) before the less common one.
    Either pass's first match wins and stops the search;
    a fence matching in neither direction at any N in range is an illustrative snippet showing
    new/desired-state code, not a drifted quote, and is silently skipped -- never flagged.
    Exception: when such an unmatched fence immediately follows (in ``fence_bodies`` order -- any
    prose between the two fences in the raw text does not break the pairing) a fence that DID match
    (clean, strip, or add), its own first-non-blank-line indentation is compared against that anchor
    fence's own first-non-blank-line indentation;
    a mismatch is flagged as a new finding (same check name, distinct message).
    This comparison only ever looks at the single immediately-preceding fence -- it does not chain
    across multiple consecutive unmatched fences.

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
        cards = _parse_cards_positioned(text)
        for card_num, card_lines, card_start_line in cards:
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

            fence_open_lines = _requirements_fence_open_lines(card_lines, card_start_line)
            last_matched_indent: int | None = None
            last_matched_token: str | None = None
            for fence_idx, fence_body in enumerate(fence_bodies, start=1):
                fence_body = re.sub(r"\n[ \t]*\Z", "", fence_body)
                fence_line = fence_open_lines[fence_idx - 1] if fence_idx <= len(fence_open_lines) else None
                # Already byte-exact -- nothing to flag.
                # This also correctly no-ops for a fence with zero leading whitespace, since every N >= 1 strip on such a fence is a no-op that reduces to this same already-checked raw content.
                clean_match_token = None
                for t in ordered_resolved_tokens:
                    if fence_body in resolved_contents[t]:
                        clean_match_token = t
                        break
                if clean_match_token is not None:
                    last_matched_indent = _first_nonblank_line_indent(fence_body)
                    last_matched_token = clean_match_token
                    continue

                matched = False
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
                            "line": fence_line,
                            "message": (
                                f"card {card_num}'s Requirements: fence {fence_idx} "
                                f"{_line_locator(fence_line)}"
                                f"matches '{matched_token}' after stripping {n} "
                                f"leading spaces per line (found N={n})"
                            ),
                        })
                        last_matched_indent = _first_nonblank_line_indent(fence_body)
                        last_matched_token = matched_token
                        matched = True
                        break
                if matched:
                    continue

                # The strip pass found nothing: this fence may instead be under-indented relative
                # to its source (the opposite drift direction), so run the symmetric add pass over
                # the same ascending N range.
                add_matched = False
                for n in range(1, 41):
                    matched_token = None
                    for candidate in (
                        _add_n_leading_spaces(fence_body, n),
                        _add_n_leading_spaces(fence_body, n, include_blank=True),
                    ):
                        for token in ordered_resolved_tokens:
                            if candidate in resolved_contents[token]:
                                matched_token = token
                                break
                        if matched_token is not None:
                            break
                    if matched_token is not None:
                        errors.append({
                            "check": "requirements-quote-indent-drift",
                            "batch": batch_path.stem,
                            "card": card_num,
                            "path": matched_token,
                            "line": fence_line,
                            "message": (
                                f"card {card_num}'s Requirements: fence {fence_idx} "
                                f"{_line_locator(fence_line)}"
                                f"matches '{matched_token}' after adding {n} "
                                f"leading spaces per line (found N={n})"
                            ),
                        })
                        last_matched_indent = _first_nonblank_line_indent(fence_body)
                        last_matched_token = matched_token
                        add_matched = True
                        break
                if add_matched:
                    continue

                # Neither the clean check, strip pass, nor add pass matched -- illustrative new/
                # replacement code. Check indentation against the immediately preceding matched
                # anchor fence in fence_bodies order, if any.
                if last_matched_indent is not None:
                    sibling_indent = _first_nonblank_line_indent(fence_body)
                    if sibling_indent is not None and sibling_indent != last_matched_indent:
                        errors.append({
                            "check": "requirements-quote-indent-drift",
                            "batch": batch_path.stem,
                            "card": card_num,
                            "path": last_matched_token,
                            "line": fence_line,
                            "message": (
                                f"card {card_num}'s Requirements: fence {fence_idx} "
                                f"({_line_locator(fence_line, 'new/replacement code')}) "
                                f"immediately follows matched fence {fence_idx - 1}, but its "
                                f"first line is indented {sibling_indent} spaces vs the anchor fence's "
                                f"{last_matched_indent} spaces"
                            ),
                        })
                last_matched_indent = None
                last_matched_token = None

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

def _is_python_project(project_root: Path) -> bool:
    """Return whether `project_root` looks like a Python project (root-level pyproject.toml/setup.py/setup.cfg, OR a nested plugins/mill/pyproject.toml marker for this repo's own dogfood layout)."""
    return (
        (project_root / "pyproject.toml").exists()
        or (project_root / "setup.py").exists()
        or (project_root / "setup.cfg").exists()
        or (project_root / "plugins" / "mill" / "pyproject.toml").exists()
    )


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
    # Python-project detection is a one-time lookup shared across every batch and the overview -- delegated to the shared _is_python_project helper.
    is_python_project = _is_python_project(project_root)

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


def _check_verify_untested_tag_in_touched_package(
    batch_files: list[Path],
    project_root: Path,
    root: str | None,
    *,
    wiki_root: Path | None = None,
    git_root: Path | None = None,
) -> list[dict]:
    """
    Flag an untouched, differently-build-tagged Go test file sitting in a package some batch's
    non-test Edits:/Creates: touched, when no batch's verify: command ever exercises that tag
    against that package.

    Go-specific: gated on `(project_root / "go.mod").exists()`, fail-open for every non-Go project
    -- mirrors `_check_verify_excludes_edited_tagged_test`'s own gate.

    Distinct from `_check_verify_excludes_edited_tagged_test`, which only fires when a batch itself
    edits the tagged test file. This check instead scans every `_test.go` file that already exists on
    disk in a touched package -- including ones no batch's Edits:/Creates: names at all -- since a
    sibling test file guarded by a different build tag can silently rot when its package's non-test
    code changes underneath it.

    Algorithm:
      1. Collect every package directory touched by any batch's non-test Edits:/Creates: tokens (a
         token ending in `_test.go` does not count as "touching" a package here). `Edits:` tokens are
         resolved via `resolve_existing_paths` since they exist on disk;
         `Creates:` tokens are used as literal relative paths without resolution, mirroring
         `_check_verify_excludes_edited_tagged_test`'s own documented `Creates:`-tokens-do-not-exist-
         yet exclusion, except here only a package directory (not file content) is needed, so the
         token's own parent directory stands in for the resolved parent.
      2. For each distinct touched package directory, list every `_test.go` file that exists in it on
         disk (every file in the package, not just batch-Edits:-named ones -- the deliberate
         difference from the sibling check) and collect its custom build tags via
         `_go_file_custom_tags`; files with no custom tags are skipped.
      3. Build, once per plan (not per package), the list of every batch's normalized verify: command
         via `_plan_dag.parse_verify_field` (a malformed `{cwd, command}` mapping raises `ValueError`
         -- caught and skipped since `_check_verify_malformed_cwd` is the sole reporter for that),
         split into shell segments via `_RE_SHELL_OPERATOR`, restricted to segments matching
         `_RE_GO_TEST_INVOCATION`.
      4. A (package, tag) pair is "covered" when at least one recorded segment both carries the tag
         via its `-tags` flag (`_verify_command_has_any_tag`) and targets the package: the segment
         contains the literal substring `"./..."`, `f"./{pkg_rel}"`, or `f"./{parent}/..."` for any
         ancestor directory `parent` of `pkg_rel`. Uncovered pairs are reported, one finding per
         (package, tagged test file).

    Error dict shape: ``{check, batch, card, path, message}``. Every finding uses ``batch=None`` --
    an overview-level property of the plan's verify commands as a set, not any single batch's own
    command -- mirrors `_check_verify_full_suite`'s own `batch=None` convention for its overview-level
    findings.

    Args:
        batch_files: Sorted list of batch file paths to validate.
        project_root: Root of the project (worktree root);
            also the `go.mod` presence-check root.
        root: Optional root subfolder for source refs, threaded to `resolve_existing_paths` exactly
            like the sibling check.
        wiki_root: Optional wiki root path, threaded to `resolve_existing_paths`.
        git_root: Optional repo root, threaded to `resolve_existing_paths`.

    Returns:
        List of error dicts, one per (touched package, untested custom tag) pair.
    """
    if not (project_root / "go.mod").exists():
        return []

    # Step 1: collect every package directory touched by any batch's non-test Edits:/Creates:.
    touched_packages: set[str] = set()
    for batch_path in batch_files:
        edit_tokens = sorted(
            t for t in _parse_edits_only(batch_path) if not t.endswith("_test.go")
        )
        if edit_tokens:
            resolved = resolve_existing_paths(
                edit_tokens, project_root, root, wiki_root=wiki_root, git_root=git_root,
            )
            for path in resolved:
                try:
                    pkg_rel = path.parent.relative_to(project_root).as_posix()
                except ValueError:
                    continue
                touched_packages.add(pkg_rel)
        create_tokens = (
            t for t in _parse_creates_only(batch_path) if not t.endswith("_test.go")
        )
        for token in create_tokens:
            touched_packages.add(Path(token).parent.as_posix())

    if not touched_packages:
        return []

    # Step 2: for each touched package, discover every on-disk _test.go file's custom tags.
    package_tagged_files: dict[str, list[tuple[str, set[str]]]] = {}
    for pkg_rel in touched_packages:
        pkg_dir = project_root / pkg_rel
        if not pkg_dir.is_dir():
            continue
        for test_file in sorted(pkg_dir.glob("*_test.go")):
            tags = _go_file_custom_tags(test_file)
            if tags:
                package_tagged_files.setdefault(pkg_rel, []).append((test_file.name, tags))

    if not package_tagged_files:
        return []

    # Step 3: build, once per plan, the list of every batch's go-test verify segments.
    go_test_segments: list[str] = []
    for batch_path in batch_files:
        try:
            frontmatter = _plan_dag._read_batch_frontmatter(batch_path)
            command, _cwd = _plan_dag.parse_verify_field(
                frontmatter, project_root, project_root,
            )
        except ValueError:
            # _check_verify_malformed_cwd is the sole reporter for this.
            continue
        if command is None:
            continue
        for segment in _RE_SHELL_OPERATOR.split(command):
            if _RE_GO_TEST_INVOCATION.search(segment):
                go_test_segments.append(segment)

    def _segment_targets_package(segment: str, pkg_rel: str) -> bool:
        if "./..." in segment:
            return True
        if f"./{pkg_rel}" in segment:
            return True
        parent = str(Path(pkg_rel).parent.as_posix())
        while parent and parent != ".":
            if f"./{parent}/..." in segment:
                return True
            parent = str(Path(parent).parent.as_posix())
        return False

    # Step 4: report every (package, tag) pair no recorded segment covers.
    errors: list[dict] = []
    for pkg_rel in sorted(package_tagged_files):
        for file_name, tags in package_tagged_files[pkg_rel]:
            covered = any(
                _verify_command_has_any_tag(segment, tags)
                and _segment_targets_package(segment, pkg_rel)
                for segment in go_test_segments
            )
            if not covered:
                tag = sorted(tags)[0]
                errors.append({
                    "check": "verify-untested-tag-in-touched-package",
                    "batch": None,
                    "card": None,
                    "path": f"{pkg_rel}/{file_name}",
                    "message": (
                        f"package '{pkg_rel}' is touched by a batch's Edits:/Creates: but its "
                        f"custom-tagged test file '{file_name}' (tag '{tag}') is never exercised "
                        f"by any batch's verify: command"
                    ),
                })

    return errors


# ---------------------------------------------------------------------------
# verify-full-suite check
# ---------------------------------------------------------------------------

# Splits a verify: command on shell-operator boundaries so each invocation in a compound
# command is scoped independently (fixes #961: a later segment's ./... wrongly attributed
# to an earlier go test invocation).
_RE_SHELL_OPERATOR = re.compile(r"&&|\|\||;")

# Matches a `go test` invocation, allowing the Go 1.20+ `-C <dir>` flag (which must precede
# the subcommand) between `go` and `test` (fixes #933: `go -C <dir> test ./...` was never
# matched by the old literal `\bgo test\b` pattern). Deliberately narrow -- a generic
# "any flags between go and test" pattern would misfire on unrelated commands like
# `go get test/pkg`.
_RE_GO_TEST_INVOCATION = re.compile(r"\bgo\s+(?:-C\s+\S+\s+)?test\b")

# Matches a `dotnet test` invocation anywhere in a segment.
_RE_DOTNET_TEST_INVOCATION = re.compile(r"\bdotnet\s+test\b")

# `dotnet test` options that consume the following token as their value (as opposed to a bare
# flag). Used by `_dotnet_test_segment_is_unscoped` to skip the value token when walking for the
# first positional (non-flag) argument, so a value like `Release` in `-c Release` is never
# mistaken for a project/solution target.
_DOTNET_TEST_VALUE_OPTIONS = frozenset({
    "-c", "--configuration",
    "-f", "--framework",
    "-r", "--runtime",
    "-o", "--output",
    "-s", "--settings",
    "-l", "--logger",
    "-v", "--verbosity",
    "-a", "--test-adapter-path",
    "-d", "--diag",
    "-e", "--environment",
    "--results-directory",
    "--arch",
    "--os",
})

# Solution-file suffixes: a `dotnet test` positional target ending in one of these (case-insensitive)
# names a whole solution rather than a single project, so it is still an unscoped full-suite run.
_DOTNET_SOLUTION_SUFFIXES = (".sln", ".slnx", ".slnf")


def _dotnet_test_segment_is_unscoped(segment: str) -> bool:
    """
    Return True when a shell segment's `dotnet test` invocation is an unscoped full-suite run.

    A segment with no `dotnet test` invocation, or one that already carries `--filter`, is
    considered scoped (returns False) without further inspection.
    Otherwise the text after the `dotnet test` match is tokenised with `shlex.split` (falling back
    to `str.split` if the text has unbalanced quoting), and the tokens are walked to find the first
    positional (non-flag) argument: any token starting with `-` is a flag and is skipped, and when
    that flag is one of `_DOTNET_TEST_VALUE_OPTIONS` and does not carry an inline `=`/`:` value, the
    following token (its value) is skipped too.

    Returns:
        True when there is no positional target at all, or the target's lowercased form ends with
        one of `_DOTNET_SOLUTION_SUFFIXES` (a whole-solution target) -- both cases still run the
        full suite. False when a project/directory/DLL target narrows the run.
    """
    m = _RE_DOTNET_TEST_INVOCATION.search(segment)
    if not m or "--filter" in segment:
        return False

    rest = segment[m.end():]
    try:
        tokens = shlex.split(rest)
    except ValueError:
        tokens = rest.split()

    target: str | None = None
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("-"):
            option = token.split("=", 1)[0].split(":", 1)[0]
            if option in _DOTNET_TEST_VALUE_OPTIONS and "=" not in token and ":" not in token:
                i += 1  # Skip the option's separate value token too.
        else:
            target = token
            break
        i += 1

    if target is None:
        return True
    return target.lower().endswith(_DOTNET_SOLUTION_SUFFIXES)


def _check_verify_full_suite(
    batch_files: list[Path],
    project_root: Path,
    overview_path: Path,
    *,
    done_gate: str | None = None,
) -> list[dict]:
    """
    Flag verify: commands that invoke an unscoped full-suite runner: run-all.py without
    -k/--only (Python/mill), go test ./... without -run (Go), dotnet test with no project
    target or a solution target and no --filter (C#), or bare pytest/python -m pytest with
    no path or -k filter (Python, non-mill).
    A verify command that exactly equals `done_gate` (when supplied) is exempt from every
    sub-check below.

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
        done_gate: The hub's configured repo-wide gate command (pipeline.done_gate), or None.
            When a frontmatter's verify command exactly equals this string, no verify-full-suite
            finding is reported for it, regardless of which sub-check would otherwise match.

    Returns:
        List of error dicts, one per unscoped full-suite invocation.
    """
    # Python-project detection is a one-time lookup shared across every batch and the overview -- mirrors _check_verify_not_isolated's own one-time-lookup pattern.
    is_python_project = _is_python_project(project_root)

    def _check_frontmatter(frontmatter: dict, batch_label: str | None) -> dict | None:
        try:
            command, _cwd = _plan_dag.parse_verify_field(frontmatter, project_root, project_root)
        except ValueError:
            # _check_verify_malformed_cwd is the sole reporter for this.
            return None
        if command is None:
            return None
        if done_gate is not None and command == done_gate:
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
        for segment in _RE_SHELL_OPERATOR.split(command):
            if (
                _RE_GO_TEST_INVOCATION.search(segment)
                and "./..." in segment
                and "-run " not in segment
            ):
                return {
                    "check": "verify-full-suite",
                    "batch": batch_label,
                    "card": None,
                    "path": command,
                    "message": (
                        "verify command invokes 'go test ./...' without a -run <pattern> filter; "
                        "scope it or document the cross-cutting-helper justification in ## Batch Tests"
                    ),
                }
        for segment in _RE_SHELL_OPERATOR.split(command):
            if _dotnet_test_segment_is_unscoped(segment):
                return {
                    "check": "verify-full-suite",
                    "batch": batch_label,
                    "card": None,
                    "path": command,
                    "message": (
                        "verify command invokes 'dotnet test' with no project target (or on a "
                        "whole solution) and no --filter; name a test project, add --filter, or "
                        "document the cross-cutting-helper justification in ## Batch Tests"
                    ),
                }
        if is_python_project and re.fullmatch(r"(python -m )?pytest", command.strip()):
            return {
                "check": "verify-full-suite",
                "batch": batch_label,
                "card": None,
                "path": command,
                "message": (
                    "verify command invokes bare pytest with no path or -k filter; "
                    "scope it or document the cross-cutting-helper justification in ## Batch Tests"
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

    A ``--only`` token naming the convention-derived test file for one of the batch's own touched
    source files is exempt exactly like a directly-touched test file: Python ``test-<stem>.py`` for
    ``<stem>.py`` (stripping any leading underscore and converting remaining underscores to hyphens),
    or Go ``<stem>_test.go`` for ``<stem>.go``.

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
        derived_test_basenames: set[str] = set()
        for t in touched:
            basename = Path(t).name
            if basename.endswith(".py") and not basename.startswith("test-"):
                stem = Path(t).stem.lstrip("_").replace("_", "-")
                derived_test_basenames.add(f"test-{stem}.py")
            elif basename.endswith(".go") and not basename.endswith("_test.go"):
                derived_test_basenames.add(f"{Path(t).stem}_test.go")

        for token in candidates:
            if Path(token).name in touched_basenames:
                continue
            if Path(token).name in derived_test_basenames:
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
# Check 1 (card count) stays batch-level; Check 2 (context-size token estimate) is evaluated
# per card, not per batch -- see _check_batch_oversized's Check 2 loop below.
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

        # Check 2: context size (token estimate), evaluated per card.
        # Collect Context/Edits/Creates/Deletes/Moves tokens from each card individually, so one
        # oversized card in an otherwise-small batch is caught without the whole-batch aggregate
        # masking (or over-penalizing) the other cards.
        for card_num, card_lines in cards:
            card_text = "\n".join(card_lines)
            context = set(_card_context_tokens(card_text))
            edits = set(_card_edits_tokens(card_text))
            creates = set(_card_creates_tokens(card_text))
            deletes = set(_card_deletes_tokens(card_text))
            moves = _card_moves_tokens(card_text)
            move_sources = {src for src, _ in moves}
            move_targets = {dst for _, dst in moves}

            # Subtract deleted and move-target tokens, then add move sources.
            card_tokens = ((context | edits | creates) - deletes - move_targets) | move_sources

            # Resolve existing paths, skipping those that don't exist (like Creates targets)
            if not card_tokens:
                continue
            resolved = resolve_existing_paths(
                list(card_tokens),
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
                    "card": card_num,
                    "path": None,
                    "message": (
                        f"card {card_num} context ~{token_estimate} tokens (cap {max_context_tokens})"
                    ),
                })

    return errors


# ---------------------------------------------------------------------------
# cross-batch-build-break check (#1056)
# ---------------------------------------------------------------------------

_RE_RENAME_TO = re.compile(r"rename\s+`([^`]+)`\s+to\s+`([^`]+)`", re.IGNORECASE)
_RE_REMOVE_SYMBOL = re.compile(r"\bremove\s+`([^`]+)`", re.IGNORECASE)
_RE_DELETE_SYMBOL = re.compile(r"\bdelete\s+`([^`]+)`", re.IGNORECASE)
_CROSS_BATCH_BUILD_BREAK_PATTERNS = (_RE_RENAME_TO, _RE_REMOVE_SYMBOL, _RE_DELETE_SYMBOL)


def _cross_batch_build_break_looks_like_file(token: str) -> bool:
    """Return True when `token` is shaped like a file path rather than a code symbol.

    A matched token ending in one of the shared ``_PATH_CANDIDATE_EXTENSIONS``, or containing "/",
    is a file-removal reference (e.g. "Remove `plugins/mill/scripts/foo.py`", the standard prose
    for a file deletion in this repo's plans), never a code symbol, and must be excluded from the
    rename/removal candidate set (#1056 plan-review round 2 finding). Reuses the same extension
    list as context-completeness's path-vs-symbol classification instead of maintaining a second,
    independently-drifting tuple.
    """
    if "/" in token:
        return True
    lowered = token.lower()
    return any(lowered.endswith(ext) for ext in _PATH_CANDIDATE_EXTENSIONS)


def _check_cross_batch_build_break(
    batch_files: list[Path],
    overview_path: Path,
    overview_text: str,
) -> list[dict]:
    """
    Flag a batch whose Requirements: rename/remove a symbol while a later-or-unordered batch's own
    Requirements: still reference the old symbol name, when the plan's own module-wide `verify:`
    is a whole-module build/compile/vet/smoke command (see #1056).

    Gated on the overview's existing top-level frontmatter `verify:` field (already documented in
    `plugins/mill/templates/plan-overview.md`) being non-null. A plan with `verify: null` has no
    whole-module build-breakage question to ask, so the check is a no-op for it -- no new
    frontmatter field is introduced.

    This is a plan-text-only check: at plan-review time none of the batches have been implemented
    yet, so the actual source tree never reflects any of the plan's renames -- there is nothing
    useful to grep in real source files. Instead, this check scans every OTHER batch's own
    Requirements: text for the literal old-symbol token the renaming batch's Requirements: names.

    A matched token that looks file-path-shaped (contains "/" or ends in a common source/doc/
    config file extension, per `_cross_batch_build_break_looks_like_file`) is never treated as a
    symbol candidate -- "Remove `plugins/mill/scripts/foo.py`" is an ordinary file-deletion
    instruction, not a renamed/removed code symbol.

    A card that mentions the old symbol is exempt when it performs its own rename/removal of that
    same symbol (i.e. its own Requirements: text also matches one of the three patterns with that
    symbol as the matched group) -- that is a further rename in the same chain, not a stale
    reference. A batch that the renaming batch is a transitive ancestor of (via
    `_compute_transitive_ancestors` -- i.e. a batch that depends on the renaming batch, directly
    or transitively) is exempt: the depends-on edge already guarantees it runs after the rename
    lands.

    Error dict shape: ``{check, batch, card, path, message}`` -- `path` carries the stale symbol
    token, `card` the referencing card's number, `batch` the referencing batch's name.

    Args:
        batch_files: Sorted list of batch file paths to validate.
        overview_path: Path to the plan's ``00-overview.md``, whose top-level `verify:` field
            gates this check.
        overview_text: Full text of ``00-overview.md`` (source of the Batch Index DAG).

    Returns:
        List of error dicts, one per stale cross-batch symbol reference found.
    """
    if not overview_path.exists():
        return []
    if _plan_dag._read_batch_frontmatter(overview_path).get("verify") is None:
        return []

    try:
        batches = extract_batch_index(overview_text)
    except PlanDAGError:
        # Check 4 has already recorded the parse error; don't double-report.
        return []

    ancestors = _compute_transitive_ancestors(batches)
    stem_to_path: dict[str, Path] = {bf.stem: bf for bf in batch_files}
    batch_name_to_path: dict[str, Path] = {}
    for entry in batches:
        stem = Path(entry.get("file", "")).stem
        if stem in stem_to_path:
            batch_name_to_path[entry["name"]] = stem_to_path[stem]

    def _renamed_symbols(requirements_text: str) -> set[str]:
        symbols: set[str] = set()
        for pattern in _CROSS_BATCH_BUILD_BREAK_PATTERNS:
            for m in pattern.finditer(requirements_text):
                if _cross_batch_build_break_looks_like_file(m.group(1)):
                    continue
                symbols.add(m.group(1))
        return symbols

    # Collect (renaming_batch_name, old_symbol) pairs from every card's Requirements:.
    renames: list[tuple[str, str]] = []
    for name, path in batch_name_to_path.items():
        text = path.read_text(encoding="utf-8")
        for _card_num, card_lines in _parse_cards(text):
            requirements = _extract_requirements_text("\n".join(card_lines)) or ""
            for old_symbol in _renamed_symbols(requirements):
                renames.append((name, old_symbol))

    errors: list[dict] = []
    for renaming_batch, old_symbol in renames:
        for other_name, other_path in batch_name_to_path.items():
            if other_name == renaming_batch:
                continue
            if renaming_batch in ancestors.get(other_name, set()):
                # renaming_batch is an ancestor of other_name -- other_name is guaranteed to run
                # after the rename lands (the depends-on edge already covers it) -- not at risk.
                continue
            text = other_path.read_text(encoding="utf-8")
            for card_num, card_lines in _parse_cards(text):
                requirements = _extract_requirements_text("\n".join(card_lines)) or ""
                if old_symbol not in requirements:
                    continue
                if old_symbol in _renamed_symbols(requirements):
                    continue
                errors.append({
                    "check": "cross-batch-build-break",
                    "batch": other_name,
                    "card": card_num,
                    "path": old_symbol,
                    "message": (
                        f"batch '{other_name}' card {card_num} Requirements: still reference "
                        f"'{old_symbol}', renamed/removed by batch '{renaming_batch}', with no "
                        f"depends-on edge ordering this batch after it"
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
    done_gate: str | None = None,
) -> list[dict]:
    """Validate plan files in plan_dir.

    Returns a sorted list of error dicts with keys: {check, batch, card, path, message}.

    Checks 1, 2, 3, 4, 5, 6, 8 from issue #10, plus wiki-config-mutation,
    plugin-manifest-context-missing, verify-not-isolated, verify-full-suite, verify-malformed-cwd,
    verify-mixed-cwd, verify-unrelated-test-file, out-of-worktree-target, batch-oversized,
    commit-none-with-content, and five Move-specific checks (move-format, move-redundant,
    move-source-missing, move-target-collision, move-mechanic-missing),
    cross-batch-creates-no-depends-on, and verify-batch-mismatch, and cross-batch-build-break.

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
        max_cards_per_batch: Maximum cards per batch before batch-oversized is raised
            (card count itself stays batch-level).
        max_batch_context_tokens: Maximum context token estimate before batch-oversized is raised,
            applied per card -- each card's own Context/Edits/Creates/Deletes/Moves token estimate
            is checked against this cap individually, not the batch's aggregate.
        parent_branch: The task's resolved parent branch name, threaded to
            verify-unrelated-test-file. ``None`` (the default) makes that check a no-op -- callers
            that cannot resolve a parent branch (e.g.
            the standalone millpy-validate-plan.py CLI) simply skip it.
        done_gate: The hub's configured pipeline.done_gate command, or None. Threaded to
            _check_verify_full_suite (see that function's own done_gate documentation).
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
    # Threaded into context-completeness's forward cross-card Creates exemption: built from the same
    # sorted batch_files list every other check sees, so a token's composite (batch_index,
    # card_number) key agrees across checks.
    creates_declaring_card_map = _build_creates_declaring_card_map(batch_files)
    # Move sources behave like Deletes (disappear) and targets like Creates (appear).
    # Computed once here and threaded into the checks that need them.
    moves_sources, moves_targets = compute_moves_union(plan_dir)
    declared_symbols = _compute_declared_symbols_union(plan_dir)
    # The symbol branch's search space (resolution-scope-rework Decision): only files already cited
    # somewhere in the plan, never a repo-wide fallback.
    cited_files_map = _compute_plan_wide_cited_files(
        batch_files, project_root, effective_root,
        wiki_root=wiki_root,
        git_root=git_root,
    )
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
    errors.extend(_check_verify_batch_mismatch(batch_files, overview_text, project_root))
    errors.extend(_check_parallel_modifies_overlap(batch_files, overview_text))
    errors.extend(_check_cross_batch_creates_no_depends_on(batch_files, overview_text))
    errors.extend(_check_cross_batch_build_break(batch_files, overview_path, overview_text))
    errors.extend(_check_ref_not_backtick_path(batch_files))
    errors.extend(_check_verify_not_isolated(batch_files, project_root, overview_path))
    errors.extend(_check_verify_full_suite(batch_files, project_root, overview_path, done_gate=done_gate))
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
    errors.extend(_check_verify_untested_tag_in_touched_package(
        batch_files, project_root, effective_root,
        wiki_root=wiki_root,
        git_root=git_root,
    ))
    errors.extend(_check_wiki_config_mutation(batch_files))
    errors.extend(_check_plugin_manifest_context_missing(batch_files))
    errors.extend(_check_context_completeness(
        batch_files, project_root, effective_root, creates_union, deletes_union,
        moves_sources, moves_targets,
        wiki_root=wiki_root,
        git_root=git_root,
        creates_declaring_card_map=creates_declaring_card_map,
        declared_symbols=declared_symbols,
        cited_files_map=cited_files_map,
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
        batch_files, project_root, effective_root, moves_sources,
        wiki_root=wiki_root,
        git_root=git_root,
    ))
    errors.extend(_check_move_mechanic_missing(batch_files))

    errors.sort(key=lambda e: (e["batch"] or "", e["card"] or 0, e["check"]))
    if skip_checks:
        errors = [e for e in errors if e["check"] not in skip_checks]
    return errors
