# Batch: merge-integration-test

```yaml
task: Fix nested-hub path resolution and SKILL.md vs shipped-API mismatches
batch: merge-integration-test
number: 3
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py
depends-on: [2]
```

## Batch Scope

Delivers the behavioral regression test for #497 bug 2: a new scenario in the existing
`test-merge.py` integration test that reproduces a parent branch carrying its own
`_mill/status.md` and proves the squash + restore-from-HEAD sequence (documented by batch 2's
Card 5) preserves it. The test runs real git (no LLM) and drives the git sequence directly
against fixture paths — it does NOT route through `resolve_active_hub` (see the fixture caveat in
the discussion's Testing section: the existing fixture builds `container/worktrees/<slug>`, not
`container/"wts"/slug`). Depends on batch 2 because the test encodes the exact restore sequence
the Card-5 prose defines; the implementer must read the finalized mill-merge Step 5 prose so the
test and skill stay in lockstep.

## Cards

### Card 7: test-merge.py — nested-hub squash preserves the parent branch's own _mill/status.md

- **Context:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/integration_tests/test-hub-relative-path.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new scenario (a new helper plus assertions invoked from `main()`, or a
  clearly-delimited new section in `main()`) that exercises the #497-bug-2 fix. Reuse the file's
  existing helpers (`_run`, `_assert`, `SCRATCH`, the `_setup_*` style) and follow
  `test-hub-relative-path.py` for building a nested layout. Steps the scenario must perform with
  raw git against fixture paths (do NOT call `resolve_active_hub`):
  1. Build a parent repo on a parent branch (e.g. `parent-feature`). Create a nested hub subdir
     (e.g. `<repo>/src/hub`) and commit, ON THE PARENT BRANCH, a `<hub>/_mill/status.md` whose
     content belongs to a DIFFERENT task (e.g. slug `other-task`) plus at least one production
     file. This is the parent's own tracked task state at the same relative `_mill/` path.
  2. Create a child branch off the parent that has its own `<hub>/_mill/` task state and a
     production-file change, then perform the child-side cleanup commit
     (`git rm -r <hub>/_mill` + a `chore: pre-merge cleanup` commit) — mirroring mill-merge Step 4.
  3. On the parent branch, run mill-merge Step 5's sequence verbatim: `git merge --squash <child>`,
     then the restore step `git reset -q HEAD -- <hub>/_mill` and `git checkout -- <hub>/_mill`,
     then `git commit`.
  4. Assertions (use `_assert`): (a) after the merge commit, `<hub>/_mill/status.md` on the parent
     branch is byte-identical to the `other-task` content committed in step 1 (the parent's state
     survived); (b) the squash commit's changed-files set (`git show --stat`/`git diff --name-only`)
     contains the child's production file and does NOT contain any `<hub>/_mill/` path (no deletion,
     no modification of parent state); (c) additionally confirm the archive-tag path still works by
     creating an archive tag over the child branch (reuse the same `_archive_tag`/git approach the
     existing flat scenario uses) and asserting the tag resolves to a commit whose tree still
     contains the child's cleanup state. Keep the existing flat-hub scenario and all its current
     assertions intact and passing. Preserve the file's exit-0-on-pass / exit-1-on-failure
     contract and ASCII-only output. Clean up scratch on pass as the existing test does.
- **Commit:** `test(mill-merge): nested-hub squash preserves parent's own _mill/status.md (#497)`

## Batch Tests

`verify:` runs the whole `test-merge.py` integration test (existing flat-hub flow + the new
nested-hub scenario). This is an integration test — it invokes real git and builds fixtures under
`.scratch/`, so it is not part of the unit `run-all.py` suite and is intentionally run as a single
file. It is the "affected integration test" the discussion's Testing section says to run green
before handoff. The new scenario is the durable regression lock for #497 bug 2: removing the
restore-from-HEAD step (or regressing mill-merge Step 5) makes assertion (a)/(b) fail.
