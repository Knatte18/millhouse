"""millpy-merge-in-subagent.py — merge-in conflict/verify-fix sub-agent dispatcher.

Dispatches a Sonnet sub-agent session to handle either merge conflict resolution
or verify-command failures after a merge. The Builder reads only the JSON verdict
on stdout; all context-heavy work happens inside the sub-agent session.

Flags:
    --mode conflicts|verify-fix   (required) which delegation mode to run

  conflicts mode:
    --files FILE [FILE ...]       paths of files with conflict markers

  verify-fix mode:
    --cmd CMD                     the verify command to re-run
    --checkpoint SHA              git SHA of the merge commit; used to diff
                                  what the merge changed

Exit codes:
    0 — sub-agent ran; JSON verdict on stdout (success or stuck)
    1 — pre-launch error (missing required flags, bad config, git failure);
        message on stderr, no JSON on stdout
"""
from __future__ import annotations

import argparse
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
import _paths
import _render
import _review_common
import _reviewers
from _implementer_common import _forward_output, emit_prepare, emit_prepare_no_dispatch, finalize_from_output


# DU-conflict resolution needs branch intent; the resolver had no signal before #314.
def _collect_task_intent(project_root: Path) -> str:
    """
    Gather task-intent excerpts from discussion.md and plan/*.md files.

    Returns a string containing excerpts from this branch's _mill/discussion.md
    and _mill/plan/*.md that describe the branch's intent. Extracts the top
    YAML block and the Edits/Creates/Deletes bullets from each plan file.
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Dispatch a Sonnet sub-agent for merge-in conflict or verify-fix work."
    )
    parser.add_argument(
        "--mode",
        required=True,
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
        "--checkpoint",
        default=None,
        help="(verify-fix mode) Git SHA of the merge commit.",
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
    args = parser.parse_args(argv)

    # Common setup
    project_root = Path.cwd()
    mill_dir = project_root / ".millhouse"
    plugin_root = Path(__file__).resolve().parent.parent

    git_root = _paths.resolve_git_root()
    wiki_path = _paths.resolve_wiki_path(git_root)

    try:
        cfg = _review_common.load_config(git_root, mill_dir)
    except _review_common.ReviewError as e:
        print(str(e), file=sys.stderr)
        return 1

    try:
        _marker.slug_from_branch(git_root, wiki_path, cfg)
    except _marker.MarkerError as e:
        print(str(e), file=sys.stderr)
        return 1

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
            post_verify_result = subprocess.run(
                args.cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=project_root,
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
        return emit_prepare(briefs_dir, "merge", "conflicts", 1, prompt_text, model_tier, session_id)

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

    return _forward_output(output, project_root)


def _run_verify_fix(args, project_root: Path, plugin_root: Path, cfg: dict, timeout: int, impl_model: str, impl_effort: str | None, stage: str = "full") -> int:
    if args.cmd is None:
        print("--cmd is required for verify-fix mode", file=sys.stderr)
        return 1
    if args.checkpoint is None:
        print("--checkpoint is required for verify-fix mode", file=sys.stderr)
        return 1

    # Shell-escaped user verify command — _subprocess_util.run does not support shell=True.
    result = subprocess.run(
        args.cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=project_root,
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
        return emit_prepare(briefs_dir, "merge", "verify-fix", 1, prompt_text, model_tier, session_id)

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
    post_verify_result = subprocess.run(
        args.cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=project_root,
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
