# Review: 18 — par-E — Migrate Python invocation to `uv run` — 01-foundation

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 01-foundation
date: 2026-04-30
```

## Findings

### [NIT] Card 3 smoke-check requires pre-existing PYTHONPATH
**Step:** Card 3 — `_shortcuts.py` smoke-check
**Issue:** `python -c "... import _shortcuts ..."` needs `scripts/` on PYTHONPATH; during this foundation batch that global env var may not exist yet (mill-setup Phase 4.7 sets it, which is batch 03).
**Fix:** Prefix with `PYTHONPATH=plugins/mill/scripts` or use `uv run` with an inline `sys.path.insert(0, 'plugins/mill/scripts')` so the smoke-check is self-contained regardless of shell state.

## Verdict

APPROVE — no BLOCKINGs; batch scope, sequencing, interface contracts, and decision alignment are all sound.