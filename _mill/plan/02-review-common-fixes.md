# Batch: _review_common.py fixes

```yaml
task: '65 (A) -- Config-load og mill-go helse-sjekk etter config-migrasjon'
batch: '_review_common.py fixes'
number: 2
cards: 2
verify: null
depends-on: []
```

## Batch Scope

This batch applies parallel fixes to `_review_common.py`'s private copy of `_deep_merge` and its own `load_config` function. The fixes mirror batch 1's changes to `_config.py` exactly: (1) `_deep_merge` gains the same None-on-dict guard; (2) `load_config` strips `hub_relative_path` before warn_unknown_keys. These two functions are independent copies of the logic in `_config.py` — they are NOT imported from `_config`. `resolve_plugin_template_path` IS imported from `_config`, so the fallback fix from batch 1 propagates automatically without any change needed here.

## Cards

### Card 5: Guard _deep_merge in _review_common.py against None overlay on dict base

- **Context:**
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_review_common._deep_merge` (line 1168-1176), add the same guard as Card 1: before `result[key] = val`, insert `if val is None and isinstance(result.get(key), dict): continue`. When `val is None` and `result.get(key)` is a dict, skip the override. When `val is None` and base value is a non-dict (scalar, None, list), allow the None override. The variable names in `_review_common._deep_merge` are `base`, `override`, `result`, `key`, `val` -- use these, do not rename.
- **Commit:** `fix(_review_common): _deep_merge preserves base dict when overlay value is None`

### Card 6: Strip hub_relative_path before warn_unknown_keys in _review_common.load_config

- **Context:**
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_review_common.load_config` (line 1261), locate the call `warn_unknown_keys(cfg, template_cfg, "merged config")`. Replace it with: `check_cfg = {k: v for k, v in cfg.items() if k != "hub_relative_path"}; warn_unknown_keys(check_cfg, template_cfg, "merged config")`. The returned `cfg` (line 1266, `return cfg`) must NOT be modified -- only the validation copy excludes `hub_relative_path`. No other changes to `_review_common.load_config`.
- **Commit:** `fix(_review_common): suppress spurious unknown-key warning for hub_relative_path`

## Batch Tests

`verify: null` -- `_review_common.py` does not have a standalone unit test that exercises `_deep_merge` or the `hub_relative_path` suppression independently. The new tests for these behaviors are in batch 4 (test-review-common.py). The pre-existing `test-review-common.py` run (with 1 known pre-existing failure) is deferred to batch 4's verify step.
