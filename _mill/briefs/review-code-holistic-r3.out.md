MILL_REVIEW_BEGIN
# Review: Audit mill-start/mill-plan/mill-go for turn reduction — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-19
```

## Findings

### [NIT:consistency] mill-go/mill-go2 line counts off by one
**Location:** `doc/turn-reduction-audit.md:56` (mill-go 29 lines / mill-go2 105 lines claim)
**Issue:** `cat -n` shows `plugins/mill/skills/mill-go/SKILL.md` has 30 lines (last line "value declared above.") and `mill-go2/SKILL.md` has 106 — both one more than cited, consistent with a `wc -l` count on files with no trailing newline undercounting by 1.
**Fix:** Re-derive both counts with a newline-agnostic method (e.g. `cat -n | tail -1`) and correct the confirmation paragraph; no effect on the substantive "adds no mechanical sequences" conclusion, which is independently correct.

### [NIT:consistency] mill-go-base Coverage-check heading tally likely off by one
**Location:** `doc/turn-reduction-audit.md:788` ("19 headings found")
**Issue:** A plain `^## |^### ` enumeration of `mill-go-base/SKILL.md`, minus the trailing meta sections (`## Principles`/`## Board discipline`/`## History`) excluded by this same doc's own convention for `mill-start`/`mill-plan`, yields 20, not 19 — e.g. `## Execute — sequential loop` (line 217) appears to parallel `mill-plan`'s `## Phases`, which *was* tallied in that file's own coverage count. No step content itself was found missing from the classification body.
**Fix:** Re-run the `grep -n '^### \|^## '` self-check for this file specifically and correct the count (or state explicitly why `## Execute — sequential loop` is excluded, if intentional).

## Verdict

APPROVE
Doc-only batch; line ranges, decision citations, and append_phase/commit-m recount methodology verified accurate against source; only two trivial count-off-by-one NITs found.
MILL_REVIEW_END
