# Review: 12 (C) — Restructure hub junction layout

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: discussion.md (rename-hub-junctions)
date: 2026-05-06
```

## Findings

### [GAP] Hub `.active` lifecycle after task completion

**Section:** Decisions → `.active` placement — hub-only; Technical context → millpy-cleanup.py

**Issue:** The discussion does not state what mill-merge or mill-cleanup should do with hub `.active` when the task's `portals/<slug>` entry and `wiki/active/<slug>/` directory are removed. Hub `.active` → `portals/<slug>` → `wiki/active/<slug>/` — once both are torn down, the hub junction becomes dangling. The migration section says "leave `.active` absent; next claim/spawn will fix it," implying this is acceptable stale state, but it is never stated for the post-merge case.

**Fix:** Add a statement to the mill-merge and mill-cleanup sections: either (a) mill-merge removes hub `.active` as part of teardown, or (b) stale/dangling hub `.active` is explicitly accepted and the next `mill-claim` or `mill-spawn` recreates it correctly.

---

### [NOTE] `wiki/active/` parent directory initialization

**Section:** Technical context → millpy-spawn.py

**Issue:** Mill-spawn creates `wiki/active/<slug>/task.md` but the discussion does not specify who ensures `wiki/active/` itself exists. On a fresh wiki clone with no prior tasks, the parent directory is absent.

**Fix:** Add one line: mill-spawn creates `wiki/active/` with `mkdir -p` (idempotent) before writing the slug subdirectory, or assign responsibility to mill-setup's wiki initialization step.

## Verdict

GAPS_FOUND

Hub `.active` teardown responsibility is unspecified; one NOTE on parent directory initialization.