MILL_REVIEW_BEGIN
# Review: Review prompt/output file listings resolve plan-relative paths to absolute before display, instead of keeping them relative

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (self-assessed; not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] tool-use-mode-relative rationale misdescribes `run_tool_use`
**Section:** `### tool-use-mode-relative`
**Issue:** The rationale claims "`_llm_claude.run_tool_use` passes `cwd` through" as the reason a relative path resolves correctly for the reviewer's `Read` tool. Verified against source: `run_tool_use()` (`_llm_claude.py:481-514`) has no `cwd` parameter at all and does not forward one to `_invoke()`; only `run_implementer()` (line 525) and the internal `_invoke()` (line 326) accept/forward `cwd`. `_reviewer_single.run()` (the actual dispatcher for review calls) also builds its `kwargs` without `cwd` (lines 71-78). So the tool-use `claude` subprocess's cwd is whatever the *ambient* Python process cwd happens to be at invocation time, never a value this code path explicitly sets to the task worktree.
**Fix:** Either correct the rationale to describe the real mechanism that guarantees ambient cwd == task worktree at every dispatch path (and cite it), or drop the cwd claim and instead have the plan verify/pin this invariant (e.g. an integration-level check that a live tool-use `Read` of a relative path succeeds), since the decision to relativize `read_list`/`batch_list` depends on this premise being true for correctness, not just cosmetics.

## Verdict

REQUEST_CHANGES
Tool-use-mode-relative decision rests on a source-contradicted claim about `run_tool_use` forwarding `cwd`.
MILL_REVIEW_END
