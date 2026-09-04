MILL_REVIEW_BEGIN
# Review: millpy-implement/fix.py: stuck-type false positives and session-hygiene gaps

```yaml
duration_s: 233.0
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] self_resolve_remint_at rejected by _status.py's closed key allow-list
**Section:** Decision `956-fresh-session-after-self-resolve`, "Compounding-retry fix" **Issue:** The corrected fix writes the new batch field via `_status.set_batch_fields(status_path, batch_name, {"self_resolve_remint_at": ...})` and claims this "folds into that same existing `set_batch_fields` call... no new write or commit needed." But `_status.py:512-521` defines `_BATCH_ALLOWED_KEYS` as a closed set (`state`, `implementer_session`, `commit_sha`, `start_sha`, `review_round`, `review_file`, `blocked_reason`, `verify_baseline_failures`) that both `set_batch_field` (line 961) and `set_batch_fields` (line 993) validate against, raising `ValueError` for any unlisted key — confirmed by the docstring at line 957: "Unknown keys raise ValueError so typos fail loudly." `self_resolve_remint_at` is not in that set, so the call as described would crash at runtime, not silently succeed. **Fix:** State explicitly that `_BATCH_ALLOWED_KEYS` in `_status.py` must also be extended to include `self_resolve_remint_at` as new plumbing for #956 — this is a real, additional code change the discussion currently omits, not covered by "no new write or commit needed."

## Verdict

REQUEST_CHANGES
The #956 field-write fix crashes against `_status.py`'s closed key-allow-list; the discussion must acknowledge the required schema change.
MILL_REVIEW_END
