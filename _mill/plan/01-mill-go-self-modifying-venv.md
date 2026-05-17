# Batch: mill-go-self-modifying-venv

```yaml
task: 'mill-go: self-modifying repo + absent worktree venv silently uses stale scripts'
batch: mill-go-self-modifying-venv
number: 1
cards: 1
verify: null
depends-on: []
```

## Batch Scope

This batch replaces the SKIP-branch in `plugins/mill/skills/mill-go/SKILL.md` Step 0 with auto-`uv sync` + halt-on-failure logic so that self-modifying tasks never fall through to stale cache code. The change is a single SKILL.md edit: replace the existing two-branch `if`/`elif` bash block at the top of Step 0 with a single-branch block that runs `uv sync` (in a subshell) when the worktree plugin venv binary is missing, halts on sync failure, and unconditionally promotes `PLUGIN_ROOT` + `MILL_PYTHON` to worktree paths. The prose paragraph immediately following the bash block is rewritten to reflect the new semantics (sync-or-halt, no fallback). No external interface for downstream batches because this batch is the entire plan.

## Cards

### Card 1: Replace mill-go Step 0 SKIP-branch with auto-`uv sync` and rewrite the following prose

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `plugins/mill/skills/mill-go/SKILL.md`, locate the second fenced bash block under the heading `## Entry` / `**Step 0: Resolve PLUGIN_ROOT.**` (the block that begins `WORKTREE_PLUGIN_ROOT="$(git rev-parse --show-toplevel)/plugins/mill"` and currently contains an `if`/`elif` pair: the `if` branch promotes `PLUGIN_ROOT`/`MILL_PYTHON` when the venv exists, the `elif` branch prints the SKIP message). Replace that **entire** bash block with the following single-branch form:

    ```bash
    WORKTREE_ROOT="$(git rev-parse --show-toplevel)"
    WORKTREE_PLUGIN_ROOT="${WORKTREE_ROOT}/plugins/mill"
    WORKTREE_VENV="${WORKTREE_PLUGIN_ROOT}/.venv/Scripts/python.exe"
    if [ -d "$WORKTREE_PLUGIN_ROOT" ]; then
        if [ ! -f "$WORKTREE_VENV" ]; then
            echo "[mill-go] self-modifying repo: worktree venv absent at ${WORKTREE_PLUGIN_ROOT}/.venv -- running 'uv sync --project plugins/mill'"
            (cd "$WORKTREE_ROOT" && uv sync --project plugins/mill) || {
                echo "[mill-go] HALT: uv sync failed in worktree ${WORKTREE_ROOT} -- cannot run self-modifying task with stale cache scripts. Run 'uv sync --project plugins/mill' manually and re-run /mill-go." >&2
                exit 1
            }
        fi
        PLUGIN_ROOT="$WORKTREE_PLUGIN_ROOT"
        MILL_PYTHON="$WORKTREE_VENV"
        echo "[mill-go] NOTE: self-modifying repo detected; PLUGIN_ROOT overridden to $PLUGIN_ROOT"
    fi
    ```

    Preserve verbatim: the exact 4-space indentation inside the outer `if`, the 8-space indentation inside the inner `if`, the subshell form `(cd "$WORKTREE_ROOT" && uv sync --project plugins/mill)`, the ASCII ` -- ` separator (no em-dash), and the redirection of the HALT message to stderr (`>&2`). The block contains no non-ASCII characters.
  - Rewrite the prose paragraph that **immediately follows** the replaced bash block (currently begins "Both `PLUGIN_ROOT` and `MILL_PYTHON` are updated together only when the worktree venv exists..." and explains the SKIP-branch semantics). Replace that paragraph with a paragraph that states three things in order: (1) when `plugins/mill/` is present in the worktree, the venv is guaranteed to be synced -- `uv sync --project plugins/mill` runs automatically on first detection of a missing `.venv/Scripts/python.exe`, and both `PLUGIN_ROOT` and `MILL_PYTHON` are then unconditionally overridden to worktree paths; (2) `uv sync` failure halts mill-go with `exit 1`; there is no fallback to the cache; (3) for non-millhouse repos (no `plugins/mill/` directory in the worktree), the block is a no-op. Keep the paragraph to ~3 sentences, ASCII-only, no em-dashes.
  - Leave **all other lines** in `plugins/mill/skills/mill-go/SKILL.md` unchanged. In particular: the preceding bash block that resolves `PLUGIN_ROOT` from `${CLAUDE_PLUGIN_ROOT}` (the block immediately above the one being replaced) is **not** touched; the trailing sentence "Use `$PLUGIN_ROOT` in place of `$CLAUDE_PLUGIN_ROOT` for all subsequent `uv run` commands in this skill." (currently at line 42) stays put.
  - The replacement must not introduce trailing whitespace on any line, and the final newline at end-of-file must be preserved.
- **Commit:** `fix(mill-go): auto-run 'uv sync' for self-modifying tasks when worktree venv is absent`

## Batch Tests

`verify: null`. This batch is a SKILL.md documentation/orchestration edit; no Python source changes and no automated test surface exercises SKILL.md bash blocks. Validation is by inspection (post-implementer review + holistic review) and by the manual scenarios already documented in `_mill/discussion.md` `## Testing` (happy path, idempotent path, failure path, no-op path). The four scenarios are operator-run after this task lands; they are out-of-scope for the implementer.
