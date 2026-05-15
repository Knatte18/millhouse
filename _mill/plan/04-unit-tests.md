# Batch: unit-tests

```yaml
task: Make implementer model configurable via config.yaml
batch: unit-tests
number: 4
cards: 5
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [3]
```

## Batch Scope

Updates all affected unit test files to reflect the production changes from batches 1–3: replaces `_implementer_sonnet` mock targets with `_implementer_claude`, adds `_reviewers.load` + `_reviewers.resolve` mocks to the implement test suites, adds new test cases for model-from-config behavior and backward-compat fallback, and updates direct `reviewers.yaml` fixture writes to `agents.yaml`. After this batch, `python plugins/mill/unit_tests/run-all.py` passes with zero failures.

---

### Card 10: Update `test-millpy-implement.py`

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_implementer_claude.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Six changes to `test-millpy-implement.py`:

  1. **Replace all `_implementer_sonnet` mock targets**: search for every occurrence of `millpy_implement._implementer_sonnet` and replace with `millpy_implement._implementer_claude`. There are multiple test methods (tests 1–5b, 7) that use `unittest.mock.patch.object(millpy_implement._implementer_sonnet, "run", ...)` — replace each one.

  2. **Add `_reviewers` mocks to `setUp`**: after the existing `self.mock_capture_snapshot` setup, add:
     ```python
     self.mock_reviewers_load = _p(
         millpy_implement._reviewers, "load",
         return_value={
             "sonnethigh": {
                 "type": "single",
                 "provider": "claude",
                 "model": "claude-sonnet-4-6",
                 "effort": "high",
             }
         },
     )
     self.mock_reviewers_resolve = _p(
         millpy_implement._reviewers, "resolve",
         return_value={
             "type": "single",
             "provider": "claude",
             "model": "claude-sonnet-4-6",
             "effort": "high",
         },
     )
     ```

  3. **Update `mock_load_config` return value**: add `"model": "sonnethigh"` to the implementer section:
     ```python
     return_value={
         "paths": {"status_md": "_mill/status.md"},
         "roles": {"implementer": {"self_fix_rounds": 2, "model": "sonnethigh"}},
         "llm": {"implementer_timeout": 1800},
     },
     ```

  4. **Update test_6_batch_prompt injection test (test_6_batch_files_and_session_ids_injected if present)**: The `mock_run` function inside the test uses `def mock_run(prompt_text, *, session_id, resume, cwd, timeout)`. After the production change, `_implementer_claude.run` is called with `model=` and `effort=` as additional kwargs. Update the mock function signature to:
     ```python
     def mock_run(prompt_text, *, model, effort, session_id, resume, cwd, timeout):
     ```

  5. **Add test: model and effort passed from config** (new test, after existing tests):
     ```python
     def test_9_model_and_effort_from_config(self):
         """Initial dispatch: model and effort read from config and passed to implementer."""
         with unittest.mock.patch.object(
             millpy_implement._implementer_claude, "run",
             return_value=(
                 '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                 "fake-session",
             ),
         ) as mock_run:
             rc, out = self._run_main(["test-batch"])

         self.assertEqual(rc, 0)
         call_kwargs = mock_run.call_args.kwargs
         self.assertEqual(call_kwargs.get("model"), "claude-sonnet-4-6")
         self.assertEqual(call_kwargs.get("effort"), "high")
     ```

  6. **Add test: model falls back to `sonnethigh` when config key absent** (new test):
     ```python
     def test_10_model_default_fallback(self):
         """When roles.implementer.model is absent, defaults to 'sonnethigh'."""
         self.mock_load_config.return_value = {
             "paths": {"status_md": "_mill/status.md"},
             "roles": {"implementer": {"self_fix_rounds": 2}},
             "llm": {"implementer_timeout": 1800},
         }
         with unittest.mock.patch.object(
             millpy_implement._implementer_claude, "run",
             return_value=(
                 '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                 "fake-session",
             ),
         ):
             rc, out = self._run_main(["test-batch"])

         self.assertEqual(rc, 0)
         # _reviewers.resolve was called with 'sonnethigh' (the default)
         self.mock_reviewers_resolve.assert_called_with(
             self.mock_reviewers_load.return_value, "sonnethigh"
         )
     ```
- **Commit:** `test(test-millpy-implement): update mocks for _implementer_claude; add model-from-config tests`

---

### Card 11: Update `test-millpy-implement-holistic.py`

- **Context:**
  - `plugins/mill/scripts/millpy-implement-holistic.py`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_implementer_claude.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement-holistic.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Four changes to `test-millpy-implement-holistic.py`:

  1. **Replace all `_implementer_sonnet` mock targets**: change every `millpy_implement_holistic._implementer_sonnet` to `millpy_implement_holistic._implementer_claude`.

  2. **Add `_reviewers` mocks to `setUp`**: after existing setup, add the same `mock_reviewers_load` and `mock_reviewers_resolve` mocks as in card 10, targeting `millpy_implement_holistic._reviewers`.

  3. **Update `mock_load_config` return value**: add `"model": "sonnethigh"` to `roles.implementer`.

  4. **Update `test_6_batch_files_and_session_ids_injected` mock_run signature**: change `def mock_run(prompt_text, *, session_id, resume, cwd, timeout)` to `def mock_run(prompt_text, *, model, effort, session_id, resume, cwd, timeout)` so it accepts the new kwargs without raising `TypeError`.
- **Commit:** `test(test-millpy-implement-holistic): update mocks for _implementer_claude`

---

### Card 12: Update `test-millpy-merge-in-subagent.py`

- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_implementer_claude.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Three changes to `test-millpy-merge-in-subagent.py`:

  1. **Replace all `_implementer_sonnet` mock targets**: change every `millpy_merge_in_subagent._implementer_sonnet` to `millpy_merge_in_subagent._implementer_claude`.

  2. **Add `_reviewers` mocks to `setUp`**: add `mock_reviewers_load` and `mock_reviewers_resolve` mocks (same pattern as cards 10–11) targeting `millpy_merge_in_subagent._reviewers`. The `mock_load_config` return value already lacks `roles.implementer.model` — the default fallback to `sonnethigh` is exercised implicitly. Optionally update `mock_load_config` to include `"model": "sonnethigh"` under `roles.implementer` for explicitness.

  3. **Update any `mock_run` side_effect functions**: if any test in this file uses a custom `def mock_run(...)` side_effect, add `model` and `effort` kwargs to its signature to match the updated `_implementer_claude.run()` call signature.
- **Commit:** `test(test-millpy-merge-in-subagent): update mocks for _implementer_claude`

---

### Card 13: Update `test-reviewers.py`

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_test_registry.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Four changes to `test-reviewers.py`:

  1. **Update direct `reviewers.yaml` writes**: every test that writes directly to `wiki / "reviewers.yaml"` must write to `wiki / "agents.yaml"` instead. Search for all occurrences of `"reviewers.yaml"` in this file and replace each with `"agents.yaml"`.

  2. **Update the "missing registry" test**: the existing test named something like `test_load_raises_when_file_absent` currently expects `ReviewerError` when `reviewers.yaml` is absent. After the fallback logic, the error fires only when *both* files are absent. Verify the test creates an empty wiki dir (no YAML files) — if so, it still passes without change. If the test wrote `reviewers.yaml` and then renamed/removed it, update accordingly.

  3. **Add backward-compat fallback test** (new test in the `TestLoad` class or equivalent):
     ```python
     def test_load_falls_back_to_reviewers_yaml(self):
         """load() succeeds when only reviewers.yaml exists (backward compat)."""
         wiki = Path(tempfile.mkdtemp())
         self.addCleanup(shutil.rmtree, wiki, True)
         # write_to() now writes agents.yaml; rename it to reviewers.yaml to simulate old hub
         write_to(wiki)
         (wiki / "agents.yaml").rename(wiki / "reviewers.yaml")
         registry = _reviewers.load(wiki)
         self.assertIn("sonnetmax", registry)
     ```
     (Import `shutil` at the top of the file if not already imported.)

  4. **Add `validate_role_refs` implementer model test** (new test):
     ```python
     def test_validate_role_refs_catches_bad_implementer_model(self):
         """validate_role_refs raises ReviewerError for bad roles.implementer.model."""
         registry = make_minimal_registry()
         cfg = {"roles": {"implementer": {"self_fix_rounds": 2, "model": "nonexistent_entry"}}}
         with self.assertRaises(ReviewerError):
             validate_role_refs(cfg, registry)
     ```
- **Commit:** `test(test-reviewers): update paths to agents.yaml; add fallback + implementer-model tests`

---

### Card 14: Update `test-review-cli.py`

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_test_registry.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-cli.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `test-review-cli.py`, find the one direct write to `_wiki / "reviewers.yaml"` (around line 88) and change it to `_wiki / "agents.yaml"`. No other changes needed — `_reviewers.load()` will find `agents.yaml` directly; the backward-compat fallback is not exercised here.
- **Commit:** `test(test-review-cli): write agents.yaml fixture instead of reviewers.yaml`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` — full suite must pass with zero failures. Expected coverage: `_implementer_claude.run()` is called in all three CLI test suites; model and effort values from config are verified in `test-millpy-implement.py` (tests 9 and 10); backward-compat fallback in `test-reviewers.py`; `validate_role_refs` implementer check in `test-reviewers.py`.
