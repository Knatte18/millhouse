MILL_REVIEW_BEGIN
# Review: mill-go: baseline-stage timeout/cold-build cost and finalize dirty-tree false positive — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Sonnet 5 (claude-sonnet-5)
reviewed_file: plan/
date: 2026-08-21
```

## Findings

### [BLOCKING:consistency] "0.6" inner dispatch drops the pre-edit PYTHONPATH worktree override
**Location:** Batch 3 / Card 6, requirement 6d. **Issue:** The pre-edit "0.6" block set `PYTHONPATH="<git_root>/plugins/mill/scripts"` directly on the inner `millpy-implement.py` invocation; the new nested `millpy-bg.py --slug baseline-recapture -- "$MILL_PYTHON" "<git_root>/.../millpy-implement.py" --stage baseline` sets no PYTHONPATH for the inner command at all, and `millpy-bg.py`'s launcher/worker (`_launcher_main`/`_worker_main`) pass no `env=` override to either `popen_detached` or `subprocess.run`, so the inner command inherits the OUTER call's `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` (cache path) instead. 6e's replacement prose still claims this preserves "the one deliberate, narrow exception to the cache-form convention" for the inner command, but the actual code block no longer implements that exception for PYTHONPATH — only the script-path argument is worktree-form now. **Fix:** Reinstate an explicit `PYTHONPATH="<git_root>/plugins/mill/scripts"` prefix on the inner command inside the `-- ` payload, or explicitly justify in 6e why relying on inherited cache-form PYTHONPATH is safe here (e.g. cite Python's script-directory sys.path[0] precedence) instead of silently dropping it.

### [BLOCKING:consistency] "0.5" halts on `dead` liveness while "0.6" treats identical case as no-op
**Location:** Batch 3 / Card 6, requirements 6a vs 6f. **Issue:** 6a's new poll instructions for "0.5" branch `"dead" -> surface a clear message... and halt`, contradicting the section's own retained, untouched principle a few lines below ("this pre-flight step never blocks the task" / "log the reason and continue to batch 1 anyway"). 6f's "0.6" Failure handling explicitly lists "a `dead` liveness-check result (the worker died mid-run)" as one of several causes treated as a no-op ("Never escalate to `stuck`/blocked over a recapture failure."). The two near-identical dispatch patterns in the same card handle the identical underlying signal oppositely. **Fix:** Make "0.5"'s `dead` handling consistent with its own "never blocks" principle (log and continue, matching "0.6"'s treatment) or explain why "0.5" specifically must halt where "0.6" must not.

### [BLOCKING:scope] `_bg.py` omitted from Card 6's Context despite naming `check_bg_status`
**Location:** Batch 3 / Card 6, requirement 6a (liveness-check snippet). **Issue:** Requirements 6a prescribes a literal `python -c "import _bg, json; ... _bg.check_bg_status(...)"` snippet and describes its return-tuple contract, but `_bg.py` (where `check_bg_status` is defined) is not listed in Card 6's `Context:` (only `CLAUDE.md`) or `Edits:` (only `mill-go-base/SKILL.md`) — the stated Context-completeness rule requires it. Card 3 by contrast lists `_verify_baseline.py` in Context for its own equivalently-literal snippet reusing `_run_verify_in`, so this is also an internal inconsistency in how the plan applies its own Context convention. **Fix:** Add `plugins/mill/scripts/_bg.py` to Card 6's `Context:` list.

## Verdict

REQUEST_CHANGES
"0.6" dispatch drops an inner PYTHONPATH override, "0.5"/"0.6" disagree on dead-worker handling, and Card 6's Context omits `_bg.py`.
MILL_REVIEW_END
