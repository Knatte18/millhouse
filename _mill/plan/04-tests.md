# Batch: Tests

```yaml
task: '65 (A) -- Config-load og mill-go helse-sjekk etter config-migrasjon'
batch: 'Tests'
number: 4
cards: 4
verify: "python plugins/mill/unit_tests/test-config.py && python plugins/mill/unit_tests/test-review-common.py"
depends-on: [1, 2, 3]
```

## Batch Scope

This batch adds regression tests for every fix delivered in batches 1-3. All new tests are appended to existing test files -- no new test files are created. The tests are unit-level: in-memory fixtures, no real git, no real LLM, no network. The pre-existing 1 failing test in test-review-common.py ("missing config -> ReviewError" -- see discussion.md Pre-existing failures section) is out of scope; it must neither be fixed nor newly broken here.

## Cards

### Card 9: New tests in test-config.py for batch 1 fixes

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/unit_tests/_test_cfg.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Define five new named test functions following the existing `test_deep_merge_…` / `test_load_config_…` naming style (uses `tempfile.TemporaryDirectory`, `print("PASS ...")` on success, `patch.object(_config, "resolve_plugin_template_path", ...)` where needed). Place the function definitions BEFORE the `if __name__ == "__main__":` block. Append the five new names to the `tests = [...]` list inside `main()`. Add `import io` at the top of the file if not already present.

  **Test A -- deep_merge None overlay preserves base dict:**
  ```python
  result = _config.deep_merge({"roles": {"k": "v"}}, {"roles": None})
  assert result == {"roles": {"k": "v"}}, f"None overlay must not clobber base dict; got {result!r}"
  print("PASS deep_merge -- None overlay on dict base is skipped, base dict preserved")
  ```

  **Test B -- deep_merge None overlay allowed for scalar base:**
  ```python
  result = _config.deep_merge({"reviewer": "foo"}, {"reviewer": None})
  assert result == {"reviewer": None}, f"None overlay should override scalar; got {result!r}"
  print("PASS deep_merge -- None overlay on scalar base allowed (reviewer: null semantics)")
  ```

  **Test C -- resolve_plugin_template_path stale CLAUDE_PLUGIN_ROOT falls back with warning:**
  Use `tempfile.TemporaryDirectory` for a nonexistent root. Set `os.environ["CLAUDE_PLUGIN_ROOT"]` to the nonexistent path inside the test, call `_config.resolve_plugin_template_path("mill-config.yaml")`, capture stderr with `io.StringIO` + `unittest.mock.patch("sys.stderr", new=<buf>)`, then restore `os.environ` and assert: (1) the returned path equals `Path(_config.__file__).resolve().parent.parent / "templates" / "mill-config.yaml"` (source-tree path); (2) stderr contains the word "CLAUDE_PLUGIN_ROOT" or the nonexistent path string (confirming a warning was emitted). Clean up env with `os.environ.pop("CLAUDE_PLUGIN_ROOT", None)` in a try/finally.
  ```python
  print("PASS resolve_plugin_template_path -- stale CLAUDE_PLUGIN_ROOT falls back to source tree with warning")
  ```

  **Test D -- load_config bare roles: key does not crash:**
  Use `_setup_plugin_template(tmp_path)` for the template (it has a full `roles:` section). Write a `mill-config.yaml` with `roles:\n` (bare key). Call `load_config(wt_root, wt_root)` with `resolve_wiki_path` patched to `side_effect=SystemExit` and `resolve_plugin_template_path` patched to the test template. Assert no exception is raised and `cfg.get("roles")` is a dict (not None).
  ```python
  print("PASS load_config -- bare roles: key does not crash; template roles: dict preserved")
  ```

  **Test E -- load_config hub_relative_path does not produce unknown-key warning:**
  Write a `.millhouse/config.local.yaml` with `hub_relative_path: subdir`. Use `_setup_plugin_template(tmp_path)` and patch `resolve_plugin_template_path`. Capture stderr. Call `load_config`. Assert that `"hub_relative_path"` does NOT appear in the captured stderr.
  ```python
  print("PASS load_config -- hub_relative_path in config.local.yaml does not emit unknown-key warning")
  ```
- **Commit:** `test(_config): add tests for None-overlay, stale-root fallback, hub_relative_path suppression`

### Card 10: New tests in test-review-common.py for batch 2 fixes

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Append the following tests to the load_config test block in `test-review-common.py` (after line 567, after the existing "load_config stale review: overlay emits stderr warning" test). Follow the existing inline-within-main() style.

  **Test A -- _review_common.load_config bare roles: key does not crash:**
  Write a `mill-config.yaml` with `roles:\n` (bare key, value is None). Create a `.millhouse/` dir with no `config.local.yaml`. Use `patch("_review_common.resolve_plugin_template_path", ...)` (or equivalently `patch.object(sys.modules["_review_common"], "resolve_plugin_template_path", ...)`) to point to a test template that HAS a full `roles:` dict (write one inline). Call `load_config(tmpdir_path, mill)`. Assert no exception; assert `cfg.get("roles")` is a dict. Note: `_review_common` imports `resolve_plugin_template_path` via `from _config import ...`, creating a local binding -- the patch MUST target the `_review_common` module's name, not `_config` directly.
  ```python
  print("PASS: load_config bare roles: does not crash; template roles: preserved")
  ```

  **Test B -- _review_common.load_config hub_relative_path does not produce unknown-key warning:**
  Write a `mill-config.yaml` with valid content. Write a `.millhouse/config.local.yaml` with `hub_relative_path: subdir`. Patch `resolve_plugin_template_path` to return the same valid mill-config.yaml path (no separate template needed since roles: is present). Capture stderr. Call `load_config`. Assert `"hub_relative_path"` does NOT appear in stderr.
  ```python
  print("PASS: load_config hub_relative_path in config.local.yaml does not emit unknown-key warning")
  ```
- **Commit:** `test(_review_common): add tests for None-overlay and hub_relative_path suppression`

### Card 11: Verify existing test-config.py tests still pass after batch 1

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Requirements:** This is a verification-only card. Run `python plugins/mill/unit_tests/test-config.py` from the worktree root. All 30 existing tests (plus the 5 new tests from Card 9) must produce PASS lines and exit 0. If any existing test fails, investigate the batch 1 changes and fix the regression. Do NOT proceed to Card 12 until this succeeds. If the test `test_unknown_key_warning_emitted` (which checks that `pipeline.autonomous_mode` IS flagged as unknown) fails because the real template now includes `autonomous_mode`: this is expected -- the test uses `_setup_plugin_template` which writes a MINIMAL test template without `autonomous_mode`, so the warning still fires in the test context and the test should still pass.
- **Commit:** none (verify-only card; no files changed)

### Card 12: Verify existing test-review-common.py tests still pass after batch 2

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Requirements:** This is a verification-only card. Run `python plugins/mill/unit_tests/test-review-common.py` from the worktree root. The pre-existing failure ("load_config missing config -> ReviewError") must remain exactly 1 failure (no new failures introduced). If a new failure appears, investigate the batch 2 changes. Do NOT proceed to commit until the count of failures is still 1.
- **Commit:** none (verify-only card; no files changed)

## Batch Tests

`verify: "python plugins/mill/unit_tests/test-config.py && python plugins/mill/unit_tests/test-review-common.py"` -- both test runners must pass (test-config.py: 0 failures; test-review-common.py: exactly 1 pre-existing failure, no new failures). If either exits non-zero due to a new failure, the batch is not done.
