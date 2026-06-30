# Plan: Fix discussion review round-cap, daemon cold-start, and nits-only no-op in finalize

```yaml
task: Fix discussion review round-cap, daemon cold-start, and nits-only no-op in finalize
slug: mill-review-and-finalize-gaps
approved: true
started: 20260630-190522
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: discussion-review-round-cap-extension
    file: 01-discussion-review-round-cap-extension.md
    depends-on: []
    verify: null
  - number: 2
    name: wiki-cold-daemon-retry
    file: 02-wiki-cold-daemon-retry.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-marker.py test-millpy-implement.py test-millpy-fix.py
  - number: 3
    name: nits-only-no-op-success
    file: 03-nits-only-no-op-success.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-fix.py
```

## Shared Decisions

### Decision: each of the three gaps is its own batch, sequenced only to avoid a shared-test-file conflict

- **Decision:** the three GitHub-issue-derived gaps (#578 round-cap, #579 cold-daemon, #582 nits-only no-op) are functionally and logically independent — no shared helper functions, no shared state, no ordering constraint between the fixes themselves. Batch 1 (`plugins/mill/skills/mill-start/SKILL.md` only) has no dependency. Batch 3 carries `depends-on: [2]` (added during plan review round 1), but this is a coordination artifact, not a logical dependency: Batch 2's Card 4 and Batch 3's Card 6 both gained test coverage in `test-millpy-fix.py`, so Batch 3 is sequenced after Batch 2 purely to avoid a same-file parallel-modify conflict.
- **Rationale:** confirmed via direct read during discussion that the three fixes share no helper functions, no shared state, and no ordering constraint. Batches 1 and 2 remain fully parallel; Batch 3's sequencing after Batch 2 costs one batch's worth of wall-clock but avoids two batches editing the same test file with no DAG edge between them (the `parallel-modifies-overlap` plan-validator class of error).
- **Applies to:** all batches.

### Decision: exception type discipline — never collapse `wiki.WikiStartupError` into `_marker.MarkerError`

- **Decision:** an exhausted wiki-daemon retry must propagate as the original `wiki.WikiStartupError` (a subclass of `wiki.WikiError`), never wrapped or re-raised as `_marker.MarkerError`.
- **Rationale:** `millpy-bg.py` already has a correct, separate `except _wiki_mod.WikiError` handler (printing "wiki unreachable") ahead of its `except _marker.MarkerError` handler (printing "non-task worktree -- switch terminals"). Wrapping the daemon failure as `MarkerError` would route it into the wrong handler and give the operator a misleading diagnosis. This was caught and corrected during discussion review (round 1) — see `_mill/discussion.md` Q&A log.
- **Applies to:** batch 2.

### Decision: do not widen the in-process dirty-tree gate's reach in this task

- **Decision:** `_implementer_common._in_scope_dirty_stuck()` stays a no-op on `millpy-fix.py`'s actual call path (it already is today, since `millpy-fix.py` never passes `task_dir`/`parent_branch`). This task does not thread those parameters through `millpy-fix.py`'s CLI to make the gate reachable there.
- **Rationale:** confirmed during discussion review (round 3) that the real backstop for stray-uncommitted-residue from a nits-only fixer pass is mill-go's Handoff-time terminal cleanliness gate (`mill-go/SKILL.md:711-720`), which already covers this regardless of this task's change. Wiring two new parameters through `millpy-fix.py`'s CLI is a separate, non-trivial scope expansion not requested by #582.
- **Applies to:** batch 3.

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_marker.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-marker.py`
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
