MILL_REVIEW_BEGIN
# Review: Blocking phase-wait gate for mill-plan/mill-go chaining

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (Sonnet 5, per system context)
reviewed_file: _mill/discussion.md
date: 2026-07-30
```

## Findings

### [GAP] Builder-lock same-slug refresh does not exclude a second concurrent waiter
**Section:** Decisions — "Automatic default, not opt-in" / Technical context (`_builder_lock.py`)
**Issue:** `_builder_lock.acquire` (verified in `plugins/mill/scripts/_builder_lock.py` lines 117-145) explicitly refreshes-and-succeeds for a same-slug caller ("idempotent by design: a crashed mill-go restarting... should not have to manually clear its own lock"). Today the entry-gate hard-halts immediately, so this window is seconds; with a 120-minute default wait, an operator who forgets/kills the first waiting session and re-invokes `/mill-go` in a second terminal gets a *second* wait that silently refreshes the same lock, and both sessions can independently observe `READY` and both proceed into Prepare/Execute for the same batch.
**Fix:** Add a Decision addressing whether the long-lived wait needs stronger same-slug exclusion (e.g. record/check the waiting session's own handle before re-arming) or explicitly accept this as an unchanged pre-existing risk, analogous to the already-accepted "Liveness ambiguity" scope-out.

### [NOTE] `build_wait_command`'s ready/blocked grep is not end-anchored
**Section:** Decisions — "Poll script contract"
**Issue:** `grep -q "^phase: <ready_phase>"` anchors only the start of the line; if a future phase value is ever added that extends an existing target as a prefix (e.g. a hypothetical `planned-v2`), the wait would false-positive on partial match. Safe today only because the current closed phase set has no such overlaps.
**Fix:** Anchor the pattern with a trailing `$` (or a delimiter check) in `build_wait_command`, or note explicitly why prefix-safety is guaranteed by the closed phase-value set and will need re-verification if that set grows.

### [NOTE] `matches_wait_trigger`'s `prefix_patterns` parameter name doesn't match its documented semantics
**Section:** Technical context — `_phase_wait.py` second helper
**Issue:** The patterns described (`^plan-review-r\d+$`, `^plan-fix-r\d+$`) are fully-anchored full-match regexes, not prefix matches, but the proposed parameter is named `prefix_patterns`.
**Fix:** Rename to `regex_patterns` (or similar) to avoid an implementer reading "prefix" and reaching for `str.startswith()` instead of `re.fullmatch()`.

## Verdict

GAPS_FOUND
One concurrency gap (builder-lock same-slug refresh) needs an explicit decision before plan writing.
MILL_REVIEW_END
