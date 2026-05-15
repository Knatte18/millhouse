# Batch: mill-go-skill

```yaml
task: 56 (A) -- Fix mill-go/start/plan/merge runtime behavioral bugs
batch: mill-go-skill
number: 3
cards: 3
verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Three targeted edits to `plugins/mill/skills/mill-go/SKILL.md`. Card 5 fixes PLUGIN_ROOT resolution so self-modifying millhouse tasks use the task worktree's local scripts instead of the cache (#283). Card 6 adds a terminal cleanliness gate to the Handoff section before `phase: done` is appended (#282 Gap 2). Card 7 corrects the Resume section to use fresh-retry (no `--resume`) for `state:running` batches (#290). All three edits are surgical prose changes inside their respective sections; no surrounding text is reformatted.

## Cards

### Card 5: mill-go Entry Step 0 -- PLUGIN_ROOT override for self-modifying repos

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `mill-go/SKILL.md`, Section `## Entry`, subsection `**Step 0: Resolve PLUGIN_ROOT.**`: after the existing code block that sets `PLUGIN_ROOT` and `MILL_PYTHON`, add the following text and code block:

  ```
  After setting `PLUGIN_ROOT`, check whether the task worktree contains a local copy of the mill plugin with an initialised venv:

  ```bash
  WORKTREE_PLUGIN_ROOT="$(git rev-parse --show-toplevel)/plugins/mill"
  WORKTREE_VENV="${WORKTREE_PLUGIN_ROOT}/.venv/Scripts/python.exe"
  if [ -d "$WORKTREE_PLUGIN_ROOT" ] && [ -f "$WORKTREE_VENV" ]; then
      PLUGIN_ROOT="$WORKTREE_PLUGIN_ROOT"
      MILL_PYTHON="$WORKTREE_VENV"
      echo "[mill-go] NOTE: self-modifying repo detected; PLUGIN_ROOT overridden to $PLUGIN_ROOT"
  elif [ -d "$WORKTREE_PLUGIN_ROOT" ]; then
      echo "[mill-go] SKIP: self-modifying repo but worktree venv absent -- using cache. Run 'uv sync --project ${WORKTREE_PLUGIN_ROOT}' to enable."
  fi
  ```

  Both `PLUGIN_ROOT` and `MILL_PYTHON` are updated together only when the worktree venv exists. If `plugins/mill/` is present but `.venv` is absent (common in fresh task worktrees where `.venv` is gitignored), the cache path is used and a skip message is logged. For non-millhouse repos the entire block is a no-op. The existing `Use $PLUGIN_ROOT in place of $CLAUDE_PLUGIN_ROOT for all subsequent uv run commands in this skill.` note below the Step 0 block remains unchanged.
- **Commit:** `fix(mill-go): override PLUGIN_ROOT to worktree-local scripts for self-modifying repos (#283)`

### Card 6: mill-go Handoff -- terminal cleanliness gate

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `mill-go/SKILL.md`, locate the `## Handoff` section (or the step that appends `phase: done` / transitions the task to done). Before the step that calls `_status.append_phase(status_path, "done", ...)` or transitions to `phase: done`, insert a new step:

  **Terminal cleanliness gate:** run `git -C <worktree> status --porcelain --untracked-files=no`. If the output is non-empty (any tracked files have uncommitted modifications), halt with:
  `BLOCKED: dirty working tree at task completion -- <N> file(s) uncommitted: <file-list>. Commit or discard before proceeding.`
  where `<N>` is the count of dirty lines and `<file-list>` is the filenames extracted from the porcelain output. Do NOT set `phase: done` when the gate fires; the task remains in its current phase so the operator can inspect and fix.

  If the output is empty, proceed normally to the `phase: done` transition.

  This gate catches uncommitted implementer work that survived all per-batch cleanliness checks (e.g. pre-batch dirt that was invisible to the snapshot-diff gate).
- **Commit:** `fix(mill-go): add terminal cleanliness gate before phase:done (#282-gap2)`

### Card 7: mill-go Resume -- state:running uses fresh-retry

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `mill-go/SKILL.md`, Section `## Resume`, subsection for `state == "running"`: replace the current invocation that uses `--resume`:

  Current (wrong):
  ```bash
  PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-bg.py" \
      --slug implement-<batch_name>-resume -- \
      "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name> --resume
  ```

  Replace with (fresh-retry, no `--resume`):
  ```bash
  PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-bg.py" \
      --slug implement-<batch_name>-resume -- \
      "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name>
  ```

  Update the prose explanation below this block. The old explanation reads: "The CLI re-attaches the warm session via the stored `implementer_session`." Replace it with: "The interrupted implementer session is dead and cannot be re-attached. A fresh batch start is the correct recovery: the CLI re-initialises state -> running, captures a new snapshot, and spawns a fresh implementer session. After parsing the report, continue at Execute step 2b (cleanliness gate)."

  No other changes to the Resume section. The `state == "reviewing"` and `state == "fixing"` paths remain unchanged.
- **Commit:** `fix(mill-go): use fresh-retry for state:running in Resume section (#290)`

## Batch Tests

The verify command `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` serves as a regression check. The SKILL.md prose changes have no automated test coverage; correctness is verified by code review.
