# Batch: merge-slug-check-and-pathspec

```yaml
task: "mill-finalize/mill-merge corrupt or mishandle _mill/status.md and task_dir on stacked branches"
batch: merge-slug-check-and-pathspec
number: 3
cards: 4
verify: null
depends-on: [1]
```

## Batch Scope

Wire the `expected_slug` identity check into every mill-merge / mill-merge-in call site
that resolves parent branch or phase from `_mill/status.md` (fixes #656/#659/#662's
misrouting), and fix #648's worktree-mode path bug in mill-merge's Direct-squash Step 5.
All mill-merge edits land in the same file (`mill-merge/SKILL.md`); the mill-merge-in
edit is one line in a sibling file and is grouped here because it is the same
"expected_slug wiring" unit of work. Depends on Batch 1 for the `expected_slug` kwarg.
`verify: null` -- these are pure SKILL.md orchestration-prose edits with no importable
surface of their own; Batch 4's integration test is what actually exercises the described
behavior end-to-end.

## Cards

### Card 6: Add expected_slug to mill-merge Entry Step 4's resolve() call

- **Context:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `## Entry`, step 4 currently reads: "Resolve parent branch via
    `_parent_branch.resolve(status_path, interactive=<True unless called
    non-interactively>)`." Add `expected_slug=slug` to the call:
    `_parent_branch.resolve(status_path, interactive=<True unless called
    non-interactively>, expected_slug=slug)`. `slug` is already bound in Entry Step 1 as
    `active_data['slug']`.
- **Commit:** `fix(mill): thread expected_slug through mill-merge's parent-branch resolve`

### Card 7: Add slug-identity check to mill-merge's Entry Step 5 phase gate

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `## Entry`, step 5 ("Phase gate -- also the re-entry point for PR-path
    recovery"), the paragraph "Try `_mill/status.md` first. If `status_path.exists()`,
    read `phase:` from it and apply the table below." gets a slug check inserted between
    confirming existence and reading `phase:`: after `status_path.exists()` is true, call
    `_status.read_slug(status_path)` and compare its return value against `slug` (the
    already-resolved `active_data['slug']` from Entry Step 1).
  - If the slugs do NOT match: do not read `phase:` from the table below at all. Instead,
    fall through to the exact branch this step already documents for "If `status_path` is
    absent": call `task = _client.get_task(wiki_path, slug)`, apply the existing `task is
    None` halt guard, and the existing `task["status"] == "pr-pending"` / else-halt
    branching, unchanged.
  - If the slugs match, the existing phase-read-and-table-lookup behavior is unchanged.
  - Update the existing halt message text in the "`_mill/status.md` absent and wiki does
    not show pr-pending" branch to additionally name the mismatch when it was what
    triggered this branch, e.g. append " (status.md slug did not match task slug
    '<slug>')" -- cosmetic, not load-bearing; keep ASCII-only per this plan's shared
    "ASCII-only messages" Decision.
- **Commit:** `fix(mill): detect status.md slug mismatch in mill-merge's phase gate`

### Card 8: Fix Direct-squash Step 5's worktree-mode path bug

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `### 5. Direct squash`, the "Direct path" bash block currently is:
    ```
    git -C <parent-path> merge --squash "$CHILD_BRANCH"
    git -C <parent-path> reset -q HEAD -- <task_dir>
    git -C <parent-path> checkout -- <task_dir>
    git -C <parent-path> commit -m "<cached_task>"
    git -C <parent-path> push
    ```
    Introduce a repo-relative pathspec variable derived from
    `cfg['paths']['status_md']`'s parent (in this hub, the literal `_mill`) and use it
    for ONLY the two middle commands:
    ```
    git -C <parent-path> merge --squash "$CHILD_BRANCH"
    git -C <parent-path> reset -q HEAD -- "$TASK_DIR_REL"
    git -C <parent-path> checkout -- "$TASK_DIR_REL"
    git -C <parent-path> commit -m "<cached_task>"
    git -C <parent-path> push
    ```
    Document `TASK_DIR_REL` as computed once (e.g. `_paths.resolve_task_path(worktree_root,
    cfg['paths']['status_md']).parent.relative_to(worktree_root).as_posix()` or an
    equivalent already-available relative form) and reused for both commands. Every other
    reference to `<task_dir>` in this skill (e.g. Step 4's `git -C <worktree> rm -r
    <task_dir>`, run against the child worktree) is unaffected and keeps its existing
    absolute form -- that one already resolves correctly within the child's own repo
    root.
  - Replace the paragraph immediately below that bash block, which currently reads:
    "Note: `<task_dir>` may be passed as either an absolute path (when
    `_paths.resolve_task_path` derives it from `worktree_root`) or a repo-relative path.
    `git reset` and `git checkout` accept both forms within the repo root." This claim is
    wrong for worktree mode and directly contradicts #648: the absolute, child-anchored
    `task_dir` value is never inside the parent's repo root when parent and child are
    separate worktree directories. Replace it with an accurate statement: these two
    commands specifically require the relative form, because they run with `-C
    <parent-path>` and a relative pathspec resolves against that `-C` target -- the
    absolute child-anchored path would resolve outside the parent's repo root and fail
    with "outside repository" (the exact #648 symptom). `$TASK_DIR_REL` is derived once
    and reused for both commands for this reason.
  - The "Why:" paragraph that follows (describing the #497 bug-2 protection this restore
    step provides) keeps its substance but should reference the corrected relative
    pathspec mechanism rather than repeating the old "accepts both forms" claim.
- **Commit:** `fix(mill): use repo-relative pathspec in mill-merge Direct-squash Step 5`

### Card 9: Add expected_slug to mill-merge-in's Entry Step 2 resolve() call

- **Context:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `## Entry`, step 2 currently reads: "call `_parent_branch.resolve(status_path,
    interactive=True)`". Add `expected_slug=slug` (`slug` is already resolved in Entry
    step 1 via `_marker.slug_from_branch(git_root, wiki_path, cfg)`):
    `_parent_branch.resolve(status_path, interactive=True, expected_slug=slug)`.
  - Preserve the existing "If `mill-merge-in` is being called from `mill-merge`'s
    auto-merge path, pass `interactive=False` and propagate the raised
    `ParentBranchError`" guidance verbatim -- `expected_slug=slug` applies in both the
    interactive and non-interactive forms of the call.
- **Commit:** `fix(mill): thread expected_slug through mill-merge-in's parent-branch resolve`

## Batch Tests

`verify: null`. This batch edits only orchestration prose in two SKILL.md files -- there
is no script surface of its own to run. The behavior these edits describe (slug-mismatch
detection falling back to the wiki; the relative-pathspec fix succeeding where the
absolute path would fail "outside repository") is exercised end-to-end by Batch 4's
integration test additions to `test-merge.py`, which mirror this batch's corrected
command sequences directly against real git worktrees.
