# Review: 18 — par-E — Migrate Python invocation to `uv run` — 04-skills-sweep

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 04-skills-sweep
date: 2026-04-30
```

## Findings

### [BLOCKING] Card 15 Reads missing `_junction.py`
**Step:** Card 15 — mill-resume/SKILL.md
**Issue:** Requirements explicitly instruct the implementer to verify the `_junction.create` API via `grep -n "^def create" plugins/mill/scripts/_junction.py` before writing the Phase 8 fix (`from _junction import create as junction_create`). `plugins/mill/scripts/_junction.py` is absent from the card's Reads list. If `_junction.create` does not exist under that name, the proposed fix is wrong and there is no other card that reads this file.
**Fix:** Add `plugins/mill/scripts/_junction.py` to Card 15's Reads.

### [NIT] Card 14 Reads missing `_sidebar.py`
**Step:** Card 14 — mill-groom/SKILL.md
**Issue:** Requirements say to audit "any other helper-call examples". Step 6 item 5 of mill-groom contains `_sidebar.regenerate(wiki)` — this helper's signature (`regenerate(wiki_path: Path) -> None`) is correct and needs no fix, but `plugins/mill/scripts/_sidebar.py` is not listed in Reads, preventing the implementer from formally verifying it.
**Fix:** Add `plugins/mill/scripts/_sidebar.py` to Card 14's Reads.

## Verdict

REQUEST_CHANGES
One blocking gap: `_junction.py` must be added to Card 15 Reads before implementation.