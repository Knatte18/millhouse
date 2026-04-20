---
kind: discussion
task: Sample render module refactor
slug: sample-render-refactor
status: in-design
written: 2026-04-20
---

# Sample render module refactor — Discussion

## Context

The `_render.py` module (at `plugins/mill/scripts/_render.py`) is a single
template-substitution helper used by every mill artefact format. It reads a
`.md` template from disk, identifies `<TOKEN>` placeholders matching the
pattern `[A-Z][A-Z0-9_]*`, substitutes all of them from a provided dictionary,
and raises `KeyError` if any token is left unresolved.

Currently the module is a plain `render(template_path, values)` function with
no caching. Every invocation re-reads the template file from disk. For the
review pipeline (which calls `render_prompt()` in `_review_common.py` for
each sub-review), this is fine at current scale. We may want caching later.

Two open questions have emerged from the Layer 02 design review:

1. Whether to extend `_render.py` with a cached variant for high-frequency
   template use in a future streaming pipeline.
2. Whether the token grammar should ever relax to allow digit-leading names
   (e.g. `<2FA_SECRET>`) — currently rejected by the `[A-Z]` leading-char
   constraint.

## Scope

This refactor is limited to `plugins/mill/scripts/_render.py`. No changes
to callers are expected — the public API surface (`render(template_path, values)`)
is stable and must remain unchanged.

Files in scope:

- `plugins/mill/scripts/_render.py` — primary target
- `plugins/mill/templates/` — read-only, to validate token patterns

Files out of scope:

- Any `_review_*.py` or `mill-review-*.py` script — those call `render_prompt()`
  which wraps `_render.render()`. We are not touching callers.
- The `_render.py` self-test block (`if __name__ == "__main__"`) — it works
  and testing it is lower priority.

## Decisions

### Decision 1: Keep the public API stable

`render(template_path: Path, values: dict[str, str]) -> str` stays exactly as
is. Callers do not need to change.

**Rationale:** `_render.render()` is imported directly by `_review_common.py`'s
`render_prompt()` wrapper, which already handles key-uppercasing and path
resolution. Adding a new parameter to `render()` would propagate breakage to
every caller.

**Alternatives rejected:**
- Add `cache: bool = False` parameter: silently ignored by callers that don't
  know about it, but confusing in code review. Prefer a separate `render_cached()`
  function if caching is added.

### Decision 2: Raise `KeyError` with all missing tokens at once

Already implemented in the current code. Worth stating explicitly: we do NOT
fail on the first missing token. The regex callback accumulates all missing
names and raises a single `KeyError` after the full substitution pass. This
surfaces all template/caller mismatches in one error rather than forcing
iterative fix-and-retry.

### Decision 3: Token grammar remains `[A-Z][A-Z0-9_]*`

We do not relax the leading-character constraint. The `[A-Z]` requirement
prevents `_render.py` from accidentally matching HTML attributes or lowercase
prose inside angle brackets (e.g. `<a href=...>`, `<em>`).

Any future token with a digit-leading name (like `<2FA_SECRET>`) is a naming
smell. Fix the name instead.

## Open questions

1. **Caching strategy** — if the review pipeline ever calls the same template
   file more than ~10 times in one session, add `functools.lru_cache` on a
   `_read_template(path)` helper. Decision deferred; benchmark first.

2. **Template discovery** — `_review_common.render_prompt()` hard-codes the
   path resolution pattern `Path(__file__).parent.parent / "templates" / name`.
   Should `_render.py` know about template roots? Current answer: no. Template
   path resolution is the caller's responsibility. `_render.render()` accepts
   any `Path`.

## Technical Context

The substitution engine is in `plugins/mill/scripts/_render.py`. The relevant
section is the `_TOKEN_RE` regex and the `replace()` closure inside `render()`:

```python
_TOKEN_RE = re.compile(r"<([A-Z][A-Z0-9_]*)>")

def render(template_path: Path, values: dict[str, str]) -> str:
    text = template_path.read_text(encoding="utf-8")
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            missing.append(name)
            return match.group(0)
        return values[name]

    rendered = _TOKEN_RE.sub(replace, text)
    if missing:
        raise KeyError(f"Unresolved template tokens: {sorted(set(missing))}")
    return rendered
```

The self-test at the bottom of `_render.py` verifies the function with a
temporary file — it is not run by pytest (no pytest in this repo), only when
the module is invoked directly as `python _render.py`.
