# Batch: docs-integration

```yaml
task: "46 (A) — Home.md state machine + split mill-merge teardown into mill-cleanup"
batch: docs-integration
number: 4
cards: 2
verify: null
depends-on: [2, 3]
```

## Batch Scope

This final batch lands two consumer-facing changes that depend on the state machine (batch 2) and mill-cleanup logic (batch 3) being settled: mill-status SKILL.md learns the new phase columns, and the integration test `test-merge.py` is updated so it no longer expects mill-merge to remove the worktree. Both are small, independent edits in different files. Card numbering continues at 19 (cards 1–18 covered batches 1–3).

## Cards

### Card 19: Update `mill-status` SKILL.md state table

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/skills/mill-cleanup/SKILL.md`
  - `task/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-status/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Update `plugins/mill/skills/mill-status/SKILL.md` so its Home.md phase / status.md phase tables reflect the new state machine. The file currently documents `[active]` / `[done]` / `[abandoned]` for Home.md and a finite set of `status.md phase:` values. Find every table or bullet list enumerating Home.md markers and extend it to include `[ready-to-merge]` and `[pr-pending]`, in order between `[active]` and `[done]`. For each new row, document:
  - `[ready-to-merge]`: written by mill-go Handoff step 2. Means "mill-go completed implementation, mill-merge has not been invoked yet." `status.md phase: done`. Next action: run `/mill-merge`.
  - `[pr-pending]`: written by mill-merge Step 5 (both PR-creation paths). Means "mill-merge created a GitHub PR; awaiting human/CI merge." `status.md phase: pr-pending`. Next action: wait for PR to merge, then run `/mill-cleanup --apply` for teardown.
  If the file has a status.md `phase:` enumeration, add `pr-pending` to it (between `done` and `blocked` or wherever fits the existing ordering). Do not rewrite the file beyond these additions; preserve the existing prose style. If a "Lifecycle diagram" or similar ASCII state graph exists, extend it to show `active → ready-to-merge → done` and the optional `ready-to-merge → pr-pending → done` PR detour. Cross-reference: `[done]` rows should mention "teardown handled by `/mill-cleanup`, not by `/mill-merge`" to reflect the new responsibility split.
- **Commit:** `docs(mill-status): document [ready-to-merge] and [pr-pending] states`

### Card 20: Integration test `test-merge.py` — drop teardown assertions

- **Context:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/skills/mill-cleanup/SKILL.md`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Modify `plugins/mill/integration_tests/test-merge.py` so it no longer asserts that mill-merge removes the worktree, branch, or portal. Find every assertion of the forms `assert not (container / "wts" / slug).exists()`, `assert <branch> not in git_branch_list(...)`, `assert not (container / "portals" / slug).exists()` (or variants — there may be just one block enumerating "verify after teardown" expectations). Replace them with the inverse assertions: `assert (container / "wts" / slug).exists(), "worktree must remain intact after mill-merge — teardown is mill-cleanup's job"`. Add a positive assertion that the branch still appears in `git branch --list` output. Keep all assertions that mill-merge DOES still perform: squash commit landed on parent, archive tag `archive/<slug>` exists on the local repo, Home.md marker flipped to `[done]`. If the test invokes any explicit `/mill-cleanup` call after `/mill-merge` to "clean up the fixture," leave it in (and add one if absent — a final `subprocess.run([... mill-cleanup --apply ...])` at the end of the test is fine for fixture cleanup so the temp dir tears down cleanly). Update the test docstring or top-level comment to state: "Verifies mill-merge lands squash + archive + Home.md [done] flip; worktree teardown is mill-cleanup's responsibility (separate test)." Do NOT introduce a new mill-cleanup integration test in this card — that is out of scope; the existing unit tests in `test-cleanup.py` (extended in batch 3) cover cleanup's PR-reap path.
- **Commit:** `test(merge): drop teardown assertions — worktree intact post-merge`

## Batch Tests

`verify: null`. The mill-status SKILL.md change is reviewer-only (no automated test). The integration test edit IS itself a test, but `test-merge.py` is operator-invoked (it runs real `git` + real `claude`) and is not part of the unit-test suite. The plan reviewer must verify the assertion inversions are correct against the new mill-merge SKILL.md text from batch 2.
