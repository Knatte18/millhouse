# Batch: status-and-module-removal

```yaml
task: "Drop the eager verify-baseline pre-flight"
batch: "status-and-module-removal"
number: 4
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py test-millpy-implement.py test-millpy-merge-in-subagent.py test-millpy-fix.py
depends-on: [1, 2, 3]
```

## Batch Scope

With every caller gone (batches 1-3), this batch deletes the cache itself: the module-baseline API and the `verify_baseline_failures` batch key in `_status.py`, the `_verify_baseline.py` module with its unit and integration tests, and the `pipeline.baseline_verify_timeout_minutes` config key.
`_verify_baseline.py` is deleted here, before batch 5, because it calls `_implementer_common._extract_failure_signatures(..., returncode=...)`, a parameter batch 5 removes.
No status.md migration (discussion Decision `no-status-migration`): `set_batch_field` / `set_batch_fields` validate only the keys being written, `read_batches` loads entries with `yaml.safe_load`, and `_serialise_batches` writes only keys in its `order` list, so a legacy key is read without error and dropped on the next batch write.

## Cards

### Card 8: Remove the module-baseline API and verify_baseline_failures key from _status.py

- **Context:**
  - `plugins/mill/scripts/_yaml_writer.py`
- **Edits:**
  - `plugins/mill/scripts/_status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Delete `_MODULE_VERIFY_BASELINE_STATES`, `get_module_verify_baseline`, `_baseline_anchor_index`, `set_module_verify_baseline`, `clear_module_verify_baseline`, `get_module_verify_baseline_signatures`, `set_module_verify_baseline_signatures` in full.
  - Delete their five API lines from the module docstring (`get_module_verify_baseline(status_path) -> str | None` through `set_module_verify_baseline_signatures(status_path, value) -> None`).
  - Remove `"verify_baseline_failures"` from `_BATCH_ALLOWED_KEYS` and from the `order` list in `_serialise_batches`.
  - In `_serialise_batches`, rewrite the two-line comment that starts `# list values (e.g.` so it no longer names `verify_baseline_failures`: `# list values serialize as a flow-sequence yaml scalar via safe_dump, never as a Python-repr-shaped raw str().` (keep the list branch itself and the rest of the comment).
  - Do not change `set_batch_field`, `set_batch_fields` or `read_batches` (confirmed at planning time: both setters validate only the keys passed in, never keys of entries read back from disk).
  - Grep `plugins/mill/scripts` and `plugins/mill/skills` for each deleted name afterwards and confirm no caller remains (batches 1-3 removed them; `_verify_baseline.py` is deleted by card 10 of this batch).
  - Then apply the overview's `unused-import-check` Decision to this file.
- **Commit:** `refactor(status): remove module verify-baseline cache and batch baseline key`

### Card 9: Update _status tests

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Remove `clear_module_verify_baseline`, `get_module_verify_baseline`, `get_module_verify_baseline_signatures`, `set_module_verify_baseline`, `set_module_verify_baseline_signatures` from the `from _status import (...)` block.
  - Delete the `# --- module_verify_baseline tests ---` block (Tests 1 through 11) and the `# --- baseline row anchoring ---` block in full; keep the `_yaml_status` helper only if a surviving test still calls it.
  - Replace the two `verify_baseline_failures` round-trip checks in the batches test (the `failures = [...]` write and the empty-list write, with their PASS lines) by:
    - a check that `set_batch_field(sp, "foundation", "verify_baseline_failures", ["x"])` raises `ValueError`, and that `set_batch_fields(sp, "foundation", {"verify_baseline_failures": []})` raises `ValueError`;
    - a legacy-key check: write a status.md whose `## Batches` yaml entry for a batch carries `verify_baseline_failures: ["--- FAIL: TestFoo"]` alongside `state: running`, assert `read_batches` returns that entry with the key present, then call `set_batch_field(sp, <name>, "review_round", 1)` and assert the re-read entry has no `verify_baseline_failures` key, keeps `state == "running"`, and has `review_round == 1`.
    Keep the sibling-field assertions the old block made (`state`, `blocked_reason` survive) by moving them onto the `review_round` write if they are not already covered.
  - After this card, grep the file for `module_verify_baseline` and confirm zero hits; `verify_baseline_failures` hits remain only in the new rejection and legacy-key checks.
- **Commit:** `test(status): cover removed baseline key and legacy-key read`

### Card 10: Delete _verify_baseline.py and its tests

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:** none
- **Creates:** none
- **Deletes:**
  - `plugins/mill/scripts/_verify_baseline.py`
  - `plugins/mill/unit_tests/test-verify-baseline.py`
  - `plugins/mill/integration_tests/test-verify-baseline.py`
  - `plugins/mill/integration_tests/test-baseline-waiver.py`
- **Moves:** none
- **Requirements:**
  - Before deleting, grep `plugins/` for `import _verify_baseline` and `_verify_baseline.` and confirm the only hits are inside the four files being deleted (batches 1 and 3 removed the imports from both CLI scripts).
  - Delete the four files with `git rm`.
  - Grep `plugins/mill/unit_tests/run-all.py` and `plugins/mill/integration_tests/` for the deleted test filenames; if any runner lists them explicitly, remove those entries (none expected — the runners glob).
- **Commit:** `refactor: delete _verify_baseline module and its tests`

### Card 11: Remove baseline_verify_timeout_minutes from both mill-config.yaml copies

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `mill-config.yaml`
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Delete the `baseline_verify_timeout_minutes: null  # Per-run wall-clock ceiling ...` line (and only that line) under `pipeline:` in both files, keeping them in sync per CLAUDE.md.
  - Bootstrap safety (overview Decision `config-key-removal-is-safe-mid-flight`): this is a key removal; its only reader was the `--stage baseline` branch batch 1 deleted, and the deployed copy a running mill-go uses reads it via `.get(...)`, so the absent key resolves to `None` — the key's current value.
  - Grep `plugins/` for `baseline_verify_timeout_minutes` afterwards and confirm zero hits.
- **Commit:** `chore(config): drop baseline_verify_timeout_minutes`

## Batch Tests

`verify:` runs `test-status.py` (the API and batch-key changes) plus `test-millpy-implement.py`, `test-millpy-merge-in-subagent.py` and `test-millpy-fix.py`, which import the CLIs that used to call the deleted `_status` functions and `_verify_baseline` — an import-time `AttributeError`/`ImportError` left behind by batches 1-3 would surface there.
All four were green on the task branch tip before planning.
