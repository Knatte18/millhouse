# Batch: teardown-reconcile

```yaml
task: Fix spawn lifecycle integrity, agent-mode async assumption, merge-in conflicts, and pre-existing failure validation
batch: teardown-reconcile
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-abandon.py test-cleanup.py
depends-on: [1]
```

## Batch Scope

Delivers the teardown-side integrity fixes from #543a and #543b: abandon and
cleanup delete the remote branch (making re-spawn of the same slug a clean
fast-forward), and cleanup gains a reconciliation backstop that resets a task
left `active` in Home.md with no real artifacts back to unclaimed. Concentrated
in `millpy-abandon.py` and `millpy-cleanup.py`. Depends on batch 1 so the
spawn/teardown subsystem changes land in order; no file overlap with batch 1.

Batch-local decision: remote-branch deletion is idempotent — a missing remote ref
is treated as success (see Shared Decision "Remote-branch delete tolerates a
missing ref"). Reconciliation only auto-resets the plain `active` marker, never
the live PR states `ready-to-merge` / `pr-pending`.

## Cards

### Card 5: Abandon deletes the remote branch instead of pushing a marker
- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-abandon.py`
  - `plugins/mill/unit_tests/test-abandon.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-abandon.py` `main`, keep the local `_status.append_phase(..., "abandoned", ...)` + `git add` + `git commit -m "task: abandon {slug}"` steps, but replace the final `git push` (which currently pushes the abandon-marker commit to `origin/<branch>`) with `git -C <active_hub> push origin --delete <branch>`, where `<branch>` is the task branch read from the status.md `branch:` field already loaded into `info` (`_status.read_status`). Treat a non-zero exit whose stderr indicates the remote ref does not exist as success (idempotent); surface any other non-zero exit as an error. Update the success message so it no longer implies a marker commit was pushed. Add a test in `test-abandon.py` mocking `_subprocess_util.run` asserting the final git invocation is `push origin --delete <branch>` (not a bare `push`) and that a "remote ref does not exist" stderr is tolerated.
- **Commit:** `fix(abandon): delete origin branch instead of pushing abandon marker (#543)`

### Card 6: Cleanup deletes the remote branch after local deletion
- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-cleanup.py`, after the successful local branch deletion in `_apply_worktree_record` (the `git branch -D <record.branch>` block) add `git -C <hub_root> push origin --delete <record.branch>`; do the same in `_apply_inplace_record` after its `git branch <delete_flag> <task_branch>` block, using `task_branch`. Guard each on a non-empty branch name. Treat a "remote ref does not exist" stderr as success (idempotent); print other non-zero exits to stderr as a non-fatal warning (matching the existing local-branch-delete warning posture). Add tests in `test-cleanup.py` mocking `_subprocess_util.run` asserting both helpers issue `push origin --delete <branch>` after the local delete and tolerate a missing remote ref.
- **Commit:** `fix(cleanup): delete origin branch on teardown (#543)`

### Card 7: Reconcile orphaned `active` markers to unclaimed
- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Promote the existing "orphan Home.md marker" detection in `build_plan` (the loop over `home_tasks` that appends `orphan Home.md marker: ...` when `marker in ("active","ready-to-merge","pr-pending") and slug not in active_slugs and slug not in wts_slugs_on_disk`) from report-only into an actual reset for the narrow safe case. Add a `to_reset_unclaimed: list[str]` field to `CleanupPlan` and populate it with slugs whose marker is exactly `"active"` (NOT `ready-to-merge`/`pr-pending` — those are live PR states) AND that have no worktree on disk AND no portal junction (reuse `_scan_orphan_portals` / the existing `portals/` enumeration — do not hand-roll a junction probe) AND no local branch (add a `git -C <hub_root> branch --list <branch>` probe via `_subprocess_util.run` — the one signal not already enumerated). In the apply phase, reset each such slug via `wiki.set_phase(slug, None)` and print an ASCII `RECONCILE: <slug> active marker reset to unclaimed (no worktree/branch/portal)` line; include it in `_print_plan`. Add tests in `test-cleanup.py`: (a) an `active` task with no worktree/branch/portal is reset to `None`; (b) a `ready-to-merge`/`pr-pending` orphan is NOT auto-reset; (c) an `active` task that still has a worktree (or branch, or portal) is left untouched.
- **Commit:** `feat(cleanup): reconcile orphaned active markers to unclaimed (#543)`

## Batch Tests

`verify:` runs `test-abandon.py` (abandon now issues `push origin --delete` and tolerates a
missing ref) and `test-cleanup.py` (both cleanup helpers delete the remote branch after the
local delete; reconciliation resets only safe orphaned `active` markers and leaves live PR
states and artifacted tasks untouched). Both are existing files extended in place; each card
ends green. Scope is the teardown subsystem only — focused `--only` is correct.
