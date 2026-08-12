# Batch: mill-merge-in-and-conflict-brief

```yaml
task: 'mill-merge/merge-in: squash non-ff rejection, stale-worktree logic, parent-branch detection, conflict resolution'
batch: mill-merge-in-and-conflict-brief
number: 3
cards: 2
verify: null
depends-on: [1]
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

Wires #817's liveness check into `mill-merge-in/SKILL.md`'s own independent `_parent_branch.resolve()` call site (Card 7), and adds #816's required post-resolution self-verification instruction to `templates/merge-in-conflict-brief.md` (Card 8). Both cards live in this batch because they are the two remaining small, mutually-independent edits outside `mill-merge/SKILL.md` (batch 2) that this task's discussion requires, and neither shares meaningful `Context:` with the other beyond both belonging to the mill-merge-in workflow's surface area. Card 7 depends on batch 1's `_parent_branch.check_liveness` / `resolve_dead_parent`. `verify: null` — #817's wiring here is exercised by batch 4's integration tests (against the underlying `_parent_branch` functions, not this prose) and #816 has no automated test per `_mill/discussion.md`'s `testing-approach` Decision (prompt text, verified by reading the rendered template).

## Cards

### Card 7: #817 — liveness check wiring in mill-merge-in Entry step 2

- **Context:**
  - `plugins/mill/scripts/_parent_branch.py`
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `## Entry` step 2, immediately after the existing sentence "If `mill-merge-in` is being called from `mill-merge`'s auto-merge path, pass `interactive=False` and propagate the raised `ParentBranchError` -- `expected_slug=slug` applies in both the interactive and non-interactive forms of the call.", append a new paragraph:
    ```markdown
    **Liveness check (#817):** after `resolve(...)` above returns a `parent_branch` successfully, verify it is still live: `_parent_branch.check_liveness(parent_branch, git_root)` (same call `mill-merge/SKILL.md` Entry Step 4 makes — see that step's own "Liveness check (#817)" paragraph for the exact bash invocation and the JSON shape returned).
    If alive, continue as before.
    If dead, call `_parent_branch.resolve_dead_parent(parent_branch, git_root, cfg)` and apply the identical halt/report/confirm/rebind behavior documented in `mill-merge/SKILL.md` Entry Step 4's "Liveness check (#817)" paragraph: report the `resolved` or `fallback` outcome and require operator confirmation before continuing (the `cycle` outcome always halts outright, no confirmation prompt), then on confirmation rebind `status.md`'s `parent:` row via `_status.update_field(status_path, "parent", resolved_branch)`, commit, push, and use `resolved_branch` as `parent_branch` for the remainder of this run.
    This check runs identically whether `mill-merge-in` is invoked standalone or dispatched from `mill-merge`'s Step 2 — `mill-merge-in` reads the same `status_path` independently via its own `resolve()` call, and must not skip this check just because `mill-merge`'s own Entry Step 4 may have already performed it moments earlier for its own call site. The redundancy is harmless: `check_liveness` is a single read-only `git ls-remote`.
    ```
  - `git_root` and `cfg` referenced above are the same variables already in scope for this skill's Entry step 1 (`_marker.slug_from_branch(git_root, wiki_path, cfg)`) — no new resolution needed.
- **Commit:** `feat(mill): wire dead-parent-branch liveness check into mill-merge-in Entry step 2 (#817)`

### Card 8: #816 — conflict-brief self-verification instruction

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/merge-in-conflict-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Insert a new numbered step 8 immediately after the existing step 7 (the "For UD conflicts..." block, ending "...Do not silently keep the modification.") and immediately before the "Never use `git checkout --ours`..." paragraph that currently precedes `## Report`:
    ```markdown
    8. Before reporting `{"status":"success"}` (with or without `discarded`), re-read each file listed in Conflicting files in full and explicitly verify no contradictory losing-side claims survive the resolution — e.g. a stale value from one side of the conflict left alongside the correct value from the other side, or a claim that only made sense before the other side's edit was applied.
       If you find a contradiction you missed, fix it before reporting.
       If you find a contradiction you cannot confidently resolve, report `{"status":"stuck","stuck_type":"logic","reason":"self-verification found an unresolved contradiction in <file>: <description>"}` instead of `{"status":"success"}`.
    ```
  - The existing "Never use `git checkout --ours`..." paragraph and the `## Report` section itself are otherwise unchanged.
- **Commit:** `feat(mill): require conflict-resolution self-verification before success report (#816)`

## Batch Tests

`verify: null`. Card 7's liveness-check wiring exercises the same `_parent_branch.check_liveness` / `resolve_dead_parent` functions batch 4's integration tests already cover directly — no separate test needed for this second call site's prose. Card 8 is prompt text with no executable logic to assert against; per `_mill/discussion.md`'s `testing-approach` Decision it is verified by reading the updated `merge-in-conflict-brief.md` for correct placement and wording.
