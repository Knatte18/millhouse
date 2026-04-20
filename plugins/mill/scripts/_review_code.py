"""
Review backend for code artefacts.

Computes a git diff (merge-base main HEAD → HEAD), bulks the plan and touched
source files into the prompt, and dispatches a single bulk review call.

Public API:
    run(cfg, slug, mill_dir, wiki_root, project_root) -> ReviewResult
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import _subprocess_util
from _llm_claude import LLMError
from _review_common import (
    ReviewError,
    ReviewResult,
    aggregate_verdict,
    bulk_files,
    check_mode,
    discover_round,
    load_reviewer,
    load_task_title,
    parse_verdict,
    read_constraints_md,
    render_prompt,
    resolve_path,
    write_review_file,
)


def _parse_touched_files(diff: str) -> list[str]:
    """Extract touched file paths from a unified diff.

    Scans for '--- a/<path>' and '+++ b/<path>' lines. Excludes '/dev/null'
    entries (added/deleted files with no counterpart).

    Returns a deduplicated list of relative path strings.
    """
    seen: dict[str, None] = {}
    for line in diff.splitlines():
        if line.startswith("--- a/") or line.startswith("+++ b/"):
            path = line[6:]
            if path != "/dev/null":
                seen[path] = None
    return list(seen.keys())


def run(
    cfg: dict,
    slug: str,
    mill_dir: Path,
    wiki_root: Path,
    project_root: Path,
) -> ReviewResult:
    """Run a code review against the diff between merge-base main HEAD and HEAD.

    Steps:
    1. Resolve plan_dir and reviews_dir; discover round.
    2. Bulk plan files; raise if plan dir is empty.
    3. Compute git diff via _subprocess_util.run; guard empty diff.
    4. Parse touched files from diff.
    5. Load reviewer; verify bulk mode.
    6. Render prompt; dispatch reviewer; write file; return ReviewResult.
    """
    # 1. Paths and round
    plan_dir = resolve_path(cfg["paths"]["plan_dir"], slug, wiki_root)
    reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug, wiki_root)
    round_n = discover_round(reviews_dir, "code")
    max_rounds = cfg["review"]["code"]["rounds"]
    if round_n > max_rounds:
        raise ReviewError(
            f"Round {round_n} exceeds max {max_rounds} for code review"
        )

    print(
        f"[_review_code] slug={slug!r} round={round_n}",
        file=sys.stderr,
    )

    # 2. Plan files
    plan_files = sorted(plan_dir.glob("*.md"))
    if not plan_files:
        raise ReviewError(f"No plan files found in {plan_dir}")

    plan_content = "\n\n".join(p.read_text(encoding="utf-8") for p in plan_files)

    # 3. Compute diff using _subprocess_util.run (Layer 01 convention)
    result = _subprocess_util.run(
        ["git", "merge-base", "main", "HEAD"],
        cwd=project_root,
        timeout=30,
    )
    if result.returncode != 0:
        raise ReviewError(
            f"git failed: {(result.stderr or '').strip()}"
        )
    base_sha = result.stdout.strip()

    result = _subprocess_util.run(
        ["git", "diff", f"{base_sha}..HEAD"],
        cwd=project_root,
        timeout=30,
    )
    if result.returncode != 0:
        raise ReviewError(
            f"git failed: {(result.stderr or '').strip()}"
        )
    diff = result.stdout

    # 3b. Empty-diff guard
    if not diff.strip():
        raise ReviewError(
            f"No diff between {base_sha}..HEAD — are you on a task branch?"
        )

    # 4. Parse touched files
    touched_paths = _parse_touched_files(diff)
    touched_files = [
        project_root / p
        for p in touched_paths
        if (project_root / p).exists()
    ]

    # 5. Load reviewer; enforce bulk mode
    reviewer_name = cfg["review"]["code"]["reviewer"]
    reviewer = load_reviewer(reviewer_name)
    check_mode(reviewer, "bulk", "code")

    style = cfg["review"]["code"]["style"]
    template_name = f"review-code-{style}"

    # 6. Bulk, render, dispatch
    bulked = bulk_files([*plan_files, *touched_files])

    prompt_text = render_prompt(
        template_name,
        task_title=load_task_title(mill_dir, slug),
        diff=diff,
        plan_content=plan_content,
        artefact_content=bulked,
        constraints=read_constraints_md(project_root),
        round=round_n,
        reviewer_model=reviewer_name,
    )

    try:
        raw = reviewer.run(prompt_text)
    except LLMError as exc:
        # Single sub-review → total failure
        raise ReviewError(f"All sub-reviews failed: {exc}") from exc

    verdict = parse_verdict(raw)
    # No scope kwarg — code review canonical filename has no batch suffix.
    path = write_review_file(reviews_dir, "code", round_n, raw)

    print(
        f"[_review_code] wrote {path.name} verdict={verdict}",
        file=sys.stderr,
    )

    return ReviewResult(
        type="code",
        round=round_n,
        verdict=verdict,
        reviews=[
            {
                "scope": "holistic",
                "verdict": verdict,
                "file": str(path),
            }
        ],
    )
