# Review: review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure — 02-subprocess-tree-kill

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 02-subprocess-tree-kill
date: 2026-05-04
```

## Findings

### [BLOCKING] `check` parameter silently dropped in Popen rewrite
**Step:** Card 8
**Issue:** Requirements enumerate every Popen argument and both completion paths but never mention handling `check=True` — the implementation would silently return `CompletedProcess` on non-zero exit instead of raising `CalledProcessError`, changing documented behaviour.
**Fix:** Add to the normal-completion requirements: "After constructing `CompletedProcess`, if `check and proc.returncode != 0`, raise `subprocess.CalledProcessError(proc.returncode, argv, stdout, stderr)` before returning."

### [NIT] `collected_stdout`/`collected_stderr` origin unspecified in re-raise
**Step:** Card 8
**Issue:** The re-raise uses `output=collected_stdout, stderr=collected_stderr` but requirements never say where these come from; `TimeoutExpired.stdout`/`.stderr` from `communicate()` are `None` or bytes (not `str`) even with `text=True`, so the re-raised exception's output type silently differs from the normal-path `CompletedProcess.stdout`.
**Fix:** State explicitly: "assign `collected_stdout = exc.stdout` and `collected_stderr = exc.stderr` from the caught exception (may be `None` or bytes — preserve as-is to match `subprocess.run` behaviour on timeout)."

## Verdict

REQUEST_CHANGES  
Card 8 requirements omit `check=True` → `CalledProcessError` handling; fix before implementing.