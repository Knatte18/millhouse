MILL_REVIEW_BEGIN
# Review: _plan_validate and baseline verify gate gaps

```yaml
duration_s: 28.9
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-24
```

## Findings

### [NIT:design] None sentinel vs. call-site typing/copy
**Section:** baseline-short-circuit-unknown **Issue:** `compute_batch_baselines` does `list(by_pair[pair])` (_verify_baseline.py:291) and `pair_cache` is typed `dict[..., list[str]]` (also at millpy-implement.py:432); a `None` value would raise TypeError, and the discussion changes only the return type. **Fix:** Note that the copy step and the `pair_cache` type annotations must handle `None`.

### [NIT:design] Driver must branch explicitly on None
**Section:** baseline-short-circuit-unknown **Issue:** millpy-implement.py:456 writes `batch_result[name]` unconditionally, and `_status.set_batch_field` with None would create the key (which the idempotence check at :424 treats as "captured"). The discussion says the key is not written but does not say the driver needs an explicit skip. **Fix:** State that the driver skips `set_batch_field` when the value is None (already implied; make it explicit and tested).

## Verdict

APPROVE
Decisions are grounded in the source; only minor implementation-detail NITs remain.
MILL_REVIEW_END
