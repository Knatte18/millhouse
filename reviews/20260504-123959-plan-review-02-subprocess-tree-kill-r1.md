# Review: review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure — 02-subprocess-tree-kill

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 02-subprocess-tree-kill
date: 2026-05-04
```

## Findings

### [BLOCKING] `check=True` silently dropped by Popen rewrite
**Step:** Card 8
**Issue:** Card 8 enumerates every Popen argument and exception path but never addresses `check`. With `subprocess.run`, `check=True` automatically raises `CalledProcessError` on non-zero exit; with Popen it must be done manually. Any caller passing `check=True` would silently receive a `CompletedProcess` instead of an exception.
**Fix:** Add to the requirements: after normal completion, `if check and proc.returncode != 0: raise subprocess.CalledProcessError(proc.returncode, argv, output=stdout, stderr=stderr)` before returning.

### [NIT] Partial output source undefined on timeout re-raise
**Step:** Card 8
**Issue:** Requirements say to re-raise `subprocess.TimeoutExpired(..., output=collected_stdout, stderr=collected_stderr)` but never state these values come from the caught exception's `.output` and `.stderr` attributes.
**Fix:** Name the exception variable (`except subprocess.TimeoutExpired as e`) and note `collected_stdout = e.output or ""`, `collected_stderr = e.stderr or ""` before the terminate/grace block.

### [NIT] `_GRACE_SECONDS` referenced in test but not imported
**Step:** Card 9
**Issue:** Card 9 uses `_GRACE_SECONDS` in the timing bound expression without saying to import it; an implementer will likely hardcode `5`, creating silent drift if the constant changes.
**Fix:** Add `from _subprocess_util import _GRACE_SECONDS` to the test's import block.

## Verdict

REQUEST_CHANGES
One BLOCKING: `check=True` CalledProcessError behaviour is unspecified and would silently regress callers.