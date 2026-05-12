# Discussion: mill-pause: graceful orchestrator pause between operations

```yaml
task: 'mill-pause: graceful orchestrator pause between operations'
slug: mill-pause
status: discussing
parent: main
```

## Problem

When the user invokes `/mill-pause` mid-session, the orchestrator (mill-go or mill-plan) should finish its in-progress async operation — whichever `millpy-bg` poll is currently running — and then stop cleanly without dispatching any new CLI call. The user can then put the machine to sleep safely, knowing the working state is consistent and resume will work correctly in the next session.

There is no existing mechanism to signal "stop after the current operation." Without this skill, the user must interrupt the session forcefully (Ctrl-C or close the terminal), leaving unknown-clean state that may confuse the resume path.

## Scope

**In:**
- A new skill directory `plugins/mill/skills/mill-pause/` containing a single `SKILL.md`.
- The SKILL.md sets LLM behavior for the remainder of the current orchestration turn: finish the in-progress awaited result, output a confirmation message, and stop without dispatching the next CLI call.
- SKILLS.md regenerated to include the new skill (via `/mill-skills-index`).

**Out:**
- No Python scripts — pure SKILL.md, no scripts.
- No changes to `_status.py`, `mill-go`, or any other orchestrator skill.
- No new status.md phase or field — existing phase state (`implementing`/`reviewing`/`fixing`) is already sufficient for mill-go's resume logic.
- No inter-session state: the skill operates entirely within the current turn.
- No `mill-plan` changes — the skill applies to mill-plan by the same LLM-instruction mechanism, without code changes.

## Decisions

### pause-granularity

- Decision: Stop after the next natural breakpoint — the first awaited async result that completes (end of current `millpy-bg` poll). Do not start the next operation.
- Rationale: This matches the task description's examples ("shell command, review round, or implementation batch") — whichever is currently running. It is the least-surprising behavior. The state left at any `millpy-bg` completion is always consistent; mill-go's resume logic reconstructs from phase + batch state.
- Rejected: "Finish the current batch" (option 2) — longer wait, not what the task implies. "Interrupt immediately" (option 3) — risks inconsistent state.

### no-status-write

- Decision: The skill writes nothing to status.md.
- Rationale: Mill-go's resume logic already inspects `implementing`/`reviewing`/`fixing` phase and the per-batch `state` field to determine exactly where to continue. No additional marker is needed. Adding a `paused` phase would require mill-go to handle a new phase, which is out of scope.
- Rejected: Timeline `paused` entry — scope creep. `blocked_reason: paused-by-user` — wrong semantics (blocked is unrecoverable without intervention; pause is intentional).

### resume-trigger

- Decision: In the next session, the user runs `/mill-go`. Mill-go's existing Resume section handles state reconstruction. The word "fortsett" (Norwegian: "continue") is a conversational cue — the skill's stop message instructs the user to run `/mill-go`.
- Rationale: Mill-go already has a complete Resume section. No new command needed.
- Rejected: A dedicated `/mill-resume-pause` command — redundant. Relying on implicit mill-go resume documentation — the user needs the instruction surfaced at pause time.

### confirmation-message

- Decision: When stopping, the LLM outputs: `"Paused after [operation description]. State is consistent. Run /mill-go to resume."` (mill-go context) or the equivalent for mill-plan.
- Rationale: The user's explicit goal is to safely sleep the machine. An explicit confirmation removes ambiguity. No file write needed — the terminal message is sufficient.
- Rejected: Silent stop — not safe for user; they need to know it's clean.

## Technical context

**Mill-go orchestration loop** — `plugins/mill/skills/mill-go/SKILL.md`:
- The loop polls `millpy-bg` subprocesses via `cat <log-path>` until `[mill-bg] EXIT` appears.
- After each poll completes, the orchestrator parses a JSON summary and dispatches the next CLI call (next batch, next review round, fix cycle, etc.).
- The natural pause point is: after parsing the JSON from the completed poll, before calling the next `millpy-bg` invocation.

**Mill-go Resume** — existing Resume section in `mill-go/SKILL.md`:
- On re-entry with phase `implementing`/`reviewing`/`fixing`, mill-go reads the current non-terminal batch entry and re-invokes the appropriate CLI.
- No modification needed — state left by a pause-after-breakpoint is exactly what Resume expects.

**Mill-plan** — `plugins/mill/skills/mill-plan/SKILL.md`:
- Also uses a `millpy-bg` poll loop for review rounds.
- Same pause semantics apply: finish the current review poll, do not start the next round.

**Skill registration** — new skills are added by creating `plugins/mill/skills/<name>/SKILL.md` and regenerating `SKILLS.md` via `/mill-skills-index`. No manifest file required.

**SKILLS.md** — auto-generated from SKILL.md frontmatter by `millpy-skills-index.py`. Regeneration is a post-implementation step.

## Constraints

- Skill must be ≤~20 lines (excluding front-matter and comments) per the task spec.
- No scripts — SKILL.md only.
- Must not change any existing skill, script, or status schema.

## Testing

This skill has no scripts, so no unit tests. Manual verification:

1. Invoke `/mill-pause` mid-way through a running `mill-go` session (while a `millpy-bg` poll is in progress).
2. Confirm the orchestrator finishes the current poll (logs `[mill-bg] EXIT`), outputs the confirmation message, and stops without dispatching the next CLI call.
3. In a new session, run `/mill-go` and confirm resume proceeds from the correct batch/round.
4. Repeat with mill-plan to confirm the same behavior.

No TDD candidates — pure LLM behavioral skill.

## Q&A log

- **Q:** After what unit should mill-pause stop the orchestrator? **A:** [auto-pick] After the next natural breakpoint (first completed `millpy-bg` poll). **Why:** Matches task description examples; existing resume handles any breakpoint state.
- **Q:** Should the skill write anything to status.md when stopping? **A:** [auto-pick] No status.md write. **Why:** Existing phase + batch state is sufficient for mill-go resume.
- **Q:** How does the user resume in the next session? **A:** [auto-pick] Run `/mill-go`. **Why:** Mill-go Resume section already handles reconstruction; "fortsett" maps to this command.
- **Q:** Which orchestrators does mill-pause apply to? **A:** [auto-pick] Mill-go primarily; mill-plan also noted. **Why:** Both share the same poll-and-dispatch loop pattern.
- **Q:** Should the skill include an explicit "safe to sleep" confirmation message? **A:** [auto-pick] Yes — "Paused after [operation]. State is consistent. Run /mill-go to resume." **Why:** User's goal is safe sleep; explicit confirmation removes ambiguity.
