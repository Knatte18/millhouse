# Batch: plugin-root-resolution

```yaml
task: "CLAUDE_PLUGIN_ROOT environment variable not exported to Bash tool"
batch: "plugin-root-resolution"
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py
depends-on: []
```

## Batch Scope

This batch closes the gap flagged by GitHub issues #811 and #813: `mill-setup` Phase 4.8 is the
one place in the mill codebase that still reads `os.environ['CLAUDE_PLUGIN_ROOT']` directly at
Python-subprocess runtime, unlike its siblings `_config.resolve_plugin_template_path` and
`_preflight.check_helpers`, which already tolerate the var's absence. A new pure helper,
`_config.resolve_plugin_root_from_syspath`, derives the plugin root by scanning `sys.path` for the
`PYTHONPATH`-inserted `scripts` entry instead — a value that never depends on `CLAUDE_PLUGIN_ROOT`
surviving as a real inherited env var, only on the `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"`
prefix that CC already substitutes textually into every Phase-4.8-sourced command line. Both the
Phase 4.8 write snippet and its Phase 8 verify snippet switch to this one helper so they can never
drift out of sync with each other again. This is a single, tightly-scoped batch — helper, its two
call sites, and its unit tests are one cohesive unit with no natural split boundary.

## Cards

### Card 1: Add `resolve_plugin_root_from_syspath` helper to `_config.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new function immediately after `resolve_plugin_template_path` (which ends at line 147,
  directly before `def resolve_repo_config_path`), matching the existing module's docstring style
  (`Args:`/`Returns:` sections, as used by `resolve_plugin_template_path`), plus a `Raises:`
  section:

  ```python
  def resolve_plugin_root_from_syspath(sys_path: list[str]) -> Path:
      """Resolve the plugin root by scanning sys.path for the PYTHONPATH-inserted scripts entry.

      CPython inserts every PYTHONPATH entry into sys.path at interpreter startup, including for
      -c invocations. Phase 4.8's command line always carries PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"
      as a prefix -- a value CC has already substituted textually before the Bash tool executes it --
      so this never depends on CLAUDE_PLUGIN_ROOT surviving as a real inherited env var.

      Args:
          sys_path: The full sys.path list. Passed explicitly (not read internally) so the function
              stays pure and testable without mocking sys.path or os.environ.

      Returns:
          The parent directory of the first sys.path entry named "scripts" (first-match-wins).

      Raises:
          SystemExit: If no sys.path entry is named "scripts".
      """
      for entry in sys_path:
          if Path(entry).name == "scripts":
              return Path(entry).resolve().parent
      raise SystemExit(
          "resolve_plugin_root_from_syspath: expected a .../scripts directory from PYTHONPATH "
          "somewhere in sys.path -- run this via the documented mill-setup invocation, not standalone"
      )
  ```

  Add `"resolve_plugin_root_from_syspath"` to the `__all__` list (lines 31-41), alongside the
  existing `"resolve_plugin_template_path"` and `"resolve_repo_config_path"` entries. Do not touch
  the module's top-of-file "Exports -------" docstring block (lines 1-19): that block already omits
  both sibling functions `resolve_plugin_template_path` and `resolve_repo_config_path`, so it is not
  an actively maintained convention to extend for this new helper.
- **Commit:** `feat(config): add resolve_plugin_root_from_syspath helper`

### Card 2: Cover `resolve_plugin_root_from_syspath` with unit tests

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add five new test functions immediately after `test_resolve_plugin_template_path_stale_root`
  (which ends at line 654, directly before `def test_load_config_bare_roles_key`), following that
  function's existing style exactly: plain top-level function, `assert` statements, a trailing
  `print("PASS ...")` line, no pytest fixtures/decorators. Cover the five TDD candidates from
  `_mill/discussion.md`'s Testing section. Build every fixture from a real `tempfile.TemporaryDirectory()`
  (already imported at the top of the file as `tempfile`, same pattern
  `test_resolve_plugin_template_path_stale_root` already uses) rather than hardcoded POSIX string
  literals -- `resolve_plugin_root_from_syspath` calls `.resolve()` internally, and on Windows
  resolving a drive-less POSIX-style literal (e.g. `'/home/x/...'`) fills in the current working
  directory's drive letter, so a hardcoded drive-less `Path(...)` on the assertion's other side would
  never compare equal. An OS-native tmp path resolves identically on both sides of the comparison on
  every platform. `os` is already imported at the top of the file for the `os.sep` use in test 4.

  ```python
  def test_resolve_plugin_root_from_syspath_basic() -> None:
      """resolve_plugin_root_from_syspath finds the scripts entry and returns its parent."""
      with tempfile.TemporaryDirectory() as tmp:
          tmp_path = Path(tmp).resolve()
          scripts_dir = tmp_path / "scripts"
          result = _config.resolve_plugin_root_from_syspath(["", str(scripts_dir)])
          assert result == tmp_path, f"Expected {tmp_path}, got {result}"
      print("PASS resolve_plugin_root_from_syspath -- basic sys.path scan")


  def test_resolve_plugin_root_from_syspath_no_scripts_entry_raises() -> None:
      """resolve_plugin_root_from_syspath with no scripts-named entry raises SystemExit."""
      try:
          _config.resolve_plugin_root_from_syspath(["", "/some/other/dir"])
          raise AssertionError("Expected SystemExit")
      except SystemExit as exc:
          assert "scripts" in str(exc), f"Expected 'scripts' in message, got {exc!r}"
      print("PASS resolve_plugin_root_from_syspath -- no scripts entry raises SystemExit")


  def test_resolve_plugin_root_from_syspath_not_at_index_one() -> None:
      """resolve_plugin_root_from_syspath finds a scripts entry prepended ahead of it."""
      with tempfile.TemporaryDirectory() as tmp:
          tmp_path = Path(tmp).resolve()
          scripts_dir = tmp_path / "scripts"
          result = _config.resolve_plugin_root_from_syspath(["", "/some/other/dir", str(scripts_dir)])
          assert result == tmp_path, f"Expected {tmp_path}, got {result}"
      print("PASS resolve_plugin_root_from_syspath -- scripts entry not at index 1 still found")


  def test_resolve_plugin_root_from_syspath_trailing_slash() -> None:
      """resolve_plugin_root_from_syspath normalizes a trailing slash on the scripts entry."""
      with tempfile.TemporaryDirectory() as tmp:
          tmp_path = Path(tmp).resolve()
          scripts_dir_str = str(tmp_path / "scripts") + os.sep
          result = _config.resolve_plugin_root_from_syspath(["", scripts_dir_str])
          assert result == tmp_path, f"Expected {tmp_path}, got {result}"
      print("PASS resolve_plugin_root_from_syspath -- trailing slash normalizes")


  def test_resolve_plugin_root_from_syspath_first_match_wins() -> None:
      """resolve_plugin_root_from_syspath returns the first scripts entry when two exist."""
      with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
          tmp1_path = Path(tmp1).resolve()
          tmp2_path = Path(tmp2).resolve()
          scripts1 = tmp1_path / "scripts"
          scripts2 = tmp2_path / "scripts"
          result = _config.resolve_plugin_root_from_syspath(["", str(scripts1), str(scripts2)])
          assert result == tmp1_path, f"Expected first match {tmp1_path}, got {result}"
      print("PASS resolve_plugin_root_from_syspath -- first match wins")
  ```

  Import the function under test the same way the rest of the file does (module-level `import _config` at the top of the file, already present -- call as `_config.resolve_plugin_root_from_syspath(...)`, no new import needed).

  Add all five new function names to the `tests = [...]` list inside `main()` (list starts at
  line 1554), placed in the same relative order as `test_resolve_plugin_template_path_stale_root`
  appears among its neighbors in that list.

  Add one bullet to the module docstring's `Covers:` list at the top of the file (lines 3-14):
  `- resolve_plugin_root_from_syspath: sys.path scan, no-match SystemExit, non-index-1 entry, trailing slash, first-match-wins`.
- **Commit:** `test(config): cover resolve_plugin_root_from_syspath`

### Card 3: Switch Phase 4.8 write and verify snippets to the new helper

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_claude_settings.py`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `### Phase 4.8 -- Write MILL_PYTHON to ~/.claude/settings.json`, replace the fenced ` ```bash `
  block (currently lines 408-430) in full. Current content:

  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "<VENV_PYTHON>" -c "
  import json, os
  from pathlib import Path
  import sys; sys.path.insert(0, os.environ['CLAUDE_PLUGIN_ROOT'] + '/scripts'); import _claude_settings

  venv = Path(os.environ['CLAUDE_PLUGIN_ROOT']) / '.venv'
  mill_python = str(venv / 'Scripts' / 'python.exe') if os.name == 'nt' else str(venv / 'bin' / 'python')
  settings_path = Path.home() / '.claude' / 'settings.json'

  data = json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else {}
  env_block = data.setdefault('env', {})
  if env_block.get('MILL_PYTHON') == mill_python:
      print(f'MILL_PYTHON already correct: {mill_python}')
  else:
      env_block['MILL_PYTHON'] = mill_python
      settings_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
      print(f'MILL_PYTHON set: {mill_python}')

  _claude_settings.merge_permission_allowlist(settings_path, _claude_settings.MILL_SUBAGENT_TOOLS)
  print(f'Permission allowlist merged: {_claude_settings.MILL_SUBAGENT_TOOLS}')
  "
  ```

  Replace with:

  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "<VENV_PYTHON>" -c "
  import json, os, sys
  from pathlib import Path
  import _claude_settings, _config

  plugin_root = _config.resolve_plugin_root_from_syspath(sys.path)
  venv = plugin_root / '.venv'
  mill_python = str(venv / 'Scripts' / 'python.exe') if os.name == 'nt' else str(venv / 'bin' / 'python')
  settings_path = Path.home() / '.claude' / 'settings.json'

  data = json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else {}
  env_block = data.setdefault('env', {})
  if env_block.get('MILL_PYTHON') == mill_python:
      print(f'MILL_PYTHON already correct: {mill_python}')
  else:
      env_block['MILL_PYTHON'] = mill_python
      settings_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
      print(f'MILL_PYTHON set: {mill_python}')

  _claude_settings.merge_permission_allowlist(settings_path, _claude_settings.MILL_SUBAGENT_TOOLS)
  print(f'Permission allowlist merged: {_claude_settings.MILL_SUBAGENT_TOOLS}')
  "
  ```

  This drops the manual `sys.path.insert(0, os.environ['CLAUDE_PLUGIN_ROOT'] + '/scripts')` line
  entirely -- CPython already populates `sys.path` from the `PYTHONPATH=` prefix on the same
  command line at interpreter startup, so `import _claude_settings` and `import _config` succeed
  with no manual insert (verified empirically during the discussion round).

  Separately, in `### Phase 8 -- Verify + report`, the `MILL_PYTHON` verify bullet (the line
  starting `- \`MILL_PYTHON\` in \`~/.claude/settings.json\` equals \`<VENV_PYTHON>\`...`, currently
  at lines 535-536) contains an inline one-line verify command on line 536. Within that single
  inline code span, apply the same substitution as above: change the import list from
  `import json, os; from pathlib import Path;` to
  `import json, os, sys; from pathlib import Path; import _config;`, and change
  `venv=Path(os.environ['CLAUDE_PLUGIN_ROOT'])/'.venv'` to
  `venv=_config.resolve_plugin_root_from_syspath(sys.path)/'.venv'`. Every other part of that
  inline command (the `expected=...`, `d=json.loads(...)`, `actual=...`, `assert ...`, `print(...)`
  segments, and the surrounding prose/backticks) is unchanged.
- **Commit:** `fix(mill-setup): resolve plugin root via sys.path scan in Phase 4.8 write + Phase 8 verify`

## Batch Tests

`verify:` runs the whole `plugins/mill/unit_tests/test-config.py` file directly, rather than a
narrower alternative, because this batch edits `_config.py` itself, a module every other
`test-config.py` case already exercises -- running the whole file catches any regression in
`resolve_plugin_template_path`'s existing coverage (same module, same env-var subject matter) in
the same pass, at no extra scoping cost since both live in one file already. (`test-config.py` has
no function-level selection mechanism of its own; `run-all.py --only <file>...`, used for other
batches' narrower verify commands, scopes by file, not by function, so it offers no narrower option
here than running this one file in full.)

After this batch merges, the operator should manually re-run `/mill-setup` once in this repo (it
is idempotent) to confirm end-to-end: (a) the Phase 4.8 output line reports the correct
`MILL_PYTHON` path, (b) the Phase 8 verify snippet passes with `OK: MILL_PYTHON=...`, (c) no
`KeyError` or other traceback. This step needs a live Claude Code session (to exercise CC's real
`${CLAUDE_PLUGIN_ROOT}` template substitution) and writes to the real
`~/.claude/settings.json`, so it is not run as part of this batch's automated `verify:` -- a unit
test cannot simulate CC's template substitution, only a live re-run can.
