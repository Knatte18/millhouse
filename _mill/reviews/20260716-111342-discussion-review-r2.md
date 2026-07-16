MILL_REVIEW_BEGIN
# Review: Batch verify/baseline/completeness gates produce false positives or time out

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-16
```

## Findings

### [GAP] #650 pre-flight implementation locus unnamed
**Section:** Decisions → done-gate-baseline-preflight
**Issue:** The decision frames the pre-flight only as a "new SKILL.md Prepare step," but the pattern it mirrors (0.5 Baseline pre-flight) is a CLI stage — SKILL.md line 224 invokes `millpy-implement.py --stage baseline` — and Testing requires a mocked-subprocess unit test, which needs code; yet no CLI stage/function/file is named (unlike the explicit loci given for #638, #642, #660).
**Fix:** State whether #650 adds a new `millpy-*.py --stage` (name it) invoked from SKILL.md, or is orchestrator-Bash-only prose (and if so, how the unit test in Testing is satisfied).

### [NOTE] `_reclassify_verify_failure` shares the buggy count heuristic
**Section:** Decisions → completeness-recount-cards-done (#660)
**Issue:** `_reclassify_verify_failure` (called at `_implementer_common.py:1021/1208/1304/1396`, immediately before each `_batch_completeness_stuck` call) uses the same `0 < content < card_count → incomplete` logic #660 identifies as wrong for brief-sanctioned combined commits, but the fix threads `cards_done` only into `_batch_completeness_stuck`.
**Fix:** State whether `_reclassify_verify_failure` also becomes `cards_done`-aware or is intentionally out of scope (it only fires on a real verify failure).

### [NOTE] Verify-present short-circuit interaction with cards_done left implicit
**Section:** Decisions → completeness-recount-cards-done (#660)
**Issue:** `_batch_completeness_stuck` today returns None when `verify_cmd is not None and not ignore_verify` (line 215); the decision doesn't say whether this short-circuit is preserved under the new `card_ids - cards_done` rule, leaving the fix's applicability domain (no-verify / ignore_verify paths only vs. always) ambiguous.
**Fix:** State explicitly that the verify-present short-circuit is kept (cards_done supplements the count only on the paths the gate currently runs).

### [NOTE] done_gate pre-flight exit-code contract unspecified
**Section:** Decisions → done-gate-baseline-preflight (#650)
**Issue:** If the pre-flight done_gate command exits non-zero or emits `status: blocked` (the Handoff-time gate halts on this, SKILL.md:796), the decision doesn't say whether the pre-flight halts the task before batch 1, warns, or proceeds.
**Fix:** State the pre-flight is non-blocking / fail-safe (mirroring `_run_baseline_stage`, which never raises and leaves the field unset).

## Verdict

GAPS_FOUND
One design-locus gap (#650) plus three clarifications on gate interactions and failure handling.
MILL_REVIEW_END
