I have enough evidence. Writing the review now.

# Review: Replace uv-run-project with direct venv Python in SKILL.md invocations

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-12
```

## Findings

### [GAP] mill-go fallback breaks after conversion
**Section:** Decisions → "Source-tree forms and fallbacks stay as `uv run --project`"
**Issue:** mill-go's fallback sets `$PLUGIN_ROOT` to the source-tree path, then all 22 subsequent Python calls use `$PLUGIN_ROOT`. After conversion, those calls become `"$PLUGIN_ROOT/.venv/Scripts/python.exe"` — which is `source-tree/.venv/Scripts/python.exe`. The fallback block comment "subsequent calls use uv run --project for the fallback path" would then be factually wrong, and the fallback scenario silently breaks if the source-tree venv doesn't exist. No conditional mechanism is described.
**Fix:** Explicitly state whether the 22 mill-go body calls are converted (breaking source-tree-fallback users) or left as `uv run --project` (making mill-go an exception), and update the comment accordingly.

### [GAP] Testing step 1 gives false positive for mill-go
**Section:** Testing → manual verification step 1
**Issue:** Step 1 greps for `uv run --project "${CLAUDE_PLUGIN_ROOT}"` and requires zero matches. mill-go uses `$PLUGIN_ROOT`, not `${CLAUDE_PLUGIN_ROOT}`, so step 1 returns zero even if mill-go's 22 calls were never converted — the check silently passes.
**Fix:** Add a second grep for `uv run --project.*PLUGIN_ROOT` (or equivalent) to verify mill-go's conversions were actually applied.

### [NOTE] mill-setup "unique inline-prefix form" prose becomes misleading
**Section:** mill-setup SKILL.md — "How to invoke the helpers" (lines 57–69, not listed in scope)
**Issue:** The prose describes `PYTHONPATH=... uv run --project "$CLAUDE_PLUGIN_ROOT"` as "mill-setup's unique inline-prefix form" with a "RIGHT" code example. After conversion the code example is mechanically updated, but the "unique" framing is outdated — every skill now uses direct python with an explicit PYTHONPATH prefix.
**Fix:** Note in scope that mill-setup's "How to invoke the helpers" prose section needs updating alongside the invocation lines.

## Verdict

GAPS_FOUND  
mill-go fallback behavior after conversion is unresolved, and the testing step cannot verify mill-go was updated.