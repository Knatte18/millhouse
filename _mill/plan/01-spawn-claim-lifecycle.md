# Batch: spawn-claim-lifecycle

```yaml
task: Fix spawn lifecycle integrity, agent-mode async assumption, merge-in conflicts, and pre-existing failure validation
batch: spawn-claim-lifecycle
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-spawn-core.py test-millpy-spawn.py test-millpy-claim.py
depends-on: []
```

## Batch Scope

Delivers the spawn-side and claim-side integrity fixes from #543b and the #544
`[s]` documentation cleanup, all concentrated in the spawn/claim subsystem
(`_spawn_core.py`, `millpy-spawn.py`, `millpy-claim.py`) plus the `mill-groom`
status table. Two structural guarantees ship here regardless of how hard the
over-claim race is to reproduce: (1) the multi-select claim only ever touches the
slugs the user selected, pinned by a regression test, and (2) spawn fails before
creating any artifact when `origin/<branch>` already exists, and unwinds every
artifact it did create if a later step fails. The teardown-side reconciliation
backstop is batch 2. No external interface is produced for later batches; batch 2
depends on this batch only to keep the spawn/teardown subsystem changes ordered.

Batch-local decision: the over-claim fix is **evidence-driven** — the implementer
must locate the actual divergence in the selection -> `source_slugs` ->
`merge_tasks` chain before changing behavior, and the regression test encodes the
selection->claim contract deterministically so it stays meaningful even if the
original live race was environmental.

## Cards

### Card 1: Locate and fix multi-select spawn over-claim
- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/wiki/_store.py`
- **Edits:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/unit_tests/test-spawn-core.py`
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Trace the multi-select claim chain — `pick_task_single_or_multi` and `_prompt_numbered_multi` in `_spawn_core.py`, then `multi_select_groom_then_claim` (the `wiki.merge_tasks(remove_slugs=source_slugs, set_phase=(merged_slug, "active"))` call), and the `claim_in_wiki` / early multi-mode claim in `millpy-spawn.py` `main` (the multi branch around the `source_slugs = [t["slug"] for t in picked]` line). Identify why a slug the user did NOT select can reach `set_phase(..., "active")` (the reported symptom: an un-picked task flipped to `active` with no artifacts) and close it so the set of slugs claimed/removed equals exactly `picked`. Add a regression test in `test-spawn-core.py` (and a CLI-level assertion in `test-millpy-spawn.py` if the divergence is in `millpy-spawn.py`) driving the reported scenario: two unmarked candidates, user selects exactly one, assert the other remains `status is None` and is never passed to `set_phase`/`merge_tasks`. The card must end with `verify:` green.
- **Commit:** `fix(spawn): multi-select claims only user-selected slugs (#543)`

### Card 2: Drop the retired `[s]` spawn-ready references
- **Context:**
  - `plugins/mill/scripts/wiki/_parse.py`
  - `plugins/mill/scripts/wiki/_render.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/millpy-claim.py`
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/skills/mill-groom/SKILL.md`
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
  - `plugins/mill/unit_tests/test-millpy-claim.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** The V3 wiki backend already retires `[s]` (`wiki/_parse.py` collapses `[s]` -> `None`, `wiki/_render.py` never emits an `[s]` marker), so only stale strings remain. Remove every `[s]`/"spawn-ready" reference: in `millpy-spawn.py` the module docstring, the `--slug` argparse help ("must be unmarked or [s]"), and the "No pickable tasks. Mark a task [s] or leave one unmarked" message (align it to the `pick_task_single` `BacklogEmpty` wording "Leave one unmarked"); in `millpy-claim.py` the module docstring, the `--slug` help, and the "Mark a task [s]" message; in `_spawn_core.py` the module/API docstrings claiming a nonexistent "[s] fast-path"; in `mill-groom/SKILL.md` the status-table row for `"s"` (spawn-ready) and the `[s]` list-suffix and action-menu references. Add assertions in `test-millpy-spawn.py` and `test-millpy-claim.py` that the spawn/claim `--slug` help text and the empty-backlog message contain no `[s]` substring. Do NOT modify `wiki/_parse.py` / `wiki/_render.py` — they are correct as-is.
- **Commit:** `docs(spawn): drop retired [s] spawn-ready references (#544)`

### Card 3: Pre-check `origin/<branch>` before spawn creates artifacts
- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_worktree.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-spawn.py` `main`, after `branch_name` is computed and before the first artifact-creating call (`_worktree.create`), probe the remote with `git ls-remote --exit-code --heads origin <branch_name>` via `_subprocess_util.run`. If the ref exists (exit 0), exit non-zero with a clear ASCII message instructing the operator to delete the surviving remote branch (e.g. via teardown) before re-spawning — and create NO worktree, junction, local branch, or wiki claim. A genuinely-absent ref (exit 2) proceeds normally; treat other non-zero exits (network) as a soft skip that proceeds (do not block spawn on an unreachable remote). Add a test in `test-millpy-spawn.py` mocking `_subprocess_util.run` so `ls-remote` reports the branch exists, and assert spawn aborts before any worktree/junction/claim side effect.
- **Commit:** `feat(spawn): pre-check origin branch before creating artifacts (#543)`

### Card 4: Roll back partial spawn on failure
- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_setup.py`
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Wrap the side-effecting span of `millpy-spawn.py` `main` (from the wiki claim through `write_initial_status`'s `--set-upstream` push) in a try/except that, on any failure, unwinds the artifacts created so far in LIFO order and then re-raises / exits non-zero: remove the `.vscode` settings written by the color step, strip the `.active` junction + hub active indicator, the portal junction, and the hub links (`.wiki`/`.portals`) via `_junction.remove` / the `_setup` teardown helper, call `_worktree.remove_safe(worktree_path, cwd=git_root, junctions_cfg=...)` (which also drops the local branch), and revert the Home.md claim via `wiki.set_phase(slug, None)`. Junctions MUST be stripped before any directory removal (never raw `rmtree`). Add a test in `test-millpy-spawn.py` that forces the `write_initial_status` push to fail (mock `_subprocess_util.run`) and asserts `_worktree.remove_safe` and `wiki.set_phase(slug, None)` are invoked and no artifact is left registered.
- **Commit:** `feat(spawn): roll back partial worktree/junctions/claim on spawn failure (#543)`

## Batch Tests

`verify:` runs the three spawn/claim unit-test files: `test-spawn-core.py` (multi-select
selection->claim contract from card 1, and the existing pick-filter coverage),
`test-millpy-spawn.py` (the `[s]`-free help/message assertions, the `origin/<branch>`
pre-check abort, and the rollback-on-push-failure path), and `test-millpy-claim.py` (the
`[s]`-free help/message assertions). All three are existing files extended in place; every
card ends green. Scope is the spawn/claim subsystem only — no cross-cutting helper is
touched, so the focused `--only` list is correct.
