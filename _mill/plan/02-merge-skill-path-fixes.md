# Batch: merge-skill-path-fixes

```yaml
task: Fix nested-hub path resolution and SKILL.md vs shipped-API mismatches
batch: merge-skill-path-fixes
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skill-helper-drift.py
depends-on: [1]
```

## Batch Scope

Delivers the genuinely-open fixes (#497, #506) as prose edits to two SKILL.md files:
`mill-merge/SKILL.md` (config load, Path Setup hub resolution, squash safety) and
`mill-merge-in/SKILL.md` (entry step 2 + verify-replay path resolution). These are the nested-hub
path-resolution and parent-status-deletion fixes. There is no runtime unit test for SKILL prose;
the batch `verify:` re-runs the drift-guard test from batch 1 to confirm that every `_<module>.<fn>(`
reference introduced by these edits resolves to a shipped helper (all helpers used here already
exist). The behavioral validation of the squash-safety edit lives in batch 3's integration test,
which is why batch 3 depends on this batch. Depends on batch 1 because the `verify:` test must exist.
Batch-local decisions: see the overview's "hub resolution" and "config load" Shared Decisions —
mill-merge uses `resolve_active_hub`; mill-merge-in uses `resolve_hub_path`.

## Cards

### Card 3: mill-merge Step 1 — load config via _config.load_config, not the obsolete wiki config.yaml

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In mill-merge `## Steps` "Step 1 — Resolve mode + load config" (the paragraph
  currently reading "Load the deep-merged config: read `<wiki_path>/config.yaml` and overlay
  `<git_root>/.millhouse/config.local.yaml` if present (same deep-merge pattern used elsewhere)"),
  replace the obsolete wiki-config instruction with the canonical helper:
  `cfg = _config.load_config(_paths.resolve_hub_path(), git_root)`. Use **`_config.load_config`**
  specifically — its signature is `load_config(hub_root, worktree_root)`, so arg1 is the hub
  (`resolve_hub_path()`) and arg2 is the worktree git root (`git_root`); arg2 is where it reads the
  `.millhouse/config.local.yaml` stub. Do NOT use `_review_common.load_config` — that is a different
  function whose arg2 is a `.millhouse` directory (`hub/".millhouse"`), and mixing the two arg
  conventions silently misreads config. (mill-go Entry step 3 happens to call the `_review_common`
  variant; do not copy its argument shape here — match `_config.load_config`'s own signature, which
  mill-start Entry step 3 uses.) Keep the rest of Step 1 (the `_marker.task_data` call,
  `_inplace.is_inplace`, mode selection) unchanged. Do not introduce an absolute path; intra-plugin
  references in prose use `${CLAUDE_PLUGIN_ROOT}` literally if any are added (none required here).
- **Commit:** `fix(mill-merge): load config via _config.load_config, not obsolete wiki config.yaml`

### Card 4: mill-merge 1.5 Path Setup — resolve the hub via resolve_active_hub (no mode branch)

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_inplace.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Rewrite mill-merge step "1.5. Path Setup" so it no longer assumes
  `worktree_root = git_root`. Replace `worktree_root = git_root` with
  `worktree_root = _paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)`
  (the `container_path`, `slug`, and `cfg` are all already in scope from Step 1). Keep deriving
  `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])` and
  `task_dir = status_path.parent` — these now resolve against the real hub. This matches mill-go's
  Path Setup (SKILL.md:38-47). Add a one-sentence note in the prose that NO in-place vs worktree
  mode branch is needed because `resolve_active_worktree` checks in-place mode first (returns
  `git_root` when `_inplace.is_inplace` is true) and `resolve_active_hub` covers both modes — so
  the single call is correct whether `mode == 'inplace'` or `'worktree'`. Leave the git-level
  `git_root` uses elsewhere in mill-merge (Step 6 archive tag, wiki calls) unchanged — those are
  correct. Update any subsequent references in the file that re-derive `status_path` from
  `worktree_root` so they stay consistent (e.g. Step 4's parenthetical "resolved via
  `_paths.resolve_task_path(worktree_root, ...)` (set in Path Setup step 1.5)").
- **Commit:** `fix(mill-merge): resolve hub via resolve_active_hub in Path Setup (nested-hub #506/#497)`

### Card 5: mill-merge Step 4/5 — restore parent's task_dir from HEAD after squash (parent-state safety)

- **Context:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Make the squash safe against deleting the parent branch's own `_mill/`
  (`task_dir`) state (#497 bug 2). Keep Step 4's child-side cleanup commit (`git -C <worktree> rm -r
  <task_dir>` + `chore: pre-merge cleanup`) as-is. In Step 5 "Direct squash", between
  `git -C <parent-path> merge --squash "$CHILD_BRANCH"` and `git -C <parent-path> commit -m "<cached_task>"`,
  insert a restore step: restore the parent's own `task_dir` from the parent's pre-squash `HEAD`
  so the squash never stages a deletion/modification of it. Concretely document the two commands
  `git -C <parent-path> reset -q HEAD -- <task_dir>` (unstage anything the squash staged under
  `task_dir`) followed by `git -C <parent-path> checkout -- <task_dir>` (restore the parent's
  working-tree copy from its index/HEAD), and state this is a clean no-op when the parent tracks
  nothing at `task_dir`. After the restore, instruct re-inspecting the staged `git -C <parent-path>
  diff --cached --stat` and proceeding to commit only the intended production files. Add a brief
  "**Why**" note: the child cleanup commit deletes `task_dir`, so a parent that independently tracks
  `task_dir/_mill/status.md` at the same relative path would otherwise have its file deleted by the
  squash diff (the #497 bug-2 corruption). Keep the existing idempotency note and the
  branch-protection fallback sub-steps intact.
- **Commit:** `fix(mill-merge): restore parent task_dir from HEAD after squash (#497 parent-state safety)`

### Card 6: mill-merge-in — hub-resolve entry status_path and verify-replay plan_dir

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Make mill-merge-in's task-state paths hub-relative instead of cwd-relative, so
  it works on a nested hub. (a) Entry step 2: replace `status_path = Path("_mill/status.md").resolve()`
  with `status_path = _paths.resolve_task_path(_paths.resolve_hub_path(), "_mill/status.md")`. Keep
  the surrounding `_parent_branch.resolve(status_path, interactive=...)` call unchanged. (b)
  Verify-replay step (the line `plan_dir = Path("_mill/plan/").resolve()`): replace with
  `plan_dir = _paths.resolve_task_path(_paths.resolve_hub_path(), "_mill/plan/")`. Use
  `resolve_hub_path()` (NOT `resolve_active_hub`) to stay consistent with this file's existing line
  56 (`_config.load_config(_paths.resolve_hub_path(), git_root)`) and because step 2 runs before
  cfg/slug are resolved — see the overview's hub-resolution Shared Decision. Do not change line 56.
- **Commit:** `fix(mill-merge-in): hub-resolve status_path and plan_dir (nested-hub #506)`

## Batch Tests

`verify:` re-runs the batch-1 drift-guard test (`test-skill-helper-drift.py`), the single
unit-level check available for SKILL.md prose: it confirms every `_<module>.<fn>(` reference in the
edited skills (`_config.load_config`, `_paths.resolve_active_hub`, `_paths.resolve_task_path`,
`_paths.resolve_hub_path`, `_parent_branch.resolve`, `_inplace.is_inplace`) resolves to a shipped
helper. All those helpers already exist, so the test stays GREEN; a failure means a typo'd helper
name was introduced. The behavioral correctness of the squash-safety edit (Card 5) is validated by
batch 3's integration test — it is intentionally out of scope for this batch's verify.
