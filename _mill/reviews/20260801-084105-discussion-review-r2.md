MILL_REVIEW_BEGIN
# Review: Add mill-quick: skip-review pipeline for simple tasks

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-01
```

## Findings

### [GAP] No concurrency guard for double-invocation of mill-quick
**Section:** Failure modes / Scope
**Issue:** mill-go acquires a builder lock at Entry specifically to prevent two concurrent sessions mutating `status.md`/committing on the same task branch (`mill-go/SKILL.md` "4. Acquire the builder lock" and Principles: "One task per worktree. The builder lock enforces this at runtime."). mill-quick is explicitly modeled as closest to mill-go's Builder role but the discussion never states whether it needs an equivalent lock, or explicitly decides one is unnecessary and why.
**Fix:** Add a Decision (or Scope/Out bullet) on whether mill-quick acquires `millpy-builder-lock.py` before writing `phase: implementing`, or explicitly states the operator-trust model makes this unnecessary.

### [GAP] Fix-commit mechanism vs. commit-push discipline is unresolved
**Section:** Technical context — Commit-push discipline / Commit discipline
**Issue:** The codebase convention for implementer commits is to invoke the `git-commit` skill (`implementer-brief.md` step 1: "Stage the affected files and commit by invoking the `git-commit` skill... Do not call raw `git commit`"), which unconditionally pushes (`git-commit/SKILL.md` Rules: "Push to remote. Set upstream if needed"). This directly conflicts with the discussion's own "Commit-push discipline" bullet, which requires the fix commit to stay unpushed until mill-merge. The discussion never states whether mill-quick's fix commit goes through `git-commit` (gets lint/codeguide-update, but pushes prematurely) or a raw `git add`/`git commit` (matches push discipline, but skips lint/codeguide sync that every other commit in the codebase gets).
**Fix:** Add an explicit Decision stating which mechanism the fix commit uses, and if raw git commands, whether lint/codeguide-update is deliberately skipped for mill-quick's fix commit.

### [NOTE] "Unconditionally followed by a code-review loop" overstates mill-go's review coupling
**Section:** Technical context (last bullet)
**Issue:** The claim "every current `mill-implementer-*` dispatch in `mill-go` is unconditionally followed by a code-review loop" is contradicted by `mill-go/SKILL.md`'s own per-batch and holistic review gates (`roles.code-review.batch.reviewer: null` skips batch review entirely; `roles.code-review.holistic.reviewer` non-null gates holistic review) — this hub's own `mill-config.yaml` currently has `code-review.batch.reviewer: null`, i.e. review is already skippable today.
**Fix:** Soften to "always structurally reaches a review-loop code path, even when config disables it at runtime" or drop the "unconditionally" framing — doesn't change any mill-quick decision, informational only.

## Verdict

GAPS_FOUND
Two gaps: missing concurrency guard, and unresolved fix-commit-mechanism-vs-push-discipline conflict.
MILL_REVIEW_END
