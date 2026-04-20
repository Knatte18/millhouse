---
kind: plan-overview
task: Sample render module refactor
verify: python -c "import _render; print('ok')"
dev-server: N/A
approved: true
started: 20260420-100000
batches: [core]
root: plugins/mill
---

# Sample render module refactor — Plan

## Context

Introduce a `render_cached()` helper to `_render.py` alongside the existing
`render()` function. The cache is an `functools.lru_cache`-backed private
function. Public API is unchanged.

## Shared Decisions

### Decision: use `lru_cache` on an internal reader, not on `render()` itself

**Why:** `render()` takes a mutable `dict` as its second argument, which is
not hashable and therefore cannot be cached directly. Caching only the
file-read step (`_read_template(path) -> str`) is safe, composable, and does
not require callers to change their call sites.

**Alternatives rejected:**
- Cache `render()` by converting `values` to a `frozenset`: fragile and
  changes the public signature semantics.
- Memoize at the `render_prompt()` layer in `_review_common.py`: leaks a
  caching concern into the wrong layer.

## All Files Touched

- scripts/_render.py
