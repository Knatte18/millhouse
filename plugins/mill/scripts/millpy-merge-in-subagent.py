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
import subprocess
import _subprocess_util
import sys
from pathlib import Path

import _implementer_claude
import _llm_claude
import _marker
import _paths
import _render
import _review_common
import _reviewers
from _implementer_common import _forward_output


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
    args = parser.parse_args(argv)

    # Common setup
    project_root = Path.cwd()
    mill_dir = project_root / ".millhouse"
    plugin_root = Path(__file__).resolve().parent.parent

    git_root = _paths.resolve_git_root()
    wiki_path = _paths.resolve_wiki_path(git_root)

    try:
        cfg = _review_common.load_config(wiki_path, mill_dir)
    except _review_common.ReviewError as e:
        print(str(e), file=sys.stderr)
        return 1

    try:
        _marker.slug_from_branch(git_root, wiki_path, cfg)
    except _marker.MarkerError as e:
        print(str(e), file=sys.stderr)
        return 1

    timeout = cfg.get("llm", {}).get("implementer_timeout", 1800)
    implementer_cfg = cfg.get("roles", {}).get("implementer", {})
    model_name = implementer_cfg.get("model", "sonnethigh")
    try:
        registry = _reviewers.load(wiki_path)
        impl_spec = _reviewers.resolve(registry, model_name)
    except _reviewers.ReviewerError as e:
        print(str(e), file=sys.stderr)
        return 1
    impl_model = impl_spec["model"]
    impl_effort = impl_spec.get("effort")

    if args.mode == "conflicts":
        return _run_conflicts(args, project_root, plugin_root, cfg, timeout, impl_model, impl_effort)
    else:
        return _run_verify_fix(args, project_root, plugin_root, cfg, timeout, impl_model, impl_effort)


def _run_conflicts(args, project_root: Path, plugin_root: Path, cfg: dict, timeout: int, impl_model: str, impl_effort: str | None) -> int:
    if not args.files:
        print("--files is required for conflicts mode", file=sys.stderr)
        return 1

    conflicting_files = "\n".join(f"- `{f}`" for f in args.files)

    template_path = plugin_root / "templates" / "merge-in-conflict-brief.md"
    prompt_text = _render.render(template_path, {
        "CONFLICTING_FILES": conflicting_files,
        "PROJECT_ROOT": str(project_root),
    })

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


def _run_verify_fix(args, project_root: Path, plugin_root: Path, cfg: dict, timeout: int, impl_model: str, impl_effort: str | None) -> int:
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


if __name__ == "__main__":
    sys.exit(main())
