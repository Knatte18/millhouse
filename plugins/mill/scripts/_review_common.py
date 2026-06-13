"""
Shared helpers, regex constants, data classes, and exceptions used by
every Layer 02 review backend.

No dependencies on any other Layer 02 file. Import this from
_review_discussion.py, _review_plan.py, _review_code.py, and the API
scripts.

Public API:
    ReviewError          — raised by the backend on config/slug/round errors
    ReviewerOverstepError — raised by worktree_snapshot_guard when a reviewer mutates HEAD or working tree
    ReviewResult         — dataclass; serialised to the CLI's stdout JSON
    RE_SIMPLE            — regex matching simple review filenames
    RE_BATCH             — regex matching plan-batch review filenames
    find_active_slug()   — branch-based slug detection with _mill/*.active glob fallback
    load_task_title()    — delegate to _marker.task_data for task_title; fall back to slug on MarkerError
    worktree_snapshot_guard() — context manager; snapshot guard wrapping each backend run()
    read_constraints_md()— read CONSTRAINTS.md, empty string if absent
    resolve_path()       — locate a path inside the active hub (where task/ lives) from a config template
    discover_round()     — determine next review round number per (review_type, scope)
    detect_resume_round() — return highest per-batch-only round (no holistic yet), or None
    bulk_files()         — concatenate file contents with FILE delimiters
    bulk_files_with_diff() — like bulk_files but substitutes git diff output for small-diff files
    build_manifest_section() — return a `## Files included` markdown block listing every bulked file
    build_deletes_section() — return a `## Intentionally deleted` markdown block listing deleted tokens
    parse_missing_context() — extract path strings from a `## Missing context` section in review text
    build_reattached_section() — return a `## Re-attached files` block with inlined file contents for NEED_CONTEXT retry
    build_tool_rule()    — mode-specific <TOOL_RULE> block (bulk / tool-use)
    render_prompt()      — render a template from plugins/mill/templates/
    parse_verdict()      — extract APPROVE/REQUEST_CHANGES from fenced yaml block
    parse_blocking_count() — count "### [<severity>]" headings in review output
    write_review_file()  — write a review file with a canonical timestamp name
    aggregate_verdict()  — worst-case verdict across a list of sub-verdicts
    load_config()        — load mill-config.yaml + optional config.local.yaml
    parse_batch_refs()   — extract Context/Edits/Creates paths from a batch file (case-insensitive none filter)
    compute_creates_union() — union of all Creates: tokens across every batch in a plan_dir
    compute_deletes_union() — union of all Deletes: tokens across every batch in a plan_dir
    resolve_ref_paths()  — resolve raw ref strings against project_root; hard-fails on missing paths not in creates_union or deletes_union
    resolve_existing_paths() — resolve raw paths and return only those that already exist on disk (silent drop, no creates_union check)
    _load_root_from_overview() — read root: field from overview's fenced-yaml block
    _check_large_prompt()    — check if prompt exceeds large_prompt threshold; return (is_over_threshold, estimated_ktok)
    resolve_large_prompt_timeout() — return large_prompt.timeout when prompt is over threshold and key is set
    maybe_switch_spec_for_large_prompt() — check prompt size; return (spec, reviewer_name), possibly overridden for large prompts
"""
from __future__ import annotations

import copy
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
from _config import (
    _apply_dispatch_shim,
    apply_env_overrides,
    warn_unknown_keys,
    resolve_plugin_template_path,
)

# ---------------------------------------------------------------------------
# Module-level regex constants
# ---------------------------------------------------------------------------

# Matches simple (non-batch) review filenames:
#   20260418-001200-discussion-review-r1.md
#   20260418-143300-code-review-r2.md
#   20260418-143300-plan-review-r1.md   (plan holistic)
RE_SIMPLE = re.compile(
    r"^\d{8}-\d{6}-(?P<type>discussion|code|plan)-review-r(?P<n>\d+)\.md$"
)

# Matches plan / code per-batch review filenames:
#   20260418-143300-plan-review-01-setup-r1.md
#   20260418-143300-code-review-foundation-r1.md
# RE_SIMPLE is checked first; a file matching RE_SIMPLE is excluded from
# RE_BATCH matching (prevents holistic files from being mis-identified).
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

    Carries the before/after HEAD SHA and the unfiltered git status --porcelain
    diff for operator inspection. The guard does not auto-rollback; the operator
    resets manually after investigating.
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
    """Snapshot git state before/after the with-block; raise on any change.

    Captures `git rev-parse HEAD` and `git status --porcelain` on entry,
    re-captures on exit, and raises ``ReviewerOverstepError`` if either the
    HEAD SHA or the porcelain diff (filtered by ``expected_paths``) differs.

    ``expected_paths`` is a list of substring patterns that filter the
    porcelain diff before comparison. A porcelain line is filtered when its
    path field (with backslashes normalised to forward slashes) contains
    ANY entry in ``expected_paths`` as a substring. HEAD-SHA changes are
    NEVER filtered.

    A fast-forward HEAD advance (where the new HEAD is a descendant of the old
    HEAD) is tolerated if no new working-tree dirt is introduced and no dirt
    is removed outside of a fast-forward commit. A stderr warning is emitted
    when a fast-forward is detected.

    If the wrapped block raises AND state was mutated, ``ReviewerOverstepError`` takes priority and chains the inner exception via ``__cause__``; if state was unchanged the inner exception is re-raised unchanged.
    If the post-snapshot capture itself raises (e.g. ``_capture_head_sha`` propagating a ``ReviewError`` from a broken git invocation), that error propagates and the inner exception is NOT chained -- the capture failure indicates the snapshot is untrustworthy, so the typed ``ReviewerOverstepError`` cannot be raised safely. This is an intentional trade-off; the inner exception, if any, is visible in the traceback frames above the capture call.
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
    fast_forward = head_changed and _pygit2_util.is_ancestor(project_root, before_sha, after_sha)

    should_raise = (
        (added)  # New working-tree dirt added
        or (head_changed and not fast_forward)  # HEAD rewritten/reset to non-descendant
        or (removed and not fast_forward)  # Dirt removed without a fast-forward commit
    )

    if should_raise:
        diff = _porcelain_diff(before_filtered, after_filtered)
        raise ReviewerOverstepError(before_sha, after_sha, diff) from inner_exc

    if fast_forward and not added and not (removed and not fast_forward):
        print(
            f"[_review_common] HEAD advanced {before_sha[:8]} -> {after_sha[:8]} "
            f"during review window (fast-forward; allowed)",
            file=sys.stderr,
        )

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
    Renames have ' -> ' between old and new path; both are checked against expected_paths.
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

@dataclass
class ReviewResult:
    """Serialisable result returned by every review backend's run() function."""

    type: str                              # "discussion" | "plan" | "code"
    round: int
    verdict: str                           # "APPROVE" | "REQUEST_CHANGES"
    reviews: list[dict] = field(default_factory=list)
    blocking_count: int = 0
    nit_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "round": self.round,
            "verdict": self.verdict,
            "blocking_count": self.blocking_count,
            "nit_count": self.nit_count,
            "reviews": self.reviews,
        }


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def find_active_slug(git_root: Path, wiki_path: Path, cfg: dict) -> str:
    """Detect active slug via branch name, falling back to _mill/*.active glob.

    Raises ReviewError (wrapping MarkerError or glob-fallback errors).
    """
    try:
        return _marker.slug_from_branch(git_root, wiki_path, cfg)
    except _marker.MarkerError as exc:
        try:
            matches = list((git_root / "_mill").glob("*.active"))
        except OSError:
            matches = []
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
    """Delegate to _marker.task_data for task_title; fall back to slug on MarkerError."""
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
    """Resolve a config path template to an absolute path inside the active worktree.

    Computes the container, git_root, and cfg internally:
      - git_root via _paths.resolve_git_root()
      - container via _paths.resolve_container_path(git_root)
      - hub_dir via _paths.resolve_hub_path() (the hub where mill-config.yaml
        lives; equals git_root when hub_relative_path == ".")
      - cfg via load_config(hub_dir, hub_dir / ".millhouse")

    cfg is sourced from the hub's own .millhouse/, not from git_root/.millhouse/,
    because mill-claim writes hub_relative_path only at the hub (it does not
    bootstrap a stub at git_root/.millhouse/ the way mill-spawn does).

    Returns active_worktree / path_tmpl after substituting any "<SLUG>" token.
    Task artefacts (_mill/plan/, _mill/reviews/, _mill/discussion.md, etc.)
    always live at the worktree root, NOT inside the hub subdirectory — so
    the base for path resolution is the worktree root, regardless of
    hub_relative_path.

    Raises:
        _paths.ActiveWorktreeNotFound | _paths.ActiveWorktreeSlugMismatch:
            propagated from the inner resolve_active_worktree call.
    """
    git_root = _paths.resolve_git_root()
    container_path = _paths.resolve_container_path(git_root)
    hub_dir = _paths.resolve_hub_path()
    cfg = load_config(hub_dir, hub_dir / ".millhouse")
    active_wt = _paths.resolve_active_worktree(
        container_path, slug, cfg=cfg, git_root=git_root,
    )
    resolved_tmpl = path_tmpl.replace("<SLUG>", slug)
    return _paths.resolve_task_path(active_wt, resolved_tmpl)


def discover_round(reviews_dir: Path, review_type: str, scope: str) -> int:
    """Scan reviews_dir and return the next round number for (review_type, scope).

    ``scope`` is either ``"holistic"`` (for discussion reviews and plan/code
    holistic reviews) or a batch name string (for per-batch plan/code reviews).

    If ``reviews_dir`` does not exist, return 1.

    Scope semantics:
    - ``scope == "holistic"``: count files where RE_SIMPLE matches AND
      ``m.group("type") == review_type``. RE_BATCH matches are ignored entirely.
    - ``scope == <batch_name>``: count files where RE_SIMPLE does NOT match AND
      RE_BATCH matches AND ``m.group("type") == review_type`` AND
      ``m.group("batch") == scope``.

    RE_SIMPLE is checked before RE_BATCH for every file, matching the existing
    convention that prevents a plan-holistic file (e.g. …-plan-review-r1.md)
    from being mis-identified as a batch review via RE_BATCH.

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

    Returns the highest round number ``N`` such that at least one per-batch
    review file exists for round ``N`` AND no holistic review file exists for
    round ``N``. Returns ``None`` when no such round exists (either all rounds
    have a holistic file, no per-batch files exist at all, or ``reviews_dir``
    does not exist).

    Uses RE_SIMPLE (checked first per convention) to identify holistic files
    and RE_BATCH to identify per-batch files, both filtered by ``review_type``.

    Consumed by ``_review_plan.run`` to detect a partially-complete run where
    per-batch reviews are done but the holistic pass has not yet fired.
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
# Header line: - **Context:** <inline>  (inline may be empty for multi-line bullet form).
_RE_REFS_HEADER = re.compile(
    r"^-\s*\*\*(Context|Edits|Creates|Deletes):\*\*(?P<inline>.*)$"
)
# Sub-bullet under a multi-line header (leading whitespace + dash).
_RE_REFS_SUB = re.compile(r"^\s+-\s*(.+)$")


def parse_batch_refs(batch_path: Path) -> list[str]:
    """Extract raw path strings from a batch file's Context/Edits/Creates/Deletes lines.

    Handles the single-line form (- **Context:** `a`, `b`) and the multi-line
    bullet form (- **Context:**\\n  - `a`\\n  - `b`). Filters tokens whose
    lowercase form equals ``'none'`` (case-insensitive). Returns a
    deduplicated list preserving first-seen order. Used by both plan review
    and code review to build the source-file bulk.
    """
    text = batch_path.read_text(encoding="utf-8")
    seen: dict[str, None] = {}
    lines = text.splitlines()

    i = 0
    while i < len(lines):
        m = _RE_REFS_HEADER.match(lines[i])
        if m:
            inline = m.group("inline").strip()
            if inline:
                backtick_tokens = re.findall(r"`([^`]+)`", inline)
                tokens = backtick_tokens if backtick_tokens else [
                    t.strip() for t in inline.split(",") if t.strip()
                ]
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
                    seen[t] = None
        i += 1

    return list(seen.keys())


def compute_creates_union(plan_dir: Path) -> set[str]:
    """Return the union of all Creates: tokens across every batch in plan_dir.

    Iterates every ``??-*.md`` file under ``plan_dir`` except
    ``00-overview.md``, extracts only the ``Creates:`` lines, and returns
    a flat set of raw token strings (NOT resolved Paths). Filters tokens
    whose lowercase form equals ``'none'`` (case-insensitive). Returns an
    empty set if ``plan_dir`` doesn't exist or contains no batch files.
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
                    tokens = backtick_tokens if backtick_tokens else [
                        t.strip() for t in inline.split(",") if t.strip()
                    ]
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

    Iterates every ``??-*.md`` file under ``plan_dir`` except
    ``00-overview.md``, extracts only the ``Deletes:`` lines, and returns
    a flat set of raw token strings (NOT resolved Paths). Filters tokens
    whose lowercase form equals ``'none'`` (case-insensitive). Returns an
    empty set if ``plan_dir`` doesn't exist or contains no batch files.
    """
    if not plan_dir.exists():
        return set()
    deletes: set[str] = set()
    for batch_path in sorted(plan_dir.glob("??-*.md")):
        if batch_path.name == "00-overview.md":
            continue
        text = batch_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            m = _RE_REFS_HEADER.match(lines[i])
            if m and m.group(1) == "Deletes":
                inline = m.group("inline").strip()
                if inline:
                    backtick_tokens = re.findall(r"`([^`]+)`", inline)
                    tokens = backtick_tokens if backtick_tokens else [
                        t.strip() for t in inline.split(",") if t.strip()
                    ]
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
) -> list[Path]:
    """Resolve batch-reference path strings to absolute ``Path``s.

    ``root`` is the optional filesystem sub-path declared in the plan
    overview's frontmatter ``root:`` field. When present every raw path
    is resolved under ``project_root / root``; otherwise directly under
    ``project_root``.

    Resolution order (first match wins):
    1. wiki/ prefix routes through wiki_root (unchanged).
    2. Candidate path under project_root (unchanged).
    3. Candidate path under git_root (when provided).
    4. creates_union/deletes_union suppression (unchanged).
    5. Hard-fail ReviewError (unchanged).

    Keyword args:
        creates_union: Set of raw token strings extracted from ``Creates:``
            lines across all batches. A path not on disk but present in
            ``creates_union`` is silently skipped — the file will exist
            after the creating batch runs (#60).
        deletes_union: Set of raw token strings extracted from ``Deletes:``
            lines across all batches. A path not on disk but present in
            ``deletes_union`` is silently skipped — the file has already
            been deleted by a prior batch. Paths still on disk that appear
            in ``deletes_union`` are resolved normally and included.
        wiki_root: When provided, raw paths starting with ``wiki/`` are
            resolved against ``wiki_root`` instead of ``project_root`` (#43).
        git_root: When provided, paths not found under project_root are
            tried under git_root as a fallback before suppression/hard-fail.
        caller_label: Prefix used in ``ReviewError`` messages. Defaults to
            the function name.

    Raises ``ReviewError`` when a candidate path is not on disk AND not in
    either ``creates_union`` or ``deletes_union`` — hard-fail replaces the
    old silent-skip + warning behaviour (#41).
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
            candidate = wiki_root / raw[len("wiki/"):]
        elif root:
            candidate = project_root / root / raw
        else:
            candidate = project_root / raw
        # Hit on disk.
        if candidate.exists():
            resolved.append(candidate)
            continue
        # Git-root fallback (only for non-wiki paths).
        if not raw.startswith("wiki/") and git_root is not None:
            # When the worktree cwd is itself the `root` sub-path, project_root
            # already ends with `root`, so project_root / root / raw doubles it.
            # Try git_root / root / raw first so `root` is joined onto the repo
            # root exactly once — matching how the plan was validated.
            gr_candidates = [git_root / root / raw] if root else []
            gr_candidates.append(git_root / raw)
            gr_hit = next((c for c in gr_candidates if c.exists()), None)
            if gr_hit is not None:
                resolved.append(gr_hit)
                continue
        # Suppression via creates_union or deletes_union.
        if raw in creates or raw in deletes:
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

    Mirrors resolve_ref_paths's standard-vs-wiki routing (wiki/ prefix
    routes through wiki_root; otherwise project_root + root) plus optional
    git_root fallback. Unlike resolve_ref_paths, missing paths and routing
    failures are silently dropped — no warning, no error, no creates_union
    check. Used to expand the bulk with cross-batch ancestor creates that
    already exist; missing creates are not an error here, they just aren't
    included.

    Resolution order (first match wins):
    1. wiki/ prefix routes through wiki_root (unchanged).
    2. Candidate path under project_root (unchanged).
    3. Candidate path under git_root (when provided).
    4. Silent drop (no raise).

    Keyword args:
        wiki_root: When provided, raw paths starting with ``wiki/`` are
            resolved against ``wiki_root`` instead of ``project_root``.
        git_root: When provided, paths not found under project_root are
            tried under git_root as a fallback before silent drop.
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
            candidate = wiki_root / raw[len("wiki/"):]
        elif root:
            candidate = project_root / root / raw
        else:
            candidate = project_root / raw
        if candidate.exists():
            result.append(candidate)
            continue
        # Git-root fallback (only for non-wiki paths).
        if not raw.startswith("wiki/") and git_root is not None:
            gr_candidate = git_root / raw
            if gr_candidate.exists():
                result.append(gr_candidate)
                continue
    return result


def _load_root_from_overview(overview_path: Path) -> str | None:
    """Read the `root:` field from the overview's top fenced-yaml block.

    v2 plan overviews use fenced ```yaml``` frontmatter (per the
    project markdown convention; `---` is reserved for SKILL.md). This
    parser locates the first ```yaml``` block and reads `root:` from
    it. Returns the root string if present and truthy, else None.
    Any structural problem (no block, unterminated, bad yaml, absent
    key) silently yields None — the review surface degrades to
    resolving paths against project_root directly, which is the right
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

    For .ipynb files: reads as JSON, extracts cell source for 'code' and
    'markdown' cell types, joins sources with blank lines between cells.
    For other extensions: returns standard UTF-8 text read.

    On JSON parse error for .ipynb: prints warning to stderr and returns
    empty string so the file still appears in bulk output as an empty section.

    If p is a directory: prints warning to stderr and returns empty string.
    """
    if p.is_dir():
        print(f"[_read_for_bulk] warning: {p} is a directory, skipping", file=sys.stderr)
        return ""

    if p.suffix == ".ipynb":
        try:
            content = p.read_text(encoding="utf-8")
            notebook = json.loads(content)
        except json.JSONDecodeError as exc:
            print(f"[_read_for_bulk] warning: {p} JSON parse error: {exc}", file=sys.stderr)
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
            print(f"[bulk_files] warning: {p} not found or not readable, skipping", file=sys.stderr)
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

    For each file: if the diff from start_sha to HEAD is smaller than
    threshold * file_content_size, include the diff instead of full content.
    Files with no diff (unchanged between start_sha and HEAD) are included
    at full content so the reviewer has all context.
    """
    parts: list[str] = []
    for p in file_paths:
        try:
            file_content = _read_for_bulk(p)
        except (FileNotFoundError, PermissionError):
            print(f"[bulk_files_with_diff] warning: {p} not found or not readable, skipping", file=sys.stderr)
            continue

        try:
            rel_path = p.relative_to(project_root).as_posix()
        except ValueError:
            rel_path = str(p)

        result = _subprocess_util.run(
            ["git", "-C", str(project_root), "diff", f"{start_sha}..HEAD", "--", rel_path],
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
            parts.append(f"--- DIFF: {p} (from {start_sha[:8]}) ---\n{diff_text}\n--- END DIFF: {p} ---")
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

    The manifest is the FIRST thing the reviewer reads inside the
    artefact section. Its job is to remove the long-context
    haystack effect: the reviewer scans this list, then can answer
    "is file X provided?" in O(1) instead of scanning a 200k-char
    bulk for the matching `--- FILE: X ---` delimiter.
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

    Falls back to raw unchanged when markers are absent (e.g. test stubs).
    """
    begin = raw.find(_REVIEW_BEGIN)
    if begin == -1:
        return raw
    end = raw.find(_REVIEW_END, begin + len(_REVIEW_BEGIN))
    if end == -1:
        return raw
    return raw[begin + len(_REVIEW_BEGIN):end].strip()


def parse_missing_context(review_text: str) -> list[str]:
    """Extract path strings from a `## Missing context` section.

    The reviewer's NEED_CONTEXT output uses the convention:

        ## Missing context

        - `path/a` — reason text
        - `path/b` — reason text

    Returns the list of raw path tokens (NOT resolved Paths). Empty
    list if the heading is absent or no bullet matches the expected
    shape. Multi-line bullets are not supported — paths must appear
    backtick-wrapped on their own bullet line.
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
    """Return a `## Re-attached files (you said these were missing)` block
    with the listed files inlined via bulk_files.

    Used by the NEED_CONTEXT resume retry: the missing-context paths
    from the prior round are re-attached at the top of the new prompt
    so the reviewer cannot claim absence again without contradicting
    itself. The section is appended to the existing artefact section.
    """
    if not file_paths:
        return ""
    return (
        "## Re-attached files (you said these were missing)\n\n"
        + bulk_files(file_paths)
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


def build_tool_rule(mode: str) -> str:
    """Return the <TOOL_RULE> block for a reviewer's MODE.

    Templates embed this as the top-of-prompt directive. In bulk mode the
    reviewer is told all content is inline; in tool-use mode it is granted
    Read/Grep/Glob. Write, Edit, and shell access are forbidden in both modes
    — the backend owns file writes and git.
    """
    if mode == "bulk":
        return _TOOL_RULE_BULK
    if mode == "tool-use":
        return _TOOL_RULE_TOOL_USE
    raise ValueError(f"Unknown reviewer mode: {mode!r} (expected 'bulk' or 'tool-use')")


def _check_large_prompt(
    prompt_text: str,
    cfg: dict,
    role: str,
    scope: str,
) -> tuple[bool, int]:
    """Check if prompt exceeds large_prompt threshold.

    Returns (is_over_threshold, estimated_ktok) where estimated_ktok is computed as
    len(prompt_text) // 4000 and threshold_ktok is read from
    cfg["roles"][role][scope]["large_prompt"]["threshold_ktok"] (default 100).
    """
    large_prompt_cfg = cfg.get("roles", {}).get(role, {}).get(scope, {}).get("large_prompt")
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
    """Return large_prompt.timeout when prompt is over threshold and key is set, else default_timeout.

    Uses _check_large_prompt to compute size check; returns the override value from
    cfg["roles"][role][scope]["large_prompt"]["timeout"] if the prompt exceeds the
    threshold and the timeout key is set, otherwise returns default_timeout.
    """
    is_over_threshold, _ = _check_large_prompt(prompt_text, cfg, role, scope)
    if not is_over_threshold:
        return default_timeout
    large_prompt_cfg = cfg.get("roles", {}).get(role, {}).get(scope, {}).get("large_prompt")
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
    is_over_threshold, estimated_ktok = _check_large_prompt(prompt_text, cfg, role, scope)
    large_prompt_cfg = cfg.get("roles", {}).get(role, {}).get(scope, {}).get("large_prompt")
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

    Auto-uppercases keyword-argument keys so callers can use idiomatic
    Python kwarg style (e.g. artefact_path="..." becomes ARTEFACT_PATH).

    Template path:
        <scripts_dir>/../templates/<template_name>.md

    Raises FileNotFoundError if the template is absent.
    Lets KeyError from _render.render() propagate unwrapped — a missing token
    is a programming error, not a user error.
    """
    templates_dir = Path(__file__).parent.parent / "templates"
    template_path = templates_dir / f"{template_name}.md"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    uppercased = {k.upper(): str(v) for k, v in tokens.items()}
    return _render.render(template_path, uppercased)


def parse_verdict(raw_output: str) -> str:
    """Extract a valid verdict value from a fenced yaml block, or unfenced fallback.

    Scans raw_output for the first fenced ```yaml block (on its own line,
    possibly with trailing whitespace). Extracts the 'verdict:' field from
    inside the block (between the opening ```yaml and closing ``` fences).

    If no fenced block is found, attempts a fallback: scans lines for an
    unfenced 'verdict: <VALUE>' line (allowing leading whitespace; strips quotes).
    If <VALUE> is one of the valid verdicts, returns it.

    Valid verdict values:
    - 'APPROVE'          — any review type
    - 'REQUEST_CHANGES'  — plan and code review
    - 'GAPS_FOUND'       — discussion review (v1 convention; a missing
                           criterion is not a must-fix defect)
    - 'NEED_CONTEXT'     — plan and code review only; reviewer cannot
                           evaluate without source files that were not
                           included in the bulk. Orchestrator responds by
                           re-firing with `--extra-file` plus a notify +
                           self-report entry.

    Raises ReviewError if:
    - No ```yaml opening fence is found AND no unfenced verdict line is found.
    - The yaml block is not closed by a ``` line.
    - The 'verdict:' field is absent from the block.
    - The verdict value is not one of the four above.

    The first ~400 chars of raw_output are included in error messages for
    debuggability.
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
        for i, line in enumerate(lines[open_idx + 1:], start=open_idx + 1):
            if line.rstrip() == "```":
                close_idx = i
                break

        if close_idx is None:
            raise ReviewError(
                f"Could not parse verdict: ```yaml block not closed.\n"
                f"Raw output preview:\n{preview}"
            )

        # Scan block body for verdict: field.
        for line in lines[open_idx + 1:close_idx]:
            stripped = line.strip()
            if stripped.startswith("verdict:"):
                value = stripped[len("verdict:"):].strip().strip('"').strip("'")
                if value in ("APPROVE", "REQUEST_CHANGES", "GAPS_FOUND", "NEED_CONTEXT"):
                    return value
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
            value = stripped[len("verdict:"):].strip().strip('"').strip("'")
            if value in ("APPROVE", "REQUEST_CHANGES", "GAPS_FOUND", "NEED_CONTEXT"):
                return value

    raise ReviewError(
        f"Could not parse verdict: no ```yaml block found and no unfenced verdict line found.\n"
        f"Raw output preview:\n{preview}"
    )


def _warn_if_prose_diverges(raw_output: str, severity: str, heading_count: int) -> None:
    _WORD_TO_INT = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }
    pattern = re.compile(
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+" + re.escape(severity),
        re.IGNORECASE,
    )
    matches = pattern.findall(raw_output)
    if not matches:
        return
    raw_val = matches[0]
    prose_count = int(raw_val) if raw_val.isdigit() else _WORD_TO_INT.get(raw_val.lower(), -1)
    if prose_count != heading_count:
        print(
            f"[_review_common] warning: parse_blocking_count heading count {heading_count} "
            f"diverges from prose count {prose_count} (severity={severity}) "
            f"— check review file for missing heading.",
            file=sys.stderr,
        )


def parse_blocking_count(raw_output: str, *, severity: str) -> int:
    """Count "### [<severity>]" ATX headings in review output.

    Searches for lines matching ``^###\\s+\\[<severity>\\]\\s+`` using
    MULTILINE mode. The severity argument is required (keyword-only).
    Match is case-sensitive. Only line-start headings are counted —
    mid-line occurrences are ignored.

    Emits a one-line stderr warning when a prose count phrase in the output
    (e.g. "Five blocking issues remain") disagrees with the heading count.
    The returned count is unchanged; the warning is for log inspection only (#225).
    """
    pattern = re.compile(
        r"^###\s+\[" + re.escape(severity) + r"\]\s+",
        re.MULTILINE,
    )
    heading_count = len(pattern.findall(raw_output))
    _warn_if_prose_diverges(raw_output, severity, heading_count)
    return heading_count


def write_review_file(
    reviews_dir: Path,
    review_type: str,
    round_num: int,
    content: str,
    scope: str | None = None,
) -> Path:
    """Build a canonical review filename, create dirs, write content, return path.

    Filename rules:
    - Discussion / code / plan-holistic:
        <ts>-<type>-review-r<N>.md
    - Plan per-batch (scope is a batch name, e.g. '01-setup'):
        <ts>-plan-review-<scope>-r<N>.md
    - Plan holistic (scope == 'holistic'):
        <ts>-plan-review-r<N>.md

    Timestamp is UTC, formatted as YYYYMMDD-HHMMSS.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    if (
        review_type in ("plan", "code")
        and scope is not None
        and scope != "holistic"
    ):
        filename = f"{ts}-{review_type}-review-{scope}-r{round_num}.md"
    else:
        filename = f"{ts}-{review_type}-review-r{round_num}.md"

    reviews_dir.mkdir(parents=True, exist_ok=True)
    out_path = reviews_dir / filename
    out_path.write_text(content, encoding="utf-8")
    return out_path.resolve()


def finalize_scope(
    reviews_dir: Path,
    review_type: str,
    round_n: int,
    raw_text: str,
    *,
    scope: str | None = None,
) -> dict:
    """Finalize a single review scope by parsing verdict and writing the review file.

    Runs parse_verdict, then write_review_file, and returns a dict
    with the review entry plus blocking/nit counts for ReviewResult assembly.

    Args:
        reviews_dir: Directory where review files are stored.
        review_type: Type of review ("discussion", "code", or "plan").
        round_n: Round number (integer).
        raw_text: Raw review output text to parse and write.
        scope: Optional scope name ("holistic" or batch name); if None defaults to "holistic".

    Returns:
        Dict with keys: scope, verdict, file, blocking_count, nit_count.

    Raises:
        ReviewError: from parse_verdict if verdict cannot be extracted.
    """
    verdict = parse_verdict(raw_text)
    review_path = write_review_file(
        reviews_dir, review_type, round_n, raw_text, scope=scope
    )
    # Severity labels are per-review-type: discussion uses GAP/NOTE; plan and
    # code use BLOCKING/NIT. The old inline finalize paths counted the matching
    # type-specific label, so finalize_scope must mirror that mapping rather
    # than a single hardcoded severity.
    if review_type == "discussion":
        blocking_severity, nit_severity = "GAP", "NOTE"
    else:
        blocking_severity, nit_severity = "BLOCKING", "NIT"
    blocking_count = parse_blocking_count(raw_text, severity=blocking_severity)
    nit_count = parse_blocking_count(raw_text, severity=nit_severity)

    effective_scope = scope if scope else "holistic"

    return {
        "scope": effective_scope,
        "verdict": verdict,
        "file": str(review_path),
        "blocking_count": blocking_count,
        "nit_count": nit_count,
    }


# ---------------------------------------------------------------------------
# Dispatch helpers and config loader (Step 8 additions)
# ---------------------------------------------------------------------------

def aggregate_verdict(sub_verdicts: list[str]) -> str:
    """Return the worst-case aggregate verdict across sub-verdicts.

    Rules:
    - Any NEED_CONTEXT propagates up to the aggregate (orchestrator must
      resolve the missing-context request before it can act on any
      REQUEST_CHANGES finding, so NEED_CONTEXT takes priority).
    - Any REQUEST_CHANGES or ERROR escalates the aggregate to REQUEST_CHANGES.
    - All APPROVE → APPROVE.
    - ERROR appears only inside reviews[] entries; aggregate is never ERROR.
    """
    if "NEED_CONTEXT" in sub_verdicts:
        return "NEED_CONTEXT"
    for v in sub_verdicts:
        if v in ("REQUEST_CHANGES", "ERROR"):
            return "REQUEST_CHANGES"
    return "APPROVE"


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. override wins on conflict."""
    result = base.copy()
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        elif val is None and isinstance(result.get(key), dict):
            continue
        else:
            result[key] = val
    return result


def load_config(hub_root: Path, mill_dir: Path) -> dict:
    """Load mill config with overlay from plugin template, repo layer, and local layer.

    Merge order (lowest to highest precedence):
    1. Plugin template (mill-config.yaml)
    2. Hub layer (mill-config.yaml at hub root)
    3. Local layer (mill_dir / config.local.yaml)
    4. Environment variable overrides

    Raises ReviewError if no sources are found (strict form for reviews).

    Args:
        hub_root: Absolute path to the hub directory.
        mill_dir: Absolute path to the .millhouse directory.

    Returns:
        Merged configuration dict.
    """
    # 1. Load plugin template
    template_path = resolve_plugin_template_path("mill-config.yaml")
    if template_path.exists():
        with template_path.open(encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}
    else:
        cfg = {}
    template_cfg = copy.deepcopy(cfg)

    # 2. Resolve hub-layer sources
    mill_cfg_path = _paths.resolve_mill_config_path(hub_root)

    # 3. Apply repo-layer merge logic
    found_repo_layer = False
    if mill_cfg_path.exists():
        with mill_cfg_path.open(encoding="utf-8") as fh:
            repo_cfg = yaml.safe_load(fh) or {}
        cfg = _deep_merge(cfg, repo_cfg)
        found_repo_layer = True

    # 4. Strict-missing semantics: require at least one source
    if not template_path.exists() and not found_repo_layer:
        raise ReviewError(
            f"Missing config: searched plugin template at {template_path} "
            f"and mill-config.yaml at {mill_cfg_path}"
        )

    # 5. Deep-merge the local layer
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
        cfg = _deep_merge(cfg, local_cfg)

    # 6. Validate unknown keys
    check_cfg = {k: v for k, v in cfg.items() if k != "hub_relative_path"}
    warn_unknown_keys(check_cfg, template_cfg, "merged config")

    # 7. Apply environment overrides
    cfg = apply_env_overrides(cfg)

    # 8. Apply dispatch enum back-compat shim for legacy via_psmux
    _apply_dispatch_shim(cfg)

    return cfg

