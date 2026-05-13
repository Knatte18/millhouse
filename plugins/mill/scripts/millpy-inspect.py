"""mill-inspect — deep dump of every active task's status.md.

Usage:
    python mill-inspect.py [<slug>] [--json] [--since <phase>]
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

PHASE_ORDER = (
    "discussing",
    "discussed",
    "planning",
    "planned",
    "implementing",
    "reviewing",
    "fixing",
    "done",
    "abandoned",
    "blocked",
)

_PHASE_INDEX = {p: i for i, p in enumerate(PHASE_ORDER)}


def _phase_index(phase: str | None) -> int:
    if phase is None:
        return 0
    return _PHASE_INDEX.get(phase, 0)


def _collect(git_root: Path, slug_filter: str | None) -> list[dict]:
    wiki = _paths.resolve_wiki_path(git_root)
    container_path = _paths.resolve_container_path(git_root)
    cfg = _config.load_config(wiki, git_root)
    branch_prefix = cfg.get("spawn", {}).get("branch_prefix", "")

    home_md = wiki / "Home.md"
    home_tasks_list: list = []
    home_marker_map: dict[str, str] = {}
    if home_md.exists():
        home_tasks_list = _tasks_md.parse(home_md.read_text(encoding="utf-8"))
        for task in home_tasks_list:
            home_marker_map[task.slug] = task.phase if task.phase is not None else "unclaimed"

    # Active worktrees: (path, slug, title) triples from <container>/wts/
    active_worktree_list = _spawn_core.discover_active_worktrees(
        container_path / "wts", home_tasks_list, branch_prefix
    )
    worktree_map: dict[str, Path] = {slug: path for path, slug, _ in active_worktree_list}
    slugs = sorted(worktree_map)

    if not slugs:
        return []

    if slug_filter is not None:
        if slug_filter not in worktree_map:
            print(f"error: no active task with slug {slug_filter!r}", file=sys.stderr)
            sys.exit(1)
        slugs = [slug_filter]

    records = []
    for slug in slugs:
        wt_path = worktree_map[slug]
        sp = _paths.status_path(wt_path, cfg)
        try:
            full = _status.read_full(sp)
        except ValueError as exc:
            print(f"[WARN] could not read {sp}: {exc}", file=sys.stderr)
            continue

        marker = home_marker_map.get(slug, "unclaimed")

        records.append({
            "slug": slug,
            "yaml": full["yaml"],
            "timeline": full["timeline"],
            "worktree": str(wt_path),
            "home_marker": marker,
        })

    return records


def _render_markdown(records: list[dict]) -> str:
    parts: list[str] = []
    for rec in records:
        parts.append(f"## {rec['slug']}")
        parts.append("")

        yaml_dict = rec["yaml"]
        for key, value in yaml_dict.items():
            if isinstance(value, str) and "\n" in value:
                parts.append(f"{key}: |")
                for line in value.splitlines():
                    parts.append(f"  {line}")
            else:
                parts.append(f"{key}: {value}")
        parts.append("")

        parts.append("Timeline:")
        if rec["timeline"]:
            for line in rec["timeline"]:
                parts.append(f"  {line}")
        else:
            parts.append("  (empty)")
        parts.append("")

        wt = rec["worktree"]
        if wt is not None:
            parts.append(f"worktree: {wt}")

        marker = rec["home_marker"]
        if marker == "active":
            parts.append(f"home_marker: {marker}")
        else:
            parts.append(f"[WARN] home_marker: {marker}")

        parts.append("")

    return "\n".join(parts)


def _render_json(records: list[dict]) -> str:
    out: dict[str, dict] = {}
    for rec in records:
        out[rec["slug"]] = {
            "status": rec["yaml"],
            "timeline": rec["timeline"],
            "worktree": rec["worktree"],
            "home_marker": rec["home_marker"],
        }
    return json.dumps(out, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Deep dump of active task status files.")
    parser.add_argument("slug", nargs="?", default=None, help="Narrow to one slug.")
    parser.add_argument("--json", action="store_true", dest="json_mode")
    parser.add_argument("--since", metavar="PHASE", default=None,
                        help="Show only tasks at or after PHASE in the phase order.")
    args = parser.parse_args()

    git_root = _paths.resolve_git_root()
    records = _collect(git_root, args.slug)

    if args.since is not None:
        cutoff = _phase_index(args.since)
        records = [
            r for r in records
            if _phase_index(r["yaml"].get("phase")) >= cutoff
        ]

    if not records:
        print("(no active tasks)")
        return 0

    if args.json_mode:
        print(_render_json(records))
    else:
        print(_render_markdown(records))

    return 0


if __name__ == "__main__":
    sys.exit(main())
