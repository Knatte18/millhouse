MILL_REVIEW_BEGIN
# Review: Improve diagnosability of plan-validate errors and finalize verify-replay failures

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] Failure-signature exact-match ignores embedded volatile timing (Go markers)
**Section:** Decisions `gap2-failure-signature-extraction` / `gap2-subset-diff-semantics`; Testing item 2
**Issue:** Go's `--- FAIL: TestFoo (0.00s)` and `FAIL\tpkg\t0.123s` marker lines embed a per-run elapsed-time value in the raw line text (confirmed in `_implementer_common.py:542`'s own comment); the design stores/compares the RAW line as the signature with exact-string set membership, so a genuinely pre-existing Go test failure will almost never produce an identical string between baseline computation and finalize's replay run, causing the subset-diff to treat it as "new" every time.
**Fix:** Add a normalization step (e.g., strip trailing `(\d+(\.\d+)?m?s)`-shaped duration suffixes, or the trailing tab-separated duration field) before using a marker line as a signature, and cover it in the `_extract_failure_signatures` unit tests with a duration-varying Go fixture pair.

### [GAP] Stale Q&A answer still tells reader to use `iter_batch_verifies`
**Section:** Q&A log line "When should each batch's baseline be computed..."
**Issue:** That answer says "using `_plan_dag.iter_batch_verifies` with no `status_path` filter," directly contradicting the later Decision `gap2-enumerate-batches-directly-not-via-iter-batch-verifies`, the Scope/Technical-context sections, and the round-1-review Q&A entry that explicitly reject `iter_batch_verifies` for this purpose.
**Fix:** Update or strike the stale clause in that Q&A answer so the log doesn't contain two contradictory statements about which enumeration mechanism to use.

### [NOTE] Per-batch enumeration doesn't state handling of `verify: null` batches
**Section:** Technical context, `millpy-implement.py:78` bullet
**Issue:** The direct-frontmatter enumeration for baseline purposes doesn't say whether a batch whose `verify:` is null/absent is skipped (no signature set to compute) or given an empty-list baseline.
**Fix:** State explicitly that a null/absent `verify:` batch is skipped for baseline purposes (mirroring `iter_batch_verifies`'s reason-1 skip), since its own finalize gate is a no-op anyway.

## Verdict

GAPS_FOUND
Two GAPs: an unaddressed signature-volatility feasibility issue, and a stale/contradictory Q&A log entry.
MILL_REVIEW_END
