# Plan: (B) — Size-based reviewer switch (mechanism + configurable target)

```yaml
task: "(B) — Size-based reviewer switch (mechanism + configurable target)"
slug: review-large-prompt-switch
approved: true
started: 20260513-142213
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: core-helper
    file: 01-core-helper.md
    depends-on: []
    verify: null

  - number: 2
    name: backend-wiring
    file: 02-backend-wiring.md
    depends-on: [1]
    verify: null

  - number: 3
    name: unit-tests
    file: 03-unit-tests.md
    depends-on: [1]
    verify: python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: token-estimation

- **Decision:** Use `len(prompt_text) // 4000` to produce an estimated kilo-token count. Compare against `threshold_ktok` (default 100). The switch fires when `estimated_ktok >= threshold_ktok`.
- **Rationale:** Char/4 is within ~10% of actual Claude token count for English + code. `// 4000` (not `// 4`) yields kilo-tokens directly so the comparison reads naturally against `threshold_ktok: 100`. No SDK dependency, instant, zero latency on every holistic review that stays below threshold.
- **Applies to:** core-helper, unit-tests

### Decision: holistic-only-scope

- **Decision:** The switch applies only in holistic review paths. No `large_prompt` key is defined or checked under `batch:` scopes.
- **Rationale:** Task spec says `roles.<role>.holistic.large_prompt`. Per-batch prompts are small by design and have no documented failure case.
- **Applies to:** core-helper, backend-wiring

### Decision: tooluse-coercion

- **Decision:** When the override spec's `tooluse` differs from the original spec's `tooluse`, preserve the original `tooluse` flag in the effective spec and log a notice to stderr. The override's `tooluse` field is ignored.
- **Rationale:** The `mode` variable and artefact section are built from `spec.get("tooluse")` before `prompt_text` is rendered. By switch time the prompt is already formatted for a specific mode; changing `tooluse` at that point would mismatch prompt format with LLM dispatch.
- **Applies to:** core-helper, unit-tests

### Decision: ascii-only-stderr

- **Decision:** All `print()` / stderr log strings are ASCII only. Em-dash becomes ` -- `; right-arrow becomes ` -> `.
- **Rationale:** Windows cp1252 terminals crash on non-ASCII stdout/stderr.
- **Applies to:** all batches

### Decision: cluster-rejection

- **Decision:** The helper raises `ReviewError` when the override spec resolves to a cluster type. `validate_role_refs` also flags cluster-type `large_prompt.reviewer` entries as errors.
- **Rationale:** `_reviewer_single.py` already rejects cluster specs at runtime. Catching this at config-validation time and in the helper prevents a confusing runtime error deep inside a review cycle.
- **Applies to:** core-helper, unit-tests

## All Files Touched

- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/_reviewers.py`
- `plugins/mill/templates/wiki-config.yaml`
- `plugins/mill/unit_tests/test-large-prompt-switch.py`
