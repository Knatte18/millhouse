MILL_REVIEW_BEGIN
# Review: mill-go2: fork-based implementer dispatch — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude, Sonnet-class (harness-reported as "Sonnet 5"; exact point-version not independently verifiable from within the session)
reviewed_file: plan/
date: 2026-08-11
```

## Findings

### [BLOCKING:design] Card 4's override text contradicts its own inference disclaimer
**Location:** batch mill-go2-implementer-override / card 4 (override body text)
**Issue:** The "Dispatch cold" mechanics bullet states as settled fact that step 6.5.1's warm `SendMessage` resume "addresses a live `agentId`, which a fork returns just as a cold agent does" — but the "Known limits" section two paragraphs later calls this exact claim ("a fork returns an `agentId` and delivers a completion `<task-notification>` in the same shapes a cold agent does") "an inference, not a spiked fact" that "the first real run falsifies" and says steps 4 and 6.5 "need fork-specific handling" if wrong. One section relies on the assumption as fact to justify a mechanical claim about the pattern; the other retracts it as unconfirmed in the same file.
**Fix:** Hedge the "Dispatch cold" bullet's sub-clause (e.g. "which a fork is assumed to return just as a cold agent does — see Known limits") so the two sections agree on confirmation status, or drop the sub-clause since "Known limits" already covers it.

### [NIT:consistency] "cited specifically" overclaims mill-plan's paraphrase
**Location:** batch mill-go2-implementer-override / card 3 and card 5 (the `parent's tools` literal-preservation rationale)
**Issue:** Both cards justify keeping the substring `parent's tools` in `mill-go-base/SKILL.md` because `mill-plan/SKILL.md` "cites the tool-inheritance claim specifically." Actual `mill-plan/SKILL.md` line 119 paraphrases as "a fork always inherits the parent's **full tool access**" — it never contains the literal substring `parent's tools`. The assertion itself still passes (it checks `mill-go-base`'s own text, not `mill-plan`'s), so nothing breaks, but the stated cross-file citation is inaccurate.
**Fix:** Reword the rationale to "paraphrased by mill-plan/SKILL.md" rather than "cited specifically," or drop the mill-plan justification for this literal.

## Verdict

REQUEST_CHANGES
Resolve the fork-return-shape self-contradiction in card 4's override text before this batch lands.
MILL_REVIEW_END
