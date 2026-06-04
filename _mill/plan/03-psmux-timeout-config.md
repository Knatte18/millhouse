# Batch: psmux-timeout-config

```yaml
task: Fix millpy-bg EXIT marker and implementer reliability
batch: psmux-timeout-config
number: 3
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Makes `RESPONSE_POLL_TIMEOUT_S` in `millpy-claude-sub.py` configurable via
`mill-config.yaml`. A new `_resolve_response_poll_timeout_s(mode)` function mirrors the
existing `_resolve_reuse_idle_timeout_s()` pattern: it loads the config and looks up
`llm.claude.psmux.response_poll_timeout_s.<mode>`, falling back to the hardcoded dict if
the key is absent. The default values in the config template match the current hardcoded
defaults exactly, so existing tasks are unaffected. No unit tests are added: the config-load
path is structurally identical to `_resolve_reuse_idle_timeout_s()` which is already covered
by indirect test runs; verify: null is appropriate for a config-wiring change.

## Cards

### Card 7: Add _resolve_response_poll_timeout_s to millpy-claude-sub.py

- **Context:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add function `_resolve_response_poll_timeout_s(mode: str) -> float` immediately after the existing `_resolve_reuse_idle_timeout_s()` function (around line 187). Body:
    ```python
    def _resolve_response_poll_timeout_s(mode: str) -> float:
        try:
            cfg = _config.load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path())
            override = (
                cfg.get("llm", {})
                .get("claude", {})
                .get("psmux", {})
                .get("response_poll_timeout_s", {})
            )
            if isinstance(override, dict) and mode in override:
                return float(override[mode])
        except (Exception, SystemExit):
            pass
        return float(RESPONSE_POLL_TIMEOUT_S.get(mode, 600))
    ```
  - Replace line 325's `RESPONSE_POLL_TIMEOUT_S[args.mode]` with `_resolve_response_poll_timeout_s(args.mode)`.
  - Do not remove or rename `RESPONSE_POLL_TIMEOUT_S` — it serves as the fallback default table.
- **Commit:** `fix(millpy-claude-sub): make response_poll_timeout_s configurable per mode`

### Card 8: Add response_poll_timeout_s keys to mill-config.yaml template

- **Context:**
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Under `llm.claude.psmux:`, after the `reuse_idle_timeout_s: 10` line, add:
    ```yaml
          response_poll_timeout_s:  # Max seconds to wait for psmux Claude TUI to return to idle per mode
            bulk: 300
            tool-use: 600
            implementer: 1800
    ```
  - Indentation must match the surrounding YAML (2-space indent per level within the `psmux:` block).
  - Values must exactly match the hardcoded defaults in `RESPONSE_POLL_TIMEOUT_S` to keep existing behaviour unchanged.
- **Commit:** `feat(mill-config): add llm.claude.psmux.response_poll_timeout_s config keys`

## Batch Tests

`verify: null` — no runnable test surface for a config-wiring change that mirrors an
identical existing config-read path (`_resolve_reuse_idle_timeout_s`) already covered by
indirect tests in the suite.
