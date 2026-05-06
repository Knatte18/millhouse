"""
Shared helpers, regex constants, data classes, and exceptions used by
every Layer 02 review backend.

No dependencies on any other Layer 02 file. Import this from
_review_discussion.py, _review_plan.py, _review_code.py, and the API
scripts.

Public API:
    ReviewError          — raised by the backend on config/slug/round errors
    ReviewResult         — dataclass; serialised to the CLI's stdout JSON
    RE_SIMPLE            — regex matching simple review filenames
    RE_BATCH             — regex matching plan-batch review filenames
    find_active_slug()   — delegate to _active.read_slug for the canonical active.slug.md
    load_task_title()    — delegate to _active.read_all for task_title; fall back to slug on missing/malformed marker
    read_constraints_md()— read CONSTRAINTS.md, empty string if absent
    resolve_path()       — locate a path inside the active worktree from a config template
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
    load_reviewer()      — import a _reviewer_<name>.py module by name
    load_config()        — load wiki/config.yaml + optional config.local.yaml
    parse_batch_refs()   — extract Context/Edits/Creates paths from a batch file (case-insensitive none filter)
    compute_creates_union() — union of all Creates: tokens across every batch in a plan_dir
    compute_deletes_union() — union of all Deletes: tokens across every batch in a plan_dir
    resolve_ref_paths()  — resolve raw ref strings against project_root; hard-fails on missing paths not in creates_union or deletes_union
    resolve_existing_paths() — resolve raw paths and return only those that already exist on disk (silent drop, no creates_union check)
    _load_root_from_overview() — read root: field from overview's fenced-yaml block
"""
from __future__ import annotations

import importlib
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
import _active
import _paths
import _render

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "round": self.round,
            "verdict": self.verdict,
            "blocking_count": self.blocking_count,
            "reviews": self.reviews,
        }


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def find_active_slug(mill_dir: Path) -> str:
    """Delegate to _active.read_slug for the canonical active.slug.md.

    Raises ReviewError (wrapping ActiveError) so callers using
    ``except ReviewError:`` keep working unchanged.
    """
    try:
        return _active.read_slug(mill_dir)
    except _active.ActiveError as exc:
        raise ReviewError(str(exc)) from exc


def load_task_title(mill_dir: Path, slug: str) -> str:
    """Delegate to _active.read_all for task_title; fall back to slug on missing/malformed marker.

    The ``slug`` parameter is kept for signature compatibility but is not used
    as a filename. It is returned when the marker is absent or has no task_title.
    """
    try:
        data = _active.read_all(mill_dir)
    except _active.ActiveError:
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

    Computes the container path internally via
    ``_paths.resolve_container_path(Path.cwd())`` and locates the active
    worktree via ``_paths.resolve_active_worktree(container_path, slug)``.
    Returns ``active_worktree / path_tmpl`` after substituting any ``<SLUG>``
    token in ``path_tmpl`` — a no-op for the current worktree-relative
    templates but guards against stale configs that still carry the old
    ``active/<SLUG>/...`` shape (paths still fail at file-open time in that
    case; this guard only prevents a literal ``<SLUG>`` segment in the result).

    Args:
        path_tmpl: Config path template string (e.g. ``"discussion.md"`` or
            ``"reviews/"``). Read from ``wiki/config.yaml`` ``paths:`` block.
        slug: Task slug used to locate the active worktree.

    Returns:
        Absolute ``Path`` inside the active worktree. No on-disk-existence check.

    Raises:
        _paths.ActiveWorktreeNotFound: When no worktree directory exists for
            ``slug``.
        _paths.ActiveWorktreeSlugMismatch: When the worktree exists but its
            marker slug does not match ``slug``.
    """
    container_path = _paths.resolve_container_path(Path.cwd())
    active_worktree = _paths.resolve_active_worktree(container_path, slug)
    resolved_tmpl = path_tmpl.replace("<SLUG>", slug)
    return active_worktree / resolved_tmpl


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
    caller_label: str = "resolve_ref_paths",
) -> list[Path]:
    """Resolve batch-reference path strings to absolute ``Path``s.

    ``root`` is the optional filesystem sub-path declared in the plan
    overview's frontmatter ``root:`` field. When present every raw path
    is resolved under ``project_root / root``; otherwise directly under
    ``project_root``.

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
) -> list[Path]:
    """Resolve raw paths and return only those that already exist on disk.

    Mirrors resolve_ref_paths's standard-vs-wiki routing (wiki/ prefix
    routes through wiki_root; otherwise project_root + root). Unlike
    resolve_ref_paths, missing paths and routing failures are silently
    dropped — no warning, no error, no creates_union check. Used to
    expand the bulk with cross-batch ancestor creates that already
    exist; missing creates are not an error here, they just aren't
    included.
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


def bulk_files(file_paths: list[Path]) -> str:
    """Concatenate file contents with '--- FILE: <path> ---' delimiters.

    Paths that do not exist are skipped with a stderr warning.
    """
    parts: list[str] = []
    for p in file_paths:
        try:
            contents = p.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"[bulk_files] warning: {p} not found, skipping", file=sys.stderr)
            continue
        parts.append(f"--- FILE: {p} ---\n{contents}")
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
            file_content = p.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            print(f"[bulk_files_with_diff] warning: {p} not found, skipping", file=sys.stderr)
            continue

        try:
            rel_path = p.relative_to(project_root).as_posix()
        except ValueError:
            rel_path = str(p)

        result = subprocess.run(
            ["git", "-C", str(project_root), "diff", f"{start_sha}..HEAD", "--", rel_path],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )

        if result.returncode != 0:
            print(
                f"[bulk_files_with_diff] warning: git diff failed for {p} (returncode={result.returncode}), using full file",
                file=sys.stderr,
            )
            parts.append(f"--- FILE: {p} ---\n{file_content}")
            continue

        diff_text = result.stdout

        if not diff_text:
            parts.append(f"--- FILE: {p} ---\n{file_content}")
            continue

        if len(diff_text) < threshold * len(file_content):
            parts.append(f"--- DIFF: {p} (from {start_sha[:8]}) ---\n{diff_text}")
            continue

        parts.append(f"--- FILE: {p} ---\n{file_content}")

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
    """Extract a valid verdict value from a fenced yaml block.

    Scans raw_output for the first fenced ```yaml block (on its own line,
    possibly with trailing whitespace). Extracts the 'verdict:' field from
    inside the block (between the opening ```yaml and closing ``` fences).

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
    - No ```yaml opening fence is found.
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

    if open_idx is None:
        raise ReviewError(
            f"Could not parse verdict: no ```yaml block found.\n"
            f"Raw output preview:\n{preview}"
        )

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


def parse_blocking_count(raw_output: str, *, severity: str) -> int:
    """Count "### [<severity>]" ATX headings in review output.

    Searches for lines matching ``^###\\s+\\[<severity>\\]\\s+`` using
    MULTILINE mode. The severity argument is required (keyword-only).
    Match is case-sensitive. Only line-start headings are counted —
    mid-line occurrences are ignored.
    """
    pattern = re.compile(
        r"^###\s+\[" + re.escape(severity) + r"\]\s+",
        re.MULTILINE,
    )
    return len(pattern.findall(raw_output))


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


def load_reviewer(name: str):
    """Import and return the _reviewer_<name> module.

    Raises ReviewError if the module cannot be found.
    """
    try:
        return importlib.import_module(f"_reviewer_{name}")
    except ModuleNotFoundError:
        raise ReviewError(
            f"Unknown reviewer '{name}': no _reviewer_{name}.py found"
        )


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. override wins on conflict."""
    result = base.copy()
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def load_config(wiki_root: Path, mill_dir: Path) -> dict:
    """Load config.yaml from wiki_root, optionally merging config.local.yaml.

    Uses PyYAML (yaml.safe_load). The shared config must exist; the local
    override is optional. When both exist, local wins on conflict (deep merge).

    Raises ReviewError if the shared config file is absent.
    Returns a plain dict.
    """
    shared_path = wiki_root / "config.yaml"
    if not shared_path.exists():
        raise ReviewError(f"Missing config at {shared_path}")

    with shared_path.open(encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}

    local_path = mill_dir / "config.local.yaml"
    if local_path.exists():
        with local_path.open(encoding="utf-8") as fh:
            local_cfg = yaml.safe_load(fh) or {}
        cfg = _deep_merge(cfg, local_cfg)

    return cfg

