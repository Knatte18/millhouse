# Plan: Fix spawn lifecycle integrity, agent-mode async assumption, merge-in conflicts, and pre-existing failure validation

```yaml
task: Fix spawn lifecycle integrity, agent-mode async assumption, merge-in conflicts, and pre-existing failure validation
slug: mill-spawn-and-workflow-integrity
approved: false
started: 20260625-070609
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: spawn-claim-lifecycle
    file: 01-spawn-claim-lifecycle.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-spawn-core.py test-millpy-spawn.py test-millpy-claim.py
  - number: 2
    name: teardown-reconcile
    file: 02-teardown-reconcile.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-abandon.py test-cleanup.py
  - number: 3
    name: verify-and-implementer
    file: 03-verify-and-implementer.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py
  - number: 4
    name: dispatch-and-mergein-docs
    file: 04-dispatch-and-mergein-docs.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-merge-in-subagent.py
```

## Shared Decisions

### Decision: ASCII-only stdout

- **Decision:** All `print()` / `_log()` / stderr text added or changed in this task uses ASCII only — render `—` as ` -- ` and `->` as ` -> `. No non-ASCII in any message string.
- **Rationale:** Windows cp1252 stdout crashes on non-ASCII (CLAUDE.md hard rule). Several cards add new user-facing messages (pre-check failure, remote-delete tolerance, reconciliation reset).
- **Applies to:** all batches

### Decision: Wiki mutations only through `_client` / `set_phase`

- **Decision:** Any change to a task's Home.md claim state (rollback-revert in batch 1, reconciliation reset in batch 2) goes through `wiki.set_phase(slug, None)` — never by editing `Home.md` in the wiki clone, never `cd .wiki/`.
- **Rationale:** CLAUDE.md "Wiki access" invariant; the daemon serializes and pushes wiki writes.
- **Applies to:** spawn-claim-lifecycle, teardown-reconcile

### Decision: Junction-safe teardown

- **Decision:** Any filesystem teardown (spawn rollback, reconciliation) strips junctions first via `_worktree.remove_safe` / `_junction.remove`; never a raw `shutil.rmtree` / `rmdir /s` over a worktree containing `.wiki`/`.portals`/`.active` junctions.
- **Rationale:** CLAUDE.md path invariant — raw deletion follows junctions and wipes the shared wiki/portals targets.
- **Applies to:** spawn-claim-lifecycle, teardown-reconcile

### Decision: Remote-branch delete tolerates a missing ref

- **Decision:** Every `git push origin --delete <branch>` treats a non-zero exit whose stderr indicates the remote ref does not exist (`remote ref does not exist` / `unable to delete ... remote ref does not exist`) as success; any other non-zero exit is surfaced as an error.
- **Rationale:** Teardown must be idempotent — re-running abandon/cleanup, or cleaning a task whose remote was never pushed, must not fail.
- **Applies to:** teardown-reconcile

### Decision: Unit-test fixtures

- **Decision:** All tests use in-memory / tempfile fixtures and mock `_subprocess_util.run` / git / wiki / verify subprocess calls; no real git, network, or LLM. Run via `run-all.py --only <basenames>`; extend the existing `test-*.py` files named per card rather than creating new ones.
- **Rationale:** Matches repo unit-test conventions (`plugins/mill/unit_tests/`), keeps `verify:` scoped and fast.
- **Applies to:** all batches

### Decision: Verify command shape and scope

- **Decision:** Every non-null `verify:` starts with the literal `PYTHONPATH= ` prefix and uses `run-all.py --only <files>` scoped to the tests the batch touches.
- **Rationale:** mill-v2 Python-project rule (CLAUDE.md "Verify command shape"); avoids loading stale cache modules and avoids the multi-minute full suite.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_spawn_core.py`
- `plugins/mill/scripts/millpy-abandon.py`
- `plugins/mill/scripts/millpy-claim.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/scripts/millpy-spawn.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-groom/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/templates/merge-in-conflict-brief.md`
- `plugins/mill/templates/plan-overview.md`
- `plugins/mill/unit_tests/test-abandon.py`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-claim.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-millpy-spawn.py`
- `plugins/mill/unit_tests/test-spawn-core.py`
