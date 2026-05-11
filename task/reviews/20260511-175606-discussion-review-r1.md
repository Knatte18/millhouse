I have enough information to write the review.

---

# Review: 47 (A) — mill-merge-in: allowlist for known-broken pre-existing test failures

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-11
```

## Findings

### [NOTE] Technical Context misstates Entry step for config loading
**Section:** Technical context — Config loading
**Issue:** The claim "already called in Entry (step 3)" is wrong — Entry step 3 is `_parent_branch.resolve`, not a config load. The current SKILL.md has no explicit config-load step; `cfg` is implicitly required because Entry step 2 calls `_marker.slug_from_branch(git_root, wiki_path, cfg)`.
**Fix:** Clarify that the plan writer should add an explicit config-load instruction at the start of Step 4 (before the loop), rather than relying on a non-existent Entry step 3 instruction. `cfg` will be available in practice because the LLM executing the SKILL.md already needs it for Entry step 2.

### [NOTE] Report section (Step 6) not addressed for skipped verifies
**Section:** Scope (In) / Technical context (new flow)
**Issue:** The current SKILL.md Step 6 Report says `<M> batch tests ran`, but with skipped verifies, `<M>` is ambiguous (total commands vs. actually-run commands). Whether to update Step 6 is not addressed.
**Fix:** Explicitly state whether Step 6 Report is in-scope for updating (e.g., `<M> batch tests ran, <K> skipped`), or call it explicitly out-of-scope with a note that per-skip log lines are sufficient.

## Verdict

APPROVE
Discussion is clear and complete; two minor NOTEs do not block plan writing.