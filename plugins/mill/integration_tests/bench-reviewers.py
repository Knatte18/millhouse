"""Benchmark harness for named reviewers.

Loads the reviewer registry, renders prompts from fixtures, invokes reviewers
via _reviewer_single.run(), collects metrics, and writes a results table to .scratch/.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import _review_common  # noqa: E402
import _reviewers  # noqa: E402
import _reviewer_single  # noqa: E402
import _reviewer_test_stub as _stub  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"

CANNED_APPROVE = (
    "# Review: stub\n"
    "\n"
    "```yaml\n"
    "verdict: APPROVE\n"
    "reviewer_model: stub\n"
    "reviewed_file: _mill/discussion.md\n"
    "date: 2026-01-01\n"
    "```\n"
    "\n"
    "## Verdict\n"
    "\n"
    "APPROVE\n"
    "All criteria met.\n"
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark named reviewers")
    parser.add_argument(
        "--reviewers",
        nargs="+",
        default=["g25flash", "g3flash_preview", "g25pro"],
        metavar="NAME",
    )
    parser.add_argument(
        "--types",
        nargs="+",
        default=["discussion", "plan", "code"],
        metavar="TYPE",
    )
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    from _paths import resolve_git_root, resolve_wiki_path  # noqa: E402
    git_root = resolve_git_root()
    wiki_path = resolve_wiki_path(git_root)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    scratch = git_root / ".scratch"
    scratch.mkdir(parents=True, exist_ok=True)

    tool_rule_bulk = _review_common.build_tool_rule("bulk")

    # Read fixtures once before the reviewer loop.
    discussion_text = (FIXTURES / "sample-discussion.md").read_text(encoding="utf-8")
    overview_text = (FIXTURES / "sample-plan" / "00-overview.md").read_text(encoding="utf-8")
    batch_text = (FIXTURES / "sample-plan" / "01-core.md").read_text(encoding="utf-8")
    code_text = (FIXTURES / "sample-code.py").read_text(encoding="utf-8")

    # Build artefact sections (template-fixed parts; reviewer_model inserted per reviewer).
    discussion_artefact_section = (
        "Evaluate the discussion document below.\n\n"
        "--- FILE: _mill/discussion.md ---\n"
        + discussion_text
    )

    plan_artefact_section = (
        "Evaluate the plan below. All plan files and referenced source files are inlined.\n\n"
        "## Files included\n\n"
        "- `_mill/plan/00-overview.md`\n"
        "- `_mill/plan/01-core.md`\n\n"
        "--- FILE: _mill/plan/00-overview.md ---\n"
        + overview_text
        + "\n\n--- FILE: _mill/plan/01-core.md ---\n"
        + batch_text
    )

    code_artefact_section = (
        "## Files included\n\n"
        "- `_mill/plan/00-overview.md`\n"
        "- `_mill/plan/01-core.md`\n"
        "- `plugins/mill/scripts/_render.py`\n\n"
        "--- FILE: _mill/plan/00-overview.md ---\n"
        + overview_text
        + "\n\n--- FILE: _mill/plan/01-core.md ---\n"
        + batch_text
        + "\n\n--- FILE: plugins/mill/scripts/_render.py ---\n"
        + code_text
    )

    header = "| Reviewer | Type | Time | Verdict | Findings | Fmt |"
    sep = "|---|---|---|---|---|---|"
    print(header, flush=True)
    print(sep, flush=True)

    rows: list[str] = []

    for reviewer_name in args.reviewers:
        # Resolve spec.
        if reviewer_name == "test_stub":
            spec: dict = {"type": "single", "provider": "test_stub", "model": "stub"}
        else:
            try:
                registry = _reviewers.load(wiki_path)
                spec = _reviewers.resolve(registry, reviewer_name)
            except _reviewers.ReviewerError as exc:
                print(f"[bench] reviewer {reviewer_name!r}: {exc}", file=sys.stderr)
                continue

        for review_type in args.types:
            if review_type not in ("discussion", "plan", "code"):
                print(f"[bench] unknown type {review_type!r}, skipping", file=sys.stderr)
                continue

            # Render prompt inside reviewer loop -- reviewer_model changes per reviewer.
            if review_type == "discussion":
                prompt_text = _review_common.render_prompt(
                    "review-discussion",
                    task_title="Sample render module refactor",
                    round=1,
                    reviewer_model=reviewer_name,
                    tool_rule=tool_rule_bulk,
                    artefact_section=discussion_artefact_section,
                    constraints="(none)",
                )
            elif review_type == "plan":
                prompt_text = _review_common.render_prompt(
                    "review-plan-holistic",
                    task_title="Sample render module refactor",
                    round=1,
                    reviewer_model=reviewer_name,
                    tool_rule=tool_rule_bulk,
                    artefact_section=plan_artefact_section,
                    constraints="(none)",
                )
            else:
                prompt_text = _review_common.render_prompt(
                    "review-code-holistic",
                    task_title="Sample render module refactor",
                    round=1,
                    reviewer_model=reviewer_name,
                    tool_rule=tool_rule_bulk,
                    artefact_section=code_artefact_section,
                    constraints="(none)",
                )

            if reviewer_name == "test_stub":
                _stub.seed([(CANNED_APPROVE, "stub-sid")])

            t0 = time.monotonic()
            text = ""
            try:
                text, _sid = _reviewer_single.run(
                    spec, prompt_text, session_id=None, timeout=args.timeout
                )
                elapsed = time.monotonic() - t0

                try:
                    verdict = _review_common.parse_verdict(text)
                except Exception:
                    verdict = "PARSE_FAIL"

                if review_type == "discussion":
                    findings = (
                        _review_common.parse_blocking_count(text, severity="GAP")
                        + _review_common.parse_blocking_count(text, severity="NOTE")
                    )
                else:
                    findings = (
                        _review_common.parse_blocking_count(text, severity="BLOCKING")
                        + _review_common.parse_blocking_count(text, severity="NIT")
                    )

                format_ok = (
                    text.strip().startswith("# Review:")
                    and "verdict:" in text
                    and "## Verdict" in text
                )

            except subprocess.TimeoutExpired:
                elapsed = time.monotonic() - t0
                verdict = "TIMEOUT"
                findings = 0
                format_ok = False
            except Exception as exc:
                elapsed = time.monotonic() - t0
                verdict = "ERROR"
                findings = 0
                format_ok = False
                print(f"[bench] {reviewer_name}/{review_type} error: {exc}", file=sys.stderr)

            raw_path = scratch / f"bench-{timestamp}-{reviewer_name}-{review_type}.md"
            raw_path.write_text(text, encoding="utf-8")

            row = f"| {reviewer_name} | {review_type} | {elapsed:.1f}s | {verdict} | {findings} | {format_ok} |"
            print(row, flush=True)
            rows.append(row)

    results_lines = [header, sep] + rows
    results_path = scratch / f"bench-{timestamp}.md"
    results_path.write_text("\n".join(results_lines) + "\n", encoding="utf-8")
    print(f"\nResults written to {results_path}", flush=True)


if __name__ == "__main__":
    main()
