MILL_REVIEW_BEGIN
# Review: Self-discovered mill-go/mill-plan skill-doc and behavior gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] `project_root` undefined-name bug missed in the 759 fix
**Section:** Decision `759-missing-import`
**Issue:** The self-validate call at `mill-plan/SKILL.md:193` passes `_plan_validate.run(plan_dir, project_root, ...)`, but `project_root` is never bound anywhere in `mill-plan/SKILL.md` (grep confirms zero other occurrences) — mill-plan's Path Setup step binds the equivalent hub-root value as `worktree_root`, not `project_root`. This is structurally identical to the `wiki_root`/`wiki_path` bug the same decision explicitly catches and fixes in this exact line, but decision 759 only mentions the `wiki_root` half.
**Fix:** Extend decision 759's "fixed in the same edit" list to also correct `project_root` → `worktree_root` in the new fenced snippet, since the edit already rewrites this call's text.

### [GAP] Holistic annotation target for #758 is underspecified
**Section:** Decision `758-mandatory-reason-annotation`, "Annotation target/format" bullet
**Issue:** The placement rule ("`## Prior failure` immediately after the batch file's frontmatter, before `## Rename mechanic`/`## Batch Scope`") is defined only against `plan-batch.md`'s section order. For the holistic branch the decision names the target as "`00-overview.md`/relevant batch file (the finding may span multiple batches)" — but `00-overview.md` has a different section order (`## Batch Index`, `## Shared Decisions`, `## All Files Touched`, no analogous slot), and choosing between "00-overview.md" vs. "relevant batch file" reintroduces exactly the card/batch-vs-whole-plan classification the decision says a uniform target was meant to avoid.
**Fix:** State explicitly where `## Prior failure` goes in `00-overview.md` (or mandate it always targets the specific batch file the holistic finding names, never the overview) and give the classification rule for "which file" in the holistic case.

### [GAP] Phase-gate widening (757) misses two crash-window phase values it should cover
**Section:** Decision `757-phase-gate-widening`
**Issue:** The four-pattern widening (`approved-*`, `reviewing-*-rN`, `fixing-*-rN`, `holistic-reviewing`) omits `self-resolved-verify-logic` (appended at `mill-go/SKILL.md:596` and `:853` — the very self-resolve step #758 makes mandatory in this same task) and `holistic-approved` (appended at line 840). A crash immediately after either append leaves `phase` at one of these values, which matches none of the widened patterns nor the exact set, so re-running mill-go still falls to "any other → surface + halt" — the exact failure mode #757 exists to close, on a case not yet covered. Notably this also weakens the rejected alternative's reasoning (consulting `## Batches` `state` was rejected as unnecessary because `phase` already discriminates resumability) — these two phase values show `phase` alone does not always discriminate it.
**Fix:** Add `self-resolved-verify-logic` and `holistic-approved` to the widened match (routing both to `## Resume`, since the underlying batch `state` remains genuinely resumable in both cases), or explain why they're intentionally excluded.

### [NOTE] Loose line-range citation for mill-plan's `signature:` convention
**Section:** Decision `759-missing-import`
**Issue:** Cites "bare `signature:` lines (e.g. lines 19-22)" in `mill-plan/SKILL.md`; only lines 19, 20, and 22 are `signature:` lines — line 21 is prose, not a third example.
**Fix:** Tighten the citation or note it's approximate (minor, doesn't affect the fix's substance).

## Verdict

GAPS_FOUND
Three GAPs: an undefined `project_root` name, an underspecified holistic annotation target, and an incomplete phase-gate widening list.
MILL_REVIEW_END
