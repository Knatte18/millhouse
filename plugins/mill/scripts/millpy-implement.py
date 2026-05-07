"""millpy-implement.py — per-batch implementer dispatch CLI.

Dispatches a per-batch implementer Sonnet session or resumes one for a
fix cycle after a code review. Encapsulates the full 10-step dispatch
sequence (status update, commit, push, render, spawn) in a single call.

Flags:
    batch_name          (positional, required) batch name from the plan
                        overview's Batch Index
    --resume            resume an existing implementer session for fix cycle
    --round N           fix-cycle round number (int, default 1; only
                        meaningful with --resume)
    --review-file PATH  path to the code-review output file (required when
                        --resume is set)

Exit codes:
    0 — implementer ran; JSON report on stdout (success or stuck)
    1 — pre-launch error (bad config, missing slug, git failure, missing
        file); message on stderr, no JSON on stdout
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path

import _active
import _implementer_sonnet
import _llm_claude
import _paths
import _plan_dag
import _render
import _review_common
import _status
import _timestamp
from _implementer_common import _forward_output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Dispatch or resume a per-batch implementer session."
    )
    parser.add_argument(
        "batch_name",
        help="Batch name from the plan overview's Batch Index.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume an existing implementer session for a fix cycle.",
    )
    parser.add_argument(
        "--round",
        type=int,
        default=1,
        help="Fix-cycle round number (default 1; only meaningful with --resume).",
    )
    parser.add_argument(
        "--review-file",
        default=None,
        help="Path to the code-review output file (required with --resume).",
    )
    args = parser.parse_args(argv)

    if args.resume and not args.review_file:
        print("--resume requires --review-file", file=sys.stderr)
        return 1

    # Common setup
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
        slug = _active.read_slug(mill_dir)
    except _active.ActiveError as e:
        print(str(e), file=sys.stderr)
        return 1

    status_path = project_root / "status.md"
    full = _status.read_full(status_path)
    task_title = full["yaml"].get("task", slug)
    branch = _status.read_branch(status_path, cfg=cfg, slug=slug)
    self_fix_rounds = cfg.get("review", {}).get("code", {}).get("self_fix_rounds", 2)
    timeout = cfg.get("llm", {}).get("implementer_timeout", 1800)

    overview_path = project_root / "plan" / "00-overview.md"
    if not overview_path.exists():
        print(f"overview not found: {overview_path}", file=sys.stderr)
        return 1

    try:
        batches = _plan_dag.extract_batch_index(overview_path.read_text(encoding="utf-8"))
    except _plan_dag.PlanDAGError as e:
        print(str(e), file=sys.stderr)
        return 1

    batch_entry = next((b for b in batches if b["name"] == args.batch_name), None)
    if batch_entry is None:
        print(f"batch {args.batch_name!r} not found in overview", file=sys.stderr)
        return 1

    batch_file = project_root / "plan" / batch_entry["file"]
    plugin_root = Path(__file__).resolve().parent.parent

    if not args.resume:
        # Initial dispatch
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return 1
        start_sha = result.stdout.strip()

        session_id = str(uuid.uuid4())

        _status.set_batch_fields(status_path, args.batch_name, {"state": "running", "start_sha": start_sha, "implementer_session": session_id})

        result = subprocess.run(
            ["git", "add", "status.md"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return 1
        result = subprocess.run(
            ["git", "commit", "-m", f"mill-go: start batch {args.batch_name}"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return 1

        result = subprocess.run(
            ["git", "push", "origin", branch],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return 1

        template_path = plugin_root / "templates" / "implementer-brief.md"
        prompt_text = _render.render(template_path, {
            "TASK_TITLE": task_title,
            "SLUG": slug,
            "BATCH_NAME": args.batch_name,
            "BATCH_FILE": str(batch_file),
            "OVERVIEW_FILE": str(project_root / "plan" / "00-overview.md"),
            "PROJECT_ROOT": str(project_root),
            "WIKI_PATH": str(wiki_path),
            "SELF_FIX_ROUNDS": str(self_fix_rounds),
            "ROUND": "1",
            "SESSION_ID": session_id,
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

    else:
        # Fix-cycle resume
        review_file = Path(args.review_file)
        if not review_file.is_absolute():
            review_file = (project_root / review_file).resolve()
        if not review_file.exists():
            print(f"review file not found: {review_file}", file=sys.stderr)
            return 1

        existing = _status.read_batches(status_path)
        batch_state = next((b for b in existing if b["name"] == args.batch_name), None)
        session_id = batch_state.get("implementer_session") if batch_state else None
        if not session_id:
            print(f"no implementer_session for batch {args.batch_name!r}", file=sys.stderr)
            return 1

        _status.set_batch_fields(status_path, args.batch_name, {"state": "fixing", "review_round": args.round, "review_file": str(review_file)})
        _status.append_phase(
            status_path,
            f"fixing-{args.batch_name}-r{args.round}",
            _timestamp.now_utc_iso(),
        )

        review_file_arg = (
            str(review_file.relative_to(project_root))
            if review_file.is_relative_to(project_root)
            else str(review_file)
        )
        result = subprocess.run(
            ["git", "add", "status.md", review_file_arg],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return 1
        result = subprocess.run(
            ["git", "commit", "-m", f"mill-go: fixing batch {args.batch_name} round {args.round}"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return 1

        result = subprocess.run(
            ["git", "push", "origin", branch],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return 1

        template_path = plugin_root / "templates" / "implementer-fix.md"
        prompt_text = _render.render(template_path, {
            "REVIEW_FILE": str(review_file),
            "BATCH_FILE": str(batch_file),
            "SELF_FIX_ROUNDS": str(self_fix_rounds),
            "ROUND": str(args.round),
        })

        try:
            output, _ = _implementer_sonnet.run(
                prompt_text,
                session_id=session_id,
                resume=True,
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
