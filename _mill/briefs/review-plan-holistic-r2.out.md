MILL_REVIEW_BEGIN
# Review: _plan_validate.py verify: command validation: false positives, missing escape hatches, and a doc/enforcement mismatch — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (per Anthropic naming; harness calls this session "Sonnet 5")
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [NIT:consistency] Card 3's anchor-test description mismatches the actual anchor tests
**Location:** batch 2 / Card 3 **Issue:** Card 3 says the 5 new tests must follow "the exact structure of the existing `test_check_verify_full_suite_go_test_dotdotdot_*` tests" while specifying construction via `_make_verify_only_batch_text(...)`, but those anchor tests (verified in source, lines 4580-4614) hand-inline the batch markdown rather than calling that helper. **Fix:** Clarify the card wording — only the tempdir/run/assert control-flow shape must match the anchors; the helper substitution for batch-text construction is an intentional simplification, not a copy of their literal body.

### [NIT:consistency] done_gate exemption gets no overview-level test
**Location:** batch 2 / Card 3 **Issue:** All 5 new tests exercise `done_gate` against a per-batch `verify:`; `_check_verify_full_suite`'s `_check_frontmatter` closure (edited by batch 1) is shared between the per-batch loop and the overview-level call, but the overview path of the exemption is never asserted. **Fix:** Optionally add a 6th test setting the overview's own `verify:` equal to `done_gate` and asserting no `verify-full-suite` finding with `batch: None`.

## Verdict

APPROVE
All quoted before/after code and doc blocks verified byte-exact against current source; decisions, DAG, and file scope are internally consistent.
MILL_REVIEW_END
