# Review: 18 — par-E — Migrate Python invocation to `uv run` — 05-tests-and-docs

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 05-tests-and-docs
date: 2026-04-30
```

## Findings

### [NIT] Card 20 "all 12 files" overstates scope for 4 files
**Step:** Card 20, requirement (1)
**Issue:** `test-worktree-sibling-resolution.py`, `test-go-assets.py`, `test-plan-assets.py`, and `test-merge.py` have no `sys.executable` subprocess calls to millpy scripts (they invoke git or import helpers directly in-process). Adding the `PLUGIN_ROOT` constant to these 4 files is harmless but unused. More importantly, `test-worktree-sibling-resolution.py` uses `MILL_SCRIPTS` (not `SCRIPTS`/`HUB`), so the instruction "add after `SCRIPTS = HUB / "plugins" / "mill" / "scripts"`" is inapplicable—a mechanical implementer adding `PLUGIN_ROOT = HUB / "plugins" / "mill"` to that file would introduce a `NameError`.
**Fix:** Exclude those 4 files from the Modifies list or add a per-file note: "no subprocess invocations to migrate; skip PLUGIN_ROOT addition."

## Verdict

APPROVE
One NIT about 4 files overstated in scope; no functional issues.