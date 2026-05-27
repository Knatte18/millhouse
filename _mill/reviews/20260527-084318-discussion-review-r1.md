# Review: mill-merge / fixer teardown recovery

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-27
```

## Findings

### [GAP] Env-strip spec: Python code contradicts Gotchas + Testing
**Section:** `### fixer-implementer-git-env-isolation` / `Gotchas` / `Testing`
**Issue:** The Python snippet in the decision (`if not k.startswith("GIT_") or k in {"GIT_PYTHON_REFRESH"}`) strips ALL `GIT_*` vars except `GIT_PYTHON_REFRESH`, which would also remove `GIT_PAGER`, `GIT_TERMINAL_PROMPT`, etc. The Gotchas section explicitly says "The strip set must not include `GIT_PAGER`, `GIT_TERMINAL_PROMPT`, etc." and the Testing section says "confirm the **seven** listed env vars are stripped" — both imply a named-7-var blocklist, not a prefix-strip. A plan implementer reading the Python code implements the prefix-strip; one reading Gotchas/Testing implements the 7-var blocklist. These produce different env shapes.
**Fix:** Resolve to one approach and align all three sections: either replace the Python snippet with a 7-var set-subtraction (`env = {k: v for k, v in os.environ.items() if k not in STRIP_VARS}`) and drop the GIT_* prefix language, or expand the allowlist in `{"GIT_PYTHON_REFRESH"}` to include `GIT_PAGER`, `GIT_TERMINAL_PROMPT`, and any other benign vars — and update Gotchas and Testing accordingly.

## Verdict

GAPS_FOUND
One unresolved inconsistency in the env-strip spec must be settled before plan writing.