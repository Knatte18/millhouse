# Plan: 34 (A) — Config schema cleanup + reviewer registry

```yaml
task: 34 (A) — Config schema cleanup + reviewer registry
slug: config-schema-refactor
approved: false
started: 20260509-153956
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: foundations
    file: 01-foundations.md
    depends-on: []
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
  - number: 2
    name: flip
    file: 02-flip.md
    depends-on: [1]
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
  - number: 3
    name: skills-docs
    file: 03-skills-docs.md
    depends-on: [2]
    verify: null
```

## Shared Decisions

### Decision: Reviewer registry layout

- **Decision:** `wiki/reviewers.yaml` is the registry. Each entry has `type: single | cluster`. `type: single` requires `provider`, `model`, `effort`, optional `tooluse: bool` (default `false`). `type: cluster` requires `workers: { use: <name>, count: <n> }` and `handler: { use: <name> }`. Cluster `use:` references resolve to `type: single` only — no nested clusters. Reviewer names match `[a-z0-9_-]+` (lowercase letters, digits, underscore, hyphen).
- **Rationale:** Locks the registry contract before runtime arrives in tasks 13 (cluster) and 31 (gemini). Validation is eager so operator typos surface at startup.
- **Applies to:** all batches.

### Decision: Roles section replaces `review:`

- **Decision:** `wiki/config.yaml` exposes `roles:`. Keys: `discussion-review`, `plan-review`, `code-review`, `implementer`. Each review role has `batch:` and/or `holistic:` subsections of shape `{rounds: <int>, reviewer: <name|null>}`. Skip semantics: `rounds: 0` OR `reviewer: null` → skip the scope. `code-review` carries `diff_scope_threshold` at role level. `implementer` carries `self_fix_rounds` at role level — no `reviewer:` slot. The boolean `per_batch:` and `holistic:` flags die. The `holistic_effort:` knob dies; effort is encoded in the named reviewer.
- **Rationale:** Symmetric vocabulary across discussion / plan / code; one truth per behaviour.
- **Applies to:** all batches.

### Decision: Atomic schema flip with no compat shim

- **Decision:** Old `review:` keys do NOT coexist with `roles:` in any window. The schema flip and consumer rewire happen in batch 2 in lockstep. No deprecation period, no dual-read.
- **Rationale:** Single-operator wiki; running both schemas is pure churn.
- **Applies to:** batch 2.

### Decision: Spec replaces `MODE` constant

- **Decision:** Reviewer modules no longer drive dispatch via a module-level `MODE = "bulk" | "tool-use"` constant. The new dispatcher (`_reviewer_single.py`) reads `spec["tooluse"]` to choose `_llm_<provider>.run_bulk` vs `run_tool_use`. Every existing `reviewer.MODE` read in the backends becomes `("tool-use" if spec.get("tooluse") else "bulk")`. `_reviewer_test_stub.py` keeps its `MODE = "bulk"` for test compatibility but the new dispatch path consults the spec.
- **Rationale:** A single `_reviewer_single.py` cannot have a static `MODE`; the spec carries the answer.
- **Applies to:** batches 1 and 2.

### Decision: `_reviewer_test_stub` resolves via a hard-coded special case

- **Decision:** `_reviewers.resolve(registry, name)` returns `{"type": "single", "provider": "test_stub", "tooluse": False}` when `name == "test_stub"` without consulting `reviewers.yaml`. `_reviewer_single.run` detects `provider == "test_stub"` and forwards to `_reviewer_test_stub.run` instead of `importlib.import_module(f"_llm_test_stub")`.
- **Rationale:** Tests across `test-review-*-flow.py` already use `load_reviewer("test_stub")`; preserving a zero-config path keeps test setup unchanged.
- **Applies to:** batches 1 and 2.

### Decision: `--max-rounds <N>` clamps both scopes uniformly

- **Decision:** The single CLI flag `--max-rounds <N>` continues to exist on `millpy-review-plan.py` and `millpy-review-code.py`. When set, it clamps both `<role>.batch.rounds` and `<role>.holistic.rounds` to `N` for the invocation. Backends apply the clamp at their per-scope round-cap check sites.
- **Rationale:** Single flag matches today's operator workflow. No demonstrated need to split.
- **Applies to:** batch 2.

### Decision: Skill docs in scope

- **Decision:** Every match for `review\.\(code\|plan\|discussion\)\.` under `plugins/mill/skills/**/*.md` updates to the new `roles.<role>.<scope>.<key>` path. The boolean `holistic: true/false` and `per_batch: true/false` references rewrite to "if `roles.<role>.<scope>.reviewer` is non-null". `holistic_rounds` references rewrite to `roles.<role>.holistic.rounds`. `holistic_effort` references are deleted.
- **Rationale:** Operator-facing docs must not drift from the live schema.
- **Applies to:** batch 3.

### Decision: Migration warning on stale `.millhouse/config.local.yaml`

- **Decision:** `_review_common.load_config` checks the overlay (`local_cfg`) for a top-level `review:` key after deep-merge. If present and truthy, write a one-line stderr warning naming the overlay path and the orphaned keys. Do not crash. The merged cfg is returned unchanged.
- **Rationale:** A cheap nudge to delete stale overlays without breaking the operator's tooling.
- **Applies to:** batch 2.

## All Files Touched

- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/_reviewer_single.py`
- `plugins/mill/scripts/_reviewer_sonnetmax.py`
- `plugins/mill/scripts/_reviewer_sonnetmax_tool.py`
- `plugins/mill/scripts/_reviewers.py`
- `plugins/mill/scripts/millpy-implement-holistic.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/reviewers.yaml`
- `plugins/mill/templates/wiki-config.yaml`
- `plugins/mill/unit_tests/_test_cfg.py`
- `plugins/mill/unit_tests/_test_registry.py`
- `plugins/mill/unit_tests/test-llm-claude.py`
- `plugins/mill/unit_tests/test-millpy-implement-holistic.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-review-cli.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
- `plugins/mill/unit_tests/test-reviewer-modules.py`
- `plugins/mill/unit_tests/test-reviewer-single.py`
- `plugins/mill/unit_tests/test-reviewers.py`
- `wiki/config.yaml`
- `wiki/reviewers.yaml`
