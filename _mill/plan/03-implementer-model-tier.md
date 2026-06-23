# Batch: implementer-model-tier

```yaml
task: "Fix agent-dispatch cwd guard, implementer self-termination, and false-success contracts"
batch: implementer-model-tier
number: 3
cards: 2
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py"
depends-on: []
```

## Batch Scope

Raises the default implementer model tier from `haiku` to `sonnethigh`
(#519). The demonstrated failure mode is a haiku-tier implementer
self-policing plan Shared Decisions and test-equivalence, passing verify
while violating the plan; a more capable default removes that failure class
(the brief-wording half of #519 lands in batch 2's Card 9). The change is a
value edit to the `roles.implementer.model` key in two synced files: the
plugin template (`plugins/mill/templates/mill-config.yaml`) and the live hub
overlay (`mill-config.yaml` at the worktree root) — per the project rule that
hub config and template stay in sync.

Batch-local decision (mid-flight config-mutation safety / bootstrap
justification): Card 11 mutates the live hub `mill-config.yaml`, which the
`wiki-config-mutation` plan validator flags. The change is safe to apply
mid-task because `roles.implementer.model` is read fresh by
`millpy-implement.py` (`implementer_cfg.get("model", "sonnethigh")`, line
~147) at the start of every batch dispatch; it carries no migration and no
schema change. The only effect of applying it during this very run is that
any implementer batch dispatched AFTER this batch uses the more capable
`sonnethigh` tier — strictly an improvement, never a breakage. This card body
is the bootstrap justification mill-plan's validator gate needs to re-run the
review with `--skip-check wiki-config-mutation`.

## Cards

### Card 11: Set roles.implementer.model to sonnethigh in template and hub config

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/templates/mill-agents.yaml`
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
  - `mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Change the `roles.implementer.model` value from `haiku` to `sonnethigh` in BOTH files: `plugins/mill/templates/mill-config.yaml` (line ~169) and the hub `mill-config.yaml` at the worktree root (line ~54). Change ONLY the `implementer` block's `model:` — leave `roles.implementer.self_fix_rounds`, `roles.fixer.model: haiku`, and `merge.model: haiku` untouched (#519 is implementer-specific). Confirm `sonnethigh` is a defined alias in `plugins/mill/templates/mill-agents.yaml` before relying on it (it is, per the registry). Do not alter surrounding comments or other keys.
- **Commit:** `feat(config): raise default implementer model to sonnethigh (#519)`

### Card 12: Unit-test the implementer-model default

- **Context:**
  - `plugins/mill/templates/mill-config.yaml`
  - `mill-config.yaml`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a unit test to `test-config.py` that loads each shipped config file with `yaml.safe_load` and asserts `roles.implementer.model == "sonnethigh"` for both `plugins/mill/templates/mill-config.yaml` and the hub `mill-config.yaml`. Resolve the repo root the way the existing tests in this file do (follow the file's existing path-resolution convention; do not hard-code an absolute path). This guards against a silent revert to `haiku` and against the template/hub pair drifting out of sync. Follow the file's `run-all.py` discovery convention.
- **Commit:** `test(config): assert implementer model default is sonnethigh in template and hub`

## Batch Tests

`verify` runs `test-config.py`, which now asserts the `roles.implementer.model`
default in both the template and the hub config (Card 12). No other runnable
surface changes in this batch. The scope is a single test file because only
config values change.
