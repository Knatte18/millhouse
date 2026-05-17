# Batch: fix-allowed-tools-argv

```yaml
task: '63 (A) — Reviewer tool-sandbox: git snapshot guard + fix --allowedTools'
batch: fix-allowed-tools-argv
number: 3
cards: 2
verify: python plugins/mill/unit_tests/test-llm-claude.py
depends-on: []
```

## Batch Scope

Fix the silent-no-op sandbox argv in `_llm_claude._build_argv`: drop `--allowedTools` when the value is empty (Claude CLI treats `--allowedTools ""` as a default-allow no-op, not a "no tools" sentinel) and emit `--disallowedTools "Edit,Write,Bash,NotebookEdit"` whenever `allowed_tools` does NOT contain any of those four tokens. The derivation lives entirely inside `_build_argv` — `_invoke`, `run_bulk`, `run_tool_use`, `run_implementer` are unchanged in signature and call shape. Auto-classifies:

| caller          | allowed_tools value                          | emits --allowedTools? | emits --disallowedTools? |
| --------------- | -------------------------------------------- | --------------------- | ------------------------ |
| run_bulk        | ""                                           | no                    | yes                      |
| run_tool_use    | "Read,Grep,Glob"                             | yes                   | yes                      |
| run_implementer | "Read,Edit,Write,Bash,Grep,Glob,Skill"       | yes                   | no                       |

The unit test `test-llm-claude.py` is extended to assert the argv shape for each of the three callers, and the existing direct `_build_argv` assertion at line 152-154 (which asserts `argv == [..., "--allowedTools", ""]`) is REPLACED with the new shape — not augmented.

Independent of batches 1, 2, 4 — no shared files.

## Cards

### Card 6: Fix _build_argv argv construction in _llm_claude.py

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  1. In `_llm_claude.py:71` `def _build_argv(...)`, locate the current argv list literal:

     ```python
     argv = [
         *_claude_argv_prefix(),
         "-p",
         "--output-format", "stream-json",
         "--verbose",
         "--model", model,
         "--allowedTools", allowed_tools,
     ]
     ```

  2. Replace the `--allowedTools` entry and append `--disallowedTools` conditionally. The full replacement form:

     ```python
     _MUTATING_TOOLS = {"Edit", "Write", "Bash", "NotebookEdit"}

     def _has_mutating_tool(allowed_tools: str) -> bool:
         """Return True if allowed_tools (comma/whitespace-delimited) contains any mutating tool name."""
         tokens = {t.strip() for t in allowed_tools.replace(",", " ").split() if t.strip()}
         return bool(tokens & _MUTATING_TOOLS)
     ```

     Place `_MUTATING_TOOLS` and `_has_mutating_tool` as module-level definitions immediately above `def _build_argv(`. Then inside `_build_argv`:

     ```python
     argv = [
         *_claude_argv_prefix(),
         "-p",
         "--output-format", "stream-json",
         "--verbose",
         "--model", model,
         *(["--allowedTools", allowed_tools] if allowed_tools else []),
     ]
     if not _has_mutating_tool(allowed_tools):
         argv += ["--disallowedTools", "Edit,Write,Bash,NotebookEdit"]
     ```

  3. The remaining `_build_argv` body (effort, resume, session-id handling) is unchanged.

  4. No change to `_invoke`, `run_bulk`, `run_tool_use`, `run_implementer`, or their docstrings beyond the auto-derived argv. The docstring at the top of `_llm_claude.py` (module docstring around lines 1-26) currently does not enumerate `--disallowedTools`; update the module docstring to note that `--disallowedTools "Edit,Write,Bash,NotebookEdit"` is added automatically when `allowed_tools` does not include those tools. Keep the docstring concise — one sentence added.

  5. ASCII-only log strings rule applies. The existing `[_llm_claude]` print breadcrumbs are unchanged; no new prints needed.

- **Commit:** `fix(_llm_claude): correct --allowedTools sandbox argv and add --disallowedTools deny-list`

### Card 7: Update test-llm-claude.py argv assertions

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  1. **Replace** the existing assertion at `test-llm-claude.py:152-155`:

     ```python
     argv = _build_argv("claude-sonnet-4-5", None, "")
     assert argv == [*prefix, "-p", "--output-format", "stream-json", "--verbose",
                     "--model", "claude-sonnet-4-5", "--allowedTools", ""]
     print("PASS: _build_argv bulk without effort / without session")
     ```

     with:

     ```python
     argv = _build_argv("claude-sonnet-4-5", None, "")
     assert "--allowedTools" not in argv, f"empty allowed_tools must omit --allowedTools; got {argv}"
     assert argv[-2:] == ["--disallowedTools", "Edit,Write,Bash,NotebookEdit"], \
         f"empty allowed_tools must end with --disallowedTools deny-list; got {argv}"
     print("PASS: _build_argv bulk (empty allowed_tools) omits --allowedTools, adds --disallowedTools")
     ```

  2. **Update** the existing tool-use assertion (current `test-llm-claude.py:158-161`):

     ```python
     argv = _build_argv("claude-sonnet-4-5", "max", "Read,Grep,Glob")
     assert "--effort" in argv and "max" in argv
     assert "Read,Grep,Glob" in argv
     print("PASS: _build_argv tool-use with effort")
     ```

     to also assert the deny-list:

     ```python
     argv = _build_argv("claude-sonnet-4-5", "max", "Read,Grep,Glob")
     assert "--effort" in argv and "max" in argv
     assert "--allowedTools" in argv and "Read,Grep,Glob" in argv
     assert "--disallowedTools" in argv
     dt_idx = argv.index("--disallowedTools")
     assert argv[dt_idx + 1] == "Edit,Write,Bash,NotebookEdit"
     print("PASS: _build_argv tool-use with effort + --disallowedTools deny-list")
     ```

  3. **Extend** the existing `run_implementer` argv-shape test (currently around `test-llm-claude.py:255-281`) to additionally assert that `--disallowedTools` is NOT present:

     ```python
     assert "--disallowedTools" not in captured_argv, \
         f"run_implementer must NOT carry --disallowedTools; got {captured_argv}"
     ```

     Insert the assertion immediately after the existing `assert tools_value == "Read,Edit,Write,Bash,Grep,Glob,Skill"` line, before the `print("PASS: run_implementer ...")` line. Update the PASS string to include `+ no --disallowedTools`.

  4. **Add** two NEW argv-shape tests for `run_bulk` and `run_tool_use` mirroring the existing `run_implementer` pattern (mock-capture of argv via `mock.patch.object(_subprocess_util_mod, "run", _fake_run)`). Each new test:

     - Define a FRESH `_fake_run` closure per test that closes over its own local `captured_argv: list[str] = []` — DO NOT rebind a module-level `captured_argv = []` while reusing the existing `_fake_run` closure. Python closures capture by name binding: the existing `_fake_run` extends the original list object, so re-assigning the name `captured_argv` in an outer scope produces a new list that the closure never writes to, making any assertions on it pass vacuously. The correct shape is exactly the existing `run_implementer` block (`captured_argv: list[str] = []` then `def _fake_run(argv, **_kwargs): captured_argv.extend(argv); return _FakeResult()`) duplicated, not mutated. The alternative — `captured_argv.clear()` between tests when reusing a single closure — is also acceptable, but the closure-per-test pattern matches what already exists in the file.
     - Reuse `_FAKE_STDOUT` / `_FakeResult` from the existing `run_implementer` test block — those are correctly module-level and safe to share.
     - Calls `run_bulk("hello", model="claude-sonnet-4-5", session_id="fake-sid-456")` / `run_tool_use("hello", model="claude-sonnet-4-5", session_id="fake-sid-789")` inside `with mock.patch.object(_subprocess_util_mod, "run", _fake_run):`.
     - For `run_bulk`: asserts `"--allowedTools" not in captured_argv` AND `argv` contains the pair `["--disallowedTools", "Edit,Write,Bash,NotebookEdit"]`.
     - For `run_tool_use`: asserts `captured_argv` contains both `["--allowedTools", "Read,Grep,Glob"]` AND `["--disallowedTools", "Edit,Write,Bash,NotebookEdit"]`.
     - Each prints one `PASS:` line.

  5. No removal of existing PASS lines beyond the one explicitly replaced in step (1). All other existing tests continue to pass unchanged.

  6. ASCII-only `print()` strings; em-dashes in any new PASS strings become `--`.

- **Commit:** `test(_llm_claude): assert --allowedTools/--disallowedTools shape per caller`

## Batch Tests

`verify: python plugins/mill/unit_tests/test-llm-claude.py`

The extended test covers: `_build_argv` for the three callers' `allowed_tools` values produces the expected shape; `run_bulk` / `run_tool_use` / `run_implementer` argv-capture matches the table in Batch Scope. All existing tests (signature checks, parse_stream_json cases, _scan_rate_limit cases, fast-fail retry path, rate-limit path) continue to pass — none of them touched the argv shape beyond the one assertion replaced in step (1) of card 7.
