# Plan: 45 (A) — Machine-level config layer

```yaml
task: 45 (A) — Machine-level config layer
slug: machine-level-config
approved: false
started: 20260511-104021
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: machine-layer-module
    file: 01-machine-layer-module.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-machine.py
  - number: 2
    name: integrate-and-document
    file: 02-integrate-and-document.md
    depends-on: [1]
    verify: python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: machine-config path resolved via `Path.home()`, not `_paths.py`

- **Decision:** `_machine.machine_config_path(home_dir=None)` lives in `_machine.py` and returns `(home_dir if home_dir is not None else Path.home()) / ".millhouse" / "config.machine.yaml"`. The helper does NOT route through `_paths.py`.
- **Rationale:** `_paths.py` is the canonical (git context, config) → path mapper. The machine config has no git context and no config dependency — it's a pure function of `$HOME`. Adding it to `_paths.py` would dilute that module's contract. Existing precedent: `_config.set_local_wiki_overrides` accepts a `cfg_path` argument from the caller and doesn't resolve any path internally — the machine helper follows the same separation.
- **Applies to:** all batches

### Decision: `home_dir` kwarg threading

- **Decision:** All three public helpers in `_machine.py` (`machine_config_path`, `load_layer`, `probe`) accept an optional `home_dir: Path | None = None` kwarg. Production callers pass nothing (so `Path.home()` is used). Tests inject a `tempfile.TemporaryDirectory()` path via the kwarg directly for `_machine.py` tests (`test-machine.py`); the cross-layer tests in `test-config.py` patch `Path.home` via `unittest.mock.patch.object` because the upstream `_config.load_config` and `_review_common.load_config` callers do not (and should not) accept a `home_dir` kwarg.
- **Rationale:** Eighteen `load_config` call sites in production. Threading a `home_dir` kwarg through every one buys nothing — `Path.home()` is the only correct value at runtime. Tests use the kwarg directly for direct-helper coverage and patch `Path.home` for cross-layer coverage. This matches conventional Python test-injection style (kwarg for new code, patch for inherited dependencies).
- **Applies to:** all batches

### Decision: lazy yaml import inside `_machine.load_layer`

- **Decision:** `_machine.py` does NOT import `yaml` at module top-level. The import lives inside `load_layer` and `probe` (where parsing happens). Module-level imports are stdlib only (`from pathlib import Path`, etc.).
- **Rationale:** `_machine.machine_config_path` is a pure path function with no YAML dependency. Some callers (e.g. mill-setup's eventual Phase 4.95 status line) may only need the path, not the parser. Module-level yaml import would make every importer pay the cost. Matches the in-function `import yaml` pattern used by some other mill helpers; consistent enough not to fight.
- **Applies to:** batch 1 (`_machine.py`)

### Decision: malformed file = soft fail, not hard fail

- **Decision:** `_machine.load_layer` lets `yaml.YAMLError` propagate (no try/except). Callers that need a soft-fail status use `_machine.probe`, which catches `yaml.YAMLError` and returns `(MALFORMED, error-string)`. The production `load_config` callers in `_config.py` and `_review_common.py` use `load_layer`, so a malformed `~/.millhouse/config.machine.yaml` will crash mill commands with the YAML parse error.
- **Rationale:** A malformed machine config is a user error the operator must fix. Silently treating it as `{}` would mask the bug (operator wonders why their override isn't taking effect). The exception message names the file and the parse error line — clear repro path. mill-setup's Phase 4.95 (in batch 2) uses `probe` to surface the error without halting setup, so the operator gets early warning during a setup re-run.
- **Applies to:** all batches

### Decision: tests use `unittest.mock.patch.object` for `Path.home` injection

- **Decision:** Cross-layer tests in `test-config.py` use:
  ```python
  from unittest.mock import patch
  with patch.object(Path, "home", return_value=Path(tmp_home)):
      cfg = _config.load_config(wiki, wt_root)
  ```
  Direct helper tests in `test-machine.py` pass `home_dir=Path(tmp)` to the helper functions and do not patch `Path.home`.
- **Rationale:** Avoids polluting the real `~/.millhouse/config.machine.yaml` (if a developer has one) during tests. `patch.object` cleanly scopes the override to the `with` block. Direct kwarg injection is preferred when the helper accepts it (cleaner than mock-patching).
- **Applies to:** batch 1 (`test-machine.py`), batch 2 (`test-config.py` new cases)

### Decision: backtick-only path bullets per `mill-receiving-review`'s `reads-not-backtick-path` rule

- **Decision:** Every `Context:`, `Edits:`, `Creates:`, `Deletes:` field in every card uses ONLY backtick-wrapped paths in indented bullet form. No inline commentary, no line-range suffixes, no parenthetical notes. Any inline observation goes in `Requirements:`.
- **Rationale:** mill-receiving-review's validator flags non-backtick paths. Stable plan-validate gate.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_config.py`
- `plugins/mill/scripts/_machine.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/templates/config.local.yaml`
- `plugins/mill/templates/config.machine.yaml`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-machine.py`
