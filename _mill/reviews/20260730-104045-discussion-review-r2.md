MILL_REVIEW_BEGIN
# Review: mill-plan: Requirements find/replace fences lose byte-exactness under list-nested indentation

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnet
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-07-30
```

## Findings

### [GAP] Dedent heuristic false-negatives on indented real-source excerpts
**Section:** Decisions › trigger-heuristic-near-miss / mechanical-fix-dedent-in-place
**Issue:** `textwrap.dedent` strips the *common minimum* leading whitespace across all lines. If the true source excerpt itself has nonzero inherent indentation (e.g. quoting a class method body: real lines indented 4/8 spaces), adding a uniform K-space list-continuation bug yields 4+K/8+K; dedent strips the new minimum (4+K), producing 0/4 — not the real file's 4/8. The dedented content then fails to match the target file, so the near-miss condition (`dedented matches, raw doesn't`) never holds and the drift is silently missed — precisely the class of quote (indented Python/YAML/nested-markdown) that's common in this codebase, not merely the "illustrative code" false-negative already acknowledged.
**Fix:** State this as a known limitation (heuristic only reliably fires when the true excerpt's own baseline indentation is 0) or add a test proving/disproving behavior on indented excerpts, so the plan and reviewers don't overstate the check's guarantee.

### [GAP] `_extract_requirements_text` cannot yield a "line index" as instructed
**Section:** Technical context (`_extract_requirements_text` reuse) / Decisions › fence-aware-boundary-detection
**Issue:** The discussion instructs calling `_extract_requirements_text(card_text)` "to locate the Requirements: header's starting line index," but the function (verified at `_plan_validate.py:1384`) takes `card_text` and returns a joined string (or `None`) — it never returns or exposes an index. There is no stated bridge from its string return value back to a position in `card_lines` for the re-scan to start from.
**Fix:** Specify the actual mechanism (e.g. re-run the function's own `header_re` against `card_lines` to find the index, or take the returned text's first line and locate it) so the fence-aware re-scan's starting point is unambiguous to implement.

### [NOTE] CRLF test case lacks an explicit test-function name
**Section:** Testing
**Issue:** Every other test bullet names its exact `test_check_requirements_quote_indent_drift_*` function; the CRLF-normalization bullet only describes the scenario ("A CRLF-normalization case: ... OR conversely...") without committing to a name or a single deterministic scenario.
**Fix:** Name the test function and pick one concrete scenario (not an "OR") to match the precision of the other test bullets.

## Verdict
GAPS_FOUND
Two GAPs: dedent heuristic silently misses drift in indented real-source quotes; index-based re-scan instruction is unimplementable as literally stated.
MILL_REVIEW_END
