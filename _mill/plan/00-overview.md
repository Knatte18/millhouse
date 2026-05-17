# Plan: mill-go self-modifying repo + absent worktree venv silently uses stale scripts

```yaml
task: 'mill-go: self-modifying repo + absent worktree venv silently uses stale scripts'
slug: self-modifying-repo-venv
approved: true
started: 20260517-111018
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: mill-go-self-modifying-venv
    file: 01-mill-go-self-modifying-venv.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: edit-target-is-skill-md-only

- **Decision:** The entire task is a documentation/orchestration edit to `plugins/mill/skills/mill-go/SKILL.md` Step 0. No Python source, no new helpers, no test files.
- **Rationale:** `_mill/discussion.md` `## Scope` names exactly this surface and explicitly lists out-of-scope alternatives (helper extraction, `millpy-spawn` changes, sibling-skill auto-sync).
- **Applies to:** all batches

### Decision: subshell-cd-pattern

- **Decision:** All `uv sync` invocations inside the bash block use the subshell pattern `(cd "$WORKTREE_ROOT" && uv sync --project plugins/mill)`. The outer shell never executes a bare `cd`.
- **Rationale:** Mandated by `_mill/discussion.md` `### uv-sync-invocation` and `## Constraints`. The outer shell's cwd must be preserved for the subsequent `git rev-parse` and Python invocations in Step 0; the subshell isolates the cwd change to the `uv sync` process only.
- **Applies to:** all batches

### Decision: halt-on-sync-failure

- **Decision:** When `uv sync` exits non-zero, mill-go halts with `exit 1` and a clear stderr message that names the worktree path and tells the operator to run `uv sync --project plugins/mill` manually and re-run `/mill-go`. No fallback to cache.
- **Rationale:** `_mill/discussion.md` `### halt-on-sync-failure`. The bug being fixed is silent fall-through to stale cache code; warn-and-continue equals the current broken behaviour.
- **Applies to:** all batches

### Decision: idempotency-via-binary-presence-check

- **Decision:** The new bash block skips `uv sync` when `${WORKTREE_PLUGIN_ROOT}/.venv/Scripts/python.exe` already exists. Sync runs only when that binary is absent.
- **Rationale:** `_mill/discussion.md` `### idempotency`. mill-go is invoked frequently; the python.exe binary's presence is a sufficient proxy for "venv initialized" without paying the ~1-2s sync cost on every invocation against an unchanged venv.
- **Applies to:** all batches

### Decision: branch-restructure-to-single-if

- **Decision:** Collapse the current two-branch `if`/`elif` Step 0 block into one `if [ -d "$WORKTREE_PLUGIN_ROOT" ]` branch. Inside that branch, sync if the venv binary is missing, then unconditionally promote `PLUGIN_ROOT` and `MILL_PYTHON` to worktree paths.
- **Rationale:** `_mill/discussion.md` `### branch-restructure`. After auto-sync the venv is guaranteed (or mill-go halted), so the `elif` "venv absent" case ceases to exist as a distinct path.
- **Applies to:** all batches

### Decision: ascii-only-stderr

- **Decision:** All stderr/stdout strings introduced by this edit use ASCII only -- the dash sequence ` -- ` instead of an em-dash, no emojis, no smart quotes.
- **Rationale:** `_mill/discussion.md` `## Constraints` cites the project-wide rule (Windows cp1252 terminals crash on non-ASCII stdout/stderr; see CLAUDE.md).
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/skills/mill-go/SKILL.md`
