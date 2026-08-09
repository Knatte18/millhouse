# Discussion: _verify_baseline.py transient worktrees can be orphaned when the task worktree is force-removed mid-computation

```yaml
task: _verify_baseline.py transient worktrees can be orphaned when the task worktree is force-removed mid-computation
slug: verify-baseline-nested-worktree-orphan-risk
status: discussing
parent: main
```

## Problem

`_verify_baseline.py`'s `compute_baseline` (and `millpy-implement.py`'s baseline-stage shared checkout, which reuses the same helper) checks out the parent branch's tip into a fresh, throwaway git worktree nested inside the task worktree itself, at `<task_worktree>/.scratch/verify-baseline-<uuid>`. Teardown of that nested worktree happens only in a `try/finally` (`_verify_baseline.py:217-224` / `millpy-implement.py:425-426`) that calls `_worktree.remove_safe`.

If the process computing the baseline is killed before that `finally` runs — the exact scenario the 600s stall-watchdog kill produces (tracked separately in `mill-pipeline-dispatch-entrygate-gaps`, #787) — the nested worktree's directory and its git registration both survive, untouched, on disk. That in itself is inert. The actual orphan happens later: when mill-cleanup eventually force-removes the *enclosing task worktree* via `_worktree.remove_safe` (`millpy-cleanup.py:572`), `git worktree remove --force <task_worktree>` deletes the task worktree's directory tree wholesale — including the nested worktree's files — but the nested worktree's git administrative entry lives in the hub repo's common `.git/worktrees/verify-baseline-<uuid>/`, a location entirely separate from the task worktree's own directory. That entry survives the deletion, now pointing at a gitdir that no longer exists. `remove_safe`'s success path (`_worktree.py:275-277`) returns immediately after a successful `git worktree remove` with no cleanup of this stale entry; only the long-path/fallback branch (`_worktree.py:309-317`) happens to call `git worktree prune`. The result: an orphaned `.git/worktrees/verify-baseline-<uuid>/` administrative entry that accumulates and can produce confusing "already exists"/lock errors on later `git worktree add` calls until someone runs `git worktree prune` manually.

## Scope

**In:**
- `_worktree.remove_safe` (`plugins/mill/scripts/_worktree.py:222-318`): restructure so `git worktree prune` runs unconditionally, once, after either the success branch or the fallback branch successfully removes the outer worktree — replacing the current fallback-only prune call.
- Unit test coverage in `plugins/mill/unit_tests/test-worktree.py` reproducing the actual orphan scenario end-to-end with real git repos (no mocks): task worktree containing a nested worktree, force-remove the task worktree via `remove_safe`, assert the nested worktree's entry is gone from `git worktree list` afterward.

**Out:**
- The orchestrator-side stall-kill notification/classification gap that produces the mid-computation kill in the first place — tracked separately in `mill-pipeline-dispatch-entrygate-gaps` (#787). This task only addresses the resulting orphaned-git-metadata consequence.
- Registry-based tracking of transient worktrees in `_verify_baseline.py` (the brief's alternative remedy) — rejected in favor of centralizing the fix in `remove_safe`, see Decisions.
- Proactive reaping of an abandoned-but-still-valid nested worktree sitting in `.scratch/` while its enclosing task worktree stays alive indefinitely (a disk-hygiene concern distinct from the git-metadata-orphan bug reported here; safely distinguishing "abandoned" from "a sibling process's live baseline computation in progress" needs a lock/age heuristic that is its own design problem).
- Any change to `millpy-implement.py`'s or `_verify_baseline.py`'s own call sites — they get the fix for free because `remove_safe` is shared.

## Decisions

### centralize-fix-in-remove-safe

- Decision: Fix `_worktree.remove_safe` itself rather than adding registry/tracking machinery to `_verify_baseline.py`.
- Rationale: `git worktree prune` only removes administrative entries whose linked working directory is verifiably missing — it is safe to call unconditionally and idempotently, including under concurrency (a sibling task's still-live nested worktree has a directory that still exists, so prune never touches it). Fixing `remove_safe` covers every current and future caller uniformly. Independently confirmed a second call site with the identical exposure: `millpy-implement.py:354-426`'s shared per-batch baseline checkout uses the same `_verify_baseline._checkout_parent_branch` + `remove_safe`-in-`finally` pattern. A registry-based fix scoped to `_verify_baseline.py` would miss that second call site entirely.
- Rejected: Registry file written by `_verify_baseline.py`, read and pruned by mill-cleanup after abnormal exit — more moving parts (registry write/read/GC, races between concurrent baseline computations sharing one registry file), and doesn't generalize to the `millpy-implement.py` call site.

### prune-runs-once-unconditionally

- Decision: Restructure `remove_safe` so `git worktree prune` is called exactly once, after either the success branch (`git worktree remove --force` returns 0) or the fallback branch (`_safe_rmtree.safe_rmtree` fallback) completes — not duplicated as separate calls in each branch.
- Rationale: DRY. The prune call's semantics (cwd, warn-on-failure, message text) are identical regardless of which branch removed the worktree; a single shared tail-call is simpler to maintain than two copies that could drift.
- Rejected: Leaving the fallback branch's existing prune call as-is and adding a second, separately-coded prune call in the success branch.

### prune-failure-is-non-fatal

- Decision: If the new unconditional `git worktree prune` call itself fails, print a warning to stderr and continue — do not raise.
- Rationale: Matches the existing fallback-path behavior (`_worktree.py:312-317`). Prune failure is a hygiene/best-effort step, not correctness-critical — the worktree removal itself (the thing `remove_safe`'s caller actually asked for) already succeeded by the time prune runs. Raising here would regress currently-working teardown paths over a secondary cleanup step.
- Rejected: Raising `WorktreeError` on prune failure.

## Technical context

- `_worktree.remove_safe` (`plugins/mill/scripts/_worktree.py:222-318`) is the single fix point. Current structure: strip junctions → kill stale holders → try `git worktree remove --force` → on success, `return` immediately (line 275-277, **no prune**) → on failure, check lock patterns (raise `WorktreeLockedError`) vs. rmtree-fallback patterns (`Filename too long`, `is not a working tree`, `Directory not empty`) → on fallback, run `_safe_rmtree.safe_rmtree` then `git worktree prune` with a warn-only failure (line 309-317). The fix moves the existing fallback-branch prune-and-warn logic to run after *both* branches instead of only the fallback branch — the cleanest shape is likely a shared local flag or restructuring the two branches to both fall through to one trailing prune call before the function returns, rather than two `return` statements each doing their own prune.
- `remove_safe` callers, all of which pick up this fix automatically: `_verify_baseline.py:224` (nested-worktree's own teardown), `millpy-implement.py:379,426` (shared per-batch baseline checkout teardown), `millpy-cleanup.py:572` (task worktree teardown — this is the call site where the orphan actually manifests), `millpy-spawn.py:204` (spawn-failure rollback).
- `git worktree prune` (confirmed via `git worktree prune -h` against the installed git 2.53.0) takes no default expiry — omitting `--expire` prunes stale entries immediately, so no age-threshold logic is needed.
- The nested worktree's git administrative entry lives in the *hub repo's* common `.git/worktrees/<name>/`, not inside the task worktree's own `.git` (which is just a file pointing at the common gitdir) — this is why deleting the task worktree's directory tree doesn't automatically clean up the nested worktree's registration; the two are tracked independently by git.
- `_verify_baseline._checkout_parent_branch` always creates the nested worktree with `-c core.longpaths=true` scoped to the single invocation and a detached HEAD (no branch), at `<project_root>/.scratch/verify-baseline-<12-hex-uuid>` — the uuid makes path collisions on retry irrelevant; the bug is purely about the stale `.git/worktrees/` registration, not path reuse.

## Constraints

None beyond the codebase's existing conventions (no `CONSTRAINTS.md` present at the hub root).

## Testing

- **TDD candidate:** `unit_tests/test-worktree.py`, extending the existing `remove_safe` coverage (which already uses a mix of real-git-repo tests for the happy paths and mocked-`_subprocess_util.run` tests for the error-branch behaviors).
- **New scenario (real git, no mocks — matches the file's `list_worktrees`/`remove` test style):**
  1. `_git_init` a hub repo.
  2. `git worktree add` a task worktree off the hub.
  3. From the hub, `git worktree add <task_worktree>/.scratch/nested <sha>` — a worktree nested inside the task worktree, registered against the hub's common gitdir (mirroring `_verify_baseline._checkout_parent_branch`'s real behavior).
  4. Call `remove_safe(task_worktree, cwd=hub, junctions_cfg={})`.
  5. Assert the task worktree directory is gone (existing behavior, unchanged).
  6. Assert (the new behavior under test) that `list_worktrees(hub)` (or a direct `git -C hub worktree list --porcelain` parse) no longer includes an entry for the nested worktree's path — proving the trailing `git worktree prune` ran and cleared the stale registration left by the outer force-removal.
- Existing mocked-error-branch tests (`Permission denied`, `is in use`, `Invalid argument`, generic `WorktreeError`, rmtree-fallback `PermissionError`) should be re-run unchanged after the restructure — none of them reach the new trailing-prune code path (they all raise before it), so no fixture updates are expected there, but confirm this holds once the restructure is written.
- No new test is needed for `_verify_baseline.py` or `millpy-implement.py` directly — they get the fix for free through `remove_safe`, and their existing baseline-computation tests don't need to know about worktree-internals prune behavior.

## Q&A log

- **Q:** Which fix approach — centralize in `_worktree.remove_safe`, or have `_verify_baseline.py` register its transient worktree for mill-cleanup to prune after abnormal exit? **A:** [auto-pick] Centralize in `_worktree.remove_safe`. **Why:** Simpler, strictly more general — covers a second call site (`millpy-implement.py`'s shared checkout) with the identical exposure, found independently during exploration — and `git worktree prune`'s semantics make it safe to call unconditionally/idempotently under concurrency.
- **Q:** Should the trailing `git worktree prune` call be a single shared call after either removal branch, or a separate duplicated call added just to the success branch? **A:** [auto-pick] Single shared call after either branch. **Why:** DRY; the prune call's semantics are identical regardless of which branch removed the worktree, so duplicating it risks drift.
- **Q:** Should a failure of the new prune call itself raise, or warn-only? **A:** [auto-pick] Warn-only (non-fatal). **Why:** Matches the existing fallback-path behavior at the same call site; the worktree removal itself already succeeded by the time prune runs, so failing the whole call over best-effort cleanup would regress working teardown paths.
- **Q:** Test coverage — real-git end-to-end reproduction of the orphan scenario, or a mocked assertion that `worktree prune` was called? **A:** [auto-pick] Real-git end-to-end, matching the file's existing `list_worktrees`/`remove` test style. **Why:** Actually reproduces the reported bug scenario instead of just asserting a call happened.
- **Q:** Should this task also add proactive reaping of orphaned `.scratch/verify-baseline-*` dirs for long-lived tasks (task worktree never removed)? **A:** [auto-pick] No — out of scope. **Why:** Matches the brief's literal ask (both listed remedies key off task-worktree removal); proactive reaping needs its own liveness-safety design to avoid the exact data-loss pattern issue #100 guards against, and is a distinct disk-hygiene concern from the git-metadata-orphan bug reported here.
