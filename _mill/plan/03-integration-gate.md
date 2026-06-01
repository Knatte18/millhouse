# Batch: Integration gate

```yaml
task: Smoke-test the psmux implementer end-to-end
batch: Integration gate
number: 3
cards: 2
verify: PYTHONPATH= "$MILL_PYTHON" plugins/mill/integration_tests/test-claude-psmux.py
depends-on: [2]
```

## Batch Scope

Final two changes: fix the silent-failure bug in the live integration test harness, then flip `via_psmux: true` in the hub config. The `verify:` command runs the full live integration test suite (all 4 tests: `test_bulk`, `test_tool_use`, `test_implementer`, `test_keep_alive_reuse`). This requires real psmux and real Claude — both are confirmed present on this machine (`psmux ls` returns sessions; `claude.exe 2.1.159.0` at `C:\Users\hanf\.local\bin\claude.exe`). Expected wall-clock: 5-15 minutes. This batch depends on batch 2 because the production fixes must be in place before the live test can pass.

## Cards

### Card 6: Fix silent-failure in test-claude-psmux.py

- **Context:** none
- **Edits:**
  - `plugins/mill/integration_tests/test-claude-psmux.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In each of the four test functions (`test_bulk`, `test_tool_use`, `test_implementer`, `test_keep_alive_reuse`): in the `except Exception as exc:` block, add `print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)` immediately before `return 1`. The line must come BEFORE the `return 1` statement.
  - Do not re-raise, do not change the `return 1`, do not change any assertion logic or timeouts.
- **Commit:** `fix(test-claude-psmux): print exception details in failure handlers`

### Card 7: Enable via_psmux in mill-config.yaml

- **Context:** none
- **Edits:**
  - `mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Change `via_psmux: false` to `via_psmux: true` in the `llm.claude.psmux` section. This is the only edit to this file.
  - Do NOT touch `plugins/mill/templates/mill-config.yaml` — the template default stays `false`.
- **Commit:** `feat(mill-config): enable via_psmux for psmux-routed LLM dispatch`

## Batch Tests

`verify:` runs `plugins/mill/integration_tests/test-claude-psmux.py` directly. The test file sets its own `sys.path` so `PYTHONPATH=` (empty) is correct.

The test suite runs four live tests that each spawn `millpy-claude-sub.py` as a subprocess, which in turn creates a psmux session, boots the Claude TUI, submits a prompt, and extracts the response:
- `test_bulk`: sends "Reply with the single word PONG" — asserts `PONG` in response.
- `test_tool_use`: sends a Glob request — asserts `plugins` appears in response.
- `test_implementer`: sends `echo __INTEGRATION_OK__` via Bash — asserts sentinel in response.
- `test_keep_alive_reuse`: first call with `--keep-alive`, second call reuses session — asserts `FIRST` then `SECOND`, no bleed-through.

All four must exit 0. With card 6's exception-printing fix, any failure will show the exception rather than the opaque "test returned non-zero" message.

Note: this `verify:` is intentionally unbounded (no `--only` flag) because there is only one integration test file being targeted. The full suite is these 4 tests; there is no filtering needed.
