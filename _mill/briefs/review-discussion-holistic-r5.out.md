MILL_REVIEW_BEGIN
# Review: Blocking phase-wait gate for mill-plan/mill-go chaining

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point-release unknown)
reviewed_file: _mill/discussion.md
date: 2026-07-30
```

## Findings

### [GAP] Poll script's BLOCKED marker duplicates the YAML key label
**Section:** Poll script contract
**Issue:** `reason=$(grep "^blocked_reason:" "<status_path>" | head -1)` captures the *entire* matched line (`blocked_reason: <value>`, verified against `_status.py`'s `set_blocked`, which writes exactly that `key: quote_scalar(value)` shape). `echo "BLOCKED: ${reason}"` therefore prints `BLOCKED: blocked_reason: <value>` — the field label is duplicated and any YAML quoting `quote_scalar` added survives verbatim into the operator-facing message.
**Fix:** Strip the `blocked_reason:` prefix (and any surrounding YAML quotes) before interpolating, so `${reason}` is the bare value — matching the "surfacing `<blocked_reason>`" framing already used in the "Orchestrator reaction to BLOCKED/TIMEOUT" Decision.

## Notes

### [NOTE] Concurrent-waiter risk framing understates how fast the lock goes stale
**Section:** "Concurrent-waiter builder-lock exclusion..." Decision
**Issue:** `_builder_lock.STALE_WINDOW_SEC` is 300s (5 min), verified in `_builder_lock.py` — far shorter than the 120-min default wait, so the lock is fully stale for nearly the entire wait duration, not a risk that "grows... to the full wait duration" gradually as currently worded.
**Fix:** If this Decision is revisited, cite the concrete 5-minute threshold; does not change the already-accepted out-of-scope verdict.

## Verdict

GAPS_FOUND
One GAP: poll script's BLOCKED-reason extraction leaks the YAML field label into the operator-facing message.
MILL_REVIEW_END
