# Review: 29 (A) — mill-merge-in: delegate konflikter og verify-feil til sub-agent — 02-skill-and-config

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 02-skill-and-config
date: 2026-05-07
```

## Findings

### [NIT] Commit body underspecified for Card 4
**Step:** Card 4
**Issue:** Requirements say the commit message "must document why editing only the template is safe" but the `Commit:` field shows only a subject line with no body.
**Fix:** Extend `Commit:` with a body line, e.g. `"CLI defaults to 3; existing hubs unaffected"`, or clarify the subject alone is sufficient.

### [NIT] Redundant `git diff --name-only` inside table cell
**Step:** Card 5 — Step 3 replacement
**Issue:** The pre-table paragraph already says "iterate `git diff --name-only --diff-filter=U`"; the replacement cell body opens with the identical instruction, creating duplication.
**Fix:** Drop the "Enumerate unresolved files via `git diff …`" sentence from the cell body — the pre-table instruction already establishes the unresolved-file list.

## Verdict

APPROVE
Interface verified: flags match Batch 1, sub-agent stages via `git add`, `--checkpoint` feeds MERGE_DIFF only.