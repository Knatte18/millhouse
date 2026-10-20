"""millpy-merge-in-subagent.py — merge-in conflict/verify-fix sub-agent dispatcher.

Dispatches a Sonnet sub-agent session to handle either merge conflict resolution or verify-command
failures after a merge.
The Builder reads only the JSON verdict on stdout;
all context-heavy work happens inside the sub-agent session.

Flags:
    --mode conflicts|verify-fix which delegation mode to run; required

  conflicts mode:
    --files FILE [FILE ...]
    paths of files with conflict markers

  verify-fix mode:
    --cmd CMD the verify command to re-run
    --label LABEL label for the verify runner's log lines and Verify log rows
    --checkpoint SHA git SHA of the merge commit; used to diff what the merge changed

  A timed-out or unlaunchable verify command prints a stuck envelope without dispatching the
  sub-agent.
  Verify-fix envelopes carry "verify_runs", the summaries of the verify runs made.

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
import os
import re
import _subprocess_util
import sys
import uuid
from pathlib import Path

import _agent_dispatch
import _implementer_claude
import _llm_claude
import _marker
import _paths
import _render
import _review_common
import _reviewers
import _verify_run
from _implementer_common import (
    _extract_status_json,
    _forward_output,
    _truncate_verify_output,
    emit_prepare,
    emit_prepare_no_dispatch,
    finalize_from_output,
)


# DU-conflict resolution needs branch intent; the resolver had no signal before #314.
def _collect_task_intent(project_root: Path) -> str:
    """
    Gather task-intent excerpts from discussion.md and plan/*.md files.

    Returns a string containing excerpts from this branch's _mill/discussion.md and _mill/plan/*.md
    that describe the branch's intent.
    Extracts the top YAML block and the Edits/Creates/Deletes/Moves bullets from each plan file.
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
                if re.match(r"^-\s*\*\*(Edits|Creates|Deletes|Moves):\*\*", line):
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


def _generous_terminal_env() -> dict:
    """
    Build a subprocess environment with a generous floor on ``COLUMNS``/``LINES``.

    A headless orchestrating process (this script) inherits no real terminal geometry, unlike an
    interactive shell.
    A ``verify:`` command that drives a tmux-based smoke test can misjudge available pane space
    from that absent/tiny geometry and fail with a "no space for new pane" error unrelated to the
    actual code under test.
    Raises ``COLUMNS``/``LINES`` to a generous floor only when the inherited value is smaller,
    leaving any larger inherited value untouched;
    a no-op for any verify command that does not consult terminal geometry.

    Returns:
        A copy of ``os.environ`` with ``COLUMNS``/``LINES`` raised to the floor when needed.
    """
    env = dict(os.environ)
    for var, floor in (("COLUMNS", 220), ("LINES", 50)):
        try:
            current = int(env.get(var, "0"))
        except ValueError:
            current = 0
        if current < floor:
            env[var] = str(floor)
    return env


def _run_merge_verify(
    cmd: str,
    label: str,
    project_root: Path,
    git_root: Path,
    timeout_s: float,
    status_path: Path | None,
) -> _verify_run.VerifyRun:
    """
    Run one merge-in verify command through the shared verify runner.

    The command runs through bash in ``project_root`` with a generous terminal geometry
    environment, a ``timeout_s`` kill, and a Verify log row appended to ``status_path`` when given.

    Returns:
        The ``VerifyRun`` record; failure, timeout and launch failure are reported in it.
    """
    return _verify_run.run_verify(
        cmd,
        cwd=project_root,
        label=label,
        git_root=git_root,
        timeout_s=timeout_s,
        shell_mode="posix",
        env=_generous_terminal_env(),
        status_path=status_path,
    )


def _verify_stuck_envelope(run: _verify_run.VerifyRun) -> dict | None:
    """
    Build the stuck envelope for a verify run that no code change can fix.

    Returns:
        A ``stuck_type: verify`` dict for a timed-out run (with ``timed_out: true``) or for a
        launch failure, or ``None`` when the command ran to an exit code.
    """
    if run.timed_out:
        return {
            "status": "stuck",
            "stuck_type": "verify",
            "timed_out": True,
            "reason": _verify_run.timeout_prefix(run)
            + _truncate_verify_output(run.output.strip())
            + _verify_run.output_suffix(run),
        }
    if run.exit_code is None:
        return {
            "status": "stuck",
            "stuck_type": "verify",
            "reason": f"verify gate raised: {run.output}",
        }
    return None


def _run_summaries(runs: list[_verify_run.VerifyRun]) -> list[dict]:
    """Return the loggable ``summary()`` dict of each verify run."""
    return [run.summary() for run in runs]


def _print_envelope_with_runs(envelope: dict, runs: list[_verify_run.VerifyRun]) -> None:
    """Print ``envelope`` as one JSON line carrying the summaries of the verify ``runs``."""
    print(json.dumps({**envelope, "verify_runs": _run_summaries(runs)}))


def _success_envelope(project_root: Path) -> dict:
    """Build the success envelope carrying the current HEAD sha of ``project_root``."""
    sha_result = _subprocess_util.run(["git", "rev-parse", "HEAD"], cwd=project_root)
    sha = sha_result.stdout.strip() if sha_result.returncode == 0 else ""
    return {"status": "success", "commit_sha": sha}


def _print_post_fix_envelope(runs: list[_verify_run.VerifyRun], project_root: Path) -> int:
    """
    Print the final verify-fix envelope from the post-fix verify run, the last of ``runs``.

    A pass prints success; a timeout, launch failure or non-zero exit prints a stuck envelope.
    Always returns 0, the exit code for a delivered verdict.
    """
    run = runs[-1]
    envelope = _verify_stuck_envelope(run)
    if envelope is None and run.exit_code == 0:
        envelope = _success_envelope(project_root)
    if envelope is None:
        envelope = {
            "status": "stuck",
            "stuck_type": "verify",
            "reason": _truncate_verify_output(run.output.strip()) + _verify_run.output_suffix(run),
        }
    _print_envelope_with_runs(envelope, runs)
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
        "--label",
        default="merge-in:verify-fix",
        help="(verify-fix mode) Label for the verify runner's log lines and Verify log rows; the SKILL passes merge-in:<batch>.",
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
    if not args.mode:
        print("--mode is required", file=sys.stderr)
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

    try:
        verify_timeout_s = _verify_run.timeout_seconds(cfg)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    status_path = _verify_run.resolve_status_path(project_root, cfg)

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
            post_verify_run = _run_merge_verify(
                args.cmd, f"{args.label}:post-fix", project_root, git_root, verify_timeout_s, status_path
            )
            return _print_post_fix_envelope([post_verify_run], project_root)
        elif args.mode == "conflicts":
            # Replicate finalize_from_output's own is_file() guard inline -- that guard is unreachable on the gate-fail branch below, so a missing --agent-output file must not crash with a raw FileNotFoundError here.
            if not Path(args.agent_output).is_file():
                print(
                    f"ERROR: --agent-output file not found: {args.agent_output} -- for"
                    " implementer/fixer/merge-in dispatches the orchestrator must write the"
                    " subagent report message to this path before calling --stage finalize",
                    file=sys.stderr,
                )
                return 1
            if not args.files:
                print("--files is required for conflicts mode", file=sys.stderr)
                return 1
            # Mirror finalize_from_output's own read: unescape HTML entities, which may appear when the text came from a <task-notification> payload, before parsing.
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
            commit_sha_field_name="pre_merge_head",
        )

    timeout = cfg.get("llm", {}).get("implementer_timeout", 1800)
    implementer_cfg = cfg.get("roles", {}).get("implementer", {})
    merge_cfg = cfg.get("merge", {})
    if args.mode == "conflicts":
        model_name = (
            merge_cfg.get("conflicts_model")
            or merge_cfg.get("model")
            or implementer_cfg.get("model", "haiku")
        )
    else:
        model_name = merge_cfg.get("model") or implementer_cfg.get("model", "haiku")
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
        return _run_verify_fix(
            args, project_root, plugin_root, cfg, timeout, impl_model, impl_effort,
            stage=args.stage,
            git_root=git_root,
            verify_timeout_s=verify_timeout_s,
            status_path=status_path,
        )


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

    return _forward_output(output, project_root, commit_sha_field_name="pre_merge_head")


def _run_verify_fix(
    args,
    project_root: Path,
    plugin_root: Path,
    cfg: dict,
    timeout: int,
    impl_model: str,
    impl_effort: str | None,
    stage: str = "full",
    *,
    git_root: Path,
    verify_timeout_s: float,
    status_path: Path | None,
) -> int:
    if args.cmd is None:
        print("--cmd is required for verify-fix mode", file=sys.stderr)
        return 1
    # Note: --checkpoint is only consumed by full mode (line 299) for git diff.
    # prepare and finalize stages do not require it.
    if args.checkpoint is None and stage == "full":
        print("--checkpoint is required for verify-fix full mode", file=sys.stderr)
        return 1

    result = _run_merge_verify(
        args.cmd, args.label, project_root, git_root, verify_timeout_s, status_path
    )
    runs = [result]

    # A timeout or launch failure is not something a code change can fix, so the fixer is never dispatched.
    stuck = _verify_stuck_envelope(result)
    if stuck is not None:
        _print_envelope_with_runs(stuck, runs)
        return 0

    # Stage: prepare (special case: verify passes)
    if stage == "prepare" and result.exit_code == 0:
        model_tier = _agent_dispatch.model_to_tier(impl_model)
        session_id = str(uuid.uuid4())
        return emit_prepare_no_dispatch(
            model_tier, session_id, "merge", "verify-fix", 1, project_root,
            verify_runs=_run_summaries(runs),
        )

    if result.exit_code == 0:
        _print_envelope_with_runs(_success_envelope(project_root), runs)
        return 0

    verify_output = result.output.strip()

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
        return emit_prepare(
            briefs_dir, "merge", "verify-fix", 1, prompt_text, model_tier, session_id,
            effort=impl_effort, verify_runs=_run_summaries(runs),
        )

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
    runs.append(
        _run_merge_verify(
            args.cmd, f"{args.label}:post-fix", project_root, git_root, verify_timeout_s, status_path
        )
    )
    return _print_post_fix_envelope(runs, project_root)


if __name__ == "__main__":
    sys.exit(main())
