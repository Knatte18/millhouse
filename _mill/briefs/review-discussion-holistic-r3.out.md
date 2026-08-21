MILL_REVIEW_BEGIN
# Review: mill-go: baseline-stage timeout/cold-build cost and finalize dirty-tree false positive

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not independently knowable)
reviewed_file: _mill/discussion.md
date: 2026-08-21
```

## Findings

### [BLOCKING:consistency] baseline-dispatch-background ignores 0.6's cache-path exception
**Section:** `baseline-dispatch-background` Decision / Scope bullet 3.
**Issue:** `mill-go-base/SKILL.md`'s existing "0.6. Per-batch baseline recapture" invokes `millpy-implement.py` via `<git_root>/plugins/mill/scripts/...`, explicitly documented in that section as "the one deliberate, narrow exception to the cache-form convention" (self-hosting task must run its own worktree copy, not the frozen `${CLAUDE_PLUGIN_ROOT}` cache). The Decision describes converting both "0.5" and "0.6" to the same generic `millpy-bg.py --slug ... -- "$MILL_PYTHON" millpy-implement.py --stage baseline` pattern, borrowed from `mill-plan`/`mill-start` examples that always use cache-form (`${CLAUDE_PLUGIN_ROOT}/scripts/...`) for the inner command — with no mention that 0.6's inner command must keep the `<git_root>` form while 0.5's inner command and both sections' outer `millpy-bg.py` wrapper stay cache-form.
**Fix:** Add an explicit note to the Decision (or Technical Context) that 0.6's converted invocation must preserve the `<git_root>/plugins/mill/scripts/millpy-implement.py` inner-command exception; only the outer `millpy-bg.py` call and 0.5's inner command use `${CLAUDE_PLUGIN_ROOT}`.

## Verdict

REQUEST_CHANGES
One BLOCKING: the dispatch-background decision silently drops 0.6's documented cache-path exception.
MILL_REVIEW_END
