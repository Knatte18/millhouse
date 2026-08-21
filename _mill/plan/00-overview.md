# Plan: mill-go: baseline-stage timeout/cold-build cost and finalize dirty-tree false positive

```yaml
task: "mill-go: baseline-stage timeout/cold-build cost and finalize dirty-tree false positive"
slug: mill-go-finalize-and-baseline-stage-bugs
approved: true
started: "20260821-091559"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: dirty-tree-briefs-exclusion
    file: 01-dirty-tree-briefs-exclusion.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
  - number: 2
    name: baseline-build-once-step
    file: 02-baseline-build-once-step.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-implement.py
  - number: 3
    name: baseline-dispatch-background-skill
    file: 03-baseline-dispatch-background-skill.md
    depends-on: []
    verify: "PYTHONPATH= grep -q millpy-bg.py plugins/mill/skills/mill-go-base/SKILL.md"
```

## Shared Decisions

### Decision: three independent batches, no depends-on edges

- **Decision:** Each batch fixes a distinct, file-disjoint piece of the two bundled bugs (`_mill/discussion.md`'s Bug A / Bug B split) and touches zero files any other batch touches. All three declare `depends-on: []`.
- **Rationale:** Batch 1 (`_implementer_common.py` + its test file) fixes the finalize dirty-tree false positive (Bug B). Batch 2 (`millpy-implement.py` + config templates + its test file) fixes the baseline cold-build cost (Bug A, part 1). Batch 3 (`mill-go-base/SKILL.md` prose only) fixes the baseline dispatch timeout ceiling (Bug A, part 2). Zero file overlap between any pair, so there is no ordering constraint and no shared `Context:` to justify merging any two.
- **Applies to:** all batches.

### Decision: reuse `_verify_baseline._run_verify_in` directly, no new function

- **Decision:** Batch 2's build-once step calls the existing `_verify_baseline._run_verify_in(command, cwd) -> tuple[int, str]` helper directly from `millpy-implement.py`'s `_run_baseline_stage` — no new function is added to `_verify_baseline.py`.
- **Rationale:** `_run_baseline_stage` already calls three other leading-underscore `_verify_baseline` helpers directly (`_checkout_parent_branch`, `_link_dependency_dirs`, `_run_module_wide_verify_algorithm`) — cross-module use of `_verify_baseline`'s module-private helpers from `millpy-implement.py` is the file's own established convention, not a new pattern. `_run_verify_in` already does exactly what a build-once step needs (run a shell command in a given cwd, return `(rc, combined_output)`), so adding a wrapper function would be a pure pass-through with no behavior of its own.
- **Applies to:** baseline-build-once-step.

### Decision: `mill-config.yaml` key addition is safe mid-flight (wiki-config-mutation bootstrap)

- **Decision:** Batch 2 adds a new optional `pipeline.baseline_prepare_cmd: null` key to both `plugins/mill/templates/mill-config.yaml` and this hub's own `mill-config.yaml`. This is a key *addition*, not a removal/rename, so the `wiki-config-mutation` validator's condition (b) (provably-unused via zero grep hits) does not apply — condition (a) (a bootstrap card explaining why the change is safe mid-flight) is used instead, per this task's own Card 4.
- **Rationale:** The key is read only via `(cfg.get("pipeline") or {}).get("baseline_prepare_cmd")` (see Card 3), which returns `None` for every existing hub whose config doesn't declare the key at all — identical to the value it would read before this key existed. No existing consumer of `cfg["pipeline"]` breaks: nothing iterates `pipeline`'s keys exhaustively or rejects unknown keys. The change is purely additive and inert until an operator opts in by setting a non-null value.
- **Applies to:** baseline-build-once-step (Card 4 specifically).

## All Files Touched

- `mill-config.yaml`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
