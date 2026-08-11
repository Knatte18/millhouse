41 chars including newline = 40 hex chars, correct SHA-1 length. Good, valid.

Both cards (1 and 2) of this batch were completed and committed this turn: 2 of 2 cards committed, matching the batch's declared card count exactly. Verify passed (9/9 tests green).

Summary of work:
- Created `/home/hanf/Code/millhouse/wts/mill-go-quality-gate-gaps/plugins/mill/scripts/_prior_blocking.py` — the `build_digest(reviews_dir, scope, batch_name=None)` helper that scans `_mill/reviews/` code-review files and extracts cumulative `### [BLOCKING...]` findings, per the batch's Requirements and the overview's Shared Decisions.
- Created `/home/hanf/Code/millhouse/wts/mill-go-quality-gate-gaps/plugins/mill/unit_tests/test-prior-blocking.py` with 9 unittest cases covering all scenarios in the card, mirroring `test-nit-gate.py`'s tempfile-fixture conventions.
- One deviation from the brief's literal wording, flagged for visibility: Card 2 case 8's second sub-check as written ("`build_digest(reviews_dir, scope="holistic")` returns `""`" for a fixture containing only a `retry-fix`-named batch file) directly contradicts Card 1's own Requirements bullet ("when `scope == "holistic"`, select every holistic-classified file plus every batch-classified file, any batch name") and contradicts cases 5/6, which explicitly require holistic scope to aggregate across all batch names. Implementing the literal case-8 assertion would have broken that established cross-batch aggregation. I kept the implementation consistent with the majority/repeated spec (bullet 38, cases 4–6) and rewrote the case-8 sub-check to assert the same underlying correctness property (RE_BATCH classification isn't confused with holistic classification) using `scope="batch", batch_name="unrelated-batch"` instead, since that's the only assertion that can actually distinguish correct from misclassified behavior given holistic scope's own aggregation rule.

```json
{"status":"success","commit_sha":"b8b902d39621297b889955fcba0e98ae3b3424c2","session_id":"27c9d47f-5fcc-43fa-9e78-1a0b0841ea71","cards_done":[1,2]}
```
