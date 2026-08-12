"""mill-review-summary — print a per-task table of review rounds: verdict, model, effort,
duration, tool-calls, cost.

Reads every review file already on disk for the active task's ``reviews_dir`` and renders one row
per file: round, type, scope, verdict, model, effort, duration, tool-calls, cost. Nothing is
computed here — this is a pure read-side view over the metadata `_review_common.write_review_file`
and `_review_common.apply_cost_metadata` already persisted (see
plugins/mill/templates/review-output.schema.md). Review files written before the cost-metadata
feature existed simply render `n/a` for the missing cells.

Usage:
    python millpy-review-summary.py [--slug <slug>] [--json] [--no-color] [--sort {round,scope}]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))

import _paths
import _review_common
import _reviewers
import yaml

# Matches a per-batch review filename for either plan or code, e.g.
# 20260418-143300-plan-review-03-templates-r2.md or 20260418-143300-code-review-05-cards-r3.md.
# Mirrors _review_common.RE_BATCH's type=plan|code alternation so per-batch code reviews (written
# for every mill-go batch) parse identically to per-batch plan reviews.
_RE_BATCH = re.compile(
    r"^\d{8}-\d{6}-(?P<type>plan|code)-review-(?P<batch>[a-z0-9-]+)-r(?P<n>\d+)\.md$"
)

# Matches a holistic (non-batch-scoped) review filename for any of the three review types, e.g.
# 20260418-001200-discussion-review-r1.md or 20260418-143300-code-review-r2.md.
_RE_SIMPLE = re.compile(
    r"^\d{8}-\d{6}-(?P<type>discussion|code|plan)-review-r(?P<n>\d+)\.md$"
)

_YAML_FENCE_RE = re.compile(r"```yaml(.*?)```", re.DOTALL)

_VERDICT_COLORS = {
    "APPROVE": "\033[32m",
    "REQUEST_CHANGES": "\033[31m",
    "ERROR": "\033[35m",
    "NEED_CONTEXT": "\033[35m",
}
_RESET = "\033[0m"


def parse_review_filename(name: str) -> dict | None:
    """Classify a review filename into its round/type/scope, or return None for a non-review file.

    Accepts the two canonical patterns documented in review-output.schema.md: the holistic form
    (`<ts>-<type>-review-r<N>.md`, scope `holistic`) and the batch-scoped form
    (`<ts>-<type>-review-<batch-name>-r<N>.md`, scope the batch name) for plan and code alike.
    Rejects anything else outright, notably the `*-fix-r<N>.md` fixer reports that share the
    reviews directory but must never appear as summary rows.
    """
    m_simple = _RE_SIMPLE.match(name)
    if m_simple:
        return {
            "round": int(m_simple.group("n")),
            "type": m_simple.group("type"),
            "scope": "holistic",
        }
    m_batch = _RE_BATCH.match(name)
    if m_batch:
        return {
            "round": int(m_batch.group("n")),
            "type": m_batch.group("type"),
            "scope": m_batch.group("batch"),
        }
    return None


def _resolve_effort(model: str | None, registry: dict | None) -> str | None:
    """Look up the `effort` key for a reviewer alias via the reviewer registry.

    Returns None when the registry is unavailable, the alias is unknown, or resolution raises for
    any other reason (e.g. a bare Agent-tool tier such as `sonnet`, which `--actual-model` can
    write and which the registry does not recognize as a reviewer name).
    """
    if model is None or registry is None:
        return None
    try:
        spec = _reviewers.resolve(registry, model)
    except Exception:
        return None
    return spec.get("effort")


def build_rows(reviews_dir: Path, registry: dict | None = None) -> list[dict]:
    """Walk `reviews_dir` and build one row per review file for the summary table.

    Uses `rglob` so `revise-<N>/` subdirectories written by mill-plan's `--revise` mode are
    included. Files that `parse_review_filename` rejects (notably `*-fix-r<N>.md` fixer reports)
    are skipped entirely. For each accepted file, the first fenced ```yaml block is extracted and
    parsed; every yaml-derived cell is None when the block is missing, unparseable, or lacks the
    key — this function never raises on a malformed review file.

    When the yaml block carries its own `round`, the filename-derived round wins (the filename is
    written by `write_review_file`, authoritative for ordering; the yaml header is reviewer text)
    and the yaml round is used only when the filename yielded none, which cannot happen for a file
    that already passed `parse_review_filename`.

    Returns:
        A list of row dicts with keys: round, type, scope, verdict, model, effort, duration_s,
        tool_calls, cost_usd, file.
    """
    rows: list[dict] = []
    for path in sorted(reviews_dir.rglob("*.md")):
        if not path.is_file():
            continue
        parsed_name = parse_review_filename(path.name)
        if parsed_name is None:
            continue

        text = path.read_text(encoding="utf-8", errors="replace")
        yaml_data: dict = {}
        fence_match = _YAML_FENCE_RE.search(text)
        if fence_match:
            try:
                loaded = yaml.safe_load(fence_match.group(1))
            except yaml.YAMLError:
                loaded = None
            if isinstance(loaded, dict):
                yaml_data = loaded

        round_num = parsed_name["round"]
        if round_num is None:
            round_num = yaml_data.get("round")

        model = yaml_data.get("reviewer_model")

        rows.append({
            "round": round_num,
            "type": parsed_name["type"],
            "scope": parsed_name["scope"],
            "verdict": yaml_data.get("verdict"),
            "model": model,
            "effort": _resolve_effort(model, registry),
            "duration_s": yaml_data.get("duration_s"),
            "tool_calls": yaml_data.get("tool_calls"),
            "cost_usd": yaml_data.get("cost_usd"),
            "file": path.name,
        })

    return rows


def format_duration(seconds: float | None) -> str:
    """Render a duration in seconds as a compact human string, or `n/a` for None.

    Under 60 seconds renders as `"{n}s"` (integer seconds); at or above 60 seconds renders as
    `"{m}m{ss:02d}s"`.
    """
    if seconds is None:
        return "n/a"
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    return f"{minutes}m{secs:02d}s"


def _format_cell(key: str, value) -> str:
    """Render a single row value as its display string, `n/a` for None."""
    if value is None:
        return "n/a"
    if key == "duration_s":
        return format_duration(value)
    if key == "cost_usd":
        return f"${value:.4f}"
    if key == "tool_calls":
        return str(int(value))
    return str(value)


def _sort_key_round(row: dict):
    return (row["round"] if row["round"] is not None else -1, row["scope"] or "")


def _sort_key_scope(row: dict):
    return (row["scope"] or "", row["round"] if row["round"] is not None else -1)


def render_table(rows: list[dict], *, no_color: bool, sort_by: str) -> None:
    """Print a width-computed, ` | `-joined table of review rows, colouring VERDICT only.

    Mirrors millpy-status.py's table-rendering conventions. Colours green for APPROVE, red for
    REQUEST_CHANGES, magenta for ERROR/NEED_CONTEXT, and only when stdout is a tty and --no-color
    was not passed.
    """
    if sort_by == "scope":
        rows = sorted(rows, key=_sort_key_scope)
    else:
        rows = sorted(rows, key=_sort_key_round)

    use_color = sys.stdout.isatty() and not no_color

    headers = ["ROUND", "TYPE", "SCOPE", "VERDICT", "MODEL", "EFFORT", "DURATION", "TOOLS", "COST"]
    key_by_header = {
        "ROUND": "round",
        "TYPE": "type",
        "SCOPE": "scope",
        "VERDICT": "verdict",
        "MODEL": "model",
        "EFFORT": "effort",
        "DURATION": "duration_s",
        "TOOLS": "tool_calls",
        "COST": "cost_usd",
    }

    rendered = [
        {h: _format_cell(key_by_header[h], row[key_by_header[h]]) for h in headers}
        for row in rows
    ]

    widths = {h: len(h) for h in headers}
    for cells in rendered:
        for h in headers:
            widths[h] = max(widths[h], len(cells[h]))

    def pad(text: str, width: int) -> str:
        return text.ljust(width)

    print(" | ".join(pad(h, widths[h]) for h in headers))
    print("-+-".join("-" * widths[h] for h in headers))

    for cells, row in zip(rendered, rows):
        parts = []
        for h in headers:
            plain = cells[h]
            w = widths[h]
            if h == "VERDICT" and use_color:
                color = _VERDICT_COLORS.get(row["verdict"] or "", "")
                if color:
                    parts.append(color + plain.ljust(w) + _RESET)
                    continue
            parts.append(plain.ljust(w))
        print(" | ".join(parts))


def _load_registry(hub: Path) -> dict | None:
    """Load the reviewer registry, degrading to None on any failure.

    A registry failure must never abort the summary table -- it only means the EFFORT column
    renders `n/a` for every row.
    """
    try:
        return _reviewers.load(hub)
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print a per-task table of review rounds: verdict, model, effort, duration, tool-calls, cost."
    )
    parser.add_argument("--slug", default=None)
    parser.add_argument("--json", action="store_true", dest="json_mode")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--sort", choices=["round", "scope"], default="round")
    args = parser.parse_args()

    git_root = _paths.resolve_git_root()
    hub = _paths.resolve_hub_path()
    wiki_root = _paths.resolve_wiki_path(git_root)
    cfg = _review_common.load_config(hub, hub / ".millhouse")

    slug = args.slug or _review_common.find_active_slug(hub, wiki_root, cfg)
    reviews_dir = _review_common.resolve_path(cfg["paths"]["reviews_dir"], slug)

    registry = _load_registry(hub)

    if not reviews_dir.exists():
        print(f"no review files found for {slug}")
        return 0

    rows = build_rows(reviews_dir, registry)
    if not rows:
        print(f"no review files found for {slug}")
        return 0

    if args.json_mode:
        print(json.dumps(rows, indent=2))
        return 0

    render_table(rows, no_color=args.no_color, sort_by=args.sort)
    return 0


if __name__ == "__main__":
    sys.exit(main())
