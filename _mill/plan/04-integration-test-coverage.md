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
    branch-switching. `_setup_trio`'s `hub` has no `_mill/` at all on `main`, and a bare
    `git checkout -- <pathspec>` fails with `pathspec '... did not match any file(s)
    known to git` when the target ref has nothing there -- independent of the
    worktree-mode bug this card targets -- so seed `hub`'s `main` branch with its own
    trivial `_mill/status.md` (distinct placeholder content, e.g. `phase: done\ntask:
    Unrelated hub task\n`) committed on `main` BEFORE the squash, so the restore
    commands have something real to act on and to protect.
  - Between the existing `git -C str(hub) merge --squash child_branch` call and the
    following `git -C str(hub) commit -m "Demo merge"` call (currently back-to-back,
    with no restore step in between), insert two sub-steps:
    1. **Repro the bug first:** run `git -C str(hub) reset -q HEAD --
       str(worktree / "_mill")` and `git -C str(hub) checkout --
       str(worktree / "_mill")` (the OLD absolute, child-worktree-anchored form) and
       assert BOTH return codes are non-zero and their combined stdout+stderr contains
       `"outside repository"` -- this proves the fixture actually reproduces #648's
       failure (an out-of-repo absolute pathspec is rejected before any pathspec-match
       check runs, so this holds regardless of the seeded content) before proving the
       fix resolves it. Since both commands fail, they never touch the index/working
       tree, so no cleanup of `hub`'s state is needed before the next sub-step.
    2. **Prove the fix:** run `git -C str(hub) reset -q HEAD -- "_mill"` and `git -C
       str(hub) checkout -- "_mill"` (the corrected repo-relative form from Batch 3 Card
       8) and assert both exit 0.
  - After the fix sub-step and the subsequent `git -C str(hub) commit -m "Demo merge"`,
    assert `hub`'s `_mill/status.md` on disk still exactly matches the placeholder
    content seeded above (byte-identical) -- mirroring `_setup_nested_hub_scenario`'s
    existing "parent's own status.md survives the squash" assertion, but this time in
    the true separate-worktree layout that assertion never actually covered.
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
    `_status.read_full(worktree / "_mill" / "status.md")["yaml"].get("slug")` and assert
    the returned value is not `None` and does NOT equal `slug` (`"demo-merge"`) --
    reading the raw field (not `_status.read_slug`, which falls back to the parent
    directory name -- always literally `"_mill"` -- when the field is absent, so it can
    never distinguish "absent" from "present and different" the way Card 1's
    `expected_slug` check does; reading the raw field keeps this test's mirror faithful
    to Card 7's corrected semantics). Then call `wiki.get_task(wiki_path, slug)` (reusing the
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
