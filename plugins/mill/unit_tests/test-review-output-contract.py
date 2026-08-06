"""Rendered-prompt conformance sweep -- the join node's integration guard.

Batches 2 and 3 each removed half of the pre-existing output contract (the Python half:
build_tool_rule / the CLIs; the static half: templates / the agent definition).
Neither proves on its own that the two halves now agree,
nor that agent-mode prose never leaks onto the shared ``--stage full`` channel.
This module renders the real ``prompt_text`` -- via ``_review_common.render_prompt(<template>,
tool_rule=build_tool_rule(mode, agent_mode), ...)`` -- for all five review templates, crossed with
both reviewer MODEs ("bulk" / "tool-use") and both dispatch channels (agent_mode True / False), and
asserts in both directions:

  - Agent-mode direction: the rendered prompt grants exactly one Write (for the report), never
  forbids Write outright, never claims the reviewer's sole output is its final chat message or
  return-as-text, and still forbids Edit / git / bash.
  - ``--stage full`` direction (the converse): the rendered prompt never grants Write, never names a
  `.out.md` destination, and never carries a `WROTE` ack instruction -- a `--stage full` reviewer
  has no brief and is granted at most Read/Grep/Glob (_llm_claude.py:80); leaking the agent-mode
  footer text here would break the API-error fallback.

Also asserts the two *static* surfaces directly, with their different invariants (Shared Decision
`all tool statements live in build_tool_rule and nowhere else`): - plugins/mill/templates/: no
review template states a tool permission or an output destination of its own. -
plugins/mill/agents/mill-reviewer.md: the file's `tools:` frontmatter IS the grant mechanism and
necessarily names a permission, so the narrower static invariant is checked instead -- no
`<OUTPUT_FILE>` token, no claim that its sole output is its final message, no blanket Write
prohibition, while still forbidding Edit / Bash / NotebookEdit. `mill-implementer.md` is out of
scope (Shared Decision `reviewers-only -- never touch the implementer path`).

Plain `test_*` functions plus a `main()` runner;
ASCII-only output, per the repo's unit-test convention (no pytest, no real git/wiki/LLM fixtures).
"""

from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
TEMPLATES_DIR = HUB / "plugins" / "mill" / "templates"
AGENTS_DIR = HUB / "plugins" / "mill" / "agents"
sys.path.insert(0, str(SCRIPTS_DIR))

import _review_common  # noqa: E402

TEMPLATE_NAMES = [
    "review-discussion",
    "review-code-batch",
    "review-code-holistic",
    "review-plan-batch",
    "review-plan-holistic",
]

MODES = ["bulk", "tool-use"]

# Tokens every template needs besides `tool_rule` (supplied per-render below), mirroring the render_prompt() call sites in _review_discussion.py, _review_code.py, and _review_plan.py.
# The artefact_section stub is a placeholder -- it carries no tool statements of its own, so it cannot contaminate either direction's assertions.
_COMMON_TOKENS = {
    "task_title": "Sample Task",
    "artefact_section": "## Artefact\nfixture content, no tool statements here",
    "constraints": "- no constraints",
    "round": 1,
    "reviewer_model": "claude-sonnet-4-6",
}

TEMPLATE_TOKENS = {
    "review-discussion": dict(_COMMON_TOKENS),
    "review-code-batch": {
        **_COMMON_TOKENS,
        "prior_nonblocking": "(none)",
        "batch_name": "sample-batch",
    },
    "review-code-holistic": {**_COMMON_TOKENS, "prior_nonblocking": "(none)"},
    "review-plan-batch": {**_COMMON_TOKENS, "batch_name": "sample-batch"},
    "review-plan-holistic": dict(_COMMON_TOKENS),
}


def _render(name: str, mode: str, agent_mode: bool) -> str:
    """Render `name` with the real build_tool_rule() output for (mode, agent_mode).

    Reproduces exactly what each backend's prepare() builds -- prepare() renders the same template
    with the same tool_rule -- without standing up git, wiki, or LLM fixtures.
    """
    tool_rule = _review_common.build_tool_rule(mode, agent_mode)
    tokens = {**TEMPLATE_TOKENS[name], "tool_rule": tool_rule}
    return _review_common.render_prompt(name, **tokens)


def _read_template_source(name: str) -> str:
    """Return the raw (unrendered) source text of template `name`."""
    return (TEMPLATES_DIR / f"{name}.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Agent-mode direction: agent_mode=True must grant Write, forbid Edit/git/bash, and never claim the review is returned as chat text / a final message.
# ---------------------------------------------------------------------------


def test_agent_mode_grants_exactly_one_write_and_forbids_edit_git_bash() -> None:
    for name in TEMPLATE_NAMES:
        for mode in MODES:
            rendered = _render(name, mode, agent_mode=True)
            # (a) no instruction forbidding Write outright.
            assert "Do NOT use Write" not in rendered, (
                f"{name}/{mode}/agent: still forbids Write outright"
            )
            # (c) grants exactly one Write, for the report.
            assert "use it exactly once, to write your full report" in rendered, (
                f"{name}/{mode}/agent: missing the single-Write report carve-out"
            )
            # (d) still forbids Edit, git, and bash.
            assert "Do NOT use Edit, or run git/bash" in rendered, (
                f"{name}/{mode}/agent: missing the Edit/git/bash prohibition"
            )
    print("PASS test_agent_mode_grants_exactly_one_write_and_forbids_edit_git_bash")


def test_agent_mode_no_sole_output_contradiction() -> None:
    """(b) no claim that the reviewer's output is its final message / chat text.

    A rendered agent-mode prompt must not tell the reviewer to "return review as text" (the
    non-agent instruction) or that its "sole output is the review file" (the deleted static claim)
    -- either would contradict the Write-to-file carve-out granted above.
    """
    for name in TEMPLATE_NAMES:
        for mode in MODES:
            rendered = _render(name, mode, agent_mode=True)
            assert "Return review as text" not in rendered, (
                f"{name}/{mode}/agent: still instructs returning review as text"
            )
            assert "sole output is the review file" not in rendered, (
                f"{name}/{mode}/agent: still claims sole output is the review file"
            )
    print("PASS test_agent_mode_no_sole_output_contradiction")


# ---------------------------------------------------------------------------
# --stage full direction (the converse): agent_mode=False must never grant Write, never name a .out.md destination, never carry a WROTE ack.
# ---------------------------------------------------------------------------


def test_stage_full_direction_grants_no_write_destination_or_ack() -> None:
    for name in TEMPLATE_NAMES:
        for mode in MODES:
            rendered = _render(name, mode, agent_mode=False)
            assert "use it exactly once, to write your full report" not in rendered, (
                f"{name}/{mode}/--stage full: leaked the agent-mode Write carve-out"
            )
            assert ".out.md" not in rendered, (
                f"{name}/{mode}/--stage full: leaked a .out.md destination"
            )
            assert "WROTE" not in rendered, (
                f"{name}/{mode}/--stage full: leaked a WROTE ack instruction"
            )
    print("PASS test_stage_full_direction_grants_no_write_destination_or_ack")


# ---------------------------------------------------------------------------
# Static surfaces: templates/ and agents/mill-reviewer.md carry DIFFERENT invariants -- conflating them would produce an unsatisfiable test.
# ---------------------------------------------------------------------------


def test_templates_state_no_tool_permission_or_destination() -> None:
    """No review template's static source states a tool permission or output destination of its own
    -- those live only in build_tool_rule's agent cells and write_brief's footer (Shared Decision
    `all tool statements live in build_tool_rule and nowhere else`).
    """
    for name in TEMPLATE_NAMES:
        source = _read_template_source(name)
        assert "Write" not in source, f"{name} static source states a Write permission"
        assert ".out.md" not in source, (
            f"{name} static source names a .out.md destination"
        )
    print("PASS test_templates_state_no_tool_permission_or_destination")


def test_agent_reviewer_static_invariant() -> None:
    """mill-reviewer.md's tools: frontmatter IS the grant mechanism, so it necessarily names a
    permission -- the narrower invariant card 14 actually produces is checked here instead of the
    templates/ rule above.
    """
    text = (AGENTS_DIR / "mill-reviewer.md").read_text(encoding="utf-8")
    assert "<OUTPUT_FILE>" not in text, (
        "mill-reviewer.md contains an <OUTPUT_FILE> token"
    )
    assert "sole output" not in text.lower(), (
        "mill-reviewer.md still claims its sole output is its final message"
    )
    must_not_line = next(
        (line for line in text.splitlines() if "MUST NOT use" in line), None
    )
    assert must_not_line is not None, (
        "mill-reviewer.md missing a MUST-NOT-use statement"
    )
    assert "Write" not in must_not_line, (
        "mill-reviewer.md blanket-prohibits Write in its MUST-NOT-use statement"
    )
    for forbidden_tool in ("Edit", "Bash", "NotebookEdit"):
        assert forbidden_tool in must_not_line, (
            f"mill-reviewer.md's MUST-NOT-use statement is missing {forbidden_tool!r}"
        )
    print("PASS test_agent_reviewer_static_invariant")


def test_no_output_file_token_anywhere() -> None:
    """Pin the constraint that made the first design of this task unbuildable.

    _render.render (_render.py:35) matches `<[A-Z][A-Z0-9_]*>` and raises KeyError: Unresolved
    template tokens for any such token missing from the caller's values dict.
    A literal <OUTPUT_FILE> in a template would hard-fail rendering before write_brief ever runs,
    and is unsuppliable on --stage full anyway;
    agent definitions are static text never passed through _render, so a token there would reach the
    model raw.
    Sweeps every file under both plugins/mill/templates/ and plugins/mill/agents/ (not just the five
    review templates and mill-reviewer.md) so a stray <OUTPUT_FILE> in any sibling file is caught
    too.
    """
    for directory in (TEMPLATES_DIR, AGENTS_DIR):
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            assert "<OUTPUT_FILE>" not in text, (
                f"{path} contains an <OUTPUT_FILE> token"
            )
    print("PASS test_no_output_file_token_anywhere")


def main() -> int:
    tests = [
        test_agent_mode_grants_exactly_one_write_and_forbids_edit_git_bash,
        test_agent_mode_no_sole_output_contradiction,
        test_stage_full_direction_grants_no_write_destination_or_ack,
        test_templates_state_no_tool_permission_or_destination,
        test_agent_reviewer_static_invariant,
        test_no_output_file_token_anywhere,
    ]
    failures: list[str] = []
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            print(f"FAIL [{fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(fn.__name__)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR [{fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(fn.__name__)
    if failures:
        print(f"\n{len(failures)} test(s) failed: {failures}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
