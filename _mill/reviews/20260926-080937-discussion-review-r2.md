MILL_REVIEW_BEGIN
# Review: Unify ask-parent into ask-thread: ask any named session, default parent

```yaml
duration_s: 295.1
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-09-26
```

## Findings

### [BLOCKING:design] Short-reply path recreates the rejected message-only failure mode
**Section:** Decision: Reply protocol: message first, file as attachment and safety net
**Issue:** The target is told to answer a short reply by message only; the file is reserved for "long" answers. If a `SendMessage` genuinely never reaches a Monitor-blocked asker (stated unverified), a short reply is lost with no file fallback — exactly the scenario the same Decision's Rejected bullet cites against a message-only protocol ("a missed message would always burn the full timeout with no alternative channel"). The Rationale's claim that "the file poll plus timeout keeps both modes correct whichever way that turns out" only holds when the target actually writes the file.
**Fix:** Require the target to always write at least the `ask-id` line (plus short content) to the reply file regardless of perceived answer length, with the message acting as an optional wake-up hint rather than the sole channel for short replies.

### [NIT:consistency] `AskUserQuestion` listed as an intercepted channel is dead per repo convention
**Section:** Decision: Two entry modes, one mechanism
**Issue:** The direct-mode routing rule names `AskUserQuestion` as one of three channels it covers, but `conversation/SKILL.md` (always active) already forbids the orchestrator from calling `AskUserQuestion` in favor of numbered text lists — so this branch cannot fire under current convention.
**Fix:** Drop `AskUserQuestion` from the enumeration, or note explicitly it's listed defensively despite being currently unreachable.

### [NIT:design] Numbering scheme across multiple 5-question batches unspecified
**Section:** Decision: Two entry modes, one mechanism ("batches of at most 5")
**Issue:** Each question is numbered, but the discussion doesn't say whether numbering restarts at 1 for each new batch of a multi-batch session or continues globally across batches.
**Fix:** State the numbering scheme.

### [NIT:consistency] Several `### Decision:` blocks omit a Rejected alternative
**Section:** Decisions: Target name used verbatim, Spawn does not switch direct mode on, Target context growth, Delivery tests
**Issue:** These four decisions carry Rationale but no Rejected bullet, though prose in the Rationale gestures at the alternative (e.g. case-folding the target name).
**Fix:** Add a one-line Rejected alternative to each, or fold trivial ones into the Scope Out list without a Decision heading.

## Verdict

REQUEST_CHANGES
One BLOCKING: short-reply delivery path lacks the file safety net the design's own rationale claims it has.
MILL_REVIEW_END
