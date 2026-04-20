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
    find_active_slug()   — locate the single .<slug>.slug.md in .millhouse/
    load_task_title()    — read task_title from slug-file frontmatter
    read_constraints_md()— read CONSTRAINTS.md, empty string if absent
    resolve_path()       — substitute <SLUG> in a config path template
    discover_round()     — determine next review round number from filesystem
    bulk_files()         — concatenate file contents with FILE delimiters
    render_prompt()      — render a template from plugins/mill/templates/
    parse_verdict()      — extract APPROVE/REQUEST_CHANGES from YAML frontmatter
    write_review_file()  — write a review file with a canonical timestamp name
    aggregate_verdict()  — worst-case verdict across a list of sub-verdicts
    load_reviewer()      — import a _reviewer_<name>.py module by name
    check_mode()         — assert reviewer.MODE matches the expected mode
    load_config()        — load wiki/config.yaml + optional config.local.yaml
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

# Matches plan per-batch review filenames:
#   20260418-143300-plan-review-01-setup-r1.md
# RE_SIMPLE is checked first; a file matching RE_SIMPLE is excluded from
# RE_BATCH matching (prevents plan-holistic from being mis-identified).
RE_BATCH = re.compile(
    r"^\d{8}-\d{6}-plan-review-(?P<batch>[a-z0-9-]+)-r(?P<n>\d+)\.md$"
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
    """Find the single .<slug>.slug.md file in mill_dir.

    Raises ReviewError if zero or more than one slug file is found.
    """
    matches = [
        p for p in mill_dir.iterdir()
        if p.name.startswith(".") and p.name.endswith(".slug.md")
    ]
    if len(matches) == 0:
        raise ReviewError(
            "No active task: no .slug.md file found in .millhouse/"
        )
    if len(matches) > 1:
        names = ", ".join(sorted(p.name for p in matches))
        raise ReviewError(
            f"Multiple .slug.md files; expected exactly one: {names}"
        )
    # Strip leading "." and trailing ".slug.md" to get the slug.
    name = matches[0].name  # e.g. ".my-task.slug.md"
    slug = name[1:-len(".slug.md")]
    return slug


def load_task_title(mill_dir: Path, slug: str) -> str:
    """Read task_title from .<slug>.slug.md's YAML frontmatter.

    Falls back to the slug itself if the field is absent or the file lacks
    valid YAML frontmatter.
    """
    slug_file = mill_dir / f".{slug}.slug.md"
    try:
        text = slug_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return slug

    # Parse YAML frontmatter delimited by "---" lines.
    if not text.startswith("---"):
        return slug

    lines = text.splitlines()
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return slug

    for line in lines[1:end_idx]:
        # Match "task_title: <value>" allowing optional quotes.
        stripped = line.strip()
        if stripped.startswith("task_title:"):
            value = stripped[len("task_title:"):].strip().strip('"').strip("'")
            if value:
                return value

    return slug


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
        # RE_SIMPLE did not match — try RE_BATCH (plan only).
        if review_type == "plan":
            m_batch = RE_BATCH.match(name)
            if m_batch:
                found.append(int(m_batch.group("n")))

    return max(found) + 1 if found else 1


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
    """Extract 'APPROVE' or 'REQUEST_CHANGES' from YAML frontmatter.

    Expects the raw_output to begin with a YAML block delimited by '---'
    lines, containing a 'verdict:' field.

    Raises ReviewError if the frontmatter is missing, verdict is absent, or
    the value is not one of the expected verdicts.
    """
    if not raw_output.lstrip().startswith("---"):
        raise ReviewError("Could not parse verdict: no YAML frontmatter found")

    lines = raw_output.lstrip().splitlines()
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        raise ReviewError("Could not parse verdict: YAML frontmatter not closed")

    for line in lines[1:end_idx]:
        stripped = line.strip()
        if stripped.startswith("verdict:"):
            value = stripped[len("verdict:"):].strip().strip('"').strip("'")
            if value in ("APPROVE", "REQUEST_CHANGES"):
                return value
            raise ReviewError(
                f"Could not parse verdict: invalid value {value!r}; "
                "expected APPROVE or REQUEST_CHANGES"
            )

    raise ReviewError("Could not parse verdict: 'verdict:' key not found in frontmatter")


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

    if review_type == "plan" and scope is not None and scope != "holistic":
        filename = f"{ts}-plan-review-{scope}-r{round_num}.md"
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
    - Any REQUEST_CHANGES or ERROR escalates the aggregate to REQUEST_CHANGES.
    - All APPROVE → APPROVE.
    - ERROR appears only inside reviews[] entries; aggregate is never ERROR.
    """
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


def check_mode(reviewer, expected_mode: str, review_type: str) -> None:
    """Assert that reviewer.MODE matches expected_mode.

    Raises ReviewError on mismatch with the exact message format specified
    in the design:
        "No {reviewer.MODE} template exists for {review_type} review.
         Configure a {expected_mode} reviewer."
    """
    if reviewer.MODE != expected_mode:
        raise ReviewError(
            f"No {reviewer.MODE} template exists for {review_type} review. "
            f"Configure a {expected_mode} reviewer."
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


# ---------------------------------------------------------------------------
# Self-test (smoke tests)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile
    import os

    print("Running _review_common.py smoke tests...", file=sys.stderr)
    errors = 0

    # --- discover_round: nonexistent dir → 1 ---
    nonexistent = Path("/tmp/__mill_test_nonexistent_reviews__")
    assert discover_round(nonexistent, "discussion") == 1, "Expected 1 for nonexistent dir"
    print("PASS: discover_round nonexistent dir returns 1")

    # --- RE_SIMPLE matches holistic plan file; RE_BATCH is NOT applied ---
    holistic_name = "20260418-001200-plan-review-r1.md"
    m = RE_SIMPLE.match(holistic_name)
    assert m is not None, "RE_SIMPLE should match holistic plan file"
    assert m.group("type") == "plan"
    assert m.group("n") == "1"
    # Verify RE_BATCH would also match if we tested it -- confirming ordering matters.
    m_batch = RE_BATCH.match(holistic_name)
    # RE_BATCH matches "r" as batch name and "1" as n -- which is the mis-identification
    # we prevent by checking RE_SIMPLE first.
    # (In discover_round, we skip RE_BATCH once RE_SIMPLE matches.)
    print("PASS: RE_SIMPLE matches plan-holistic file before RE_BATCH could mis-identify it")

    # --- discover_round cross-type isolation ---
    with tempfile.TemporaryDirectory() as tmpdir:
        reviews = Path(tmpdir)
        # Create a plan-batch file in the reviews dir.
        (reviews / "20260418-001200-plan-review-01-setup-r2.md").write_text("x")
        # discover_round for "discussion" should ignore the plan-batch file → 1.
        result = discover_round(reviews, "discussion")
        assert result == 1, f"Expected 1 for discussion in plan-batch-only dir, got {result}"
        print("PASS: discover_round cross-type isolation (plan-batch ignored for discussion)")

        # discover_round for "plan" should pick up the batch file.
        result = discover_round(reviews, "plan")
        assert result == 3, f"Expected 3 for plan (max=2, next=3), got {result}"
        print(f"PASS: discover_round for plan with batch file: {result}")

    # --- find_active_slug: empty dir -> ReviewError ---
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir = Path(tmpdir)
        try:
            find_active_slug(mill_dir)
            print("FAIL: expected ReviewError for empty mill_dir", file=sys.stderr)
            errors += 1
        except ReviewError as e:
            assert "No active task" in str(e)
            print(f"PASS: find_active_slug empty dir -> ReviewError")

    # --- find_active_slug: one slug file -> returns slug ---
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir = Path(tmpdir)
        (mill_dir / ".my-task.slug.md").write_text("---\ntask_title: My Task\n---\n")
        slug = find_active_slug(mill_dir)
        assert slug == "my-task", f"Expected 'my-task', got {slug!r}"
        print(f"PASS: find_active_slug: {slug!r}")

    # --- load_task_title: present field ---
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir = Path(tmpdir)
        (mill_dir / ".my-task.slug.md").write_text(
            "---\ntask_title: My Task Title\nslug: my-task\n---\n"
        )
        title = load_task_title(mill_dir, "my-task")
        assert title == "My Task Title", f"Expected 'My Task Title', got {title!r}"
        print(f"PASS: load_task_title with field: {title!r}")

    # --- load_task_title: missing field -> falls back to slug ---
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir = Path(tmpdir)
        (mill_dir / ".my-task.slug.md").write_text("---\nslug: my-task\n---\n")
        title = load_task_title(mill_dir, "my-task")
        assert title == "my-task", f"Expected slug fallback 'my-task', got {title!r}"
        print(f"PASS: load_task_title fallback: {title!r}")

    # --- resolve_path ---
    wiki_root = Path("/wiki")
    p = resolve_path("active/<SLUG>/discussion.md", "my-slug", wiki_root)
    assert str(p).replace("\\", "/") == "/wiki/active/my-slug/discussion.md", f"Got {p}"
    print(f"PASS: resolve_path: {p}")

    # --- parse_verdict: valid APPROVE ---
    raw = "---\nverdict: APPROVE\n---\n\nSome review text.\n"
    v = parse_verdict(raw)
    assert v == "APPROVE", f"Expected APPROVE, got {v!r}"
    print("PASS: parse_verdict APPROVE")

    # --- parse_verdict: valid REQUEST_CHANGES ---
    raw = "---\nverdict: REQUEST_CHANGES\n---\n"
    v = parse_verdict(raw)
    assert v == "REQUEST_CHANGES"
    print("PASS: parse_verdict REQUEST_CHANGES")

    # --- parse_verdict: no frontmatter -> ReviewError ---
    try:
        parse_verdict("No frontmatter here.")
        print("FAIL: expected ReviewError", file=sys.stderr)
        errors += 1
    except ReviewError as e:
        print("PASS: parse_verdict no frontmatter -> ReviewError")

    # --- write_review_file: creates file ---
    with tempfile.TemporaryDirectory() as tmpdir:
        reviews = Path(tmpdir) / "reviews"
        path = write_review_file(reviews, "discussion", 1, "---\nverdict: APPROVE\n---\n")
        assert path.exists(), f"Expected file at {path}"
        assert "discussion-review-r1" in path.name
        print(f"PASS: write_review_file discussion: {path.name}")

        # Plan batch scope
        path2 = write_review_file(reviews, "plan", 1, "content", scope="01-setup")
        assert "plan-review-01-setup-r1" in path2.name, f"Got {path2.name}"
        print(f"PASS: write_review_file plan-batch: {path2.name}")

        # Plan holistic scope
        path3 = write_review_file(reviews, "plan", 1, "content", scope="holistic")
        assert "plan-review-r1" in path3.name, f"Got {path3.name}"
        assert "holistic" not in path3.name
        print(f"PASS: write_review_file plan-holistic: {path3.name}")

    # --- bulk_files: nonexistent path skipped with warning ---
    with tempfile.TemporaryDirectory() as tmpdir:
        existing = Path(tmpdir) / "a.md"
        existing.write_text("hello")
        result = bulk_files([existing, Path("/nonexistent/path/x.md")])
        assert "hello" in result
        assert "FILE:" in result
        print("PASS: bulk_files skips missing files")

    # --- render_prompt: FileNotFoundError for missing template ---
    try:
        render_prompt("nonexistent-template-xyz")
        print("FAIL: expected FileNotFoundError", file=sys.stderr)
        errors += 1
    except FileNotFoundError:
        print("PASS: render_prompt missing template: FileNotFoundError")

    # --- aggregate_verdict ---
    assert aggregate_verdict(["APPROVE", "APPROVE"]) == "APPROVE"
    print("PASS: aggregate_verdict all APPROVE")
    assert aggregate_verdict(["APPROVE", "REQUEST_CHANGES"]) == "REQUEST_CHANGES"
    print("PASS: aggregate_verdict with REQUEST_CHANGES")
    assert aggregate_verdict(["APPROVE", "ERROR"]) == "REQUEST_CHANGES"
    print("PASS: aggregate_verdict ERROR escalates to REQUEST_CHANGES")
    assert aggregate_verdict([]) == "APPROVE"
    print("PASS: aggregate_verdict empty list -> APPROVE")

    # --- load_reviewer: nonexistent -> ReviewError ---
    try:
        load_reviewer("nonexistent_xyz_abc")
        print("FAIL: expected ReviewError for nonexistent reviewer", file=sys.stderr)
        errors += 1
    except ReviewError as e:
        assert "nonexistent_xyz_abc" in str(e)
        print("PASS: load_reviewer nonexistent -> ReviewError")

    # --- check_mode: mismatch -> ReviewError with correct message ---
    class _FakeBulkReviewer:
        MODE = "bulk"
    try:
        check_mode(_FakeBulkReviewer, "tool-use", "discussion")
        print("FAIL: expected ReviewError for mode mismatch", file=sys.stderr)
        errors += 1
    except ReviewError as e:
        msg = str(e)
        assert "bulk" in msg, f"Expected 'bulk' in error, got: {msg!r}"
        assert "tool-use" in msg, f"Expected 'tool-use' in error, got: {msg!r}"
        assert "discussion" in msg, f"Expected 'discussion' in error, got: {msg!r}"
        print(f"PASS: check_mode mismatch -> ReviewError: {msg!r}")

    # --- check_mode: matching mode -> no error ---
    try:
        check_mode(_FakeBulkReviewer, "bulk", "plan")
        print("PASS: check_mode matching mode -> no error")
    except ReviewError as e:
        print(f"FAIL: unexpected ReviewError: {e}", file=sys.stderr)
        errors += 1

    # --- load_config: valid YAML + local override ---
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki = Path(tmpdir) / "wiki"
        wiki.mkdir()
        mill = Path(tmpdir) / ".millhouse"
        mill.mkdir()

        (wiki / "config.yaml").write_text(
            "review:\n  plan:\n    rounds: 3\n    batch: sonnetmax\n",
            encoding="utf-8",
        )
        cfg = load_config(wiki, mill)
        assert cfg["review"]["plan"]["rounds"] == 3, f"Expected 3, got {cfg}"
        print("PASS: load_config loads shared config")

        # Local override
        (mill / "config.local.yaml").write_text(
            "review:\n  plan:\n    rounds: 1\n",
            encoding="utf-8",
        )
        cfg = load_config(wiki, mill)
        assert cfg["review"]["plan"]["rounds"] == 1, f"Expected 1 after override, got {cfg}"
        assert cfg["review"]["plan"]["batch"] == "sonnetmax", "batch key lost in merge"
        print("PASS: load_config local override wins; other keys preserved")

    # --- load_config: missing config -> ReviewError ---
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki = Path(tmpdir) / "wiki"
        wiki.mkdir()
        mill = Path(tmpdir) / ".millhouse"
        mill.mkdir()
        try:
            load_config(wiki, mill)
            print("FAIL: expected ReviewError for missing config", file=sys.stderr)
            errors += 1
        except ReviewError as e:
            assert "Missing config" in str(e)
            print("PASS: load_config missing config -> ReviewError")

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        sys.exit(1)
    else:
        print("\nAll smoke tests passed.")
