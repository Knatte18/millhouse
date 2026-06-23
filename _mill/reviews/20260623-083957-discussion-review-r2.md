All claims verified against source. The discussion is technically grounded, scope is clear, all four issues have concrete decisions with rationale + rejected alternatives, round-1 GAP and NOTEs are resolved, testing strategy is named per area with TDD candidates, and constraints (ASCII, win32-gate, verify-prefix, path-resolution) are acknowledged.

One thing worth noting: `parse_blocking_count` has a keyword-only `severity` parameter (`*, severity`), so the #515 nit-gate's call must use `parse_blocking_count(text, severity="NIT")` — but this is an implementation detail the plan writer will handle, not a discussion gap. I found no GAPs that would block plan writing.

MILL_REVIEW_BEGIN
# Review: Fix nit-enforcement gate, Windows verify false-positive, reviewer oscillation, and scope-violation handling

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-23
```

## Findings

### [NOTE] Concatenated holistic verify_cmd: PYTHONPATH-prefix collision
**Section:** Decisions / #518b (Structural catch)
**Issue:** Joining each batch's `PYTHONPATH= <cmd>` with `&&` yields `... && PYTHONPATH= <cmd2>`; the second prefix is fine, but a batch with `verify: null` plus a non-null sibling must not produce a dangling `&&` or empty leading segment.
**Fix:** State the join contract explicitly — filter null/empty commands first, then join survivors; all-null derives `None` (no gate), as already noted in Testing.

### [NOTE] Nit-gate severity arg is keyword-only
**Section:** Decisions / #515 (gate via parse_blocking_count)
**Issue:** `parse_blocking_count(raw_output, *, severity)` is keyword-only (verified `_review_common.py:1288`); a positional call in `_nit_gate.compute_unfixed_nits` would TypeError.
**Fix:** Note that the gate must call `parse_blocking_count(text, severity="NIT")` — implementation detail, not a scope question.

## Verdict

APPROVE
All four fixes have grounded decisions, resolved round-1 gaps, and named per-area tests; notes are non-blocking.
MILL_REVIEW_END
