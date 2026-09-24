MILL_REVIEW_BEGIN
# Review: _plan_validate and baseline verify gate gaps

```yaml
duration_s: 47.2
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: /home/knatte/Code/millhouse/wts/plan-verify-gate-gaps/_mill/discussion.md
date: 2026-09-24
```

## Findings

### [BLOCKING:design] Seeded pair_cache bypasses the short-circuit detection
**Section:** baseline-short-circuit-unknown / Technical context **Issue:** Detection lives only in `_signatures_for_pair`, but `_run_per_batch_baseline_standalone` (millpy-implement.py:432-435) pre-seeds `pair_cache[(cmd, cwd)]` with the module-wide `list[str]`, so a batch whose compound `&&` verify string equals the module-wide command never reaches the detector and still records the misleading signature list. The discussion only says the seed "must not break". **Fix:** State the disposition for a seeded compound pair (e.g. skip seeding, or apply the same all-synthetic + `&&` test to the seed) and add a test.

### [NIT:consistency] "first-batch-stem" in the card-1 message is undefined
**Section:** card-numbering-starts-at-1 **Issue:** The card-numbering check is a global minimum across batch files, but the message names "<first-batch-stem>" without saying whether that is the first file in the list or the batch holding the minimum. **Fix:** Pick one (the batch containing the minimum card is more useful) and state it.

### [NIT:design] Holistic fix path silently skips None baselines
**Section:** baseline-short-circuit-unknown **Issue:** millpy-fix.py:470-476 unions per-batch baselines and skips falsy values. With a `None` batch among non-empty ones, the holistic gate waives only the other batches' signatures. That is probably fine, but the discussion lists only 455 as a downstream consumer and does not confirm this path. **Fix:** Note the holistic-union behaviour as acceptable, or cover it with a test.

### [NIT:scope] Wider trade-off than the one stated
**Section:** Known trade-off **Issue:** The rule "`&&` present and all signatures synthetic" also marks a compound whose last conjunct fails with non-marker output (e.g. `lint && go build` with a compile error) as unknown, not just a first-conjunct failure. **Fix:** Widen the stated trade-off to cover this.

## Verdict

REQUEST_CHANGES
The seeded pair_cache path can bypass the new detection; the disposition is undecided.
MILL_REVIEW_END
