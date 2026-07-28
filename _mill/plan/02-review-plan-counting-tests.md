# Batch: review-plan-counting-tests

```yaml
task: 'Plan review verdict correctness: unverified platform claims and missing nit_count in subprocess dispatch'
batch: review-plan-counting-tests
number: 2
cards: 7
verify: null
depends-on: [1]
```

## Batch Scope

Add test coverage proving Batch 1's `finalize_scope()` refactor actually works: every one of the 4 refactored write sites in `_review_plan.py`, the skip-approved carryforward site, and the `[MEDIUM]`-fold-in regression (#720) get a real, non-vacuous assertion backed by a fixture containing at least one genuine `[NIT]`/`[BLOCKING]`/off-vocabulary finding heading — never a reused zero-finding fixture with a trivially-passing `== 0` assertion appended (a fixture like that would pass identically on unfixed and fixed code and prove nothing). This batch does not add coverage for Batch 1's 6 schema-parity-only (`"nit_count": 0`) error-path additions (Cards 3/5) — those sites have no successful raw response to compute real counts from, so there is no non-vacuous finding-based assertion to write for them; the existing error-path tests already covering `blocking_count == 0` on those sites are left untouched. This batch depends on Batch 1 (`review-plan-counting-fix`) because every new assertion here exercises that batch's refactored code paths.

## Cards

_One `### Card N` per card, numbered globally across all batches._

### Card 7: Test 14 & Test 29 — add `nit_count` parity assertions with real `[NIT]` fixtures

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `main()`'s "Test 14 — aggregate blocking_count" block, append a new heading `### [NIT] issue four\n\n- b\n\n` to the `two_blockings` string literal (between its two existing `### [BLOCKING]` headings and the closing ````` ```yaml\nverdict: REQUEST_CHANGES\n``` ````` fence — anywhere in the body before the yaml fence is fine as long as the heading survives on its own line). Add `assert r.nit_count == 1, f"expected aggregate nit_count=1, got {r.nit_count}"` immediately after the existing `assert r.blocking_count == 3, ...` line, and update the `print("PASS test14: ...")` message to also mention `nit_count`. In "Test 29 — fail-loud unrecognized severity in synchronous per-batch dispatch", append a new heading `### [NIT] minor note\n\n- b\n\n` to the `major_only` string literal (same placement rule as above). Add `assert r.nit_count == 1, f"expected nit_count=1, got {r.nit_count}"` immediately after the existing `assert r.blocking_count == 1, ...` line, and update the `print("PASS test29: ...")` message to also mention `nit_count`. Do not change `one_blocking` or `APPROVE_TEXT` (module-level constant) — they stay zero-finding fixtures for the other two `stub.seed(...)` legs in Test 14.
- **Commit:** `test(review-plan): assert nit_count parity in Test 14 and Test 29`

### Card 8: Test 7 — assert `blocking_count`/`nit_count` on holistic NEED_CONTEXT retry-success

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In "Test 7 — NEED_CONTEXT resume fallback in holistic block", the `stub.seed([...])` call's third tuple (the holistic-retry response, currently `(APPROVE_TEXT, "sid-3")`) must be replaced with a new local text literal carrying a real finding, e.g. ````RETRY_APPROVE_WITH_NIT_TEXT = "# Review: test\n\n### [NIT] cleanup note\n\n- b\n\n```yaml\nverdict: APPROVE\n```\n"```` (define this as a local variable inside the Test 7 block, not a module-level constant — it is only used here), paired with `"sid-3"`. After the existing `rv_hol = next(rv for rv in r.reviews if rv["scope"] == "holistic")` and `assert rv_hol["verdict"] == "APPROVE", ...` lines, add `assert rv_hol["blocking_count"] == 0, f"expected holistic blocking_count=0, got {rv_hol['blocking_count']}"` and `assert rv_hol["nit_count"] == 1, f"expected holistic nit_count=1, got {rv_hol['nit_count']}"`. Do not change the retry-prompt assertions (`retry_text`, `retry_kwargs`) already present in this test.
- **Commit:** `test(review-plan): assert blocking_count/nit_count on holistic NEED_CONTEXT retry-success`

### Card 9: New test — holistic NEED_CONTEXT no-resolve branch

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new test block to `main()` (placed immediately after the Test 7 block, before the "Test 8 — skip-approved happy path" comment), following the same `with _test_helpers.safe_temp_dir() as tmpdir: ... try: ... except AssertionError ... except Exception ... finally: os.chdir(orig_dir)` structure every other numbered test in this file uses, incrementing `errors` on failure and printing `PASS test7b: ...` / `FAIL test7b: ...` (use the `test7b` label since it exercises the sibling branch to Test 7's NEED_CONTEXT-retry-success path and this file's tests are not renumbered when a new one is inserted between existing numbers — see Test 9's existing comment referencing "bug C fix #184" for a precedent of a test that stays put while later tests keep their original numbers). Use a single batch (`("alpha", "01-alpha.md", ["src/a.py"], [])`) via `_make_plan_fixture`. Define a local text literal ````NEED_CONTEXT_UNRESOLVABLE_WITH_NIT_TEXT = "# Review: test\n\n### [NIT] pending cleanup\n\n- b\n\n```yaml\nverdict: NEED_CONTEXT\n```\n\n## Missing context\n\n- `nonexistent/missing.py` — need this file\n"```` (the referenced path must not exist anywhere under `project_root` and must not be a `Creates:`/`Deletes:` token in any batch file, so `resolve_existing_paths` returns an empty list and the no-retry / no-resolve branch fires — do not reuse the module-level `NEED_CONTEXT_TEXT` constant, which intentionally references `src/a.py`, a path the fixture DOES create on disk). `stub.seed([(APPROVE_TEXT, "sid-1"), (NEED_CONTEXT_UNRESOLVABLE_WITH_NIT_TEXT, "sid-2")])`. Call `r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)`. Assert exactly 2 prompts were captured via `stub.captured_prompts()` (alpha + holistic first call; no retry call, since no missing_paths resolved). Assert `rv_hol = next(rv for rv in r.reviews if rv["scope"] == "holistic")` has `rv_hol["verdict"] == "NEED_CONTEXT"`, `rv_hol["blocking_count"] == 0`, and `rv_hol["nit_count"] == 1`.
- **Commit:** `test(review-plan): cover holistic NEED_CONTEXT no-resolve branch counters`

### Card 10: New test — holistic-normal site direct `blocking_count`/`nit_count` coverage

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new test block to `main()` (placed immediately after the "Test 14 — aggregate blocking_count" block, before the "Test 15 — max_rounds kwarg override" comment), following the same test-block structure as every other numbered test in this file, labeled `test14b` (sibling to Test 14, inserted without renumbering later tests — same precedent as Card 9's `test7b`). Use a single batch (`("alpha", "01-alpha.md", ["src/a.py"], [])`) via `_make_plan_fixture`. Define a local text literal ````holistic_blocking_and_nit = "# Review\n\n### [BLOCKING] missing edge case\n\n- b\n\n### [NIT] naming nit\n\n- b\n\n```yaml\nverdict: REQUEST_CHANGES\n```\n"````. `stub.seed([(APPROVE_TEXT, "sid-a"), (holistic_blocking_and_nit, "sid-hol")])`. Call `r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)`. Assert `rv_hol = next(rv for rv in r.reviews if rv["scope"] == "holistic")` has `rv_hol["blocking_count"] == 1` and `rv_hol["nit_count"] == 1` — asserting this review entry's OWN counts directly, not only the run-level aggregate (which Test 14 already covers for the per-batch legs; this test is what actually exercises the "holistic normal" refactor site's own `finalize_scope()` call, since Test 14's holistic leg stays `APPROVE_TEXT`).
- **Commit:** `test(review-plan): cover holistic-normal site's own blocking_count/nit_count`

### Card 11: Test 8 — extend skip-approved carryforward with real `[NIT]` and off-vocabulary findings

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In "Test 8 — skip-approved happy path", replace the two carried-forward `.write_text(APPROVE_TEXT, encoding="utf-8")` calls with two new local text literals: for the `01-a-r1` file, ````APPROVE_WITH_NIT_TEXT = "# Review: test\n\n### [NIT] cosmetic\n\n- b\n\n```yaml\nverdict: APPROVE\n```\n"````; for the `03-c-r1` file, ````APPROVE_WITH_UNRECOGNIZED_SEVERITY_TEXT = "# Review: test\n\n### [MAJOR] mislabeled issue\n\n- b\n\n```yaml\nverdict: APPROVE\n```\n"```` (an off-vocabulary `[MAJOR]` heading alongside a `verdict: APPROVE` yaml block — `_scan_approved_batches()` carries this batch forward because `parse_verdict` still reads `APPROVE`, exercising the round-3 finding that verdict is never cross-validated against the review's actual finding counts). Leave the `02-b-r1` file's `REQUEST_CHANGES_TEXT` and the `holistic-r1` file's `APPROVE_TEXT` unchanged. After the existing carryforward assertions (`rv_a["session_id"] is None`, `rv_a["verdict"] == "APPROVE"`, `rv_c["session_id"] is None`, etc.), add: `assert rv_a["blocking_count"] == 0` and `assert rv_a["nit_count"] == 1` (from the `[NIT]` heading); `assert rv_c["blocking_count"] == 1` and `assert rv_c["nit_count"] == 0` (the `[MAJOR]` heading folds into `blocking_count` via `count_unrecognized_severity_findings`). Also add `assert r.blocking_count == 1, f"expected aggregate blocking_count=1, got {r.blocking_count}"` and `assert r.nit_count == 1, f"expected aggregate nit_count=1, got {r.nit_count}"` (the fresh `02-b` and fresh `holistic` dispatches both return the existing zero-finding `APPROVE_TEXT`/`REQUEST_CHANGES_TEXT`, contributing 0 to both aggregates, so the only nonzero contributions come from the two carryforward entries this card adds).
- **Commit:** `test(review-plan): exercise carryforward blocking_count/nit_count with real findings`

### Card 12: New test — #720 holistic-path `[MEDIUM]`-only regression

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new test block to `main()` (placed immediately after "Test 29 — fail-loud unrecognized severity in synchronous per-batch dispatch", before the `if errors:` summary block at the end of `main()`), following the same test-block structure as every other numbered test in this file, labeled `test30` (the next free number after Test 29). Use a single batch (`("alpha", "01-alpha.md", ["src/a.py"], [])`) via `_make_plan_fixture`. Define a local text literal ````medium_only_holistic = "# Review\n\n### [MEDIUM] borderline concern\n\n- b\n\n```yaml\nverdict: REQUEST_CHANGES\n```\n"````. `stub.seed([(APPROVE_TEXT, "sid-a"), (medium_only_holistic, "sid-hol")])`. Call `r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root)`. Assert `r.blocking_count == 1, f"expected blocking_count=1, got {r.blocking_count}"` and `r.nit_count == 0, f"expected nit_count=0, got {r.nit_count}"` — proving the holistic dispatch path (not just the per-batch path Test 29 already covers) folds an off-vocabulary `[MEDIUM]` severity into `blocking_count` rather than dropping it (#720). Update the `errors` summary logic is unaffected — this new block must increment the existing `errors` variable on failure exactly like every other test block.
- **Commit:** `test(review-plan): cover #720 MEDIUM-fold-in on the holistic dispatch path`

### Card 13: `test-review-common.py` — extend isolated `finalize_scope()` `[MEDIUM]`-only case

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Immediately after the existing `finalize_scope` integration test block (the one asserting `result["blocking_count"] == 2` and `result["nit_count"] == 1` from a mixed `[BLOCKING]`+`[MAJOR]`+`[NIT]` fixture, inside the same `with _test_helpers.safe_temp_dir() as tmpdir:` block using the same `reviews` directory variable), add a new isolated case: ````raw_medium_only = "```yaml\nverdict: REQUEST_CHANGES\nreviewed_file: 01-setup.md\ndate: 2026-01-01\n```\n### [MEDIUM] borderline concern\n"````. Call `result = finalize_scope(reviews, "plan", 2, raw_medium_only, scope="01-setup")` (round `2`, distinct from the preceding call's round `1`, so `write_review_file` does not collide on filename). Assert `result["blocking_count"] == 1, f"expected blocking_count 1, got {result['blocking_count']}"` and `result["nit_count"] == 0, f"expected nit_count 0, got {result['nit_count']}"`. Print a `PASS: finalize_scope folds an isolated [MEDIUM]-only finding into blocking_count with zero recognized findings present` line matching this file's existing print-per-assertion-block convention.
- **Commit:** `test(review-common): cover isolated MEDIUM-only fold-in through finalize_scope`

## Batch Tests

`verify:` runs both `test-review-plan-flow.py` (Cards 7-12) and `test-review-common.py` (Card 13) via `run-all.py --only`. Every new/modified assertion in this batch is backed by a fixture containing at least one real `[NIT]`, `[BLOCKING]`, or off-vocabulary-severity finding heading — none reuses a zero-finding fixture to assert a trivially-true `== 0`, per the vacuous-test trap this task's own discussion-review loop caught twice (Test 14/29's original `nit_count` plan, and Test 8's carryforward `blocking_count` half).
