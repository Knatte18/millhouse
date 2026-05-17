# Batch: strand-a-env-interp

```yaml
task: '51 (D) -- Config infra: env interpolation + agents.yaml inheritance'
batch: strand-a-env-interp
number: 1
cards: 3
verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py
depends-on: []
```

## Batch Scope

Adds env-variable interpolation as the last step of `_config.load_config`. After all overlays (wiki -> machine -> worktree-stub -> worktree-real) are merged, every string value in the result is scanned for `${VAR}` and `${VAR:-default}` patterns and substituted from `os.environ`. Unset variables without a default raise a new `ConfigError(ValueError)` carrying the variable name and dotted key-path. Lists are walked; non-strings (int / bool / None) and dict keys pass through untouched.

The batch ships three things together because they are coupled: card 1 introduces the new exception class and the implementation; card 2 covers it with unit tests (every reviewer-mandated behaviour is asserted); card 3 documents the syntax in the `wiki-config.yaml` template that mill-setup ships to new hubs. No production `wiki/config.yaml` is touched (the discussion explicitly defers per-machine config-yaml flips to the operator). External callers of `load_config` (`mill-spawn`, `mill-go`, `mill-merge-in`, `mill-cleanup`, `mill-color`, `mill-terminal`, `mill-vscode`) require no changes because interpolation is transparent at the dict level.

The batch is verified by running `test-config.py` directly, which exercises the existing load_config tests plus all eleven new interpolation tests.

---

### Card 1: Add `ConfigError` and env-interpolation pass to `_config.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Three additions to `_config.py`, in order:

  **Change A -- new module-level imports.** At the top of the file, add `import os` and `import re` next to the existing `from pathlib import Path` / `import yaml` / `import _machine` block. Add nothing else.

  **Change B -- new exception class.** Define `class ConfigError(ValueError): pass` after the imports and before `def load_config`. Single-line body, no docstring beyond a one-line comment if useful. The class inherits `ValueError` so callers may catch with either name.

  **Change C -- new module-level regex constant.** Define directly after the `ConfigError` class:

  ```python
  # POSIX env-var convention: uppercase only; lowercase patterns are literal.
  _ENV_INTERP_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(:-(.*?))?\}")
  ```

  **Change D -- new private helpers, defined after `deep_merge`.**

  `def _substitute_string(value: str, key_path: str) -> str`:
  - Walk every match of `_ENV_INTERP_RE` in `value`.
  - For each match: variable name is group 1; `:-default` presence is group 2 (truthy when the `:-` literal appears, including the empty-default form `${VAR:-}`); default string is group 3 (may be `""`).
  - If `os.environ` contains the variable, substitute with the environ value.
  - Else if the `:-` literal appeared (group 2 is not None), substitute with `group(3)` (which is `""` for `${VAR:-}`).
  - Else raise `ConfigError(f"Unset env var '{var}' at config key '{key_path}'")`.
  - Use `re.sub` with a substitution function so all matches in one string are processed in a single pass; never re-scan the substituted output.

  `def _interpolate_env(cfg, key_path: str = "")`:
  - Type-dispatch: dict -> return new dict with same keys and recursively interpolated values (key_path extended as `f"{key_path}.{k}"` when `key_path` is non-empty, else `k`); list -> return new list with each element recursively interpolated (key_path extended as `f"{key_path}[{i}]"`); str -> return `_substitute_string(cfg, key_path)`; everything else (int, bool, None, float) -> return value unchanged.
  - Keys are not interpolated; only values.

  **Change E -- wire into `load_config`.** After the existing block that conditionally merges the real config (the `if hub_subpath != ".":` branch) and before `return cfg`, add `cfg = _interpolate_env(cfg)`. The interpolation runs unconditionally on whatever `cfg` ended up being, including the `{}` case (empty dict walks trivially and returns `{}`).

  No other code in `_config.py` changes. The existing `deep_merge` and `set_local_wiki_overrides` are untouched. The `load_config` docstring is unchanged (callers consume the same dict; interpolation is internal).

- **Commit:** `feat(_config): interpolate ${VAR} / ${VAR:-default} env tokens after overlay merge`

---

### Card 2: Add env-interpolation unit tests to `test-config.py`

- **Context:**
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Add eleven new test functions to `test-config.py`, after the existing `# load_config` block and before the existing `# deep_merge` block (a new commented section header `# env-interpolation` separates them). Each test follows the existing pattern: `with tempfile.TemporaryDirectory() as tmp: ...`, writes a fixture wiki config via `_write_yaml`, calls `_config.load_config(wiki, wt_root)`, asserts result, and ends with `print("PASS env-interp -- <short label>")`. None patches `Path.home`; every test creates its own `wiki` dir under tmp so the machine-layer is benign (machine config absent -> no-op merge, same as `test_load_config_machine_absent_graceful`).

  Tests that mutate `os.environ` use this exact pattern so the environ is restored even on AssertionError:

  ```python
  saved = os.environ.pop("MY_VAR", None)
  try:
      os.environ["MY_VAR"] = "actual"
      # ... call load_config, assert ...
  finally:
      if saved is None:
          os.environ.pop("MY_VAR", None)
      else:
          os.environ["MY_VAR"] = saved
  ```

  Add `import os` to the existing imports block at the top of the file if not already imported.

  The eleven test functions:

  1. `test_interp_default_when_var_unset` -- wiki config `key: "${UNSET_ENV_INTERP_VAR:-mydefault}"`; assert result `cfg["key"] == "mydefault"`. Pop `UNSET_ENV_INTERP_VAR` from environ before the call to guarantee unset state.
  2. `test_interp_env_value_when_var_set` -- set `os.environ["TEST_ENV_INTERP_SET"] = "actual"`; wiki config `key: "${TEST_ENV_INTERP_SET:-default}"`; assert `cfg["key"] == "actual"`. Restore environ in `finally`.
  3. `test_interp_unset_no_default_raises` -- wiki config `key: "${REQUIRED_UNSET_VAR}"`; pop var from environ. Expect `ConfigError` (catch as `_config.ConfigError`); assert `"REQUIRED_UNSET_VAR"` appears in `str(exc)` AND `"key"` appears in `str(exc)` (the dotted key-path).
  4. `test_interp_no_pattern_unchanged` -- wiki config `key: "plain string"`; assert `cfg["key"] == "plain string"`.
  5. `test_interp_nested_walk` -- wiki config:
     ```yaml
     a:
       b:
         c: "${INTERP_DEEP:-deep}"
     ```
     Pop `INTERP_DEEP`. Assert `cfg["a"]["b"]["c"] == "deep"`.
  6. `test_interp_list_walk` -- wiki config:
     ```yaml
     xs:
       - "${LIST_A:-a}"
       - "${LIST_B:-b}"
     ```
     Pop both vars. Assert `cfg["xs"] == ["a", "b"]`.
  7. `test_interp_non_string_values_untouched` -- wiki config:
     ```yaml
     count: 5
     flag: true
     nothing: null
     ```
     Assert `cfg["count"] == 5` (int, not str), `cfg["flag"] is True`, `cfg["nothing"] is None`.
  8. `test_interp_applied_after_all_overlays` -- wiki config `key: "${INTERP_A:-wiki}"`; worktree-local stub at `<wt_root>/.millhouse/config.local.yaml` with `key: "${INTERP_B:-local}"`. Pop both vars. After merge, worktree-local wins, then interpolation runs on the merged value -> `cfg["key"] == "local"`. (Demonstrates: interpolation runs on the post-merge string, not on each layer independently.)
  9. `test_interp_multiple_in_one_string` -- wiki config `key: "${INTERP_X:-x}-${INTERP_Y:-y}"`; pop both. Assert `cfg["key"] == "x-y"`. Verifies multi-match `re.sub` single-pass works.
  10. `test_interp_empty_default` -- wiki config `key: "${INTERP_EMPTY:-}"`; pop var. Assert `cfg["key"] == ""` (empty string allowed).
  11. `test_interp_lowercase_name_passthrough` -- wiki config `key: "${my_var}"`; set `os.environ["my_var"] = "foo"` (proves the test does not depend on it being unset). Assert `cfg["key"] == "${my_var}"` (literal passthrough -- regex does not match lowercase). Documents the POSIX-only convention. Restore environ in `finally`.

  Add `import _config` to existing imports if not present (it already is). Add `from _config import ConfigError` only if you prefer the short form in test 3; otherwise `_config.ConfigError` is fine.

- **Commit:** `test(_config): cover env-interpolation -- defaults, env wins, unset raises, nested, lists, multi-match, lowercase passthrough`

---

### Card 3: Document `${VAR:-default}` syntax in `wiki-config.yaml` template

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/wiki-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Add two pieces of documentation to the template. The template ships to new hubs only; existing hubs are unaffected.

  **Change A -- header note.** In the existing header comment block (lines 1-18), under the `# Path tokens` block, append a new fenced section before line 19 (the `# Junctions and hardlinks ...` paragraph):

  ```yaml
  # Env-var interpolation (substituted by mill scripts at run time):
  #   ${VAR}          -- replaced with the value of env var VAR; unset raises ConfigError
  #   ${VAR:-default} -- replaced with VAR if set; otherwise the literal "default"
  # Variable names must be uppercase (POSIX convention); lowercase forms pass through
  # as literal text. Interpolation applies to string values everywhere in this file,
  # including inside lists and nested maps.
  ```

  Use only ASCII characters in the comment text (per Shared Decisions). Place the new block as its own section between `# Path tokens (...) ... <SLUG>` and the `# Junctions and hardlinks ...` paragraph, separated from each by a blank `#` line.

  **Change B -- example use on a machine-overridable key.** In the existing `roles:` block (lines 95-129), add a commented-out example showing the env-interp syntax on the `roles.code-review.batch.reviewer` key. Insert two commented lines immediately above the existing `      reviewer: sonnetmedium` line under `code-review.batch:` (do NOT change the existing uncommented reviewer line):

  ```yaml
        # Override per machine without committing a wiki change:
        # reviewer: "${CODE_REVIEWER:-sonnetmedium}"
  ```

  The indentation must match the surrounding YAML (6 spaces -- inside `roles.code-review.batch`). The comment explains the intended use-case (per-machine override). No other keys are flipped to env-interp form; the discussion explicitly defers production `wiki/config.yaml` flips.

  No code is changed; this card is documentation-only.

- **Commit:** `docs(wiki-config.yaml): document ${VAR:-default} env-interpolation syntax with reviewer override example`

## Batch Tests

`verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py` -- runs the full `test-config.py` suite, including the existing twelve load_config / deep_merge / set_local_wiki_overrides tests and the eleven new interpolation tests added by card 2. A green run confirms that (a) interpolation is wired into the load_config chain after all overlays (test 8); (b) every error path raises the documented exception with the documented message (test 3); (c) no existing test regresses (every old test runs untouched). The wiki-config.yaml template change (card 3) has no runnable surface and is verified by inspection only.
