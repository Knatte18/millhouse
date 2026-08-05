MILL_REVIEW_BEGIN
# Review: mill-go's one-shot pre-batch-1 baseline can't cover a task's own later per-batch-baseline capability

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-05
```

## Findings

### [GAP] Agent-mode "step 6" hook site is a shared step, not a unique call point
**Section:** Decision: hook placement (Agent-mode bullet)
**Issue:** The decision says to insert the hook "immediately before step 6's `--stage finalize` invocation (see `## Agent-mode dispatch` step 6)," but step 6 of `## Agent-mode dispatch` (verified in `plugins/mill/skills/mill-go/SKILL.md`, "Run finalize stage") is a shared generic step reused verbatim at ~8+ call sites across the file (`### 1. Implement`, `### 3. Code Review loop`, the fix loop, Holistic Review, etc., for `millpy-implement.py`, `millpy-review-code.py`, and `millpy-fix.py` alike) — only the implementer CLI's own finalize (`batch_status.get("verify_baseline_failures")`, confirmed at `millpy-implement.py` line ~730) actually reads/uses the baseline being retried. "One new sub-step" is inconsistent with modifying the shared step-6 definition itself, which would fire the check before every review/fix finalize call too, contradicting "once per task run" placement intent.
**Fix:** State explicitly that the hook is inserted locally within `### 1. Implement`'s own Agent-mode dispatch instance (the one with `<cli> = millpy-implement.py`), not into the shared `## Agent-mode dispatch` step-6 definition — matching the file's existing precedent of locally-scoped, per-call-site insertions (e.g. the tree-guard checkpoints repeated at lines ~508/530/609/794/835 rather than folded into the shared pattern).

### [NOTE] Q&A log entry predates the trigger-condition fix
**Section:** Q&A log, "Self-hosting gate + retry-worthiness check" entry
**Issue:** This entry still describes the inline check as only "the 'baseline still missing' check," omitting the non-`None`-verify half added by the round-1 GAP fix (documented further down in the same Q&A log and in the current Decision: retry trigger condition text).
**Fix:** Update that Q&A entry to mention both halves of the condition, or note it's superseded by the later round-1 fix entry, to avoid a plan writer reading only the earlier entry.

## Verdict

GAPS_FOUND
Agent-mode hook-placement wording points at a shared multi-site step, not the intended single insertion point.
MILL_REVIEW_END
