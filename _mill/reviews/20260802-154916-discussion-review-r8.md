MILL_REVIEW_BEGIN
# Review: Improve diagnosability of plan-validate errors and finalize verify-replay failures

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not directly knowable)
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] Duration normalization doesn't cover run-all.py's own FAIL-marker shapes
**Section:** Decisions `gap2-failure-signature-extraction` / `gap2-signature-normalization-strips-duration`
**Issue:** The existing `"--- FAIL "` / `"FAIL -- "` markers reused here are labeled "presumably dotnet," but they are actually mill's own `plugins/mill/unit_tests/run-all.py` test-runner format (`run-all.py:91` `"--- {marker} {name} ({elapsed:.1f}s) ---"`, `:107` `"FAIL -- {len(failures)} of {len(tests)} in {total:.1f}s: {failures}"`; already exercised for truncation in `test-implementer-common.py`'s "Test H", lines 2193-2200). This is the template-recommended `verify:` shape for virtually every batch in this repo (`plugins/mill/templates/plan-batch.md:18`). Both lines embed a volatile per-run duration in a NON-trailing position (`(1.2s) ---` has trailing text after the parenthetical; `in 45.6s: [...]` has the failures list after the duration) — but the decided normalization strips only a *trailing* `(<digits>s)`/tab-duration suffix (Go's two shapes). It will not touch either run-all.py format, so a genuinely unchanged pre-existing failure will still fail exact-match comparison every finalize call (different elapsed time each run), spuriously blocking the batch — the exact false-positive class gap2 exists to fix, unfixed for this repo's own dominant verify-command shape.
**Fix:** Extend `_normalize_failure_signature` with patterns for run-all.py's two shapes (strip `(<digits>[.<digits>]s)` regardless of trailing text after it for the per-test line; strip the `in <digits>[.<digits>]s` token from the summary line), and correct the "presumably dotnet" attribution to name run-all.py explicitly; add a Testing-section case mirroring Test H's fixture strings.

## Verdict

GAPS_FOUND
Signature normalization misses mill's own run-all.py duration shapes, breaking the fix for this repo's default verify command.
MILL_REVIEW_END
