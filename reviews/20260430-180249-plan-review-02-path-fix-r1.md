# Review: 18 — par-E — Migrate Python invocation to `uv run` — 02-path-fix

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 02-path-fix
date: 2026-04-30
```

## Findings

### [NIT] Cards 5 and 6 omit "add `import os`" instruction

**Step:** Cards 5 and 6
**Issue:** Both `millpy-terminal.py` and `_llm_claude.py` currently have no `import os`, yet both cards introduce an `os.name == "nt"` check without explicitly directing the implementer to add the import. Card 4 already has `import os` in the source, so the omission is only risky in files that currently lack it. For `_llm_claude.py`, the card 6 smoke-check (`import _llm_claude; print('ok')`) is a pure import test — it would pass even with a missing `import os`, leaving the runtime `NameError` undetected until a live run.
**Fix:** Add one line to each card's Requirements: "Add `import os` (not currently present in this file)."

### [NIT] Card 5 smoke-check mis-describes `--help` behaviour

**Step:** Card 5
**Issue:** `millpy-terminal.py` has no argparse; `--help` is silently ignored, and the smoke-check resolves to a full run that returns 0 only if `resolve_git_root()` succeeds and no worktrees are found — making it environment-dependent rather than a reliable importability check.
**Fix:** Change the smoke-check to `uv run --project plugins/mill python -c "import millpy-terminal; print('ok')"` (import-only, like card 6), or accept the environment dependency and note it in the card.

## Verdict

APPROVE — two NITs; no blockers. Core cmd-wrapper logic, decision alignment, and atomicity are all sound.