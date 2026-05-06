# Plan: '6 (A) — Plan reviewer: detect self-applying layout changes that strand in-flight state'

```yaml
task: '6 (A) — Plan reviewer: detect self-applying layout changes that strand in-flight state'
slug: plan-reviewer-self-apply
approved: false
started: 20260506-113540
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - name: wiki-config-check
    file: 01-wiki-config-check.md
    depends-on: []
    verify: "uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py"
```

## Shared Decisions

### Decision: detection-signal

- **Decision:** Detect `wiki/config.yaml` in `Modifies:` or `Creates:` fields by exact string match — no path resolution needed.
- **Rationale:** The token `wiki/config.yaml` appearing in any batch card's Modifies:/Creates: list is the exact condition that indicates a self-applying layout risk. String matching avoids the need to resolve paths against wiki_root, keeping the check fast and dependency-free.
- **Applies to:** wiki-config-check

### Decision: one-error-per-batch

- **Decision:** `_check_wiki_config_mutation` emits at most one error per batch, regardless of whether `wiki/config.yaml` appears in both `Modifies:` and `Creates:` fields.
- **Rationale:** The finding is a batch-level fact ("this batch writes wiki/config.yaml"). Whether it appears in one field or two doesn't change the finding or the fix. Deduplication avoids confusing double-reporting.
- **Applies to:** wiki-config-check

### Decision: helper-design

- **Decision:** Add `_parse_creates_only` as a sibling of the existing `_parse_modifies_only`; union the two sets inline inside `_check_wiki_config_mutation`. Do not use `parse_batch_refs` (returns Reads too).
- **Rationale:** Keeps `_parse_creates_only` consistent with the existing `_parse_modifies_only` / `_parse_deletes_only` pattern. No third helper needed.
- **Applies to:** wiki-config-check

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/templates/review-plan-batch.md`
- `plugins/mill/templates/review-plan-holistic.md`
- `plugins/mill/unit_tests/test-plan-validate.py`
