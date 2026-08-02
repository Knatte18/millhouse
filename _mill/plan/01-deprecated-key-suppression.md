# Batch: deprecated-key-suppression

```yaml
task: mill-config.yaml unknown-key warning for pipeline.autonomous_mode
batch: deprecated-key-suppression
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py
depends-on: []
```

## Batch Scope

This batch closes out a stale unknown-key warning: `pipeline.autonomous_mode`
was documented in the config template and referenced by `_autonomous.py`,
but that entire feature was fully deleted by commit `6cbd6dc6` without
removing the key from configs that had already written it, so
`_config.py`'s generic unknown-key validator now warns on every mill
invocation in any hub whose config still carries the key. The fix is a
one-line addition to the existing `deprecated_keys` suppression set in
`_config.py` (the same mechanism already used for the deleted
`llm.claude.psmux.via_psmux` key), plus one unit test asserting the
warning is suppressed. There is no external interface change and no
second batch — both cards land in a single implementer pass. No
batch-local decisions differ from `## Shared Decisions` in the overview.

## Cards

### Card 1: Add `pipeline.autonomous_mode` to `deprecated_keys`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `warn_unknown_keys` (around line 113), the
  `deprecated_keys` set (line 122) currently reads:
  ```
deprecated_keys = {"llm.claude.psmux.via_psmux"}
```
  Change it to add `"pipeline.autonomous_mode"` as a second entry in the
  same set literal:
  ```
  deprecated_keys = {"llm.claude.psmux.via_psmux", "pipeline.autonomous_mode"}
  ```
  No other changes to `_config.py`. `walk_unknown_keys` already produces
  dotted paths (e.g. `"pipeline.autonomous_mode"`) for nested keys, matching
  the existing `via_psmux` entry's convention — no change needed there.
- **Commit:** `fix(config): suppress unknown-key warning for removed pipeline.autonomous_mode`

### Card 2: Add unit test for the suppression

- **Context:**
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new test function
  `test_pipeline_autonomous_mode_does_not_trigger_unknown_key_warning()`
  immediately after `test_via_psmux_does_not_trigger_unknown_key_warning`
  (currently ends at line 1347 with its `print(...)` call). It does NOT
  call the shared `_setup_plugin_template` helper (that helper's synthetic
  template has no top-level `pipeline:` key, so `walk_unknown_keys` would
  flag the whole `"pipeline"` path as unknown at the top level rather than
  recursing to produce `"pipeline.autonomous_mode"` — the assertion would
  pass vacuously regardless of whether `deprecated_keys` contains the new
  entry). Instead it writes its own dedicated template inline, identical
  to `_setup_plugin_template`'s content plus a `pipeline:` section so the
  recursion actually reaches the nested key:
  ```
  def test_pipeline_autonomous_mode_does_not_trigger_unknown_key_warning() -> None:
      """pipeline.autonomous_mode does not trigger generic unknown-key warning."""
      with tempfile.TemporaryDirectory() as tmp:
          tmp_path = Path(tmp)
          _write_yaml(
              tmp_path / "templates" / "mill-config.yaml",
              "spawn:\n  branch_prefix: ''\n"
              "git:\n"
              "  parent-branch: null\n"
              "  require_pr_to_base: false\n"
              "  base_branch: main\n"
              "roles:\n"
              "  discussion-review:\n"
              "    holistic:\n"
              "      reviewer: sonnetmax\n"
              "  plan-review:\n"
              "    holistic:\n"
              "      reviewer: sonnetmax\n"
              "    batch:\n"
              "      reviewer: sonnetmedium\n"
              "  code-review:\n"
              "    holistic:\n"
              "      reviewer: sonnetmedium\n"
              "    batch:\n"
              "      reviewer: sonnetmedium\n"
              "  implementer:\n"
              "    model: sonnethigh\n"
              "pipeline:\n"
              "  auto_merge: true\n"
          )
          wt_root = tmp_path / "hub"
          _git_init(wt_root)
          _write_yaml(
              wt_root / "mill-config.yaml",
              "pipeline:\n  autonomous_mode: false\n"
          )

          with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
              with patch.object(
                  _config, "resolve_plugin_template_path",
                  return_value=tmp_path / "templates" / "mill-config.yaml"
              ):
                  with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
                      _config.load_config(wt_root, wt_root)
                      stderr_output = mock_stderr.getvalue()

          assert "unknown key: pipeline.autonomous_mode" not in stderr_output, (
              f"pipeline.autonomous_mode should not trigger unknown-key warning, stderr: {stderr_output!r}"
          )
      print("PASS pipeline.autonomous_mode does not trigger unknown-key warning")
  ```
  Register the new function in the module-level `tests = [...]` list
  (around line 1556) immediately after the
  `test_via_psmux_does_not_trigger_unknown_key_warning,` entry, adding:
  `test_pipeline_autonomous_mode_does_not_trigger_unknown_key_warning,`
  All helpers used (`tempfile`, `Path`, `_git_init`, `_write_yaml`,
  `_paths`, `_config`, `io`, `patch`) are already imported/defined in
  `test-config.py` for existing tests — no new imports needed, and
  `_setup_plugin_template` is not called by this test.
- **Commit:** `test(config): assert pipeline.autonomous_mode suppresses unknown-key warning`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-config.py` directly (its
`if __name__ == "__main__":` block executes every registered test and
exits non-zero on any failure) — scoped to this one file since the
batch touches only `_config.py` and `test-config.py`, and
`test-config.py` is the module that exercises `_config.py`.
