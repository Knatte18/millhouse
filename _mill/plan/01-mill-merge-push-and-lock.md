# Batch: mill-merge-push-and-lock

```yaml
task: 'mill-merge/merge-in: nested-layout config resolution, stale locks, and rollback-target bugs'
batch: mill-merge-push-and-lock
number: 1
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Fixes two bugs in `plugins/mill/skills/mill-merge/SKILL.md`'s Step 5 (Direct squash) / Step 8 (Release merge lock) flow: (1) `#904`/`#862` — Step 5's push-failure classification has no branch for a plain non-fast-forward rejection, so the existing pre-squash `merge --ff-only` guard's race window (between the guard and the actual push) still ends in a full Step 1–5 rollback instead of a cheap fetch+rebase+retry; (2) `#863` — the merge lock is released at Step 8, the very end of the Teardown sequence, so a session interrupted between Step 5's successful push and Step 8 leaks the lock. Both fixes live in the same file and the same "push succeeded, what happens next" flow, so they are one batch. `Requirements:` below give exact before/after text for each edit site — apply them as literal text edits (Edit tool), not paraphrases, since this file is followed verbatim by an LLM orchestrator at runtime. Every fenced block below reproduces the source file's own byte-exact indentation (flush left, no extra indent from this card's own list nesting) — copy fence contents literally, do not re-indent them to match this document's bullet structure.

## Cards

### Card 1: push-failure-classification — add non-fast-forward rebase-retry branch

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `**On push failure — branch-protection fallback:**` section (under `### 5. Direct squash`), replace the existing numbered sub-step 1 and the start of sub-step 2 with a new sub-step 1a inserted between them. This section's current sub-steps 1–8 keep their numbers unchanged except for the new 1a insertion (sub-steps 2–8 are otherwise untouched — do not renumber them).

  Find this exact text (fence content is byte-exact, flush-left, matching the source file's own indentation):

```
1. Check the captured output for any of these substrings: `Changes must be made through a pull request`, `repository rule violations`, `protected branch`, `GH006`.
   If none match → fail the step and trigger the Step 1–5 rollback (do not attempt the fallback).

2. If a match is found — branch-protection rejection — undo the local squash commit on the parent:
```

  Replace it with:

```
1. Check the captured output for any of these substrings: `Changes must be made through a pull request`, `repository rule violations`, `protected branch`, `GH006`.
   If a match is found, skip to sub-step 2 (branch-protection rejection) below.
   If none match, continue to sub-step 1a.

1a. Check the captured output for `! [rejected]` together with either `(fetch first)` or `(non-fast-forward)` — git's own literal rejection markers for a plain non-fast-forward push rejection (distinct from the branch-protection substrings in sub-step 1 above, and from any other failure such as auth or network errors).

    If both markers are present:

    ```bash
    git -C <parent-path> fetch origin "<parent_branch>"
    git -C <parent-path> rebase "origin/<parent_branch>"
    ```

    On a rebase conflict (non-zero exit from `git rebase`): capture the conflicting files via `git -C <parent-path> diff --name-only --diff-filter=U`, then run `git -C <parent-path> rebase --abort`, then fail the step and trigger the Step 1–5 rollback, naming the conflicting files in the operator-facing report.

    On a clean rebase (exit 0): retry the push once —

    ```bash
    git -C <parent-path> push
    ```

    If this retry succeeds (exit 0): the parent now has the squash commit rebased onto the current `origin/<parent_branch>` tip — treat this exactly as if the original push above had succeeded, and continue from the "Post-Step-5-success sequencing" paragraph at the end of this `### 5. Direct squash` section.
    If this retry also fails: fail the step and trigger the Step 1–5 rollback.

    If neither marker is present (this is not a plain non-fast-forward rejection — e.g. an auth or network failure): fail the step and trigger the Step 1–5 rollback (do not attempt any fallback) — this is the unchanged "no match" behavior for any failure that is neither branch-protection nor a plain non-fast-forward rejection.

2. If a match is found in sub-step 1 — branch-protection rejection — undo the local squash commit on the parent:
```

  Do not modify sub-steps 2 through 8 or the `**Idempotency check:**` line that follows them.
- **Commit:** `fix(mill-merge): add non-fast-forward rebase-retry branch to Step 5 push-failure classification (#904, #862)`

### Card 2: merge-lock-early-release — relocate Step 8's execution point

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Four edits in the same file, all independent of Card 1's edit (different sections). Apply all four; order among them does not matter.

  **Edit A — `## Teardown sequence` intro paragraph.** Find this exact text:

```
## Teardown sequence

Steps 4–7 implement the canonical merge sequence;
worktree, portal, and wiki active-dir teardown is handled by `/mill-cleanup`.
Each step is independent;
a failed step is reported with its name so the user can re-run from that step (Step 4's squash idempotency handles the common re-entry case).
```

  Replace it with:

```
## Teardown sequence

Steps 4–7 implement the canonical merge sequence;
worktree, portal, and wiki active-dir teardown is handled by `/mill-cleanup`.
Each step is independent;
a failed step is reported with its name so the user can re-run from that step (Step 4's squash idempotency handles the common re-entry case).

**Step 8 (release merge lock) executes out of its numeric position on the direct-squash path:** once Step 5's squash+push succeeds (including via the sub-step 1a rebase-retry — see Card 1), Step 8 runs immediately — before Steps 5.5, 6, and 7 — since none of those three steps touch the locked parent worktree. See "Post-Step-5-success sequencing" at the end of `### 5. Direct squash` and `### 8. Release merge lock`'s own note. This reordering does not affect the `merged` PR-state route (`## Entry`), which already skips Steps 1/2 (never acquires the lock) and documents Step 8 there as a no-op.
```

  **Edit B — end of `### 5. Direct squash`.** Find this exact text (the section's final paragraph, immediately before the `### 5.5. Preflight check for cache helpers` heading):

```
**Idempotency check:** if `git merge --squash` prints "Already up to date" or `git commit` prints "nothing to commit" → skip `push` and proceed to Step 6.
```

  Replace it with:

```
**Idempotency check:** if `git merge --squash` prints "Already up to date" or `git commit` prints "nothing to commit" → skip `push` and proceed to Step 6.

**Post-Step-5-success sequencing:** whenever Step 5 succeeds — either via the original `git -C <parent-path> push` above, or via sub-step 1a's rebase-retry push under "On push failure — branch-protection fallback" — run Step 8 (release merge lock) immediately next, before proceeding to Step 5.5. This applies to the direct-squash path only (this section); it does not apply to the `merged` PR-state route, which never reaches this section and has its own unaffected Step 8 no-op note in `## Entry`.
```

  **Edit C — `### 7. Home.md — mark [done]` failure-handling paragraph.** Find this exact text:

```
**Failure handling after the squash landed on parent:** do NOT roll back the merge.
Report the error, release all locks, tell the user "Merge landed on <parent> but <step> failed: <err>.
Re-run `/mill-merge` to retry — Step 5's idempotency check will skip the squash."
This is the non-destructive boundary: once the parent has the squash, it stays.
```

  Replace it with:

```
**Failure handling after the squash landed on parent:** do NOT roll back the merge.
The merge lock was already released by Step 8's early execution (see "Post-Step-5-success sequencing" at the end of `### 5. Direct squash`), so there is nothing left to release here.
Report the error, tell the user "Merge landed on <parent> but <step> failed: <err>.
Re-run `/mill-merge` to retry — Step 5's idempotency check will skip the squash."
This is the non-destructive boundary: once the parent has the squash, it stays.
```

  **Edit D — `### 8. Release merge lock`.** Find this exact text:

```
### 8. Release merge lock

Delete `<parent-path>/.scratch/merge.lock`.
Run this in a `finally:` equivalent so the lock is released on every exit path.

**In-place mode:** no merge lock was acquired (Entry Steps 1 and 2 were skipped).
Skip lock release.
```

  Replace it with:

```
### 8. Release merge lock

Delete `<parent-path>/.scratch/merge.lock`.
Run this in a `finally:` equivalent so the lock is released on every exit path.

**Execution point on the direct-squash path:** this step runs immediately after Step 5 succeeds (see "Post-Step-5-success sequencing" at the end of `### 5. Direct squash`), before Steps 5.5, 6, and 7 — not at the end of the Teardown sequence as its position in this document might otherwise suggest. On any of the pre-squash halts in Step 5 (dirty-parent-worktree, parent-fast-forward-failure) or a Step 1–5 rollback, this step still runs at its normal point in the Rollback/halt flow, unchanged.

**In-place mode:** no merge lock was acquired (Entry Steps 1 and 2 were skipped).
Skip lock release.
```
- **Commit:** `fix(mill-merge): release merge lock immediately after Step 5 succeeds, not at Step 8's end-of-sequence position (#863)`

## Batch Tests

`verify: null` — both cards are `SKILL.md` prose edits with no Python code changed and no existing unit/integration test exercises the LLM-followed instruction flow directly. `plugins/mill/integration_tests/test-merge.py` was considered (per `_mill/discussion.md`'s Testing section) but tests the underlying Python helpers (`_archive_tag.py`, `_parent_branch.py`, teardown state machinery) driven by real git, not the SKILL.md prose an orchestrator follows — it has no assertion surface for "does the rebase-retry branch text exist" or "does Step 8 now run early", so extending it would not meaningfully verify this batch. Manual review of the rendered SKILL.md text (this batch's actual deliverable) is the verification for both cards.
