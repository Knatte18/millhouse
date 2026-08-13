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
- **Requirements:** Add three new numbered cases to `main()` in `test-implementer-common.py`, inserted immediately before the `if errors:` block that closes `main()` (after existing Case 72e, which ends right before that block). Follow the file's existing `# Case N:` inline-block convention exactly (see Case 57 at line 3156 for the closest existing precedent — it already exercises `_in_scope_dirty_stuck` via `_forward_output` with `task_dir`/`parent_branch`/`start_sha` kwargs). `parent_branch` is now an inert guard input for this function (per Card 5) — pass the literal string `"main"` in every new case below; there is no need to query the fixture's actual checked-out branch name.

  **Gate-ordering constraint (applies to Cases 73 and 74):** `_forward_output` runs the no-content-commit gate (`_implementer_common.py:1697-1718`) BEFORE the dirty-tree gate. That gate fires whenever `git rev-parse HEAD == start_sha` (unless the only commit since `start_sha` is a `"mill-go: start batch"`-prefixed commit — see `_is_only_start_batch_commit`). Both new cases below therefore make an intervening commit, unrelated to the file being tested, strictly after capturing `start_sha`, so `HEAD != start_sha` and the no-content-commit gate never preempts the dirty-tree gate under test.

  - **Case 73** (the core #825 regression — negative case). The new `git diff --name-only <start_sha>` owned-paths set is a straight content comparison between `start_sha`'s tree and the current working tree — it has no notion of *when* a change happened, only *whether* current content differs from `start_sha`'s. A file that is dirty relative to `HEAD` is therefore excluded from owned-paths only when its current (dirty) content is byte-identical to what `start_sha`'s own tree already has for that path. Construct exactly this:
    1. `base_sha = _setup_fixture(project_root)`.
    2. Create `_mill/briefs/prior.out.md` with content `"content-A"`; `git add` + `git commit -m "prior batch commit"` (simulates an already-approved prior batch's commit).
    3. Capture `batch_start_sha = git rev-parse HEAD` (this commit) — the CURRENT batch's `start_sha`.
    4. Overwrite `_mill/briefs/prior.out.md` with content `"content-B"`; `git add` + `git commit -m "intervening commit"` (an unrelated, later commit — also satisfies the gate-ordering constraint above, since it is not `"mill-go: start batch"`-prefixed).
    5. Revert the working-tree copy back to exactly its `batch_start_sha` content: `git -C <project_root> checkout <batch_start_sha> -- _mill/briefs/prior.out.md`. This file is now flagged dirty by `git status --porcelain` (it differs from `HEAD`'s `"content-B"`) but is byte-identical to `batch_start_sha`'s own tree — exactly the "prior batch's committed file, touched again by later activity, currently reads back its earlier content" shape.
    6. Call `_forward_output('{"status":"success","commit_sha":"abc","session_id":"case73"}\n', project_root, start_sha=batch_start_sha, verify_cmd=None, task_dir=project_root / "_mill", parent_branch="main")`.
    7. Assert `status == "success"` — the dirty-tree gate does not fire, because `_mill/briefs/prior.out.md` does not appear in `git diff --name-only batch_start_sha` (empty output — verified: content matches exactly), so it is excluded from owned-paths despite `git status --porcelain` flagging it.
  - **Case 74** (positive case — never-committed dirt since `start_sha` still fires):
    1. `base_sha = _setup_fixture(project_root)`.
    2. Create `_mill/marker.txt` with any content; `git add` + `git commit -m "card-1 commit"` — an intervening commit unrelated to `README.md`, satisfying the gate-ordering constraint (`HEAD != base_sha`) without touching the file under test.
    3. Overwrite `README.md` (tracked since `base_sha`, untouched by the intervening commit) with new content, WITHOUT committing.
    4. Call `_forward_output('{"status":"success","commit_sha":"abc","session_id":"case74"}\n', project_root, start_sha=base_sha, verify_cmd=None, task_dir=project_root / "_mill", parent_branch="main")`.
    5. Assert `status == "stuck"`, `stuck_type == "logic"`, and `"README.md"` appears in the `reason` string — proving a file with only uncommitted changes since `start_sha` (never committed at all since then) still trips the gate, matching the Decision's explicit rejection of a pure `git log`/`git rev-list` owned-paths source.
  - **Case 75** (`start_sha=None` disables the gate): reuse `_setup_fixture` and dirty a tracked file, but call `_forward_output` with `start_sha=None` explicitly alongside `task_dir`/`parent_branch` both non-`None`. `start_sha=None` also disables the no-content-commit gate (guarded by the same `if start_sha is not None`), so no intervening commit is needed here. Assert `status == "success"` — with `start_sha=None`, `_in_scope_dirty_stuck` returns `None` immediately per its guard (Card 5), so the dirty-tree gate cannot fire regardless of the working tree's actual dirt. This mirrors the file's existing `task_dir is None or parent_branch is None` disable-guard test coverage pattern for this same function, extended to the new parameter.

  Note that existing Case 57 (line 3156) already covers the "file committed since `start_sha` by the CURRENT batch's own intervening commit, then dirtied again" positive scenario — no new case is needed for that sub-scenario; its assertions remain valid unchanged after Card 5's fix because `README.md` in that fixture is committed strictly after `base_sha`/`start_sha` by an on-branch commit and then dirtied to different content again, so it remains in `git diff --name-only start_sha` scope exactly as it was in the old parent-diff scope.
- **Commit:** `test(implementer-common): regression coverage for start_sha-scoped dirty-tree gate (#825)`

## Batch Tests

`verify:` runs `test-implementer-common.py` directly (single file). Cases 73-75 cover the negative (false-block fixed) case, the never-committed-dirt positive case, and the `start_sha=None` disable-guard; Case 57 (pre-existing) already covers the committed-then-dirtied positive case and continues to pass unmodified.
