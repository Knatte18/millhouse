# Review: 19 (A) — mill-go + scripts infra fixes — 04-docs-pythonpath

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 04-docs-pythonpath
date: 2026-05-06
```

## Findings

### [NIT] New text omits the `uv run python -c` qualifier
**Step:** Card 6
**Issue:** The replacement sentence says to prefix "inline `uv run python -c` calls" but the original bullet also covers `uv run --project ... python -c "..."` invocations generally; the qualifier is clear enough in context, but "inline" is not defined anywhere in CLAUDE.md and could confuse a reader.
**Fix:** Replace "inline `uv run python -c` calls" with `` `uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "..."` calls ``.

### [NIT] mill-setup SKILL.md replacement text loses idempotency framing
**Step:** Card 7
**Issue:** The current sentence explicitly says "only required in mill-setup"; the replacement is accurate but doesn't mention that after a new session opens, the prefix is no longer needed — a reader might infer they always need it.
**Fix:** Append: "Once a new CC session is opened, the global env var is active and the prefix is no longer needed."

## Verdict

APPROVE
Docs-only batch; both corrections are accurate and self-contained.