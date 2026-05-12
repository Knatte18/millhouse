Now I have enough context to write the review. I've identified:

1. A direct contradiction between the Decision block and Q&A log on the orphan-scan oracle criterion.
2. The compat shim's coverage overstated — it only covers `status.md` but scope claims full transparency for all in-flight `task/` access.
3. The template's `active/<SLUG>/` drift from live `task/` paths is not called out — a mechanical "replace `task/`" pass would miss it.
4. The `.portals` per-worktree mechanism is informally stated, not formally decided.

---

# Review: 33 (A) — Working-dir rename + portals redesign + junction cleanup

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-12
```

## Findings

### [GAP] Orphan-scan oracle contradicts itself across sections
**Section:** § "mill-cleanup orphan portal scan" Decision vs Q&A log (last entry)
**Issue:** The Decision block picks target-not-exists as oracle and explicitly rejects "check slug against Home.md" ("doesn't catch hub self-portals or force-deleted slugs"). The Q&A log then picks slug-vs-Home.md as the oracle and claims it "covers hub-self-portals." The Testing section introduces a third criterion (git-worktree-exists AND target-exists). All three differ and an implementer must choose one.
**Fix:** Resolve in the Decision block: pick one oracle with a clear rationale, note why the others were set aside.

### [GAP] Compat shim coverage overstated for in-flight worktrees
**Section:** § Scope — "No migration of existing in-flight worktrees' `task/` dirs (compat shim handles these transparently)"
**Issue:** The Technical Context describes a shim only in `_status.py` for `status.md` path resolution. After the config change to `_mill/`, any review operation on an in-flight task (which reads `plan_dir` and `reviews_dir` from the same config) will fail — those files are still at `task/plan/` and `task/reviews/`, but config now points to `_mill/`. The claim of transparent handling does not hold for plan and review operations.
**Fix:** Either extend the shim to cover all three paths (`status.md`, `plan/`, `reviews/`) or narrow the claim: "compat shim handles status.md transparently; operators must rename `task/` → `_mill/` in any in-flight worktree before running review operations."

### [NOTE] Template path drift not acknowledged in scope or technical context
**Section:** § Technical Context — `templates/wiki-config.yaml` bullet
**Issue:** The live wiki config has `task/discussion.md`; the template has `active/<SLUG>/discussion.md`. The discussion describes the template change as "update paths: to `_mill/`" without flagging the different starting point. A plan batch written as "find/replace `task/` → `_mill/`" will silently miss the template's `active/<SLUG>/` lines.
**Fix:** Add one sentence noting the template drift so the plan writer uses an explicit rewrite for the `paths:` block in the template rather than a mechanical string substitution.

### [NOTE] `.portals` per-worktree creation mechanism informally stated
**Section:** § "hub junction inventory after redesign" Decision
**Issue:** The Decision block lists two implementation alternatives ("mill-spawn creates explicitly" vs "new wiki/config.yaml entry with non-slug token") and labels one "the simpler approach" without formally choosing it. The Q&A log only confirms the outcome (both hub and per-worktree) without naming the mechanism.
**Fix:** Promote the chosen mechanism to a formal "Decision:" sentence so the plan writer does not have to infer it.

## Verdict

GAPS_FOUND — two gaps must resolve before planning: the orphan-scan oracle contradiction and the compat-shim scope overstatement.