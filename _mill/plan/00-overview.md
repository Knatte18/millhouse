# Plan: mill-plan: entry-gate wait for upstream mill-start misses discussion-gap-fix-r{N} and races the pinning commit

```yaml
task: 'mill-plan: entry-gate wait for upstream mill-start misses discussion-gap-fix-r{N} and races the pinning commit'
slug: mill-plan-entry-gate-wait-trigger-gaps
approved: false
started: 20260918-175252
parent: main
root: ""
verify: null
discussion_sha: 070d102d3c44af1d67ae30080a42e1c108ef36b1
```

## Batch Index

```yaml
batches:
  - number: 1
    name: entry-gate-wait-fixes
    file: 01-entry-gate-wait-fixes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-phase-wait.py
```

## Shared Decisions

### Decision: additive-only extension to `_phase_wait.build_wait_command`

- **Decision:** the new `clean_tree_root`/`clean_tree_paths` keyword-only parameters on `build_wait_command` default to `None`, and the function must render byte-identical output to today's when both are omitted. No call site outside `mill-plan/SKILL.md`'s Entry-gate wait (in particular, `mill-go-base/SKILL.md`'s own copy of this wait, and every existing unit test that calls `build_wait_command` with only the original four positional arguments) is edited by this task.
- **Rationale:** the three source issues (#1041, #1028, #1029) are scoped to mill-plan's own wait for mill-start; widening `mill-go-base/SKILL.md`'s analogous wait for `phase: planned` to the same clean-tree gating is explicitly out of scope (see `_mill/discussion.md`'s Decisions section) and left as a candidate follow-up task.
- **Applies to:** all batches (there is only one batch in this plan).

### Decision: mill-plan's trigger list stays independently maintained, not shared with mill-go-base's

- **Decision:** mill-plan's Entry-gate wait keeps its own inline `matches_wait_trigger(phase, {"discussing"}, [...])` call with its own 2-pattern list (`discussion-fix-r{N}`, `discussion-gap-fix-r{N}`), widened in place. This task does not introduce a shared constant or helper between mill-plan's list and mill-go-base's structurally similar but distinct 4-pattern list (which also covers `plan-review-r{N}`/`plan-fix-r{N}`, phases mill-start never writes).
- **Rationale:** the two lists cover genuinely different phase vocabularies (mill-start's vs. mill-plan's own phases) — mirroring `mill-go-base/SKILL.md`'s pattern list value-for-value is correct parity, but factoring out a shared constant across two unrelated phase vocabularies would be speculative generalization beyond this task's three source issues.
- **Applies to:** entry-gate-wait-fixes.

## All Files Touched

- `plugins/mill/scripts/_phase_wait.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/unit_tests/test-phase-wait.py`
