# Batch: plan-review-holistic-rounds-gate

```yaml
task: 'Self-discovered mill pipeline bugs: silent archive-tag push failure, ignored --max-rounds override, dead test-registry helper, truncated commit_sha in implementer reports'
batch: plan-review-holistic-rounds-gate
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-plan-flow.py
depends-on: []
```

## Batch Scope

Fixes a one-line gate bug in `_review_plan.py::run()` so `--max-rounds N` can force a holistic plan review to dispatch even when `roles.plan-review.holistic.rounds: 0` is configured, mirroring the already-correct sibling check in `_review_discussion.py::run()`. One batch: a single-line source fix plus its one regression test. No batch-local decisions differ from `## Shared Decisions` in the overview — in particular, the `reviewer_override`-specific gate a few lines above and the sibling `batch`-rounds gate are explicitly untouched (see the overview's "Items explicitly out of scope" decision).

## Cards

### Card 4: Fix the holistic-disablement gate to read the effective round override

- **Context:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_review_plan.py::run()` (~line 730), change `elif holistic_name is None or cfg["roles"]["plan-review"]["holistic"]["rounds"] == 0:` to `elif holistic_name is None or holistic_max_rounds == 0:`, where `holistic_max_rounds` is the variable already computed at ~line 676 (`max_rounds if max_rounds is not None else cfg["roles"]["plan-review"]["holistic"]["rounds"]`). This mirrors `_review_discussion.py::run()`'s equivalent check (`max_rounds_cfg = max_rounds if max_rounds is not None else cfg[...]["rounds"]; if max_rounds_cfg == 0: ...`, ~lines 251-252 of that file). Do not touch the `reviewer_override`-specific gate at ~line 718 (`if reviewer_override is not None and cfg["roles"]["plan-review"]["holistic"]["rounds"] != 0:`), which intentionally reads the raw config value even when an override name is given (documented in the function's docstring, ~lines 657-666, as the "null-bypass Decision"). Do not touch the sibling `batch`-rounds gate at ~line 711 (`cfg["roles"]["plan-review"]["batch"]["rounds"] == 0`).
- **Commit:** `fix(review-plan): honor --max-rounds override in holistic-disablement gate`

### Card 5: Add a regression test for the --max-rounds override forcing holistic dispatch

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/unit_tests/test-review-plan-flow.py`'s `main()`, add a new test block ("Test 33") immediately before the final `if errors:` check (~line 2237), following the exact try/except/finally structure used by the existing "Test 11 — holistic_only=True: only holistic fires" block (~line 852): build a fixture via `_make_plan_fixture(tmpdir, batch_specs)` with at least one batch spec; set `cfg["roles"]["plan-review"]["holistic"]["rounds"] = 0` after fixture creation; seed one approve response (`stub.seed([(APPROVE_TEXT, "sid-max-rounds-override")])`); call `r = plan_run(cfg, SLUG, mill_dir, wiki_root, project_root, git_root=project_root, max_rounds=1, holistic_only=True)`; assert `len(stub.captured_prompts()) == 1` (before Card 4's fix, this would be `0` since the buggy gate skips holistic dispatch entirely and `holistic_only=True` already skips per-batch review — the assertion message should note this is the `--max-rounds`-forces-holistic-despite-`rounds:0` regression from issue #740); assert `len(r.reviews) == 1 and r.reviews[0]["scope"] == "holistic"`; assert `r.verdict == "APPROVE"`. Use `os.chdir(project_root)` / `os.chdir(orig_dir)` in `try`/`finally` exactly as the surrounding tests do.
- **Commit:** `test(review-plan): cover --max-rounds forcing holistic dispatch despite rounds:0`

## Batch Tests

`verify:` runs `test-review-plan-flow.py` in full — it already contains 30+ prior test blocks in the same `main()` function that Card 5's new block is appended to; scoping to just the new block is not possible with this file's structure (no `--only`-style sub-selection within a single file), and the file is the correct, already-scoped target (not the wider `run-all.py` suite) since `_review_plan.py` has no other dedicated test file.
