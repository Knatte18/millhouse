MILL_REVIEW_BEGIN
# Review: Fix unit test suite failures, spurious review warning, and implementer verify-gate gaps — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-16
```

## Findings

### [NIT] test-millpy-fix.py in verify but not in Context
**Location:** Batch 3 (cards 6/7), 00-overview batch 3 verify
**Issue:** Batch 3's `verify:` runs `test-millpy-fix.py` and card 6 edits `millpy-fix.py`, but `test-millpy-fix.py` is absent from every card's `Context:`/`Edits:` and from the holistic manifest, so the implementer cannot confirm the regression run stays green.
**Fix:** Add `plugins/mill/unit_tests/test-millpy-fix.py` to card 6's or card 7's `Context:` so the implementer can read the existing fix-path cases before threading `verify_cmd`.

### [NIT] Card 5 gate-after-drift wording vs. emit-point ordering
**Location:** Batch 3, card 5
**Issue:** `_forward_output` has four success emits (parsed at L250/252, inferred at L290 post-drift, L299, L310); the "gate runs AFTER `_commit_formatter_drift`" rule is unambiguous only for the L290 path — the other inferred emits have no drift commit between HEAD-capture and emit, so re-reading HEAD inside the gate is redundant but harmless.
**Fix:** Optional — note that for the non-drift emits the gate simply runs against the already-current HEAD; no behavioural change needed.

## Verdict

APPROVE
Plan is well-grounded, sequencing and DAG are sound; only two minor context/clarity nits.
MILL_REVIEW_END
