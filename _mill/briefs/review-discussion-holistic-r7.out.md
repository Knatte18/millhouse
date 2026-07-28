MILL_REVIEW_BEGIN
# Review: mill-vscode/mill-spawn leak CLAUDE_CODE_CHILD_SESSION into spawned VS Code windows

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-28
```

Verified against source: all four launch call sites and their exact line numbers
(`millpy-vscode.py:132`, `millpy-vscode.py:275`, `millpy-terminal.py:118`,
`millpy-terminal.py:121`), the `_llm_claude.py` `STRIP_VARS`/lines 82-90/332/358/384
precedent and its psmux-vs-direct-`claude -p` distinction, `_subprocess_util.py`'s
`run()`/`popen_detached()` API and existing `test-subprocess-util.py` import line,
`millpy-spawn.py`'s and `_vscode.py`'s confirmed absence of `code` subprocess spawns,
and the `test-millpy-vscode.py` (18 mock sites, all kwargs-discarding) /
`test-millpy-terminal.py` (5-vs-3 kwargs split, exemplar lines 74/342/122) audits —
all check out exactly as described, including the specific mock-site content proving
`env` is dropped by every non-exemplar site. No other `code`/`claude` subprocess
launch sites exist elsewhere in `plugins/mill/scripts/`. No `CONSTRAINTS.md` at the
hub root, confirmed. All four `### Decision:` entries carry rationale and rejected
alternatives; no open TBDs or hedge language found. Scope, testing strategy, and the
accepted instance-reuse limitation are stated precisely enough that a plan writer
would not need to guess.

## Verdict

APPROVE
All claims verified against source; scope, decisions, and testing are precise and internally consistent.
MILL_REVIEW_END
