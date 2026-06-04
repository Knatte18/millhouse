"""millpy-implement.py — per-batch implementer dispatch CLI.

Dispatches a per-batch implementer Sonnet session. Encapsulates the full
10-step dispatch sequence (status update, commit, push, render, spawn)
in a single call.

Flags:
    batch_name          (positional, required) batch name from the plan
                        overview's Batch Index

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

import _cleanliness
import _implementer_claude
import _llm_claude
import _marker
import _paths
import _plan_dag
import _render
import _review_common
import _reviewers
import _status
from _implementer_common import _forward_output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Dispatch or resume a per-batch implementer session."
    )
    parser.add_argument(
        "batch_name",
        help="Batch name from the plan overview's Batch Index.",
    )
    args = parser.parse_args(argv)

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

    plan_dir = cfg.get("paths", {}).get("plan_dir", "_mill/plan/")
    status_path = _paths.status_path(project_root, cfg)
    full = _status.read_full(status_path)
    task_title = full["yaml"].get("task", slug)

    branch_result = _subprocess_util.run(
        ["git", "-C", str(project_root), "branch", "--show-current"]
    )
    if branch_result.returncode != 0:
        print(json.dumps({"status": "stuck", "stuck_type": "transient", "reason": f"git branch --show-current failed: {branch_result.stderr.strip()}"}))
        print(branch_result.stderr, file=sys.stderr)
        return 1
    branch = branch_result.stdout.strip()
    if not branch:
        print(json.dumps({"status": "stuck", "stuck_type": "transient", "reason": "detached HEAD: no current branch"}))
        print("detached HEAD: no current branch", file=sys.stderr)
        return 1
    self_fix_rounds = cfg.get("roles", {}).get("implementer", {}).get("self_fix_rounds", 2)
    implementer_cfg = cfg.get("roles", {}).get("implementer", {})
    model_name = implementer_cfg.get("model", "sonnethigh")
    try:
        registry = _reviewers.load(git_root)
        impl_spec = _reviewers.resolve(registry, model_name)
    except _reviewers.ReviewerError as e:
        print(str(e), file=sys.stderr)
        return 1
    impl_model = impl_spec["model"]
    impl_effort = impl_spec.get("effort")
    timeout = impl_spec.get("timeout") or cfg.get("llm", {}).get("implementer_timeout", 1800)

    plan_base = _paths.resolve_task_path(project_root, plan_dir)
    overview_path = plan_base / "00-overview.md"
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

    batch_file = plan_base / batch_entry["file"]
    plugin_root = Path(__file__).resolve().parent.parent

    result = _subprocess_util.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return 1
    start_sha = result.stdout.strip()

    snapshot_path = project_root / "_mill" / f".cleanliness-snapshot-{args.batch_name}.txt"
    _cleanliness.capture_snapshot(project_root, snapshot_path)

    session_id = str(uuid.uuid4())

    _status.set_batch_fields(status_path, args.batch_name, {"state": "running", "start_sha": start_sha, "implementer_session": session_id})

    last_log = _subprocess_util.run(
        ["git", "log", "-1", "--pretty=%s"],
        cwd=project_root,
    )
    skip_start_commit = (
        last_log.returncode == 0
        and last_log.stdout.strip() == f"mill-go: start batch {args.batch_name}"
    )

    if not skip_start_commit:
        result = _subprocess_util.run(
            ["git", "add", status_path.relative_to(project_root).as_posix(), str(snapshot_path.relative_to(project_root))],
            cwd=project_root,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return 1
        result = _subprocess_util.git_commit(
            project_root,
            f"mill-go: start batch {args.batch_name}",
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

    template_path = plugin_root / "templates" / "implementer-brief.md"
    prompt_text = _render.render(template_path, {
        "TASK_TITLE": task_title,
        "SLUG": slug,
        "BATCH_NAME": args.batch_name,
        "BATCH_FILE": str(batch_file),
        "OVERVIEW_FILE": str(overview_path),
        "PROJECT_ROOT": str(project_root),
        "WIKI_PATH": str(wiki_path),
        "SELF_FIX_ROUNDS": str(self_fix_rounds),
        "ROUND": "1",
        "SESSION_ID": session_id,
    })

    max_chars = cfg.get("llm", {}).get("max_implementer_prompt_chars", 0)
    if max_chars > 0 and len(prompt_text) > max_chars:
        print(json.dumps({"status": "stuck", "stuck_type": "transient", "reason": f"brief exceeds max_implementer_prompt_chars ({len(prompt_text)} chars)"}))
        return 0

    try:
        output, _ = _implementer_claude.run(
            prompt_text,
            model=impl_model,
            effort=impl_effort,
            session_id=session_id,
            resume=False,
            cwd=project_root,
            timeout=timeout,
        )
    except _llm_claude.LLMError as e:
        result = _subprocess_util.run(["git", "rev-list", "--count", f"{start_sha}..HEAD"], cwd=project_root)
        if result.returncode == 0:
            commits_made = int(result.stdout.strip())
        else:
            commits_made = 0
        print(json.dumps({"status": "stuck", "stuck_type": "transient", "reason": str(e), "commits_made": commits_made}))
        print(str(e), file=sys.stderr)
        return 1
    return _forward_output(output, project_root, start_sha=start_sha, snapshot_path=snapshot_path, session_id=session_id)


if __name__ == "__main__":
    sys.exit(main())
