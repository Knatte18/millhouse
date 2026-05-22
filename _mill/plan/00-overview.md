# Plan: Set MILL_PYTHON via mill-setup, use in all skill invocations

```yaml
task: Set MILL_PYTHON via mill-setup, use in all skill invocations
slug: mill-python-env-var
approved: true
started: 20260522-071246
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: mill-setup bootstrap
    file: 01-mill-setup-bootstrap.md
    depends-on: []
    verify: null
  - number: 2
    name: CLAUDE.md updates
    file: 02-claude-md-updates.md
    depends-on: []
    verify: null
  - number: 3
    name: skill replace heavy
    file: 03-skill-replace-heavy.md
    depends-on: []
    verify: null
  - number: 4
    name: skill replace remaining
    file: 04-skill-replace-remaining.md
    depends-on: []
    verify: null
  - number: 5
    name: verify
    file: 05-verify.md
    depends-on: [1, 2, 3, 4]
    verify: null
```

## Shared Decisions

### Decision: replacement-scope

- **Decision:** `plugins/mill/skills/mill-setup/SKILL.md` keeps the full `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"` form in all its Bash commands. All other SKILL.md files replace that string with `"$MILL_PYTHON"`. CLAUDE.md files get targeted text edits (not a blanket replacement).
- **Rationale:** mill-setup is the bootstrapper that WRITES `MILL_PYTHON` to `~/.claude/settings.json`. On a fresh machine the env var does not exist when mill-setup first runs; using `$MILL_PYTHON` in its own commands would fail silently.
- **Applies to:** all batches

### Decision: replacement-mechanism

- **Decision:** Use the Edit tool with `replace_all: true`, `old_string: '"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"'`, `new_string: '"$MILL_PYTHON"'` for each non-mill-setup SKILL.md file.
- **Rationale:** The exact quoted string `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"` appears identically in every command block. A single `replace_all` per file handles all occurrences without requiring the implementer to locate each line individually.
- **Applies to:** batches 3, 4

### Decision: worktree-paths

- **Decision:** All file edits target paths within the task worktree `c:\Code\millhouse\wts\mill-python-env-var\`. The user CLAUDE.md is at the absolute path `C:\Users\hanf\.claude\CLAUDE.md`.
- **Rationale:** The task worktree is a full checkout of the millhouse repo; the file tree mirrors the hub.
- **Applies to:** all batches

## All Files Touched

- `CLAUDE.md`
- `plugins/mill/skills/git-commit/SKILL.md`
- `plugins/mill/skills/mill-abandon/SKILL.md`
- `plugins/mill/skills/mill-add/SKILL.md`
- `plugins/mill/skills/mill-autofix/SKILL.md`
- `plugins/mill/skills/mill-claim/SKILL.md`
- `plugins/mill/skills/mill-cleanup/SKILL.md`
- `plugins/mill/skills/mill-color/SKILL.md`
- `plugins/mill/skills/mill-fold/SKILL.md`
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
- `C:\Users\hanf\.claude\CLAUDE.md`
