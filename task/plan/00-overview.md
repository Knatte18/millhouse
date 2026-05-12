# Plan: Replace uv-run-project with direct venv Python in SKILL.md invocations

```yaml
task: Replace uv-run-project with direct venv Python in SKILL.md invocations
slug: skills-direct-venv-invocation
approved: false
started: 20260512-141739
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: bulk-skill-conversion
    file: 01-bulk-skill-conversion.md
    depends-on: []
    verify: null
  - number: 2
    name: mill-go-conversion
    file: 02-mill-go-conversion.md
    depends-on: []
    verify: null
  - number: 3
    name: mill-setup-and-claudemd
    file: 03-mill-setup-and-claudemd.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: invocation-form

- **Decision:** Cache-form invocations of mill Python scripts in SKILL.md bash blocks use the direct venv Python binary: `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"`. The PYTHONPATH prefix `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` is added universally for direct (top-level) calls.
- **Rationale:** The venv exists in the plugin cache; invoking the Python binary directly avoids uv's project-resolution and venv-presence-check overhead on every call. The PYTHONPATH prefix is needed because the Bash subshell does not reliably inherit the Windows user env var.
- **Applies to:** all batches

### Decision: nested-call-exception

- **Decision:** When a Python invocation appears AFTER `--` inside a `millpy-bg.py` launcher line, it MUST NOT carry the `PYTHONPATH="${...}/scripts"` shell prefix. The nested form is `"$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/..."` (or the `${CLAUDE_PLUGIN_ROOT}` equivalent) with no PYTHONPATH= prefix.
- **Rationale:** Tokens after `--` are passed as argv to `subprocess.run` inside the millpy-bg worker — not parsed as shell env-assignment. If the prefix is included, the subprocess tries to exec a binary named `PYTHONPATH=…` and fails. The outer launcher already set PYTHONPATH in the process environment; it is inherited automatically through launcher → worker → subprocess.
- **Applies to:** all batches

### Decision: source-tree-forms-untouched

- **Decision:** Invocations using `uv run --project plugins/mill ...` (source-tree paths) are NOT converted in any batch. They remain as `uv run --project plugins/mill plugins/mill/scripts/millpy-X.py` and `PYTHONPATH="plugins/mill/scripts" uv run --project plugins/mill python -c "..."`.
- **Rationale:** Source-tree forms are the documented exception in CLAUDE.md. They run from the millhouse repo itself where the venv may not have been created yet; `uv run` creates it on demand.
- **Applies to:** all batches

### Decision: variable-form-normalisation

- **Decision:** When converting a line that uses `"$CLAUDE_PLUGIN_ROOT"` without braces, normalise to `"${CLAUDE_PLUGIN_ROOT}"` (with braces) as part of the same edit. Do not normalise braces on lines that are not being converted.
- **Rationale:** Mixing `"$CLAUDE_PLUGIN_ROOT"` and `"${CLAUDE_PLUGIN_ROOT}"` in the same file is inconsistent. Since the line is being rewritten anyway, normalising costs nothing.
- **Applies to:** all batches

### Decision: windows-only-venv-path

- **Decision:** The direct Python binary path is hardcoded as `.venv/Scripts/python.exe` (Windows convention). No cross-platform OS detection or fallback to `.venv/bin/python`.
- **Rationale:** All mill operators run Windows 11. Adding OS detection adds boilerplate to every line for a hypothetical Linux/Mac operator.
- **Applies to:** all batches

## All Files Touched

- `CLAUDE.md`
- `plugins/mill/skills/mill-abandon/SKILL.md`
- `plugins/mill/skills/mill-add/SKILL.md`
- `plugins/mill/skills/mill-autofix/SKILL.md`
- `plugins/mill/skills/mill-claim/SKILL.md`
- `plugins/mill/skills/mill-cleanup/SKILL.md`
- `plugins/mill/skills/mill-color/SKILL.md`
- `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-groom/SKILL.md`
- `plugins/mill/skills/mill-inspect/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-resume/SKILL.md`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/skills/mill-skills-from-scripts/SKILL.md`
- `plugins/mill/skills/mill-skills-index/SKILL.md`
- `plugins/mill/skills/mill-spawn/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/skills/mill-status/SKILL.md`
- `plugins/mill/skills/mill-terminal/SKILL.md`
- `plugins/mill/skills/mill-vscode/SKILL.md`
- `plugins/mill/skills/mill-wiki-push/SKILL.md`
