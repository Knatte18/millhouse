# Discussion: mill-go-base: take the subagent report from the SubagentHandback message

```yaml
task: 'mill-go-base: take the subagent report from the SubagentHandback message'
slug: subagent-handback-report
status: discussing
parent_branch: main
```

## Problem

`mill-go-base/SKILL.md`'s "## Agent-mode dispatch" tells the orchestrator to wait for the `<task-notification>` of a background subagent and read the subagent's final message from its payload.
The harness now delivers the report as a separate `SubagentHandback` message (an agent-message from the `agentId`).
The `<task-notification>`'s `<result>` only says the report "was delivered to you as a message from <agentId>" and carries no report text.
The hand-back message can arrive before the notification.
Observed on every implementer and reviewer dispatch in three runs (GitHub issues #1153, #1155, #1157, all already closed and folded into this task).

Consequences today: step 2 waits on a notification that adds nothing, step 3 classifies on a payload that is empty, and step 4 tells the orchestrator to write "the message captured from the `<task-notification>`" to `<brief_path>.out.md`, which is the wrong source.

## Scope

**In:**

- `plugins/mill/skills/mill-go-base/SKILL.md`, "## Agent-mode dispatch": steps 2, 3(a)/(b)/(c), 4, 5.5 and "Agent-mode properties" — name the hand-back message as the report source, define event order, stop requiring a notification when the hand-back message already carries the report.
- `plugins/mill/skills/mill-go-base/holistic-review.md`: the NIT-fixer paragraph that says "After the dispatch's `<task-notification>` is accepted: capture the notification to `<brief_path>.out.md`".
- `plugins/mill/docs/harness-tool-contracts.md`, "## Agent tool": the contract bullet that says the notification payload carries the final message text.
- `plugins/mill/skills/mill-pause/SKILL.md`: the in-flight Agent-mode bullet that waits for the `<task-notification>`.
- `plugins/mill/skills/mill-start/SKILL.md` and `plugins/mill/skills/mill-plan/SKILL.md`: the one sentence each that describes the notification payload as "carries only a one-line ack".
- Error-message wording in `plugins/mill/scripts/_implementer_common.py` and `plugins/mill/scripts/millpy-merge-in-subagent.py` ("notification message" -> "subagent report message") and the comment beside each `html.unescape` call.
- Comments in `millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py`, `unit_tests/test-review-finalize.py` and `unit_tests/test-implementer-common.py` that contrast reviewer output with the implementer's `<task-notification>` payload being HTML-escaped: reword to "the implementer's report (notification payload or hand-back message)" so they stay true; no logic change.
- A unit test pinning the new SKILL wording only if an existing SKILL-text test pattern fits (see Testing).

**Out:**

- `mill-go2/SKILL.md` has no notification wording of its own; it inherits mill-go-base.
- Monitor-based wait sections (entry-gate waits, orch-wait, orch-review, ask-thread) — a different tool with its own two-notification contract, unaffected.
- The reviewer file-based contract (`.out.md` written by the reviewer, finalize keys on file presence) — unchanged.
- The liveness-probe design (`TaskOutput`, `test -f <output_path>`) — unchanged in mechanism.
- No change to finalize CLI logic or to `html.unescape` behaviour.

## Decisions

### report-source

- Decision: The subagent's report is the text of the `SubagentHandback` message from that `agentId`.
  The `<task-notification>` payload is a fallback report source only, used when no hand-back message was received and the payload holds a non-empty message.
- Rationale: matches observed harness behaviour in three independent runs; keeps older harnesses that still put the text in the notification working.
- Rejected: dropping the notification path entirely — the notification is still the only carrier of `<status>` (failed/stopped/interrupted) and API-error markers, which step 3 depends on.

### event-order-and-what-to-wait-for

- Decision: Define the two events explicitly.
  The hand-back message and the `<task-notification>` are separate events and either may arrive first; the hand-back message normally arrives first.
  The orchestrator does not wait for the notification once a hand-back message carrying the report has arrived and no error signal is pending.
  Concretely: (1) hand-back message arrives with a report -> classify from it, capture it (step 4), run finalize; a notification arriving later for the same `agentId` is ignored unless its `<status>` is non-`completed`, in which case step 3's non-clean-terminal handling applies (probe first).
  (2) Notification arrives first with `<status>` `completed` and a result that only points to a hand-back message -> that is not a report; take no action this turn and wait for the hand-back message (it is already in flight or delivered).
  Bound: if no hand-back message has been seen by the time the notification is processed and the payload is empty or only a pointer, treat the situation as step 3's existing empty/no-structured-report handling instead of waiting indefinitely: implementer -> Clean mid-work stop path (finalize with whatever `.out.md` exists; finalize's commit recount decides); reviewer -> finalize keyed on `output_path` presence; fixer/merge-in -> same finalize path.
  A hand-back message is delivered by the harness before or together with the notification in the observed runs, so this bound is a safety net for older harnesses, not an expected path.
  (3) Notification arrives with a non-`completed` `<status>` or an API-error marker and no hand-back message -> existing step 3 paths unchanged.
- Rationale: the issues' suggested fix is "document the hand-back message as the report source and define the order of the two events".
  Step 3's status-based classification needs a defined behaviour when the message arrives before any notification.
- Rejected: always wait for both events — reintroduces the wasted wait the issues complain about.
  Rejected: key everything on the hand-back message and ignore `<status>` — loses stall/watchdog-kill detection.

### reviewer-dispatch

- Decision: A reviewer's hand-back message is only its one-line ack; arrival of the hand-back message (or a clean notification) is the "agent finished" signal.
  Step 4 stays skipped for reviewers; finalize keys on `output_path` presence as today.
  The `review_elapsed_s` second `date +%s` reading is taken when the first terminal event (hand-back message or notification) is accepted.
- Rationale: keeps the existing reviewer contract, only fixes what event counts as completion.
- Rejected: reading the ack text to branch (already forbidden by the "Deliberately no ack predicate" rule).

### capture-and-unescape

- Decision: Step 4 writes the hand-back message text to `<brief_path>.out.md` verbatim (utf-8), same file naming.
  Keep `html.unescape` at the finalize read sites unchanged.
  Assumption: the hand-back text is not HTML-escaped; `html.unescape` on unescaped text is a no-op except for literal entity-looking text (e.g. a report quoting `&amp;`), which the JSON status parse does not depend on.
  Nobody has confirmed the assumption against the harness; the residual risk (a quoted entity in report prose being altered before it lands in status.md) is accepted, since only the machine-read `status` JSON block drives behaviour.
  The code comments beside `html.unescape` are reworded to say the payload of a notification may be escaped, without claiming the hand-back message is.
- Rationale: smallest safe change; behaviour verified unchanged for the escaped-notification fallback.
- Rejected: removing unescape — would break the fallback path.

### warm-resume-wait

- Decision: Step 5.5's `SendMessage` warm resume gets the same treatment: the resumed agent's answer arrives as a hand-back message; wait for that, with the notification as fallback and status source.
- Rationale: identical mechanism; leaving step 5.5 on "Wait for the resulting `<task-notification>`" would leave the same bug.

## Technical context

- All Agent-mode dispatch semantics live in `plugins/mill/skills/mill-go-base/SKILL.md`, section `## Agent-mode dispatch` (from about line 242) through `**Agent-mode properties:**` (about line 452).
  Read the current worktree copy, not the plugin cache.
- Wording that must change there, by step: step 2's "must then **wait for the completion `<task-notification>`**" paragraph and the "read the subagent's final message from the notification payload" sentence; step 2's reviewer stopwatch sentence "Once the terminal `<task-notification>`... is accepted"; step 3's opening "Classify the notification", 3(a) "If the notification message contains a raw API/infrastructure error marker", 3(b) and 3(c) (their triggers key on `<status>` of the notification — keep, add that a hand-back report with a valid JSON `status` block needs no status tag); the "Clean mid-work stop" sentence "write the notification to the `.out.md` file"; step 4's "message captured from the `<task-notification>`"; step 5.5.1's "Wait for the resulting `<task-notification>`" and "Write the notification's message"; Agent-mode properties bullet 1 ("waits for the `<task-notification>`").
- Mixed sentences that mention notifications for other reasons (liveness-probe "wait for the agent's own next `<task-notification>`") stay: after a probe says "still running", the next terminal event may be either a hand-back message or a notification; reword to "next terminal event (hand-back message or `<task-notification>`)".
- Contract doc: `plugins/mill/docs/harness-tool-contracts.md` line 17 says the notification carries the final message text; change to describe the two events, keeping the `<status>` sentence.
- Line-break convention: one sentence per line in markdown prose (see `mill:prose`).
- The `mill-go-base` SKILL is copied/loaded by `mill-go` and `mill-go2` via `## Dispatch overrides`; do not touch either variant.

## Constraints

- No `sed` anywhere; use Edit/Write.
- Generated markdown metadata uses fenced yaml, not frontmatter.
- Prose rules: no empty intensifiers, don't pin perishable specifics (do not quote issue counts or run branches in the SKILL text; cite the contract doc).
- `print()` output ASCII only if any script message text is touched.
- Verification commands for Python must start with `PYTHONPATH=` (empty).

## Testing

- No behaviour change in Python beyond message wording; existing unit tests must still pass: run `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` (or the repo's documented equivalent).
- `plugins/mill/unit_tests/test-mill-go-variants.py` pins the presence of `## Agent-mode dispatch`; it must keep passing.
- Add or extend a small SKILL-text test only if an existing test already greps SKILL text for required phrases (mirror it); otherwise verify with `grep` that no remaining sentence tells the orchestrator to read the report solely from the `<task-notification>` payload.
- Manual checklist for the plan's verify step: grep `mill-go-base/SKILL.md`, `holistic-review.md`, `mill-pause/SKILL.md` for `notification` and confirm every hit is either the status/fallback role or a Monitor-wait sentence.

## Q&A log

- **Q:** Keep the notification as a fallback report source or remove it? **A:** [auto-pick] Keep as fallback. **Why:** notification is still the sole carrier of `<status>` and API-error markers; removing it breaks step 3.
- **Q:** Wait for the notification after the hand-back message arrives? **A:** [auto-pick] No, proceed on the hand-back message; act on a later notification only if its status is non-completed. **Why:** issues ask to stop waiting for a notification that adds nothing.
- **Q:** Change `html.unescape` at finalize read sites? **A:** [auto-pick] No; reword comments only. **Why:** still needed for the notification fallback and harmless otherwise.
- **Q:** Extend the change to step 5.5 warm-resume and to holistic-review.md / mill-pause? **A:** [auto-pick] Yes. **Why:** same stale wording, same bug.
