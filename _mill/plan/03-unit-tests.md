# Batch: unit-tests

```yaml
task: "(B) — Size-based reviewer switch (mechanism + configurable target)"
batch: unit-tests
number: 3
cards: 1
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [1]
```

## Batch Scope

This batch creates `test-large-prompt-switch.py` in `plugins/mill/unit_tests/`. The test file covers `maybe_switch_spec_for_large_prompt` and the `validate_role_refs` extension from batch 1. All tests are in-memory: no real LLM, no real git, no subprocess. The verify command runs the full unit-test suite so regressions in other modules are also caught.

This batch can run in parallel with batch 2 (both depend only on batch 1).

## Cards

### Card 7: Write `test-large-prompt-switch.py`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/unit_tests/_test_cfg.py`
  - `plugins/mill/unit_tests/_test_registry.py`
  - `plugins/mill/unit_tests/test-reviewers.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-large-prompt-switch.py`
- **Deletes:** none
- **Requirements:**
  Write the file exactly as specified below. The module follows the same pattern as `test-reviewers.py`: module-level `sys.path` setup, helper fixtures, one function per test with `print("PASS: ...")` at the end, a `main()` that collects and runs them, and `if __name__ == "__main__": sys.exit(main())`.

  **`sys.path` setup (same pattern as existing tests):**
  ```python
  HUB = Path(__file__).resolve().parent.parent.parent.parent
  sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))
  sys.path.insert(0, str(Path(__file__).resolve().parent))
  ```

  **Imports:**
  ```python
  import contextlib
  import io
  import sys
  from pathlib import Path
  # ... HUB and sys.path setup ...
  from _review_common import ReviewError, maybe_switch_spec_for_large_prompt
  from _reviewers import ReviewerError, validate_role_refs
  from _test_cfg import make_minimal_cfg
  from _test_registry import make_minimal_registry
  ```

  **Fixture helpers (module-level functions, not test functions):**

  `_make_cfg_with_large_prompt(role, scope, threshold_ktok, reviewer)` — returns `make_minimal_cfg()` with `cfg["roles"][role][scope]["large_prompt"] = {"threshold_ktok": threshold_ktok, "reviewer": reviewer}`. Defaults: `role="code-review"`, `scope="holistic"`, `threshold_ktok=1`, `reviewer="override-reviewer"`.

  `_make_registry_with_cluster()` — returns `make_minimal_registry()` extended with `worker_single` (single type, provider=claude, model=claude-sonnet-4-6) and `my_cluster` (cluster type, workers.use=worker_single, workers.count=3, handler.use=worker_single).

  `_override_spec()` — returns `{"type": "single", "provider": "claude", "model": "claude-opus-4-7", "effort": "max", "tooluse": False}`.

  **Tests:**

  `test_below_threshold_no_switch()`: Build registry with `override-reviewer` using `_override_spec()`. Use `_make_cfg_with_large_prompt(threshold_ktok=1)`. Prompt = `"x" * 3999` (gives `3999 // 4000 = 0 < 1` → no switch). Capture stderr with `contextlib.redirect_stderr(io.StringIO())`. Assert returned spec is the same object as original (identity check), name unchanged, stderr is empty string.

  `test_above_threshold_switches()`: Same registry and cfg. Prompt = `"x" * 4000` (gives `4000 // 4000 = 1 >= 1` → switch). Assert returned name is `"override-reviewer"`, returned spec model is `"claude-opus-4-7"`, stderr contains `"large-prompt switch"`, `"sonnetmax"`, and `"override-reviewer"`.

  `test_no_large_prompt_config_noop()`: Use plain `make_minimal_cfg()` (no `large_prompt` key). Prompt = `"x" * 100_000`. Assert returned spec is same object as original (identity), name unchanged. No stderr capture needed.

  `test_null_reviewer_noop()`: Use `_make_cfg_with_large_prompt(threshold_ktok=1, reviewer=None)`. Prompt = `"x" * 4000`. Assert no switch (spec identity, name unchanged).

  `test_tooluse_coercion_original_true_override_false()`: Build `original_spec` with `tooluse=True`. Override spec has `tooluse=False` (default from `_override_spec()`). Prompt = `"x" * 4000`, `threshold_ktok=1`. Assert: returned spec has `tooluse=True`, returned name is `"override-reviewer"`, stderr contains `"tooluse differs"`.

  `test_tooluse_matching_no_notice()`: Both `original_spec["tooluse"] = False` and override `tooluse=False`. Prompt = `"x" * 4000`, `threshold_ktok=1`. Assert: returned spec has `tooluse=False`, stderr does NOT contain `"tooluse differs"`, stderr DOES contain `"large-prompt switch"`.

  `test_validate_role_refs_bad_large_prompt_reviewer()`: Use `make_minimal_cfg()`, add `cfg["roles"]["code-review"]["holistic"]["large_prompt"] = {"threshold_ktok": 100, "reviewer": "nonexistent-override"}`. Use `make_minimal_registry()`. Call `validate_role_refs(cfg, registry)` inside `try/except ReviewerError`. Assert exception message contains `"nonexistent-override"` and `"large_prompt"`.

  `test_validate_role_refs_cluster_large_prompt_reviewer()`: Use `make_minimal_cfg()`, add `cfg["roles"]["code-review"]["holistic"]["large_prompt"] = {"threshold_ktok": 100, "reviewer": "my_cluster"}`. Use `_make_registry_with_cluster()`. Assert `ReviewerError` raised with `"my_cluster"` in message and `"cluster"` (case-insensitive) in message.

  **`main()` function:** collect all eight test functions in a list, call each in a try/except, collect failures, print `PASS` or `FAIL` summary to stderr, return 0 or 1.

- **Commit:** `test(review): add unit tests for large-prompt reviewer switch`

## Batch Tests

The `verify:` command `python plugins/mill/unit_tests/run-all.py` runs the new test file alongside all existing tests. All 8 new tests must pass. Existing tests must not regress.
