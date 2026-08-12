# Plan: CLAUDE_PLUGIN_ROOT environment variable not exported to Bash tool

```yaml
task: "CLAUDE_PLUGIN_ROOT environment variable not exported to Bash tool"
slug: "claude-plugin-root-env-setup"
approved: true
started: "20260812-180207"
parent: "main"
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: plugin-root-resolution
    file: 01-plugin-root-resolution.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py
```

## Shared Decisions

### Decision: resolve plugin root by scanning `sys.path`, not `os.environ`

- **Decision:** Both the Phase 4.8 `MILL_PYTHON`-write snippet and its verify snippet in
  `mill-setup/SKILL.md` derive the plugin root by scanning `sys.path` for the first entry whose
  directory name is `scripts` and returning its parent, via a new `_config.resolve_plugin_root_from_syspath`
  helper — instead of reading `os.environ['CLAUDE_PLUGIN_ROOT']` directly.
- **Rationale:** `$CLAUDE_PLUGIN_ROOT` is reliably available only as literal template-substituted
  text inside SKILL.md-sourced Bash command strings, not reliably available as a real inherited OS
  env var to the Python subprocess it launches (confirmed empirically in the discussion round: the
  `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` prefix on the same command line is always correctly
  substituted by CC before the Bash tool executes, and CPython natively inserts every `PYTHONPATH`
  entry into `sys.path` at interpreter startup — including for `-c` invocations — so scanning
  `sys.path` never depends on `CLAUDE_PLUGIN_ROOT` surviving as a real env var). Two independent
  field reports (GitHub issues #811, #813) hit `ModuleNotFoundError` because Phase 4.8 was the one
  site in the codebase still reading `os.environ['CLAUDE_PLUGIN_ROOT']` directly, unlike
  `_config.resolve_plugin_template_path` and `_preflight.check_helpers`, which already tolerate its
  absence.
- **Applies to:** all batches (single batch in this plan).

## All Files Touched

- `plugins/mill/scripts/_config.py`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/unit_tests/test-config.py`
