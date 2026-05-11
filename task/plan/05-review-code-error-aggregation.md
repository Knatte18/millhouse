# Batch: review-code-error-aggregation

```yaml
task: 44 (A) — Bug-fix batch 4
batch: review-code-error-aggregation
number: 5
cards: 3
verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-review-code-flow.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-review-plan-flow.py
depends-on: [4]
```

## Batch Scope

Currently when `_reviewer_single.run` raises `LLMError` (including `LLMRateLimitError`), `_review_code.py` returns a top-level `verdict: "REQUEST_CHANGES"` with `reviews[0].verdict = "ERROR"` (#228). The orchestrator (mill-go) reads only the top-level `verdict` and dispatches the implementer to fix — but the review file is `null`, so the fix can't proceed. Fix: when every entry in the constructed `reviews[]` has `verdict == "ERROR"`, set the top-level `verdict` to `"ERROR"`. mill-plan's `_review_plan.py` already has the same code pattern documented at its line-281 docstring (`all-ERROR → REQUEST_CHANGES; no raise`); audit and align both modules to the new convention (`all-ERROR → top-level ERROR; no raise`). The corresponding mill-go SKILL.md step 4.5 ("ERROR-only-aggregate retry") is added in Batch 8.

Depends on Batch 4 because this batch's verify re-runs `test-review-code-flow.py` and `test-review-plan-flow.py`; those files must pass before this batch ships its own additions.

## Cards

### Card 9: Add all-ERROR → top-level ERROR aggregation to `_review_code.run`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_reviewer_single.py`
  - `plugins/mill/scripts/_llm_claude.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Identify every `return ReviewResult(...)` in `_review_code.py`. There are three relevant cases:
     - First `LLMError` fallback (around line 302): top-level `verdict="REQUEST_CHANGES"`, `reviews=[{verdict: "ERROR", ...}]`.
     - Resume-retry `LLMError` fallback (around line 343): top-level `verdict="REQUEST_CHANGES"`, `reviews=[{verdict: "ERROR", ...}]`.
     - Normal-path return (around line 369): top-level `verdict=verdict` (parsed), `reviews=[{verdict: verdict, ...}]`.
  2. In ALL three cases, immediately before constructing the return value, compute: `all_errors = all(r.get("verdict") == "ERROR" for r in reviews_list)` where `reviews_list` is the local variable holding the `reviews=[...]` content. If `all_errors and len(reviews_list) >= 1`, override the top-level `verdict` variable to `"ERROR"`. Then construct the `ReviewResult` as before.
  3. For the normal-path return, this only fires when the LLM raised `LLMError` mid-call — but the existing structure raises and returns early, so `all_errors` will only be True in the two fallback cases. The third return-site change is for consistency only; verify by reading the code that `all_errors` cannot be True there unless future code adds an ERROR-injection path.
  4. Do NOT change `blocking_count` aggregation — it stays at `0` in the fallback cases (no review file → no findings). Do NOT change the `reviews[]` shape — each entry keeps `{scope, verdict, file, error?, session_id?}`.
  5. Refactor consideration: extract `def _aggregate_top_verdict(reviews_list: list[dict], parsed_verdict: str) -> str` into a local helper at the top of the module (`return "ERROR" if reviews_list and all(r.get("verdict") == "ERROR" for r in reviews_list) else parsed_verdict`). Call it from all three return-sites. This keeps the three call sites symmetric and makes Batch 5's test easier to target.
- **Commit:** `fix(_review_code): propagate all-ERROR sub-reviews as top-level ERROR (#228)`

### Card 10: Align `_review_plan` aggregation with the new convention

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Read `_review_plan.py` end-to-end. The module-level docstring (lines 6–8) and the `_aggregate_reviews` (or equivalent) function's comment (line 281) currently state "all-ERROR → REQUEST_CHANGES; no raise". Update both texts to read "all-ERROR → ERROR; no raise" so the two modules share semantics.
  2. Audit the actual aggregation site (look for the final `ReviewResult(...)` construction in `_review_plan.run`, near line 503, 538, 604, plus the holistic-aggregation logic around line 369). At each construction site, ensure the same `all_errors` check fires; if `_review_plan.py` ALREADY returns top-level ERROR when all sub-reviews are ERROR, this card is doc-only. If it returns top-level REQUEST_CHANGES today (matching the stale docstring), update the construction to match the new convention.
  3. If a shared helper is appropriate, put `_aggregate_top_verdict` from Card 9 into `_review_common.py` instead, exported as a public function, and have BOTH `_review_code.py` and `_review_plan.py` import it. Decide based on what already exists in `_review_common.py`; if the module already has small public helpers like `parse_verdict`, add `_aggregate_top_verdict` (or `aggregate_top_verdict`) there.
  4. Do NOT change the mill-plan SKILL.md step 4.5 — that is already correctly written for top-level ERROR detection.
- **Commit:** `fix(_review_plan): align all-ERROR aggregation with code reviewer (#228)`

### Card 11: Test all-ERROR aggregation in `test-review-code-flow.py` and `test-review-plan-flow.py`

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_reviewer_single.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add two new test functions in each file (four total):
  1. In `test-review-code-flow.py`:
     - `test_review_code_all_error_returns_top_level_error` — fixture builds a worktree + wiki tree, monkeypatches `_reviewer_single.run` to raise `LLMError("simulated rate limit")` on every call. Invoke `_review_code.run(...)` (or the entry the existing tests use). Assert returned `ReviewResult` has `verdict == "ERROR"` (top-level) AND `len(reviews) >= 1` AND `all(r["verdict"] == "ERROR" for r in reviews)`.
     - `test_review_code_mixed_returns_parsed_verdict` — monkeypatch `_reviewer_single.run` so the FIRST sub-review raises, but a hypothetical second one succeeds. If `_review_code.run` only does one sub-review (typical), this test is replaced with `test_review_code_single_error_returns_error` — single sub-review that raises, top-level becomes "ERROR" (same as the all-error case but with the explicit single-entry assertion).
  2. In `test-review-plan-flow.py`:
     - `test_review_plan_all_error_returns_top_level_error` — same shape as code-flow version: monkeypatch so all sub-reviews raise; assert top-level `verdict == "ERROR"`.
     - `test_review_plan_single_error_returns_error` — single sub-review that raises; top-level becomes "ERROR".
  3. Use the existing fixture patterns in each file (read `test_review_code_*` for the worktree-build pattern). If the fixtures depend on Batch 4's seeded config.yaml, they will already be wired up; do not re-seed.
- **Commit:** `test(review-flow): cover all-ERROR top-level verdict aggregation`

## Batch Tests

`verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-review-code-flow.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-review-plan-flow.py`. The four new tests above must pass; all pre-existing tests must continue to pass.
