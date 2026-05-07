# Batch: backend-fixes

```yaml
task: '28 (A) — review-plan robustness'
batch: backend-fixes
number: 1
cards: 4
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Fix bugs B and C in `_review_plan.py` and update tests in `test-review-plan-flow.py`. Bug B makes the holistic `parse_verdict` failure path produce an ERROR entry instead of raising to the caller. Bug C removes stale per-batch entries from resume-mode results. Both fixes are in the same function (`run()`) and closely interact — after B, the holistic produces an ERROR entry; after C, a subsequent resume run returns only the fresh holistic entry. Test 17 must be updated to reflect the new resume behavior; test 20 is added for bug B.

This batch delivers the updated `_review_plan.py` and updated `test-review-plan-flow.py`. Batch 4 (SKILL.md step 4.5 trigger change for bug D) depends on this batch's ERROR entry being produced correctly.

## Cards

### Card 1: Bug B — catch ReviewError from parse_verdict in holistic else branch

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_review_plan.run()`, the holistic section has a `try/except LLMError` around `holistic_reviewer.run(...)`. The `else` branch currently calls `verdict = parse_verdict(raw)` without any protection against `ReviewError`. Wrap the entire body of the `else` branch in a `try/except ReviewError as exc:` block. On `ReviewError`: call `path = write_review_file(reviews_dir, "plan", round_n, raw, scope="holistic")` to write the raw LLM output to a review file (for operator inspection), then append `{"scope": "holistic", "round": round_n, "verdict": "ERROR", "blocking_count": 0, "file": str(path), "error": f"parse_verdict failed: {exc}", "session_id": session_id}` to `reviews`. Do not re-raise. This single outer `try/except ReviewError` covers both `parse_verdict(raw)` calls: the one at the start of the else branch and the one inside the NEED_CONTEXT retry sub-branch's inner `else`. The pattern matches the per-batch `_review_one_batch` which wraps its entire body in `except ReviewError at line 247.
- **Commit:** `fix(_review_plan): catch ReviewError from parse_verdict in holistic section (#185)`

### Card 2: Bug C — exclude stale per-batch entries from resume-mode result

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_review_plan.run()`, in the `if resume_round is not None:` block (roughly lines 342–380), remove the `reviews.extend(_disk_reviews)` call. Keep the `_disk_reviews` list construction loop and the `print(f"[_review_plan] resuming round {resume_round} from {len(_disk_reviews)} on-disk per-batch files; firing holistic only", ...)` stderr log. After this change `reviews` remains empty when entering the holistic section; the holistic appends its single entry; the final `reviews` list contains only that holistic entry. The `_disk_reviews` variable and loop are retained for debuggability (the log already reports the count).
- **Commit:** `fix(_review_plan): exclude stale per-batch entries from resume-mode result (#184)`

### Card 3: Test 20 — holistic parse_verdict failure becomes ERROR entry

- **Context:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add Test 20 to `test-review-plan-flow.py` after Test 19. Setup: one-batch plan (alpha), holistic enabled. Seed the stub with two responses: `(APPROVE_TEXT, "sid-batch")` for the per-batch call and `("# Raw prose without any yaml block\n\nThe plan looks fine.", "sid-hol")` for the holistic call (no ```yaml block → `parse_verdict` raises `ReviewError`). Call `plan_run(cfg, SLUG, mill_dir, wiki_root, project_root)`. Assertions:
  - No `ReviewError` raised.
  - `r.verdict == "REQUEST_CHANGES"` (aggregate of APPROVE + ERROR = REQUEST_CHANGES via `aggregate_verdict`).
  - `len(r.reviews) == 2` (one per-batch APPROVE entry and one holistic ERROR entry).
  - The holistic entry: `rv_hol["scope"] == "holistic"`, `rv_hol["verdict"] == "ERROR"`, `rv_hol["file"] is not None` (review file was written), `"parse_verdict failed" in rv_hol.get("error", "")`.
  Follow the `with tempfile.TemporaryDirectory() as tmpdir:` + try/except/finally pattern used by all other tests.
- **Commit:** `test(_review_plan): test 20 — holistic parse_verdict failure → ERROR entry (#185)`

### Card 4: Update Test 17 for bug C — resume now returns holistic-only

- **Context:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Update Test 17 in `test-review-plan-flow.py` to assert the new post-fix behavior (holistic-only reviews[] in resume mode). Changes:
  - Change `assert len(r.reviews) == 3` → `assert len(r.reviews) == 1`.
  - Remove the `rv_alpha`, `rv_beta` variable definitions and all their assertions (these scopes are no longer in `reviews[]` after the fix).
  - Keep `rv_hol = next((rv for rv in r.reviews if rv["scope"] == "holistic"), None)` and the `assert rv_hol is not None` / `assert rv_hol["session_id"] == "sid-hol-resume"` assertions.
  - Update the print string to: `"PASS test17: mid-round resume — stub fires once (holistic only), holistic-only result (bug C fix #184)"`.
  The stub setup, `reviews_dir.mkdir`, and per-batch file pre-population are unchanged.
- **Commit:** `test(_review_plan): update test 17 for bug C — resume returns holistic-only (#184)`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` runs all unit tests. Relevant tests in `test-review-plan-flow.py`:
- Test 17: mid-round resume (updated assertions for holistic-only result)
- Test 20: holistic parse_verdict failure → ERROR entry (new)
- Tests 1–16, 18–19: must continue passing (regression check)
