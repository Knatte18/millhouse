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
- **Requirements:** Update `plugins/mill/skills/mill-status/SKILL.md` to document the new Home.md state machine. The current file has NO phase table or bullet list of states — only a short description and a `## Run it` block. Create a new `## Phase reference` section immediately after the `## Run it` section, containing a markdown table with the following rows (in order):

  | Home.md marker | status.md phase | Written by | Next action |
  |---|---|---|---|
  | (unmarked) | n/a | — backlog | run `/mill-spawn` to claim |
  | `[s]` | n/a | — spawn-ready fast-path | run `/mill-spawn` to claim |
  | `[active]` | `discussing`/`discussed`/`planning`/`planned`/`implementing`/`reviewing`/`fixing`/`blocked` | mill-spawn / mill-claim | continue work via mill-start, mill-plan, mill-go |
  | `[ready-to-merge]` | `done` | mill-go Handoff step 2 | run `/mill-merge` to squash to parent |
  | `[pr-pending]` | `pr-pending` | mill-merge Step 5 (both PR-creation paths) | wait for GitHub PR to merge, then `/mill-cleanup --apply` |
  | `[done]` | `done` | mill-merge Step 7 (post-squash) | run `/mill-cleanup --apply` for worktree/branch/portal teardown |
  | `[abandoned]` | `abandoned` | mill-abandon | run `/mill-cleanup --apply` for teardown |

  Add a paragraph after the table summarising the lifecycle: `active → ready-to-merge → done` for the common path; `active → ready-to-merge → pr-pending → done` for the PR path; `active → abandoned` for the abandon path. Cross-reference: teardown for both `[done]` and `[abandoned]` is handled by `/mill-cleanup`, not by `/mill-merge`. Preserve the existing description and `## Run it` block above; only append the new section.
- **Commit:** `docs(mill-status): document [ready-to-merge] and [pr-pending] states`

### Card 20: Integration test `test-merge.py` — drop teardown assertions

- **Context:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/skills/mill-cleanup/SKILL.md`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Modify `plugins/mill/integration_tests/test-merge.py` so it no longer asserts that mill-merge removes the worktree, branch, portal, or wiki active directory, AND so that it no longer SIMULATES those removals before the assertions. The current test executes `git worktree remove --force <worktree>`, `git branch -D <branch>`, junction-removal calls, and `shutil.rmtree(wiki / "active" / slug)` + `_wiki.write_commit_push(...)` as part of simulating mill-merge's old Steps 8–10. **Remove every one of those simulation calls** (search for `git worktree remove`, `git branch -D`, `_junction.remove`, `shutil.rmtree` against the wiki active-dir, and `_wiki.write_commit_push` with `f"active/{slug}/"` in the wiki paths list — delete all of them from the test body). Then find every assertion of the forms `assert not (container / "wts" / slug).exists()`, `assert <branch> not in git_branch_list(...)`, `assert not (container / "portals" / slug).exists()`, and `assert not (wiki / "active" / slug).exists()` and replace each with the inverse: `assert (container / "wts" / slug).exists(), "worktree must remain intact after mill-merge — teardown is mill-cleanup's job"`; add positive assertions that the branch still appears in `git branch --list` output, the portal junction still exists, and `(wiki / "active" / slug).exists()` if the legacy layout fixture was used. **Add archive-tag creation AND assertion:** the current `test-merge.py` has neither, and the test fixture's `_setup_trio` initialises `hub` as a bare `git init` with no `origin` remote — so any `git push` from `hub` would fail. Insert between the squash commit step (step 5) and the Home.md flip (step 7) only the local-tag creation: `subprocess.run(["git", "-C", str(hub), "tag", f"archive/{slug}", child_branch], check=True)`. Do NOT add a `git push origin archive/<slug>` call (hub has no origin remote in this fixture); the assertion verifies local-tag existence only. After mill-merge runs, assert `subprocess.run(["git", "-C", str(hub), "tag", "-l", f"archive/{slug}"], capture_output=True, text=True).stdout.strip() != ""`. For fixture cleanup at the end of the test, invoke `mill-cleanup --apply` (or `shutil.rmtree` the temp dir directly) so the temp dir tears down cleanly. Update the test docstring or top-level comment to state: "Verifies mill-merge lands squash + archive tag + Home.md [done] flip; worktree, branch, portal, and wiki active-dir teardown are mill-cleanup's responsibility (separate test)." Do NOT introduce a new mill-cleanup integration test in this card — that is out of scope; the existing unit tests in `test-cleanup.py` (extended in batch 3) cover cleanup's PR-reap path.
- **Commit:** `test(merge): drop teardown assertions — worktree intact post-merge`

## Batch Tests

`verify: null`. The mill-status SKILL.md change is reviewer-only (no automated test). The integration test edit IS itself a test, but `test-merge.py` is operator-invoked (it runs real `git` + real `claude`) and is not part of the unit-test suite. The plan reviewer must verify the assertion inversions are correct against the new mill-merge SKILL.md text from batch 2.
