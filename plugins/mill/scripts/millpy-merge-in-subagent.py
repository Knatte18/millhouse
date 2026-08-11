"""millpy-merge-in-subagent.py — merge-in conflict/verify-fix sub-agent dispatcher.

Dispatches a Sonnet sub-agent session to handle either merge conflict resolution or verify-command
failures after a merge.
The Builder reads only the JSON verdict on stdout;
all context-heavy work happens inside the sub-agent session.

Flags:
    --mode conflicts|verify-fix which delegation mode to run; required unless --recompute-baseline
        is set
    --recompute-baseline reset and eagerly recompute the cached module_verify_baseline after a
        successful parent-branch sync.
        Independent of --mode;
        a synchronous computation with no LLM session involved.

  conflicts mode:
    --files FILE [FILE ...]
    paths of files with conflict markers

  verify-fix mode:
    --cmd CMD the verify command to re-run --checkpoint SHA git SHA of the merge commit; used to
    diff what the merge changed

Exit codes:
    0 — sub-agent ran;
        JSON verdict on stdout (success or stuck)
    1 — pre-launch error (missing required flags, bad config, git failure);
        message on stderr, no JSON on stdout
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import _subprocess_util
import sys
import uuid
from pathlib import Path

import _agent_dispatch
import _implementer_claude
import _llm_claude
import _marker
import _parent_branch
import _paths
import _plan_dag
import _render
import _review_common
import _reviewers
import _status
import _verify_baseline
from _implementer_common import _extract_status_json, _forward_output, _posix_shell_run_args, emit_prepare, emit_prepare_no_dispatch, finalize_from_output


# DU-conflict resolution needs branch intent; the resolver had no signal before #314.
def _collect_task_intent(project_root: Path) -> str:
    """
    Gather task-intent excerpts from discussion.md and plan/*.md files.

    Returns a string containing excerpts from this branch's _mill/discussion.md and _mill/plan/*.md
    that describe the branch's intent.
    Extracts the top YAML block and the Edits/Creates/Deletes bullets from each plan file.
    Returns empty string if _mill directory does not exist.
    """
    mill_dir = project_root / "_mill"
    if not mill_dir.is_dir():
        return ""

    output: list[str] = []

    # Add discussion.md if present
    discussion_file = mill_dir / "discussion.md"
    if discussion_file.is_file():
        discussion_content = discussion_file.read_text(encoding="utf-8")
        output.append(f"### From discussion.md\n\n{discussion_content}")

    # Add plan files
    plan_dir = mill_dir / "plan"
    if plan_dir.is_dir():
        for plan_file in sorted(plan_dir.glob("*.md")):
            plan_content = plan_file.read_text(encoding="utf-8")

            # Extract top YAML block (between ``` ```yaml ``` ``` and the next ``` ```)
            yaml_match = re.search(r"(```yaml.*?```)", plan_content, re.DOTALL)
            yaml_block = yaml_match.group(1) if yaml_match else ""

            # Extract Edits/Creates/Deletes bullets
            header_lines: list[str] = []
            lines = plan_content.splitlines()
            for i, line in enumerate(lines):
                if re.match(r"^-\s*\*\*(Edits|Creates|Deletes):\*\*", line):
                    header_lines.append(line)
                    # Check for sub-bullets
                    j = i + 1
                    while j < len(lines):
                        if re.match(r"^\s+-\s*(.+)$", lines[j]):
                            header_lines.append(lines[j])
                            j += 1
                        else:
                            break

            bullets_text = "\n".join(header_lines)

            if yaml_block or bullets_text:
                filename = plan_file.name
                output.append(f"### From _mill/plan/{filename}\n")
                if yaml_block:
                    output.append(yaml_block)
                if bullets_text:
                    if yaml_block:
                        output.append("")
                    output.append(bullets_text)

    return "\n\n".join(output)


def _verify_conflict_markers(files: list[str], project_root: Path) -> dict | None:
    """
    Verify that none of ``files`` still carries an unresolved merge conflict after a conflicts-mode
    sub-agent self-reports success (#713).

    A sub-agent's own ``{"status": "success"}`` claim is not proof: it may have edited a file
    without ever running ``git add`` on it,
    or it may have left ``<<<<<<<``/``=======``/``>>>>>>>`` markers in place while still staging the
    file.
    This function runs two independent git checks, both scoped to ``files`` and both always executed
    (neither short-circuits the other), to catch either failure mode before the caller's success
    envelope reaches the Builder:

    1. ``git diff --name-only --diff-filter=U`` — lists paths still marked unmerged in the index.
        Any of ``files`` appearing here was never staged at all (same idiom as
            ``mill-merge-in/SKILL.md`` step 3 and ``millpy-wikipush.py``'s dirty-wiki check).
    2. ``git diff --cached --check`` — greps the staged diff for git's own ``"conflict marker"``
        warning, which fires when a staged hunk still contains literal marker lines.

    A file resolved via ``git rm`` (a modify/delete resolution) needs no special-casing: it is
    absent from both check outputs by construction -- already resolved out of check 1's unmerged
    list,
    and nothing left to diff for check 2.

    Args:
        files: Paths (relative to ``project_root``) the sub-agent claimed to have resolved.
        project_root: Absolute path to the git worktree these checks run against.

    Returns:
        ``None`` when both checks are clean.
        Otherwise a ``{"status": "stuck", "stuck_type": "logic", "reason": ...}`` dict the caller
        substitutes for the sub-agent's own success envelope -- either because a check found a real
        marker/staging problem, or because a check's own git invocation failed (e.g.
        lock contention), signaled by a ``"fatal:"`` prefix in its output, which makes that check's
        finding untrustworthy and short-circuits immediately ahead of the two ordinary findings.
    """
    unmerged_result = _subprocess_util.run(
        ["git", "diff", "--name-only", "--diff-filter=U", "--", *files],
        cwd=project_root,
    )
    unmerged_combined = unmerged_result.stdout + unmerged_result.stderr
    if "fatal:" in unmerged_combined:
        return {
            "status": "stuck",
            "stuck_type": "logic",
            "reason": f"conflict-marker verification itself failed to run: {unmerged_combined}",
        }

    marker_result = _subprocess_util.run(
        ["git", "diff", "--cached", "--check", "--", *files],
        cwd=project_root,
    )
    marker_combined = marker_result.stdout + marker_result.stderr
    if "fatal:" in marker_combined:
        return {
            "status": "stuck",
            "stuck_type": "logic",
            "reason": f"conflict-marker verification itself failed to run: {marker_combined}",
        }

    # Check 1: any of our files still listed as unmerged means it was never staged.
    unmerged_files = [f for f in files if f in unmerged_result.stdout.splitlines()]

    # Check 2: any "conflict marker" line in the staged diff means markers survived staging.
    marker_lines = [
        line for line in marker_combined.splitlines() if "conflict marker" in line
    ]

    clauses = []
    if unmerged_files:
        clauses.append(f"file(s) never staged / still unmerged: {', '.join(unmerged_files)}")
    if marker_lines:
        clauses.append(f"residual conflict markers found in staged files: {', '.join(marker_lines)}")

    if clauses:
        return {"status": "stuck", "stuck_type": "logic", "reason": "; ".join(clauses)}

    return None


def _run_recompute_baseline(project_root: Path, git_root: Path, cfg: dict) -> int:
    """
    Reset and eagerly recompute the cached ``module_verify_baseline`` after a successful
    parent-branch sync in ``mill-merge-in``.

    Mirrors ``millpy-implement.py``'s ``_run_baseline_stage`` in structure and error-handling shape
    -- the two functions compute the same thing from two different entry points (task-start
    pre-flight vs. post-merge-in recompute) -- but always clears the cached value first (via
    ``_status.clear_module_verify_baseline``) so a stale, already-cached baseline from before the
    merge is never reused: ``--stage baseline``'s own idempotent no-op-if-cached behavior is exactly
    why a bare call to it would not recompute after a merge-in without this explicit reset.

    Never raises -- every failure path (no module-wide verify configured, parent branch
    unresolvable, status.md absent, or the computation itself raising) prints a JSON line
    describing the outcome and returns 0 without blocking the merge-in;
    a baseline-recompute failure must never fail an otherwise successful merge.

    Args:
        project_root: Absolute path to the task worktree root.
        git_root: Absolute path to the repo root ``git`` commands run against.
        cfg: Already-loaded mill config dict (avoids a redundant reload).

    Returns:
        Always 0 -- outcomes are communicated through the printed JSON line.
    """
    try:
        status_path = _paths.require_status_path(project_root, cfg)
    except Exception as e:
        print(json.dumps({"status": "success", "baseline": "error", "reason": str(e)}))
        return 0

    plan_dir = cfg.get("paths", {}).get("plan_dir", "_mill/plan/")
    plan_base = _paths.resolve_task_path(project_root, plan_dir)
    overview_path = plan_base / "00-overview.md"
    overview_frontmatter = _plan_dag._read_batch_frontmatter(overview_path)
    module_wide_verify_cmd = overview_frontmatter.get("verify") or None

    if module_wide_verify_cmd is None:
        print(
            json.dumps(
                {
                    "status": "success",
                    "baseline": "skipped",
                    "reason": "no module-wide verify configured",
                }
            )
        )
        return 0

    # Reset: force recomputation regardless of any currently-cached value.
    _status.clear_module_verify_baseline(status_path)

    try:
        parent_branch = _parent_branch.resolve(status_path, interactive=False)
    except Exception as e:
        print(json.dumps({"status": "success", "baseline": "error", "reason": str(e)}))
        return 0

    try:
        result = _verify_baseline.compute_baseline(
            project_root, git_root, parent_branch, module_wide_verify_cmd
        )
    except Exception as e:
        print(f"[millpy-merge-in-subagent] baseline recompute failed: {e}", file=sys.stderr)
        print(json.dumps({"status": "success", "baseline": "error", "reason": str(e)}))
        return 0

    _status.set_module_verify_baseline(status_path, result)
    print(json.dumps({"status": "success", "baseline": "computed", "value": result}))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Dispatch a Sonnet sub-agent for merge-in conflict or verify-fix work."
    )
    parser.add_argument(
        "--mode",
        required=False,
        choices=["conflicts", "verify-fix"],
        help="Delegation mode: 'conflicts' or 'verify-fix'.",
    )
    parser.add_argument(
        "--recompute-baseline",
        action="store_true",
        help="Reset and eagerly recompute the cached module_verify_baseline after a successful parent-branch sync. Independent of --mode; when set, --mode is not required and no other mode-specific flag is consulted.",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        default=None,
        help="(conflicts mode) Paths of files with conflict markers.",
    )
    parser.add_argument(
        "--cmd",
        default=None,
        help="(verify-fix mode) The verify command to run.",
    )
    parser.add_argument(
        "--checkpoint",
        default=None,
        help="(verify-fix mode, full stage only) Git SHA of the merge commit; used in full mode to diff what the merge changed.",
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
        "--session-id",
        default=None,
        help="Accepted for CLI-shape parity with millpy-fix.py / millpy-implement.py; ignored in all stages -- conflicts-mode finalize delegates to finalize_from_output(..., session_id=None) and verify-fix finalize re-runs --cmd directly.",
    )
    parser.add_argument(
        "--start-sha",
        default=None,
        help="Accepted for CLI-shape parity with millpy-fix.py / millpy-implement.py; ignored in all stages.",
    )
    parser.add_argument(
        "--round",
        default=None,
        help="Accepted for CLI-shape parity with millpy-fix.py / millpy-implement.py; ignored in all stages.",
    )
    args = parser.parse_args(argv)
    if not args.recompute_baseline and not args.mode:
        print("--mode is required unless --recompute-baseline is set", file=sys.stderr)
        return 1

    # Common setup
    project_root = _paths.resolve_hub_path()
    mill_dir = project_root / ".millhouse"
    plugin_root = Path(__file__).resolve().parent.parent

    git_root = _paths.resolve_git_root()
    wiki_path = _paths.resolve_wiki_path(git_root)

    try:
        cfg = _review_common.load_config(project_root, mill_dir)
    except _review_common.ReviewError as e:
        print(str(e), file=sys.stderr)
        return 1

    try:
        slug = _marker.slug_from_branch(git_root, wiki_path, cfg)
    except _marker.MarkerError as e:
        print(str(e), file=sys.stderr)
        return 1

    container_path = _paths.resolve_container_path(git_root)
    project_root = _paths.resolve_active_hub(
        container_path, slug, cfg=cfg, git_root=git_root, skip_slug_validation=True
    )
    mill_dir = project_root / ".millhouse"
    # Reload against the resolve_active_hub()-corrected root -- the bootstrap cfg above may have come from a different (e.g.
    # primary-clone template) config than the task hub's own mill-config.yaml.
    # Downstream consumers (verify-cwd resolution, conflict handling, finalize dispatch) must observe this corrected value, per cfg-reload-after-active-hub.
    cfg = _review_common.load_config(project_root, mill_dir)

    if args.recompute_baseline:
        return _run_recompute_baseline(project_root, git_root, cfg)

    # Stage: finalize (early exit before mode-specific logic)
    if args.stage == "finalize":
        if not args.agent_output:
            print("--agent-output is required when --stage finalize", file=sys.stderr)
            return 1
        if args.mode == "verify-fix":
            if args.cmd is None:
                print("--cmd is required for verify-fix mode", file=sys.stderr)
                return 1
            # Re-run verify command before finalizing
            _run_args, _run_kwargs = _posix_shell_run_args(args.cmd)
            post_verify_result = subprocess.run(
                _run_args,
                capture_output=True,
                text=True,
                cwd=project_root,
                **_run_kwargs,
            )
            # Case A: verify passes with no fixer needed (initial verify was 0)
            # Case B: fixer ran, post-fix verify passes
            if post_verify_result.returncode == 0:
                sha_result = _subprocess_util.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=project_root,
                )
                sha = sha_result.stdout.strip() if sha_result.returncode == 0 else ""
                print(json.dumps({"status": "success", "commit_sha": sha}))
                return 0
            # Case C: fixer ran, post-fix verify still fails
            verify_output = (post_verify_result.stdout + post_verify_result.stderr).strip()
            print(json.dumps({"status": "stuck", "stuck_type": "verify", "reason": verify_output}))
            return 0
        elif args.mode == "conflicts":
            # Replicate finalize_from_output's own is_file() guard inline -- that guard is unreachable on the gate-fail branch below, so a missing --agent-output file must not crash with a raw FileNotFoundError here.
            if not Path(args.agent_output).is_file():
                print(
                    f"ERROR: --agent-output file not found: {args.agent_output} -- for"
                    " implementer/fixer/merge-in dispatches the orchestrator must write the"
                    " notification message to this path before calling --stage finalize",
                    file=sys.stderr,
                )
                return 1
            if not args.files:
                print("--files is required for conflicts mode", file=sys.stderr)
                return 1
            # Mirror finalize_from_output's own read: unescape the HTML entities the harness injects into the <task-notification> payload before parsing.
            output = html.unescape(Path(args.agent_output).read_text(encoding="utf-8"))
            self_reported = _extract_status_json(output)
            if self_reported is not None and self_reported.get("status") == "success":
                gate_result = _verify_conflict_markers(args.files, project_root)
                if gate_result is not None:
                    print(json.dumps(gate_result))
                    return 0
        return finalize_from_output(
            Path(args.agent_output),
            project_root,
            start_sha=None,
            snapshot_path=None,
            session_id=None,
        )

    timeout = cfg.get("llm", {}).get("implementer_timeout", 1800)
    implementer_cfg = cfg.get("roles", {}).get("implementer", {})
    model_name = cfg.get("merge", {}).get("model") or implementer_cfg.get("model", "haiku")
    try:
        registry = _reviewers.load(git_root)
        impl_spec = _reviewers.resolve(registry, model_name)
    except _reviewers.ReviewerError as e:
        print(str(e), file=sys.stderr)
        return 1
    impl_model = impl_spec["model"]
    impl_effort = impl_spec.get("effort")

    if args.mode == "conflicts":
        return _run_conflicts(args, project_root, plugin_root, cfg, timeout, impl_model, impl_effort, stage=args.stage)
    else:
        return _run_verify_fix(args, project_root, plugin_root, cfg, timeout, impl_model, impl_effort, stage=args.stage)


def _run_conflicts(args, project_root: Path, plugin_root: Path, cfg: dict, timeout: int, impl_model: str, impl_effort: str | None, stage: str = "full") -> int:
    if not args.files:
        print("--files is required for conflicts mode", file=sys.stderr)
        return 1

    conflicting_files = "\n".join(f"- `{f}`" for f in args.files)
    task_intent = _collect_task_intent(project_root)

    template_path = plugin_root / "templates" / "merge-in-conflict-brief.md"
    prompt_text = _render.render(template_path, {
        "CONFLICTING_FILES": conflicting_files,
        "PROJECT_ROOT": str(project_root),
        "TASK_INTENT": task_intent,
    })

    # Stage: prepare
    if stage == "prepare":
        briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")
        model_tier = _agent_dispatch.model_to_tier(impl_model)
        session_id = str(uuid.uuid4())
        return emit_prepare(briefs_dir, "merge", "conflicts", 1, prompt_text, model_tier, session_id, effort=impl_effort)

    # Stage: full (default)
    try:
        output, _ = _implementer_claude.run(
            prompt_text,
            model=impl_model,
            effort=impl_effort,
            session_id=None,
            resume=False,
            cwd=project_root,
            timeout=timeout,
        )
    except _llm_claude.LLMError as e:
        print(json.dumps({"status": "stuck", "stuck_type": "transient", "reason": str(e)}))
        print(str(e), file=sys.stderr)
        return 1

    # Gate: a sub-agent's own success self-report is not proof that every conflicting file was actually resolved and staged clean -- verify before letting the success envelope reach the Builder (#713).
    self_reported = _extract_status_json(output)
    if self_reported is not None and self_reported.get("status") == "success":
        gate_result = _verify_conflict_markers(args.files, project_root)
        if gate_result is not None:
            print(json.dumps(gate_result))
            return 0

    return _forward_output(output, project_root)


def _run_verify_fix(args, project_root: Path, plugin_root: Path, cfg: dict, timeout: int, impl_model: str, impl_effort: str | None, stage: str = "full") -> int:
    if args.cmd is None:
        print("--cmd is required for verify-fix mode", file=sys.stderr)
        return 1
    # Note: --checkpoint is only consumed by full mode (line 299) for git diff.
    # prepare and finalize stages do not require it.
    if args.checkpoint is None and stage == "full":
        print("--checkpoint is required for verify-fix full mode", file=sys.stderr)
        return 1

    # Shell-escaped user verify command — _subprocess_util.run does not support shell=True.
    _run_args, _run_kwargs = _posix_shell_run_args(args.cmd)
    result = subprocess.run(
        _run_args,
        capture_output=True,
        text=True,
        cwd=project_root,
        **_run_kwargs,
    )

    # Stage: prepare (special case: verify passes)
    if stage == "prepare" and result.returncode == 0:
        briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")
        model_tier = _agent_dispatch.model_to_tier(impl_model)
        session_id = str(uuid.uuid4())
        return emit_prepare_no_dispatch(model_tier, session_id, "merge", "verify-fix", 1, project_root)

    if result.returncode == 0:
        sha_result = _subprocess_util.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
        )
        sha = sha_result.stdout.strip() if sha_result.returncode == 0 else ""
        print(json.dumps({"status": "success", "commit_sha": sha}))
        return 0

    verify_output = (result.stdout + result.stderr).strip()

    diff_result = _subprocess_util.run(
        ["git", "diff", f"{args.checkpoint}..HEAD"],
        cwd=project_root,
    )
    merge_diff = diff_result.stdout if diff_result.returncode == 0 else "(diff unavailable)"

    verify_fix_rounds = cfg.get("merge", {}).get("verify_fix_rounds", 3)

    template_path = plugin_root / "templates" / "merge-in-verify-brief.md"
    prompt_text = _render.render(template_path, {
        "VERIFY_CMD": args.cmd,
        "VERIFY_OUTPUT": verify_output,
        "MERGE_DIFF": merge_diff,
        "VERIFY_FIX_ROUNDS": str(verify_fix_rounds),
        "PROJECT_ROOT": str(project_root),
    })

    # Stage: prepare (verify failed, need to dispatch)
    if stage == "prepare":
        briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")
        model_tier = _agent_dispatch.model_to_tier(impl_model)
        session_id = str(uuid.uuid4())
        return emit_prepare(briefs_dir, "merge", "verify-fix", 1, prompt_text, model_tier, session_id, effort=impl_effort)

    # Stage: full (default)
    try:
        output, _ = _implementer_claude.run(
            prompt_text,
            model=impl_model,
            effort=impl_effort,
            session_id=None,
            resume=False,
            cwd=project_root,
            timeout=timeout,
        )
    except _llm_claude.LLMError as e:
        print(json.dumps({"status": "stuck", "stuck_type": "transient", "reason": str(e)}))
        print(str(e), file=sys.stderr)
        return 1

    # Post-sub-agent re-verification (only in full mode)
    _run_args, _run_kwargs = _posix_shell_run_args(args.cmd)
    post_verify_result = subprocess.run(
        _run_args,
        capture_output=True,
        text=True,
        cwd=project_root,
        **_run_kwargs,
    )

    # Case B: fixer ran, post-fix verify passes
    if post_verify_result.returncode == 0:
        sha_result = _subprocess_util.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
        )
        sha = sha_result.stdout.strip() if sha_result.returncode == 0 else ""
        print(json.dumps({"status": "success", "commit_sha": sha}))
        return 0

    # Case C: fixer ran, post-fix verify still fails
    verify_output = (post_verify_result.stdout + post_verify_result.stderr).strip()
    print(json.dumps({"status": "stuck", "stuck_type": "verify", "reason": verify_output}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
