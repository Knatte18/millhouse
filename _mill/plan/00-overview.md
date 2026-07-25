# Plan: Batch review/verify pipeline doesn't account for cross-batch state changes

```yaml
task: Batch review/verify pipeline doesn't account for cross-batch state changes
slug: mill-review-verify-pipeline-state-gaps
approved: false
started: "20260725-112456"
parent: hanf/linux-port-more
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: review-code-moves-suppression
    file: 01-review-code-moves-suppression.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-code-flow.py
  - number: 2
    name: review-common-parse-deletes
    file: 02-review-common-parse-deletes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-common.py
  - number: 3
    name: iter-batch-verifies-cross-batch-filter
    file: 03-iter-batch-verifies-cross-batch-filter.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-dag.py
  - number: 4
    name: verify-replay-callers-wiring
    file: 04-verify-replay-callers-wiring.md
    depends-on: [3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-fix.py
```

## Shared Decisions

### Decision: metadata-driven cross-batch verify suppression, not disk state

- **Decision:** Detecting that a batch's `verify:` command references a target a later batch reverted is done by matching normalized command tokens against the plan's own `Deletes:`/`Moves:` declarations (per-batch, DAG-order-aware), never by checking live filesystem existence.
- **Rationale:** A disk-existence check would false-positive on a command that creates its own output path before consuming it (e.g. `mkdir -p out && go build -o out/app ./cmd/app`). Matching against plan-declared author intent avoids that failure mode entirely. See `_mill/discussion.md` Decision 2 for the full analysis, including the accepted limitations (exact-match only, no directory-containment; all-or-nothing suppression per command; raw-string lexical matching with no cwd/root coordinate resolution).
- **Applies to:** `iter-batch-verifies-cross-batch-filter`, `verify-replay-callers-wiring`.

### Decision: `iter_batch_verifies()` is the single choke point for cross-batch verify filtering

- **Decision:** Both the "target removed by a later batch" filter and the "batch not yet approved" filter live inside `_plan_dag.iter_batch_verifies()` itself — not in a wrapper, not duplicated per caller. Every caller (`millpy-fix.py` holistic prepare/finalize, `mill-merge-in` Step 4) gets the corrected behavior through the same function.
- **Rationale:** `iter_batch_verifies()`'s contract is "replay exactly what survives to matter" from the caller's perspective; no caller wants the unfiltered list. See `_mill/discussion.md` Decision 3.
- **Applies to:** `iter-batch-verifies-cross-batch-filter`, `verify-replay-callers-wiring`.

### Decision: new `status_path` kwarg is strictly additive

- **Decision:** `iter_batch_verifies(plan_dir, hub_root, git_root, *, status_path: Path | None = None)`. Omitting `status_path` reproduces today's behavior byte-for-byte (no approved-state filtering, and Decision 2's later-removal scan runs unconditionally over every strictly-later batch regardless of state). Passing it activates both the approved-state filter AND narrows Decision 2's scan to only count a later batch's declared removal once that later batch's own state is `"approved"`.
- **Rationale:** Backward compatibility for any future caller that doesn't have a `status_path` to hand, and a single flag that turns on the full, mutually-consistent state-aware behavior rather than two independently-toggleable half-behaviors. See `_mill/discussion.md` Decision 4 and its composition note under Decision 2.
- **Applies to:** `iter-batch-verifies-cross-batch-filter`, `verify-replay-callers-wiring`.

### Decision: dependency direction — `_plan_dag.py` may import `_review_common.py` and `_status.py`, never `_plan_validate.py`

- **Decision:** The new `parse_deletes()` per-batch parser is added to `_review_common.py` (not `_plan_validate.py`, which already has a private `_parse_deletes_only` doing similar work). `_plan_dag.py` imports `parse_deletes` and the existing `parse_moves` from `_review_common.py`, and imports `_status` for `read_batches`.
- **Rationale:** `_plan_validate.py` already imports `_plan_dag.py` (`import _plan_dag`). `_plan_dag.py` importing back from `_plan_validate.py` would be circular. `_review_common.py` and `_status.py` have zero dependency on `_plan_dag.py` or `_plan_validate.py`, so `_plan_dag.py` depending on them introduces no cycle. See `_mill/discussion.md` Decision 2's Rejected bullet.
- **Applies to:** `review-common-parse-deletes`, `iter-batch-verifies-cross-batch-filter`.

### Decision: visible, counted skips — no silent drops

- **Decision:** Every batch `iter_batch_verifies()` filters out (for either new reason) must be attributable and reported by its caller: `millpy-fix.py` prints a `[millpy-fix] skipped <batch_name>: <reason>` stderr line per dropped batch; `mill-merge-in` Step 4 extends its existing allowlist `skipped` counter with two new per-reason counts in the final report line.
- **Rationale:** A verify that never ran must never look identical, in the report, to one that ran and passed. See `_mill/discussion.md` Decision 5.
- **Applies to:** `verify-replay-callers-wiring`.

## All Files Touched

- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_plan_dag.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-plan-dag.py`
- `plugins/mill/unit_tests/test-millpy-fix.py`
