# Batch: config

```yaml
task: Remove batch review (plan-review.batch / code-review.batch)
batch: config
number: 5
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-config.py test-reviewers.py test-large-prompt-switch.py
depends-on: [4]
```

## Batch Scope

Removes the per-batch review config surface now that no code reads it: the `batch:` blocks under `roles.plan-review` and `roles.code-review`, `pipeline.rename_detect_pct`, `roles.code-review.diff_scope_threshold`, and the two `MILL_*_BATCH_REVIEWER` env overrides.
Stale copies of these keys in existing hubs or `config.local.yaml` files keep loading and print a removal hint through `_config.RENAMED_KEY_HINTS`.
The hub `mill-config.yaml` and the plugin template change together, per CLAUDE.md's sync rule.

## Cards

### Card 15: Remove per-batch review keys from the config surface

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/templates/mill-config.yaml`
  - `mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  **Bootstrap safety (why editing the hub config mid-flight is safe).**
  The mill-go run executing this plan loads config via `_config.load_config`, which deep-merges the plugin-cache template before the hub file.
  The cached template predates this task and still carries both `batch:` blocks (`rounds: 0`, `reviewer: null`), `pipeline.rename_detect_pct` and `roles.code-review.diff_scope_threshold`.
  Removing them from this worktree's hub file therefore leaves the running orchestrator's merged config unchanged, and its cached `mill-go-base` skill keeps taking the "per-batch reviewer is null" shortcut for batches 6 and 7.

  In `plugins/mill/scripts/_config.py`:
  - Delete the `MILL_PLAN_BATCH_REVIEWER` and `MILL_CODE_BATCH_REVIEWER` entries from `ENV_REGISTRY`.
  - Add four entries to `RENAMED_KEY_HINTS`, keyed by the dotted block/leaf path `walk_unknown_keys` reports (it reports a whole unknown subtree as one path):
    - `"roles.plan-review.batch"`: `"per-batch plan review was removed; only roles.plan-review.holistic is read -- this block has no effect"`
    - `"roles.code-review.batch"`: `"per-batch code review was removed; only roles.code-review.holistic is read -- this block has no effect"`
    - `"pipeline.rename_detect_pct"`: `"the per-batch rename check was removed with per-batch code review -- this key has no effect"`
    - `"roles.code-review.diff_scope_threshold"`: `"diff-scoped code review was removed with per-batch code review -- this key has no effect"`

  In `plugins/mill/templates/mill-config.yaml`:
  - Delete the `MILL_PLAN_BATCH_REVIEWER` and `MILL_CODE_BATCH_REVIEWER` lines from the header comment's env-override list.
  - Delete the `batch:` block under `roles.plan-review` and the `batch:` block under `roles.code-review`, each with all its child keys.
  - Delete `pipeline.rename_detect_pct` (with its trailing comment) and `roles.code-review.diff_scope_threshold`.
  - In the `roles.fixer` comment, change `roles.code-review.<scope>.reviewer` to `roles.code-review.holistic.reviewer`.

  In the hub `mill-config.yaml`, make the same deletions: both `batch:` blocks, `pipeline.rename_detect_pct` and `roles.code-review.diff_scope_threshold`.
  Leave every other key untouched.
- **Commit:** `refactor(config): remove per-batch review keys and env overrides`

### Card 16: Update config and reviewer tests

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
  - `plugins/mill/unit_tests/_test_cfg.py`
  - `plugins/mill/unit_tests/test-reviewers.py`
  - `plugins/mill/scripts/_reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/unit_tests/test-config.py`:
  - Delete `test_env_override_plan_batch_reviewer` and `test_env_override_code_batch_reviewer` and their entries in `main()`'s test list.
  - Replace `test_load_config_rename_detect_pct_key_present` (and its `main()` entry) with `test_load_config_stale_batch_review_keys_warn`: a hub `mill-config.yaml` carrying a `roles.plan-review.batch` block, a `roles.code-review.batch` block, `pipeline.rename_detect_pct: 30` and `roles.code-review.diff_scope_threshold: 0.25`, loaded against the real template, loads without raising, and stderr contains `unknown key: roles.plan-review.batch`, `unknown key: roles.code-review.batch`, `unknown key: pipeline.rename_detect_pct` and `unknown key: roles.code-review.diff_scope_threshold`, each followed by its `RENAMED_KEY_HINTS` hint text (assert the hint via `_config.RENAMED_KEY_HINTS[path]`, not a copied string).
  - Add `test_template_has_no_batch_review_keys`: parse the real template and assert `"batch" not in roles["plan-review"]`, `"batch" not in roles["code-review"]`, `"rename_detect_pct" not in pipeline`, `"diff_scope_threshold" not in roles["code-review"]`.
  - Add `test_env_registry_has_no_batch_reviewer_entries`: `MILL_PLAN_BATCH_REVIEWER` and `MILL_CODE_BATCH_REVIEWER` are not keys of `_config.ENV_REGISTRY`.
  - In `test_load_config_auto_approve_on_cap_keys_present`, drop the `roles.code-review.batch` assertions and the docstring mention; the key is now checked for three scopes.
  - Leave the synthetic fixture templates in other tests alone: their `batch:` blocks are test inputs to `walk_unknown_keys`, not the real template.

  In `plugins/mill/unit_tests/_test_cfg.py`, delete the `batch` entries under `plan-review` and `code-review` and the `diff_scope_threshold` entry in `make_minimal_cfg`'s baseline, and update its module docstring if it mentions the batch scope.

  In `plugins/mill/unit_tests/test-reviewers.py`:
  - The `resolve_role` tests that use `"plan-review", "batch"`: rewrite them against `"plan-review", "holistic"` (null reviewer, rounds 0, explicit reviewer, unknown reviewer), so `resolve_role`'s own behaviour keeps coverage.
  - The `fixer_weaker_than_reviewer_warning` tests: pass `scope="holistic"` and expect `roles.code-review.holistic.reviewer=` in the warning text.

  In `plugins/mill/scripts/_reviewers.py`, change the `fixer_weaker_than_reviewer_warning` docstring's scope example from `(e.g. "batch")` to `(e.g. "holistic")`.
- **Commit:** `test(config): cover stale batch-review keys and drop batch-scope cases`

## Batch Tests

`verify:` runs `test-config.py` (template contents, `ENV_REGISTRY`, stale-key hints), `test-reviewers.py` (`resolve_role` and the fixer-tier warning), and `test-large-prompt-switch.py` (the other consumer of `_test_cfg.make_minimal_cfg`).
