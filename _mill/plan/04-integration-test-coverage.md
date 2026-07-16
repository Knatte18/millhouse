# Batch: integration-test-coverage

```yaml
task: "mill-finalize/mill-merge corrupt or mishandle _mill/status.md and task_dir on stacked branches"
batch: integration-test-coverage
number: 4
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py
depends-on: [1, 2, 3]
```

## Batch Scope

Add end-to-end coverage for the two behaviors this task's SKILL.md edits (Batches 2 and
3) describe but that have no automated test today: #648's true worktree-mode path bug
(neither of `test-merge.py`'s two existing scenarios exercises the restore commands from
a genuinely separate parent-worktree directory), and mill-merge's phase-gate
slug-mismatch fallback (#656/#659/#662). Both cards extend the existing flat-hub
scenario in `test-merge.py`'s `main()`, reusing its already-established `hub` /
`worktree` / `wiki_path` / `slug` fixture from `_setup_trio`. Depends on Batches 1-3 so
the behavior under test matches what is actually shipped by the time this batch runs.

## Cards

### Card 10: Add true worktree-mode #648 repro to the flat-hub scenario

- **Context:** none
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `main()`'s flat-hub scenario, `hub` and `worktree` (from `_setup_trio`) are
    genuinely separate directories -- this is the true worktree-mode layout #648 was
    reported against, unlike `_setup_nested_hub_scenario`'s same-directory
    branch-switching. Between the existing `git -C str(hub) merge --squash child_branch`
    call and the following `git -C str(hub) commit -m "Demo merge"` call (currently
    back-to-back, with no restore step in between), insert two sub-steps:
    1. **Repro the bug first:** run `git -C str(hub) reset -q HEAD --
       str(worktree / "_mill")` (the OLD absolute, child-worktree-anchored form) and
       assert its return code is non-zero and its combined stdout+stderr contains
       `"outside repository"` -- this proves the fixture actually reproduces #648's
       failure before proving the fix resolves it. Since this command fails, it never
       reaches the index/working tree, so no cleanup or reset of `hub`'s state is needed
       before the next sub-step.
    2. **Prove the fix:** run `git -C str(hub) reset -q HEAD -- "_mill"` and `git -C
       str(hub) checkout -- "_mill"` (the corrected repo-relative form from Batch 3 Card
       8) and assert both exit 0.
  - `_setup_trio`'s `hub` has no `_mill/` at all on `main`, so this restore step is
    inherently a content no-op -- the assertion is purely that the corrected commands
    succeed rather than failing "outside repository", which is the entirety of #648's
    reported bug.
- **Commit:** `test(mill): add true worktree-mode repro+fix coverage for #648`

### Card 11: Add phase-gate slug-mismatch fallback scenario

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add `import _status` alongside the existing `import _parent_branch` /
    `import _plan_dag` block near the top of the file.
  - After the flat-hub scenario's existing assertions (following the "PASS -- mill-merge
    end-to-end (flat-hub scenario)" print), add a new sub-scenario that simulates the
    post-Step-3-corruption state mill-finalize's restore path produces (per this task's
    Batch 2 fix): write a status.md to `worktree / "_mill" / "status.md"` (create the
    `_mill/` directory if absent) whose yaml block describes a DIFFERENT, foreign task --
    `slug: other-task`, `phase: discussing`, `parent: main` -- mirroring
    `_setup_nested_hub_scenario`'s existing "other-task" foreign-status.md pattern.
  - Mirror mill-merge's corrected Entry Step 5 phase-gate logic directly as plain test
    code (this logic is orchestration prose in SKILL.md, not an importable function, so
    the test replicates the same two-call sequence Batch 3 Card 7 now documents): call
    `_status.read_slug(worktree / "_mill" / "status.md")` and assert it does NOT equal
    `slug` (`"demo-merge"`); then call `wiki.get_task(wiki_path, slug)` (reusing the
    already-registered `demo-merge` task from `_setup_trio`'s `wiki.upsert_task` call) and
    assert the returned dict's `status` field reflects `demo-merge`'s real state -- not
    the foreign task's `phase: discussing` -- proving the documented wiki-fallback path
    resolves correctly instead of trusting the corrupted file's `phase:`/`parent:`
    fields.
- **Commit:** `test(mill): add phase-gate slug-mismatch fallback coverage for #656/#659/#662`

## Batch Tests

`test-merge.py` (real git, `.scratch/` fixtures, no real LLM) now covers, in addition to
its two pre-existing scenarios: the true worktree-mode #648 repro-then-fix (Card 10), and
the phase-gate slug-mismatch-to-wiki-fallback behavior underlying #656/#659/#662 (Card
11). Both new sub-scenarios reuse the flat-hub fixture's already-established `hub` /
`worktree` / `wiki_path` / `slug`, so no new top-level fixture function is introduced.
