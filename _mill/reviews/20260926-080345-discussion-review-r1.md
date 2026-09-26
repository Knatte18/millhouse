# Review: Unify ask-parent into ask-thread: ask any named session, default parent

```yaml
verdict: REQUEST_CHANGES
reviewer_model: orchestrator
reviewed_file: _mill/discussion.md
date: 2026-09-26
```

## Findings

### [BLOCKING:design] No correlation between a question batch and its reply
**Section:** Decisions -> Reply protocol; Script and CLI shape
**Issue:** The message and the reply carry no batch id, and the only stale protection is `prepare` unlinking the reply file (`_ask_parent.py:216`), which does not cover a message that arrives during a later wait.
A late reply to a timed-out batch, or a reply split across two messages, is taken as the answer to the current batch, because the protocol treats the first arriving message as the complete reply and `consume` then deletes the file.
Direct mode sends many batches per session, so this is a normal path, and the new message channel makes it more likely than the file-only design.
**Suggested fix:** put a per-`prepare` batch id in the rendered message and require the target to echo it as the first line of its reply; the asker accepts only a reply with the current id and treats a message without it as not a reply.
State in the decision that one reply is one message (or one file), and that later or unmatched messages are ignored.

### [NIT:design] "Would otherwise ask the operator" is not defined
**Section:** Decisions -> Two entry modes, one mechanism (direct mode)
**Issue:** Direct mode reroutes "whenever the session would otherwise ask the operator a question", but skills ask through `AskUserQuestion`, numbered menus and plain prose, and the discussion does not say which of these it covers or how a skill loaded earlier in the session is bound by it.
**Suggested fix:** name the covered mechanisms (all operator questions, including `AskUserQuestion`) and state that the rule is an instruction held in the loaded skill's context, so the plan writer does not invent an enforcement mechanism.

## Verdict

REQUEST_CHANGES
One BLOCKING design gap: replies are not tied to a batch, so late or split replies can be taken for the current answer.
