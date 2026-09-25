# Review: Ask the parent session when stuck (parent_thread)

```yaml
verdict: APPROVE
reviewer_model: orchestrator
reviewed_file: _mill/discussion.md
date: 2026-09-25
```

## Findings

### [NIT:consistency] Handoff halts do notify + lock release before halting; escalation slot not stated
**Section:** `escalate-before-recording-block`, `converted-sites` row `go-handoff-gate`
**Issue:** The decision places escalation before `set_blocked` / batch-`blocked` / commit, but the `handoff.md` halts (unfixed nits, done-gate blocked) call `_notify.notify(...)` then `millpy-builder-lock.py release` before halting, and never call `set_blocked`. The discussion keeps the notify calls "only when the halt proceeds" but does not say the escalation goes before the notify + release pair. The lock is per-worktree, so holding it through the wait is harmless, but a plan writer must pick the position.
**Suggested fix:** State that the escalation runs before the `_notify.notify` + `builder-lock release` pair at each handoff site, and that the lock stays held during the wait.

### [NIT:decision] Parent-guided `retry` at `go-batch` re-fires the implementer fresh
**Section:** `converted-sites`, row `go-batch`
**Issue:** `retry` re-fires the implementer fresh for the batch. A fresh re-fire of a `Commit: none` card that performs an external, hard-to-reverse action can repeat that action, because no commit shows it already happened. The self-resolve path in mill-go-base has this hazard already; the discussion does not say whether the parent-guided path inherits whatever guard exists.
**Suggested fix:** Add one line: `retry` at `go-batch` follows the same re-dispatch rules as the existing self-resolve re-fire, including any `Commit: none` idempotency guard.

### [NIT:consistency] `plan-cap` `approve` cannot reuse the `--approve` re-entry guard as-is
**Section:** `converted-sites`, row `plan-cap`
**Issue:** The row says `approve` has "the same effect as the existing `--approve` re-entry". That re-entry (mill-plan Entry step 4) only runs when `phase == "blocked"` and `blocked_reason` starts with `"max-rounds exhausted"`. Because escalation runs before the block is recorded, neither condition holds yet.
**Suggested fix:** Say that the site applies the effect directly (flip `approved: true` in `00-overview.md`, commit, fall into Handoff) rather than re-entering through the `--approve` pre-check.

### [NIT:decision] Case and exactness of the `parent_thread` name
**Section:** `unreachable-parent`, Problem (example `MH:orch`)
**Issue:** `--parent` stores a free-form string, and `SendMessage` needs the exact session name. Session names are now lower-cased at assembly (`mh:orch`), so a spawner passing `MH:orch` may be reported "unreachable" if name lookup is case-sensitive. That is unverified, and the discussion's own example uses the upper-case form.
**Suggested fix:** Note that the spawner must pass the exact live session name (as shown by `ListAgents`), and use lower-case in the examples and tests.

## Verdict

APPROVE
No blockers: scope, decisions and fallbacks are explicit, every referenced code location checked out (`read_parent_branch` at `_status.py:949`, `set_blocked`, mill-go-base `### Blocked` / `### Stuck escalation`, the holistic-review, handoff, mill-plan, mill-start and mill-quick cap/gate sites, and `_cleanliness` already ignoring untracked `_mill/` files); the four NITs are wording clarifications for the plan.
