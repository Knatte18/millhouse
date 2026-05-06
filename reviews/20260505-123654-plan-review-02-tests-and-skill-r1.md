# Review: 1 — Implementer dispatch-CLI + Agent-resume fix (conflicts with 8) — 02-tests-and-skill

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 02-tests-and-skill
date: 2026-05-05
```

## Findings

### [BLOCKING] Card 5 Edit 2 leaves orphaned state-management instructions
**Step:** Card 5 — "Edit 2 — REQUEST_CHANGES section"
**Issue:** Edit 2 replaces only the blockquote + `_implementer_sonnet.run` spawn call. The preceding text — "set batch state → `fixing`. `_status.append_phase(...)`. Commit on the task branch: `git -C <worktree> add status.md reviews/<file> && git -C <worktree> commit -m "..."`. **Resume the implementer session** with a new user message:" — is left in place. After the edit the Builder would still manually set state, call `append_phase`, and commit, then invoke the CLI which also does all three, producing a double commit. The dangling "with a new user message:" phrase introducing the CLI invocation bullet makes the resulting instruction incoherent.
**Fix:** Replace the entire `REQUEST_CHANGES` bullet (from "— set batch state → `fixing`" through "On stuck → escalate."), not just its tail. The replacement is already correct; the starting boundary of the replacement block is wrong.

### [NIT] `addCleanup` unavailable in standalone-function pattern
**Step:** Card 4 — CWD isolation guidance
**Issue:** The plan recommends `addCleanup(os.chdir, original_cwd)` for restoring cwd, but `addCleanup` is a `unittest.TestCase` instance method. The required pattern ("Follow the exact pattern of `test-millpy-validate-plan.py`") uses standalone functions, not `TestCase` subclasses. An implementer who follows the recommendation literally gets `AttributeError: 'function' object has no attribute 'addCleanup'`.
**Fix:** Change guidance to match the reference test: use try/finally (`try: ... finally: os.chdir(orig)`).

### [NIT] Edit 3 description names wrong commit
**Step:** Card 5 — "Edit 3 — Board discipline"
**Issue:** "The affected lines are in the Prepare commit and the **Approve** commit annotations." The Approve commit (`mill-go: approve batch {batch_name}`) has no `(no push)` annotation. The second affected commit is the Handoff/done commit (`mill-go: done {slug}` in `## Handoff`).
**Fix:** Change description to "Prepare and Handoff/done commits". The rule itself ("remove `(no push)` from any line ending with it") is unambiguous and will find the correct lines regardless.

## Verdict

REQUEST_CHANGES
Edit 2's replacement boundary is wrong and produces a broken SKILL.md with duplicate state management.