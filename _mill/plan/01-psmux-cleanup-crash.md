# Batch: psmux-cleanup-crash

```yaml
task: "Unhandled exceptions in mill-go orchestration components should degrade gracefully"
batch: "psmux-cleanup-crash"
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-psmux-driver.py test-llm-claude.py
depends-on: []
```

## Batch Scope

This batch fixes the psmux-cleanup crash (GitHub issues #661, #657, #655, #647): every
per-batch and holistic-round call to `_llm_claude.cleanup_session()` shells out to
`_psmux.list_sessions()` (`psmux ls`) even when the current dispatch mode never created a
psmux session (`agent`, `subprocess`), and the call raises an unhandled `FileNotFoundError`
whenever the `psmux` binary is absent — printing a full Python traceback on every batch/round.
This batch adds a dispatch-mode early-return gate inside `cleanup_session()` itself (so no
caller needs to change), plus a `FileNotFoundError` catch inside `_psmux.list_sessions()` as
defense-in-depth for a genuine `dispatch: psmux` misconfiguration, then removes the now-obsolete
`|| true` band-aids from the two `mill-go/SKILL.md` invocation sites. No external interface
changes — `cleanup_session(session_id)`'s signature and the two `mill-go/SKILL.md` call sites'
Python snippets are otherwise untouched; only the internal control flow changes. All
batch-local decisions are documented per-card below (no deviations from the overview's Shared
Decisions).

## Cards

### Card 1: `_psmux.list_sessions()` degrades cleanly when the psmux binary is missing

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_psmux.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_psmux.py`'s `list_sessions()` function, add a sibling
  `except FileNotFoundError: return []` clause immediately after the existing
  `except PsmuxError as e:` clause (same `try` block that wraps
  `_subprocess_util.run(argv, timeout=PSMUX_COMMAND_TIMEOUT_S)`), so a missing `psmux` binary
  degrades the same way the existing `"no server running"` `PsmuxError` case already does —
  returning `[]` instead of letting `FileNotFoundError` propagate as an unhandled traceback.
  Do not change any other line of `list_sessions()`, and do not touch any other function in
  `_psmux.py` (`new_session`, `set_history_limit`, `send_keys`, `load_buffer`,
  `paste_buffer`, `capture_pane`, `kill_session` are out of scope).
- **Commit:** `fix(psmux): list_sessions returns empty list when psmux binary is missing`

### Card 2: test coverage for `list_sessions()` FileNotFoundError handling

- **Context:**
  - `plugins/mill/scripts/_psmux.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-psmux-driver.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `test-psmux-driver.py`, immediately after the existing
  `# Test list_sessions with "no server running" error` block, add a new block in the same
  style: `with mock.patch.object(_psmux._subprocess_util, "run") as mock_run:` set
  `mock_run.side_effect = FileNotFoundError(2, "No such file or directory", "psmux")`, call
  `result = list_sessions()`, `assert result == []`, and print
  `PASS: list_sessions returns empty list when psmux binary is missing (FileNotFoundError)` on
  success (matching the file's existing bare-`assert`-then-`print` convention for this test
  function — errors propagate to the caller's `try/except` at the module level, consistent
  with every other test block in this file).
- **Commit:** `test(psmux): cover list_sessions FileNotFoundError handling`

### Card 3: `cleanup_session()` dispatch-mode gate

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_llm_claude.py`'s `cleanup_session(session_id)` (currently ~line 525),
  after the existing `if not session_id: return None` guard and before the existing
  `try: import _psmux ...` block that performs the actual psmux cleanup, insert a new gate
  that mirrors `_get_via_psmux_flag()`'s resolution chain (same file, ~line 99): inside its own
  `try:` block, locally `import _paths` and `import _config` (matching
  `_get_via_psmux_flag`'s local-import style — do not add these as module-level imports),
  compute `git_root = _paths.resolve_git_root(Path.cwd())`, then
  `cfg = _config.load_config(_paths.resolve_hub_path(), git_root)`, then
  `if _agent_dispatch.resolve_dispatch_mode(cfg) != "psmux": return None`.
  `_agent_dispatch` is already imported at module level (line 42) — reference it directly, do
  not re-import it locally. Wrap this whole new block in `except Exception: pass` so that on
  any resolution failure (missing config, cwd outside a git worktree, etc.) execution falls
  through to the existing psmux-cleanup logic below rather than raising or returning — this is
  the deliberate inverse of `_get_via_psmux_flag`'s "return False on any error" contract:
  `cleanup_session` must never silently skip cleanup just because dispatch-mode resolution
  itself failed. Leave the existing `psmux_name = f"mill-{session_id[:12]}"` /
  `existing = _psmux.list_sessions()` / `if psmux_name in existing: ...` /
  `except _psmux.PsmuxError: pass` block below completely unchanged — this card only adds the
  new gate above it.
- **Commit:** `fix(llm-claude): cleanup_session no-ops when dispatch mode is not psmux`

### Card 4: test coverage for the `cleanup_session()` dispatch-mode gate

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `test-llm-claude.py`'s existing `# K5: cleanup_session behavior` block
  (~lines 715-761): each of the four existing sub-tests — K5(i) session-exists-and-killed,
  K5(ii) session-not-present, K5(iii) PsmuxError-swallowed, K5(iv) no-op-on-None/empty — mocks
  only `_psmux_mod.list_sessions` / `_psmux_mod.kill_session` and calls `cleanup_session(...)`
  directly. After Card 3 lands, these calls resolve the REAL local dispatch mode via the real
  `_config.load_config`/`_paths.resolve_git_root` (which resolves to `dispatch: agent` in this
  worktree), so the new gate will short-circuit every one of them before `list_sessions` is
  ever called, breaking all four existing assertions. Fix this by wrapping each of K5(i)-(iv)'s
  existing `with mock.patch.object(_psmux_mod, ...)` block(s) in an outer
  `with mock.patch.object(_config_mod, "load_config", return_value={"llm": {"claude": {"dispatch": "psmux"}}}):`
  and `with mock.patch.object(_paths, "resolve_git_root", return_value=Path(".")):` —
  reusing exactly the two-mock pattern already used for `_get_via_psmux_flag` Test 12
  sub-case (i) in the same file (~lines 888-890) — so dispatch resolves to `"psmux"` and
  control passes through the new gate to the existing mocked `list_sessions`/`kill_session`
  behavior, unchanged. `_config_mod` is already imported at module level
  (`import _config as _config_mod`); `_paths` is imported locally inside the existing Test 11
  block (~line 875) — hoist that `import _paths` to the module-level import section (with the
  other `# noqa: E402` imports) since it is now needed earlier in the file (K5 precedes Test
  11/12), and remove the now-redundant local `import _paths` inside Test 11. Then add three
  NEW sub-tests immediately after the (now-fixed) K5(iv) block: **K5(v)** dispatch mode
  `"agent"` — mock `_config_mod.load_config` to return
  `{"llm": {"claude": {"dispatch": "agent"}}}` and `_paths.resolve_git_root` to return
  `Path(".")`, then mock `_psmux_mod.list_sessions` with
  `mock.Mock(side_effect=AssertionError("list_sessions should not be called in agent mode"))`,
  call `cleanup_session("any-session-id-here")`, and assert no exception propagates (proving
  the gate short-circuited before `list_sessions` was ever called); print
  `PASS: K5(v) cleanup_session no-ops under dispatch: agent` on success. **K5(vi)**: identical
  to K5(v) but with dispatch `"subprocess"` and message
  `PASS: K5(vi) cleanup_session no-ops under dispatch: subprocess`. **K5(vii)**:
  dispatch-mode-resolution failure — mock `_paths.resolve_git_root` with
  `side_effect=SystemExit("no git root")`, mock `_psmux_mod.list_sessions` with
  `return_value=["mill-abc-123-de-f"]` and `_psmux_mod.kill_session` with `return_value=None`
  (as a `mock.patch.object(..., return_value=None) as mock_kill`), call
  `cleanup_session("abc-123-de-fghij-rest")`, and assert `mock_kill.called` is True with
  `mock_kill.call_args[0][0] == "mill-abc-123-de-f"` — proving that when dispatch-mode
  resolution itself fails, cleanup still proceeds (falls through to the existing logic) rather
  than silently skipping; print
  `PASS: K5(vii) cleanup_session proceeds when dispatch-mode resolution fails` on success.
- **Commit:** `test(llm-claude): cover cleanup_session dispatch-mode gate`

### Card 5: remove obsolete `|| true` band-aids from mill-go cleanup blocks

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/skills/mill-go/SKILL.md`, remove the trailing `|| true`
  from the two Bash tool-call blocks that invoke `_llm_claude.cleanup_session(...)`: the
  **per-batch cleanup block** under the "Per-batch session cleanup." heading (the fenced bash
  block whose Python `-c` string ends with `_llm_claude.cleanup_session(sid)`, ~line 184-195)
  and the **holistic cleanup block** under the "Holistic session cleanup." heading (the fenced
  bash block whose Python `-c` string ends with
  `_llm_claude.cleanup_session('${holistic_sid}')`, ~line 530-542). In each block, change the
  closing line from `" || true` to a bare `"` (the closing quote of the inline `-c` string,
  with `|| true` and its preceding space removed, no trailing whitespace introduced). Do not
  alter any other line in either fenced block, and do not alter the surrounding prose in either
  "Per-batch session cleanup." or "Holistic session cleanup." paragraph — both already describe
  the calls as "idempotent and failure-swallowing," which remains accurate after this change
  (idempotent because `cleanup_session` is a safe no-op once nothing needs cleaning up;
  failure-swallowing internally via its own `except _psmux.PsmuxError: pass` and, after Card 3,
  the dispatch-mode gate — not via the shell-level `|| true`).
- **Commit:** `docs(mill-go): remove obsolete || true after cleanup_session hardening`

## Batch Tests

`verify:` runs `test-psmux-driver.py` (Cards 1-2) and `test-llm-claude.py` (Cards 3-4) via
`run-all.py --only`, scoped to exactly the two files this batch edits tests for. Card 5
(`mill-go/SKILL.md`) has no runnable test surface — it is a documentation/skill file with no
associated unit test; its correctness is verified by inspection (the two-line diff is
mechanical and unambiguous) and, transitively, the next `/mill-go` run that exercises the
cleanup blocks.
