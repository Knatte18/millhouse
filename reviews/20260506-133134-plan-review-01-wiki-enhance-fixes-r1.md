# Review: 9 (B) — Wiki-enhance: small wiki cleanups — 01-wiki-enhance-fixes

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 01-wiki-enhance-fixes
date: 2026-05-06
```

## Findings

### [BLOCKING] Wrong function name `render` vs `render_sidebar` in `_sidebar.py`
**Step:** Card 2 + Card 3
**Issue:** Card 2 instructs the implementer to change "the `render()` function's linked-task branch" and Card 3 instructs to "import `_sidebar.render` directly" and "call `render()`" — but `_sidebar.py` exposes `render_sidebar()`, not `render()`. Following the plan literally produces `ImportError: cannot import name 'render' from '_sidebar'`, failing the verify step.
**Fix:** Replace every occurrence of `render()` / `_sidebar.render` in both cards with `render_sidebar()` / `_sidebar.render_sidebar`.

### [NIT] Pipeline comment lines for removed keys not mentioned
**Step:** Card 1
**Issue:** `wiki/config.yaml` has multi-line inline comments documenting `builder` and `implementer` immediately above those keys inside the `pipeline:` block. Card 1 says to remove the keys but does not mention removing those companion comment lines; an implementer following the card literally may leave orphaned documentation.
**Fix:** Add a sentence: "Also remove the `# builder —` and `# implementer —` comment lines from the `pipeline:` block in `wiki/config.yaml`."

## Verdict

REQUEST_CHANGES — one BLOCKING wrong function name would fail `test-sidebar.py` at import.