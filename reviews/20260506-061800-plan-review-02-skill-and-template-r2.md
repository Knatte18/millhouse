# Review: 4 (A) — mill-setup: --from-url for separate wiki repo — 02-skill-and-template

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 02-skill-and-template
date: 2026-05-06
```

## Findings

### [NIT] WikiPushError absent from Error conditions table
**Step:** Card 5 — Update Phase 3 + `## Error conditions` table
**Issue:** Phase 3 prose correctly documents that `WikiPushError` from the pull path (when `clone_or_init` calls `git pull --ff-only` on an existing clone) should be surfaced verbatim, but the `## Error conditions` table additions only include `WikiSetupError` and unknown-CLI-argument rows — leaving `WikiPushError` undocumented in the table.
**Fix:** Add a row: `clone_or_init` raises `WikiPushError` (pull path: ff-only failed, network, credentials, divergence) → halt; instruct user to inspect and fix the wiki clone manually.

### [NIT] Pre-existing slug= omission visible to this batch's implementer
**Step:** Card 5 — Reads `_wiki.py`
**Issue:** Existing Phase 3.1 and Phase 6/6a prose calls `_wiki.write_commit_push(...)` without the required keyword-only `slug=` argument — a `TypeError` at runtime. The batch's implementer will read `_wiki.py` and see the signature; no fix is requested by the card, leaving the gap.
**Fix:** Out of scope for this batch but worth flagging so the implementer adds a follow-up issue rather than silently ignoring it.

## Verdict

APPROVE
Two NITs only; no blocking issues — plan is well-specified and internally consistent.