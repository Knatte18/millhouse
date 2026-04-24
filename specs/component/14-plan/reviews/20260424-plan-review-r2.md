# Review: junction-rule enforcement + _paths.py consolidation — holistic r2

```yaml
verdict: APPROVE
reviewer_model: sonnet-4-6 (via Agent tool)
reviewed_file: specs/component/14-plan/
date: 2026-04-24
based_on: r1 findings; plan files as of 20260424
```

## r1 Finding Resolution

### [RESOLVED] BLOCKING — Card 10 missing line-47 scratch reference
`04-docs.md` Card 10 requirements now explicitly call out **two** lines to update in "Repo layout pointers": the `integration_tests/` pointer (line 47) AND the `.millhouse/` pointer (bottom of section). Both are listed with the exact new text. Finding is closed.

### [RESOLVED] NIT — Card 7 variable name inconsistency
`03-scratch-move.md` Card 7 now names both forms explicitly: `test-spawn.py`, `test-merge.py`, `test-plan-assets.py`, `test-go-assets.py`, and `smoke-llm-claude.py` use `SCRATCH`; the three review tests use `_SCRATCH`. An implementer doing the pass will see both forms and apply the same substitution. Finding is closed.

### [RESOLVED] NIT — Card 7 missing `test-bootstrap.ps1` prose comment
Card 7 now explicitly calls out the prose comment (~line 22) alongside the `$scratch` variable, with exact replacement text for both. Finding is closed.

## Fresh Pass

No new blocking issues found. Two observations:

### [NIT] `resolve_git_root` missing from error-path coverage note in `test-paths.py`
Card 2 says `resolve_git_root` is NOT unit-tested and asks for "a comment in the test file pointing at that coverage" — but does not name which integration test provides that coverage. The batch-verify says `test-spawn.py`, not the unit-test comment. Minor: the implementer may omit the specific test name in the comment, leaving a vague "see integration tests" note.
- Low risk — integration coverage exists regardless.
- Consider: Card 2 could say "add a comment: `# resolve_git_root is exercised by test-spawn.py and test-merge.py`" to spare the implementer a grep.

### [NIT] `00-overview.md` "All Files Touched" lists `test-review-discussion.py`, `test-review-plan.py`, `test-review-code.py` with `(SCRATCH constant)` — mismatches the `_SCRATCH` name now clarified in Card 7
- The list is a reference index, not instructions, so it does no harm.
- Cosmetic only — could say `(_SCRATCH constant)` for those three files to stay consistent with Card 7's clarification.

## Verdict

APPROVE
All three r1 findings are cleanly resolved. Two cosmetic NITs in the fresh pass — neither blocks implementation. Plan is clear, complete, and safe to execute.
