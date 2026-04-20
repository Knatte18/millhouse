---
kind: plan-batch
batch-name: core
batch-depends: []
approved: true
---

# Batch 01: core

## Batch-Specific Context

Add `_read_template()` (lru-cached internal helper) and `render_cached()`
(public wrapper that uses the cached reader) to `_render.py`. No changes to
the existing `render()` function or to any caller.

## Batch Files

- scripts/_render.py

## Steps

### Step 01: Add `_read_template` and `render_cached` to `_render.py`

- **Creates:** nothing (adds to existing file)
- **Modifies:** scripts/_render.py
- **Reads:** scripts/_render.py
- **Requirements:**
  - Add a module-level `@functools.lru_cache(maxsize=None)` decorated private
    function `_read_template(path: Path) -> str` that reads the template file.
  - Add `render_cached(template_path: Path, values: dict[str, str]) -> str`
    that calls `_read_template(template_path)` instead of
    `template_path.read_text()`.
  - All existing behaviour of `render()` (missing-token accumulation,
    `KeyError` raise) must be preserved in `render_cached()`.
  - Import `functools` at the top of the file.
- **Test approach:** read the module docstring; run `python _render.py`.
- **Commit:** `feat(_render): add render_cached with lru_cache file-read`
