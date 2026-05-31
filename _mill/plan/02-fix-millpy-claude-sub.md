# Batch: Fix millpy-claude-sub

```yaml
task: Replace claude -p with psmux-routed LLM dispatch
batch: Fix millpy-claude-sub
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-claude-sub.py
depends-on: []
```

## Batch Scope

Four targeted fixes to `millpy-claude-sub.py`, all in the same file and applied
in card order: (1) add `_resolve_shell_path()` config reader and bump
`rows=100`; (2) rewrite `_wait_for_idle_prompt` to use status-bar check; (3)
rewrite `_wait_for_idle_stable` as a two-phase status-bar wait; (4) send
`Escape` on the reuse path before prompt submission. These are independent
diffs within the same file; apply them sequentially.

## Cards

### Card 2: Add _resolve_shell_path() and fix new_session calls

- **Context:**
  - `doc/psmux-tui-behavior.md`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add `_resolve_shell_path() -> str` immediately after
  `_resolve_reuse_idle_timeout_s()` (around line 167). Body: try
  `_config.load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path())`,
  return `cfg.get("llm",{}).get("claude",{}).get("psmux",{}).get("shell_path",
  "pwsh")`. On any `Exception` or `SystemExit`, return `"pwsh"`. In both
  `new_session` call sites (currently `shell_argv=["pwsh", "-NoLogo",
  "-NoProfile"]` at approximately lines 213 and 237), replace `"pwsh"` with
  `_resolve_shell_path()`. Also change `rows=50` to `rows=100` at both call
  sites (same two locations). No other changes in this card.
- **Commit:** `fix(millpy-claude-sub): read shell_path from config; bump rows to 100`

### Card 3: Rewrite _wait_for_idle_prompt with status-bar check

- **Context:**
  - `doc/psmux-tui-behavior.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Replace the body of `_wait_for_idle_prompt` (currently checks for lines
  starting with `❯`). New body: poll `_psmux.capture_pane(session_name,
  alternate=True)` in a loop; on each iteration check `"for shortcuts" in
  capture` — return `True` immediately if found. On `PsmuxError` return `False`.
  On timeout return `False`. Keep the same signature
  `(session_name: str, timeout_s: float) -> bool` and the same
  `start/timeout/sleep` structure. Update the docstring: "Poll capture-pane
  status bar for the idle marker ('for shortcuts'). Return True on match, False
  on timeout."
- **Commit:** `fix(millpy-claude-sub): replace ❯ check with status-bar check in _wait_for_idle_prompt`

### Card 4: Rewrite _wait_for_idle_stable as two-phase status-bar wait

- **Context:**
  - `doc/psmux-tui-behavior.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Replace the body of `_wait_for_idle_stable` with a two-phase implementation.
  Phase 1: record `phase1_start = time.monotonic()`. Poll in a loop while
  `time.monotonic() - phase1_start < BOOT_READY_TIMEOUT_S`. On each iteration
  call `_psmux.capture_pane(session_name, alternate=True)` (swallow
  `PsmuxError`); if `"esc to interrupt" in capture` or `"esctointerrupt" in
  capture`, `break` out of the loop. Sleep `POLL_INTERVAL_S` between polls.
  Fall through on timeout (do NOT raise). Phase 2: record
  `phase2_start = time.monotonic()`. `prev_idle = False`. Poll in a loop;
  on each iteration: `curr_idle = "for shortcuts" in capture` (swallow
  `PsmuxError` → `curr_idle = False`); if `prev_idle and curr_idle` return
  `True`; set `prev_idle = curr_idle`; if
  `time.monotonic() - phase2_start >= timeout_s` return `False`; sleep
  `POLL_INTERVAL_S`. Keep the same signature
  `(session_name: str, timeout_s: float) -> bool`. Update the docstring to
  describe the two-phase approach and the fall-through behaviour.
- **Commit:** `fix(millpy-claude-sub): rewrite _wait_for_idle_stable as two-phase status-bar wait`

### Card 5: Send Escape on reuse path before bracketed paste

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In the reuse path, immediately after the `session_reused = True` assignment
  and before the `# Step 10` comment block, add:
  ```python
  if session_reused:
      _psmux.send_keys(session_name, "Escape", enter=False)
      time.sleep(POLL_INTERVAL_S)
  ```
  This clears any auto-suggest text the TUI may have pre-filled in the input
  area after a previous response. The new-session path never has auto-suggest
  (session is freshly started), so the guard is inside `if session_reused:`.
  No other changes in this card.
- **Commit:** `fix(millpy-claude-sub): send Escape before reuse prompt submission`

## Batch Tests

`test-claude-sub.py` — S1-S11 mock `_wait_for_idle_prompt` and
`_wait_for_idle_stable` at the module level, so the mock signatures survive the
rewrite. However, the direct unit tests for `_wait_for_idle_stable` at the
bottom of the file (Scenarios a/b/c) mock `_psmux.capture_pane` to return
`"❯ idle\n"` — these will fail after Card 4's rewrite because the new code
checks for `"for shortcuts"`, not `"❯"`. Those direct tests are updated in
Batch 4 (Card 10). The `verify:` here runs the current test suite; Card 4's
changes will cause the Scenario tests to fail until Batch 4 lands. If the
implementer runs verify after each card, this is expected — the fix is
incomplete until Batch 4.
