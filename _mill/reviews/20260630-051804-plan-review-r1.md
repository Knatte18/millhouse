MILL_REVIEW_BEGIN
# Review: Fix mid-batch stop recovery and fixer false-success in agent-dispatch mode — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-30
```

## Findings

### [BLOCKING] Card 5 misses 4 transient-asserting test cases
**Location:** Batch 1, Card 5 (test-implementer-common.py)
**Issue:** Cards 2 and 3 flip `_reclassify_verify_failure`'s partial branch and every `_batch_completeness_stuck` emission from `transient` to `incomplete`, but card 5 only updates cases 27a, 44a, 50g. Cases 41 (line 2117), 43 (line 2180), 48e (line 2387), and 49f (line 2424) also assert `stuck_type == "transient"` while calling those exact code paths, so batch 1's `verify:` (which runs this whole file) will go RED.
**Fix:** Add cases 41, 43, 48e, 49f to card 5's "assert incomplete" update list (41/43/49f are direct `_batch_completeness_stuck` calls; 48e is the parsed-success `_reclassify_verify_failure` partial branch). Case 28 (API-error -> transient) and case 42 (commits_made only) correctly stay unchanged.

### [NIT] Explicit-success completeness `incomplete` lacks commit_sha
**Location:** Batch 1, Card 3 (_forward_output line ~939/946)
**Issue:** Card 3a makes `_batch_completeness_stuck` emit `incomplete` for all callers including the explicit-success-path call at ~939, but card 3c only attaches `commit_sha` at the three inference-path sites (1052/1136/1220). The ~946 print emits the `incomplete` dict with no `commit_sha`, contradicting the overview Decision ("Its envelope carries `commit_sha`") and the envelope-parity goal — reachable when `verify_cmd` is null and the batch is partial.
**Fix:** Attach `commit_sha` at the line ~946 print site too (or route it through the same attach helper) so every `incomplete` envelope is uniform.

### [NIT] Resume re-dispatch renders a fresh SESSION_ID, not the preserved one
**Location:** Batch 2, Card 7 (millpy-implement.py)
**Issue:** Card 7 preserves `start_sha` and does not overwrite `implementer_session`, but line 295 still generates a fresh `uuid` that is rendered as the brief `SESSION_ID`. On a `--resume-incomplete` re-dispatch the brief's `SESSION_ID` then diverges from status.md's retained `implementer_session` that finalize reports.
**Fix:** On `--resume-incomplete`, render `SESSION_ID` from the retained `implementer_session` read from status.md so the brief and finalize agree on one session id.

## Verdict

REQUEST_CHANGES
Batch 1 verify will fail: four transient-asserting test cases were not updated to incomplete.
MILL_REVIEW_END
