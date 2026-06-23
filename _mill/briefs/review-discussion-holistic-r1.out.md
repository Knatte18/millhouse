MILL_REVIEW_BEGIN
# Review: Fix agent-dispatch cwd guard, implementer self-termination, and false-success contracts

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-23
```

## Findings

### [GAP] Completeness-gate commit baseline is underspecified
**Section:** Decision `implementer-no-yield-and-completeness` + Technical context (line 253)
**Issue:** The gate counts "content commits since `start_sha`", but `start_sha` is captured (millpy-implement.py ~212) *before* the `mill-go: start batch` commit is created (~239), so `start_sha..HEAD` includes that orchestration commit; line 253's "excluding the prepare pre-commit / empty commits as appropriate" leaves the exclusion mechanism undefined.
**Fix:** State the exact count (e.g. raw `git rev-list --count start_sha..HEAD`, accepting the start-commit inflation as safe since over-count never falsely demotes) so the plan writer cannot pick an inconsistent filtering scheme.

### [GAP] Threading new params through finalize_from_output not specified
**Section:** Decision `implementer-no-yield-and-completeness` / `finalize-rejects-dirty-in-scope-tree`
**Issue:** Both new checks live in `_forward_output`, but the agent-dispatch path enters via `finalize_from_output` (millpy-implement.py ~195), which has no `card_count`/`task_dir`/`parent_branch` params today; the discussion threads from `millpy-implement.py` to `_forward_output` but skips the intermediate `finalize_from_output` signature.
**Fix:** Name `finalize_from_output` as a signature that must also gain the new params and forward them, so subprocess and agent-dispatch finalize stay in parity.

### [NOTE] parent_branch resolution for finalize dirty-tree check
**Section:** Decision `finalize-rejects-dirty-in-scope-tree`
**Issue:** mill-go 2b resolves parent via `_parent_branch.resolve(status_path, interactive=False)` (SKILL.md ~248); the finalize CLI must use the non-interactive form since no operator is attached, but the discussion says only "resolved from status.md as mill-go's 2b gate does."
**Fix:** Pin `interactive=False` explicitly for the finalize-path resolution.

## Verdict

GAPS_FOUND
Two counting/threading specifics need pinning before the plan writer proceeds; decisions otherwise sound and source-grounded.
MILL_REVIEW_END
