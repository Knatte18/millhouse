MILL_REVIEW_BEGIN
# Review: mill-vscode/mill-spawn leak CLAUDE_CODE_CHILD_SESSION into spawned VS Code windows — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-28
```

Verified all three cards of batch `scrub-session-env` against `00-overview.md` and `01-scrub-session-env.md`.

- `_subprocess_util.py`: `_SCRUBBED_ENV_KEYS` frozenset (exact 3-key allowlist, no prefix param) placed after `_GRACE_SECONDS`/`_CREATE_BREAKAWAY_FROM_JOB` per spec. `scrub_env(env=None)` builds via dict comprehension, never mutates input, defaults to live `os.environ`. Docstring `Public API:` entry added in the existing style. `run()`/`popen_detached()` bodies untouched, matching the "untouched" Shared Decision.
- `test-subprocess-util.py`: import line updated exactly as specified; new cases (p)/(q)/(r) match the required allowlist/no-op/default-os.environ coverage, including the non-mutation assertion and the `CLAUDE_CODE_USE_BEDROCK` over-strip regression check.
- `millpy-vscode.py`: `import _subprocess_util` added in alphabetical position; both `_spawn_and_open()` and the interactive picker in `main()` now pass `env=_subprocess_util.scrub_env()`; the "must keep its console" comment is preserved verbatim.
- `millpy-terminal.py`: same pattern applied to both the Windows and POSIX `claude` launch branches, comments preserved.
- Test files for both scripts: exactly the two (`vscode`) / one (`terminal`) exemplar blocks named in the batch were updated with `patch.dict(os.environ, ...)` + env-kwarg capture + the three env assertions (not-None, no allowlisted keys, `PATH` preserved); no other existing test blocks were touched, consistent with "no other test in this file changes."
- No out-of-plan files present; `All Files Touched` in the overview matches the 6 edited files plus the 2 already-context source files in the manifest exactly.
- Cross-batch/cross-card contract (helper produced by Card 1, consumed by Cards 2/3) is compatible — signature and behavior match call-site usage in both scripts.
- No duplicate reimplementation of the scrub logic was introduced within this batch's scope; the codebase's separate `_llm_claude.py::STRIP_VARS` (git-var stripping, pre-existing, different key set) is explicitly out of scope per the batch's own `Batch Tests` note and is unrelated to this task's files.

## Verdict

APPROVE
Implementation matches every card and Shared Decision in the plan with no deviations found.
MILL_REVIEW_END
