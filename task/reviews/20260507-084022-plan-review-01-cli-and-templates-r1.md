# Review: 29 (A) — mill-merge-in: delegate konflikter og verify-feil til sub-agent — 01-cli-and-templates

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 01-cli-and-templates
date: 2026-05-07
```

## Findings

### [NIT] Unused `slug` variable in common setup
**Step:** Card 1, `main()` common setup
**Issue:** Requirements mandate `slug = _active.read_slug(mill_dir)` but `slug` is not passed to `_run_conflicts` / `_run_verify_fix` and does not appear as a render token in either template; Python linters will flag `F841: assigned but never used`, which may fail the `git-commit` skill's lint gate.
**Fix:** Assign to `_` (i.e. `_ = _active.read_slug(mill_dir)`) to document the guard intent, or add a comment explaining it as a worktree-validation side-effect.

### [NIT] No timeout on verify subprocess in `_run_verify_fix`
**Step:** Card 1, `_run_verify_fix` subprocess call
**Issue:** `subprocess.run(args.cmd, shell=True, ...)` has no `timeout` argument; a hanging verify command blocks the CLI process indefinitely. The `timeout` value is already in scope (passed as a parameter) but is only forwarded to `_implementer_sonnet.run`.
**Fix:** Pass `timeout=timeout` to the verify `subprocess.run` call so a hung test suite doesn't stall the merge-in workflow.

## Verdict

APPROVE
Token contracts between Card 1 and the two templates are consistent; dispatch logic, error handling, and shared-decision alignment are correct.