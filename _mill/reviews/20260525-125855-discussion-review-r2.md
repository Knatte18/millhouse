# Review: Finish V3 wiki adoption — complete batch 3 port and test sweep

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md (round 2)
date: 2026-05-25
```

## Findings

### [GAP] `merge_tasks` API signature in Technical Context is wrong
**Section:** Technical Context → V3 wiki API table
**Issue:** Table documents `merge_tasks(wiki_path, source_slugs, merged_slug, merged_fields) → None`, but the actual signature is `merge_tasks(wiki_path, *, remove_slugs: list[str], upsert: dict, set_phase: tuple[str, str|None]|None = None) -> dict` (verified at `_client.py:289–295`). Wrong param names, wrong arity, wrong return type.
**Fix:** Replace the table row with the correct keyword-only signature and `dict` return type so card-26 plan code calls the function correctly.

## Verdict

GAPS_FOUND
One GAP: `merge_tasks` API signature documented incorrectly; plan writer would generate broken card-26 code.