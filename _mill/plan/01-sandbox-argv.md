# Batch: sandbox-argv

```yaml
task: '66 (A) -- Review sandbox follow-up: guard exceptions + bare-exit + sandbox argv'
batch: sandbox-argv
number: 1
cards: 2
verify: python plugins/mill/unit_tests/test-llm-claude-argv.py
depends-on: []
```

## Batch Scope

Fix the sandbox-defeating bug in `_llm_claude._build_argv` (#335). The current `if allowed_tools` test is falsy for the empty string passed by `run_bulk`, so `--allowedTools ""` is dropped from the argv and the subprocess inherits Claude CLI's full default tool surface (Skill, Agent, MCP, WebFetch, ...). Change the test to `if allowed_tools is not None` so the empty allow-list is emitted explicitly. Add a unit test that asserts the argv shape for three input cases: empty string, populated string, and None. The existing `--disallowedTools` deny-list stays in place as defence-in-depth.

This batch has no external interface that downstream batches consume -- it is a self-contained one-line code fix plus its regression guard.

## Cards

### Card 1: replace `if allowed_tools` with `if allowed_tools is not None` in `_build_argv`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_build_argv` (currently around line 84-116 of `_llm_claude.py`), change line 104 from `*(["--allowedTools", allowed_tools] if allowed_tools else [])` to `*(["--allowedTools", allowed_tools] if allowed_tools is not None else [])`. Do not touch any other line. Do not remove or modify the `--disallowedTools` branch on lines 106-107; the deny-list is intentional defence-in-depth.
- **Commit:** `fix(llm-claude): emit --allowedTools "" explicitly so empty allow-list is not dropped`

### Card 2: unit test asserting `_build_argv` argv shape for empty, populated, and None allow-lists

- **Context:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-llm-claude-argv.py`
- **Deletes:** none
- **Requirements:** Create a new `unittest.TestCase`-based test file that imports `_build_argv` from `_llm_claude` (use the same import style as other test files under `plugins/mill/unit_tests/`). Cover four cases:
  1. `_build_argv(model="m", effort=None, allowed_tools="")` MUST produce an argv list whose contiguous subsequence `["--allowedTools", ""]` is present, AND whose subsequence `["--disallowedTools", "Edit,Write,Bash,NotebookEdit"]` is also present.
  2. `_build_argv(model="m", effort=None, allowed_tools="Read,Grep,Glob")` MUST produce an argv with `["--allowedTools", "Read,Grep,Glob"]` AND `["--disallowedTools", "Edit,Write,Bash,NotebookEdit"]`.
  3. `_build_argv(model="m", effort=None, allowed_tools="Read,Edit,Write,Bash,Grep,Glob,Skill")` MUST produce an argv with `["--allowedTools", "Read,Edit,Write,Bash,Grep,Glob,Skill"]` AND MUST NOT contain `--disallowedTools` anywhere.
  4. (Optional defensive case) `_build_argv(model="m", effort=None, allowed_tools=None)` -- if the implementation chooses to accept `None`, the argv MUST NOT contain `--allowedTools`. If the implementation rejects `None` (current type hint is `str`), this case may be omitted; document the choice in the test docstring. Default: omit case 4 since the function signature today is `allowed_tools: str`. The first three cases are the regression guard for #335.

  The test file must be runnable both standalone (`python plugins/mill/unit_tests/test-llm-claude-argv.py`) and via `plugins/mill/unit_tests/run-all.py`. Follow the conventions of existing tests like `test-bg-launcher.py` for the `if __name__ == "__main__": unittest.main()` block.
- **Commit:** `test(llm-claude): add argv-shape regression for empty allowed_tools`

## Batch Tests

`verify:` runs the new `test-llm-claude-argv.py`. The test exercises every code path in `_build_argv`'s allow-list / deny-list branch logic. No other test file is affected by this batch's change.
