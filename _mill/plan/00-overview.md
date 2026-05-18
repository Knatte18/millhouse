# Plan: 65 (A) -- Config-load og mill-go helse-sjekk etter config-migrasjon

```yaml
task: '65 (A) -- Config-load og mill-go helse-sjekk etter config-migrasjon'
slug: 'mill-config-load-fixes'
approved: true
started: '20260518-064044'
parent: 'main'
root: ""
verify: "python plugins/mill/unit_tests/test-config.py"
```

## Batch Index

```yaml
batches:
  - number: 1
    name: _config.py fixes and template schema
    file: 01-config-fixes.md
    depends-on: []
    verify: "python plugins/mill/unit_tests/test-config.py"

  - number: 2
    name: _review_common.py fixes
    file: 02-review-common-fixes.md
    depends-on: []
    verify: null

  - number: 3
    name: _wiki health-check and mill-go SKILL.md
    file: 03-wiki-healthcheck-and-skillmd.md
    depends-on: []
    verify: null

  - number: 4
    name: Tests
    file: 04-tests.md
    depends-on: [1, 2, 3]
    verify: "python plugins/mill/unit_tests/test-config.py"
```

## Shared Decisions

### Decision: hub_relative_path suppression via pre-validation strip

- **Decision:** Strip `hub_relative_path` from a copy of the merged cfg before calling `warn_unknown_keys` in both `_config.load_config` and `_review_common.load_config`. Do not add it to the template schema.
- **Rationale:** `hub_relative_path` is a per-machine, gitignored key consumed by the loader itself, not a shared schema key. Adding it to the shared template would mislead operators. The returned cfg is unchanged; only the validation input is filtered.
- **Applies to:** batch 1, batch 2

### Decision: None-overlay guard on dict base only

- **Decision:** In `deep_merge` / `_deep_merge`, when the overlay value is `None` AND the base value is a dict, skip the override (keep the base dict). When the base value is a scalar, `None` is allowed to override (the `reviewer: null` use case).
- **Rationale:** YAML bare keys parse as `None`. The user's intent is "inherit defaults", not "delete this section". But `reviewer: null` explicitly disabling a reviewer must continue to work.
- **Applies to:** batch 1, batch 2

### Decision: resolve_plugin_template_path fallback with warning

- **Decision:** After resolving the CLAUDE_PLUGIN_ROOT-based path, check if it exists on disk. If not, emit a single-line stderr warning (ASCII-only, no em-dash) naming the missing path and the source-tree fallback being used, then return the source-tree path instead.
- **Rationale:** A stale CLAUDE_PLUGIN_ROOT causes silent template-load failure, leading to a KeyError many frames downstream. A warning at resolution time is immediately actionable.
- **Applies to:** batch 1

### Decision: pipeline.autonomous_mode added to template

- **Decision:** Add `autonomous_mode: false` to the `pipeline:` section of `plugins/mill/templates/mill-config.yaml`. Add a comment: `# Set true by mill-autofix; read by mill-go and mill-plan for autonomous stuck-handling.`
- **Rationale:** The key is consumed by mill-go and mill-plan SKILL.md files and is a real shared config key. The template omission causes a spurious warn_unknown_keys warning when users set it in config.local.yaml.
- **Applies to:** batch 1

### Decision: _wiki.health_check accepts plugin template as valid config source

- **Decision:** Add a third check to `_wiki.health_check`: if neither `mill-config.yaml` nor `wiki/config.yaml` is found, check whether the plugin template (`resolve_plugin_template_path("mill-config.yaml")`) exists. If it does, return success. Raise `WikiHealthError` only if all three sources are absent.
- **Rationale:** `_config.load_config` always loads the plugin template first. On branches forked before the `mill-config.yaml` migration commit, neither hub file exists -- but the implementer still runs successfully on template defaults. The health check's "no valid config source" condition is now too strict.
- **Applies to:** batch 3

### Decision: mill-go SKILL.md Step 3 arg fix

- **Decision:** Replace `_review_common.load_config(wiki_path, Path(".millhouse"))` with `_review_common.load_config(_paths.resolve_git_root(), Path(".millhouse"))` in mill-go SKILL.md Step 3. Update the prose to reference `mill-config.yaml` at the hub root rather than `wiki/config.yaml`.
- **Rationale:** `_review_common.load_config(repo_root, mill_dir)` expects `repo_root` to be the hub root where `mill-config.yaml` lives. Passing `wiki_path` means hub-specific overrides are silently ignored.
- **Applies to:** batch 3

### Decision: All print strings ASCII-only

- **Decision:** All new `print(...)` / `f"..."` strings in Python files use ASCII only. No em-dash (--), no Unicode arrows (->). Use ` -- ` and ` -> ` instead.
- **Rationale:** CLAUDE.md convention; Windows cp1252 terminals crash on non-ASCII stdout/stderr.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_config.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_wiki.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-review-common.py`
