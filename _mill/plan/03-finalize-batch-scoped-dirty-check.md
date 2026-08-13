# Batch: finalize-batch-scoped-dirty-check

```yaml
task: 'mill-spawn, millpy-implement, _cleanliness, discussion-review: small bugs and inconsistencies'
batch: finalize-batch-scoped-dirty-check
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
depends-on: []
```

## Batch Scope

Fixes GitHub issue #825: `_implementer_common._in_scope_dirty_stuck` (the per-batch finalize dirty-tree gate) currently calls `_cleanliness.compute_terminal_dirt`, whose owned-paths scope is task-wide (`task_dir` subtree ∪ the whole task's parent-diff-owned paths). This means a prior, already-approved batch's committed file (e.g. `_mill/briefs/<batch>.out.md`) falls within scope, so if it becomes dirty again post-commit for any reason unrelated to the current batch, the current batch's finalize incorrectly false-blocks. The fix re-scopes this one gate to the current batch's own range: owned paths become `git diff --name-only <start_sha>` (a working-tree diff against the batch's own start commit, not a commit-range log/rev-list — this still catches uncommitted current-batch dirt, not just committed changes), intersected with `git status --porcelain` dirt. `compute_terminal_dirt` itself is untouched and remains the authoritative task-wide gate used by mill-go's separate terminal (task-completion) cleanliness check (see batch 4 / #818 for that gate's own unrelated fix).

External interface: `_in_scope_dirty_stuck`'s signature gains one new parameter (`start_sha`); its single call site is updated in the same card. No other module imports this function. Self-contained batch.

## Cards

### Card 5: re-scope `_in_scope_dirty_stuck` to `start_sha`-based batch ownership

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. Add `import _pygit2_util` to the module-level import block (`plugins/mill/scripts/_implementer_common.py:3-14`), in alphabetical order between `import _cleanliness` (line 11) and `import _status` (line 12).
  2. Replace `_in_scope_dirty_stuck`'s signature (currently `plugins/mill/scripts/_implementer_common.py:416-421`) to add a fifth parameter `start_sha: str | None` after `session_id: str | None`:
     ```python
     def _in_scope_dirty_stuck(
         project_root: Path,
         task_dir: Path | None,
         parent_branch: str | None,
         session_id: str | None,
         start_sha: str | None,
     ) -> dict | None:
     ```
  3. Replace the function's disable-guard (currently `if task_dir is None or parent_branch is None: return None` at line 445) with:
     ```python
     if task_dir is None or parent_branch is None or start_sha is None:
         return None
     ```
     `task_dir` and `parent_branch` remain required guard inputs even though the owned-paths computation below no longer derives from them directly — this is the discussion's explicit decision (extend the existing guard, do not replace it), so do not remove these two parameters as apparently-unused cleanup.
  4. Replace the function body between the guard and the final `if dirt:` block (currently lines 448-455, the `try: dirt = _cleanliness.compute_terminal_dirt(...) except Exception: return None` block) with:
     ```python
     try:
         diff_result = _subprocess_util.run(
             ["git", "diff", "--name-only", start_sha],
             cwd=project_root,
         )
         if diff_result.returncode != 0:
             return None
         owned_paths = {line for line in diff_result.stdout.splitlines() if line}
         porcelain_lines = _pygit2_util.status_porcelain(project_root, include_untracked=False)
         dirt = [line for line in porcelain_lines if line[3:] in owned_paths]
     except Exception:
         # Any failure (including GitOpsError on non-git paths, e.g. test fixtures) is a
         # safe no-op; the mill-go 2b cleanliness gate is authoritative.
         return None
     ```
     `porcelain_lines` entries are `"XY path"` strings (2-char status code + space + path), matching the same `line[3:]` slicing convention `_cleanliness._filter_to_task_scope` already uses for the same porcelain format.
  5. The trailing `if dirt: return {...}` / `return None` block (lines 457-464) is unchanged.
  6. Update the function's docstring (lines 422-442) to describe the new `start_sha`-based scope instead of `compute_terminal_dirt`, and to document the new `start_sha` parameter and its `None`-disables-the-gate behavior. Explain the "unlike `compute_terminal_dirt`, this gate deliberately drops `task_dir`'s blanket subtree inclusion" distinction so a future reader does not "fix" this function to match `compute_terminal_dirt`'s broader scope.
  7. Update the call site (`plugins/mill/scripts/_implementer_common.py:1758-1760`, currently `_dirty_result = _in_scope_dirty_stuck(project_root, task_dir, parent_branch, _gate_session_id)`) to pass `start_sha` (the enclosing function's own `start_sha` parameter, already in scope and used earlier in the same function at lines 1697, 1721, and 1743) as the fifth positional argument:
     ```python
     _dirty_result = _in_scope_dirty_stuck(
         project_root, task_dir, parent_branch, _gate_session_id, start_sha
     )
     ```
- **Commit:** `fix(implementer-common): scope per-batch dirty-tree gate to start_sha, not task-wide parent-diff (#825)`

### Card 6: regression tests for the batch-scoped dirty-tree gate

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `README.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add three new numbered cases to `main()` in `test-implementer-common.py`, inserted immediately before the `if errors:` block that closes `main()` (after existing Case 72e, which ends right before that block). Follow the file's existing `# Case N:` inline-block convention exactly (see Case 57 at line 3156 for the closest existing precedent — it already exercises `_in_scope_dirty_stuck` via `_forward_output` with `task_dir`/`parent_branch`/`start_sha` kwargs).

  - **Case 73** (the core #825 regression — negative case): using `_setup_fixture(project_root)` for the base commit, then commit a change to `_mill/briefs/prior.out.md` (create `_mill` dir, write the file, `git add`, `git commit -m "prior batch commit"`) to simulate an already-approved prior batch; capture that commit's SHA via `git rev-parse HEAD` as `batch_start_sha` (this is the CURRENT batch's `start_sha` — everything up to and including the prior batch's own commit predates it). Then dirty `_mill/briefs/prior.out.md` again in the working tree WITHOUT committing (simulating the prior batch's file being re-dirtied post-commit for reasons unrelated to the current batch). Call `_forward_output` with `start_sha=batch_start_sha`, `task_dir=project_root / "_mill"`, `parent_branch=<the branch _setup_fixture leaves checked out>`, and a `'{"status":"success","commit_sha":"abc","session_id":"case73"}'` agent-output JSON line. Assert the resulting `status` is `"success"` (the gate must NOT fire — `prior.out.md`'s only commit predates `batch_start_sha`, so it is out of the current batch's `git diff --name-only batch_start_sha` scope even though it is dirty). Contrast this explicitly in a comment with the pre-fix behavior (would have false-blocked via `compute_terminal_dirt`'s task-wide `_mill/` blanket inclusion).
  - **Case 74** (positive case — never-committed dirt since `start_sha` still fires): using `_setup_fixture(project_root)` for `base_sha`, dirty the already-tracked `README.md` (written by `_setup_fixture`) in the working tree WITHOUT any commit since `base_sha`. Call `_forward_output` with `start_sha=base_sha`, `task_dir=project_root / "_mill"` (create the empty dir first), `parent_branch=<current branch>`. Assert `status == "stuck"` and `stuck_type == "logic"` and the reason mentions `README.md` — proving `git diff --name-only <start_sha>` (a working-tree diff, not a commit-range diff) catches uncommitted dirt with zero commits since `start_sha`, matching the Decision's explicit rejection of a pure `git log`/`git rev-list` owned-paths source.
  - **Case 75** (`start_sha=None` disables the gate): reuse `_setup_fixture` and dirty a tracked file, but call `_forward_output` with `start_sha=None` explicitly alongside `task_dir`/`parent_branch` both non-`None`. Assert the dirty-tree gate does not fire (either `status == "success"`, or if some earlier gate in `_forward_output`'s pipeline would independently demote for an unrelated reason, assert specifically that the returned `reason` — when `stuck_type == "logic"` — does NOT contain `"in-scope working tree dirty"`, proving the dirty-tree gate itself is disabled rather than coincidentally not firing). This mirrors the file's existing `task_dir is None or parent_branch is None` disable-guard test coverage pattern for this same function, extended to the new parameter.

  Note that existing Case 57 (line 3156) already covers the "file committed since `start_sha`, then dirtied again" positive scenario referenced in the discussion's Testing plan — no new case is needed for that sub-scenario; its assertions remain valid unchanged after Card 5's fix because `README.md` in that fixture is committed strictly after `base_sha`/`start_sha`, so it is within `git diff --name-only start_sha` scope exactly as it was within the old parent-diff scope.
- **Commit:** `test(implementer-common): regression coverage for start_sha-scoped dirty-tree gate (#825)`

## Batch Tests

`verify:` runs `test-implementer-common.py` directly (single file). Cases 73-75 cover the negative (false-block fixed) case, the never-committed-dirt positive case, and the `start_sha=None` disable-guard; Case 57 (pre-existing) already covers the committed-then-dirtied positive case and continues to pass unmodified.
