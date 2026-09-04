# Batch: cleanliness-gate-dead-parent-recovery

```yaml
task: "mill-go: done-gate halt path and cleanliness-gate recovery are under-documented"
batch: "cleanliness-gate-dead-parent-recovery"
number: 3
cards: 2
verify: null
depends-on: [2]
```

## Batch Scope

Wires `_parent_branch.check_liveness` / `resolve_dead_parent` (already implemented for `mill-merge`/`mill-merge-in`, #817) into mill-go's two cleanliness call sites — `SKILL.md` step 2b (per-batch, Card 6) and `handoff.md`'s terminal cleanliness gate (task-scoped, Card 7) — so a squash-merged-and-deleted parent branch auto-rebinds on a high-confidence chain resolution instead of crashing on an unresolvable `git diff`. Depends on batch 2 because Card 7 halts through `handoff.md`'s terminal-dirt-gate `BLOCKED:` message, which batch 2's Card 5 already gave a builder-lock-release + `_notify.notify` pair — Card 7 builds its new `fallback`/`cycle` halt text on top of that existing pair rather than re-adding it. Card 6 and Card 7 are grouped in one batch because they implement the same decision (`cleanliness-gate-dead-parent-recovery`) with two structurally different halt mechanisms per call site — reviewing them together keeps the two mechanisms' divergence visible and intentional, exactly the class of cross-site consistency gap the discussion's own round-2 review caught.

## Cards

### Card 6: `SKILL.md` step 2b — dead-parent liveness check and auto-rebind

- **Context:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `SKILL.md`'s `### 2b. Cleanliness gate` section, immediately after the existing line `parent_branch = _parent_branch.resolve(status_path, interactive=False)` and before the `_cleanliness.revert_out_of_scope_drift(...)` call, insert a liveness check that wraps the existing dirt-computation flow:
  1. Call `_parent_branch.check_liveness(parent_branch, git_root)`.
  2. If it returns `True`: proceed to the existing `revert_out_of_scope_drift` call exactly as today, no change.
  3. If it returns `False`: call `_parent_branch.resolve_dead_parent(parent_branch, git_root, cfg)`.
     - **`outcome: "resolved"`:** auto-rebind non-interactively — `_status.update_field(status_path, "parent", resolved_branch)` (reading `resolved_branch` from the returned dict's `branch` field) plus `_status.append_phase(status_path, "self-resolved-dead-parent", _timestamp.now_utc_iso())`, folded into one commit: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: rebind dead parent branch for <batch_name>"`. No push (matches this section's existing no-push-mid-batch convention — the batch's own eventual commit/push covers it). Then retry the `_cleanliness.revert_out_of_scope_drift(worktree_root, task_dir, resolved_branch, git_root)` call once, using `resolved_branch` in place of the original `parent_branch` for the remainder of this cleanliness gate. Proceed normally (continue to the existing `in_scope_dirt is None` / non-empty / empty branches below) using this retry's result.
     - **`outcome: "fallback"` or `outcome: "cycle"`:** route through the section's own existing batch-blocked mechanism — `_status.set_batch_field(status_path, batch_name, "state", "blocked")`, `_status.set_batch_field(status_path, batch_name, "blocked_reason", <fallback-text> | <cycle-text>)`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on <batch_name> — parent branch dead, no resolution"`), then go to *Blocked* (the shared `SKILL.md` `### Blocked` section, which already performs its own `_notify.notify` + builder-lock release as part of its existing defined behavior — do not add a second, redundant release/notify call here). Use `blocked_reason: f"parent branch {parent_branch} no longer exists; no archive-tag chain resolved a successor ({reason})"` for `fallback` (reading `reason` from the returned dict's `reason` field) and `blocked_reason: "parent branch archive-tag chain walk hit its hop cap without resolving a live parent"` for `cycle`.
  4. If the `resolved`-outcome retry (step 3's first bullet) still returns `in_scope_dirt is None`, fall through to the section's existing `in_scope_dirt is None` halt branch unchanged (do not loop further) — this is the existing "parent diff unresolvable" batch-blocked path, already present in the file.
  Do not change the two `signature:` lines immediately below the existing inline-Python block, or the existing `in_scope_dirt` non-empty/empty branches that follow — this card only inserts the new liveness-check-and-rebind logic between the `parent_branch = ...` line and the existing `revert_out_of_scope_drift` call.
- **Commit:** `feat(mill-go): auto-rebind dead parent branch in per-batch cleanliness gate`

### Card 7: `handoff.md` terminal cleanliness gate — dead-parent liveness check and auto-rebind

- **Context:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `handoff.md`'s "**Terminal cleanliness gate.**" section, immediately after the existing line `parent_branch = _parent_branch.resolve(status_path, interactive=False)` and before the `in_scope_dirt = _cleanliness.compute_terminal_dirt(worktree_root, task_dir, parent_branch)` call, insert the same liveness-check-and-rebind shape Card 6 adds to `SKILL.md` step 2b, adapted for this task-scoped (not batch-scoped) call site:
  1. Call `_parent_branch.check_liveness(parent_branch, git_root)`.
  2. If it returns `True`: proceed to the existing `compute_terminal_dirt` call exactly as today, no change.
  3. If it returns `False`: call `_parent_branch.resolve_dead_parent(parent_branch, git_root, cfg)`.
     - **`outcome: "resolved"`:** auto-rebind non-interactively — `_status.update_field(status_path, "parent", resolved_branch)` plus `_status.append_phase(status_path, "self-resolved-dead-parent", _timestamp.now_utc_iso())`, folded into one commit: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: rebind dead parent branch at task completion"`. No push (matches this section's existing no-push-mid-batch convention). Then retry `_cleanliness.compute_terminal_dirt(worktree_root, task_dir, resolved_branch)` once, using `resolved_branch` in place of the original `parent_branch` for the remainder of this gate. Proceed normally (continue to the existing `in_scope_dirt is None` / non-empty / empty branches below) using this retry's result.
     - **`outcome: "fallback"` or `outcome: "cycle"`:** halt via this gate's own existing bare-`BLOCKED:`-message convention (no `blocked_reason` field write — that field belongs to `SKILL.md`'s batch-state bookkeeping, not this task-scoped halt) — insert the same `_notify.notify(...)` and builder-lock-release calls batch 2's Card 5 already added immediately before this gate's existing `in_scope_dirt is None` halt message (do not add a second, redundant pair — reuse that same insertion point), then halt with `BLOCKED: cannot determine in-scope dirt at task completion -- parent branch <parent_branch> no longer exists; <fallback: no archive-tag chain resolved a successor (<reason>)> | <cycle: archive-tag chain walk hit its hop cap without resolving a live parent>. Investigate the parent branch and retry.` Do NOT set `phase: done` (matches the existing sentence already attached to this gate's halts).
  4. If the `resolved`-outcome retry (step 3's first bullet) still returns `in_scope_dirt is None`, fall through to the section's existing `in_scope_dirt is None` halt branch unchanged (do not loop further) — the existing "parent diff unresolvable" message, whose `_notify.notify`/lock-release pair batch 2's Card 5 already added.
  Do not change the existing `in_scope_dirt` non-empty/empty branches that follow, or the re-check-after-self-resolve / still-non-empty halt messages further down this section — this card only inserts the new liveness-check-and-rebind logic between the `parent_branch = ...` line and the existing `compute_terminal_dirt` call.
- **Commit:** `feat(handoff): auto-rebind dead parent branch in terminal cleanliness gate`

## Batch Tests

`verify: null` — both cards edit orchestrator-prose skill files (`SKILL.md`, `handoff.md`), not the underlying `_parent_branch.check_liveness`/`resolve_dead_parent` functions, which already have unit test coverage from the #817 work and are unchanged by this batch. Per `_mill/discussion.md`'s Testing section, this is a TDD candidate only at the manual/integration-verification level (confirming a task worktree whose recorded `parent:` branch has been deleted correctly auto-rebinds or halts instead of crashing) — not something the Python unit-test suite exercises directly.
