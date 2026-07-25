MILL_REVIEW_BEGIN
# Review: mill-plan review severity counting and validation schema gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-07-25
```

## Findings

### [GAP] Fail-loud helper's suggested shape omits the YAML-findings fallback path
**Section:** Technical context (severity-counting call graph), Scope (new shared helper), Testing
**Issue:** `parse_blocking_count` (verified at `_review_common.py:1564`) has two independent counting paths — heading regex, and a YAML-fenced `findings:` list fallback used when heading_count is 0 (tested at `test-review-common.py:1969-2016`, referencing real incident #552, with case-insensitive severity matching there vs. case-sensitive for headings). The discussion's suggested new-helper shape ("Technical context", last bullet) and every listed test case for it (Testing §1) only describe scanning `### [XXX]` headings — none cover a reviewer emitting an unrecognized severity (e.g. `severity: MAJOR`) inside a YAML-only findings block with no matching heading. Since #552 shows YAML-only output is a real production shape, an unrecognized severity there would still be silently dropped, reproducing Bug 1 through the exact code path this task exists to close.
**Fix:** Decide explicitly whether the fail-loud helper must also scan fenced `findings:` blocks (mirroring `parse_blocking_count`'s fallback and its case-insensitivity there), and add a corresponding test case; if intentionally out of scope, state that and the rationale.

### [GAP] Commit: none fix doesn't address the backend no-content-commit gate
**Section:** Scope (`_plan_validate.py`, `implementer-brief.md`), Decision `full-fix-not-validator-only`
**Issue:** `_implementer_common.py` contains a mechanical, code-level "no-content-commit" gate (top-level check ~line 1431-1465, and `_reclassify_verify_failure`'s `content == 0` branch at lines 149-160) that demotes any self-reported `success` to `stuck_type: logic` when zero content commits exist since `start_sha` — its own docstring states this is "unaffected by cards_done: zero commits is zero work regardless of any self-report." The only existing exemption is `nits_only`. Nothing in Scope, Decisions, or Technical context mentions this gate. A batch composed entirely (or, on a late resume, entirely of remaining) `Commit: none` verification cards would legitimately produce zero content commits and would be mechanically misclassified as stuck despite `cards_done` correctly reporting every card addressed — the same "tooling can't see this card's true state" problem the `full-fix-not-validator-only` decision explicitly says the task exists to eliminate, just at a layer the discussion never surfaces.
**Fix:** Extend Scope to cover `_implementer_common.py`'s no-content-commit gate(s) with a `Commit: none`-aware exemption (or an equivalent to `nits_only`'s carve-out), and confirm whether an all-`Commit: none` batch is a supported shape.

### [NOTE] Testing hedge for _review_plan.py's 5 inline call sites doesn't name the existing test file
**Section:** Testing (`_review_plan.py`'s 5 inline `run()` call sites)
**Issue:** Text reads "existing test file for `_review_plan.py` if present, else cover via..." — non-committal. `test-review-plan-flow.py` already exists in `plugins/mill/unit_tests/` and is the natural target.
**Fix:** Name `test-review-plan-flow.py` directly as the target for the MAJOR-only synchronous-dispatch regression test.

## Verdict

GAPS_FOUND
Two unaddressed technical gaps (YAML-fallback severity path; backend no-content-commit gate) risk each bug fix being incomplete.
MILL_REVIEW_END
