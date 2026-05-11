# Batch: machine-layer-module

```yaml
task: 45 (A) — Machine-level config layer
batch: machine-layer-module
number: 1
cards: 2
verify: python plugins/mill/unit_tests/test-machine.py
depends-on: []
```

## Batch Scope

Adds the new module `plugins/mill/scripts/_machine.py` and its dedicated unit test file `plugins/mill/unit_tests/test-machine.py`. This batch is a self-contained foundation: nothing else in mill imports `_machine` yet (batch 2 wires it in). The deliverable is a callable, tested helper that surfaces three operations — derive the canonical machine-config path, load + parse the file (or return `{}` if absent), and probe with status + detail for setup-time reporting. Batch 2 consumes the public API exactly as defined here. No batch-local deviations from the Shared Decisions in `00-overview.md`.

## Cards

### Card 1: Create `_machine.py` with `machine_config_path`, `load_layer`, `probe`

- **Context:**
  - `plugins/mill/scripts/_config.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_machine.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/scripts/_machine.py` exposing the following public API. Match the docstring style of `_config.py` — top-level module docstring with a one-line summary followed by an `Exports` block listing every public symbol with a one-line description; each function gets a Google-style docstring with `Args:`, `Returns:`, and (where applicable) `Raises:` sections.
  - Module-level string constants: `MISSING = "missing"`, `PRESENT = "present"`, `MALFORMED = "malformed"`. Exposed for callers (mill-setup's Phase 4.95) so they don't string-compare literals.
  - `def machine_config_path(home_dir: Path | None = None) -> Path:` — return `(home_dir if home_dir is not None else Path.home()) / ".millhouse" / "config.machine.yaml"`. Pure function; does not touch the filesystem. `home_dir` is for test injection only.
  - `def load_layer(home_dir: Path | None = None) -> dict:` — call `machine_config_path(home_dir)`. If `path.exists()` is False, return `{}`. Otherwise call `yaml.safe_load(path.read_text(encoding="utf-8"))` and return the result, substituting `{}` when `safe_load` returns `None` (empty file). Lazy-import `yaml` inside this function (no top-level import). Lets `yaml.YAMLError` propagate uncaught — soft failure on malformed YAML is `probe`'s job, not `load_layer`'s.
  - `def probe(home_dir: Path | None = None) -> tuple[str, object]:` — return a `(status, detail)` tuple:
    - File missing (`path.exists()` is False) → `(MISSING, None)`.
    - File present + parses → `(PRESENT, parsed)` where `parsed` is the dict from `yaml.safe_load` (with `{}` substituted for `None`-on-empty).
    - File present but `yaml.YAMLError` raised → `(MALFORMED, str(error))`. Catch ONLY `yaml.YAMLError`, never bare `Exception` or `OSError` — let unrelated errors crash so they surface.
  - Top-level imports: `from __future__ import annotations`, `from pathlib import Path`. No `import yaml` at module top.
  - `__all__` list: `["MISSING", "PRESENT", "MALFORMED", "machine_config_path", "load_layer", "probe"]`.
- **Commit:** `feat(machine): add machine-level config helper module`

### Card 2: Create `test-machine.py` with four test functions

- **Context:**
  - `plugins/mill/unit_tests/test-config.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-machine.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/unit_tests/test-machine.py`. Mirror the prelude of `test-config.py`: same `HUB = Path(__file__).resolve().parent.parent.parent.parent`, same `SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"`, same `sys.path.insert(0, str(SCRIPTS_DIR))`, then `import _machine`. Each test function uses `tempfile.TemporaryDirectory()` for any filesystem fixture, raises `AssertionError` on mismatch, and prints `PASS <name>` on success. Register all four in a module-level `tests = [...]` list inside `main()` exactly like `test-config.py`'s `main()`. Return 0 on all-pass, 1 on any failure. Tests:
  - `test_machine_config_path_uses_home_arg()` — call `_machine.machine_config_path(home_dir=Path("/fake"))`; assert the result equals `Path("/fake") / ".millhouse" / "config.machine.yaml"`. Then call `_machine.machine_config_path()` (no arg) and assert the result equals `Path.home() / ".millhouse" / "config.machine.yaml"`.
  - `test_load_layer_missing_returns_empty()` — `with tempfile.TemporaryDirectory() as tmp:` call `_machine.load_layer(home_dir=Path(tmp))` (do NOT create `<tmp>/.millhouse/`); assert the result equals `{}`.
  - `test_load_layer_present_returns_dict()` — `tempfile.TemporaryDirectory()`, create `<tmp>/.millhouse/config.machine.yaml` (parents=True, exist_ok=True) with content `roles:\n  discussion-review:\n    holistic:\n      reviewer: cluster-gemini\n`. Call `_machine.load_layer(home_dir=Path(tmp))`. Assert `result["roles"]["discussion-review"]["holistic"]["reviewer"] == "cluster-gemini"`.
  - `test_probe_three_states()` — three sub-cases, all in one function (no separate fixtures needed; each sub-case uses its own `tempfile.TemporaryDirectory()`):
    - Sub-case "missing": no `.millhouse/` dir → `_machine.probe(home_dir=Path(tmp))` returns `(_machine.MISSING, None)`.
    - Sub-case "present": write valid YAML (e.g. `roles:\n  discussion-review:\n    holistic:\n      reviewer: sonnet\n`) → `probe` returns `(_machine.PRESENT, parsed_dict)` where `parsed_dict["roles"]["discussion-review"]["holistic"]["reviewer"] == "sonnet"`.
    - Sub-case "malformed": write `: : :\n` (invalid YAML — leading mapping key with no scalar) → `probe` returns `(_machine.MALFORMED, error_string)` where `error_string` is a non-empty `str`.
- **Commit:** `test(machine): add unit tests for _machine module`

## Batch Tests

Run `python plugins/mill/unit_tests/test-machine.py` from the worktree root. Expected output: four `PASS` lines (one per test), exit code 0. The verify command in this batch's frontmatter is the same. No interaction with `test-config.py` or other tests in this batch; they remain unchanged. `run-all.py` would also work but is more than needed for batch verification — the per-file invocation is faster and proves the module in isolation.
