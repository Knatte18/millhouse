MILL_REVIEW_BEGIN
# Review: Wiki daemon error-log leak and stale plugin-cache config validation produce misleading noise

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-25
```

## Findings

### [GAP] Incomplete caller enumeration for load_config
**Section:** Problem §2 / Technical context (callers to verify)
**Issue:** Both the affected-scripts list and the post-refactor "verify still work" list omit `millpy-review-discussion.py:92` (imports `load_config` from `_review_common` at line 82) and the internal `_review_common.py:376` self-call — both invoke the duplicate being deleted.
**Fix:** Add `millpy-review-discussion.py` and the `_review_common.py:376` internal call to the affected/verify lists so the refactor covers every call site.

### [GAP] No test named for daemon-logger-consolidation
**Section:** Testing / Decision: daemon-logger-consolidation
**Issue:** Testing enumerates cases for exception-classification, stdio-redirection, and config-augmentation, but no test verifies connection-level logs actually route to the consolidated `wiki-server` destination and no longer reach root/stderr — the exact behavior the decision's rationale says is load-bearing.
**Fix:** Add a unit case asserting `DaemonBase` connection logging lands in the consolidated destination (not root/basicConfig stderr) post-refactor.

### [NOTE] Benign-typed exceptions from handle_request silenced
**Section:** Decision: daemon-exception-classification / Scope In
**Issue:** Type-based classification silences `OSError`/`JSONDecodeError`/`UnicodeDecodeError` "raised ANYWHERE," so a genuine business-logic `OSError` (e.g. an uncaught git/file failure) escaping `handle_request` drops to debug — in tension with the stated "genuine bugs stay visible" goal.
**Fix:** State whether benign-type silencing is intended even when the source is `handle_request`, or scope it to the pre-`handle_request` region.

### [NOTE] Redirect target left as alternatives
**Section:** Decision: daemon-stdio-redirection
**Issue:** The `Popen` redirect target is "e.g. `subprocess.DEVNULL`, or ideally to the daemon's own log file" — an unresolved either/or a plan writer could decide either way.
**Fix:** Pick one (DEVNULL is sufficient given logger-consolidation already owns the log file).

## Verdict

GAPS_FOUND
Incomplete caller list and a missing logger-consolidation test must resolve before planning.
MILL_REVIEW_END
