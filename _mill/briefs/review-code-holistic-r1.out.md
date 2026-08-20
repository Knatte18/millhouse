MILL_REVIEW_BEGIN
# Review: git-pr: gh pr create fails on GraphQL 5xx with no REST fallback documented — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-20
```

## Findings

None. The single batch (rest-fallback) fully realizes Card 1's three requirements against `plugins/mill/skills/git-pr/SKILL.md`:

- Step `### 10.5 REST-API fallback` (SKILL.md:219-250) is inserted verbatim between step 10 (create) and step 11 (browser), mirrors the file's existing `1.5` sub-step convention, fires unconditionally on step 10's non-zero exit (`unconditional-rest-attempt`), skips cleanly when `gh` was already flagged unavailable in step 7, and passes exactly `title`/`body`/`head`/`base` — matching step 10's fields with no extras.
- Duplicate-PR detection (SKILL.md:246-250) runs only after both step 10 and step 10.5 have failed, per `duplicate-pr-check-after-both-tiers`, with the `gh pr view` retry then REST GET fallback and the "URL could not be retrieved" terminal message, correctly ordered after both create attempts.
- Step 11's trigger (SKILL.md:254-255) is reworded exactly as specified, including the `gh`-unavailable-in-step-7 early-exit sentence, and the three platform `open`/`start`/`xdg-open` blocks are unchanged.
- Step 12 (SKILL.md:269-274) keeps the default wording byte-identical and adds the two new cause-agnostic report lines (REST-fallback success, duplicate-URL found) exactly as specified, with no cause-naming ("GraphQL") language.
- The REST payload's bare `head="<branch>"` (create, SKILL.md:233) vs. owner-prefixed `head="<owner>:<branch>"` (duplicate-lookup GET, SKILL.md:247) correctly reflects the two endpoints' differing field requirements per `discussion.md`'s `rest-payload-construction`/`duplicate-pr-detection` notes — not an inconsistency.
- `All Files Touched` (00-overview.md) lists only `SKILL.md`; no out-of-plan files present. Steps 1–9 are unaffected by this batch's edits.

## Verdict

APPROVE
Implementation matches the plan and both shared decisions verbatim; no scope, consistency, or design gaps found.
MILL_REVIEW_END
