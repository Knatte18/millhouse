"""mill-status — print a status table for all active tasks.

Usage:
    python mill-status.py [--json] [--no-color] [--sort {slug,phase}]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))

import _config
import _paths
import _spawn_core
import _status
import _tasks_md


def _build_rows(git_root: Path) -> list[dict]:
    wiki = _paths.resolve_wiki_path(git_root)
    container_path = _paths.resolve_container_path(git_root)
    cfg = _config.load_config(wiki, git_root)
    branch_prefix = cfg.get("spawn", {}).get("branch_prefix", "")

    # Home.md tasks
    home_md = wiki / "Home.md"
    if home_md.exists():
        home_tasks_list = _tasks_md.parse(home_md.read_text(encoding="utf-8"))
        home_tasks = {t.slug: t for t in home_tasks_list}
    else:
        home_tasks_list = []
        home_tasks = {}

    # Active worktrees: (path, slug, title) triples from <container>/wts/
    active_worktree_list = _spawn_core.discover_active_worktrees(
        container_path / "wts", home_tasks_list, branch_prefix
    )
    worktree_map: dict[str, str] = {slug: str(path) for path, slug, _ in active_worktree_list}
    active_worktree_paths: dict[str, Path] = {slug: path for path, slug, _ in active_worktree_list}
    active_slugs: set[str] = set(worktree_map)

    # Read status for each active worktree
    status_data: dict[str, dict | None] = {}
    for slug, wt_path in active_worktree_paths.items():
        sp = wt_path / "status.md"
        try:
            status_data[slug] = _status.read_status(sp)
        except ValueError:
            status_data[slug] = None  # unreadable

    # Union all slugs
    all_slugs = set(home_tasks) | active_slugs

    rows = []
    for slug in sorted(all_slugs):
        sd = status_data.get(slug)  # None if no active worktree, or dict | None
        has_active = slug in active_slugs
        unreadable = has_active and sd is None

        # title
        if has_active and sd is not None:
            title = sd.get("task")
        elif slug in home_tasks:
            title = home_tasks[slug].title
        else:
            title = None

        # phase
        if unreadable:
            phase = "unreadable"
        elif has_active and sd is not None:
            phase = sd["phase"]
        else:
            phase = None

        # marker
        if slug in home_tasks:
            ht = home_tasks[slug]
            marker = ht.phase if ht.phase is not None else "unclaimed"
        else:
            marker = "missing"

        # marker_flag
        if marker == "active" and slug not in worktree_map:
            marker_flag = "WT?"
        elif has_active and slug not in home_tasks:
            marker_flag = "HM?"
        else:
            marker_flag = ""

        rows.append({
            "slug": slug,
            "title": title,
            "phase": phase,
            "marker": marker,
            "marker_flag": marker_flag,
            "worktree_path": worktree_map.get(slug, "-"),
            "current_batch": sd["current_batch"] if sd else None,
            "last_timeline_entry": sd["last_timeline_entry"] if sd else None,
            "blocked_reason": sd["blocked_reason"] if sd else None,
        })

    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Print mill task status table.")
    parser.add_argument("--json", action="store_true", dest="json_mode")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--sort", choices=["slug", "phase"], default="slug")
    args = parser.parse_args()

    git_root = _paths.resolve_git_root()
    rows = _build_rows(Path(git_root))

    if args.json_mode:
        out = [{k: v for k, v in row.items()} for row in rows]
        print(json.dumps(out, indent=2))
        return 0

    _render_table(rows, no_color=args.no_color, sort_by=args.sort)
    return 0


_PHASE_ORDER = {
    "blocked": 0,
    "implementing": 1,
    "reviewing": 2,
    "fixing": 3,
    "planning": 4,
    "discussed": 5,
    "discussing": 6,
}


def _sort_key_phase(row: dict):
    p = row["phase"]
    if p in _PHASE_ORDER:
        return (str(_PHASE_ORDER[p]), p)
    return ("z", p or "")


def _truncate(text: str | None, max_len: int = 40) -> str:
    if text is None:
        return "-"
    if len(text) > max_len:
        return text[:max_len] + "\u2026"
    return text


_PHASE_COLORS = {
    "blocked": "\033[31m",
    "implementing": "\033[33m",
    "reviewing": "\033[33m",
    "fixing": "\033[33m",
    "done": "\033[32m",
    "unreadable": "\033[35m",
}
_RESET = "\033[0m"


def _render_table(rows: list[dict], no_color: bool, sort_by: str) -> None:
    if sort_by == "phase":
        rows = sorted(rows, key=_sort_key_phase)
    else:
        rows = sorted(rows, key=lambda r: r["slug"])

    use_color = sys.stdout.isatty() and not no_color

    headers = ["SLUG", "TITLE", "PHASE", "MARKER", "WORKTREE", "BATCH", "LAST EVENT", "BLOCKED"]

    # Build plain-text cell values per row (used for width calc and rendering)
    rendered = []
    for row in rows:
        marker_cell = row["marker"] + (" " + row["marker_flag"] if row["marker_flag"] else "")
        phase_plain = row["phase"] if row["phase"] is not None else "\u2014"
        rendered.append({
            "SLUG": row["slug"],
            "TITLE": _truncate(row["title"]),
            "PHASE": phase_plain,
            "MARKER": marker_cell,
            "WORKTREE": row["worktree_path"],
            "BATCH": row["current_batch"] if row["current_batch"] is not None else "-",
            "LAST EVENT": _truncate(row["last_timeline_entry"]),
            "BLOCKED": row["blocked_reason"] if row["blocked_reason"] is not None else "-",
        })

    # Column widths from plain text
    widths = {h: len(h) for h in headers}
    for cells in rendered:
        for h in headers:
            widths[h] = max(widths[h], len(cells[h]))

    def pad(text: str, width: int) -> str:
        return text.ljust(width)

    header_row = " | ".join(pad(h, widths[h]) for h in headers)
    sep_row = "-+-".join("-" * widths[h] for h in headers)
    print(header_row)
    print(sep_row)

    for cells, row in zip(rendered, rows):
        parts = []
        for h in headers:
            plain = cells[h]
            w = widths[h]
            if h == "PHASE" and use_color:
                color = _PHASE_COLORS.get(row["phase"] or "", "")
                if color:
                    parts.append(color + plain.ljust(w) + _RESET)
                    continue
            parts.append(plain.ljust(w))
        print(" | ".join(parts))


if __name__ == "__main__":
    sys.exit(main())
