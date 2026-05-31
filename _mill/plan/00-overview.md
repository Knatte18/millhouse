# Plan: Replace claude -p with psmux-routed LLM dispatch

```yaml
task: Replace claude -p with psmux-routed LLM dispatch
slug: replace-claude-p-with-psmux
approved: true
started: 20260531-145020
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: Fix extract_response
    file: 01-fix-extract-response.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-psmux-capture.py

  - number: 2
    name: Fix millpy-claude-sub
    file: 02-fix-millpy-claude-sub.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-claude-sub.py

  - number: 3
    name: Config shell_path key
    file: 03-config-shell-path.md
    depends-on: []
    verify: null

  - number: 4
    name: Tests
    file: 04-tests.md
    depends-on: [1, 2, 3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-psmux-capture.py test-claude-sub.py test-llm-claude.py
```

## Shared Decisions

### Decision: status-bar-markers

- **Decision:** Idle state is detected by `"for shortcuts" in capture`; processing state by `"esc to interrupt" in capture` (or `"esctointerrupt"` — capture may omit spaces in the status bar). Both checks are case-sensitive substring matches against the full `capture-pane` output string.
- **Rationale:** Empirically verified on claude CLI 2.1.158. The `❯` prompt is present in all states and is not a valid idle signal.
- **Applies to:** Batch 2 (millpy-claude-sub.py)

### Decision: no-changes-to-psmux-driver

- **Decision:** `_psmux.py` and `_llm_claude.py` are correct and receive no changes in this task.
- **Rationale:** The bugs are in the wrapper logic (idle detection, response extraction) and config, not the subprocess driver or dispatch layer.
- **Applies to:** all batches

### Decision: config-read-pattern

- **Decision:** New `_resolve_shell_path()` in `millpy-claude-sub.py` follows the exact pattern of the existing `_resolve_reuse_idle_timeout_s()`: call `_config.load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path())`, navigate nested keys with `.get()` chains, return the default on any `Exception` or `SystemExit`.
- **Rationale:** Consistent with existing pattern in the same file; handles missing config gracefully.
- **Applies to:** Batch 2, Batch 3

## All Files Touched

- `mill-config.yaml`
- `plugins/mill/integration_tests/test-claude-psmux.py`
- `plugins/mill/scripts/_psmux_capture.py`
- `plugins/mill/scripts/millpy-claude-sub.py`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-claude-sub.py`
- `plugins/mill/unit_tests/test-llm-claude.py`
- `plugins/mill/unit_tests/test-psmux-capture.py`
