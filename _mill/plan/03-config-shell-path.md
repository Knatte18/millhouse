# Batch: Config shell_path key

```yaml
task: Replace claude -p with psmux-routed LLM dispatch
batch: Config shell_path key
number: 3
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Add the `llm.claude.psmux.shell_path` key to two YAML config files: the plugin
template (sets the key schema and default for new hubs) and the hub
`mill-config.yaml` (sets the site-specific value for this machine). Pure YAML
edits; no Python changes. No runnable test surface; `verify: null`.

## Cards

### Card 6: Add shell_path key to plugin template mill-config.yaml

- **Context:**
  - `mill-config.yaml`
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `plugins/mill/templates/mill-config.yaml`, locate the `llm.claude.psmux:`
  block (currently around line 105-107, containing `via_psmux: false` and
  `reuse_idle_timeout_s: 10`). Add a new line after `via_psmux`:
  ```yaml
      shell_path: pwsh  # Shell binary passed to new_session. Use the full path if pwsh on PATH is a broken stub (e.g. C:/Code/tools/powershell7/pwsh.exe on Windows machines with App Execution Alias disabled).
  ```
  The indentation must match the existing keys in that block (4 spaces).
- **Commit:** `feat(templates/mill-config): add llm.claude.psmux.shell_path key`

### Card 7: Set shell_path in hub mill-config.yaml

- **Context:**
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:**
  - `mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `mill-config.yaml`, locate the `llm:` → `claude:` → `psmux:` block
  (currently around lines 9-11, containing `via_psmux: false`). Add after
  `via_psmux: false`:
  ```yaml
      shell_path: "C:/Code/tools/powershell7/pwsh.exe"
  ```
  This is the site-specific absolute path confirmed working during investigation.
  The indentation must match `via_psmux` in that file.
- **Commit:** `fix(mill-config): set shell_path to working pwsh path`

## Batch Tests

Pure YAML edits. No runnable test surface at this layer — the reading code
(`_resolve_shell_path()`) is exercised by `test-claude-sub.py` in Batch 4.
`verify: null` is correct here.
