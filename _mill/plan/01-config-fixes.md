# Batch: _config.py fixes and template schema

```yaml
task: '65 (A) -- Config-load og mill-go helse-sjekk etter config-migrasjon'
batch: '_config.py fixes and template schema'
number: 1
cards: 4
verify: "python plugins/mill/unit_tests/test-config.py"
depends-on: []
```

## Batch Scope

This batch delivers four self-contained fixes to `_config.py` and the `mill-config.yaml` template:
(1) `deep_merge` is guarded against None overlay values clobbering nested dicts;
(2) `resolve_plugin_template_path` warns and falls back to the source-tree when CLAUDE_PLUGIN_ROOT is stale;
(3) `load_config` strips `hub_relative_path` from the validation copy before calling `warn_unknown_keys`;
(4) `pipeline.autonomous_mode: false` is added to the template schema so it is no longer flagged as unknown.
All four changes touch files that are exclusively owned by this batch (no overlap with batches 2 or 3).

## Cards

### Card 1: Guard deep_merge against None overlay on dict base

- **Context:**
  - `plugins/mill/unit_tests/test-config.py`
- **Edits:**
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_config.deep_merge` (line 283), add a guard before the `else` branch: `if val is None and isinstance(out.get(key), dict): continue`. When `val is None` and `out.get(key)` is a dict, skip the override and keep the base dict. When `val is None` and the base value is a non-dict scalar (e.g. `reviewer: null` use case), allow the None override (the existing `else: out[key] = val` handles this correctly). No other changes to `deep_merge` logic.
- **Commit:** `fix(_config): deep_merge preserves base dict when overlay value is None`

### Card 2: Warn and fall back in resolve_plugin_template_path when CLAUDE_PLUGIN_ROOT path missing

- **Context:**
  - `plugins/mill/unit_tests/test-config.py`
- **Edits:**
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_config.resolve_plugin_template_path` (line 126-141), after constructing `candidate = Path(plugin_root_env).resolve() / "templates" / filename`, add an existence check: `if not candidate.exists(): print(f"[config] CLAUDE_PLUGIN_ROOT={plugin_root_env!r}: {candidate} not found, falling back to source tree", file=sys.stderr); return Path(__file__).resolve().parent.parent / "templates" / filename`. Only apply this fallback when `candidate` does NOT exist. If `candidate` exists, return it as before. The warning string must be ASCII-only (no Unicode). `sys` is already imported at the top of the file.
- **Commit:** `fix(_config): resolve_plugin_template_path warns and falls back on stale CLAUDE_PLUGIN_ROOT`

### Card 3: Strip hub_relative_path before warn_unknown_keys in load_config

- **Context:**
  - `plugins/mill/unit_tests/test-config.py`
- **Edits:**
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_config.load_config`, locate the `warn_unknown_keys(cfg, template_cfg, source_label or "merged config")` call (line 217). Replace it with: `check_cfg = {k: v for k, v in cfg.items() if k != "hub_relative_path"}; warn_unknown_keys(check_cfg, template_cfg, source_label or "merged config")`. The variable `cfg` (returned from `load_config`) must NOT be modified -- only `check_cfg` (the validation-only copy) excludes `hub_relative_path`. Do not strip any other keys.
- **Commit:** `fix(_config): suppress spurious unknown-key warning for hub_relative_path`

### Card 4: Add autonomous_mode to mill-config.yaml template pipeline section

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the `pipeline:` section of `plugins/mill/templates/mill-config.yaml` (after `auto_report: true`, around line 110), add `autonomous_mode: false` with an inline comment on the same line or the line before: `# Set true by mill-autofix; read by mill-go and mill-plan for autonomous stuck-handling.` The new line must be `  autonomous_mode: false` (two-space indent matching the existing keys). No other changes to the template.
- **Commit:** `chore(templates): add autonomous_mode to mill-config.yaml pipeline schema`

## Batch Tests

`verify: "python plugins/mill/unit_tests/test-config.py"` — all 30 existing tests must still pass after this batch. No new tests are added in this batch (new tests live in batch 4). The verify command confirms the existing test suite is not regressed by the `deep_merge` and `load_config` changes.
