# Batch: review-fixture-seeding

```yaml
task: 44 (A) — Bug-fix batch 4
batch: review-fixture-seeding
number: 4
cards: 2
verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-review-code-flow.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-review-plan-flow.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-review-discussion-flow.py
depends-on: []
```

## Batch Scope

Three review-flow tests fail on main with `Missing config at <tempdir>/container/wiki/config.yaml` because their fixtures construct a `<tempdir>/container/...` tree but do not seed `wiki/config.yaml` with content `load_config` requires (#226). The fix is in the test fixtures, not the production `load_config` — the production invariant ("missing config = error") is correct. Identify the failing tests, locate where each constructs the `<tempdir>/container/wiki/` tree, and add or extend the config-seeding step so `load_config` succeeds.

This batch must land BEFORE Batch 5 (`review-code-error-aggregation`), because Batch 5 adds new test cases to `test-review-code-flow.py` and its verify command re-runs that file — verify would fail on the pre-existing #226 breakage if Batch 4 has not shipped.

## Cards

### Card 7: Diagnose and fix `<tempdir>/container/wiki/config.yaml` seeding gap

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/templates/wiki-config.yaml`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Run `uv run --project plugins/mill python plugins/mill/unit_tests/test-review-code-flow.py 2>&1` (and the two siblings) and capture which test functions fail with the literal substring `Missing config at`. Most likely the failing tests use a container-form layout (`<tempdir>/container/wts/<slug>/` worktree + `<tempdir>/container/wiki/`) instead of the older flat `<tempdir>/wiki/` layout that the existing config seeders cover. The path-resolution rules in `_paths.py` decide which form `load_config` looks under.
  2. For each failing test, locate where the fixture constructs the container tree. Add a seed step BEFORE `load_config` is called: write a minimal `config.yaml` to `<container>/wiki/config.yaml` matching the structure the existing flat-form seeders use (the `paths:`, `spawn:`, plus a `roles:` block stub if the test exercises reviewer-role resolution). Reuse the existing inline-seed pattern (see `test-review-discussion-flow.py:44–48` and `test-review-code-flow.py:105–111` for examples of the existing flat-form seed strings).
  3. Minimum config keys to seed (copy from existing flat-form fixtures): `paths:` block with `discussion_file`, `plan_dir`, `reviews_dir`; `spawn:` block with `branch_prefix`; if the test exercises reviewer dispatch, a `roles:` block with `discussion-review.holistic`, `plan-review.batch`, `plan-review.holistic`, `code-review.batch`, `code-review.holistic` populated with `{rounds: 1, reviewer: test_stub}` (so the test_stub reviewer is selected).
  4. If `_test_helpers.py` already contains a helper like `seed_wiki_config(wiki_root)` or `build_test_config(...)`, use it. Otherwise add one — name it `seed_wiki_config(wiki_root: Path, *, include_roles: bool = False) -> None` — to `_test_helpers.py` and call it from each failing fixture. The helper writes `(wiki_root / "config.yaml").write_text(...)` with the minimal content listed in step 3; `include_roles=True` adds the `roles:` block. If you add the helper, also add a one-paragraph docstring describing its purpose.
  5. Do NOT modify `_review_common.load_config` or `_config.load_config` — the "missing config = error" invariant must remain.
  6. Do NOT add `xfail` or skip markers. The tests must pass.
- **Commit:** `test(review-flow): seed container/wiki/config.yaml in failing fixtures (#226)`

### Card 8: Optional `seed_wiki_config` helper added to `_test_helpers.py`

- **Context:**
  - `plugins/mill/templates/wiki-config.yaml`
- **Edits:**
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** If — and ONLY if — Card 7 added a `seed_wiki_config(wiki_root, *, include_roles=False)` helper to `_test_helpers.py`, this card is a no-op (the helper was added in Card 7's commit). Otherwise: extract the inline seed pattern from `test-review-discussion-flow.py:44–48` (and similar in the other two files) into a single shared helper named `seed_wiki_config(wiki_root: Path, *, include_roles: bool = False) -> None` in `_test_helpers.py`, then update the three test files to call it. The helper accepts the wiki-root directory (the parent of `config.yaml`) and writes the minimal config; `include_roles=True` adds the `roles:` block with stub `test_stub` reviewer entries. Keep the call-sites' encoding="utf-8" behavior. If a name collision exists (e.g. a different `seed_wiki_config` already exists), pick `seed_wiki_config_minimal` instead.
- **Commit:** `refactor(_test_helpers): extract seed_wiki_config helper`

## Batch Tests

`verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-review-code-flow.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-review-plan-flow.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-review-discussion-flow.py`. All three test files must pass. Pre-existing test functions in these files must continue to pass; only the previously-failing 3 tests should newly pass.
