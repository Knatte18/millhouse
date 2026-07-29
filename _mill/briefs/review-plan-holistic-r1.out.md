MILL_REVIEW_BEGIN
# Review: Review dispatch: no per-round reviewer override, and reviewer_model echoes the dispatch flag instead of the model that ran — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-07-29
```

## Findings

### [BLOCKING] effort field never forwarded to test_stub provider
**Location:** Batch unit-tests-discussion / Card 14 check 4; Batch unit-tests-plan / Card 16 check 4
**Issue:** `_reviewer_single.run()` (lines 49-51) calls `stub.run(prompt_text, session_id=session_id, resume=resume, timeout=timeout)` for `provider == "test_stub"` — it never passes `effort`, so `stub.captured_prompts()[-1][1]["effort"]` is always `None` regardless of the resolved spec's `effort` field. Both cards seed two `test_stub` specs distinguished only by `effort` ("max" vs "low") and assert `stub.captured_prompts()[-1][1]["effort"] == "max"` to prove `maybe_switch_spec_for_large_prompt` was skipped; this assertion will fail (actual value `None`), and no other field distinguishes the two specs (both use the same placeholder `model`).
**Fix:** Either have `_reviewer_single.run()` forward `effort=spec.get("effort")` to `stub.run(...)` (out of this plan's current scope/cards), or redesign the two checks to distinguish dispatched spec via a different observable (e.g. distinct `model` values plus asserting on `spec["model"]` via a stub extension, or a `prompt_observer` capturing something spec-derived).

### [BLOCKING] Context completeness: cross-file helper references missing from Context
**Location:** Batch unit-tests-discussion / Cards 13, 14; Batch unit-tests-plan / Card 15
**Issue:** Card 13 check 3 and Card 15 check 3 instruct "mirror `test-large-prompt-switch.py`'s `_make_registry_with_cluster` shape", and Card 14 check 3 instructs "mirroring `test-reviewers.py::test_single_gemini_bulk_mode`'s save/restore pattern" — but neither `test-large-prompt-switch.py` nor `test-reviewers.py` is listed in Card 13's, Card 14's, or Card 15's `Context:` (Card 13/14 Context = `_review_discussion.py`/`_review_common.py`/`_reviewers.py`/`_reviewer_test_stub.py`; Card 15 Context = `_review_plan.py`/`_review_common.py`). Per this plan's own Context-completeness rule, a function named in `Requirements:` from a file not in `Context:`/`Edits:` forces cold-start exploration.
**Fix:** Add `plugins/mill/unit_tests/test-large-prompt-switch.py` to Card 13's and Card 15's `Context:`, and `plugins/mill/unit_tests/test-reviewers.py` to Card 14's `Context:` (Card 16 references "Card 14, check 3" cross-batch; consider inlining the pattern text there too rather than requiring the batch-05 file).

### [NIT] Card 1 misnames the exception raised on `None.startswith(...)`
**Location:** Batch reviewer-override-helper / Card 1, step 3
**Issue:** The rationale states a naive `model_to_tier(spec.get("model"))` call on a spec with no `model` key "would fail with `TypeError`"; in CPython, `None.startswith(...)` raises `AttributeError`, not `TypeError`.
**Fix:** Correct the parenthetical to say `AttributeError`. Does not change the required ordering (the missing-model check must still run before step 4).

### [NIT] Overview's rounds=0 rationale overstates `_review_plan.py::prepare()`'s existing behavior
**Location:** 00-overview.md / "Decision: `--reviewer` bypasses a `reviewer: null` disablement, not a `rounds: 0` disablement"
**Issue:** The rationale claims `rounds: 0` is "checked independently (in `prepare()`'s `effective_max == 0` branch ... before any reviewer-name resolution runs)" for all four resolution sites, but `_review_plan.py::prepare()`'s holistic branch (lines 462-553) has no `rounds == 0` check at all — only `_review_discussion.py::prepare()` has this check; `_review_plan.py` only checks rounds in `run()`. Card 5 correctly does not add such a check, so this is a documentation-only inaccuracy, not an implementation gap.
**Fix:** Scope the rationale sentence to `_review_discussion.py::prepare()` and `run()`'s early-return stubs (both backends), rather than implying `_review_plan.py::prepare()` has an equivalent gate.

## Verdict

REQUEST_CHANGES
Two BLOCKING issues: a broken effort-based dispatch assertion in two test batches, and missing Context entries for cross-file helper references.
MILL_REVIEW_END
