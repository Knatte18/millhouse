# Batch: fixer-config

```yaml
task: "Dedicated fixer agent for post-holistic-review fix cycles"
batch: "fixer-config"
number: 1
cards: 2
verify: "uv run --project plugins/mill python plugins/mill/unit_tests/test-reviewers.py"
depends-on: []
```

## Batch Scope

Foundation batch. Introduces the new `roles.fixer.model` config key in the plugin template (default `haiku`) and extends `_reviewers.validate_role_refs` to fail closed when `roles.fixer.model` references an unknown reviewer name. Adds one mirror test in `test-reviewers.py` that follows the existing `test_validate_role_refs_catches_bad_implementer_model` pattern. No external interface change beyond the new optional config key. Batches 2 and 3 read this key; batch 1 must land first so batch 2's tests can rely on the key being resolvable from the merged config.

## Cards

### Card 1: Add roles.fixer block to the plugin template config

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** The file already has an active `roles:` block (lines 122-159 of the current head: `roles:` followed by `discussion-review:`, `plan-review:`, `code-review:`, and `implementer:` subsections). Add a `fixer:` subsection under the existing `roles:` block, as a sibling of `implementer:`. The new subsection's only key is `model: haiku`. Place `fixer:` immediately AFTER the existing `implementer:` subsection (i.e., as the last key under `roles:`) and BEFORE the `# Notifications` divider that follows. Do NOT create a second top-level `roles:` key -- a duplicate would silently shadow the existing block under PyYAML last-wins semantics and break every reviewer config. Do NOT modify any other key in the file. The end state is that `_config.load_config` returns a dict where `cfg["roles"]["fixer"]["model"] == "haiku"` AND every existing role subsection (`discussion-review`, `plan-review`, `code-review`, `implementer`) is preserved unchanged.
- **Commit:** `config: add roles.fixer.model default to plugin template`

### Card 2: Extend validate_role_refs to check roles.fixer.model

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/unit_tests/test-reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_reviewers.validate_role_refs(cfg, registry)`, mirror the existing `impl_model = cfg.get("roles", {}).get("implementer", {}).get("model")` check (lines 458-463 of `_reviewers.py`): add an identical block for `fixer_model = cfg.get("roles", {}).get("fixer", {}).get("model")` that, when non-None, calls `resolve(registry, fixer_model)` and on `ReviewerError` appends a string `f"roles.fixer.model={fixer_model!r}: {exc}"` to `errors`. Place the new block immediately after the existing `roles.implementer.model` check and before the `if errors: raise ReviewerError(...)` line. In `test-reviewers.py`, add a new top-level function `test_validate_role_refs_catches_bad_fixer_model` that mirrors `test_validate_role_refs_catches_bad_implementer_model` exactly (same shape and asserts) but with cfg `{"roles": {"fixer": {"model": "nonexistent_entry"}}}` and prints `PASS: validate_role_refs catches bad fixer model ref`. Register the new function in the `tests = [...]` list at the bottom of the file, immediately after `test_validate_role_refs_catches_bad_implementer_model`.
- **Commit:** `reviewers: validate roles.fixer.model name reference`

## Batch Tests

`uv run --project plugins/mill python plugins/mill/unit_tests/test-reviewers.py` -- the new `test_validate_role_refs_catches_bad_fixer_model` test must PASS, and no existing test in this file may regress. The full registry test suite covers `validate_role_refs` happy-path, missing-name, and the original implementer-model variant; the new test exercises the fixer-model variant.
