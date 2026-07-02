All discussion claims verified accurate against source (the `_dispatch` single-`_ensure_daemon`-call structure, git-pr Step 1.5 env-var guard, mill-finalize Step 5 invocation, skills-index `_extract_frontmatter` YAMLError→None collapse, and migrate script's unguarded `_print_task_brief`). The discussion is decision-complete with rationale and rejected alternatives for all four issues. A few minor refinements remain.

MILL_REVIEW_BEGIN
# Review: Fix daemon health-check race, finalize env-var delivery, skills-index drop, and encoding crash

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-02
```

## Findings

### [NOTE] Respawn failure mid-retry unspecified
**Section:** Decisions › daemon-respawn-on-retry
**Issue:** If the in-loop `_ensure_daemon()` re-invocation itself raises `WikiStartupError` (respawn fails), the decision does not say whether that propagates immediately or the loop continues to exhaust its backoff budget.
**Fix:** State the intended behavior (propagate `WikiStartupError` as terminal vs. keep retrying) so the plan writer implements the except handler consistently.

### [NOTE] git-pr flag not surfaced in Usage/argument-hint
**Section:** Decisions › git-pr-explicit-flag; Technical context › git-pr
**Issue:** The decision adds `--skip-task-branch-guard` and updates Steps 1.5/2, but is silent on whether git-pr's `## Usage` block and `argument-hint:` frontmatter (currently `[base-branch]`) should mention the flag or leave it internal-only.
**Fix:** Note whether the flag stays undocumented (mill-finalize-internal) or is added to the public usage surface.

### [NOTE] skills-index error-signalling mechanism left open
**Section:** Decisions › skills-index-fail-loud
**Issue:** Decision offers "raise a typed exception or return a sentinel distinct from `None`" without choosing; observable behavior is identical but the internal contract between `_extract_frontmatter` and `_scan` differs.
**Fix:** Fine to defer to the plan, but flag it as a deliberate implementation choice so the plan card names one.

## Verdict

APPROVE
Decision-complete and source-grounded; only minor implementation-latitude notes remain.
MILL_REVIEW_END