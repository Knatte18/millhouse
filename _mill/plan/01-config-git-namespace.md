# Batch: config-git-namespace

```yaml
task: "Fix config unknown-key warning on git namespace and commit _mill/briefs/ after dispatch"
batch: config-git-namespace
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-config.py
depends-on: []
```

## Batch Scope

Silence the spurious `[config] unknown key: git (in merged config)` warning (#511) by registering the `git` namespace in the config schema-of-record. The validator `_config.walk_unknown_keys` flags any top-level key in the merged config that is absent from the plugin template; the template's `git:` block is currently commented out, so `git` is "unknown" even though `git.parent-branch` (git-pr), `git.require_pr_to_base` and `git.base_branch` (mill-finalize) are legitimate. This batch replaces the commented example with a real, populated block at no-op defaults and locks the behavior with two unit tests (a positive no-warning test and a negative typo-still-warns test). Self-contained; no external interface for the next batch. Independent of batch 2 (no shared files).

## Cards

### Card 1: Register the git namespace in the template schema

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/skills/mill-finalize/SKILL.md`
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Under the "Git integration" comment header (~lines 76-82), replace the commented example block (the `# git:`, `#   require_pr_to_base: true`, `#   base_branch: main` lines) with a real, uncommented block:
  ```yaml
  git:
    parent-branch: null         # consumed by git-pr (reads .millhouse/config.yaml); null/absent -> falls back to arg/main
    require_pr_to_base: false    # consumed by mill-finalize; true -> open a PR instead of pushing directly
    base_branch: main            # consumed by mill-finalize; PR --base target; falls back to main if absent
  ```
  Keep the surrounding "Git integration" explanatory comments. `parent-branch` is **net-new** (the current comment has only `require_pr_to_base` and `base_branch` — this is an addition, not an uncomment). This registers `git` plus its three subkeys in the template dict that `_config.walk_unknown_keys` treats as the schema, so `[config] unknown key: git` no longer fires while any unregistered `git.*` subkey still warns. The three defaults (`null` / `false` / `main`) match existing fallbacks, so no hub behavior changes.
- **Commit:** `fix(config): register git namespace in template schema (#511)`

### Card 2: Lock git-namespace registration with unit tests

- **Context:**
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add two test functions modeled on the existing `test_via_psmux_does_not_trigger_unknown_key_warning` (uses the `_setup_plugin_template` fixture, `_write_yaml`, `_git_init`, and patches `_config.resolve_plugin_template_path` + `_paths.resolve_wiki_path`, capturing `sys.stderr`):
  1. `test_git_namespace_no_unknown_key_warning` — write a hub `mill-config.yaml` whose body is a `git:` block setting `parent-branch`, `require_pr_to_base: false`, and `base_branch: main`; call `_config.load_config(wt_root, wt_root)` with stderr captured; assert `"unknown key: git"` is NOT in the captured stderr.
  2. `test_git_unknown_subkey_still_warns` — write a `git:` block containing a bogus subkey (e.g. `git:\n  bogus-key: x\n`); assert `"unknown key: git.bogus-key"` IS in the captured stderr (proves the namespace is registered without disabling typo detection).
  Register both functions in the `tests = [...]` list inside `main()` (same place `test_via_psmux_does_not_trigger_unknown_key_warning` is registered) so `run-all.py --only test-config.py` executes them. Each function ends with a `print("PASS ...")` line matching the file's convention.
- **Commit:** `test(config): lock git namespace registration (#511)`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-config.py` runs the entire `test-config.py` suite (including the two new tests). Scope is the single test file the batch edits. The positive test confirms the warning is gone for registered git keys; the negative test confirms typo-detection still works. Card 1 (template edit) must land before the tests pass because `_setup_plugin_template` copies the real template into the fixture.
