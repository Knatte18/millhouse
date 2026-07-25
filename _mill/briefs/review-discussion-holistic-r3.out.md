MILL_REVIEW_BEGIN
# Review: Wiki daemon error-log leak and stale plugin-cache config validation produce misleading noise

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-25
```

## Findings

### [NOTE] Bug-1 field-report narrative not reconciled with confirmed-present inner guard
**Section:** Problem (item 1) / daemon-exception-classification rationale
**Issue:** `_daemon.py:142-153`'s inner guard (verified present, correctly scoped to `json.JSONDecodeError` on `json.loads(msg_text)`) already exists in current code, yet #684/#687/#688 report the exact literal `JSONDecodeError(...)` string escaping via the *outer* handler — which the inner guard should prevent for that specific exception/call-site combination; the discussion doesn't consider whether some/all of those reports came from a daemon running stale (plugin-cache-lag) code predating the guard, a mechanism directly analogous to bug 2's core theme in this same task.
**Fix:** One-line acknowledgment that field reports may reflect cache/publish lag rather than a live code gap, and that the shipped fix faces the same rollout-lag exposure before it's observable — consistent with the existing out-of-scope note on cache-refresh timing.

## Verdict

APPROVE
All decisions, line citations, caller lists, and test-file references verified accurate against source; only a non-blocking narrative note remains.
MILL_REVIEW_END
