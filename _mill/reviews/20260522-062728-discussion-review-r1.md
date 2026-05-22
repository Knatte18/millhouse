# Review: Replace psmux marker protocol with idle-prompt detection

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-22
```

## Findings

### [GAP] Test update scope is internally inconsistent
**Section:** `## Technical context` vs `## Testing`
**Issue:** Technical context says "tests that exercise the success path (S1, S4, S6, S7) need to mock `_wait_for_idle_stable`," but the Testing section says "S1–S5, S7–S9: update `extract_response` mock signature only." S1, S4, and S7 appear in both buckets with contradictory instructions. Additionally, S9 is a reuse-path success test that reaches Step 11 (confirmed by reading the code: reuse path skips Steps 7–8 but still executes Steps 10–11), so it also needs `_wait_for_idle_stable` mocked — yet it appears only in the "signature only" list. A plan writer cannot reconcile which section is authoritative for these four tests.
**Fix:** Reconcile the two sections into a single definitive list: S6 is a full rewrite; S1, S4, S7, and S9 need both `_wait_for_idle_stable` added and `extract_response` signature updated; S2, S3, S5, S8 are signature-only (or unchanged).

### [NOTE] `alternate=True` not specified for new capture calls
**Section:** `## Technical context — _wait_for_idle_stable` and new Step 11
**Issue:** All existing `capture_pane` calls used for idle/response detection use `alternate=True` (lines 122 and 281 of `millpy-claude-sub.py`); the description of `_wait_for_idle_stable` and the snapshot_b capture does not specify this parameter.
**Fix:** State that both the stability-check polls inside `_wait_for_idle_stable` and the snapshot_b capture use `alternate=True`, consistent with the existing pattern.

## Verdict

GAPS_FOUND
Testing section contradicts technical context on four tests; resolve before plan writing.