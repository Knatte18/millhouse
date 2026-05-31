# Batch: validate-and-config

```yaml
task: mill-go / mill-merge / plan-validator follow-up bugs (round 2)
batch: validate-and-config
number: 3
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py test-config.py
depends-on: []
```

## Batch Scope

This batch fixes two independent bugs that both live in the Python layer: (1) `_plan_validate.py` needs a new `verify-full-suite` ERROR check to block plans that invoke `run-all.py` without a `-k` filter (#392), and (2) `_config.py` `load_config` needs to augment `template_cfg` with the worktree-local template so that keys added to the source template but absent from the stale cache template are not flagged as unknown (#401). Three new tests cover the validator check; two new tests cover the config augmentation.

## Cards

### Card 8: _plan_validate.py — add verify-full-suite ERROR check (#392)

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add a new function `_check_verify_full_suite(batch_files: list[Path]) -> list[dict]` immediately after `_check_verify_not_isolated` (which ends around line 841). The function must:
  1. Iterate `batch_files`.
  2. For each file, parse the frontmatter yaml block using the same pattern as `_check_verify_not_isolated` (find the first ` ```yaml ` / ` ``` ` fenced block, `yaml.safe_load` it).
  3. Extract `verify`; skip if None, not a string, or empty.
  4. If `"run-all.py"` is in the `verify` string AND `"-k "` is NOT in the `verify` string, append:
     ```python
     {
         "check": "verify-full-suite",
         "batch": batch_path.stem,
         "card": None,
         "path": verify,
         "message": "verify command invokes run-all.py without a filter (-k pattern); use '-k <pattern>' or '--only <files>' to scope the run",
     }
     ```
  5. Return the errors list.

  Then, in `validate_plan()`, add `errors.extend(_check_verify_full_suite(batch_files))` immediately after the `errors.extend(_check_verify_not_isolated(batch_files))` call (currently line 1004).

  The check name `"verify-full-suite"` must be used exactly (the mill-plan SKILL.md's fix table will reference it by this name).
- **Commit:** `fix(_plan_validate): add verify-full-suite ERROR check for unbounded run-all.py (#392)`

### Card 9: _config.py — augment template_cfg with worktree-local template (#401)

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:**
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `load_config`, immediately after the line `template_cfg = copy.deepcopy(cfg)` (currently line 172), insert:

  ```python
  # Augment template_cfg with the worktree-local template when it exists and
  # differs from the resolved cache template (handles cache-lag in self-modifying repos).
  _worktree_template = worktree_root / "plugins" / "mill" / "templates" / "mill-config.yaml"
  if _worktree_template.exists() and _worktree_template.resolve() != template_path.resolve():
      _wt_cfg = yaml.safe_load(_worktree_template.read_text(encoding="utf-8")) or {}
      template_cfg = deep_merge(template_cfg, _wt_cfg)
  ```

  The variable names `_worktree_template` and `_wt_cfg` use the leading underscore to signal local-only scope and avoid shadowing. No other changes to `load_config` or to any other function.
- **Commit:** `fix(_config): augment template_cfg with worktree-local template to silence stale-cache unknown-key warnings (#401)`

### Card 10: test-plan-validate.py — three new tests for verify-full-suite (#392)

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Read the existing `test-plan-validate.py` to understand its fixture pattern (it likely creates temporary plan dirs with batch files). Add three new test cases to `main()`:

  **Test A — run-all.py without filter is ERROR:** Create a batch file whose frontmatter contains `verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`. Call `_check_verify_full_suite([batch_path])` (or call `validate_plan(...)` and check the errors list). Assert one error with `check == "verify-full-suite"`.

  **Test B — run-all.py with -k filter is OK:** Create a batch file with `verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py -k test_foo`. Assert zero `verify-full-suite` errors.

  **Test C — run-all.py with --only is OK:** Create a batch file with `verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-foo.py`. Assert zero `verify-full-suite` errors. (Note: `--only` does not contain `-k ` but is a valid scoped invocation. The check must NOT flag `--only`-scoped commands. Implement this by checking that the verify string contains either `-k ` OR `--only `; flag only when neither is present.)

  Increment `errors` on assertion failure.

  **Important:** Update the `_check_verify_full_suite` in card 8 if needed: the check should skip the error when the verify command contains `"--only "` (with trailing space), since `--only` is equivalent to `-k` for test scoping. The final condition: flag if `"run-all.py"` in verify AND `"-k "` not in verify AND `"--only "` not in verify.
- **Commit:** `test(_plan_validate): cover verify-full-suite check for unbounded run-all.py (#392)`

### Card 11: test-config.py — two new tests for template_cfg augmentation (#401)

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/templates/mill-config.yaml`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Read the existing `test-config.py` to understand its fixture approach. Add two new test cases to `main()`:

  **Test A — worktree template augments template_cfg:** Set up two temp dirs: one acting as the "cache" (write a minimal `mill-config.yaml` template WITHOUT `pipeline.max_cards_per_batch`), one as the worktree (write `plugins/mill/templates/mill-config.yaml` WITH `pipeline.max_cards_per_batch: 10`). Also create a hub `mill-config.yaml` that contains `pipeline.max_cards_per_batch: 10`. Patch `resolve_plugin_template_path` to return the cache template path. Call `load_config(hub_root, worktree_root)` and capture stderr. Assert that no `"[config] unknown key"` lines appear on stderr.

  **Test B — same template path skips augmentation:** Set up a single temp dir where the worktree template path resolves to the SAME path as the cache template. Assert that `deep_merge` is not called a second time (use a spy or verify the result is identical to a single-load). A simpler alternative: assert that the result is identical to calling with a worktree template that has no extra keys (no double-merge artifact).

  Use `unittest.mock.patch` to mock `resolve_plugin_template_path` when needed. Redirect stderr to capture the `[config] unknown key` output.

  Increment `errors` on assertion failure.
- **Commit:** `test(_config): cover worktree-local template augmentation of template_cfg (#401)`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py test-config.py`

Covers cards 8–11 directly. The two changed Python modules (`_plan_validate.py`, `_config.py`) each have dedicated test files; no other tests in the suite import from these modules in a way that would regress from this batch's additive changes.
