# Review: 16 (A) — Autonomous bug-fix pipeline (mill-autofix)

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: task/discussion.md
date: 2026-05-07
```

## Findings

### [GAP] Slug derivation is untestable as prose
**Section:** § slug-derivation decision + § Testing
**Issue:** Slug derivation is described as "implemented as a helper inline in the skill instructions" (natural language prose), yet `test-autofix.py` imports and tests it as Python code — two incompatible representations.
**Fix:** Clarify whether slug derivation is a Python function (name the module/function and add it to scope) or LLM prose (remove the unit tests and describe empirical testing instead).

### [GAP] Working-tree cleanliness not enforced per iteration
**Section:** § Technical context (millpy-claim.py) + § Per-bug loop stuck cleanup helper
**Issue:** Technical context explicitly states "mill-autofix must ensure no uncommitted changes before each claim," but the per-bug loop has no such check, and the stuck-cleanup helper (`git checkout <parent_branch>` + `rm active.slug.md`) does not remove untracked files left in `task/` from a partially-executed loop iteration (e.g., crash after step e but before f).
**Fix:** Add an explicit clean-tree step to the stuck-cleanup helper (e.g., `git clean -fd task/`) and document the per-iteration pre-claim check in the loop flow.

### [NOTE] Unexpected phase values after sub-skill return not handled
**Section:** § Per-bug loop steps h–i
**Issue:** The flow routes on `phase == blocked` or `phase == planned`/`done`, but if mill-plan or mill-go exits abnormally (phase still `discussion` or `claimed`), the decision is unspecified.
**Fix:** Add one sentence: any phase value other than the expected success state is treated as `blocked` and routes to stuck cleanup.

### [NOTE] Dry-run exits after config.local.yaml is modified
**Section:** § Mill-autofix skill flow — Entry / Fetch / Cleanup
**Issue:** Step 6 writes `pipeline.autonomous_mode: true` before the dry-run early-exit in step 8. The try/finally cleanup is described for the loop but the dry-run path should also restore config.local.yaml.
**Fix:** Note that the "Cleanup (always)" section explicitly covers the dry-run early-exit, or move the config mutation to after the dry-run check.

## Verdict

GAPS_FOUND
Two gaps block plan writing: slug derivation's implementation form is ambiguous, and per-iteration working-tree cleanliness is unspecified despite being called out as required.