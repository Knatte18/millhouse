# Review: 39 (A) — mill-start question-format UX

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-09
```

## Verdict

APPROVE — all decisions are made, scope is precisely bounded, and all technical claims verified against source.

The discussion is unusually thorough. Every section I spot-checked matches reality: `_subprocess_util.py` confirmed to have `CREATE_NO_WINDOW` already (line 89) but no `popen_detached`; `millpy-bg.py` launcher at lines 94/136 confirmed to use bare `subprocess.run`/`Popen` without `CREATE_NO_WINDOW`; `_inplace.prompt_stale_worktree` confirmed at line 74 with `1→inplace, 2→worktree, 3→abort`; test names at lines 123–175 match the rename targets exactly; `_review_common.py:610` and `conversation/SKILL.md:34` match the descriptions. The one non-trivial implementation detail — that `CompletedProcess.stdout` is `None` (not `""`) when stdout is redirected — is pre-empted by the Gotchas section and is safely deferred to implementation. The test-subprocess-util.py file already exists; the "or extend an existing file if one exists — confirm during plan" hedge covers this correctly.