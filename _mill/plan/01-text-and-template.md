# Batch: text-and-template

```yaml
task: mill-go / mill-merge / plan-validator follow-up bugs (round 2)
batch: text-and-template
number: 1
cards: 3
verify: null
depends-on: []
```

## Batch Scope

This batch fixes three bugs that require only prose edits to SKILL.md files and one template file: moving the `commit_sha` write in mill-go past the cleanliness gate (#397), adding worktree-scripts detection and an ImportError fallback to mill-merge step 6 (#402), and extending the merge-in-conflict-brief template with UD-conflict detection instructions (#399). No Python code changes; no tests.

## Cards

### Card 1: mill-go SKILL.md — move commit_sha write to after cleanliness gate (#397)

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `plugins/mill/skills/mill-go/SKILL.md`, under `### 2. Parse implementer report`, locate and remove the sentence "Record `commit_sha` from a successful report on the batch entry." (it currently appears as the last line of step 2, just before `### 2b. Cleanliness gate`).

  Then, in `### 2b. Cleanliness gate`, locate the paragraph starting "If the returned list is empty, invoke the per-batch cleanup block". Insert the following sentence after the per-batch-cleanup-block sentence and before the "Then continue to..." phrase: `Record \`commit_sha\` via \`_status.set_batch_field(status_path, batch_name, "commit_sha", <sha from JSON report>)\`.`

  The resulting step-2b "empty list" paragraph must read (in order): (1) invoke the per-batch cleanup block, (2) record commit_sha, (3) then continue to step 3.

  Do not alter any other step-2 or step-2b text.
- **Commit:** `fix(mill-go): move commit_sha write to after cleanliness gate (#397)`

### Card 2: mill-merge SKILL.md — worktree scripts detection for step 6 (#402)

- **Context:**
  - `plugins/mill/scripts/_archive_tag.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `plugins/mill/skills/mill-merge/SKILL.md`, find `### 6. Archive tag`. The existing code block starts with `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "...`. Replace the entire bash code block for step 6 with the following (verbatim):

  ```bash
  # Prefer worktree scripts when available (handles cache-lag in self-modifying repos)
  if [ -f "$(git rev-parse --show-toplevel)/plugins/mill/scripts/_archive_tag.py" ]; then
      MILL_SCRIPTS="$(git rev-parse --show-toplevel)/plugins/mill/scripts"
  else
      MILL_SCRIPTS="${CLAUDE_PLUGIN_ROOT}/scripts"
  fi
  PYTHONPATH="$MILL_SCRIPTS" "$MILL_PYTHON" -c "
  from pathlib import Path
  import _paths
  try:
      import _archive_tag
  except ImportError as e:
      raise SystemExit(f'[mill-merge] step 6 failed: {e}. Cache may be stale -- run: uv sync --project plugins/mill')
  worktree = _paths.resolve_git_root()
  result = _archive_tag.create_or_resolve(worktree, '<slug>', '$CHILD_BRANCH')
  print(f'[mill-merge] archive-tag action: {result[\"action\"]} -- tag: {result[\"tag\"]}')
  if result['moved_aside_to']:
      print(f'[mill-merge] prior tag preserved as {result[\"moved_aside_to\"]}')
  "
  ```

  Keep the description paragraph that follows ("Idempotently tags the cleanup-commit tip...") unchanged.
- **Commit:** `fix(mill-merge): use worktree scripts for step 6; add ImportError fallback (#402)`

### Card 3: merge-in-conflict-brief.md — UD conflict detection (#399)

- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/templates/merge-in-conflict-brief.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `plugins/mill/templates/merge-in-conflict-brief.md`, find the current instruction 5 which begins "For modify/delete (DU) conflicts:". After that instruction, add a new instruction 6 (keeping the numbered list style):

  ```
  6. For UD conflicts — files this branch **modified** that the parent branch **deleted**: do not silently keep the modification. Instead:
     a. Run `git log --diff-filter=D --oneline MERGE_HEAD -- <file>` to find the deletion commit on the parent.
     b. Run `git show <deletion-commit>` to inspect context.
     c. If the deletion commit message mentions a replacement file (e.g. "replaced by", "moved to", "consolidated into"), or the commit also adds a file in the same directory with overlapping content: stage the deletion — `git -C <PROJECT_ROOT> rm <file>`.
     d. If detection is inconclusive: report `{"status":"stuck","stuck_type":"logic","reason":"modify/delete conflict on <file>: cannot determine if parent deletion is a replacement -- operator must decide"}` and halt. Do NOT silently keep the modification.
  ```

  No other lines in the file should change.
- **Commit:** `fix(merge-in-conflict-brief): add UD-conflict detection and replacement check (#399)`

## Batch Tests

`verify: null` — all changes are prose (SKILL.md files and one template). There is no runnable test surface; correctness is verified by the plan reviewer and the code reviewer reading the edited text.
