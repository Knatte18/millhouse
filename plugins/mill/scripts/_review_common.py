"""
Shared helpers, regex constants, data classes, and exceptions used by every Layer 02 review backend.

No dependencies on any other Layer 02 file.
Import this from _review_discussion.py, _review_plan.py, _review_code.py, and the API scripts.

Public API:
    ReviewError — raised by the backend on config/slug/round errors
    ReviewerOverstepError — raised by worktree_snapshot_guard when a reviewer mutates HEAD or
    working tree
    ReviewResult — dataclass; serialised to the CLI's stdout JSON
    RE_SIMPLE — regex matching simple review filenames
    RE_BATCH — regex matching plan-batch review filenames
    find_active_slug() — branch-based slug detection;
    skips the daemon when a _mill/*.active marker confirms the current branch, else falls back to
    the marker only if the daemon call fails
    load_task_title() — read status.md on disk first;
    fall back to _marker.task_data for task_title, then to slug on MarkerError
    worktree_snapshot_guard() — context manager; snapshot guard wrapping each backend run()
    read_constraints_md()— read CONSTRAINTS.md, empty string if absent
    resolve_path() — locate a path inside the active hub (where task/ lives) from a config template
    discover_round()     — determine next review round number per (review_type, scope)
    detect_resume_round() — return highest per-batch-only round (no holistic yet), or None
    bulk_files() — concatenate file contents with FILE delimiters
    bulk_files_with_diff() — like bulk_files but substitutes git diff output for small-diff files
    build_manifest_section() — return a `## Files included` markdown block listing every bulked file
    build_deletes_section() — return a `## Intentionally deleted` markdown block listing deleted
    tokens
    parse_missing_context() — extract path strings from a `## Missing context` section in review
    text
    build_reattached_section() — return a `## Re-attached files` block with inlined file contents
    for NEED_CONTEXT retry
    build_tool_rule()    — dispatch-aware <TOOL_RULE> block (bulk / tool-use x non-agent / agent-mode)
    render_prompt() — render a template from plugins/mill/templates/
    parse_verdict() — extract APPROVE/REQUEST_CHANGES from fenced yaml block; GAPS_FOUND is
    accepted on read (historical) and normalised to REQUEST_CHANGES
    parse_blocking_count() — count "### [<severity>]" (optionally classed) headings in review
    output; historical re-read sites only -- extract_findings() covers the new-review path
    count_unrecognized_severity_findings() — count findings whose severity matches neither of the
    two recognized labels, scanning both headings and YAML fallback
    Finding — dataclass; severity, class (cls), title, demoted
    extract_findings() — single pass over a review's raw text producing every Finding exactly
    once, scanning both the heading and fenced-YAML mechanisms
    apply_blocking_ceiling() — demote BLOCKING findings whose class is outside blocking_classes to
    NIT, in place; never promotes and never touches a cls-None finding
    rewrite_demoted_findings() — rewrite every on-disk representation (heading and yaml) of each
    demoted finding so the file agrees with the envelope
    resolve_blocking_classes() — read roles.<role>.<scope>.blocking_classes from config, falling
    back to the documented per-stage default
    write_review_file() — write a review file with a canonical timestamp name
    aggregate_verdict() — worst-case verdict across a list of sub-verdicts
    load_config() — load mill-config.yaml + optional config.local.yaml
    parse_batch_refs()   — extract Context/Edits/Creates paths from a batch file (case-insensitive none filter)
    parse_moves()        — extract Moves: source/destination pairs from a batch file (tolerates malformed bullets)
    compute_creates_union() — union of all Creates: tokens across every batch in a plan_dir
    compute_deletes_union() — union of all Deletes: tokens across every batch in a plan_dir
    compute_moves_union() — union of all Moves: sources and targets across every batch in a plan_dir
    resolve_ref_paths() — resolve raw ref strings against project_root;
    hard-fails on missing paths not in creates_union or deletes_union
    resolve_existing_paths() — resolve raw paths and return only those that already exist on disk (silent drop, no creates_union check)
    _load_root_from_overview() — read root: field from overview's fenced-yaml block
    _check_large_prompt()    — check if prompt exceeds large_prompt threshold; return (is_over_threshold, estimated_ktok)
    resolve_large_prompt_timeout() — return large_prompt.timeout when prompt is over threshold and
    key is set
    maybe_switch_spec_for_large_prompt() — check prompt size;
    return (spec, reviewer_name), possibly overridden for large prompts
"""

from __future__ import annotations

import json
import re
import _subprocess_util
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml
import _marker
import _paths
import _pygit2_util
import _render
import _reviewers
import _status
from _config import (
    load_config as _core_load_config,
    resolve_plugin_template_path,
    resolve_repo_config_path,
)

# ---------------------------------------------------------------------------
# Module-level regex constants
# ---------------------------------------------------------------------------

# Matches simple (non-batch) review filenames: 20260418-001200-discussion-review-r1.md 20260418-143300-code-review-r2.md 20260418-143300-plan-review-r1.md (plan holistic)
RE_SIMPLE = re.compile(
    r"^\d{8}-\d{6}-(?P<type>discussion|code|plan)-review-r(?P<n>\d+)\.md$"
)

# Matches plan / code per-batch review filenames: 20260418-143300-plan-review-01-setup-r1.md 20260418-143300-code-review-foundation-r1.md RE_SIMPLE is checked first;
# a file matching RE_SIMPLE is excluded from RE_BATCH matching (prevents holistic files from being mis-identified).
RE_BATCH = re.compile(
    r"^\d{8}-\d{6}-(?P<type>plan|code)-review-(?P<batch>[a-z0-9-]+)-r(?P<n>\d+)\.md$"
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ReviewError(Exception):
    """Raised by the backend on config / slug / reviewer / round errors.

    Caught by the API scripts, which print str(exc) to stderr and exit 1.
    """


class ReviewerOverstepError(ReviewError):
    """Raised when a reviewer mutated git state (HEAD or working tree) during a review pass.

    Carries the before/after HEAD SHA and the unfiltered git status --porcelain diff for operator
    inspection.
    The guard does not auto-rollback;
    the operator resets manually after investigating.
    """

    def __init__(self, before_sha: str, after_sha: str, porcelain_diff: str) -> None:
        self.before_sha = before_sha
        self.after_sha = after_sha
        self.porcelain_diff = porcelain_diff
        msg = (
            f"reviewer overstep detected: HEAD {before_sha[:8]} -> {after_sha[:8]}; "
            f"porcelain diff:\n{porcelain_diff}"
        )
        super().__init__(msg)


@contextmanager
def worktree_snapshot_guard(
    project_root: Path,
    *,
    expected_paths: list[str] | None = None,
) -> Iterator[None]:
    """Snapshot git state before/after the with-block;
raise on unsanctioned changes.

    Captures ``git rev-parse HEAD`` and ``git status --porcelain`` on entry, re-captures on exit,
    and raises ``ReviewerOverstepError`` if the reviewer made unsanctioned mutations to HEAD or the
    working tree.

    ``expected_paths`` is a list of substring patterns that filter the porcelain diff before
    comparison.
    A porcelain line is filtered when its path field (with backslashes normalised to forward
    slashes) contains ANY entry in ``expected_paths`` as a substring.

    Fast-forward tolerance: a HEAD advance is permitted when ``after_sha`` is a strict descendant of
    ``before_sha`` (i.e.
    the reviewer committed its own output files in a forward direction).
    In that case the guard emits a one-line warning to stderr containing the token ``fast-forward``
    and both short SHAs, then skips the ``ReviewerOverstepError`` raise -- provided no NEW
    working-tree dirt appeared (entries in ``added`` after porcelain filtering).
    A non-fast-forward HEAD change (orphan branch, reset to unrelated commit, etc.) still raises
    unconditionally.
    If the ancestry check itself raises ``GitOpsError``, the fast-forward flag is set to ``False``
    so the non-verifiable advance is treated conservatively as an overstep.

    Raise rules (``ff`` = fast-forward detected):
    - ``bool(added)`` -- new dirt appeared;
        always raises.
    - ``head_changed and not ff`` -- non-fast-forward HEAD change;
        raises.
    - ``bool(removed) and not ff``-- working-tree entries disappeared without a fast-forward commit
        to account for them;
        raises.

    If the wrapped block raises AND state was mutated, ``ReviewerOverstepError`` takes priority and
    chains the inner exception via ``__cause__``;
    if state was unchanged the inner exception is re-raised unchanged.

    If the post-snapshot capture itself raises (e.g. ``_capture_head_sha`` propagating a
    ``ReviewError`` from a broken git invocation), that error propagates and the inner exception is
    NOT chained -- the capture failure indicates the snapshot is untrustworthy, so the typed
    ``ReviewerOverstepError`` cannot be raised safely.
    This is an intentional trade-off;
    the inner exception, if any, is visible in the traceback frames above the capture call.
    """
    before_sha = _capture_head_sha(project_root)
    before_porcelain = _capture_porcelain(project_root)
    inner_exc: Exception | None = None
    try:
        yield
    except Exception as exc:
        inner_exc = exc
    after_sha = _capture_head_sha(project_root)
    after_porcelain = _capture_porcelain(project_root)
    before_filtered = _filter_porcelain(before_porcelain, expected_paths)
    after_filtered = _filter_porcelain(after_porcelain, expected_paths)

    added = set(after_filtered) - set(before_filtered)
    removed = set(before_filtered) - set(after_filtered)
    head_changed = before_sha != after_sha

    # Determine whether the HEAD advance is a clean fast-forward (after_sha is a descendant of before_sha).
    # If the ancestry helper raises GitOpsError the relationship cannot be verified, so treat it conservatively as non-fast-forward.
    ff = False
    if head_changed:
        try:
            ff = _pygit2_util.is_ancestor(project_root, before_sha, after_sha)
        except _pygit2_util.GitOpsError:
            ff = False

    # Emit a warning when a fast-forward is accepted so operators can inspect logs.
    if ff:
        print(
            f"[worktree_snapshot_guard] fast-forward: HEAD {before_sha[:8]} -> {after_sha[:8]}",
            file=sys.stderr,
        )

    should_raise = (
        bool(added) or (head_changed and not ff) or (bool(removed) and not ff)
    )

    if should_raise:
        diff = _porcelain_diff(before_filtered, after_filtered)
        raise ReviewerOverstepError(before_sha, after_sha, diff) from inner_exc

    if inner_exc is not None:
        raise inner_exc


def _capture_head_sha(project_root: Path) -> str:
    """Return the current HEAD SHA as a hex string. Raises ReviewError on git failure."""
    try:
        return _pygit2_util.head_sha(project_root)
    except _pygit2_util.GitOpsError as e:
        raise ReviewError(
            f"worktree_snapshot_guard: HEAD SHA read failed in {project_root}: {e}"
        ) from e


def _capture_porcelain(project_root: Path) -> list[str]:
    """Return git status --porcelain as a list of lines (one per entry). Raises ReviewError on failure."""
    try:
        return _pygit2_util.status_porcelain(project_root, include_untracked=True)
    except _pygit2_util.GitOpsError as e:
        raise ReviewError(
            f"worktree_snapshot_guard: status read failed in {project_root}: {e}"
        ) from e


def _filter_porcelain(lines: list[str], expected_paths: list[str] | None) -> list[str]:
    """Drop porcelain lines whose path field matches any expected_paths substring.

    Each porcelain line has a 2-character status code, a space, then the path.
    Renames have ' -> ' between old and new path;
    both are checked against expected_paths.
    Path comparison normalises backslashes to forward slashes.
    """
    if not expected_paths:
        return list(lines)
    kept: list[str] = []
    for line in lines:
        # Porcelain format: "XY path" or "XY old -> new" for renames
        path_field = line[3:] if len(line) > 3 else line
        normalised = path_field.replace("\\", "/")
        # Split rename arrows so both sides are checked
        candidates = [s.strip() for s in normalised.split(" -> ")]
        if any(pat in cand for cand in candidates for pat in expected_paths):
            continue
        kept.append(line)
    return kept


def _porcelain_diff(before: list[str], after: list[str]) -> str:
    """Return a human-readable diff string of before vs after porcelain line sets."""
    before_set = set(before)
    after_set = set(after)
    added = sorted(after_set - before_set)
    removed = sorted(before_set - after_set)
    parts: list[str] = []
    for line in added:
        parts.append(f"  + {line}")
    for line in removed:
        parts.append(f"  - {line}")
    return "\n".join(parts) if parts else "  (no porcelain line diff; HEAD changed)"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

# Unified severity vocabulary (all three review types: discussion, plan, code).
# GAP/NOTE/GAPS_FOUND are historical v1 discussion-review-only values; parse_verdict()
# still accepts GAPS_FOUND on read for archive readability, but nothing emits it again.
BLOCKING_SEVERITY = "BLOCKING"
NIT_SEVERITY = "NIT"

# The four class names a finding's heading bracket may carry, e.g. "### [BLOCKING:design] ...".
# Meaning is identical across all three review types (see class-definitions-generic-across-stages):
#   design       -- a decision is missing, wrong, or rests on a false premise.
#   scope        -- the work inventory is incomplete, or the enumeration method is unreliable.
#   decision     -- a named artifact with no stated disposition.
#   consistency  -- the artefact contradicts itself, carries a superseded statement, or violates an
#       established repo convention.
RECOGNIZED_CLASSES = ("design", "scope", "decision", "consistency")


@dataclass
class Finding:
    """A single severity+class finding extracted from a reviewer's raw output.

    ``cls`` is ``None`` when the finding's heading carried no class suffix or an unrecognised one
    (e.g. ``### [BLOCKING]`` or ``### [BLOCKING:perf]``) -- such a finding is exempt from the
    ``blocking_classes`` ceiling in ``apply_blocking_ceiling``, per the
    unknown-class-preserves-stated-severity Shared Decision.
    ``demoted`` is ``True`` once ``apply_blocking_ceiling`` has downgraded this finding from
    ``BLOCKING`` to ``NIT``, or when ``extract_findings`` reads it back from a review file that
    already carries the demotion marker written by ``rewrite_demoted_findings``.

    This dataclass carries no field naming which of the two mechanisms (markdown heading or fenced
    ``findings:`` YAML) the finding came from -- ``rewrite_demoted_findings`` keys its rewrite on
    ``title`` (and ``cls``) and updates every representation, so an origin tag would be both unused
    and wrong for a title that appears in both mechanisms.
    """

    severity: str
    cls: str | None
    title: str
    demoted: bool = False

    def to_dict(self) -> dict[str, Any]:
        # Serialised key is "class" (Python attribute is "cls" because "class" is reserved).
        return {
            "severity": self.severity,
            "class": self.cls,
            "title": self.title,
            "demoted": self.demoted,
        }


@dataclass
class ReviewResult:
    """Serialisable result returned by every review backend's run() function.

    ``blocking_count`` and ``nit_count`` are derived values kept consistent with ``findings`` -- they
    count, respectively, the ``BLOCKING`` and ``NIT`` entries in ``findings``.
    ``findings`` aggregates across sub-reviews by concatenation, exactly as ``blocking_count`` and
    ``nit_count`` already aggregate by summation.
    """

    type: str  # "discussion" | "plan" | "code"
    round: int
    verdict: str  # "APPROVE" | "REQUEST_CHANGES"
    reviews: list[dict] = field(default_factory=list)
    blocking_count: int = 0
    nit_count: int = 0
    findings: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "round": self.round,
            "verdict": self.verdict,
            "blocking_count": self.blocking_count,
            "nit_count": self.nit_count,
            "findings": self.findings,
            "reviews": self.reviews,
        }


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def find_active_slug(hub_root: Path, wiki_path: Path, cfg: dict) -> str:
    """Detect active slug via branch name;
    skip the daemon round-trip only when a cheap branch check confirms a single _mill/*.active
        on-disk marker.
    On daemon failure, an unconfirmed lone marker is still trusted, exactly as before this fast path
        existed.

    Raises ReviewError (wrapping MarkerError or glob-fallback errors).
    """
    try:
        matches = list((hub_root / "_mill").glob("*.active"))
    except OSError:
        matches = []
    if len(matches) == 1:
        try:
            branch = _pygit2_util.current_branch(hub_root) or ""
        except _pygit2_util.GitOpsError:
            branch = ""
        branch_slug = _pygit2_util.strip_branch_prefix(branch, cfg)
        if branch_slug == matches[0].stem:
            return matches[0].stem
    try:
        return _marker.slug_from_branch(hub_root, wiki_path, cfg)
    except _marker.MarkerError as exc:
        if len(matches) == 1:
            return matches[0].stem
        if len(matches) > 1:
            slugs = sorted(m.stem for m in matches)
            raise ReviewError(
                f"{len(slugs)} tasks active ({', '.join(slugs)}); use --slug <slug>"
            ) from exc
        raise ReviewError(
            f"no active task detected; run mill-spawn or mill-claim to start a task"
            f" (branch detection: {exc})"
        ) from exc


def load_task_title(git_root: Path, wiki_path: Path, cfg: dict, slug: str) -> str:
    """Read task_title from status.md on disk;
fall back to the wiki daemon.

    The first parameter is named git_root for historical reasons,
    but every call site passes the hub-resolved project_root -- status.md is read relative to
    whichever value is actually passed in.
    """
    try:
        status_path = _paths.require_status_path(git_root, cfg)
        full = _status.read_full(status_path)
        title = full["yaml"].get("task")
        if title:
            return title
    except (_paths.TaskHubError, ValueError, KeyError):
        pass
    try:
        data = _marker.task_data(git_root, wiki_path, cfg)
    except _marker.MarkerError:
        return slug
    return data.get("task_title") or slug


def read_constraints_md(project_root: Path) -> str:
    """Read CONSTRAINTS.md from the project root.

    Returns empty string if the file is absent.
    """
    constraints_path = project_root / "CONSTRAINTS.md"
    try:
        return constraints_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def resolve_path(path_tmpl: str, slug: str) -> Path:
    """Resolve a config path template to an absolute path inside the active hub.

    Computes the container, git_root, and cfg internally:
      - git_root via _paths.resolve_git_root()
      - container via _paths.resolve_container_path(git_root)
      - hub_dir via _paths.resolve_hub_path() (Path.cwd().resolve() — the hub where mill scripts
      run; equals git_root for hub_relative_path == ".")
      - cfg via load_config(hub_dir, hub_dir / ".millhouse")

    cfg is sourced from the hub's own .millhouse/, not from git_root/.millhouse/, because mill-claim
    writes hub_relative_path only at the hub (it does not bootstrap a stub at git_root/.millhouse/
    the way mill-spawn does).

    Returns active_hub / path_tmpl after substituting any "<SLUG>" token.

    ``slug`` is always an already-resolved value here — every caller of ``resolve_path``
    (``_review_code.py``, ``_review_plan.py``, ``_review_discussion.py``, and the
    ``millpy-review-*.py`` CLIs) obtains ``slug`` from its own flow (``find_active_slug`` or a
    ``--slug`` override) before calling this function, so ``resolve_path`` never needs
    ``resolve_active_hub``'s inner ``slug_from_branch`` re-validation. ``skip_slug_validation=True``
    is passed accordingly, avoiding a daemon
    round-trip on every call — this function runs on both the ``prepare`` and ``finalize`` stage of
    every review round, at least twice per round.

    Raises:
        _paths.ActiveWorktreeNotFound | _paths.ActiveWorktreeSlugMismatch: propagated from the inner
        resolve_active_hub call.
    """
    git_root = _paths.resolve_git_root()
    container_path = _paths.resolve_container_path(git_root)
    hub_dir = _paths.resolve_hub_path()
    cfg = load_config(hub_dir, hub_dir / ".millhouse")
    active_hub = _paths.resolve_active_hub(
        container_path,
        slug,
        cfg=cfg,
        git_root=git_root,
        skip_slug_validation=True,
    )
    resolved_tmpl = path_tmpl.replace("<SLUG>", slug)
    return _paths.resolve_task_path(active_hub, resolved_tmpl)


def discover_round(reviews_dir: Path, review_type: str, scope: str) -> int:
    """Scan reviews_dir and return the next round number for (review_type, scope).

    ``scope`` is either ``"holistic"`` (for discussion reviews and plan/code holistic reviews) or a
    batch name string (for per-batch plan/code reviews).

    If ``reviews_dir`` does not exist, return 1.

    Scope semantics:
    - ``scope == "holistic"``: count files where RE_SIMPLE matches AND ``m.group("type") ==
        review_type``.
        RE_BATCH matches are ignored entirely.
    - ``scope == <batch_name>``: count files where RE_SIMPLE does NOT match AND RE_BATCH matches AND
        ``m.group("type") == review_type`` AND ``m.group("batch") == scope``.

    RE_SIMPLE is checked before RE_BATCH for every file, matching the existing convention that
    prevents a plan-holistic file (e.g. …-plan-review-r1.md) from being mis-identified as a batch
    review via RE_BATCH.

    Return ``max(found) + 1`` if any matching files exist, else 1.
    """
    if not reviews_dir.exists():
        return 1

    found: list[int] = []
    for entry in reviews_dir.iterdir():
        if not entry.is_file():
            continue
        name = entry.name
        m_simple = RE_SIMPLE.match(name)
        if m_simple:
            if scope == "holistic" and m_simple.group("type") == review_type:
                found.append(int(m_simple.group("n")))
            # RE_SIMPLE matched — skip RE_BATCH for this file regardless.
            continue
        # RE_SIMPLE did not match — try RE_BATCH (per-batch scope only).
        if scope != "holistic":
            m_batch = RE_BATCH.match(name)
            if (
                m_batch
                and m_batch.group("type") == review_type
                and m_batch.group("batch") == scope
            ):
                found.append(int(m_batch.group("n")))

    return max(found) + 1 if found else 1


def detect_resume_round(reviews_dir: Path, review_type: str) -> int | None:
    """Return the highest per-batch-only round for review_type, or None.

    Returns the highest round number ``N`` such that at least one per-batch review file exists for
    round ``N`` AND no holistic review file exists for round ``N``.
    Returns ``None`` when no such round exists (either all rounds have a holistic file, no per-batch
    files exist at all, or ``reviews_dir`` does not exist).

    Uses RE_SIMPLE (checked first per convention) to identify holistic files and RE_BATCH to
    identify per-batch files, both filtered by ``review_type``.

    Consumed by ``_review_plan.run`` to detect a partially-complete run where per-batch reviews are
    done but the holistic pass has not yet fired.
    """
    if not reviews_dir.exists():
        return None

    batch_rounds: set[int] = set()
    holistic_rounds: set[int] = set()

    for entry in reviews_dir.iterdir():
        if not entry.is_file():
            continue
        name = entry.name
        m_simple = RE_SIMPLE.match(name)
        if m_simple:
            if m_simple.group("type") == review_type:
                holistic_rounds.add(int(m_simple.group("n")))
            continue
        m_batch = RE_BATCH.match(name)
        if m_batch and m_batch.group("type") == review_type:
            batch_rounds.add(int(m_batch.group("n")))

    candidates = batch_rounds - holistic_rounds
    if not candidates:
        return None
    return max(candidates)


# Regex constants for parse_batch_refs.
# Header line: - **Context:** <inline> (inline may be empty for multi-line bullet form).
_RE_REFS_HEADER = re.compile(
    r"^-\s*\*\*(Context|Edits|Creates|Deletes):\*\*(?P<inline>.*)$"
)
# Sub-bullet under a multi-line header (leading whitespace + dash).
_RE_REFS_SUB = re.compile(r"^\s+-\s*(.+)$")

# Header line for the Moves: field.
# Kept separate from _RE_REFS_HEADER because a Moves sub-bullet has a two-backtick-path grammar (src -> dst) that the reads-not-backtick-path validator rejects when mixed with single-path headers.
_RE_MOVES_HEADER = re.compile(r"^-\s*\*\*Moves:\*\*(?P<inline>.*)$")

# Matches a well-formed move sub-bullet: exactly `src` -> `dst`.
# The separator must be the ASCII literal " -> " (space, hyphen-minus, greater-than, space).
# Any sub-bullet that does not match this pattern is skipped as malformed.
_RE_MOVE_PAIR = re.compile(r"^`([^`]+)` -> `([^`]+)`$")


def parse_batch_refs(
    batch_path: Path,
    fields: tuple[str, ...] = ("Context", "Edits", "Creates", "Deletes"),
) -> list[str]:
    """Extract raw path strings from a batch file's Context/Edits/Creates/Deletes lines.

    Handles the single-line form (- **Context:** `a`, `b`) and the multi-line bullet form (-
    **Context:**\\n - `a`\\n - `b`).
    Filters tokens whose lowercase form equals ``'none'`` (case-insensitive).
    Returns a deduplicated list preserving first-seen order.
    Used by both plan review and code review to build the source-file bulk.

    Args:
        batch_path: Path to the batch file.
        fields: Tuple of field names to extract (e.g., ("Edits", "Creates")).
            Defaults to ("Context", "Edits", "Creates", "Deletes").

    Returns:
        Deduplicated list of raw path strings from matched fields, preserving first-seen order.
    """
    text = batch_path.read_text(encoding="utf-8")
    seen: dict[str, None] = {}
    lines = text.splitlines()

    i = 0
    while i < len(lines):
        m = _RE_REFS_HEADER.match(lines[i])
        if m and m.group(1) in fields:
            inline = m.group("inline").strip()
            if inline:
                backtick_tokens = re.findall(r"`([^`]+)`", inline)
                tokens = (
                    backtick_tokens
                    if backtick_tokens
                    else [t.strip() for t in inline.split(",") if t.strip()]
                )
            else:
                tokens = []
                j = i + 1
                while j < len(lines):
                    sm = _RE_REFS_SUB.match(lines[j])
                    if not sm:
                        break
                    rest = sm.group(1).strip()
                    bt = re.findall(r"`([^`]+)`", rest)
                    if bt:
                        tokens.append(bt[0])
                    j += 1
            for t in tokens:
                if t.lower() != "none":
                    seen[t] = None
        i += 1

    return list(seen.keys())


def parse_moves(batch_path: Path) -> list[tuple[str, str]]:
    """
    Extract Moves: source/destination pairs from a single batch file.

    Scans every ``- **Moves:**`` header in the file.
    Two forms are supported:

    * Inline ``none`` (case-insensitive): the header carries no moves; treated as an empty
        contribution so the file does not raise.
    * Multi-line sub-bullets (empty inline value or any non-"none" inline): each sub-bullet is read
        with ``_RE_REFS_SUB`` and then matched against ``_RE_MOVE_PAIR``.
        A sub-bullet that does not match the pattern (e.g.
        missing arrow, only one backtick path) is silently skipped so that malformed bullets are
            reported by the ``move-format`` validator check (batch 2) rather than raising here.

    The returned list is deduplicated, preserving first-seen order.
    The function never raises;
    any I/O error propagates from ``read_text``.

    Args:
        batch_path: Path to a batch markdown file (e.g. ``01-foo.md``).

    Returns:
        Deduplicated list of ``(source, destination)`` string tuples in first-seen order.
        Empty list when the file declares no moves or all Moves: headers carry the ``none``
        sentinel.
    """
    text = batch_path.read_text(encoding="utf-8")
    # Use an insertion-ordered dict (Python 3.7+) as an ordered set of pairs.
    seen: dict[tuple[str, str], None] = {}
    lines = text.splitlines()

    i = 0
    while i < len(lines):
        m = _RE_MOVES_HEADER.match(lines[i])
        if m:
            inline = m.group("inline").strip()

            # Explicit "none" sentinel: this card declares no moves;
            # skip without scanning sub-bullets so the `none` token is not mistakenly treated as a file path.
            if inline.lower() == "none":
                i += 1
                continue

            # Non-"none" inline (or empty): scan the following sub-bullets.
            # An unexpected non-empty inline value is simply ignored;
            # the sub-bullets on the lines below are the authoritative source.
            j = i + 1
            while j < len(lines):
                sm = _RE_REFS_SUB.match(lines[j])
                if not sm:
                    # No longer in a sub-bullet block; stop scanning.
                    break
                rest = sm.group(1).strip()
                pm = _RE_MOVE_PAIR.match(rest)
                if pm:
                    # Well-formed pair: record source and destination.
                    pair = (pm.group(1), pm.group(2))
                    if pair not in seen:
                        seen[pair] = None
                # Malformed sub-bullet: tolerate silently.
                j += 1
        i += 1

    return list(seen.keys())


def parse_deletes(batch_path: Path) -> set[str]:
    """
    Extract Deletes: tokens from a single batch file.

    Scans every ``- **Deletes:**`` header in the file.
    Two forms are supported: the single-line inline form (``- **Deletes:** a, b``) and the
    multi-line sub-bullet form (``- **Deletes:**`` followed by `` - a`` / `` - b`` sub-bullets, each
    a backtick-quoted path).
    Tokens whose lowercase form equals ``'none'`` (case-insensitive) are filtered out, so a card
    that declares no deletions contributes nothing.

    A malformed or absent ``Deletes:`` header simply contributes nothing to the returned set;
    this function never raises except for I/O errors propagated from ``read_text``.

    Args:
        batch_path: Path to a single batch markdown file (e.g. ``01-foo.md``).

    Returns:
        Set of raw token strings (NOT resolved Paths) declared under every ``Deletes:`` header in
        this file.
        Empty set when the file declares no deletions or every ``Deletes:`` header carries the
        ``none`` sentinel.
    """
    text = batch_path.read_text(encoding="utf-8")
    deletes: set[str] = set()
    lines = text.splitlines()

    i = 0
    while i < len(lines):
        m = _RE_REFS_HEADER.match(lines[i])
        if m and m.group(1) == "Deletes":
            inline = m.group("inline").strip()
            if inline:
                backtick_tokens = re.findall(r"`([^`]+)`", inline)
                tokens = (
                    backtick_tokens
                    if backtick_tokens
                    else [t.strip() for t in inline.split(",") if t.strip()]
                )
            else:
                tokens = []
                j = i + 1
                while j < len(lines):
                    sm = _RE_REFS_SUB.match(lines[j])
                    if not sm:
                        break
                    rest = sm.group(1).strip()
                    bt = re.findall(r"`([^`]+)`", rest)
                    if bt:
                        tokens.extend(bt)
                    j += 1
            for t in tokens:
                if t.lower() != "none":
                    deletes.add(t)
        i += 1

    return deletes


def compute_creates_union(plan_dir: Path) -> set[str]:
    """Return the union of all Creates: tokens across every batch in plan_dir.

    Iterates every ``??-*.md`` file under ``plan_dir`` except ``00-overview.md``, extracts only the
    ``Creates:`` lines, and returns a flat set of raw token strings (NOT resolved Paths).
    Filters tokens whose lowercase form equals ``'none'`` (case-insensitive).
    Returns an empty set if ``plan_dir`` doesn't exist or contains no batch files.
    """
    if not plan_dir.exists():
        return set()
    creates: set[str] = set()
    for batch_path in sorted(plan_dir.glob("??-*.md")):
        if batch_path.name == "00-overview.md":
            continue
        text = batch_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            m = _RE_REFS_HEADER.match(lines[i])
            if m and m.group(1) == "Creates":
                inline = m.group("inline").strip()
                if inline:
                    backtick_tokens = re.findall(r"`([^`]+)`", inline)
                    tokens = (
                        backtick_tokens
                        if backtick_tokens
                        else [t.strip() for t in inline.split(",") if t.strip()]
                    )
                else:
                    tokens = []
                    j = i + 1
                    while j < len(lines):
                        sm = _RE_REFS_SUB.match(lines[j])
                        if not sm:
                            break
                        rest = sm.group(1).strip()
                        bt = re.findall(r"`([^`]+)`", rest)
                        if bt:
                            tokens.extend(bt)
                        j += 1
                for t in tokens:
                    if t.lower() != "none":
                        creates.add(t)
            i += 1
    return creates


def compute_deletes_union(plan_dir: Path) -> set[str]:
    """Return the union of all Deletes: tokens across every batch in plan_dir.

    Iterates every ``??-*.md`` file under ``plan_dir`` except ``00-overview.md``, extracts only the
    ``Deletes:`` lines, and returns a flat set of raw token strings (NOT resolved Paths).
    Filters tokens whose lowercase form equals ``'none'`` (case-insensitive).
    Returns an empty set if ``plan_dir`` doesn't exist or contains no batch files.
    """
    if not plan_dir.exists():
        return set()
    deletes: set[str] = set()
    for batch_path in sorted(plan_dir.glob("??-*.md")):
        if batch_path.name == "00-overview.md":
            continue
        deletes |= parse_deletes(batch_path)
    return deletes


def compute_moves_union(plan_dir: Path) -> tuple[set[str], set[str]]:
    """
    Return the union of all Moves: sources and targets across every batch in plan_dir.

    Iterates every ``??-*.md`` file under ``plan_dir`` except ``00-overview.md`` (mirroring
    ``compute_creates_union``), calls ``parse_moves`` on each, and accumulates the source path
    (first element of each pair) and the destination path (second element) into two independent
    sets.

    The source set mirrors the semantics of ``compute_deletes_union`` (sources disappear after the
    move) and the target set mirrors ``compute_creates_union`` (targets appear after the move).
    Callers that need to suppress ``non-existent-path`` errors for move targets should treat
    ``targets`` the same way they treat ``creates_union``.

    Args:
        plan_dir: Path to the plan directory containing batch markdown files.

    Returns:
        A ``(sources, targets)`` tuple of sets of raw token strings (NOT resolved Paths).
        Returns ``(set(), set())`` when ``plan_dir`` does not exist or contains no batch files with
        Moves: entries.
    """
    if not plan_dir.exists():
        return (set(), set())

    sources: set[str] = set()
    targets: set[str] = set()

    # Iterate batch files in sorted order, skipping the overview.
    for batch_path in sorted(plan_dir.glob("??-*.md")):
        if batch_path.name == "00-overview.md":
            continue
        # parse_moves never raises; malformed bullets are silently skipped.
        for src, dst in parse_moves(batch_path):
            sources.add(src)
            targets.add(dst)

    return (sources, targets)


def resolve_ref_paths(
    raw_paths: list[str],
    project_root: Path,
    root: str | None,
    *,
    creates_union: set[str] | None = None,
    deletes_union: set[str] | None = None,
    wiki_root: Path | None = None,
    git_root: Path | None = None,
    caller_label: str = "resolve_ref_paths",
    soft_fail_gitignored: bool = False,
) -> list[Path]:
    """Resolve batch-reference path strings to absolute ``Path``s.

    ``root`` is the optional filesystem sub-path declared in the plan overview's frontmatter
    ``root:`` field.
    When present every raw path is resolved under ``project_root / root``;
    otherwise directly under ``project_root``.

    Resolution order (first match wins):
    1. wiki/ prefix routes through wiki_root (unchanged).
    2. Candidate path under git_root/root/raw (when git_root and root set).
    3. Candidate path under project_root (unchanged).
    4. Candidate path under git_root/raw (when git_root provided, no root).
    5. creates_union/deletes_union suppression (unchanged).
    6. When ``soft_fail_gitignored`` is True and no candidate is on disk, confirm via ``git
        check-ignore`` whether any candidate is git-ignored under its own source root;
        if so, skip the ref with a stderr warning instead of hard-failing (#733).
    7. Hard-fail ReviewError (unchanged).

    Keyword args:
        creates_union: Set of raw token strings extracted from ``Creates:`` lines across all
            batches.
            A path not on disk but present in ``creates_union`` is silently skipped — the file will
                exist after the creating batch runs (#60).
        deletes_union: Set of raw token strings extracted from ``Deletes:`` lines across all
            batches.
            A path not on disk but present in ``deletes_union`` is silently skipped — the file has
                already been deleted by a prior batch.
            Paths still on disk that appear in ``deletes_union`` are resolved normally and included.
        wiki_root: When provided, raw paths starting with ``wiki/`` are resolved against
            ``wiki_root`` instead of ``project_root`` (#43).
        git_root: When provided, paths not found under project_root are tried under git_root as a
            fallback before suppression/hard-fail.
        caller_label: Prefix used in ``ReviewError`` messages.
            Defaults to the function name.
        soft_fail_gitignored: When True, a missing non-wiki candidate that is confirmed git-ignored
            (via ``git check-ignore``) under its own source root is silently skipped with a stderr
            warning instead of raising ``ReviewError``.
            Opt-in;
            the ``wiki/`` branch is never affected.
            Default False (#733).

    Raises ``ReviewError`` when a candidate path is not on disk AND not in either ``creates_union``
    or ``deletes_union`` — hard-fail replaces the old silent-skip + warning behaviour (#41).
    """
    creates = creates_union or set()
    deletes = deletes_union or set()
    resolved: list[Path] = []
    for raw in raw_paths:
        # Defensive None/none filter — must run before any string operations.
        if raw is None or (isinstance(raw, str) and raw.lower() == "none"):
            continue
        # Wiki-path resolution.
        if raw.startswith("wiki/"):
            if wiki_root is None:
                raise ReviewError(
                    f"[{caller_label}] wiki-prefixed ref {raw!r} but no wiki_root provided"
                )
            candidate = wiki_root / raw[len("wiki/") :]
            # Hit on disk.
            if candidate.exists():
                resolved.append(candidate)
                continue
            # Suppression via creates_union or deletes_union.
            if raw in creates or raw in deletes:
                continue
            # Hard-fail.
            raise ReviewError(
                f"[{caller_label}] referenced path not found: {raw!r}; "
                f"not in plan creates_union, not on disk; resolved candidate: {candidate}"
            )
        # Non-wiki path resolution: try git_root/root/raw (if git_root available), then project_root/root/raw, then git_root/raw (if no root).
        # Each candidate is paired with the source_root it was built from, so a later soft-fail check can run `git check-ignore` against the right repo.
        candidates: list[tuple[Path, Path]] = []
        if root and git_root is not None:
            # When the worktree cwd is itself the `root` sub-path, project_root already ends with `root`, so project_root / root / raw doubles it.
            # Try git_root / root / raw first so `root` is joined onto the repo root exactly once — matching how the plan was validated.
            candidates.append((git_root / root / raw, git_root))
        if root:
            candidates.append((project_root / root / raw, project_root))
        else:
            candidates.append((project_root / raw, project_root))
        if git_root is not None:
            candidates.append((git_root / raw, git_root))
        # Primary candidate is the first one for error reporting.
        candidate = candidates[0][0]
        # Try all candidates; first match wins.
        hit = next((pair for pair in candidates if pair[0].exists()), None)
        if hit is not None:
            resolved.append(hit[0])
            continue
        # Suppression via creates_union or deletes_union.
        if raw in creates or raw in deletes:
            continue
        # Opt-in soft-fail: a missing ref that is confirmed git-ignored under its own source root is skipped with a warning instead of hard-failing (#733).
        # Only attempted when the caller opted in.
        if soft_fail_gitignored:
            skipped = False
            for cand, source_root in candidates:
                try:
                    result = _subprocess_util.run(
                        ["git", "-C", str(source_root), "check-ignore", "-q", str(cand)]
                    )
                except Exception:
                    # Any failure (including a non-git source_root) means "not confirmed ignored" — never propagates.
                    continue
                if result.returncode == 0:
                    print(
                        f"[resolve_ref_paths] warning: skipping git-ignored Context: ref "
                        f"{raw!r} (confirmed ignored under {source_root})",
                        file=sys.stderr,
                    )
                    skipped = True
                    break
            if skipped:
                continue
        # Hard-fail.
        raise ReviewError(
            f"[{caller_label}] referenced path not found: {raw!r}; "
            f"not in plan creates_union, not on disk; resolved candidate: {candidate}"
        )
    return resolved


def resolve_existing_paths(
    raw_paths: list[str],
    project_root: Path,
    root: str | None,
    *,
    wiki_root: Path | None = None,
    git_root: Path | None = None,
) -> list[Path]:
    """Resolve raw paths and return only those that already exist on disk.

    Mirrors resolve_ref_paths's standard-vs-wiki routing (wiki/ prefix routes through wiki_root;
    otherwise project_root + root) plus optional git_root fallback.
    Unlike resolve_ref_paths, missing paths and routing failures are silently dropped — no warning,
    no error, no creates_union check.
    Used to expand the bulk with cross-batch ancestor creates that already exist; missing creates
    are not an error here, they just aren't included.

    Resolution order (first match wins):
    1. wiki/ prefix routes through wiki_root (unchanged).
    2. Candidate path under git_root/root/raw (when git_root and root set).
    3. Candidate path under project_root (unchanged).
    4. Candidate path under git_root/raw (when git_root provided, no root).
    5. Silent drop (no raise).

    Keyword args:
        wiki_root: When provided, raw paths starting with ``wiki/`` are resolved against
        ``wiki_root`` instead of ``project_root``.
        git_root: When provided, paths not found under project_root are tried under git_root as a
        fallback before silent drop.
    """
    result: list[Path] = []
    for raw in raw_paths:
        # Defensive None/none filter — same as resolve_ref_paths.
        if raw is None or (isinstance(raw, str) and raw.lower() == "none"):
            continue
        # Wiki-path routing.
        if raw.startswith("wiki/"):
            if wiki_root is None:
                # Key divergence from resolve_ref_paths: silent drop instead of raise.
                continue
            candidate = wiki_root / raw[len("wiki/") :]
            if candidate.exists():
                result.append(candidate)
            continue
        # Non-wiki path resolution: try git_root/root/raw (if git_root available), then project_root/root/raw, then git_root/raw (if no root).
        candidates = []
        if root and git_root is not None:
            # When the worktree cwd is itself the `root` sub-path, project_root already ends with `root`, so project_root / root / raw doubles it.
            # Try git_root / root / raw first so `root` is joined onto the repo root exactly once — matching how the plan was validated.
            candidates.append(git_root / root / raw)
        if root:
            candidates.append(project_root / root / raw)
        else:
            candidates.append(project_root / raw)
        if git_root is not None:
            candidates.append(git_root / raw)
        # Try all candidates; first match wins (silent drop if none found).
        hit = next((c for c in candidates if c.exists()), None)
        if hit is not None:
            result.append(hit)
    return result


def _load_root_from_overview(overview_path: Path) -> str | None:
    """Read the `root:` field from the overview's top fenced-yaml block.

    v2 plan overviews use fenced ```yaml``` frontmatter (per the project markdown convention; `---`
    is reserved for SKILL.md).
    This parser locates the first ```yaml``` block and reads `root:` from it.
    Returns the root string if present and truthy, else None.
    Any structural problem (no block, unterminated, bad yaml, absent key) silently yields None — the
    review surface degrades to resolving paths against project_root directly, which is the right
    behaviour for a mill-v2 worktree where root is typically empty.
    """
    try:
        text = overview_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None

    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "```yaml":
            start = i + 1
            break
    if start is None:
        return None
    end = None
    for j in range(start, len(lines)):
        if lines[j].strip() == "```":
            end = j
            break
    if end is None:
        return None

    fm_text = "\n".join(lines[start:end])
    try:
        data = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    return data.get("root") or None


def _read_for_bulk(p: Path) -> str:
    """Read file content, handling .ipynb notebooks specially.

    For .ipynb files: reads as JSON, extracts cell source for 'code' and 'markdown' cell types,
    joins sources with blank lines between cells.
    For other extensions: returns standard UTF-8 text read.

    On JSON parse error for .ipynb: prints warning to stderr and returns empty string so the file
    still appears in bulk output as an empty section.

    If p is a directory: prints warning to stderr and returns empty string.
    """
    if p.is_dir():
        print(
            f"[_read_for_bulk] warning: {p} is a directory, skipping", file=sys.stderr
        )
        return ""

    if p.suffix == ".ipynb":
        try:
            content = p.read_text(encoding="utf-8")
            notebook = json.loads(content)
        except json.JSONDecodeError as exc:
            print(
                f"[_read_for_bulk] warning: {p} JSON parse error: {exc}",
                file=sys.stderr,
            )
            return ""

        cells = notebook.get("cells", [])
        sources: list[str] = []
        for cell in cells:
            cell_type = cell.get("cell_type")
            if cell_type not in ("code", "markdown"):
                continue
            source = cell.get("source", "")
            if isinstance(source, list):
                sources.append("".join(source))
            else:
                sources.append(str(source))
        return "\n\n".join(sources)
    else:
        return p.read_text(encoding="utf-8", errors="replace")


def bulk_files(file_paths: list[Path]) -> str:
    """Concatenate file contents with '--- FILE: <path> ---' delimiters.

    Paths that do not exist are skipped with a stderr warning.
    """
    parts: list[str] = []
    for p in file_paths:
        try:
            contents = _read_for_bulk(p)
        except (FileNotFoundError, PermissionError):
            print(
                f"[bulk_files] warning: {p} not found or not readable, skipping",
                file=sys.stderr,
            )
            continue
        parts.append(f"--- FILE: {p} ---\n{contents}\n--- END FILE: {p} ---")
    return "\n\n".join(parts)


def bulk_files_with_diff(
    file_paths: list[Path],
    start_sha: str,
    project_root: Path,
    threshold: float,
) -> str:
    """Like bulk_files but substitutes git diff output for small-diff files.

    For each file: if the diff from start_sha to HEAD is smaller than threshold * file_content_size,
    include the diff instead of full content.
    Files with no diff (unchanged between start_sha and HEAD) are included at full content so the
    reviewer has all context.
    """
    parts: list[str] = []
    for p in file_paths:
        try:
            file_content = _read_for_bulk(p)
        except (FileNotFoundError, PermissionError):
            print(
                f"[bulk_files_with_diff] warning: {p} not found or not readable, skipping",
                file=sys.stderr,
            )
            continue

        try:
            rel_path = p.relative_to(project_root).as_posix()
        except ValueError:
            rel_path = str(p)

        result = _subprocess_util.run(
            [
                "git",
                "-C",
                str(project_root),
                "diff",
                f"{start_sha}..HEAD",
                "--",
                rel_path,
            ],
        )

        if result.returncode != 0:
            print(
                f"[bulk_files_with_diff] warning: git diff failed for {p} (returncode={result.returncode}), using full file",
                file=sys.stderr,
            )
            parts.append(f"--- FILE: {p} ---\n{file_content}\n--- END FILE: {p} ---")
            continue

        diff_text = result.stdout

        if not diff_text:
            parts.append(f"--- FILE: {p} ---\n{file_content}\n--- END FILE: {p} ---")
            continue

        if len(diff_text) < threshold * len(file_content):
            parts.append(
                f"--- DIFF: {p} (from {start_sha[:8]}) ---\n{diff_text}\n--- END DIFF: {p} ---"
            )
            continue

        parts.append(f"--- FILE: {p} ---\n{file_content}\n--- END FILE: {p} ---")

    return "\n\n".join(parts)


def build_manifest_section(file_paths: list[Path]) -> str:
    """Return a `## Files included` markdown block listing every bulked file.

    Output shape (no trailing newline):

        ## Files included (N=<count>)

        - <path-1>
        - <path-2>
        ...

    The manifest is the FIRST thing the reviewer reads inside the artefact section.
    Its job is to remove the long-context haystack effect: the reviewer scans this list, then can
    answer "is file X provided?"
    in O(1) instead of scanning a 200k-char bulk for the matching `--- FILE: X ---` delimiter.
    """
    if not file_paths:
        return "## Files included (N=0)\n\n(no files)"
    count = len(file_paths)
    bullets = "\n".join(f"- {p}" for p in file_paths)
    return f"## Files included (N={count})\n\n{bullets}"


def build_deletes_section(deletes_tokens: list[str]) -> str:
    """Return a `## Intentionally deleted` markdown block listing deleted tokens.

    Output shape (no trailing newline):

        ## Intentionally deleted (N=<count>)

        - <token-1>
        - <token-2>
        ...

    Empty list returns the empty string so callers can splice unconditionally.
    Tokens are emitted as-is — no backtick wrapping is added by this helper.
    """
    if not deletes_tokens:
        return ""
    count = len(deletes_tokens)
    bullets = "\n".join(f"- {t}" for t in deletes_tokens)
    return f"## Intentionally deleted (N={count})\n\n{bullets}"


_RE_MISSING_CONTEXT_BULLET = re.compile(r"^\s*-\s+`([^`]+)`")

_REVIEW_BEGIN = "MILL_REVIEW_BEGIN"
_REVIEW_END = "MILL_REVIEW_END"


def extract_review_content(raw: str) -> str:
    """Strip everything outside MILL_REVIEW_BEGIN / MILL_REVIEW_END markers.

    Falls back to raw unchanged when markers are absent (e.g.
    test stubs).
    """
    begin = raw.find(_REVIEW_BEGIN)
    if begin == -1:
        return raw
    end = raw.find(_REVIEW_END, begin + len(_REVIEW_BEGIN))
    if end == -1:
        return raw
    return raw[begin + len(_REVIEW_BEGIN) : end].strip()


def parse_missing_context(review_text: str) -> list[str]:
    """Extract path strings from a `## Missing context` section.

    The reviewer's NEED_CONTEXT output uses the convention:

        ## Missing context

        - `path/a` — reason text
        - `path/b` — reason text

    Returns the list of raw path tokens (NOT resolved Paths).
    Empty list if the heading is absent or no bullet matches the expected shape.
    Multi-line bullets are not supported — paths must appear backtick-wrapped on their own bullet
    line.
    """
    lines = review_text.splitlines()
    in_section = False
    paths: list[str] = []
    for line in lines:
        if not in_section:
            if line.startswith("## Missing context"):
                in_section = True
            continue
        # Stop at the next ## heading.
        if line.startswith("## "):
            break
        m = _RE_MISSING_CONTEXT_BULLET.match(line)
        if m:
            token = m.group(1)
            if token.lower() != "none":
                paths.append(token)
    return paths


def build_reattached_section(file_paths: list[Path]) -> str:
    """Return a `## Re-attached files (you said these were missing)` block with the listed files
    inlined via bulk_files.

    Used by the NEED_CONTEXT resume retry: the missing-context paths from the prior round are
    re-attached at the top of the new prompt so the reviewer cannot claim absence again without
    contradicting itself.
    The section is appended to the existing artefact section.
    """
    if not file_paths:
        return ""
    return "## Re-attached files (you said these were missing)\n\n" + bulk_files(
        file_paths
    )


_TOOL_RULE_BULK = (
    "**CRITICAL: Do NOT request tool calls. All content you need is in this prompt.**\n"
    "**CRITICAL: Review-only. Do NOT suggest modifications. Findings only.**\n"
    "**CRITICAL: Do NOT read `reviews/`. Evaluate fresh each round.**\n"
    "**CRITICAL: Do NOT use Write. Return review as text.**"
)

_TOOL_RULE_TOOL_USE = (
    "**You MAY use Read, Grep, and Glob to verify claims against source files.**\n"
    "**CRITICAL: Do NOT use Write, Edit, or run git/bash. Return review as text.**\n"
    "**CRITICAL: Review-only. Do NOT suggest modifications. Findings only.**\n"
    "**CRITICAL: Do NOT read `reviews/`. Evaluate fresh each round.**"
)

# Agent-mode bulk: the trap cell.
# A reviewer's `mode` derives from the `tooluse` spec flag, which defaults to False, so the plain "bulk" name is reachable in agent mode too.
# Today's non-agent bulk text opens with a bare "Do NOT request tool calls", which under agent mode would contradict the Write instruction below it and yield no .out.md and an ERROR envelope every round.
# This cell instead forbids tool calls only for *gathering content* ("everything you need is in this prompt") and carves out exactly one Write -- the report to the file named in the brief's output-contract footer.
# Because the templates' static read-only header is removed in a later batch, this cell (like its tool-use sibling below) is also the sole remaining statement of the read-only posture, so it restates it in full.
_TOOL_RULE_BULK_AGENT = (
    "**CRITICAL: Do NOT use any tool to gather content -- everything you need "
    "is in this prompt.**\n"
    "**CRITICAL: The one exception is Write -- use it exactly once, to write "
    "your full report to the file named in this brief's output-contract "
    "footer.**\n"
    "**CRITICAL: Do NOT use Edit, or run git/bash.**\n"
    "**CRITICAL: Review-only. Do NOT suggest modifications. Findings only.**\n"
    "**CRITICAL: Do NOT read `reviews/`. Evaluate fresh each round.**"
)

# Agent-mode tool-use: keeps the Read/Grep/Glob verification grant and adds the same single-Write carve-out as the bulk-agent cell above, for the same reason -- the report now goes to a file, not into the chat response.
_TOOL_RULE_TOOL_USE_AGENT = (
    "**You MAY use Read, Grep, and Glob to verify claims against source files.**\n"
    "**CRITICAL: The one exception beyond that is Write -- use it exactly "
    "once, to write your full report to the file named in this brief's "
    "output-contract footer.**\n"
    "**CRITICAL: Do NOT use Edit, or run git/bash.**\n"
    "**CRITICAL: Review-only. Do NOT suggest modifications. Findings only.**\n"
    "**CRITICAL: Do NOT read `reviews/`. Evaluate fresh each round.**"
)


def build_tool_rule(mode: str, agent_mode: bool = False) -> str:
    """Return the <TOOL_RULE> block for a reviewer's MODE and dispatch channel.

    Templates embed this as the top-of-prompt directive,
    and it is the only channel-aware injection point in a review prompt -- the sole owner of the
    read-only clause, the Write carve-out, and the report destination.
    No template or agent definition may state a tool permission or output destination of its own.

    Four cells result from crossing `mode` with `agent_mode`: - bulk x non-agent, tool-use x
        non-agent: byte-identical to the pre-agent-mode strings.
        This is the `--stage full` fallback path (raw LLM-provider call, at most Read/Grep/Glob, no
            Write, no brief to name a report file in) and must keep working verbatim. - bulk x
            agent, tool-use x agent: same tool grants as their non-agent counterparts, plus exactly
            one Write permitted for the report (named by description only -- the literal path lives
            in write_brief's footer, never a template token).
        Still forbid Edit, git, and bash.

    Args:
        mode: "bulk" or "tool-use".
        agent_mode: When True, return the agent-mode cell (adds the single Write carve-out).
            Defaults to False, which returns today's pre-existing text unchanged -- this is what
                keeps every existing positional callsite green.

    Returns:
        The <TOOL_RULE> markdown block for the requested cell.

    Raises:
        ValueError: If mode is not "bulk" or "tool-use".
    """
    if mode == "bulk":
        return _TOOL_RULE_BULK_AGENT if agent_mode else _TOOL_RULE_BULK
    if mode == "tool-use":
        return _TOOL_RULE_TOOL_USE_AGENT if agent_mode else _TOOL_RULE_TOOL_USE
    raise ValueError(f"Unknown reviewer mode: {mode!r} (expected 'bulk' or 'tool-use')")


def _check_large_prompt(
    prompt_text: str,
    cfg: dict,
    role: str,
    scope: str,
) -> tuple[bool, int]:
    """Check if prompt exceeds large_prompt threshold.

    Returns (is_over_threshold, estimated_ktok) where estimated_ktok is computed as len(prompt_text)
    // 4000 and threshold_ktok is read from
    cfg["roles"][role][scope]["large_prompt"]["threshold_ktok"] (default 100).
    """
    large_prompt_cfg = (
        cfg.get("roles", {}).get(role, {}).get(scope, {}).get("large_prompt")
    )
    if not large_prompt_cfg:
        return (False, len(prompt_text) // 4000)
    threshold_ktok = large_prompt_cfg.get("threshold_ktok", 100)
    estimated_ktok = len(prompt_text) // 4000
    is_over_threshold = estimated_ktok >= threshold_ktok
    return (is_over_threshold, estimated_ktok)


def resolve_large_prompt_timeout(
    prompt_text: str,
    cfg: dict,
    role: str,
    scope: str,
    default_timeout: int,
) -> int:
    """Return large_prompt.timeout when prompt is over threshold and key is set, else
    default_timeout.

    Uses _check_large_prompt to compute size check;
    returns the override value from cfg["roles"][role][scope]["large_prompt"]["timeout"] if the
    prompt exceeds the threshold and the timeout key is set, otherwise returns default_timeout.
    """
    is_over_threshold, _ = _check_large_prompt(prompt_text, cfg, role, scope)
    if not is_over_threshold:
        return default_timeout
    large_prompt_cfg = (
        cfg.get("roles", {}).get(role, {}).get(scope, {}).get("large_prompt")
    )
    if not large_prompt_cfg:
        return default_timeout
    override_timeout = large_prompt_cfg.get("timeout")
    if override_timeout is None:
        return default_timeout
    return override_timeout


def maybe_switch_spec_for_large_prompt(
    prompt_text: str,
    spec: dict,
    reviewer_name: str,
    cfg: dict,
    role: str,
    scope: str,
    registry: dict,
) -> tuple[dict, str]:
    """Check prompt size; return (spec, reviewer_name), possibly overridden for large prompts."""
    is_over_threshold, estimated_ktok = _check_large_prompt(
        prompt_text, cfg, role, scope
    )
    large_prompt_cfg = (
        cfg.get("roles", {}).get(role, {}).get(scope, {}).get("large_prompt")
    )
    if not large_prompt_cfg or not is_over_threshold:
        return (spec, reviewer_name)
    override_name = large_prompt_cfg.get("reviewer")
    if override_name is None:
        return (spec, reviewer_name)
    override_spec = _reviewers.resolve(registry, override_name)
    if override_spec.get("type") == "cluster":
        raise ReviewError(
            f"large_prompt.reviewer {override_name!r} is cluster type; "
            "only single reviewers are supported for large-prompt switch"
        )
    effective_spec = dict(override_spec)
    original_tooluse = spec.get("tooluse", False)
    if effective_spec.get("tooluse", False) != original_tooluse:
        print(
            f"[_review_common] large-prompt switch: override {override_name!r} tooluse differs; "
            f"preserving original tooluse={original_tooluse}",
            file=sys.stderr,
        )
        effective_spec["tooluse"] = original_tooluse
    print(
        f"[_review_common] large-prompt switch: estimated ~{estimated_ktok}k tok, "
        f"switching reviewer {reviewer_name!r} -> {override_name!r}",
        file=sys.stderr,
    )
    return (effective_spec, override_name)


def render_prompt(template_name: str, **tokens) -> str:
    """Render a review prompt template from plugins/mill/templates/.

    Auto-uppercases keyword-argument keys so callers can use idiomatic Python kwarg style (e.g.
    artefact_path="..."
    becomes ARTEFACT_PATH).

    Template path:
        <scripts_dir>/../templates/<template_name>.md

    Raises FileNotFoundError if the template is absent.
    Lets KeyError from _render.render() propagate unwrapped — a missing token is a programming
    error, not a user error.
    """
    templates_dir = Path(__file__).parent.parent / "templates"
    template_path = templates_dir / f"{template_name}.md"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    uppercased = {k.upper(): str(v) for k, v in tokens.items()}
    return _render.render(template_path, uppercased)


def parse_verdict(raw_output: str) -> str:
    """Extract a valid verdict value from a fenced yaml block,
or unfenced fallback.

    Scans raw_output for the first fenced ```yaml block (on its own line, possibly with trailing
    whitespace). Extracts the 'verdict:' field from inside the block (between the opening ```yaml
    and closing ``` fences).

    If no fenced block is found, attempts a fallback: scans lines for an unfenced 'verdict: <VALUE>'
    line (allowing leading whitespace; strips quotes).
    If <VALUE> is one of the valid verdicts, returns it.

    Valid verdict values:
    - 'APPROVE' — any review type
    - 'REQUEST_CHANGES' — plan and code review
    - 'GAPS_FOUND' — historical v1 discussion-review value, accepted for archive readability only.
        No template emits it again;
        any occurrence found is normalised to 'REQUEST_CHANGES' before this function returns.
    - 'NEED_CONTEXT' — plan and code review only;
        reviewer cannot evaluate without source files that were not included in the bulk.
        Orchestrator responds by re-firing with `--extra-file` plus a notify + self-report entry.

    Raises ReviewError if:
    - No ```yaml opening fence is found AND no unfenced verdict line is found.
    - The yaml block is not closed by a ``` line.
    - The 'verdict:' field is absent from the block.
    - The verdict value is not one of the four above.

    The first ~400 chars of raw_output are included in error messages for debuggability.
    """
    preview = raw_output[:400].strip()
    lines = raw_output.splitlines()

    # Find the first ```yaml opening fence.
    open_idx = None
    for i, line in enumerate(lines):
        if line.rstrip() == "```yaml":
            open_idx = i
            break

    if open_idx is not None:
        # Find the closing ``` fence after the opening.
        close_idx = None
        for i, line in enumerate(lines[open_idx + 1 :], start=open_idx + 1):
            if line.rstrip() == "```":
                close_idx = i
                break

        if close_idx is None:
            raise ReviewError(
                f"Could not parse verdict: ```yaml block not closed.\n"
                f"Raw output preview:\n{preview}"
            )

        # Scan block body for verdict: field.
        for line in lines[open_idx + 1 : close_idx]:
            stripped = line.strip()
            if stripped.startswith("verdict:"):
                value = stripped[len("verdict:") :].strip().strip('"').strip("'")
                if value in (
                    "APPROVE",
                    "REQUEST_CHANGES",
                    "GAPS_FOUND",
                    "NEED_CONTEXT",
                ):
                    # Normalise the historical v1 value to its unified-vocabulary equivalent.
                    return "REQUEST_CHANGES" if value == "GAPS_FOUND" else value
                raise ReviewError(
                    f"Could not parse verdict: invalid value {value!r}; "
                    f"expected APPROVE, REQUEST_CHANGES, GAPS_FOUND, or NEED_CONTEXT.\n"
                    f"Raw output preview:\n{preview}"
                )

        raise ReviewError(
            f"Could not parse verdict: 'verdict:' key not found in ```yaml block.\n"
            f"Raw output preview:\n{preview}"
        )

    # Fallback: scan for unfenced verdict line.
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("verdict:"):
            value = stripped[len("verdict:") :].strip().strip('"').strip("'")
            if value in ("APPROVE", "REQUEST_CHANGES", "GAPS_FOUND", "NEED_CONTEXT"):
                # Normalise the historical v1 value to its unified-vocabulary equivalent.
                return "REQUEST_CHANGES" if value == "GAPS_FOUND" else value

    raise ReviewError(
        f"Could not parse verdict: no ```yaml block found and no unfenced verdict line found.\n"
        f"Raw output preview:\n{preview}"
    )


def _warn_if_prose_diverges(raw_output: str, severity: str, heading_count: int) -> None:
    """
    Emit a warning if prose count diverges from heading count.

    Only warns when heading_count > 0 (to suppress spurious warnings on clean APPROVE reviews with
    no severity headings).
    The raw_output is filtered to exclude lines starting with 'verdict:' before the prose scan, so
    verdict lines cannot trigger warnings.
    """
    if heading_count == 0:
        return

    _WORD_TO_INT = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }

    # Filter out verdict: lines from prose scan
    filtered_lines = [
        line
        for line in raw_output.splitlines()
        if not line.strip().startswith("verdict:")
    ]
    filtered_output = "\n".join(filtered_lines)

    pattern = re.compile(
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
        + re.escape(severity),
        re.IGNORECASE,
    )
    matches = pattern.findall(filtered_output)
    if not matches:
        return
    raw_val = matches[0]
    prose_count = (
        int(raw_val) if raw_val.isdigit() else _WORD_TO_INT.get(raw_val.lower(), -1)
    )
    if prose_count != heading_count:
        print(
            f"[_review_common] warning: parse_blocking_count heading count {heading_count} "
            f"diverges from prose count {prose_count} (severity={severity}) "
            f"-- check review file for missing heading.",
            file=sys.stderr,
        )


def parse_blocking_count(raw_output: str, *, severity: str) -> int:
    """Count "### [<severity>]" or "### [<severity>:<class>]" ATX headings in review output.

    Searches for lines matching ``^###\\s+\\[<severity>(?::[a-z-]+)?\\]\\s+`` using MULTILINE mode --
    the optional class suffix (e.g. ``:design``) is matched and ignored, so a classed heading is
    counted purely on its severity token.
    The severity argument is required (keyword-only).
    Match is case-sensitive.
    Only line-start headings are counted — mid-line occurrences are ignored.

    When the heading count is 0, falls back to scanning all fenced ```yaml blocks for a `findings:`
    list, counting entries whose `severity` field (case-insensitive) matches the severity argument.
    A `class:` field alongside `severity:` on the same entry does not affect this count.

    This function remains in use only for the historical re-read sites named in the
    ceiling-applied-once-at-write-time Shared Decision (_review_plan.py's recovery/resume re-reads
    and _nit_gate.py); the new-review path goes through extract_findings() instead, which classifies
    every finding in a single pass.

    Emits a one-line stderr warning when a prose count phrase in the output (e.g. "Five blocking
    issues remain") disagrees with the heading count.
    The returned count is unchanged;
    the warning is for log inspection only (#225).
    """
    pattern = re.compile(
        r"^###\s+\[" + re.escape(severity) + r"(?::[a-z-]+)?\]\s+",
        re.MULTILINE,
    )
    heading_count = len(pattern.findall(raw_output))

    # When headings are present they are the authoritative count — skip yaml scan.
    if heading_count > 0:
        _warn_if_prose_diverges(raw_output, severity, heading_count)
        return heading_count

    # No headings found — scan fenced yaml blocks for a structured findings list.
    # Reviewers that emit YAML-only output (no markdown headings) use this path.
    yaml_count = 0
    lines = raw_output.splitlines()
    index = 0
    while index < len(lines):
        # Locate the opening fence of a yaml block.
        if lines[index].rstrip() == "```yaml":
            body_lines: list[str] = []
            index += 1
            # Collect lines until the closing fence; skip unclosed blocks silently.
            while index < len(lines) and lines[index].rstrip() != "```":
                body_lines.append(lines[index])
                index += 1
            if index < len(lines):
                # Closing fence found — try to parse the block as YAML.
                try:
                    parsed = yaml.safe_load("\n".join(body_lines))
                except yaml.YAMLError:
                    # Malformed yaml block — skip and continue scanning.
                    index += 1
                    continue
                # Only count blocks that carry a findings list.
                if isinstance(parsed, dict) and isinstance(
                    parsed.get("findings"), list
                ):
                    for entry in parsed["findings"]:
                        if (
                            isinstance(entry, dict)
                            and entry.get("severity", "").upper() == severity.upper()
                        ):
                            yaml_count += 1
        index += 1

    _warn_if_prose_diverges(raw_output, severity, yaml_count)
    return yaml_count


def count_unrecognized_severity_findings(
    raw_output: str, *, blocking_severity: str, nit_severity: str
) -> int:
    """Count findings whose severity matches neither recognized label, always scanning both the heading mechanism and the YAML-fallback mechanism unconditionally -- never gating one on the other's result -- since a mixed-format document could otherwise hide an unrecognized severity in whichever mechanism the two known severities did not use (deliberate, not a bug -- see the "Accepted risk" note in _mill/discussion.md).

    This function has no unknown-*class* responsibility -- that classification lives in
    extract_findings(), in the same single pass that builds the findings list, which is what
    prevents a classed-but-off-vocabulary-severity heading (e.g. "### [NIT:perf]") from being
    counted here as well as there.
    """
    unrecognized_count = 0

    # Markdown headings: same "### [<label>]" shape parse_blocking_count matches, generalized to capture any all-uppercase bracketed label (the severity-vocabulary convention every known severity follows -- BLOCKING, NIT, GAP, NOTE, MAJOR, MINOR, ...)
    # rather than one fixed severity, so every heading in the document is inspected.
    # A mixed-case bracket like "[Major]" is not a severity-shaped label at all and is deliberately not matched, case-sensitive like parse_blocking_count.
    # An optional class suffix (e.g. ":design") is matched and ignored -- this function judges a classed heading on its severity token alone.
    heading_pattern = re.compile(r"^###\s+\[([A-Z0-9-]+)(?::[a-z-]+)?\]\s+", re.MULTILINE)
    for match in heading_pattern.finditer(raw_output):
        label = match.group(1)
        if label != blocking_severity and label != nit_severity:
            unrecognized_count += 1

    # Fenced yaml findings blocks: reuse parse_blocking_count's own fenced-block-scanning approach,
    # but check every entry's severity against both known labels (case-insensitive) instead of one.
    blocking_upper = blocking_severity.upper()
    nit_upper = nit_severity.upper()
    lines = raw_output.splitlines()
    index = 0
    while index < len(lines):
        # Locate the opening fence of a yaml block.
        if lines[index].rstrip() == "```yaml":
            body_lines: list[str] = []
            index += 1
            # Collect lines until the closing fence; skip unclosed blocks silently.
            while index < len(lines) and lines[index].rstrip() != "```":
                body_lines.append(lines[index])
                index += 1
            if index < len(lines):
                # Closing fence found -- try to parse the block as YAML.
                try:
                    parsed = yaml.safe_load("\n".join(body_lines))
                except yaml.YAMLError:
                    # Malformed yaml block -- skip and continue scanning.
                    index += 1
                    continue
                # Only inspect blocks that carry a findings list.
                if isinstance(parsed, dict) and isinstance(
                    parsed.get("findings"), list
                ):
                    for entry in parsed["findings"]:
                        if not isinstance(entry, dict):
                            continue
                        entry_severity = entry.get("severity", "").upper()
                        if entry_severity != blocking_upper and entry_severity != nit_upper:
                            unrecognized_count += 1
        index += 1

    return unrecognized_count


# Matches a finding heading in the new class-aware syntax: "### [BLOCKING:design] <title>".
# The class group is optional -- "### [BLOCKING] <title>" has cls=None.
_RE_FINDING_HEADING = re.compile(
    r"^###\s+\[(?P<sev>[A-Z0-9-]+)(?::(?P<cls>[a-z-]+))?\]\s+(?P<title>.*)$",
    re.MULTILINE,
)

# The re-read signal for a heading-mechanism demotion: rewrite_demoted_findings inserts this line as
# the first field line of a demoted finding, and extract_findings looks for it to set demoted=True
# on a finding it re-reads from an already-written file.
_RE_DEMOTED_FROM_MARKER = re.compile(r"^\*\*Demoted-from:\*\*\s*BLOCKING\s*$", re.MULTILINE)


def _iter_yaml_block_findings(raw_text: str) -> list[dict]:
    """Return every `findings:` list entry from every fenced ```yaml block in raw_text, concatenated
    in block order.

    Mirrors parse_blocking_count's own fenced-block-scanning approach: a block that fails to parse as
    YAML, or that carries no `findings:` list, contributes nothing and is skipped silently -- the
    same tolerant behaviour every other yaml-fallback scan in this module already has.
    """
    entries: list[dict] = []
    lines = raw_text.splitlines()
    index = 0
    while index < len(lines):
        if lines[index].rstrip() == "```yaml":
            body_lines: list[str] = []
            index += 1
            while index < len(lines) and lines[index].rstrip() != "```":
                body_lines.append(lines[index])
                index += 1
            if index < len(lines):
                try:
                    parsed = yaml.safe_load("\n".join(body_lines))
                except yaml.YAMLError:
                    index += 1
                    continue
                if isinstance(parsed, dict) and isinstance(parsed.get("findings"), list):
                    entries.extend(e for e in parsed["findings"] if isinstance(e, dict))
        index += 1
    return entries


def extract_findings(raw_text: str) -> list[Finding]:
    """Extract every finding in raw_text exactly once, scanning both the markdown-heading mechanism
    and the fenced-`findings:`-YAML mechanism unconditionally.

    Neither scan is gated on the other's result, per the dual-mechanism-scan-preserved Shared
    Decision -- a mixed-format document (headings for one severity, a yaml block for the other) must
    not be able to hide a finding in whichever mechanism the known labels did not use.

    Severity classification: a severity equal to BLOCKING_SEVERITY or NIT_SEVERITY is kept as-is
    (uppercased first for the YAML path, since YAML authors are not held to the heading's uppercase
    convention);
    any other severity is forced to BLOCKING_SEVERITY, preserving the existing house rule that an
    off-vocabulary severity folds into the blocking bucket.

    Class classification: a class in RECOGNIZED_CLASSES is kept;
    a missing or unrecognised class becomes None (exempt from the ceiling) and emits one ASCII-only
    stderr warning naming the finding's title.

    Results are concatenated heading-scan-first, then deduplicated across mechanisms ONLY: a title
    produced by the yaml scan is dropped when and only when the heading scan already produced that
    same title.
    Two findings sharing a title within a single mechanism are both kept -- heading-vs-heading and
    yaml-vs-yaml alike -- because they are genuinely distinct findings, and collapsing them would
    silently drop one from both the returned list and the derived scalars.

    `demoted` is set to True when the finding already carries the marker rewrite_demoted_findings
    writes: a `**Demoted-from:** BLOCKING` field line for the heading mechanism, or a `demoted_from`
    entry field for the yaml mechanism.
    This function never applies the ceiling itself -- it only reports a demotion that is already
    recorded in the text, which is what lets the historical re-read sites in _review_plan.py agree
    with the envelope produced when the finding was first finalized.
    """
    matches = list(_RE_FINDING_HEADING.finditer(raw_text))
    heading_findings: list[Finding] = []
    heading_titles: set[str] = set()
    for i, m in enumerate(matches):
        title = m.group("title").strip()
        sev_token = m.group("sev")
        severity = (
            sev_token if sev_token in (BLOCKING_SEVERITY, NIT_SEVERITY) else BLOCKING_SEVERITY
        )
        cls_token = m.group("cls")
        cls = cls_token if cls_token in RECOGNIZED_CLASSES else None
        if cls is None:
            print(
                f"[_review_common] warning: finding has unknown or missing class -- {title}",
                file=sys.stderr,
            )
        # A finding's field lines run from the end of its own heading to the start of the next
        # heading (or end of text) -- that span is where a **Demoted-from:** marker would live.
        field_start = m.end()
        field_end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
        demoted = bool(_RE_DEMOTED_FROM_MARKER.search(raw_text[field_start:field_end]))
        heading_findings.append(Finding(severity=severity, cls=cls, title=title, demoted=demoted))
        heading_titles.add(title)

    yaml_findings: list[Finding] = []
    for entry in _iter_yaml_block_findings(raw_text):
        title = str(entry.get("title", "")).strip()
        # Cross-mechanism dedup only: a yaml title already seen from the heading scan is dropped.
        if not title or title in heading_titles:
            continue
        sev_raw = str(entry.get("severity", "")).upper()
        severity = sev_raw if sev_raw in (BLOCKING_SEVERITY, NIT_SEVERITY) else BLOCKING_SEVERITY
        cls_raw = entry.get("class")
        cls = cls_raw if cls_raw in RECOGNIZED_CLASSES else None
        if cls is None:
            print(
                f"[_review_common] warning: finding has unknown or missing class -- {title}",
                file=sys.stderr,
            )
        demoted = bool(entry.get("demoted_from"))
        yaml_findings.append(Finding(severity=severity, cls=cls, title=title, demoted=demoted))

    return heading_findings + yaml_findings


def apply_blocking_ceiling(
    findings: list[Finding], blocking_classes: frozenset[str]
) -> list[Finding]:
    """Demote every BLOCKING finding whose class falls outside blocking_classes to NIT, in place.

    A finding whose `cls` is None is never demoted -- an unclassifiable finding cannot be checked
    against `blocking_classes`, per the unknown-class-preserves-stated-severity Shared Decision.
    A finding already at NIT_SEVERITY is never promoted;
    the stage table is a ceiling, never a floor, per the ceiling-demotes-only Shared Decision.

    Mutates and returns `findings` for caller convenience (the list is also what
    rewrite_demoted_findings and the blocking/nit scalar counts read next).
    """
    for finding in findings:
        if (
            finding.severity == BLOCKING_SEVERITY
            and finding.cls is not None
            and finding.cls not in blocking_classes
        ):
            finding.severity = NIT_SEVERITY
            finding.demoted = True
    return findings


def _demote_yaml_entry_text(entry_text: str) -> str:
    """Rewrite one fenced-yaml `findings:` entry's raw text: `severity: BLOCKING` -> `severity: NIT`,
    plus an added `demoted_from: BLOCKING` field line.

    Operates as a line-level edit on `entry_text` (the entry's own lines, bullet included) rather
    than a yaml.safe_dump round-trip, which would reorder keys, restyle quoting, and drop comments
    across the whole fenced block.
    """
    lines = entry_text.splitlines(keepends=True)
    # The new field line's indentation matches this entry's other standalone field lines (e.g.
    # "  class: scope") -- found by scanning past the first (bullet) line for the first line that is
    # pure leading whitespace followed by content.
    field_indent = None
    for line in lines[1:]:
        m = re.match(r"^(\s+)\S", line)
        if m:
            field_indent = m.group(1)
            break
    if field_indent is None:
        # Single-line entry (bullet and first key on the same line) -- derive the field indent from
        # the bullet's own leading whitespace plus two spaces.
        bullet_m = re.match(r"^(\s*)-", lines[0])
        base = bullet_m.group(1) if bullet_m else ""
        field_indent = base + "  "

    out_lines: list[str] = []
    inserted = False
    for line in lines:
        rewritten = re.sub(r"(severity:\s*)BLOCKING\b", r"\1NIT", line, count=1, flags=re.IGNORECASE)
        out_lines.append(rewritten)
        if not inserted and re.search(r"severity:\s*BLOCKING\b", line, re.IGNORECASE):
            newline = "\n" if line.endswith("\n") else ""
            out_lines.append(f"{field_indent}demoted_from: BLOCKING{newline}")
            inserted = True
    return "".join(out_lines)


def _find_yaml_findings_entries(body_lines: list[str]) -> list[tuple[int, int]]:
    """Return (start, end) line-index spans (relative to body_lines) for every list item under a
    `findings:` key inside one fenced yaml block's body.

    `end` is exclusive. Returns an empty list when body_lines carries no `findings:` key.
    """
    findings_idx = None
    findings_indent = None
    for idx, line in enumerate(body_lines):
        m = re.match(r"^(\s*)findings:\s*$", line.rstrip("\n"))
        if m:
            findings_idx = idx
            findings_indent = len(m.group(1))
            break
    if findings_idx is None:
        return []

    entries: list[tuple[int, int]] = []
    entry_indent = None
    start = None
    i = findings_idx + 1
    while i < len(body_lines):
        line = body_lines[i].rstrip("\n")
        if line.strip() == "":
            i += 1
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent <= findings_indent:
            # Dedent back to findings:'s own level or shallower -- a sibling top-level key, or the
            # end of the mapping this findings: key lives in.
            break
        m = re.match(r"^(\s*)-\s", line)
        if m and (entry_indent is None or indent == entry_indent):
            if start is not None:
                entries.append((start, i))
            start = i
            entry_indent = indent
        i += 1
    if start is not None:
        entries.append((start, i))
    return entries


def _rewrite_demoted_headings(
    raw_text: str, demote_pairs: set[tuple[str, str | None]]
) -> str:
    """Rewrite every `### [BLOCKING:<cls>] <title>` heading whose (title, cls) pair is in
    demote_pairs to `### [NIT:<cls>] <title>`, inserting a `**Demoted-from:** BLOCKING` line as the
    first non-blank line after the heading (preserving a blank line between the heading and its
    first field line, when one is present).
    """
    lines = raw_text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _RE_FINDING_HEADING.match(line.rstrip("\n"))
        if m and m.group("sev") == BLOCKING_SEVERITY and m.group("cls") is not None:
            title = m.group("title").strip()
            cls = m.group("cls")
            if (title, cls) in demote_pairs:
                newline = "\n" if line.endswith("\n") else ""
                out.append(f"### [{NIT_SEVERITY}:{cls}] {m.group('title')}{newline}")
                i += 1
                if i < len(lines) and lines[i].strip() == "":
                    out.append(lines[i])
                    i += 1
                out.append("**Demoted-from:** BLOCKING\n")
                continue
        out.append(line)
        i += 1
    return "".join(out)


def _rewrite_demoted_yaml_entries(
    raw_text: str, demote_pairs: set[tuple[str, str | None]]
) -> str:
    """Rewrite every fenced `findings:` yaml entry whose (title, class) pair is in demote_pairs and
    whose severity is BLOCKING (case-insensitively), via _demote_yaml_entry_text.
    """
    lines = raw_text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].rstrip("\n") != "```yaml":
            out.append(lines[i])
            i += 1
            continue
        out.append(lines[i])
        i += 1
        block_start = i
        while i < len(lines) and lines[i].rstrip("\n") != "```":
            i += 1
        body_lines = lines[block_start:i]

        entries = _find_yaml_findings_entries(body_lines)
        cursor = 0
        for start, end in entries:
            out.extend(body_lines[cursor:start])
            entry_text = "".join(body_lines[start:end])
            try:
                parsed = yaml.safe_load(entry_text)
            except yaml.YAMLError:
                out.append(entry_text)
                cursor = end
                continue
            entry_dict = parsed[0] if isinstance(parsed, list) and parsed else None
            if (
                isinstance(entry_dict, dict)
                and str(entry_dict.get("severity", "")).upper() == BLOCKING_SEVERITY
                and (str(entry_dict.get("title", "")).strip(), entry_dict.get("class"))
                in demote_pairs
            ):
                out.append(_demote_yaml_entry_text(entry_text))
            else:
                out.append(entry_text)
            cursor = end
        out.extend(body_lines[cursor:])

        if i < len(lines):
            out.append(lines[i])  # closing fence
            i += 1
    return "".join(out)


def rewrite_demoted_findings(raw_text: str, findings: list[Finding]) -> str:
    """Rewrite raw_text so every demoted finding's on-disk representation agrees with `findings`.

    For each finding with `demoted is True`, keyed on the pair (title, cls) rather than on title
    alone, rewrites EVERY occurrence matching that pair -- not just the first -- across BOTH
    representations extract_findings reads: the markdown-heading mechanism and the fenced
    `findings:`-YAML mechanism.
    Rewriting both is required by the demotion-rewritten-into-review-file Shared Decision: a
    demotion visible in only one representation reproduces the exact file/envelope divergence that
    Decision exists to prevent.

    Matching on (title, cls) and rewriting every matching occurrence, rather than tracking a count of
    how many Finding entries share a title, is what makes duplicate titles safe: two
    `### [BLOCKING:scope] Missing test coverage` headings are both out-of-ceiling and both demoted,
    so both are rewritten, while a same-titled `### [BLOCKING:design]` heading does not match the
    (title, "scope") pair and is correctly left alone.

    Every finding reaching this function with `demoted is True` has a non-None `cls` -- only
    apply_blocking_ceiling sets `demoted`, and it never demotes a `cls is None` finding -- so no
    pair in demote_pairs has a None class component.

    Returns raw_text unchanged (byte-identical) when no finding is demoted.
    """
    demote_pairs = {(f.title, f.cls) for f in findings if f.demoted}
    if not demote_pairs:
        return raw_text
    raw_text = _rewrite_demoted_headings(raw_text, demote_pairs)
    raw_text = _rewrite_demoted_yaml_entries(raw_text, demote_pairs)
    return raw_text


def rewrite_verdict_token(raw_text: str, new_verdict: str) -> str:
    """Rewrite raw_text's two persisted verdict tokens (the fenced-yaml `verdict:` field and the
    `## Verdict` section's first line) to `new_verdict`, in place.

    `finalize_scope` is the sole caller: after the blocking-class ceiling recomputes the verdict,
    the on-disk artifact still shows the reviewer's original (pre-ceiling) verdict unless this
    helper runs. It is a no-op-preserving companion to `rewrite_demoted_findings` -- the caller
    (Card 7) gates whether this function is even invoked, so the "byte-identical when nothing needs
    to change" guarantee is enforced one level up rather than inside this function.

    Two independent in-place rewrites:
    1. Fenced-yaml `verdict:` field -- reuses `apply_actual_model_override`'s header-fence-finding
       scan verbatim as the location strategy: iterate ` ```yaml ` fence-delimited blocks, and the
       block whose body contains a line matching `^verdict:\\s*\\S` is the header block. That
       line's value is replaced in place, preserving its original trailing newline. If no
       yaml-fenced block has a `verdict:` line, this half is left unmodified -- defensive only,
       since `finalize_scope` only reaches this helper after `parse_verdict` already succeeded on
       the same `raw_text`.
    2. `## Verdict` section token -- per review-output.schema.md's `### \\`## Verdict\\`` contract
       (a required section with exactly two lines: the verdict token, then a one-sentence
       summary), scans for a line whose stripped content is exactly `## Verdict`, then finds the
       first subsequent non-blank line -- that line is the verdict token. Only that line's content
       is replaced, preserving its trailing newline; the following summary line is untouched. If
       no `## Verdict` heading is found, this half is left unmodified -- defensive only, since
       every template emits one.

    Returns:
        The rewritten text.
    """
    lines = raw_text.splitlines(keepends=True)

    # Locate the yaml header block (the fenced block whose body carries the `verdict:` line) and
    # rewrite that line's value in place.
    index = 0
    while index < len(lines):
        if lines[index].rstrip("\n") != "```yaml":
            index += 1
            continue
        block_end = index + 1
        while block_end < len(lines) and lines[block_end].rstrip("\n") != "```":
            block_end += 1
        block_body_start = index + 1
        for body_index in range(block_body_start, block_end):
            if re.match(r"^verdict:\s*\S", lines[body_index]):
                newline = "\n" if lines[body_index].endswith("\n") else ""
                lines[body_index] = f"verdict: {new_verdict}{newline}"
                break
        else:
            index = block_end + 1
            continue
        break

    # Locate the `## Verdict` section heading and rewrite its first non-blank line (the verdict
    # token itself), leaving the following one-sentence summary line untouched.
    heading_index = None
    for line_index, line in enumerate(lines):
        if line.rstrip("\n") == "## Verdict":
            heading_index = line_index
            break
    if heading_index is not None:
        for line_index in range(heading_index + 1, len(lines)):
            if lines[line_index].strip() == "":
                continue
            newline = "\n" if lines[line_index].endswith("\n") else ""
            lines[line_index] = f"{new_verdict}{newline}"
            break

    return "".join(lines)


def write_review_file(
    reviews_dir: Path,
    review_type: str,
    round_num: int,
    content: str,
    scope: str | None = None,
) -> Path:
    """Build a canonical review filename, create dirs, write content, return path.

    Filename rules:
    - Discussion / code / plan-holistic: <ts>-<type>-review-r<N>.md
    - Plan per-batch (scope is a batch name, e.g. '01-setup'): <ts>-plan-review-<scope>-r<N>.md
    - Plan holistic (scope == 'holistic'): <ts>-plan-review-r<N>.md

    Timestamp is UTC, formatted as YYYYMMDD-HHMMSS.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    if review_type in ("plan", "code") and scope is not None and scope != "holistic":
        filename = f"{ts}-{review_type}-review-{scope}-r{round_num}.md"
    else:
        filename = f"{ts}-{review_type}-review-r{round_num}.md"

    reviews_dir.mkdir(parents=True, exist_ok=True)
    out_path = reviews_dir / filename
    out_path.write_text(content, encoding="utf-8")
    return out_path.resolve()


# Horizontal whitespace only (`[ \t]`, not `\s`) between the colon and the value -- `\s` also matches `\n`, which would let this pattern bleed across a line boundary and swallow the line below when `reviewer_model:` has no value of its own (e.g.
# a malformed `reviewer_model:\n` followed by a non-blank line such as a closing yaml fence).
_RE_REVIEWER_MODEL_LINE = re.compile(r"^reviewer_model:[ \t]*\S.*$", re.MULTILINE)


def apply_actual_model_override(raw_text: str, actual_model: str | None) -> str:
    """
    Rewrite or inject the ``reviewer_model:`` line in a reviewer's raw output so the persisted
    review file records the model that actually ran the review, rather than the model the reviewer's
    own prompt-echoed text claims it is (which is unreliable in agent-mode dispatch -- see #644).

    Behavior:
    1. If `actual_model` is None, the caller has no override to apply --
    return `raw_text` completely unchanged (today's behavior).
    2. Otherwise, search for a line matching `reviewer_model:[ \\t]*\\S.*` (the line the
        review-prompt templates instruct the reviewer to echo, e.g. `<REVIEWER_MODEL>` in
        review-code-batch.md).
        If found, replace that line's value in place with `reviewer_model: {actual_model}`.
    3. If no such line is found (the reviewer omitted or malformed it), inject a new
        `reviewer_model: {actual_model}` line immediately after the opening ` ```yaml ` fence of the
        fenced block that carries the reviewer's `verdict:` line (the YAML header block). If no
        block carries a `verdict:` line, fall back to the first ` ```yaml ` fence in `raw_text`.
        If there is no ` ```yaml ` fence at all, there is nowhere sensible to anchor the injection,
            so `raw_text` is returned unchanged.

    Args:
        raw_text: Raw review output text, prior to verdict parsing or disk write.
        actual_model: The model that actually produced this review,
            or None to leave `raw_text` untouched.

    Returns:
        The (possibly rewritten) raw text.
    """
    if actual_model is None:
        return raw_text

    replacement_line = f"reviewer_model: {actual_model}"
    if _RE_REVIEWER_MODEL_LINE.search(raw_text):
        return _RE_REVIEWER_MODEL_LINE.sub(replacement_line, raw_text, count=1)

    # No well-formed reviewer_model line exists to rewrite.
    # Find the yaml fenced block that carries the reviewer's verdict -- that is the header block the new line belongs in -- and remember the first yaml fence encountered as a fallback anchor in case no block has a verdict.
    lines = raw_text.splitlines(keepends=True)
    first_fence_index: int | None = None
    header_fence_index: int | None = None
    index = 0
    while index < len(lines):
        if lines[index].rstrip("\n") != "```yaml":
            index += 1
            continue
        if first_fence_index is None:
            first_fence_index = index
        block_end = index + 1
        while block_end < len(lines) and lines[block_end].rstrip("\n") != "```":
            block_end += 1
        block_body = lines[index + 1 : block_end]
        if any(re.match(r"^verdict:\s*\S", line) for line in block_body):
            header_fence_index = index
            break
        index = block_end + 1

    fence_index = (
        header_fence_index if header_fence_index is not None else first_fence_index
    )
    if fence_index is None:
        # No yaml fence anywhere in the text -- nothing to anchor to.
        return raw_text

    # Insert the new line directly after the chosen opening fence.
    if not lines[fence_index].endswith("\n"):
        lines[fence_index] = lines[fence_index] + "\n"
    lines.insert(fence_index + 1, f"{replacement_line}\n")
    return "".join(lines)


def finalize_scope(
    reviews_dir: Path,
    review_type: str,
    round_n: int,
    raw_text: str,
    *,
    scope: str | None = None,
    actual_model: str | None = None,
    blocking_classes: frozenset[str] | None = None,
) -> dict:
    """Finalize a single review scope by parsing verdict, extracting findings, applying the
    blocking-class ceiling, and writing the review file.

    Runs, in order: apply_actual_model_override; parse_verdict(raw_text); extract_findings(raw_text);
    when `blocking_classes` is not None, apply_blocking_ceiling on the extracted findings and then
    rewrite_demoted_findings on raw_text, so the file on disk agrees with the (possibly demoted)
    findings before it is written; write_review_file with the (possibly-rewritten) text.
    `blocking_count` and `nit_count` are then derived by counting the post-ceiling findings list --
    the two independent regex sweeps (parse_blocking_count / count_unrecognized_severity_findings)
    are no longer used on this path, per the single-pass-finding-extraction Shared Decision.

    The returned `verdict` is recomputed from the post-ceiling findings, per the
    verdict-derives-from-surviving-blocking-count Shared Decision: when `parse_verdict` returned
    `NEED_CONTEXT`, that value passes through unchanged;
    otherwise the returned verdict is `REQUEST_CHANGES` when `blocking_count > 0`, else `APPROVE`.
    The reviewer's own `verdict:` line is advisory only past this point.

    Args:
        reviews_dir: Directory where review files are stored.
        review_type: Type of review ("discussion", "code", or "plan").
        round_n: Round number (integer).
        raw_text: Raw review output text to parse and write.
        scope: Optional scope name ("holistic" or batch name);
            if None defaults to "holistic".
        actual_model: The model that actually produced this review, used to correct an unreliable
            self-reported `reviewer_model:` line before parsing or writing;
            if None, `raw_text` is used unmodified.
        blocking_classes: The set of classes that stay BLOCKING at this stage (see
            resolve_blocking_classes). `None` means "apply no ceiling" -- every historical/test call
            site that does not pass it keeps today's counting behaviour untouched. Every production
            call site passes this explicitly.

    Returns:
        Dict with keys: scope, verdict, file, blocking_count, nit_count, findings (a list of
        Finding.to_dict() dicts, in extract_findings' concatenation order).

    Raises:
        ReviewError: from parse_verdict if verdict cannot be extracted.
    """
    raw_text = apply_actual_model_override(raw_text, actual_model)
    verdict = parse_verdict(raw_text)
    findings = extract_findings(raw_text)
    if blocking_classes is not None:
        findings = apply_blocking_ceiling(findings, blocking_classes)
        raw_text = rewrite_demoted_findings(raw_text, findings)
    review_path = write_review_file(
        reviews_dir, review_type, round_n, raw_text, scope=scope
    )
    blocking_count = sum(1 for f in findings if f.severity == BLOCKING_SEVERITY)
    nit_count = sum(1 for f in findings if f.severity == NIT_SEVERITY)

    if verdict != "NEED_CONTEXT":
        verdict = "REQUEST_CHANGES" if blocking_count > 0 else "APPROVE"

    effective_scope = scope if scope else "holistic"

    return {
        "scope": effective_scope,
        "verdict": verdict,
        "file": str(review_path),
        "blocking_count": blocking_count,
        "nit_count": nit_count,
        "findings": [f.to_dict() for f in findings],
    }


# ---------------------------------------------------------------------------
# Dispatch helpers and config loader (Step 8 additions)
# ---------------------------------------------------------------------------


def aggregate_verdict(sub_verdicts: list[str]) -> str:
    """Return the worst-case aggregate verdict across sub-verdicts.

    Rules:
    - Any NEED_CONTEXT propagates up to the aggregate (orchestrator must resolve the missing-context
        request before it can act on any REQUEST_CHANGES finding, so NEED_CONTEXT takes priority).
    - Any REQUEST_CHANGES or ERROR escalates the aggregate to REQUEST_CHANGES.
    - All APPROVE → APPROVE.
    - ERROR appears only inside reviews[] entries;
        aggregate is never ERROR.
    """
    if "NEED_CONTEXT" in sub_verdicts:
        return "NEED_CONTEXT"
    for v in sub_verdicts:
        if v in ("REQUEST_CHANGES", "ERROR"):
            return "REQUEST_CHANGES"
    return "APPROVE"


# Per-stage default blocking_classes, used by resolve_blocking_classes when a hub's mill-config.yaml
# has not (yet) set roles.<role>.<scope>.blocking_classes.
# Keyed by role name (see _REVIEW_TYPE_TO_ROLE below for the review_type -> role mapping).
DEFAULT_BLOCKING_CLASSES: dict[str, frozenset[str]] = {
    "discussion-review": frozenset({"design"}),
    "plan-review": frozenset({"design", "scope"}),
    "code-review": frozenset({"design", "scope", "decision", "consistency"}),
}

_REVIEW_TYPE_TO_ROLE = {
    "discussion": "discussion-review",
    "plan": "plan-review",
    "code": "code-review",
}


def resolve_blocking_classes(cfg: dict, review_type: str, scope: str | None) -> frozenset[str]:
    """Return the set of classes that stay BLOCKING at this review stage.

    Reads `cfg["roles"][<role>][<scope_key>]["blocking_classes"]` defensively -- every level in that
    path may be missing or None -- where `<role>` is `review_type` mapped through
    _REVIEW_TYPE_TO_ROLE ("discussion" -> "discussion-review", "plan" -> "plan-review", "code" ->
    "code-review") and `<scope_key>` is "holistic" when `scope` is None or the literal "holistic",
    else "batch".

    When the config key is present and is a non-empty list of strings, returns
    `frozenset(value)`. Otherwise falls back to DEFAULT_BLOCKING_CLASSES[role] -- a hub whose
    mill-config.yaml has not been updated with `blocking_classes:` degrades to the documented default
    rather than raising.

    Never raises. An unrecognised `review_type` (not one of "discussion", "plan", "code") falls back
    to `frozenset(RECOGNIZED_CLASSES)`, so an unknown caller can never accidentally demote every
    finding it produces.
    """
    role = _REVIEW_TYPE_TO_ROLE.get(review_type)
    if role is None:
        return frozenset(RECOGNIZED_CLASSES)

    scope_key = "holistic" if scope is None or scope == "holistic" else "batch"

    roles_cfg = cfg.get("roles") if isinstance(cfg, dict) else None
    role_cfg = roles_cfg.get(role) if isinstance(roles_cfg, dict) else None
    scope_cfg = role_cfg.get(scope_key) if isinstance(role_cfg, dict) else None
    value = scope_cfg.get("blocking_classes") if isinstance(scope_cfg, dict) else None

    if isinstance(value, list) and value:
        return frozenset(value)
    return DEFAULT_BLOCKING_CLASSES[role]


def load_config(hub_root: Path, mill_dir: Path) -> dict:
    """Load mill config, delegating the core template/repo/local merge to ``_config.load_config``
    and layering two review-specific behaviors on top.

    ``_config.load_config`` owns the merge order (plugin template -> hub/repo layer -> local stub ->
    real config -> env overrides), including its 2026-05-31 worktree-template cache-lag augmentation
    (source-tree template keys not yet landed in the installed plugin cache are folded into the
    unknown-key check's baseline before the delegate's own unknown-key warning fires).
    Delegating here means this function automatically inherits that fix and any future fix to the
    shared merge logic, instead of re-diverging with its own copy.

    On top of the delegate this wrapper adds:
    1. Missing-source strictness: raises ``ReviewError`` when neither the plugin template nor any
        repo-layer mill-config.yaml exists.
        This must be checked independently of the delegate's return value, because
            ``_config.load_config`` never raises and returns ``{}`` both when nothing is found and
            when a legitimately-present source is empty.
    2. A stale-``review:``-key warning: peeks at ``mill_dir / config.local.yaml`` (read-only,
        alongside the delegate's own internal read of the same file) and warns to stderr when it
        carries an orphaned top-level ``review:`` block that should have been renamed to ``roles:``.

    Args:
        hub_root: Absolute path to the hub directory.
        mill_dir: Absolute path to the .millhouse directory.

    Returns:
        Merged configuration dict, as produced by ``_config.load_config``.

    Raises:
        ReviewError: If neither the plugin template nor a repo-layer mill-config.yaml source exists.
    """
    worktree_root = mill_dir.parent

    # Missing-source check, independent of the delegate's return value: an empty dict from the delegate does not distinguish "nothing found" from "a source was found but happened to be empty".
    template_path = resolve_plugin_template_path("mill-config.yaml")
    mill_cfg_path = resolve_repo_config_path(hub_root, worktree_root)
    if not template_path.exists() and mill_cfg_path is None:
        raise ReviewError(
            f"Missing config: searched plugin template at {template_path} "
            f"and mill-config.yaml in hub, main worktree, or task worktree"
        )

    # Delegate the core template/repo/local merge (including env overrides, env interpolation, and the dispatch back-compat shim) to the shared implementation.
    cfg = _core_load_config(hub_root, worktree_root)

    # Stale-review-key warning: the delegate reads config.local.yaml internally but does not expose it, so this is re-derived here as a read-only peek at the same file.
    local_path = mill_dir / "config.local.yaml"
    if local_path.exists():
        with local_path.open(encoding="utf-8") as fh:
            local_cfg = yaml.safe_load(fh) or {}
        stale_review = local_cfg.get("review")
        if stale_review:
            orphaned = sorted(stale_review.keys())
            print(
                f"[load_config] warning: {local_path} contains stale 'review:' keys "
                f"(orphaned: {orphaned}); remove them or update to 'roles:'",
                file=sys.stderr,
            )

    return cfg
