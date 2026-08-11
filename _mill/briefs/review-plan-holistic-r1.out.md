MILL_REVIEW_BEGIN
# Review: mill-go2: fork-based implementer dispatch — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: plan/
date: 2026-08-11
```

## Findings

### [BLOCKING:design] Card 5's "second site" claim is factually wrong
**Location:** batch 2, card 5, requirement 3. **Issue:** The requirement says to amend the base's closing sentence to name mill-go2's implementer override as "an experimental second site," but `mill-plan/SKILL.md`'s existing "Fork scope guardrail" section (lines 118-127) already documents a second, currently-live fork-usage site (Phase: Plan) alongside mill-start's Explore phase — mill-go2 would be at minimum a third site, and the closing sentence should plausibly also cite `mill-plan/SKILL.md`. **Fix:** Correct the requirement to count/cite all pre-existing fork-usage sites (mill-start Explore, mill-plan Phase: Plan) before adding mill-go2, or state explicitly why mill-plan's usage doesn't count.

### [BLOCKING:design] Cold-fallback trigger doesn't clearly cover all implementer re-dispatch points
**Location:** batch 2, card 4, "Cold fallback, once per batch" bullet. **Issue:** The override names exactly two "Forked dispatch points" (initial dispatch, step-4(a)'s transient retry) and explicitly carves out 6.5.2 as cold, but the base's Override point A applies per-role to every `Agent()` call site, not just named ones — and `### Stuck escalation` has its own separate one-shot re-fires for `transient` (already-retried-once) and `verify`/`logic` (first occurrence) that aren't step-4 calls and aren't explicitly assigned fork-or-cold. **Fix:** Enumerate every implementer `Agent()` call site in the base (step-4(a), Stuck-escalation's transient/verify/logic re-fires, 6.5.2) and state fork-or-cold for each, rather than relying on the ambiguous phrase "terminal-failure re-dispatch under the base's step-4 classification."

### [NIT:consistency] New helper omitted from `_status.py`'s module docstring
**Location:** batch 1, card 2. **Issue:** `_status.py`'s top docstring lists every public function under "Public API," including `append_recovery_log` and `append_inferred_success_log`, but card 2's requirements never ask for `append_fork_fallback_log` to be added to that list, breaking the established documentation convention. **Fix:** Add a requirement line instructing the docstring's Public API list to gain `append_fork_fallback_log(status_path, batch_name, timestamp) -> None`.

## Verdict

REQUEST_CHANGES
Two design gaps in batch 2's fork-override text (site count, re-dispatch coverage) plus one doc-consistency NIT in batch 1.
MILL_REVIEW_END
