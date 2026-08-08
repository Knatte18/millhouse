# Batch: claude-sub-idle-mock

```yaml
task: 'Unit test suite: hangs, unmocked-path errors, and stuck/success envelope bug found in piecewise sweep'
batch: 'claude-sub-idle-mock'
number: 1
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --sequential --only test-claude-sub.py
depends-on: []
```

## Batch Scope

`test-claude-sub.py`'s S5 scenario ("keep-alive true, error mid-call when wrapper owns session")
never mocks `_wait_for_idle_stable`, so `millpy-claude-sub.py:main()`'s Step 11 call to it runs for
real against a static `_psmux.capture_pane` mock, looping for up to ~5.25 minutes before it would
resolve on its own — indistinguishable from an indefinite hang under any bounded test timeout. This
is a single-file, single-card batch: one missing mock line, no other scenario in the file is
affected (S1-S4, S6-S17 already mock every real-wait call their own code path reaches).

## Cards

### Card 1: Mock `_wait_for_idle_stable` in S5

- **Context:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-claude-sub.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `S5` scenario's `with` block (the block that opens with
  `mock.patch("_psmux.new_session"), \` and currently ends with
  `mock.patch("sys.stderr", new_callable=io.StringIO):`), add
  `mock.patch.object(mod, "_wait_for_idle_stable", return_value=False)` as an additional context
  manager in that same `with` statement.
  `_wait_for_idle_stable` (`millpy-claude-sub.py:142`) is currently unmocked in S5: `main()`
  unconditionally calls it at Step 11 (`millpy-claude-sub.py:351`) after building/sending the
  claude launch command, regardless of which session-acquisition branch was taken. Because S5's
  `mock_list_sessions` returns `[]`, the `"new-name"` session does not already exist, so `main()`
  takes the create-new-session branch (`session_owned_by_us = True`, `session_reused = False`) and
  reaches Step 11 for real. With `_psmux.capture_pane` mocked to a static `""`, Phase 1 of
  `_wait_for_idle_stable` never finds `"interrupt"` in the pane and falls through after
  `PROCESSING_WAIT_TIMEOUT_S = 15`s, then Phase 2 never finds `"shortcuts"` and runs out the full
  `RESPONSE_POLL_TIMEOUT_S["bulk"] = 300`s (S5 sets `mode="bulk"` and mocks
  `_config.load_config` to return `{}`, so no config override applies) — a real ~315s sleep in the
  test process. Mocking `_wait_for_idle_stable` directly to `return_value=False` drives `main()`
  into the real `RuntimeError(f"response-poll timeout: ...")` path (`millpy-claude-sub.py:351-355`),
  which is caught by the outer `except Exception` block, calls `_psmux.kill_session` (already
  mocked in S5 as `m_kill`, since `session_owned_by_us=True`), and returns `1`. Do not change any
  of S5's existing assertions (`assert m_kill.call_count > 0`, `assert ret == 1`) or any other line
  in S5 — they already match this path exactly.
- **Commit:** `fix(test): mock _wait_for_idle_stable in test-claude-sub.py S5 to prevent 5-minute hang`

## Batch Tests

`verify:` runs `test-claude-sub.py` alone, sequentially (this file's own hang history makes
`--sequential` the safer choice for this specific file even though the fix removes the hang).
Confirms all `S1`-`S17` scenarios print `PASS`, with no hang, in well under the default
per-invocation timeout.
