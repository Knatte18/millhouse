"""Unit tests for the five review prompt templates under plugins/mill/templates/.

Covers:
  - Each template still renders via _review_common.render_prompt with the exact token set its
      backend supplies -- the guard against an accidentally introduced <UPPERCASE> token, which
      _render.render() raises KeyError for at render time (production), a failure test-render.py
      cannot see because it only renders tempfile fixtures.
  - The tool-prohibition header and the sole-output sentence deleted by card 15,
      and (for review-discussion.md only) the tool-use mode claim deleted by card 16, stay deleted.
  - The MILL_REVIEW_BEGIN/MILL_REVIEW_END wrapper and the REPORT-not-fix instruction kept by card 15
      stay present.
  - No template names the report destination via an <OUTPUT_FILE> token (Shared Decision "no
      <OUTPUT_FILE> token anywhere").
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
TEMPLATES_DIR = HUB / "plugins" / "mill" / "templates"
sys.path.insert(0, str(SCRIPTS_DIR))

import _review_common  # noqa: E402

# Mirrors _review_common.RECOGNIZED_CLASSES -- kept as a literal tuple (not imported) so this test
# also catches an accidental drift between the backend's class list and the templates it renders.
RECOGNIZED_CLASSES = ("design", "scope", "decision", "consistency")

ANTI_LADDER_SENTENCE = (
    "Class governs who decides and when the loop stops, never whether a finding gets fixed."
)

TEMPLATE_NAMES = [
    "review-discussion",
    "review-code-batch",
    "review-code-holistic",
    "review-plan-batch",
    "review-plan-holistic",
]

# Tokens every one of the five templates needs, mirroring the render_prompt() call sites in _review_discussion.py, _review_code.py, and _review_plan.py.
_COMMON_TOKENS = {
    "task_title": "Sample Task",
    "tool_rule": "<TOOL_RULE fixture text>",
    "artefact_section": "## Artefact\nfixture content",
    "constraints": "- no constraints",
    "round": 1,
    "reviewer_model": "claude-sonnet-4-6",
}

# Per-template additions: review-code-* also needs prior_nonblocking;
# the batch variants additionally need batch_name (the holistic variants do not).
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


def _read_template_source(name: str) -> str:
    """Return the raw (unrendered) source text of template `name`."""
    return (TEMPLATES_DIR / f"{name}.md").read_text(encoding="utf-8")


def test_all_templates_render() -> None:
    """Each of the five templates renders with the token set its backend supplies.

    A missing token (e.g.
    an accidentally introduced <UPPERCASE> placeholder) would raise KeyError inside render_prompt --
    this is the only test that exercises the real files in plugins/mill/templates/ rather than a
    tempfile fixture.
    """
    for name in TEMPLATE_NAMES:
        tokens = TEMPLATE_TOKENS[name]
        rendered = _review_common.render_prompt(name, **tokens)
        assert rendered, f"{name} rendered to an empty string"
    print("PASS test_all_templates_render")


def test_deleted_prose_stays_deleted() -> None:
    """The tool prohibitions and sole-output sentence removed by cards 15/16 are gone."""
    forbidden_everywhere = [
        "You are a READ-ONLY reviewer",
        "MUST NOT call Edit, Write, Bash",
        "MUST NOT make git commits",
        "Your sole output is the review file",
    ]
    for name in TEMPLATE_NAMES:
        source = _read_template_source(name)
        for phrase in forbidden_everywhere:
            assert phrase not in source, (
                f"{name} still contains deleted phrase {phrase!r}"
            )

    # review-discussion.md's source-grounding rule also lost its false tool-use mode claim (card 16);
    # the other four templates' source-grounding paragraphs never made this claim, so there is no counterpart to check.
    discussion_source = _read_template_source("review-discussion")
    assert "You are in tool-use mode" not in discussion_source, (
        "review-discussion.md still contains the deleted tool-use mode claim"
    )
    print("PASS test_deleted_prose_stays_deleted")


def test_kept_prose_stays_kept() -> None:
    """The MILL_REVIEW markers and the REPORT-not-fix instruction survive the edit."""
    for name in TEMPLATE_NAMES:
        source = _read_template_source(name)
        assert "MILL_REVIEW_BEGIN" in source, f"{name} missing MILL_REVIEW_BEGIN"
        assert "MILL_REVIEW_END" in source, f"{name} missing MILL_REVIEW_END"
        assert "REPORT" in source and "do NOT fix them" in source, (
            f"{name} missing the REPORT-not-fix instruction"
        )
    print("PASS test_kept_prose_stays_kept")


def test_plan_criteria_bullets_present() -> None:
    """The two new plan-review criteria bullets (All Files Touched scope, platform-behavior-claim
    verification) are present verbatim in both plan-review templates' raw source.
"""
    for name in ["review-plan-holistic", "review-plan-batch"]:
        source = _read_template_source(name)
        assert (
            "the overview's `## All Files Touched` section lists the union of"
            in source
        ), f"{name} missing the All-Files-Touched-scope criteria bullet"
        assert "Platform-behavior-claim verification" in source, (
            f"{name} missing the platform-behavior-claim-verification criteria bullet"
        )
    print("PASS test_plan_criteria_bullets_present")


def test_no_output_file_token() -> None:
    """No template names the report destination via an <OUTPUT_FILE> token."""
    for name in TEMPLATE_NAMES:
        source = _read_template_source(name)
        assert "<OUTPUT_FILE>" not in source, f"{name} contains an <OUTPUT_FILE> token"
    print("PASS test_no_output_file_token")


def test_unified_vocabulary_and_class_taxonomy() -> None:
    """All five review templates speak the unified BLOCKING/NIT vocabulary with a class suffix.

    Covers the unified-severity-vocabulary and class-syntax-in-bracket Shared Decisions: the retired
    GAP/NOTE/GAPS_FOUND tokens are gone, every template shows a classed BLOCKING and NIT finding-heading
    example, an ``## Out of scope for this stage`` section is present, and the anti-ladder guarantee
    sentence appears verbatim.
    """
    blocking_heading_re = re.compile(r"### \[BLOCKING:([a-z]+)\]")
    nit_heading_re = re.compile(r"### \[NIT:([a-z]+)\]")
    for name in TEMPLATE_NAMES:
        source = _read_template_source(name)

        # The retired per-type vocabulary must not survive as a bracketed severity label or a
        # verdict value -- none of the five templates use "GAP"/"NOTE" for anything else, so a
        # blanket substring check is safe (confirmed by inspection, not just at test-write time --
        # test_all_templates_render below would fail loudly if a template reintroduced either word
        # as a real token this test doesn't otherwise cover).
        for retired_token in ("GAP", "NOTE", "GAPS_FOUND"):
            assert retired_token not in source, (
                f"{name} still contains the retired token {retired_token!r}"
            )

        blocking_classes = set(blocking_heading_re.findall(source))
        assert blocking_classes, f"{name} has no ### [BLOCKING:<class>] finding-heading example"
        assert blocking_classes <= set(RECOGNIZED_CLASSES), (
            f"{name} has a BLOCKING finding-heading example with an unrecognised class: "
            f"{blocking_classes - set(RECOGNIZED_CLASSES)}"
        )

        nit_classes = set(nit_heading_re.findall(source))
        assert nit_classes, f"{name} has no ### [NIT:<class>] finding-heading example"
        assert nit_classes <= set(RECOGNIZED_CLASSES), (
            f"{name} has a NIT finding-heading example with an unrecognised class: "
            f"{nit_classes - set(RECOGNIZED_CLASSES)}"
        )

        assert "## Out of scope for this stage" in source, (
            f"{name} missing the '## Out of scope for this stage' section"
        )

        assert ANTI_LADDER_SENTENCE in source, (
            f"{name} missing the anti-ladder guarantee sentence verbatim"
        )
    print("PASS test_unified_vocabulary_and_class_taxonomy")


def main() -> int:
    tests = [
        test_all_templates_render,
        test_deleted_prose_stays_deleted,
        test_kept_prose_stays_kept,
        test_plan_criteria_bullets_present,
        test_no_output_file_token,
        test_unified_vocabulary_and_class_taxonomy,
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
