MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: Phase Plan Review gate, convergence, and DAG-validation correctness bugs — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (best-effort self-assessment; exact point version unconfirmed)
reviewed_file: plan/
date: 2026-08-21
```

## Findings

### [NIT:consistency] Card 1's step 4.5->3.5 rename leaves a stale cross-file reference
**Location:** Batch 1 / Card 1. **Issue:** After relocating and renumbering mill-plan's "Step 4.5" to "Step 3.5", `plugins/mill/skills/mill-go-base/SKILL.md:801` still reads "The two-pass cap mirrors mill-plan's existing step 4.5." — a step name that will no longer exist in mill-plan/SKILL.md once this batch lands. No card in this plan touches that line or notes it as accepted drift. **Fix:** Add a one-line edit to `mill-go-base/SKILL.md:801` (or record the drift as an accepted follow-up in Shared Decisions, matching the precedent already set for the deferred mill-start Timeline bug).

### [NIT:consistency] Card 10 adds real `git` subprocess calls, contradicting the test file's stated no-real-git convention
**Location:** Batch 2 / Card 10. **Issue:** `test-plan-validate.py`'s own module docstring states "no real LLM, no real git, no network" (line 4), but Card 10's new gitignore fixtures require `git init` plus a genuine `git check-ignore` subprocess call (since `resolve_ref_paths`'s soft-fail path shells out to real git); Card 10 doesn't update that docstring line. Card 10's own hedge — "check whether test-plan-validate.py already has a git-fixture helper... in a sibling test file this file's own imports reference" — doesn't actually lead anywhere today, since `test-plan-validate.py` currently imports nothing but `_plan_validate`; the real existing helper (`init_minimal_git_repo`, pygit2-based, in `_test_helpers.py`) isn't reachable via that clause as written. **Fix:** Update the docstring's "no real git" claim to note the one documented exception, and name `_test_helpers.init_minimal_git_repo` directly rather than relying on an import-based hedge that doesn't currently resolve.

## Verdict

APPROVE
Two low-severity doc-consistency NITs found; all card requirements, call shapes, and cross-references verified accurate against source.
MILL_REVIEW_END
