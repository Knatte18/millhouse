# Discussion: Explore and adopt Claude Code fork-agents in mill orchestration

```yaml
task: Explore and adopt Claude Code fork-agents in mill orchestration
slug: explore-fork-agent-opportunities
status: discussing
parent: main
```

## Problem

Claude Code has a native "fork" sub-agent (`Agent` tool, `subagent_type: "fork"`) that
continues from the parent's own conversation instead of starting cold. Mill dispatches
every sub-agent cold: it renders a brief file, spawns a fresh `mill:mill-implementer` or
`mill:mill-reviewer`, and relays the result back. The open question was whether forking
could replace or supplement that pattern, and in particular whether it would fix the
orchestrator context-bloat problem observed in mill-go.

The exploration answered both questions, and the answer to the second one is no. Fork
does **not** fix the bloat, because the bloat is not caused by cold-starting agents — it
is caused by mill-go's agent-mode output contract, which forces every sub-agent's entire
final message through the orchestrator's context *twice*. That defect is real,
independently confirmed, and is what this task actually fixes. Fork itself turns out to
fit exactly one place in mill.

**Why now:** a mill-go run was observed burning ~75k/200k tokens of orchestrator context
in a single task. Agent-mode dispatch is the shipped default (`dispatch: agent` in both
the hub config and the plugin template), and the subprocess/psmux paths are dead in
practice, so every mill task pays this cost on every dispatch.

## Scope

**In:**

- **A. Fork adoption at one site:** mill-start's Explore phase gains SKILL.md guidance to
  prefer `Agent(subagent_type: "fork")` for scoped sub-investigations that need the task
  context already in the orchestrator's head.
- **B. Fix the agent-mode output contract** across **all** agent-mode dispatch sites
  (reviewers: discussion / plan / code; implementer; fixer; NIT-fixer; merge-in conflict
  resolver; merge-in verify-fix). The sub-agent writes its own `<brief>.out.md`; the
  orchestrator's `Write` step is deleted; the sub-agent's final message shrinks to a
  one-line ack.
- **C. Grant `mill-reviewer` a `Write` capability** narrowly scoped to `_mill/briefs/`,
  and update the five review templates + the agent definition whose current instructions
  contradict the new contract.
- **D. Remove the now-incorrect `html.unescape()` calls** at the four finalize read sites.
- **E. A durable decision note** recording why fork is rejected for the scripted dispatch
  sites, so this is not re-litigated.

**Out:**

- Forking any scripted dispatch site (implementer / fixer / reviewer / merge-in). Rejected
  on the merits — see Decisions.
- Forking `mill-self-report`. Considered and rejected — see Decisions.
- Merging with the deferred `mill-orchestrator` task (id 0, Thread A/B split). It remains
  a separate, larger proposal. See Technical context for how the two relate.
- Deleting the `subprocess` / `psmux` dispatch paths. They are dead in practice but
  removing them is a separate cleanup.
- Two unrelated bugs found while mapping (file these, don't fix here):
  `millpy-implement.py --stage prepare` never emits `start_sha` even though
  `mill-go/SKILL.md` step 6 says to thread `--start-sha` back into finalize; and
  `_agent_dispatch.resolve_dispatch_mode()` defaults to `"subprocess"` while both shipped
  configs set `agent`, so a hub missing an `llm.claude` block silently falls back to the
  `claude -p` path.

## Decisions

### fork-rejected-for-scripted-dispatch

- **Decision:** Do not use `subagent_type: "fork"` at any of mill's scripted dispatch
  sites (implementer, per-batch/holistic code review, fixer, NIT-fixer, discussion review,
  plan review, merge-in conflict resolver, merge-in verify-fix).
- **Rationale:** Fork's only real advantage over a fresh Agent is that the child inherits
  the parent's context and therefore needs no brief. (Its other advertised property —
  "the child's tool output stays out of the parent" — is **not** a differentiator: an
  ordinary fresh Agent call already behaves that way; only the final message returns.)
  Mill pays the brief-writing cost deliberately, and the brief is load-bearing for three
  things fork destroys, each independently disqualifying:
  1. **Per-role model tiers.** A fork always runs on the parent's model and **ignores a
     `model` override**. Mill assigns models per role: `roles.fixer.model: haiku`,
     `roles.implementer.model: sonnethigh`, `roles.discussion-review…reviewer: opushigh`.
     Forking the fixer silently promotes a Haiku fixer to whatever the orchestrator runs
     on.
  2. **The reviewer's read-only invariant.** `mill-reviewer` is granted only
     `Read, Grep, Glob` — it *cannot* edit source or run commands, by construction. A fork
     inherits the **parent's** tools, so a reviewer forked from mill-go would hold `Edit`,
     `Write`, and `Bash`. The safety property evaporates.
  3. **Crash-safe resume.** The brief is a committed git artifact; `--stage prepare` writes
     it, commits state, and pushes, so a dead session resumes cleanly. A fork's "brief" is
     the parent's in-memory context — not on disk, not reconstructible after a crash.
     Every state-mutating dispatch depends on this.
  A fourth, softer reason applies to reviewers specifically: **review independence.** A
  forked reviewer inherits the author's reasoning, including the rationalizations review
  exists to catch. Discussion review and plan review must not be warm-context.
- **Rejected:** Adding a fourth `fork` dispatch mode. It would trade away model tiers, the
  reviewer tool grant, and resumability for a saving (brief composition) that mill wants
  to keep paying.

### fork-adopted-in-mill-start-explore

- **Decision:** Add guidance (not a mandate) to `mill-start`'s Explore phase: prefer
  `Agent(subagent_type: "fork")` for scoped sub-investigations that need the task context;
  keep fresh `Explore` agents for broad mechanical sweeps where a cold agent is fine and
  cheaper.
- **Rationale:** This is the one place in mill with no brief, no resume requirement, no
  per-role model tier, and no tool restriction to lose — so none of the three
  disqualifiers apply. It is also fork's documented use case ("use a fork when a named
  subagent would need too much background to be useful"). The orchestrator at that point
  holds the task body, the scope digest, and the repo conventions; a fork inherits all of
  it for free and explores better-informed, while its file-reading tool output still stays
  out of the parent's context.
- **Rejected:** Mandating fork for all Explore sub-agents (a broad mechanical sweep does
  not benefit from the inherited context and would pay the parent's prefix on every turn);
  and no change at all (leaves a free quality win on the table).

### no-fork-for-mill-self-report

- **Decision:** Leave `mill-self-report` running in the orchestrator's own context.
- **Rationale:** It was the strongest remaining candidate — its job is literally "scan your
  session memory", so it is the one skill that *cannot* be delegated to a cold agent, and
  fork is the only mechanism that would make it delegatable. But it fires as the **last**
  step of Handoff, so context reclaimed there is nearly worthless, and the parent has to
  block on the fork anyway. Adding a dispatch mechanism for a marginal gain is not worth
  the complexity.
- **Rejected:** Forking it to protect against auto-compact destroying the session memory
  it needs. Real but speculative; revisit if it is ever observed.

### subagent-writes-its-own-out-md

- **Decision:** Every agent-mode sub-agent writes its **own** `<brief>.out.md`. The
  orchestrator's "capture output" `Write` step (`mill-go/SKILL.md:149`) is **deleted**.
  `--stage finalize` continues to read `--agent-output <brief>.out.md` exactly as it does
  today, so the finalize contract is unchanged.
- **Rationale:** This is the actual context-bloat fix. Today `mill-go/SKILL.md:123` makes
  the orchestrator read the sub-agent's **entire** final message out of the
  `<task-notification>`, and `:149` makes it **write that whole thing back out** to
  `.out.md`. A full reviewer output — thousands of lines of findings — therefore lands in
  the Builder's context *twice*, even though `:376` and `:820` explicitly forbid the
  Builder from acting on findings. The subprocess path never did this: the worker wrote
  the review file itself and the Builder grepped one JSON line out of a log. **Agent mode
  regressed relative to subprocess mode**; this restores parity.
- **Rejected:** Reviewers-only scope (implementers and fixers bloat the Builder too, and a
  single uniform contract is simpler than two); and fork (a fork's final message also
  returns as a tool result, so it fixes nothing here).

### one-line-ack-as-final-message

- **Decision:** The sub-agent's final message becomes a single-line ack —
  `WROTE <abs path to .out.md>`. The orchestrator neither needs nor reads anything from
  it; the verdict/status reaches the Builder via `finalize`'s stdout JSON envelope, as it
  already does.
- **Rationale:** Deleting the `Write` step alone only halves the bloat — the notification
  payload is the other half, and it arrives in the Builder's context whether or not the
  Builder does anything with it. Shrinking the final message is what actually reclaims the
  budget.
- **Rejected:** Returning the one-line JSON verdict as the final message (a redundant
  cross-check with `finalize`, and it invites the Builder to start trusting a channel it
  is supposed to ignore); keeping the full output as the final message (halves the fix).

### reviewer-write-grant-scoped-to-briefs

- **Decision:** Add `Write` to `mill-reviewer`'s tool list, with a prompt guardrail
  restricting it to `_mill/briefs/`. The reviewer writes **only** its own `.out.md`.
- **Rationale:** Narrowest grant that makes the new contract work. The reviewer does *not*
  need to write the review file — `finalize` still owns `_mill/reviews/` and renders it
  from `.out.md`. The invariant that actually matters ("the reviewer never touches source
  code or git") survives fully intact. `mill-implementer` already has `Write`, so only
  `mill-reviewer`'s definition changes.
- **Rejected:** Granting `_mill/reviews/` too and making `finalize` a pure parser — more
  moving parts, weaker invariant, no benefit.

### missing-out-md-is-transient

- **Decision:** `finalize` treats a missing or empty `.out.md` as `stuck_type: transient`.
- **Rationale:** With a one-line ack there is no longer an implicit fallback: today, if the
  agent dies mid-way, the notification payload still carries partial output that the
  orchestrator writes to `.out.md`. Under the new contract a dead agent may leave no file
  at all. `transient` feeds mill-go's **existing** one-retry path, so this needs no new
  machinery.
- **Rejected:** Having the orchestrator stat the file before calling `finalize` — duplicates
  logic `finalize` already owns, and adds a step to the hot path.

### remove-html-unescape

- **Decision:** Delete the `html.unescape()` call at all four finalize read sites
  (`millpy-review-code.py:183`, `millpy-review-plan.py:185`,
  `millpy-review-discussion.py:146`, `_implementer_common.py:892`).
- **Rationale:** Those calls exist because the harness HTML-escapes the
  `<task-notification>` payload before delivery (fix #605), and the orchestrator was
  writing that escaped payload to `.out.md`. Once the **agent** writes the file directly,
  the content is never HTML-escaped — and unescaping it anyway would **corrupt** any
  literal `&lt;`, `&gt;`, or `&amp;` appearing inside quoted source code in a finding.
  Leaving these in trades a token bug for a correctness bug.
- **Rejected:** Leaving them as defensive no-ops. They are not no-ops; they are actively
  destructive on legitimate content.

### decision-note-for-fork-rejection

- **Decision:** Record the fork rejection durably in the repo, not only in this
  `discussion.md` (which lives on a task branch and is squash-merged into history where
  nobody will find it).
- **Rationale:** "Why don't we just fork the reviewer?" is a question that will recur. The
  three disqualifiers (model override ignored, tool-grant inheritance, crash-safe resume)
  are non-obvious and worth six lines of prose.
- **Rejected:** Relying on `discussion.md` alone.

## Technical context

**Dispatch inventory.** Mill has 12 sub-agent / background-LLM dispatch sites. The ones in
scope for the output-contract fix are the agent-mode ones:

| Site | Skill / script | Agent | Brief template |
|---|---|---|---|
| Per-batch implementer | `mill-go` §1 → `millpy-implement.py` | `mill:mill-implementer` | `implementer-brief.md` |
| Per-batch code review | `mill-go` §3 → `millpy-review-code.py --batch` | `mill:mill-reviewer` | `review-code-batch.md` |
| Holistic code review | `mill-go` → `millpy-review-code.py` | `mill:mill-reviewer` | `review-code-holistic.md` |
| Per-batch fixer / NIT-fixer | `mill-go` §3 → `millpy-fix.py --scope batch` | `mill:mill-implementer` | `fixer-batch-brief.md` |
| Holistic fixer | `mill-go` → `millpy-fix.py --scope holistic` | `mill:mill-implementer` | `fixer-holistic-brief.md` |
| Discussion review | `mill-start` → `millpy-review-discussion.py` | `mill:mill-reviewer` | `review-discussion.md` |
| Plan review | `mill-plan` → `millpy-review-plan.py --holistic-only` | `mill:mill-reviewer` | `review-plan-{batch,holistic}.md` |
| Merge-in conflicts | `mill-merge-in` → `millpy-merge-in-subagent.py --mode conflicts` | `mill:mill-implementer` | `merge-in-conflict-brief.md` |
| Merge-in verify-fix | `mill-merge-in` → `millpy-merge-in-subagent.py --mode verify-fix` | `mill:mill-implementer` | `merge-in-verify-brief.md` |

**The dispatch protocol** is documented once, in `plugins/mill/skills/mill-go/SKILL.md`
§"## Agent-mode dispatch" (lines ~105–175); every other skill points at it. It is a
three-step prepare → Agent → finalize pattern:

- `--stage prepare` renders the brief via `_agent_dispatch.write_brief()` and emits a JSON
  envelope: `{stage, brief_path, subagent_type, model, session_id, role, scope, round,
  start_sha?, nits_only?}`.
- The orchestrator calls the `Agent` tool with `prompt: "Read this file and follow the
  instructions exactly: <brief_path>"`, then waits for the `<task-notification>`.
- **Step 5 (`:149`) — the defect:** "Write the message captured from the
  `<task-notification>` to `<brief_path>.out.md`."
- `--stage finalize --agent-output <brief>.out.md` parses the file and emits the verdict /
  status JSON that the Builder actually consumes.

**Single choke point for the brief change.** Every brief in mill — implementer, fixer,
merge-in, and all five review prompts — is written through
`_agent_dispatch.write_brief(briefs_dir, role, scope, round_n, prompt_text)`
(`_agent_dispatch.py:96-120`). Appending the output-contract directive there covers all
nine dispatch sites uniformly, instead of editing seven templates by hand. The `.out.md`
path is mechanically derivable from `brief_path` (replace the trailing `.md`), so a small
helper alongside `write_brief` should own that rule — it is currently restated in prose in
three separate places in `mill-go/SKILL.md`. Adding `output_path` to the prepare envelope
is worth considering so the orchestrator never string-munges the path itself.

**Conflicting instructions that must be swept.** Seven files currently tell the sub-agent
that its final message *is* its output, which directly contradicts the new contract:

- `plugins/mill/agents/mill-reviewer.md` — "Your sole output is your final message. Do not
  create intermediate files…" (and its tool list must gain `Write`).
- `plugins/mill/skills/mill-go/SKILL.md` — steps 5 and 6, plus the warm-`SendMessage`
  resume path at `:163` which re-states the capture rule, plus the clean-mid-work-stop path
  at `:135` which says "write the notification to the `.out.md` file as normal".
- `plugins/mill/templates/review-{code-batch,code-holistic,discussion,plan-batch,plan-holistic}.md`.

**Downstream rationale that goes stale.** `mill-start/SKILL.md:152` and
`mill-plan/SKILL.md:111` both pre-emptively load the `mill-receiving-review` skill, and
both justify it with the claim that "under Agent-mode dispatch a reviewer's findings arrive
already embedded in the `<task-notification>` payload the orchestrator must read just to
learn the round's verdict". After this change that is **no longer true** — findings arrive
only in the review file. The pre-emptive load is still correct (the orchestrator must have
the skill active before it reads the review file to present gaps or NITs), but the stated
reason must be rewritten or it will mislead the next reader.

**Relationship to the deferred `mill-orchestrator` task (id 0).** That proposal's core
principle is "Thread B never reads source files" and its own context-budget evidence
section already names this exact defect class (items 1 and 2: `millpy-implement.py` dumping
subprocess output to stdout; `millpy-bg.py` polling tail-output). This task fixes the
agent-mode equivalent of the same disease. The two are **complementary, not overlapping**:
id 0 restructures *who* orchestrates, this task fixes *what the orchestrator is forced to
read*. Landing this makes id 0 cheaper, because a lean agent-mode dispatch is a
precondition for a Sonnet Thread B. Fork is orthogonal to both and is not a mechanism
either one needs.

**Fork availability** (verified, not assumed): requires Claude Code ≥ 2.1.117, on by
default from 2.1.161; this environment runs 2.1.207. `subagent_type: "fork"` is present in
the orchestrator's own `Agent` tool schema. It cannot be dispatched by mill's Python CLIs —
it is a harness-level feature — which is a further structural reason it can only ever
appear in SKILL.md-level guidance, never in a `prepare` envelope.

## Constraints

- No `CONSTRAINTS.md` at the hub root.
- `finalize`'s external contract (`--agent-output <path>`, and the JSON envelopes it emits)
  must not change — mill-go, mill-start, and mill-plan all parse those envelopes.
- The reviewer must remain unable to touch source code or git. The `Write` grant is scoped
  to `_mill/briefs/` for exactly this reason.
- Briefs are committed artifacts (`git add _mill/briefs/` appears throughout mill-go). The
  `.out.md` files land in the same directory and are committed with them, so the audit
  trail is preserved — the sub-agent's full output remains on disk and in git, it simply
  stops passing through the orchestrator's context.
- ASCII-only in `print()` / `_log()` output (Windows cp1252).

## Testing

Unit tests live in `plugins/mill/unit_tests/test-<name>.py`, run via `run-all.py`, with
in-memory/tempfile fixtures and no real git or LLM. That suits every part of this change
except the SKILL.md edits, which are prose and are verified by inspection.

- **`_agent_dispatch` output-path helper — TDD candidate.** The `.md` → `.out.md` rule is
  currently prose restated in three places; make it one function and test it directly,
  including the edge case of a brief path that contains `.md` in a directory component.
- **`write_brief` output-contract footer.** Assert the rendered brief instructs the agent
  to write `<brief>.out.md` and to reply with the one-line ack, for every `role` value used
  by the nine dispatch sites. This is the test that proves the change is uniform rather
  than reviewer-only.
- **`finalize` on a missing / empty `.out.md` — TDD candidate.** Assert `stuck_type:
  transient` for: file absent, file present but zero bytes, file present but whitespace
  only. One test per finalize entry point (`_implementer_common.finalize_from_output` plus
  the three review CLIs), because they have four separate read sites today.
- **`html.unescape` removal — regression test.** A finding whose body quotes source code
  containing a literal `&lt;`, `&gt;`, and `&amp;` must round-trip through `finalize`
  byte-identically into the review file. This test would **fail on today's code**, which is
  the point: it pins the correctness bug the removal fixes.
- **Prepare-envelope shape.** If `output_path` is added, assert it is present and absolute
  for every prepare-emitting CLI.
- **Conflicting-instruction sweep.** A cheap grep-style test asserting that no file under
  `templates/` or `agents/` still says the agent's sole output is its final message. This
  is the kind of thing that silently regresses when someone adds a sixth review template.

Not covered by unit tests, and accepted: the end-to-end behaviour that the orchestrator's
context actually shrinks. Verify that manually on the first real mill-go run after this
lands, by observing that the `<task-notification>` payload is one line.

## Q&A log

- **Q:** Given fork is a poor fit for the scripted dispatch sites, what should this task build? **A:** Fork where it fits, *and* fix the `.out.md` bloat in the same task — it is the motivating problem and fork cannot solve it.
- **Q:** How do we preserve the reviewer's read-only invariant while letting it write? **A:** Grant `Write` guardrailed to `_mill/briefs/` only; the reviewer writes its own `.out.md` and nothing else. `finalize` still owns `_mill/reviews/`.
- **Q:** Fork `mill-self-report`? **A:** No. It fires as the last step of Handoff, so the context it would save is nearly worthless.
- **Q:** How should mill-start's Explore phase use fork? **A:** Guidance, not a mandate — prefer fork for scoped sub-investigations that need the task context; keep cold `Explore` agents for broad mechanical sweeps.
- **Q:** Which dispatch sites get the "sub-agent writes its own `.out.md`" contract? **A:** All of them. Nearly everything writes an `.out.md` today; fix the whole set uniformly.
- **Q:** What is the sub-agent's final message once it writes its own `.out.md`? **A:** A one-line ack (`WROTE <path>`). The Builder needs nothing from it — `finalize` supplies the verdict.
- **Q:** What if the sub-agent dies before writing `.out.md`? **A:** `finalize` reports `stuck_type: transient`, which feeds mill-go's existing one-retry path. No new machinery.
- **Q:** Record the fork rejection durably? **A:** Yes — a short decision note in the repo. The three disqualifiers are non-obvious and the question will recur.
- **Q:** Are the `subprocess` / `psmux` dispatch paths a constraint on this design? **A:** No — they are dead in practice; only agent dispatch is relevant in mill today. (Removing them is a separate cleanup, out of scope here.)
