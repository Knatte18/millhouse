I have verified all major claims. The discussion is accurate against source: `_dispatch()` resolves `(host, port, token)` once before the retry loop (line 157) and catches all three exceptions with `[2,4,8]` backoff (lines 160-174); `_extract_frontmatter()` collapses parse errors to `None` (lines 47-50); git-pr's Step 1.5 guards on `MILL_FINALIZE_PR_CLEANUP` (lines 36-73); mill-finalize Step 5 uses the env-var prefix (line 99); `millpy-wiki-migrate.py._print_task_brief` prints via plain `print()` (lines 58-59). The `--auto` flag pattern exists in mill-start. No existing skills-index test exists (the `_extract_frontmatter` in `test-agents-defs.py` is an unrelated local copy). `millpy-wiki-migrate.py` has no SKILL.md invocation site — it is a manually-run one-shot tool.

MILL_REVIEW_BEGIN
# Review: Fix daemon health-check race, finalize env-var delivery, skills-index drop, and encoding crash

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-02
```

## Findings

### [GAP] Encoding fix leaves two non-equivalent options unpicked
**Section:** Decisions → encoding-crash-scope
**Issue:** The decision offers `sys.stdout.reconfigure(...)` in-script OR `PYTHONIOENCODING=utf-8` in "invocation docs/wrapper" without choosing; these are not equivalent — the script has no SKILL.md/wrapper invocation site (verified: only a manual run + one integration test invoke it), so the env-var-in-docs path relies on a human remembering a prefix and would not actually prevent the crash.
**Fix:** Pick the in-script `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` approach explicitly, since the tool is run ad hoc with no controllable invocation prefix.

### [NOTE] git-pr Step 2 base-branch parse has no flag concept
**Section:** Scope / Decisions → git-pr-explicit-flag
**Issue:** Scope only updates Step 1.5 to recognize `--skip-task-branch-guard`, but git-pr Step 2 resolves the base branch from "the argument the user provided" with no notion of flags; `/git-pr <parent_branch> --skip-task-branch-guard` passes two tokens.
**Fix:** State that Step 2's base-branch resolution must strip/ignore the `--skip-task-branch-guard` flag so it is never mistaken for a positional base branch.

### [NOTE] "raw title/brief/body" slightly overstates print site
**Section:** Technical context → Encoding safety
**Issue:** `_print_task_brief()` prints `title` and truncated `brief` raw but does not print `body` (it emits only a " BODY" marker), so the "raw title/brief/body" phrasing is inaccurate.
**Fix:** Reword to "raw title/brief" to avoid a plan writer expecting body pass-through; the guard is still warranted for title/brief.

## Verdict

GAPS_FOUND
One implementation choice (encoding fix approach) must be resolved before planning; two minor notes.
MILL_REVIEW_END