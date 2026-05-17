# Plan: 59 (A) -- Small infra fixes batch 8

```yaml
task: 59 (A) -- Small infra fixes batch 8
slug: mill-misc-fixes-8
approved: false
started: '20260517-131402'
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: helper-api-additions
    file: 01-helper-api-additions.md
    depends-on: []
    verify: "C:/Code/millhouse/wts/millhouse/plugins/mill/.venv/Scripts/python.exe plugins/mill/unit_tests/test-status.py && C:/Code/millhouse/wts/millhouse/plugins/mill/.venv/Scripts/python.exe plugins/mill/unit_tests/test-paths.py"
  - number: 2
    name: validator-depends-on-cross-check
    file: 02-validator-depends-on-cross-check.md
    depends-on: []
    verify: "C:/Code/millhouse/wts/millhouse/plugins/mill/.venv/Scripts/python.exe plugins/mill/unit_tests/test-plan-validate.py"
  - number: 3
    name: merge-in-intent-aware
    file: 03-merge-in-intent-aware.md
    depends-on: []
    verify: null
  - number: 4
    name: test-vscode-processes-skip
    file: 04-test-vscode-processes-skip.md
    depends-on: []
    verify: "C:/Code/millhouse/wts/millhouse/plugins/mill/.venv/Scripts/python.exe plugins/mill/unit_tests/test-vscode-processes.py"
  - number: 5
    name: skill-and-docs-prose
    file: 05-skill-and-docs-prose.md
    depends-on: [1, 2]
    verify: null
```

## Shared Decisions

### Decision: ASCII-only output

- **Decision:** All new `print()` / `_log()` strings use plain ASCII (`-`, `--`, `->`). Em-dash and right-arrow Unicode characters are forbidden in stdout/stderr lines per CLAUDE.md `## Conventions worth carrying`.
- **Rationale:** Windows cp1252 terminals crash on non-ASCII stdout.
- **Applies to:** all batches.

### Decision: ${CLAUDE_PLUGIN_ROOT} in SKILL.md and shell commands

- **Decision:** Any intra-plugin path written in a SKILL.md or shell command uses `${CLAUDE_PLUGIN_ROOT}`. Never hardcode `plugins/mill/...` (the source tree).
- **Rationale:** External repos run mill from the plugin cache; source-tree paths break those installs.
- **Applies to:** Batch 5 (the SKILL.md edits).

### Decision: tests run with `uv run --project plugins/mill`

- **Decision:** Unit tests added or extended in this plan invoke via `uv run --project plugins/mill python plugins/mill/unit_tests/<name>.py`. Tests live in `plugins/mill/unit_tests/` and follow the existing in-memory / `tempfile` fixture convention.
- **Rationale:** Matches every existing test in the repo; the `verify:` commands in this overview already use the source-tree venv form.
- **Applies to:** Batches 1, 2, 4.

### Decision: phase-locked-fold rule applies; this task is `[active]`

- **Decision:** This plan is committed at the start of mill-go. Any scope addition via `/mill-fold` or `/mill-ghissues-to-tasks` is forbidden once the phase locks (per CLAUDE.md `_tasks_md.LOCKED_FOLD_PHASES`).
- **Rationale:** Scope creep against a frozen plan invalidates the DAG. Already enforced by the wiki tooling; restated here as a Shared Decision so the implementer does not attempt mid-flight fold-ins.
- **Applies to:** all batches.

### Decision: codeguide-update fires per-card commit

- **Decision:** Implementer's `git-commit` skill invokes `codeguide-update` on every per-card commit so docs stay in step with the code.
- **Rationale:** Existing convention from `git-commit.md` / `git-workflow.md`.
- **Applies to:** all batches.

## All Files Touched

- `.claude-plugin/marketplace.json`
- `CLAUDE.md`
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/merge-in-conflict-brief.md`
- `plugins/mill/unit_tests/test-paths.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-status.py`
- `plugins/mill/unit_tests/test-vscode-processes.py`
- `update-plugins.ps1`
