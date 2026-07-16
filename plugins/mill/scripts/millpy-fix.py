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

import _agent_dispatch
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
from _implementer_common import (
    _forward_output,
    _has_windows_lock_error_signature,
    emit_prepare,
    finalize_from_output,
)
from wiki import WikiStartupError


def _is_windows_lock_error(e: Exception) -> bool:
    """
    Check if exception is a Windows file-locking error.

    Returns True if the exception is caused by a Windows file-locking issue:
    - OSError with winerror == 32 (process cannot access the file), OR
    - Error message contains Windows file-locking signature patterns
    """
    # Check for OSError with winerror == 32 (WinError 32)
    cause = getattr(e, "__cause__", None)
    if isinstance(cause, OSError) and getattr(cause, "winerror", None) == 32:
        return True

    # Delegate string-signature match to shared helper
    return _has_windows_lock_error_signature(str(e))


def _resolve_holistic_verify(
    batch_verifies: list[tuple[str, str, Path | None]],
) -> tuple[str, Path | None]:
    """
    Join a holistic scope's per-batch verify commands into one, enforcing a uniform cwd.

    Holistic-scope fixing runs every contributing batch's verify command as a
    single joined shell command (`" && ".join(...)`), and that joined command
    executes with exactly one subprocess `cwd`. When the batches resolve to
    more than one distinct non-None `cwd` (via the `verify: {cwd: hub|git_root,
    ...}` mapping form introduced by `_plan_dag.parse_verify_field`), no single
    subprocess `cwd` can satisfy all of them. That is a plan-authoring error --
    mixing `cwd: hub` and `cwd: git_root` batches into one holistic join --
    and must surface immediately rather than have the fixer silently pick one
    batch's cwd over another's.

    Args:
        batch_verifies: `(batch_name, command, cwd)` triples in DAG order, as
            returned by `_plan_dag.iter_batch_verifies`.

    Returns:
        `(joined_command, cwd_override)`. `joined_command` is every batch's
        command joined with `" && "`, in the same order as `batch_verifies`.
        `cwd_override` is the single distinct `cwd` shared by every batch that
        specified one, or `None` when every batch's cwd was `None` (i.e. every
        contributing batch used the plain-string `verify:` form).

    Raises:
        ValueError: More than one distinct non-None `cwd` value is present
            across `batch_verifies`. The message names each conflicting batch
            and the cwd it resolved to.
    """
    # Track each distinct non-None cwd in first-seen order, paired with the
    # batch name that specified it, so a conflict error can name the
    # disagreeing batches rather than just the cwd values.
    cwd_to_batch_name: dict[Path, str] = {}
    for batch_name, _command, cwd in batch_verifies:
        if cwd is not None and cwd not in cwd_to_batch_name:
            cwd_to_batch_name[cwd] = batch_name

    if len(cwd_to_batch_name) > 1:
        conflicts = ", ".join(
            f"{batch_name!r} -> {cwd}" for cwd, batch_name in cwd_to_batch_name.items()
        )
        raise ValueError(
            "holistic verify joining requires a single cwd across all contributing "
            f"batches, but found mixed cwd values: {conflicts}"
        )

    joined_command = " && ".join(command for _, command, _ in batch_verifies)
    # A single distinct cwd if any batch specified one, otherwise None (every
    # batch used the plain-string verify form with no cwd opinion).
    cwd_override = next(iter(cwd_to_batch_name), None)
    return joined_command, cwd_override


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
    parser.add_argument(
        "--stage",
        choices=["prepare", "finalize", "full"],
        default="full",
        help="Stage of execution: prepare (render brief), finalize (process output), or full (default, unchanged behavior).",
    )
    parser.add_argument(
        "--agent-output",
        help="Path to agent output file (required when --stage finalize).",
    )
    parser.add_argument(
        "--start-sha",
        default=None,
        help="SHA captured at prepare stage (from prepare envelope).",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Session ID from prepare envelope (for finalize stage).",
    )
    parser.add_argument(
        "--nits-only",
        action="store_true",
        help="Fix nits only (write nits-fixed marker if successful).",
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
    project_root = _paths.resolve_hub_path()
    mill_dir = project_root / ".millhouse"

    git_root = _paths.resolve_git_root()
    wiki_path = _paths.resolve_wiki_path(git_root)

    try:
        cfg = _review_common.load_config(git_root, mill_dir)
    except _review_common.ReviewError as e:
        print(str(e), file=sys.stderr)
        return 1

    name_result = _subprocess_util.run(
        ["git", "config", "--global", "--get", "user.name"], cwd=project_root
    )
    email_result = _subprocess_util.run(
        ["git", "config", "--global", "--get", "user.email"], cwd=project_root
    )
    git_name = name_result.stdout.strip()
    git_email = email_result.stdout.strip()
    if not git_name or not git_email:
        print(
            "git config --global user.name and user.email must be set", file=sys.stderr
        )
        return 1

    try:
        slug = _marker.slug_from_branch(git_root, wiki_path, cfg)
    except _marker.MarkerError as e:
        print(str(e), file=sys.stderr)
        return 1
    except WikiStartupError as e:
        print(f"wiki daemon unreachable: {e}", file=sys.stderr)
        return 1

    try:
        status_path = _paths.require_status_path(project_root, cfg)
    except _paths.TaskHubError as e:
        print(str(e), file=sys.stderr)
        return 1
    full = _status.read_full(status_path)
    task_title = full["yaml"].get("task", slug)
    branch = _status.read_branch(status_path, cfg=cfg, slug=slug)
    self_fix_rounds = (
        cfg.get("roles", {}).get("implementer", {}).get("self_fix_rounds", 2)
    )
    fixer_cfg = cfg.get("roles", {}).get("fixer", {})
    model_name = fixer_cfg.get("model", "haiku")
    try:
        registry = _reviewers.load(git_root)
        fixer_spec = _reviewers.resolve(registry, model_name)
    except _reviewers.ReviewerError as e:
        print(str(e), file=sys.stderr)
        return 1
    fixer_model = fixer_spec["model"]

    # Advisory-only: warn (stderr, non-blocking) when roles.fixer.model resolves
    # weaker than the code-review reviewer configured for this invocation's
    # scope. The two config keys are fully independent, so an operator
    # escalating the reviewer mid-task can silently leave the fixer on a
    # weaker model. An unresolvable reviewer name is validate_role_refs's
    # concern elsewhere, not this warning's -- swallow and move on.
    reviewer_name = (
        cfg.get("roles", {}).get("code-review", {}).get(args.scope, {}).get("reviewer")
    )
    if reviewer_name is not None:
        try:
            reviewer_spec = _reviewers.resolve(registry, reviewer_name)
        except _reviewers.ReviewerError:
            pass
        else:
            warning = _reviewers.fixer_weaker_than_reviewer_warning(
                fixer_spec,
                reviewer_spec,
                fixer_name=model_name,
                reviewer_name=reviewer_name,
                scope=args.scope,
            )
            if warning is not None:
                print(warning, file=sys.stderr)

    fixer_effort = fixer_spec.get("effort")
    timeout = fixer_spec.get("timeout") or cfg.get("llm", {}).get(
        "implementer_timeout", 1800
    )

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
        batches = _plan_dag.extract_batch_index(
            overview_path.read_text(encoding="utf-8")
        )
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

    # Stage: finalize
    if args.stage == "finalize":
        if not args.agent_output:
            print("--agent-output is required when --stage finalize", file=sys.stderr)
            return 1
        fixer_snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-fixer.txt"
        # Resolve verify command for batch/holistic fixes. cwd_override is
        # pre-initialized to None here (before branching on args.scope) because
        # the batch-scope read below is nested inside `if batch_entry is not
        # None:` and the holistic-scope read inside `if batch_verifies:` --
        # either guard can be false, leaving the pre-initialized None value,
        # exactly matching pre-#604 behavior.
        verify_cmd = None
        cwd_override = None
        if args.scope == "batch":
            batch_entry = next(
                (b for b in batches if b["name"] == args.batch_name), None
            )
            if batch_entry is not None:
                batch_file = plan_base / batch_entry["file"]
                batch_frontmatter = _plan_dag._read_batch_frontmatter(batch_file)
                verify_cmd, cwd_override = _plan_dag.parse_verify_field(
                    batch_frontmatter, project_root, git_root
                )
        elif args.scope == "holistic":
            # Derive concatenated verify_cmd from all batch verify commands in DAG order
            batch_verifies = _plan_dag.iter_batch_verifies(
                plan_base, project_root, git_root
            )
            if batch_verifies:
                verify_cmd, cwd_override = _resolve_holistic_verify(batch_verifies)
        nits_scope = args.batch_name if args.scope == "batch" else "holistic"
        return finalize_from_output(
            Path(args.agent_output),
            project_root,
            start_sha=args.start_sha,
            snapshot_path=fixer_snapshot_path if fixer_snapshot_path.exists() else None,
            session_id=args.session_id,
            verify_cmd=verify_cmd,
            nits_only=args.nits_only,
            status_path=status_path,
            nits_scope=nits_scope,
            git_root=git_root,
            cwd_override=cwd_override,
        )

    # Compute the fixer-brief carve-out clause once, from the already-parsed
    # --nits-only flag. This is the single source of truth both brief templates
    # render into their two zero-new-commit sentences, so the brief's wording can
    # never drift from _implementer_common.py's actual nits_only runtime guard
    # (which already allows a legitimate --nits-only no-op pass to report success
    # with zero new commits). The value carries its own leading punctuation and
    # terminal period so neither template branch needs to hardcode punctuation
    # after the token.
    nits_only_carveout = (
        ", unless every finding was a legitimate --nits-only no-op requiring no code change."
        if args.nits_only
        else "."
    )

    # Branch on scope (for prepare and full stages)
    if args.scope == "batch":
        # Per-batch fixer dispatch
        batch_entry = next((b for b in batches if b["name"] == args.batch_name), None)
        if batch_entry is None:
            print(f"batch {args.batch_name!r} not found in overview", file=sys.stderr)
            return 1

        batch_file = plan_base / batch_entry["file"]
        # Resolve batch verify command for batch-scope fixes
        batch_frontmatter = _plan_dag._read_batch_frontmatter(batch_file)
        verify_cmd, cwd_override = _plan_dag.parse_verify_field(
            batch_frontmatter, project_root, git_root
        )

        _status.set_batch_fields(
            status_path,
            args.batch_name,
            {
                "state": "fixing",
                "review_round": args.round,
                "review_file": str(review_file),
            },
        )
        _status.append_phase(
            status_path,
            f"fixing-{args.batch_name}-r{args.round}",
            _timestamp.now_utc_iso(),
        )

        result = _subprocess_util.run(
            [
                "git",
                "add",
                status_path.relative_to(project_root).as_posix(),
                review_file_arg,
            ],
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
                "LANGUAGE_SKILLS": _agent_dispatch.language_skills_directive(
                    batch_file
                ),
                "NITS_ONLY_CARVEOUT": nits_only_carveout,
            },
        )

    else:  # args.scope == "holistic"
        # Holistic fixer dispatch
        # Derive concatenated verify_cmd from all batch verify commands in DAG order
        batch_verifies = _plan_dag.iter_batch_verifies(
            plan_base, project_root, git_root
        )
        verify_cmd, cwd_override = (
            _resolve_holistic_verify(batch_verifies) if batch_verifies else (None, None)
        )
        batch_files_text = "\n".join(str(plan_base / b["file"]) for b in batches)

        _status.append_phase(status_path, "holistic-fixing", _timestamp.now_utc_iso())

        result = _subprocess_util.run(
            [
                "git",
                "add",
                status_path.relative_to(project_root).as_posix(),
                review_file_arg,
            ],
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
                "NITS_ONLY_CARVEOUT": nits_only_carveout,
            },
        )

    # Shared dispatch tail for both scopes
    _sha_result = _subprocess_util.run(["git", "rev-parse", "HEAD"], cwd=project_root)
    start_sha = _sha_result.stdout.strip() if _sha_result.returncode == 0 else None

    max_chars = cfg.get("llm", {}).get("max_implementer_prompt_chars", 0)
    if max_chars > 0 and len(prompt_text) > max_chars:
        print(
            json.dumps(
                {
                    "status": "stuck",
                    "stuck_type": "transient",
                    "reason": f"brief exceeds max_implementer_prompt_chars ({len(prompt_text)} chars)",
                }
            )
        )
        return 0

    # Stage: prepare
    if args.stage == "prepare":
        briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")
        model_tier = _agent_dispatch.model_to_tier(fixer_model)
        scope_label = args.batch_name if args.scope == "batch" else "holistic"
        return emit_prepare(
            briefs_dir,
            "fix",
            scope_label,
            args.round,
            prompt_text,
            model_tier,
            session_id,
            start_sha=start_sha,
            nits_only=args.nits_only,
            effort=fixer_effort,
        )

    # Stage: full (default)
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
        stuck_type = "verify" if _is_windows_lock_error(e) else "transient"
        if start_sha is None:
            commits_made = 0
        else:
            result = _subprocess_util.run(
                ["git", "rev-list", "--count", f"{start_sha}..HEAD"], cwd=project_root
            )
            if result.returncode == 0:
                commits_made = int(result.stdout.strip())
            else:
                commits_made = 0
        print(
            json.dumps(
                {
                    "status": "stuck",
                    "stuck_type": stuck_type,
                    "reason": str(e),
                    "commits_made": commits_made,
                }
            )
        )
        print(str(e), file=sys.stderr)
        return 1

    nits_scope = args.batch_name if args.scope == "batch" else "holistic"
    return _forward_output(
        output,
        project_root,
        start_sha=start_sha,
        session_id=session_id,
        verify_cmd=verify_cmd,
        nits_only=args.nits_only,
        status_path=status_path,
        nits_scope=nits_scope,
        git_root=git_root,
        cwd_override=cwd_override,
    )


if __name__ == "__main__":
    sys.exit(main())
