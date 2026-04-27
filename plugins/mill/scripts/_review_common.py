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
    resolve_path()       — substitute <SLUG> in a config path template
    discover_round()     — determine next review round number from filesystem
    bulk_files()         — concatenate file contents with FILE delimiters
    build_tool_rule()    — mode-specific <TOOL_RULE> block (bulk / tool-use)
    render_prompt()      — render a template from plugins/mill/templates/
    parse_verdict()      — extract APPROVE/REQUEST_CHANGES from fenced yaml block
    write_review_file()  — write a review file with a canonical timestamp name
    aggregate_verdict()  — worst-case verdict across a list of sub-verdicts
    load_reviewer()      — import a _reviewer_<name>.py module by name
    load_config()        — load wiki/config.yaml + optional config.local.yaml
    parse_batch_refs()   — extract Reads/Modifies/Creates paths from a batch file
    resolve_ref_paths()  — resolve raw ref strings against project_root (+ root:)
"""
from __future__ import annotations

import importlib
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
import _active
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "round": self.round,
            "verdict": self.verdict,
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


def resolve_path(path_tmpl: str, slug: str, wiki_root: Path) -> Path:
    """Resolve a config path template to an absolute path.

    Uses plain str.replace — does NOT use _render.render() (that reads files;
    config paths are plain strings).

    Example:
        resolve_path('active/<SLUG>/discussion.md', 'my-slug', wiki_root)
        → wiki_root / 'active/my-slug/discussion.md'
    """
    resolved = path_tmpl.replace("<SLUG>", slug)
    return wiki_root / resolved


def discover_round(reviews_dir: Path, review_type: str) -> int:
    """Scan reviews_dir and return the next round number.

    If reviews_dir does not exist, return 1. Otherwise scan for review files
    matching RE_SIMPLE (checked first) or RE_BATCH (only for plan type, only
    when RE_SIMPLE does not match). Return max(found_rounds) + 1, or 1 if no
    matching files exist.

    RE_SIMPLE is checked before RE_BATCH to prevent a plan-holistic file
    (e.g. …-plan-review-r1.md) from being mis-identified as a batch review.
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
            if m_simple.group("type") == review_type:
                found.append(int(m_simple.group("n")))
            # RE_SIMPLE matched — skip RE_BATCH for this file regardless.
            continue
        # RE_SIMPLE did not match — try RE_BATCH (plan or code).
        if review_type in ("plan", "code"):
            m_batch = RE_BATCH.match(name)
            if m_batch and m_batch.group("type") == review_type:
                found.append(int(m_batch.group("n")))

    return max(found) + 1 if found else 1


# Regex constants for parse_batch_refs.
# Header line: - **Reads:** <inline>  (inline may be empty for multi-line bullet form).
_RE_REFS_HEADER = re.compile(
    r"^-\s*\*\*(Reads|Modifies|Creates):\*\*(?P<inline>.*)$"
)
# Sub-bullet under a multi-line header (leading whitespace + dash).
_RE_REFS_SUB = re.compile(r"^\s+-\s*(.+)$")


def parse_batch_refs(batch_path: Path) -> list[str]:
    """Extract raw path strings from a batch file's Reads/Modifies/Creates lines.

    Handles the single-line form (- **Reads:** `a`, `b`) and the multi-line
    bullet form (- **Reads:**\\n  - `a`\\n  - `b`). Filters the literal token
    'none'. Returns a deduplicated list preserving first-seen order. Used by
    both plan review and code review to build the source-file bulk.
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
                if t != "none":
                    seen[t] = None
        i += 1

    return list(seen.keys())


def resolve_ref_paths(
    raw_paths: list[str],
    project_root: Path,
    root: str | None,
) -> list[Path]:
    """Resolve batch-reference path strings to absolute ``Path``s.

    ``root`` is the optional filesystem sub-path declared in the plan
    overview's frontmatter ``root:`` field. When present every raw path
    is resolved under ``project_root / root``; otherwise directly under
    ``project_root``. Non-existent paths are dropped with a stderr
    warning (the reviewer tolerates missing files — it just can't
    include them in the bulk).
    """
    resolved: list[Path] = []
    for raw in raw_paths:
        if root:
            candidate = project_root / root / raw
        else:
            candidate = project_root / raw
        if candidate.exists():
            resolved.append(candidate)
        else:
            print(
                f"[resolve_ref_paths] warning: referenced path not found, skipping: {candidate}",
                file=sys.stderr,
            )
    return resolved


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

