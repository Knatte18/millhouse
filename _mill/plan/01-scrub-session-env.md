# Batch: scrub-session-env

```yaml
task: "mill-vscode/mill-spawn leak CLAUDE_CODE_CHILD_SESSION into spawned VS Code windows"
batch: scrub-session-env
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-subprocess-util.py test-millpy-vscode.py test-millpy-terminal.py
depends-on: []
```

## Batch Scope

This batch closes GitHub issue #719: `millpy-vscode.py` and `millpy-terminal.py` spawn
`code`/`claude` as a subprocess of the running Claude Code session without scrubbing
`CLAUDE_CODE_CHILD_SESSION`/`CLAUDE_CODE_SESSION_ID`/`CLAUDE_CODE_ENTRYPOINT` from the
child environment, so any Claude session opened in the spawned window inherits the
child-session marker and disables transcript saving. The whole fix is one cohesive
unit — a single new helper plus four call sites that all use it the same way — so it
is one batch. Card 1 adds the shared `scrub_env()` helper and its dedicated unit
tests (an external interface the other two cards consume). Cards 2 and 3 wire that
helper into the two files' four call sites and update exactly the test exemplars
`discussion.md`'s `Testing` section names — no other existing test in either file
changes. No batch-local decisions beyond what `## Shared Decisions` in the overview
already states.

## Cards

### Card 1: Add `scrub_env()` helper and its unit tests

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/unit_tests/test-subprocess-util.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `plugins/mill/scripts/_subprocess_util.py`: add a module-level constant
    `_SCRUBBED_ENV_KEYS = frozenset({"CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_ENTRYPOINT"})`
    near the top of the file (after the existing `_GRACE_SECONDS` /
    `_CREATE_BREAKAWAY_FROM_JOB` module constants).
  - Add a new public function:
    `def scrub_env(env: dict[str, str] | None = None) -> dict[str, str]:` that returns
    `{k: v for k, v in (env if env is not None else os.environ).items() if k not in _SCRUBBED_ENV_KEYS}`.
    When `env` is `None` (the default), read from `os.environ`; when a caller passes an
    explicit `env` dict, filter that dict instead — never mutate the input, always
    return a new dict. Do not add a `prefix` parameter — the filter is an exact-match
    allowlist, not a prefix match (see overview `Decision: allowlist, not prefix
    match`).
  - Add `scrub_env` to the module docstring's `Public API:` list, one line, in the
    same style as the existing `run(...)` / `popen_detached(...)` entries — state that
    it strips the 3 named `CLAUDE_CODE_*` session markers and is used by interactive
    launchers that bypass `run()`.
  - In `plugins/mill/unit_tests/test-subprocess-util.py`: add `scrub_env` to the
    existing `from _subprocess_util import _GRACE_SECONDS, popen_detached, run` line
    (line 21) so it reads
    `from _subprocess_util import _GRACE_SECONDS, popen_detached, run, scrub_env  # noqa: E402`.
  - Add 3 new labeled test cases inside `main()`, following the existing
    `# (x) <description>` / `try/except AssertionError` / `failures.append(...)`
    convention used by every existing case in this file, placed after case `(o)` and
    before the `if failures:` block. Continue the letter sequence from `(o)`:
    - `(p)`: call `scrub_env(env={...})` with an explicit fake dict containing all 3
      allowlisted keys (`CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`,
      `CLAUDE_CODE_ENTRYPOINT`) set to arbitrary non-empty values, plus ordinary keys
      `PATH` and `HOME`, plus a same-prefix persistent-config key
      `CLAUDE_CODE_USE_BEDROCK` (per `discussion.md`'s round-2 finding — proves the
      allowlist does not over-strip). Assert the 3 allowlisted keys are absent from
      the result and that `PATH`, `HOME`, and `CLAUDE_CODE_USE_BEDROCK` are present
      with their original values, unchanged. Also assert the input dict passed to
      `scrub_env` is itself unmodified afterward (the function must not mutate its
      argument).
    - `(q)`: call `scrub_env(env={"PATH": "/usr/bin", "HOME": "/home/x"})` — a dict
      with none of the 3 allowlisted keys present. Assert the result is unchanged
      (full dict equality with the input) — no-op, no error, when none of the
      allowlisted keys exist.
    - `(r)`: call `scrub_env()` with no argument (default `env=None`), using
      `unittest.mock.patch.dict(os.environ, {"CLAUDE_CODE_CHILD_SESSION": "1"})` (a
      new `import os` and `unittest.mock.patch.dict` import/usage — `os` is not
      currently imported in this file; add `import os` alongside the other stdlib
      imports at the top) to inject one allowlisted key into the real environment for
      the duration of the test. Assert `"CLAUDE_CODE_CHILD_SESSION"` is absent from
      the result, and that some other real key already present in `os.environ`
      before the patch (e.g. `PATH`, which is present in every POSIX process) is
      present in the result with its real value — proving the default path reads live
      `os.environ`, not an empty dict.
- **Commit:** `fix(subprocess-util): add scrub_env() to strip CLAUDE_CODE_* session markers`

### Card 2: Wire `scrub_env()` into `millpy-vscode.py`'s two launch sites

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-vscode.py`
  - `plugins/mill/unit_tests/test-millpy-vscode.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `plugins/mill/scripts/millpy-vscode.py`: add `import _subprocess_util` to the
    existing block of local-module imports (alongside `_spawn_core`,
    `_vscode_processes`).
  - In `_spawn_and_open()` (currently `subprocess.run(_build_code_argv(launch_path))`,
    line 132): change the call to
    `subprocess.run(_build_code_argv(launch_path), env=_subprocess_util.scrub_env())`.
  - In `main()`'s interactive picker (currently `subprocess.run(code_argv)`, line
    275, immediately after the "Interactive launcher — must keep its console; do NOT
    route through `_subprocess_util.run`" comment): change the call to
    `subprocess.run(code_argv, env=_subprocess_util.scrub_env())`. Do not remove or
    alter that comment — the constraint it documents (bypass `_subprocess_util.run()`
    for console ownership) is still true; only the `env=` kwarg is new. Passing
    `env=_subprocess_util.scrub_env()` here does not violate that comment: it calls
    the plain `scrub_env()` function directly, not the `run()` wrapper.
  - In `plugins/mill/unit_tests/test-millpy-vscode.py`, update exactly these two
    existing test blocks — no other test in this file changes:
    - The **"two worktrees, user picks first"** test (`mock_subprocess_run(argv,
      **kwargs)` defined just above its `with (...)` block, patched in via
      `patch("mill_vscode.subprocess.run", side_effect=mock_subprocess_run)`): change
      the mock function body from `subprocess_calls.append({"argv": argv})` to
      `subprocess_calls.append({"argv": argv, "env": kwargs.get("env")})`. Add
      `patch.dict(os.environ, {"CLAUDE_CODE_CHILD_SESSION": "1", "PATH": os.environ.get("PATH", "")})`
      to the test's `with (...)` context-manager tuple (a new `import os` at the top
      of this file, alongside the existing stdlib imports, if not already present).
      After the existing PASS/FAIL assertions on `argv`, add new assertions: the
      captured `subprocess_calls[0]["env"]` is not `None`; none of
      `CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_ENTRYPOINT`
      appear as keys in it; `"PATH"` is present in it with the same value injected via
      `patch.dict`. Follow the existing `errors += 1` / `print("FAIL: ...")` /
      `print("PASS: ...")` control-flow convention already used in this test block.
    - The **"no active worktrees, no flags -> spawn called, new worktree opened"**
      test (`side_effect=lambda a, **kw: subprocess_calls.append({"argv": a})` patched
      onto `mill_vscode.subprocess.run`): change the lambda to
      `lambda a, **kw: subprocess_calls.append({"argv": a, "env": kw.get("env")})`.
      Add the same `patch.dict(os.environ, {"CLAUDE_CODE_CHILD_SESSION": "1", "PATH":
      os.environ.get("PATH", "")})` to this test's `with (...)` tuple. Add the same
      three env assertions (not-`None`, no allowlisted keys, `PATH` present with its
      injected value) after the existing `argv` assertion, following the existing
      `errors += 1` control-flow convention in this test block.
- **Commit:** `fix(mill-vscode): pass scrub_env() to both code-launch subprocess calls`

### Card 3: Wire `scrub_env()` into `millpy-terminal.py`'s two launch sites

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-terminal.py`
  - `plugins/mill/unit_tests/test-millpy-terminal.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `plugins/mill/scripts/millpy-terminal.py`: add `import _subprocess_util` to
    the existing block of local-module imports (alongside `_spawn_core`).
  - In `main()` (currently, lines 116-121, immediately after the "Interactive
    launcher — must keep its console; do NOT route through `_subprocess_util.run`"
    comment repeated on both branches):
    - Windows branch: change
      `subprocess.run(["cmd", "/c", "claude", "--name", selected_slug], cwd=launch_path)`
      to
      `subprocess.run(["cmd", "/c", "claude", "--name", selected_slug], cwd=launch_path, env=_subprocess_util.scrub_env())`.
    - POSIX branch: change
      `subprocess.run(["claude", "--name", selected_slug], cwd=launch_path)` to
      `subprocess.run(["claude", "--name", selected_slug], cwd=launch_path, env=_subprocess_util.scrub_env())`.
    - Do not remove or alter either "must keep its console" comment — only the
      `env=` kwarg is new on each call, exactly as in Card 2.
  - In `plugins/mill/unit_tests/test-millpy-terminal.py`, update exactly this one
    existing test block — no other test in this file changes:
    - The **"single worktree -> auto-selected, subprocess called without prompt"**
      test (`patch("mill_terminal.subprocess.run", side_effect=lambda *a, **kw: subprocess_calls.append(kw.get("cwd")))`):
      change the lambda to
      `lambda *a, **kw: subprocess_calls.append({"cwd": kw.get("cwd"), "env": kw.get("env")})`.
      Update the existing assertion `subprocess_calls[0] != wt1` (and its associated
      FAIL message) to read from the new dict shape (`subprocess_calls[0]["cwd"] !=
      wt1`) instead of the old bare-value shape. Add
      `patch.dict(os.environ, {"CLAUDE_CODE_CHILD_SESSION": "1", "PATH": os.environ.get("PATH", "")})`
      to this test's `with (...)` tuple (a new `import os` at the top of this file, if
      not already present). Add new assertions after the existing `cwd` check: the
      captured `subprocess_calls[0]["env"]` is not `None`; none of
      `CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_ENTRYPOINT`
      appear as keys in it; `"PATH"` is present in it with the same value injected via
      `patch.dict`. Follow the existing `errors += 1` control-flow convention already
      used in this test block. `millpy-terminal.py`'s Windows branch and every other
      existing test in this file are unaffected — see `discussion.md`'s `Testing`
      section for why the Windows branch stays untested (no existing `os.name` mock in
      this file, pre-existing gap, out of scope).
- **Commit:** `fix(mill-terminal): pass scrub_env() to both claude-launch subprocess calls`

## Batch Tests

`verify:` runs
`plugins/mill/unit_tests/run-all.py --only test-subprocess-util.py test-millpy-vscode.py test-millpy-terminal.py`,
covering exactly the three files this batch edits: the new `scrub_env()` unit tests
(Card 1), and the updated exemplar tests in both call-site test files (Cards 2 and 3).
No other test file references `scrub_env`, `millpy-vscode.py`, or `millpy-terminal.py`,
so this scope is complete for the batch. `_llm_claude.py`'s `STRIP_VARS`-based tests
are untouched and out of scope (see `discussion.md`'s `Scope > Out`).
