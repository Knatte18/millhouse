MILL_REVIEW_BEGIN
# Review: millpy-implement/fix.py: stuck-type false positives and session-hygiene gaps

```yaml
duration_s: 223.0
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not independently knowable)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] 955 heartbeat join-point rests on a false premise about `_worker_main`'s control flow
**Section:** Decision `955-heartbeat-for-diagnosability`. **Issue:** Verified `millpy-bg.py:56-89` (`_worker_main`): the original `log_f` handle lives only inside the `with open(log_path, "w", ...) as log_f:` block (lines 58-69), which exits — closing that handle — either at `return 0` (line 70, success path) or when control leaves the block on exception; the `finally` block (lines 80-89) runs strictly *after* that closure and opens its own fresh `"a"`-mode handle for the EXIT write, never seeing the original `log_f`. Stopping/joining the heartbeat thread "in the existing finally block" per the decision text is therefore too late to guarantee the thread isn't mid-write on the now-closed original handle — a live heartbeat thread racing the `with` block's exit can hit `ValueError: I/O operation on closed file` inside the thread, silently dropping writes and printing thread-hook noise, directly undercutting the decision's own "does not open a second handle" premise. **Fix:** correct the decision to join the heartbeat thread immediately after `subprocess.run()` returns, still inside the `with` block (before line 69's dedent), not in `finally`; note the `finally` block already opens an independent `"a"` handle for the EXIT write regardless.

## Verdict

REQUEST_CHANGES
955's heartbeat-thread join point rests on a false premise about where `_worker_main`'s file handle actually closes.
MILL_REVIEW_END
