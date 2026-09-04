MILL_REVIEW_BEGIN
# Review: millpy-implement/fix.py: stuck-type false positives and session-hygiene gaps

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude (Sonnet 5 family; system-reported model id claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] #954 fix verified against only 1 of 4 `_run_verify_gates` call sites
**Section:** Decision `954-commit-baseline-write-before-dirty-check` + Technical context. **Issue:** `_forward_output` calls `_run_verify_gates` four times (`_implementer_common.py:1865, 2091, 2201, 2311` — explicit-JSON-success path plus three no-JSON inference branches), all four already forwarding identical `status_path`/`batch_name`/`start_sha`, so all four are equally reachable through the corroboration-waiver branch that #954 fixes. The discussion's root-cause citation and ordering proof ("`_run_verify_gates` runs at line ~1865, `_in_scope_dirty_stuck` at line 1975") name only the first call site, and the decision never states whether `git_name`/`git_email` must be threaded to all four or just one; Testing candidate (a) also only exercises the explicit-JSON path. **Fix:** State explicitly that `git_name`/`git_email` must be forwarded from `_forward_output` to every `_run_verify_gates` call site (not just the one cited), and add a testing candidate covering the no-JSON-inference success path so an implementation that only fixes the first call site cannot pass review.

## Verdict

REQUEST_CHANGES
One BLOCKING: #954's fix is verified/tested against only one of four reachable call sites.
MILL_REVIEW_END
