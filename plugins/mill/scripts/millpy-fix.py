"""millpy-fix.py — unified fixer dispatch CLI.

Dispatches a cold-start fixer session to fix findings from a code review.
Supports both per-batch and holistic scopes. Always cold-start (resume=False).

Flags:
    --scope {batch,holistic}  (required) fix scope: "batch" for per-batch,
                              "holistic" for cross-batch
    --batch-name NAME         (required iff --scope batch) batch name from
                              the plan overview's Batch Index
    --review-file PATH        (required) absolute or relative path to the
                              code review output file
    --round N                 fix-cycle round number (int, default 1)

Exit codes:
    0 — fixer ran; JSON report on stdout (success or stuck)
    1 — pre-launch error (bad config, missing slug, missing file, etc.);
        message on stderr, no JSON on stdout
"""
from __future__ import annotations

import argparse
import json
import _subprocess_util
import sys
import uuid
from pathlib import Path

import _implementer_claude
import _llm_claude
import _marker
import _paths
import _plan_dag
import _render
import _review_common
import _reviewers
import _status
import _timestamp
from _implementer_common import _forward_output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Dispatch a fixer session for code review findings."
    )
    parser.add_argument(
        "--scope",
        choices=["batch", "holistic"],
        required=True,
        help="Fix scope: 'batch' for per-batch, 'holistic' for cross-batch.",
    )
    parser.add_argument(
        "--batch-name",
        default=None,
        help="Batch name (required iff --scope batch).",
    )
    parser.add_argument(
        "--review-file",
        default=None,
        help="Path to the code review output file (required).",
    )
    parser.add_argument(
        "--round",
        type=int,
        default=1,
        help="Fix-cycle round number (default 1).",
    )
    args = parser.parse_args(argv)

    # Validate mutual constraints
    if args.scope == "batch" and not args.batch_name:
        print("--batch-name is required when --scope batch", file=sys.stderr)
        return 1
    if args.scope == "holistic" and args.batch_name:
        print("--batch-name must not be set when --scope holistic", file=sys.stderr)
        return 1

    if args.review_file is None:
        print("--review-file is required", file=sys.stderr)
        return 1

    # Common setup
    project_root = Path.cwd()
    mill_dir = project_root / ".millhouse"

    git_root = _paths.resolve_git_root()
    wiki_path = _paths.resolve_wiki_path(git_root)

    try:
        cfg = _review_common.load_config(git_root, mill_dir)
    except _review_common.ReviewError as e:
        print(str(e), file=sys.stderr)
        return 1

    name_result = _subprocess_util.run(["git", "config", "--global", "--get", "user.name"], cwd=project_root)
    email_result = _subprocess_util.run(["git", "config", "--global", "--get", "user.email"], cwd=project_root)
    git_name = name_result.stdout.strip()
    git_email = email_result.stdout.strip()
    if not git_name or not git_email:
        print("git config --global user.name and user.email must be set", file=sys.stderr)
        return 1

    try:
        slug = _marker.slug_from_branch(git_root, wiki_path, cfg)
    except _marker.MarkerError as e:
        print(str(e), file=sys.stderr)
        return 1

    status_path = _paths.status_path(project_root, cfg)
    full = _status.read_full(status_path)
    task_title = full["yaml"].get("task", slug)
    branch = _status.read_branch(status_path, cfg=cfg, slug=slug)
    self_fix_rounds = cfg.get("roles", {}).get("implementer", {}).get("self_fix_rounds", 2)
    timeout = cfg.get("llm", {}).get("implementer_timeout", 1800)
    fixer_cfg = cfg.get("roles", {}).get("fixer", {})
    model_name = fixer_cfg.get("model", "haiku")
    try:
        registry = _reviewers.load(git_root)
        fixer_spec = _reviewers.resolve(registry, model_name)
    except _reviewers.ReviewerError as e:
        print(str(e), file=sys.stderr)
        return 1
    fixer_model = fixer_spec["model"]
    fixer_effort = fixer_spec.get("effort")

    review_file = Path(args.review_file)
    if not review_file.is_absolute():
        review_file = (project_root / review_file).resolve()
    if not review_file.exists():
        print(f"review file not found: {review_file}", file=sys.stderr)
        return 1

    plan_base = _paths.resolve_task_path(project_root, "_mill/plan/")
    overview_path = plan_base / "00-overview.md"
    if not overview_path.exists():
        print(f"overview not found: {overview_path}", file=sys.stderr)
        return 1

    try:
        batches = _plan_dag.extract_batch_index(overview_path.read_text(encoding="utf-8"))
    except _plan_dag.PlanDAGError as e:
        print(str(e), file=sys.stderr)
        return 1

    session_id = str(uuid.uuid4())

    review_file_arg = (
        str(review_file.relative_to(project_root))
        if review_file.is_relative_to(project_root)
        else str(review_file)
    )

    plugin_root = Path(__file__).resolve().parent.parent

    # Branch on scope
    if args.scope == "batch":
        # Per-batch fixer dispatch
        batch_entry = next((b for b in batches if b["name"] == args.batch_name), None)
        if batch_entry is None:
            print(f"batch {args.batch_name!r} not found in overview", file=sys.stderr)
            return 1

        batch_file = plan_base / batch_entry["file"]

        _status.set_batch_fields(
            status_path, args.batch_name, {"state": "fixing", "review_round": args.round, "review_file": str(review_file)}
        )
        _status.append_phase(status_path, f"fixing-{args.batch_name}-r{args.round}", _timestamp.now_utc_iso())

        result = _subprocess_util.run(
            ["git", "add", status_path.relative_to(project_root).as_posix(), review_file_arg],
            cwd=project_root,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return 1

        result = _subprocess_util.git_commit(
            project_root,
            f"mill-go: fixing batch {args.batch_name} round {args.round}",
            name=git_name,
            email=git_email,
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

        template_path = plugin_root / "templates" / "fixer-batch-brief.md"
        prompt_text = _render.render(
            template_path,
            {
                "TASK_TITLE": task_title,
                "SLUG": slug,
                "BATCH_NAME": args.batch_name,
                "BATCH_FILE": str(batch_file),
                "OVERVIEW_FILE": str(overview_path),
                "REVIEW_FILE": str(review_file),
                "PROJECT_ROOT": str(project_root),
                "WIKI_PATH": str(wiki_path),
                "SESSION_ID": session_id,
                "ROUND": str(args.round),
                "SELF_FIX_ROUNDS": str(self_fix_rounds),
            },
        )

    else:  # args.scope == "holistic"
        # Holistic fixer dispatch
        batch_files_text = "\n".join(str(plan_base / b["file"]) for b in batches)

        _status.append_phase(status_path, "holistic-fixing", _timestamp.now_utc_iso())

        result = _subprocess_util.run(
            ["git", "add", status_path.relative_to(project_root).as_posix(), review_file_arg],
            cwd=project_root,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return 1

        result = _subprocess_util.git_commit(
            project_root,
            f"mill-go: holistic fix round {args.round}",
            name=git_name,
            email=git_email,
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

        template_path = plugin_root / "templates" / "fixer-holistic-brief.md"
        prompt_text = _render.render(
            template_path,
            {
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
            },
        )

    # Shared dispatch tail for both scopes
    try:
        output, _ = _implementer_claude.run(
            prompt_text,
            model=fixer_model,
            effort=fixer_effort,
            session_id=session_id,
            resume=False,
            cwd=project_root,
            timeout=timeout,
        )
    except _llm_claude.LLMError as e:
        print(json.dumps({"status": "stuck", "stuck_type": "transient", "reason": str(e)}))
        print(str(e), file=sys.stderr)
        return 1

    return _forward_output(output, project_root, session_id=session_id)


if __name__ == "__main__":
    sys.exit(main())
