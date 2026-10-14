MILL_REVIEW_BEGIN
# Review: Drop the eager verify-baseline pre-flight

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: C:\Code\millhouse\wts\drop-verify-baseline-preflight\_mill\discussion.md
date: 2026-10-14
```

## Findings

### [BLOCKING:decision] `_extract_failure_signatures`' `returncode` / NONZERO_EXIT synthesis has no disposition
**Section:** Scope (`_implementer_common.py`), Decision `signatures-field` **Issue:** The discussion says `_extract_failure_signatures` stays, but the only caller passing `returncode=` is `_run_verify_gate`'s `signatures = ...` line (deleted here), and `_done_gate.py` and the tail-truncation recovery both call it without `returncode`, so the `returncode` parameter and the synthetic `NONZERO_EXIT:` branch lose every production caller (their remaining consumers are tests). **Fix:** State whether the `returncode` parameter and `NONZERO_EXIT` synthesis (and their unit-test cases in `test-implementer-common.py`) are kept or removed, with rationale consistent with the YAGNI reasoning used for `"signatures"`.

### [NIT:scope] Stale present-tense comment in `_plan_dag.py`
**Section:** Scope (present-tense comments) **Issue:** The `parse_verify_field` docstring in `plugins/mill/scripts/_plan_dag.py` (~line 507) lists "baseline" among the read sites of the `verify:` field, which describes removed code in the present tense; it is absent from the enumerated comment edits, and the final grep (which keys on specific identifiers, not the word) will not catch it. **Fix:** Add it to the present-tense comment list (drop "baseline" from the site list).

## Verdict

REQUEST_CHANGES
One undisposed artifact (`returncode` synthesis in `_extract_failure_signatures`) must be decided before planning.
MILL_REVIEW_END
