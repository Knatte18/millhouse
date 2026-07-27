MILL_REVIEW_BEGIN
# Review: mill-vscode/mill-spawn leak CLAUDE_CODE_CHILD_SESSION into spawned VS Code windows

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-27
```

## Findings

### [GAP] Testing scope narrower than Technical context's mock-audit claims
**Section:** Testing / Technical context
**Issue:** Technical context frames all 18 `test-millpy-vscode.py` sites and all 8 `test-millpy-terminal.py` sites as needing env assertions ("5 ... need updating ... for this fix's `env` assertions"; "the other 3 ... need ... only new assertions added"; "100% ... need the signature change"), but Testing names only ~2 exemplar scenarios per file (`--slug`/numeric-selection + `--new`/spawn-and-open for vscode; auto-select + numeric-picker for terminal) for actual new assertions. Scope/In's "at each of the four [call] sites" agrees with Testing's narrower reading, leaving Technical context the outlier.
**Fix:** State explicitly whether new `kwargs["env"]` assertions land on every mock site in both files or only one exemplar per real call site, so a plan writer doesn't mis-scope the test-update task in either direction.

### [GAP] `code` CLI's default single-instance/window-reuse behavior unaddressed
**Section:** Problem / Technical context (`_build_code_argv`)
**Issue:** Neither launch site passes `--new-window`/`-n`; VS Code's default CLI behavior, when an instance is already running, is to message that instance to open a new window rather than launch a fresh OS process — in that path the new window's extension host/terminal environment comes from whenever the already-running instance was originally started, not from this (now-scrubbed) `subprocess.run` call's `env=`. The repo's own `--filter-open`/`_vscode_processes.find_open_vscode_paths` machinery shows multiple simultaneous worktree windows sharing one VS Code session is the expected usage pattern, so this isn't a corner case the fix can ignore by assumption.
**Fix:** Confirm whether repeat `code` invocations against an already-running instance bypass the newly-scrubbed env; either scope that as a known limitation with rationale, or address it (e.g. `--new-window`) so the fix holds for the multi-window case the codebase already anticipates.

## Verdict

GAPS_FOUND
Two unresolved gaps: test-assertion coverage scope, and VS Code instance-reuse env propagation for repeat launches.
MILL_REVIEW_END
