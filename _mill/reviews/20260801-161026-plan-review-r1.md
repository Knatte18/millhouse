MILL_REVIEW_BEGIN
# Review: Non-interactive pipeline: only mill-start's interview may prompt the operator — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (self-assessed; the harness names this session "Sonnet 5" per its own metadata — stated for transparency, not corrected)
reviewed_file: plan/
date: 2026-08-01
```

## Findings

### [BLOCKING] Card 13 leaves a dangling "Phase 4 (Cleanup)" reference in mill-autofix
**Location:** batch 6 (`06-cleanup-dead-autonomous-mode.md`), Card 13
**Issue:** `mill-autofix/SKILL.md`'s `### Step 0: Branch guard + killswitch check` (inside `## Phase 3: Per-bug loop`) contains: "If `STOP`: halt the loop immediately. Do **not** delete the file. Proceed to Phase 4 (Cleanup) then Phase 5 (Report)." Card 13 deletes `## Phase 4: Cleanup — restore autonomous mode` in full and fixes the Phase 3 intro sentence's "proceed to Phase 4" reference, plus the Principles bullet's "(Phase 4)" parenthetical — but this Step 0 killswitch sentence is a third, distinct occurrence of "Phase 4" that no card's Requirements quotes or replaces. After this batch lands, the killswitch path still instructs the agent to "proceed to Phase 4 (Cleanup)," a heading that no longer exists.
**Fix:** Add a fourth edit to Card 13 (or a new card) replacing this sentence, e.g. "Proceed to Phase 5 (Report)."

### [BLOCKING] Card 7's holistic-scope glob description doesn't actually mirror `_find_final_code_review`
**Location:** batch 4 (`04-mill-go-handoff-gates.md`), Card 7
**Issue:** The card's replacement text tells the implementer to glob for `*-code-review-r*.md` "with no batch-name segment (mirrors `_nit_gate._find_final_code_review`'s own matching)" to identify holistic review files. The actual function uses anchored regex (`RE_SIMPLE` requires nothing between `review-` and `r\d+` before `.md`), which correctly excludes per-batch files. The glob string `*-code-review-r*.md`, however, is an unanchored substring match: a per-batch file whose batch name begins with "r" (e.g. a batch named `retry-fix` -> `...-code-review-retry-fix-r1.md`) contains the literal substring `-code-review-r` and would be wrongly picked up as a holistic-scope candidate. This contradicts the claimed mirroring and could select the wrong review file (and thus the wrong `--round`/dispatch args) when self-resolving the nit gate for a batch with such a name.
**Fix:** Describe the holistic match precisely (e.g. "the timestamp is immediately followed by `-code-review-r<digits>.md` with nothing else in between") rather than a glob string that a batch-name collision can defeat.

## Verdict

REQUEST_CHANGES
Card 13 leaves a stale Phase-4 reference; Card 7's holistic glob can mis-match a per-batch review file.
MILL_REVIEW_END
