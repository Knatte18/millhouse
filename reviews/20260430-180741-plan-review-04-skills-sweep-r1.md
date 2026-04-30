# Review: 18 — par-E — Migrate Python invocation to `uv run` — 04-skills-sweep

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 04-skills-sweep
date: 2026-04-30
```

## Findings

### [BLOCKING] Card 9 perpetuates wrong `_tasks_md.set_phase` signature
**Step:** Card 9 requirements, bullet (2) — helper-shape audit
**Issue:** The card lists `_tasks_md.set_phase(home_path, slug, phase)` as the "real function signature" to verify against. The actual signature in `_tasks_md.py` is `set_phase(text: str, slug: str, phase: str | None) -> str` — first arg is string content (not a Path), and the function returns the rewritten string rather than mutating in place. The mill-go SKILL.md currently calls `_tasks_md.set_phase(home_path, slug, "done")` which is the existing bug. The implementer will compare the SKILL.md call against the "correct" signature in the card, see `home_path` in both, and conclude no mismatch — leaving the bug intact.
**Fix:** Change the card's listed expected signature to `_tasks_md.set_phase(text: str, slug: str, phase)` (string content, not Path), mark the existing mill-go call as wrong, and require the fix to read the file text first and write back the returned string.

### [BLOCKING] Card 15 misses second broken `millpy` import in mill-resume Phase 8
**Step:** Card 15 — fix mill-resume broken module ref
**Issue:** Card 15 addresses Phase 10's `python -m millpy.entrypoints.regenerate_sidebar`, but Phase 8 of mill-resume SKILL.md also contains `from millpy.core.junction import create as junction_create` — another reference to the non-existent `millpy` package. This is executable code in a Python snippet, not prose. Card 18's grep (`python\s+-m\s+millpy\.`) targets CLI invocations only and will not catch import statements in code blocks, so this survives the entire migration.
**Fix:** Extend card 15 to replace Phase 8's `from millpy.core.junction import create as junction_create` / `junction_create(...)` with the correct flat-helper pattern (e.g. `import _junction; _junction.create(...)` or the actual API documented in `_junction.py`), and add a grep for `millpy\.core\.` to card 18's verification sweep.

### [NIT] Card 8 "exactly one invocation" claim is factually wrong for mill-worktree
**Step:** Card 8 requirements description
**Issue:** The requirements state "each of these 12 skills has … exactly one `python …` invocation in a fenced bash block." mill-worktree/SKILL.md has three separate invocations (`create`, `remove`, `list`) in a single fenced block. The mismatch is risk-bearing: an implementer who takes the "exactly one" claim seriously may replace only the first line and leave two unrewritten.
**Fix:** Change the description to "one or more invocations" (or enumerate mill-worktree explicitly), while keeping the existing requirement wording "Replace each invocation" which is already correct.

## Verdict

REQUEST_CHANGES
Two BLOCKINGs: card 9 wrong helper signature propagates a known bug; card 15 misses a second broken `millpy` import.