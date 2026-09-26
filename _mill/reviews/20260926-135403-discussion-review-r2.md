MILL_REVIEW_BEGIN
# Review: mill-merge: run the deterministic path as one script

```yaml
duration_s: 254.1
verdict: APPROVE
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-09-26
```

## Findings

### [NIT:consistency] "notify failure" warning contradicts `_notify.notify`'s contract
**Demoted-from:** BLOCKING
**Section:** Decision `json-result-contract` (`warnings` field) and Decision `routing-preserved` (Step 9).
**Issue:** Both cite "notify failure" as a `warnings`-list entry, but `_notify.notify` (`plugins/mill/scripts/_notify.py`) is documented and implemented to never raise and never return a success/failure signal to the caller — delivery errors are "logged to stderr and swallowed" by design, so `_merge.py` has no value to put in `warnings`.
**Fix:** Either state that `_notify.py` gets a small additive helper/return value to expose delivery failure (permissible per Scope's "small additive helpers" carve-out, since `_notify` isn't in the frozen-internals list), or drop "notify failure" from the `warnings` examples and leave notify failures silent as today.

### [NIT:consistency] "one helper" for `subproc_s` may not cover `_client` calls
**Section:** Decision `timing`.
**Issue:** The decision says one helper accumulates elapsed time for "git, gh, and `_client` calls," but `_client` calls go through a socket/daemon client (`wiki/_client.py`), not a subprocess — a helper written narrowly around `subprocess.run` won't time them without a generic wrapper.
**Fix:** State explicitly that the timing helper wraps arbitrary callables (not just subprocess invocations) so it can also wrap `_client` calls.

## Verdict

APPROVE
One blocking consistency gap: notify-failure warning conflicts with `_notify`'s no-signal contract.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
