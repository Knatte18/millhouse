# Review: 12 (C) — Restructure hub junction layout — 04-skills-docs

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 04-skills-docs
date: 2026-05-06
```

## Findings

### [NIT] Card 13 reqs 1+2 specify `.portals` target ambiguously
**Step:** Card 13, requirements 1 and 2
**Issue:** Req 2 says "update `.others` → `.portals`" (implicitly keeping target `../../portals/`); req 1 says add `.portals -> ../../wiki/active/<slug>/` *if not already present from the inner-worktree update*. Since req 2 always produces `.portals`, req 1's `.portals` clause is dead text — the `../../wiki/active/<slug>/` target is silently discarded by the guard. The net result is `.portals → ../../portals/`, which is probably correct, but an implementer reading req 1 at face value may write the wrong target.
**Fix:** Remove `.portals -> ../../wiki/active/<slug>/` from req 1 entirely (it is never applied); confirm req 2 leaves the target `../../portals/` unchanged, and add that target explicitly to the rename instruction.

### [NIT] Card 14 references `wiki/active/<slug>/task.md` without supporting context
**Step:** Card 14, requirement 4
**Issue:** The proposed mill-spawn description update includes "creates `wiki/active/<slug>/task.md`" but no context file — shared decisions, batch 02 plan, or current scripts — mentions a `task.md` file in the wiki active directory. Documenting a file that batch 02 does not actually create produces a permanently inaccurate skill description.
**Fix:** Before implementing card 14, confirm what file (if any) batch 02 writes into `wiki/active/<slug>/`; update the requirement to name the correct file, or remove the claim if the directory is created with no initial content.

### [NIT] Card 13 req 5 may miss the Project shape intro paragraph
**Step:** Card 13, requirement 5
**Issue:** The "wherever `status.md`, `discussion.md`, `plan/`, `reviews/` are described at worktree root" clause is broad but doesn't explicitly name the Project shape opening sentence ("Working state (`status.md`, `discussion.md`, `plan/`, `reviews/`) lives at the worktree root on the task branch."). An implementer who reads requirements 1–4 literally and treats req 5 as only covering the Path invariants section could leave the intro paragraph stale.
**Fix:** Add the Project shape intro sentence as an explicit edit target in requirement 5.

## Verdict

APPROVE
Three NITs; the path-update requirements across all five cards are comprehensive, correctly sequenced, and consistent with the shared decisions.