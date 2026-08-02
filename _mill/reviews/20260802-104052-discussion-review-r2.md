MILL_REVIEW_BEGIN
# Review: Self-discovered mill-go/mill-plan skill-doc and behavior gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] Scope commits to a #758 unit test that Testing rules out
**Section:** Scope (`## Scope` "In:" bullet) vs `## Testing`
**Issue:** Scope's "In:" list states "Unit test coverage for the two behavior-affecting fixes (#757's phase-gate widening, #758's mandatory reason-annotation), extending the existing `test-phase-wait.py`/mill-go-adjacent test files" — but the `## Testing` section for #758 explicitly says "no unit test applies... no TDD candidate here" because the fix is SKILL.md prose interpreted by the orchestrating LLM, not a testable Python function. Confirmed via source: grep across `plugins/mill/scripts/` finds no Python function backing the "card vs. batch-level `## Prior failure`" annotation logic — only the pre-existing `self-resolved-verify-logic` phase string in `_status.py`.
**Fix:** Narrow the Scope bullet to name only #757's test extension (`test-phase-wait.py`), or explicitly state #758 has no test deliverable — as written, a plan writer following Scope literally would create a spurious/inapplicable test card for a non-testable prose change.

### [NOTE] "Renders the full batch file" overstates the brief's mechanism
**Section:** Decision `758-mandatory-reason-annotation`, Annotation target/format paragraph
**Issue:** Claims "the implementer brief template already renders the full batch file into the implementer's context" — but `implementer-brief.md` only passes `<BATCH_FILE>` as an absolute-path token and instructs "Read the batch file first" (line 44); it is not inline-substituted into the rendered prompt text the way `<TASK_TITLE>`/`<BATCH_NAME>` are.
**Fix:** Rephrase to "the implementer reads the full batch file via its own Read call before starting cards" — the practical conclusion (a `## Prior failure` section is read unconditionally) still holds, so this is wording-only, not a functional gap.

## Verdict

GAPS_FOUND
Scope's unit-test commitment for #758 directly contradicts Testing's "no unit test applies" verdict for the same fix.
MILL_REVIEW_END
