"""millpy-implement-holistic.py — holistic implementer dispatch CLI.

Dispatches a fresh (cold-start) holistic implementer session to fix
cross-batch findings from a holistic code review. Always cold-start —
no --resume flag, since holistic findings span the entire worktree.

Flags:
    --review-file PATH  (required) absolute or relative path to the
                        holistic code review output file
    --round N           fix-cycle round number (int, default 1)

Exit codes:
    0 — implementer ran; JSON report on stdout (success or stuck)
    1 — pre-launch error (bad config, missing slug, git failure, missing
        file); message on stderr, no JSON on stdout
"""
from __future__ import annotations

import argparse
import json
import _subprocess_util
import sys
import uuid
from pathlib import Path

import _implementer_sonnet
import _llm_claude
import _marker
import _paths
import _plan_dag
import _render
import _review_common
import _status
import _timestamp
from _implementer_common import _forward_output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Dispatch a holistic implementer session for cross-batch fix."
    )
    parser.add_argument(
        "--review-file",
        default=None,
        help="Path to the holistic code review output file (required).",
    )
    parser.add_argument(
        "--round",
        type=int,
        default=1,
        help="Holistic fix-cycle round number (default 1).",
    )
    args = parser.parse_args(argv)

    if args.review_file is None:
        print("--review-file is required", file=sys.stderr)
        return 1

    project_root = Path.cwd()
    mill_dir = project_root / ".millhouse"

    git_root = _paths.resolve_git_root()
    wiki_path = _paths.resolve_wiki_path(git_root)

    try:
        cfg = _review_common.load_config(wiki_path, mill_dir)
    except _review_common.ReviewError as e:
        print(str(e), file=sys.stderr)
        return 1

    try:
        slug = _marker.slug_from_branch(git_root, wiki_path, cfg)
    except _marker.MarkerError as e:
        print(str(e), file=sys.stderr)
        return 1

    status_path = project_root / "task" / "status.md"
    full = _status.read_full(status_path)
    task_title = full["yaml"].get("task", slug)
    branch = _status.read_branch(status_path, cfg=cfg, slug=slug)
    self_fix_rounds = cfg.get("review", {}).get("code", {}).get("self_fix_rounds", 2)
    timeout = cfg.get("llm", {}).get("implementer_timeout", 1800)

    review_file = Path(args.review_file)
    if not review_file.is_absolute():
        review_file = (project_root / review_file).resolve()
    if not review_file.exists():
        print(f"review file not found: {review_file}", file=sys.stderr)
        return 1

    overview_path = project_root / "task" / "plan" / "00-overview.md"
    if not overview_path.exists():
        print(f"overview not found: {overview_path}", file=sys.stderr)
        return 1

    try:
        batches = _plan_dag.extract_batch_index(overview_path.read_text(encoding="utf-8"))
    except _plan_dag.PlanDAGError as e:
        print(str(e), file=sys.stderr)
        return 1

    batch_files_text = "\n".join(
        str(project_root / "task" / "plan" / b["file"]) for b in batches
    )

    batch_states = _status.read_batches(status_path)
    sid_map = {b["name"]: b.get("implementer_session", "(none)") for b in batch_states}
    batch_session_ids_text = "\n".join(
        f"{b['name']}: {sid_map.get(b['name'], '(none)')}" for b in batches
    )

    session_id = str(uuid.uuid4())

    _status.append_phase(status_path, "holistic-fixing", _timestamp.now_utc_iso())

    review_file_arg = (
        str(review_file.relative_to(project_root))
        if review_file.is_relative_to(project_root)
        else str(review_file)
    )

    result = _subprocess_util.run(
        ["git", "add", "task/status.md", review_file_arg],
        cwd=project_root,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return 1

    result = _subprocess_util.run(
        ["git", "commit", "-m", f"mill-go: holistic fix round {args.round}"],
        cwd=project_root,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return 1

    result = _subprocess_util.run(
        ["git", "push", "origin", branch],
        cwd=project_root,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return 1

    plugin_root = Path(__file__).resolve().parent.parent
    template_path = plugin_root / "templates" / "implementer-holistic-brief.md"
    prompt_text = _render.render(template_path, {
        "TASK_TITLE": task_title,
        "SLUG": slug,
        "OVERVIEW_FILE": str(overview_path),
        "REVIEW_FILE": str(review_file),
        "PROJECT_ROOT": str(project_root),
        "WIKI_PATH": str(wiki_path),
        "SESSION_ID": session_id,
        "ROUND": str(args.round),
        "SELF_FIX_ROUNDS": str(self_fix_rounds),
        "BATCH_FILES": batch_files_text,
        "BATCH_SESSION_IDS": batch_session_ids_text,
    })

    try:
        output, _ = _implementer_sonnet.run(
            prompt_text,
            session_id=session_id,
            resume=False,
            cwd=project_root,
            timeout=timeout,
        )
    except _llm_claude.LLMError as e:
        print(json.dumps({"status": "stuck", "stuck_type": "transient", "reason": str(e)}))
        print(str(e), file=sys.stderr)
        return 1

    return _forward_output(output, project_root)


if __name__ == "__main__":
    sys.exit(main())
