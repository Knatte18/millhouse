# Review: 18 — par-E — Migrate Python invocation to `uv run` — 03-mill-setup-skill

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 03-mill-setup-skill
date: 2026-04-30
```

## Findings

### [NIT] Req 4 phrasing risks dropping `from pathlib import Path`
**Step:** Card 7, Requirement 4 (Phase 4.7 snippet edit)
**Issue:** "The snippet body should start with `import _shortcuts; written = _shortcuts.write_all(Path('.millhouse'))` directly" reads as: remove everything above `import _shortcuts`. But `from pathlib import Path` is used on that very next line — removing it causes `NameError`.
**Fix:** Tighten to: "remove `import sys` and the `sys.path.insert(...)` line; keep `from pathlib import Path`."

## Verdict

APPROVE
Batch scope, bootstrap pattern, PowerShell escaping, Phase 8 invariant updates, and API audit requirement are all correctly specified; one ambiguous phrasing worth tightening.