# Review: 28 (A) — review-plan robustness

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: task/discussion.md
date: 2026-05-07
```

## Findings

### [GAP] Bug A scope covers only step 2; step 4.5 and step 1.5 re-run also have bare calls
**Section:** Scope / Technical context / File map
**Issue:** The file map says "step 2 (bug A: bare CLI call)" but the SKILL.md has two additional autonomous `millpy-review-plan.py` invocations without `millpy-bg`: step 4.5's retry block (lines 115-116) and step 1.5's post-validator-fix re-run (line 77). The problem description says "the CLI is invoked without the wrapper that every other review CLI uses" — that diagnosis applies to all three call sites equally, but the discussion only commits to fixing step 2.
**Fix:** Extend the file map and scope to state that all autonomous invocations of `millpy-review-plan.py` in the SKILL.md receive the `millpy-bg` wrapper — step 2, step 4.5, and the step 1.5 re-run. (Step 6's user-facing example is a manual invocation and can stay as-is.)

### [NOTE] `_check_wiki_config_mutation` error message still advises `--skip-validate`
**Section:** Technical context / Bug E
**Issue:** `_plan_validate.py:642` says `"use --skip-validate if a bootstrap card is present"`. After bug E's fix, the correct operator action for that single check is `--skip-check wiki-config-mutation`; `--skip-validate` is now the heavier option. The discussion updates the SKILL.md fix-table row but leaves the error message unchanged; operators reading raw validator JSON will still be steered toward the nuclear flag.
**Fix:** Add updating the error message at `_plan_validate.py:642` to the `_plan_validate.py` scope line (already in-scope for the `skip_checks` param addition).

## Verdict

GAPS_FOUND  
One call-site ambiguity in bug A's scope must be resolved before the plan can correctly target all affected SKILL.md steps.