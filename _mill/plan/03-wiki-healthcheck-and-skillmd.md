# Batch: _wiki health-check and mill-go SKILL.md

```yaml
task: '65 (A) -- Config-load og mill-go helse-sjekk etter config-migrasjon'
batch: '_wiki health-check and mill-go SKILL.md'
number: 3
cards: 2
verify: null
depends-on: []
```

## Batch Scope

This batch delivers two related fixes to the mill-go operational surface: (1) `_wiki.health_check` is updated to also accept the plugin template as a valid config source, so it no longer fails on branches forked before the mill-config.yaml migration commit; (2) the mill-go SKILL.md is updated in two places -- Step 0 to accurately describe the health-check semantics, and Step 3 to pass the correct `hub_root` (not `wiki_path`) as the first arg to `_review_common.load_config`. Both fixes address issue #328.

## Cards

### Card 7: Update _wiki.health_check to accept plugin template as valid config source

- **Context:**
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/scripts/_wiki.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_wiki.health_check` (line 364-415), after the existing wiki/config.yaml fallback block (lines 398-409), add a third check: `from _config import resolve_plugin_template_path; plugin_tmpl = resolve_plugin_template_path("mill-config.yaml"); if plugin_tmpl.exists(): return`. This check fires only when neither `hub_root/mill-config.yaml` nor `wiki_root/config.yaml` was found. Update the docstring to list a third valid source: "3. Plugin template (mill-config.yaml) resolved via resolve_plugin_template_path". Update the final error-message string (line 414) to include the plugin template path searched: `f"no config source found: searched {mill_cfg}, {wiki_cfg}, and {plugin_tmpl}"`. The import `from _config import resolve_plugin_template_path` should be placed inside the function body alongside the existing `import _paths` (line 388) to avoid circular-import risk. All strings must be ASCII-only.
- **Commit:** `fix(_wiki): health_check accepts plugin template as valid config source`

### Card 8: Update mill-go SKILL.md Step 0 wording and Step 3 load_config arg

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Apply the following changes to `plugins/mill/skills/mill-go/SKILL.md`:

  **Step 0 (line 115-135 and lines 312-330 -- both occurrences):** Change the comment "verify the wiki is intact" to "verify a config source is reachable". Change "the wiki disappeared mid-run and the implementer's downstream 'Missing config' error would mask the root cause" to "a config source became unavailable mid-run and the implementer's downstream error would mask the root cause". Locate the echo line by searching for the surrounding context (e.g. `HALT: wiki appears missing`); the actual file uses an em-dash `—` not double-hyphen. Change `echo "[mill-go] HALT: wiki appears missing or corrupted — re-run mill-setup to restore it"` to `echo "[mill-go] HALT: no config source reachable -- re-run mill-setup if mill-config.yaml is missing"`. Apply the same wording changes to the second occurrence (the holistic-review loop's Step 0 block around line 312-330). The bash code calling `_wiki.health_check(hub_root)` itself does NOT change -- only the surrounding prose comments and the echo message change.

  **Step 3 (line 54):** Replace the function call `_review_common.load_config(wiki_path, Path(".millhouse"))` with `_review_common.load_config(_paths.resolve_git_root(), Path(".millhouse"))`. Replace the prose description "deep-merge `<wiki_path>/config.yaml` with `.millhouse/config.local.yaml` via `_review_common.load_config(wiki_path, Path(".millhouse"))`" with "load `mill-config.yaml` from the hub root, merged with `.millhouse/config.local.yaml`, via `_review_common.load_config(_paths.resolve_git_root(), Path(".millhouse"))`". Do not change any other text in Step 3.
- **Commit:** `fix(mill-go): update health-check wording and Step 3 load_config arg`

## Batch Tests

`verify: null` -- SKILL.md is a documentation file with no runnable test surface. `_wiki.health_check` has no dedicated unit test in the current test suite; the behavior change is validated indirectly by the integration tests (which are out of scope here). The overall test suite runs in batch 4's verify step.
