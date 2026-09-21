MILL_REVIEW_BEGIN
# Review: mill-go/mill-merge-in orchestration robustness gaps, round 2 — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-21
```

## Findings

### [BLOCKING:scope] Card 6's TaskOutput-unavailable fallback documents 2 of 4 identical probe sites
**Location:** batch 2 / Card 6 (`mill-go-base/SKILL.md`)
**Issue:** The card only adds the clarifying sentence after step 3(b) and 3(c)'s "or the probe call itself errors" clauses, but `mill-go-base/SKILL.md`'s step 5.5 `incomplete` recovery has two more `TaskOutput(...)` probes with the identical "or the probe call itself errors" fallback phrase (verified at lines 419–421, the warm-`SendMessage` liveness probe, and lines 432–435, the cold-resume defensive re-check) that the card's Requirements never mention.
**Fix:** Extend Card 6 to add the same clarifying sentence after both of step 5.5's "or the probe call itself errors" occurrences, or explicitly justify in the card why those two sites are exempt.

### [NIT:consistency] `renumber_after_collision` doesn't shift prose cross-references to card numbers
**Location:** batch 5 / Card 11
**Issue:** `renumber_after_collision`'s regex only rewrites `### Card N:` heading lines; it never touches a card's own prose that names another card by number (e.g. this very plan's own Card 11 Requirements says "the caller (Card 12, in `mill-go-base/SKILL.md`)"). After an auto-renumber, such an in-plan textual reference goes stale even though execution-relevant state (card_ids, `_check_card_numbering`) stays correct.
**Fix:** Either document this as an accepted limitation in Card 11's Requirements/docstring (mirroring Card 1's "known limitation, accepted" pattern), or add a note instructing Card 12's self-resolve caller to grep the renumbered batch for stale "Card N" prose mentions.

### [NIT:consistency] Card 3's split-logic citation omits `_parse_cards`'s fence-awareness
**Location:** batch 1 / Card 3
**Issue:** Card 3 says `parse_card_commit_messages` should split cards "the same way `_plan_validate._parse_cards` does," but `_parse_cards` (verified in `_plan_validate.py`) is fence-aware (toggles on lines starting with ```` ``` ````) while the described inline reimplementation is not — it mirrors the already-shipped, non-fence-aware `parse_commit_none_card_ids` instead. Harmless in practice (no plan card's `Requirements:` fence in this plan contains a `### ` line), but the citation itself misstates `_parse_cards`'s actual behavior.
**Fix:** Reword the citation to say it matches `parse_commit_none_card_ids`'s splitting convention (not `_parse_cards`'s), since that is the function it actually mirrors.

## Verdict

REQUEST_CHANGES
Card 6's fallback-doc coverage gap and two minor citation/consistency nits need addressing.
MILL_REVIEW_END
