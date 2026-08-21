MILL_REVIEW_BEGIN
# Review: mill-go: baseline-stage timeout/cold-build cost and finalize dirty-tree false positive

```yaml
duration_s: 249.3
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-21
```

## Findings

### [BLOCKING:design] baseline-dispatch-background rests on a false precedent
**Section:** `### Decision: baseline-dispatch-background` (and Scope bullet 3, Technical context bullet 3) **Issue:** Claims the `millpy-bg.py` background-dispatch+poll pattern is "already used for discussion-review and code-review CLI dispatch elsewhere in this file" (`mill-go-base/SKILL.md`). Verified false: `mill-go-base/SKILL.md` has zero occurrences of `millpy-bg`/`_bg.py`; its own "### 3. Code Review loop" dispatches via the "## Agent-mode dispatch" Task-tool/subagent-notification pattern (lines ~695-734), a structurally different mechanism (no log-polling, per lines 408-409 of the same file). The `millpy-bg.py` poll pattern only exists in `mill-start/SKILL.md`, and there only as the "Subprocess/psmux branch" fallback for discussion-review, not code-review. **Fix:** Correct the citation — either name `mill-start/SKILL.md`'s subprocess/psmux branch as the actual precedent (dropping the code-review claim), or independently justify why `millpy-bg.py` (rather than the file's own established Agent-mode dispatch pattern) is the right mechanism for a non-LLM CLI computation like `--stage baseline`.

### [NIT:scope] Other SKILL.md call sites share the identical timeout risk, unaddressed
**Section:** `## Scope` "In" bullet 3 / `### Decision: baseline-dispatch-background` **Issue:** `mill-go-base/SKILL.md` itself flags two other foreground 600000ms-capped Bash calls as sharing "the identical default-2-minute-Bash-timeout risk that motivated the original finalize-stage-CLI fix" (line ~374, finalize-stage verify replay for `millpy-fix.py`/`millpy-implement.py --stage finalize`; line ~526, `run_preflight`'s `done_gate` command) — neither is touched by this task, and the discussion's Scope/Out sections never acknowledge or exclude them. **Fix:** Add a one-line Out-of-scope note explaining why these two other identical-risk call sites are deliberately left for a future task.

## Verdict

REQUEST_CHANGES
Baseline-dispatch decision cites a code-review dispatch precedent in mill-go-base/SKILL.md that does not exist.
MILL_REVIEW_END
