# Batch: mill-merge-in-stale-ref

```yaml
task: Fix mill-merge-in stale ref check, PowerShell 5.1 ConvertTo-Json, and _status str-path crash
batch: mill-merge-in-stale-ref
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py
depends-on: []
```

## Batch Scope

Fixes GitHub #600: `mill-merge-in`'s Step 1 no-op check compares `HEAD` against the *local* parent-branch ref without fetching, so a stale local ref (e.g. because the parent branch is checked out unpulled in a sibling worktree) causes the entire checkpoint/merge/verify/rollback safety net to be silently skipped. This batch is a `SKILL.md` prose edit (Card 1) plus the matching integration-test fixture/assertion update that keeps `test-merge.py` honest against the new documented behavior (Card 2). No Python production code changes — `mill-merge-in`'s Step 1 and Step 3 are plain inline bash in the skill markdown, not backed by a script. External interface: none: the next batch does not depend on this one.

## Cards

### Card 1: Add MERGE_REF resolution to mill-merge-in Step 1 and Step 3, update No-op guarantee wording

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Replace the "### 1. No-op check" section's bash block (currently just `git log HEAD..<parent-branch> --oneline`) with a block that first fetches origin, then resolves `MERGE_REF` deterministically from durable git refs (not a shell variable carried into a later block — the SKILL's fenced bash blocks each run as a separate tool call), then diffs against `MERGE_REF`:

  ```bash
  git fetch origin "<parent-branch>" 2>/dev/null
  if git rev-parse --verify --quiet "refs/remotes/origin/<parent-branch>" >/dev/null 2>&1 \
     && git merge-base --is-ancestor "<parent-branch>" "origin/<parent-branch>"; then
    MERGE_REF="origin/<parent-branch>"
  else
    MERGE_REF="<parent-branch>"
  fi
  git log HEAD.."$MERGE_REF" --oneline
  ```

  Keep the existing prose immediately after it ("If output is empty -> report 'Nothing to merge -- already up to date.' and exit 0 immediately...") unchanged.

  In "### 3. Merge parent into current", replace the bash block `git merge <parent-branch>` with a block that **re-runs the identical `MERGE_REF` resolution snippet above** (same four lines: `git fetch origin "<parent-branch>" 2>/dev/null`, the `if git rev-parse ... && git merge-base --is-ancestor ...` check, the two `MERGE_REF=` assignments) followed by `git merge "$MERGE_REF"`. Re-running the resolution is required (not optional) because the earlier value cannot be threaded across the two separate fenced bash blocks; re-deriving from `refs/remotes/origin/<parent-branch>` (durable on disk after Step 1's fetch, exactly like the existing `$CHK` checkpoint ref) reproduces the identical `MERGE_REF` deterministically. Do not change any of the surrounding conflict-resolution table or rollback text in Step 3.

  In the "## No-op guarantee" section, reword the existing sentence "When step 1 returns empty, this skill touches nothing: no checkpoint, no verify, no codeguide-update, no output side effects." to "When step 1 returns empty, this skill touches no task state: no checkpoint, no verify, no codeguide-update, no output side effects." (only the fourth word changes, from "nothing" to "no task state" — the enumerated list stays verbatim), and append one new sentence immediately after it: "Step 1 always performs a network fetch (`git fetch origin <parent-branch>`) even when the result is a no-op; this is a deliberate cost of correctly detecting a stale local ref and is the only exception to the "touches no task state" guarantee." Do not change the second sentence of that section ("`mill-merge` depends on this...").
- **Commit:** `fix(mill-merge-in): fetch and compare against origin/<parent-branch> before no-op check and merge (#600)`

### Card 2: Extend test-merge.py fixture with a real origin remote, update Step 1 replica

- **Context:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  `_setup_trio` (function starting at line 76) currently gives the hub/code repo no `origin` remote at all — only the wiki gets one (see the `git -C <wiki_path> push origin main` calls at lines 178 and 287, and the `git init <hub>` call at line 191 with no matching `remote add`). Add a real bare `origin` remote for the hub repo, mirroring the existing wiki pattern:
  1. Immediately after the hub's `git init` + initial commit (after the block ending at line 196, before the `.millhouse` junction setup at line 198), create a bare repo `container / "hub-origin.git"` via `git init --bare <path> -b main`, then `git -C <hub> remote add origin <hub-origin.git path>`, then `git -C <hub> push origin main`.
  2. No additional push is required after the "Task branch + worktree with a single commit ahead of main" block (line 221): that commit lands on `test/<slug>`, which is never pushed to origin, so `main` itself never advances past the step-1 push and `origin/main` stays in sync with it.

  Update the existing "--- mill-merge-in no-op check: parent has no new commits vs HEAD ---" block (currently at lines ~446-453: a single `git log HEAD..{parent} --oneline` call) to instead run the same `MERGE_REF` resolution the SKILL.md now documents (fetch, then `git rev-parse --verify --quiet refs/remotes/origin/{parent}` + `git merge-base --is-ancestor {parent} origin/{parent}`, defaulting to `MERGE_REF={parent}` on failure) via a small local `_run` sequence, then assert `git log HEAD.."{MERGE_REF}" --oneline` is empty exactly as today. Since at this point in the test `main` has no new commits relative to the pushed origin and the worktree's `HEAD` has no relationship difference introduced yet, `MERGE_REF` must resolve to `origin/main` (fetch succeeds, local `main` is not ahead of `origin/main`) — assert this explicitly (e.g. capture and assert the resolved `MERGE_REF` value equals `"origin/main"`) so the test genuinely exercises the fetch-succeeds branch, not just the local-ref fallback.
- **Commit:** `test(mill-merge): exercise fetch-and-compare-origin no-op check against a real origin remote`

## Batch Tests

`verify:` runs the full `test-merge.py` integration test (no `--only` scoping mechanism exists for integration tests; the file is a single self-contained script). This is the only test that exercises `mill-merge-in`'s Step 1/Step 3 bash sequence, so running the whole file is the minimum meaningful scope — there is nothing narrower to target within this file. Card 2's fixture change (real `origin` remote) is exercised by every assertion in the file that runs after `_setup_trio`, not just the no-op-check assertion, so a full-file run also catches any regression the new remote might introduce elsewhere in the fixture.
