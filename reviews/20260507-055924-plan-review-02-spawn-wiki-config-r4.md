# Review: 12 (C) — Restructure hub junction layout — 02-spawn-wiki-config

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 02-spawn-wiki-config
date: 2026-05-07
```

## Findings

### [NIT] Unnecessary pre-creation of target dirs in Card 7 fixture updates
**Step:** Card 7, req 4 and 5
**Issue:** Plan requires pre-creating `wiki_path / "active"` (no-slug test) and `wiki_path / "active" / "my-task"` (with-slug test). Neither is needed: the no-slug case never reaches `target.mkdir` (the token-scope filter `continue`s before that line in `_setup.py`); the with-slug case already calls `target.mkdir(parents=True, exist_ok=True)` inside `create_hub_links`.
**Fix:** Remove the pre-creation lines from both test fixture setups; the tests pass without them.

### [NIT] Mock return value inconsistency between Card 9 req 3 and req 4
**Step:** Card 9, `test-millpy-claim.py` req 3 and 4
**Issue:** Req 3 changes `resolve_hub_path` mock to return `Path("/fake/repo/subdir")`; req 4 sets `write_initial_status.return_value` to `Path("/fake/repo/task/status.md")`. The return value is inconsistent with the hub path after req 3 (should be `/fake/repo/subdir/task/status.md`). No tests assert on this return value content, so it won't cause failures.
**Fix:** Use `Path("/fake/repo/subdir/task/status.md")` as the return value in the standard fixture and `/fake/repo/src/Models/task/status.md` for the subfolder case, to keep the mock self-consistent.

## Verdict

APPROVE — batch is internally consistent and correctly implements all three shared decisions; two NITs are harmless.