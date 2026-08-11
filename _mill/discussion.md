# Discussion: mill-go2: fork-based fixer (NIT-fix) dispatch

```yaml
task: 'mill-go2: fork-based fixer (NIT-fix) dispatch'
slug: mill-go2-fork-fixer
status: discussing
parent: main
```

## Problem

`mill-go2` is an opt-in experimental variant of the `mill-go` orchestrator, created by the
`mill-go2-scaffold` task so that fork-dispatch experiments never destabilise the production
orchestrator.
The scaffold extracted every piece of `mill-go`'s machinery into a shared `mill-go-base` skill and
reduced both `mill-go` and `mill-go2` to thin variant files that bind a `VARIANT_LABEL` and declare
two override points.
Both variants currently declare `(none)` for both override points, so `/mill-go2` is behaviourally
identical to `/mill-go` today.

This task is the first of two experiments layered on that scaffold: swap `mill-go2`'s **fixer**
dispatch from a cold `Agent(subagent_type: "mill:mill-implementer")` call to
`Agent(subagent_type: "fork")`.
The sibling task `mill-go2-fork-implementer` does the same for the implementer role;
the two are independent and both depend only on `mill-go2-scaffold`.
The motivating hypothesis, drawn from Webster (Loomyard's implementer, which forks per execution
batch), is that a forked fixer inherits the driver's already-warm understanding of the task and so
needs less brief-reading and fewer wrong turns than a cold session that starts from nothing.

**Why now:** `mill-go2-scaffold` has landed (commit `6cda129c`), and the override points it built
exist and are exercised by a passing contract test.
There is nothing further to wait for.

## Scope

**In:**

- `plugins/mill/skills/mill-go2/SKILL.md` — fill the currently-empty `## Dispatch overrides`
  section with a fixer-role override that dispatches `Agent(subagent_type: "fork")`, plus the
  cold-fallback, fallback-recording, and experiment-risk text described under Decisions.
- `plugins/mill/unit_tests/test-mill-go-variants.py` — add one contract check locking the fork
  override's presence in `mill-go2` and its absence in `mill-go`.
- `plugins/mill/scripts/_status.py` — add `append_fork_fallback_log`, an append-only audit-log
  helper mirroring the existing `append_inferred_success_log`.
  Required by Decision `fallback-record-must-not-overwrite-phase`;
  this is the task's only production-code change.
- `plugins/mill/unit_tests/` — coverage for that helper (see `Testing` for whether it extends an
  existing file or adds one).

**Out:**

- `plugins/mill/skills/mill-go-base/SKILL.md` — **no edits at all**, including its `Why not fork?`
  section.
  See Decision `no-base-edits`.
- `plugins/mill/skills/mill-go/SKILL.md` — stays `(none)` for both override points.
  The production orchestrator is unchanged by this task, which is the entire reason the variant
  split exists.
- Every Python script **except** `_status.py`'s one new helper.
  No change to `millpy-fix.py`, `_implementer_common.py`, `_agent_dispatch.py`, `_notify.py`, or any
  other helper, and no change to any existing function in `_status.py` — `append_fork_fallback_log`
  is purely additive and no existing caller is touched.
- The implementer, reviewer, and merge-in roles.
  Reviewer is explicitly and permanently out of scope for forking (see Decision
  `reviewer-stays-cold`);
  implementer belongs to the sibling task.
- `plugins/mill/templates/mill-config.yaml` — no new config key.
  See Decision `driver-model-guardrail-is-documentation-only`.
- The `subprocess` and `psmux` dispatch modes.
  Override point A is consulted only inside the base's Agent-mode dispatch pattern, so a
  `subprocess`/`psmux` run of `/mill-go2` is unaffected and keeps today's `millpy-bg` behaviour.
  The hub config is `dispatch: agent` (`mill-config.yaml:10`), so the Agent-mode branch is the one
  that matters in practice.
- Driver-session context growth over a long task, and any periodic driver re-fork or reset to
  bound it.
  See Decision `driver-context-growth-not-mitigated-here`.

## Decisions

### fork-all-four-fixer-dispatch-sites

- Decision: the override applies to **every** fixer dispatch, not only the NIT-only passes.
  `mill-go-base` dispatches the fixer at four sites: per-batch NIT-only (`SKILL.md:791`), per-batch
  `REQUEST_CHANGES` (`:813`), holistic NIT-only (`:1239`), and holistic `REQUEST_CHANGES` (`:1261`).
  All four go through the same shared Agent-mode dispatch pattern and all four therefore hit
  Override point A.
- Rationale: Override point A is **role-scoped, not site-scoped** — the base says "consult your
  variant's `## Dispatch overrides` for this role" (`mill-go-base/SKILL.md:238-242`).
  A site-selective override would have to re-state which of the four call sites it covers, which
  costs bytes in a byte-capped file (see Constraint `variant-file-byte-cap`) and creates a drift
  surface if the base ever adds or moves a fixer dispatch site.
- Rejected: NIT-only passes alone (matches the task title literally, but splits one role across two
  dispatch shapes for no mechanical benefit);
  batch scope only (narrower blast radius, same drift problem).

### fork-call-shape

- Decision: the override replaces the default `Agent()` call with
  `Agent(subagent_type: "fork", prompt: "Read this file and follow the instructions exactly:
  <brief_path>")`.
  The prompt string is **character-identical** to the default path's.
  `model` and the envelope's `subagent_type` are **omitted deliberately**, not passed and ignored.
  `isolation` is not passed.
- Rationale: the on-disk brief remains the fixer's contract;
  the inherited context is a bonus on top of it, never a substitute, so the fixer must still read
  the brief.
  A fork always runs on the parent's model and ignores a `model` override, so passing the
  envelope's `model: haiku` would be misleading text that reads as if it takes effect.
  `isolation: "worktree"` would be actively wrong — the fixer must commit to the task branch in the
  real worktree.
- Rejected: passing `model` anyway for audit visibility (misleading);
  a shortened prompt that leans on inherited context (breaks the brief-is-the-contract invariant
  that finalize's `scope_violations` gate depends on).

### role-identification-is-structural

- Decision: no role-detection logic is written at all.
  The override applies because of **where it sits** — Override point A states that "the role for the
  current dispatch is the one named by the calling subsection" (`mill-go-base/SKILL.md:238-242`),
  so a `### fixer` subsection is consulted at fixer dispatches and nowhere else.
  Decision `per-role-subsections-for-sibling-disjointness` already produces exactly that structure,
  which makes this free.
- Rationale: an earlier draft made this a decision about keying on the prepare envelope's
  `role: "fix"` field, weighing that against the CLI name and `subagent_type`.
  All three were answers to a question the base does not ask.
  Writing envelope-inspection prose into the override would add bytes against the 4096-byte cap and
  imply a discrimination step that Override point A already performs structurally.
- On the envelope field: `emit_prepare` does set `"role": role` unconditionally
  (`_implementer_common.py:1362`) and `millpy-fix.py` does pass the literal `"fix"`
  (`millpy-fix.py:653-666`), so `role: "fix"` is present in every fixer envelope and is useful when
  reading a transcript after the fact.
  Nothing in the override depends on it, and the override must not be written as though it does.
- Rejected: keying on the envelope `role` field, the CLI name, or `subagent_type` — the first two
  are redundant with structural placement, and the third does not discriminate at all (fixer and
  implementer both resolve to `mill:mill-implementer`, see Technical context).

### cold-fallback-on-first-terminal-failure

- Decision: the first time a forked fixer dispatch reaches a terminal failure classification under
  the base's step 4, re-dispatch **once** using the default (non-forked) `Agent()` call — the
  envelope's own `subagent_type` and `model`, and the **same `brief_path`** — rather than a second
  fork.
  "Terminal failure classification" means exactly what the base already defines: a raw
  API/infrastructure error per step 4(a), or a non-clean terminal `<task-notification>` whose
  `TaskOutput(task_id: <agentId>, block: false)` liveness probe per step 4(c) reports the agent is
  no longer running.
  No new failure detection is introduced.
- Rationale: the fork gets one shot and the retry uses the proven path, so a fork-specific failure
  mode cannot cost the task its whole fix round.
  No new machinery is required: the brief already exists on disk because the prepare stage wrote it
  before the dispatch shape was ever chosen (`_agent_dispatch.write_brief`, called by
  `emit_prepare`), and step 4(c) already probes fixer dispatches specifically.
- Rejected: fork-again-then-cold (Webster's two-tier warm-re-fork-then-cold-strand recovery — but a
  warm re-fork of a *dead* fork buys nothing here, since the fixer has no partial-progress state
  worth preserving the way an implementer's committed cards do);
  immediate escalation with no cold attempt (drops the fallback the task explicitly requires);
  adding a fork-path-specific liveness probe (duplicates step 4(c)).

### override-applies-to-first-attempt-only

- Decision: the `### fixer` override text must state its own applicability condition explicitly:
  it governs the **first** fixer dispatch for a given scope and round, and does **not** govern
  step 4's automatic re-dispatch.
  The Builder tracks a local per-scope-per-round flag (e.g. `fork_attempted`), sets it when it
  issues the forked dispatch, and uses the default `Agent()` call — the envelope's own
  `subagent_type` and `model` — whenever that flag is already set.
  The flag resets at the start of each new scope/round dispatch, so a later fix round in the same
  task forks again rather than staying cold for the remainder of the run.
- Rationale: the cold retry is not a fresh trip through the dispatch pattern's steps 1-3.
  Step 4(a) says "re-dispatch once immediately using a fresh brief and session"
  (`mill-go-base/SKILL.md:271`) and step 4(c) routes to "the existing one-retry transient
  classification from (a) and re-dispatch exactly as today" (`:322-323`) — both are actions inside
  step 4, and neither says to re-enter step 3.
  Override point A lives in step 3 and is **role-scoped only**: its text resolves which role is
  dispatching, and carries no attempt-number signal whatsoever.
  So nothing structural distinguishes "first dispatch" from "step 4's retry", and an override that
  merely says "fork the fixer" would fork again on the retry — silently converting the cold
  fallback into an infinite-fork loop bounded only by the retry budget, which is the exact opposite
  of Decision `cold-fallback-on-first-terminal-failure`.
  The distinction has to be carried by the override's own prose because there is nowhere else to put
  it without editing the base.
- Consequence for the plan: this is the one place the override text must be written as a
  conditional rather than a flat substitution.
  Budget bytes for it (see Constraint `variant-file-byte-cap`);
  it is not optional prose.
- Rejected: relying on step 4 to re-enter step 3 and re-consult (undefined in the base — and if it
  did re-consult, it would fork again, which is wrong);
  keying the retry's dispatch shape on an envelope field (no field carries attempt number — the
  prepare envelope is rebuilt identically for a retry);
  editing the base to add an attempt-aware signal to Override point A (conflicts with
  `no-base-edits`, and would change shared machinery for one variant's benefit).

### fallback-consumes-existing-retry-budget

- Decision: the cold fallback **consumes** the base's existing one-retry-transient budget.
  Fork attempt plus cold retry equals two attempts total;
  a second consecutive terminal failure escalates via `### Stuck escalation` exactly as today.
- Rationale: mill-go2 then tolerates precisely as much failure as mill-go before escalating, so any
  observed difference in outcomes is attributable to the fork itself rather than to a longer retry
  budget.
  That comparability is the point of running the variant.
- Rejected: an additional attempt on top of the existing budget (more resilient, but muddies the
  experiment's comparison against mill-go and delays escalation).

### record-the-fallback

- Decision: immediately before the cold retry, emit a notification and append a dedicated audit-log
  row, then commit the row:
  `_notify.notify("<VARIANT_LABEL>.fork-fallback", f"fixer {scope} r{N}", slug=slug)` and
  `_status.append_fork_fallback_log(status_path, scope, N, _timestamp.now_utc_iso())`,
  followed by
  `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: fork-fallback for fixer {scope} r{N}"`.
  `{scope}` is the batch name for batch scope and the literal `holistic` for holistic scope,
  matching the `scope_label` the fix CLI already computes (`millpy-fix.py:655`).
  `append_fork_fallback_log` is a **new helper this task adds** to `plugins/mill/scripts/_status.py`
  (see Decision `fallback-record-must-not-overwrite-phase` for why, and `Testing` for its coverage).
- Rationale: how often a forked fixer dies is the single most valuable measurement this experiment
  produces, and an unrecorded fallback is invisible once the session ends.
- Rejected: `_notify` only (lost once the session ends);
  nothing at all (makes the experiment unmeasurable);
  folding the row into the fixer's own next commit (the fixer commits from a separate session and
  may never reach a commit if the cold retry also fails).

### fallback-record-must-not-overwrite-phase

- Decision: the fallback record must **not** go through `_status.append_phase`.
  It goes through a new append-only audit-log helper,
  `_status.append_fork_fallback_log(status_path, scope, round, timestamp)`, which creates and
  appends to a `## Fork-fallback log` section and never touches the top-level `phase:` field.
- Rationale: `append_phase` overwrites `phase:` in the top yaml block (`_status.py:425-432`), and
  `phase:` drives the entry gate's phase table (`mill-go-base/SKILL.md:114-121`) plus the
  mid-execution widening predicate (`:127-132`).
  That predicate matches an exact set
  `{implementing, reviewing, fixing, self-resolved-verify-logic, holistic-approved}` and the regexes
  `^approved-.*$`, `^reviewing-.*-r\d+$`, `^fixing-.*-r\d+$`, `^holistic-reviewing$`.
  A literal like `fork-fallback-fix-<scope>-r<N>` matches none of them, so a session crash between
  the fallback commit and the cold retry's own next phase write would resume onto the table's
  `any other -> surface + halt` row (`:121`) — the task would halt on a phase name nothing
  recognises.
  Registering the literal in the widening table would fix that but requires editing
  `mill-go-base/SKILL.md`, which Decision `no-base-edits` forbids and which would put a
  variant-specific string in the shared base.
  An append-only audit section sidesteps the conflict entirely: `phase:` keeps whatever value the
  in-flight fix round already set (`fixing-{scope}-r{N}`, which the widening regex
  `^fixing-.*-r\d+$` already matches and routes to `## Resume`), so crash-resume behaves exactly as
  it does for a non-forked fixer.
- Precedent: two append-only audit-log helpers already exist and are the direct model for this one —
  `_status.append_recovery_log` (`:1067`) and `_status.append_inferred_success_log` (`:1175`).
  Both lazily create their own `## ... log` section on first call, append one row per call inside
  the existing fenced block, and never rewrite prior rows or touch `phase:`.
  The new helper mirrors `append_inferred_success_log` line for line, differing only in heading
  constant and row format.
- Correction to the record: an earlier draft of Decision `record-the-fallback` justified the
  `append_phase` call by citing `self-resolved-verify-logic` and `self-resolved-terminal-dirt` as
  precedent.
  That was wrong on both counts.
  `self-resolved-verify-logic` **is** registered in the widening exact-set
  (`mill-go-base/SKILL.md:130`), so it is precedent for registering a literal, not for skipping
  registration;
  `self-resolved-terminal-dirt` is written during Handoff, where there is no subsequent resume
  exposure, so it is not analogous to a mid-fix write at all.
- Rejected: registering `fork-fallback-fix-<scope>-r<N>` in the base's widening table (conflicts
  with `no-base-edits`, and leaks a variant-specific literal into shared machinery);
  reusing the existing `fixing-{scope}-r{N}` literal (resume-safe, but records nothing — it is the
  string the fix CLI already writes, so the fallback would leave no trace);
  `_status.update_field` with a top-level key (does not touch `phase:`, but overwrites rather than
  appends, so a second fallback in the same task would clobber the first).

### broader-tool-grant-accepted-as-documented-risk

- Decision: accept that a fork inherits the driver's tool grant, and record it as an explicit
  experiment risk in the variant file.
  Do not add a scope-tightening instruction to the fork's prompt.
- Rationale: the task proposal's stated premise — that the fixer's tool grant is narrower than the
  implementer's — is **factually wrong**, and the plan must not be written against it.
  `emit_prepare` hardcodes `_agent_dispatch.SUBAGENT_IMPLEMENTER`
  (`_implementer_common.py:1357-1359`), so today's cold fixer already dispatches as
  `mill:mill-implementer` with the full `Read, Edit, Write, Bash, Grep, Glob, Skill` grant
  (`plugins/mill/agents/mill-implementer.md`).
  Forking loses nothing relative to today's fixer.
  The real delta is the opposite direction and worth stating: a fork inherits the **orchestrator's**
  grant, which is strictly broader (`Agent`, `TaskOutput`, `SendMessage`, `WebFetch`, `Workflow`,
  and so on).
  Fixer scope discipline has never come from the tool grant — it comes from the brief and from
  finalize's `scope_violations` gate (`mill-go-base/SKILL.md:1375`), both of which are unchanged.
- Rejected: adding a scope-tightening prompt line (belt-and-braces, but costs bytes against the
  4096-byte cap for a constraint the brief already imposes);
  treating it as blocking until a grant-narrowing mechanism exists (kills the experiment over a
  premise that does not hold).

### driver-model-guardrail-is-documentation-only

- Decision: state in `mill-go2`'s override text that forking the fixer forfeits
  `roles.fixer.model: haiku` and that `/mill-go2` should therefore be driven from a solid model
  tier.
  Add no config key and no enforcement.
- Rationale: the driver model is the operator's own Claude Code session model.
  Nothing inside mill can read it, so any "enforcement" would be a check that cannot be evaluated.
  The user accepted this cost explicitly when scoping the task.
- Rejected: a `roles.fixer.fork: true` config key (an extra switch on top of an already opt-in
  variant, gating behaviour that the variant file itself already declares);
  saying nothing (the cost then lives only in the wiki proposal, invisible to anyone reading the
  skill).

### driver-context-growth-not-mitigated-here

- Decision: this task adds no mitigation for unbounded driver-session context growth across a long
  task.
  The question is scoped out deliberately, not overlooked.
- Provenance: this is the third of the three open questions carried by the sibling task's proposal
  (`mill-go2-fork-implementer`), which this task's own wiki body incorporates by reference for the
  shared Webster research.
  This task's own body lists only two open questions, both of which are answered above —
  the fallback-contract shape by `cold-fallback-on-first-terminal-failure` plus
  `Technical context`'s "What is unchanged by forking", and the model/config-key question by
  `driver-model-guardrail-is-documentation-only`.
  It is recorded here so a cold reader can see it was considered.
- Rationale: context growth is a property of the **driver session**, not of the fixer dispatch.
  Any mitigation — periodic driver re-fork, a reset checkpoint between batches — would be
  variant-wide machinery affecting every role, which collides with Decision `no-base-edits` and
  with the 4096-byte variant cap.
  It is also the wrong place to look first: the fixer is the cheapest fork in the system (NIT-fix
  passes are narrow and there are few per task) against one implementer fork per batch, so if
  driver bloat becomes real it will surface on the sibling task's implementer path long before it
  surfaces here.
  Finally, it is an observational question with no mechanical answer available yet — there is
  nothing to build until a real `/mill-go2` run demonstrates the problem and shows its shape.
- Rejected: adding a driver re-fork or reset mechanism in this task (variant-wide machinery,
  requires base edits, and speculative ahead of any evidence);
  leaving the question unmentioned (a cold reader cannot distinguish a considered omission from a
  missed one, which is exactly the gap this entry closes).

### no-base-edits

- Decision: `mill-go-base/SKILL.md` is not edited by this task, including its `Why not fork?`
  section (`:423-430`).
- Rationale: Override point A already consults the variant's section at every Agent-mode dispatch,
  so the override is purely additive in `mill-go2/SKILL.md` and the base needs no new logic.
  Adding a "mill-go2 overrides this" sentence to `Why not fork?` would make the base reference a
  specific variant by name, which the variant contract deliberately avoids — the whole
  parameterization lock in `test-mill-go-variants.py:199-223` exists to keep variant-specific
  strings out of the base.
- Rejected: a clarifying sentence in `Why not fork?` (violates the parameterization intent);
  broader base edits formalizing a fork-dispatch path (turns an additive experiment into
  shared-machinery surgery, which is exactly what the variant split was built to avoid).
- Note for the reader: `Why not fork?`'s three disqualifiers remain accurate as written for the
  base.
  For the fixer specifically, (1) model loss is the accepted cost;
  (2) tool inheritance is the documented risk above;
  (3) "no on-disk brief" does not apply — the prepare stage writes a brief regardless of dispatch
  shape, and the fixer has no `--resume-incomplete` path to lose (that recovery is implementer-only,
  `mill-go-base/SKILL.md:353`).

### reviewer-stays-cold

- Decision: the reviewer role is never forked, in this task or the sibling.
- Rationale: `mill:mill-reviewer` holds a read-only grant (`Read, Grep, Glob, Write`).
  Forking it would hand it `Edit` and `Bash` from the driver and destroy the read-only guarantee
  that makes review findings trustworthy.
- Rejected: nothing — this is inherited from the task proposal and is not up for revisiting here.

### per-role-subsections-for-sibling-disjointness

- Decision: structure `## Dispatch overrides` as one `### <role>` subsection per role from the
  outset, so this task writes `### fixer` and the sibling task writes `### implementer` as a
  disjoint block.
- Rationale: both tasks branch from the same `(none)` placeholder and edit the same section of the
  same file, so whichever lands second hits a conflict.
  Disjoint per-role subsections reduce that to a trivial textual resolution and keep the section
  readable at two entries.
- Rejected: ignoring the conflict and resolving it at merge time (works, but the conflict is
  gratuitous);
  a shared prep commit defining the empty per-role skeleton first (cleanest, but adds a
  coordination step across two independent worktrees for a conflict this decision already reduces
  to trivial).

### test-extends-the-existing-variant-contract

- Decision: add one check function to `plugins/mill/unit_tests/test-mill-go-variants.py` rather
  than creating a new test file.
- Rationale: the fork override is part of the variant contract, and that file already owns every
  assertion about these two SKILL.md files (byte cap, machinery literals, required headers,
  parameterization lock).
  A second file asserting on the same two files would drift.
- Rejected: a new `test-mill-go2-fork.py` (cleaner separation, guaranteed drift);
  no new test (the existing checks would pass on an override that says nothing useful, so the
  fork behaviour itself would be unlocked).

## Technical context

**The variant/base split.**
`plugins/mill/skills/mill-go2/SKILL.md` is a 28-line, 804-byte thin variant.
It declares three sections — `## Variant binding` (binding `VARIANT_LABEL: mill-go2`),
`## Driver preamble` (`(none)`), and `## Dispatch overrides` (`(none)`) — then loads
`mill:mill-go-base`.
`plugins/mill/skills/mill-go/SKILL.md` is the same shape with `VARIANT_LABEL: mill-go`.
All 1481 lines of orchestrator machinery live in `plugins/mill/skills/mill-go-base/SKILL.md`.

**Override point A** (`mill-go-base/SKILL.md:238-242`) sits inside step 3 of the shared Agent-mode
dispatch pattern, immediately before the default `Agent()` invocation:

> consult your variant's `## Dispatch overrides` for this role;
> if it declares one, follow it instead of the default `Agent()` call below.
> The role for the current dispatch is the one named by the calling subsection (implementer, fixer,
> reviewer, or merge-in).

Because it lives in the shared pattern, it fires at every Agent-mode dispatch site for every role.
Override point B is the `## Driver preamble` section, consulted at `mill-go-base/SKILL.md:30-33`;
this task does not use it.

**The four fixer dispatch sites**, all of which route through Override point A:

| Site | Line | `<args>` to `millpy-fix.py` |
|---|---|---|
| Per-batch APPROVE, `nit_count > 0` | `:791` | `--scope batch --batch-name <b> --review-file <f> --round <N> --nits-only --prior-blocking <p>` |
| Per-batch `REQUEST_CHANGES` | `:813` | `--scope batch --batch-name <b> --review-file <f> --round <N>` |
| Holistic APPROVE, `nit_count > 0` | `:1239` | `--scope holistic --review-file <f> --round {H} --nits-only --prior-blocking <p>` |
| Holistic `REQUEST_CHANGES` | `:1261` | `--scope holistic --review-file <f> --round {H}` |

**The prepare envelope** the Builder parses at step 2 is built by
`_implementer_common.emit_prepare` (`:1324-1373`) and always contains `stage`, `brief_path`,
`subagent_type`, `model`, `session_id`, `role`, `scope`, `round`, plus optional `start_sha`,
`nits_only`, and `effort`.
For a fixer dispatch, `role` is `"fix"` and `scope` is the batch name or `"holistic"`.
Note that fixer envelopes carry **no `output_path`** — that field exists only on the three review
CLIs — so step 6 keeps deriving `<brief_path>.out.md`, and step 4(c)'s reviewer-only `test -f`
pre-check does not apply to the fixer (`mill-go-base/SKILL.md:312-316`).

**What is unchanged by forking.**
Steps 4 (classification and recovery), 5 (write the notification message to `<brief_path>.out.md`),
6 (`--stage finalize`), and 7 (branch on verdict) all operate on the `<task-notification>` and the
`agentId`.
`plugins/mill/docs/harness-tool-contracts.md:10-22` records the confirmed contract for those two
things — a launch acknowledgement carrying an `agentId`, then exactly one combined-result
`<task-notification>` with a `<status>` tag — but it was spiked against `Agent(subagent_type: ...)`
generally and does **not** single out `subagent_type: "fork"`.
That a fork delivers both identically is therefore a mechanical inference (same tool, same
notification pipe), not an independently spike-confirmed fact.
The inference is load-bearing: steps 4 through 7 are reused unchanged on the strength of it.
It is also the cheapest thing to falsify — the very first `/mill-go2` run exercises it, and a fork
whose notification shape differs would show up immediately as a misclassified dispatch rather than
as a subtle wrong answer.
If that happens, the fix is scoped to the override's fallback trigger, not to the base.
Step 6 for `millpy-fix.py` still requires `--review-file` at every stage (its argparse validates
before branching on `--stage`), still passes `--session-id` and `--start-sha`, still passes
`--nits-only` when and only when the prepare envelope carried `nits_only: true`, and still needs an
extended Bash timeout (~600000ms) because fix-CLI finalize replays every batch's `verify:` command.
The per-batch and holistic cleanup blocks call `_llm_claude.cleanup_session(sid)`, which is a
no-op-safe call when there is no psmux session to reap.

**Byte accounting for the variant file.**
Current 804 bytes, cap 4096 (exclusive).
The `### fixer` override should land around 1200-1400 bytes, leaving roughly 1900-2100 bytes for
the sibling task's `### implementer` block.
This is comfortable but not unlimited — prefer terse imperative prose over restating base
behaviour, and reference the base's step numbers rather than reproducing their text.

**Banned literals in the variant file** (enforced by `test-mill-go-variants.py`):
the machinery headers `## Agent-mode dispatch`, `## Holistic code review`, `## Execute`, and the
string `You are the **Builder**`;
and the hardcoded families `"mill-go: `, `_notify.notify("mill-go.`, and `[mill-go]`.
Write `<VARIANT_LABEL>` in the override's `_notify` and commit-message strings rather than a
literal variant name — `mill-go2` would not trip the checks, but `<VARIANT_LABEL>` matches how the
base parameterizes the same three families and survives a future variant rename.
Refer to the shared pattern as "the default Agent call" or "Override point A", never by its section
heading, which is a banned machinery literal.

## Constraints

There is no `CONSTRAINTS.md` at the hub root.
Constraints discovered during discussion:

### variant-file-byte-cap

`test-mill-go-variants.py:146` fails any variant SKILL.md of 4096 bytes or more.
Two independent tasks are adding text to the same 804-byte file.
See the byte accounting above.

### no-machinery-in-variants

The same test bans four base-machinery literals from variant files.
The override text must not name the shared dispatch section by its heading.

### required-headers-are-line-exact

`_check_override_sections_present` matches `## Dispatch overrides`, `## Driver preamble`, and
`## Variant binding` against `splitlines()`, so each must remain its own exact line.
Adding `### fixer` beneath `## Dispatch overrides` is safe;
altering, indenting, or suffixing the `##` header line is not.

### mill-go-must-not-regress

`plugins/mill/skills/mill-go/SKILL.md` must still declare `(none)` for both override points after
this task.
The new test check asserts this directly.

### ascii-only-in-generated-output

Per `CLAUDE.md`, `print()`/`_log()` output is ASCII-only.
The new test's failure strings must use ` -- ` rather than an em dash and `->` rather than an
arrow glyph.

## Testing

This task has two test surfaces: a contract-locking check on the variant SKILL.md files, and
genuine behavioural coverage for the one new `_status.py` helper.

**TDD candidate 1 — `_status.append_fork_fallback_log` in `test-status.py`.**
Write the cases first;
the helper is small enough that its whole behaviour is specified before a line of it exists.
Extend `plugins/mill/unit_tests/test-status.py`, which already imports the two analogous helpers and
carries a six-case template for `append_inferred_success_log` at `:982-1090`.
Mirror that template's case list exactly, since the new helper mirrors the implementation:

- Creates the `## Fork-fallback log` section lazily on first call.
- Appends a second row without disturbing the first.
- The row carries the scope label and the round number.
- **Does not disturb `## Timeline` or the yaml block's `phase:`** — this is the case that locks the
  BLOCKING finding from discussion review round 1 and is the reason the helper exists at all.
  It must assert `phase:` is byte-identical before and after.
- Raises `ValueError` when the section heading is present but its fenced block is missing.
- Raises `ValueError` when the fenced block is unterminated.

Cover both scope shapes in the row-format case: a batch name (`batch-a`) and the literal `holistic`.
Do not re-test the lazy-section-insert machinery itself beyond the above — it is
`_find_inferred_success_log_block`'s already-covered pattern, and the new helper's own
`_find_fork_fallback_log_block` is a direct copy.

**TDD candidate 2 — the one new check in `test-mill-go-variants.py`.**
Write the check first against the current `(none)` state, watch it fail, then write the override
text and watch it pass.
This is a genuine TDD candidate because the assertion is fully specified before the prose exists.

Add a `_check_fork_override()` function following the file's established shape (module-level
function returning `list[str]` of `FAIL: ...` strings, registered in `main()`'s `checks` tuple).
It should extract the `## Dispatch overrides` section body for each variant, then assert the
conditions below.

**The extraction rule needs care.**
The naive "from the header line to the next line beginning `## ` or end of file" rule is **wrong**
against the files as they exist today.
`## Dispatch overrides` is the last `##` header in both variant files, and the shared closing
paragraph — `Load the `mill:mill-go-base` skill via the Skill tool, ...` — sits directly beneath it
with no separating header.
A run-to-EOF rule therefore swallows that boilerplate into the section body, and the
`mill-go`-is-exactly-`(none)` assertion below fails on the unedited file.

Extract instead from the line after `## Dispatch overrides` up to whichever of these comes first:
the next line beginning `## `, the line beginning ``Load the `mill:mill-go-base` skill``, or end of
file.
Then strip surrounding whitespace.
Assert on that body:

- `mill-go2`'s section body is **not** `(none)`, names the `fixer` role, and contains the literal
  `subagent_type: "fork"`.
- `mill-go`'s section body **is** exactly `(none)` after stripping.

Update `main()`'s docstring, which currently reads "Run all seven variant-contract checks".

**Scenarios that must be covered by the check, stated as the failures it should catch:**

- The override is added to the wrong variant (`mill-go` instead of `mill-go2`).
- The override is added to `mill-go2` but the placeholder `(none)` is left in place alongside it.
- The section is filled with text that never names `fork`, e.g. a prose note that forgets the
  actual dispatch change.
- `mill-go`'s `(none)` is deleted or replaced during a sibling-task merge conflict resolution.
- The extraction rule regresses to running to EOF and starts swallowing the shared
  `mill:mill-go-base` loading paragraph into the section body.
  Guard this by asserting the extracted `mill-go` body is exactly `(none)` — that assertion fails
  loudly the moment the boilerplate leaks in, which is precisely why it is stated as an equality
  rather than a `"(none)" in body` containment check.

**Regression coverage that comes for free** from the existing checks, once the file is edited:
the 4096-byte cap, the four machinery literals, the three required header lines, the
single-`VARIANT_LABEL`-binding rule, and the hardcoded-`mill-go`-literal ban.
These need no new assertions;
they simply must still pass.

**Verify command** (Python project, so the `PYTHONPATH=` isolation prefix is mandatory):

```
PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-mill-go-variants.py
PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-status.py
```

Both files are standalone runners printing a `PASS:`/`FAIL:` summary and exiting non-zero on
failure, so a plan card may carry either line as its `verify:` depending on which file that card
touches.

Confirmed green against the pre-change tree during discussion.

**Not tested, deliberately:** the fork dispatch itself.
Whether `Agent(subagent_type: "fork")` produces a usable fixer is the experiment's question, and it
is answered by running `/mill-go2` on a real task, not by a unit test.
The `fork-fallback-fix-<scope>-r<N>` status rows from Decision `record-the-fallback` are the
instrument for that observation.

## Q&A log

- **Q:** Which fixer dispatch sites get forked — all four, NIT-only passes, or batch scope only?
  **A:** All four sites.
  **Why:** Override point A is role-scoped rather than site-scoped, so a site-selective override
  would have to enumerate call sites in a byte-capped file and would drift if the base moves one.
- **Q:** What triggers the fallback when a fixer fork dies or stalls, and what is the fallback?
  **A:** Reuse the base's existing step-4 classification verbatim;
  on the first terminal failure, re-dispatch cold with the same `brief_path`.
  **Why:** the brief is already on disk from prepare and step 4(c) already probes fixer dispatches,
  so no new machinery is needed.
- **Q:** A fork inherits the orchestrator's tool grant — accept, tighten via the prompt, or treat as
  blocking?
  **A:** Accept and document as an explicit experiment risk.
  **Why:** the proposal's premise was wrong (the cold fixer already dispatches as
  `mill:mill-implementer`), and fixer scope discipline comes from the brief and the
  `scope_violations` gate, never from the grant.
- **Q:** How is the driver-model requirement enforced?
  **A:** Documentation only — a note in the variant's override text, no config key.
  **Why:** the driver model is the operator's session model;
  nothing inside mill can read it, so enforcement is not evaluable.
- **Q:** How is the conflict with the sibling task, which edits the same section, handled?
  **A:** Structure `## Dispatch overrides` as one `### <role>` subsection per role from the start.
  **Why:** the two tasks then append disjoint blocks, reducing the conflict to a trivial textual
  resolution.
- **Q:** Does the cold fallback consume the existing one-retry-transient budget or add an attempt?
  **A:** [auto-pick] It consumes the existing budget.
  **Why:** mill-go2 then escalates after exactly as many attempts as mill-go, keeping the
  experiment's outcomes comparable to the production orchestrator.
- **Q:** Should the fallback be recorded for measurability?
  **A:** [auto-pick] Yes — `_notify` plus a committed `status.md` phase row.
  **Why:** fork death rate is the experiment's key measurement, and an unrecorded fallback is
  invisible once the session ends.
- **Q:** Where does the test coverage live?
  **A:** [auto-pick] Extend `test-mill-go-variants.py` with one new check.
  **Why:** that file already owns every assertion about these two SKILL.md files;
  a second file would drift.
- **Q:** The shared research carries a third open question — does the long-lived driver session need
  to periodically re-fork or reset to bound its own context growth?
  **A:** Scoped out explicitly, with no mitigation in this task.
  **Why:** it is a driver-session property rather than a fixer-dispatch one, so any mitigation would
  be variant-wide machinery colliding with `no-base-edits` and the byte cap;
  and the implementer path forks far more often, so driver bloat would surface there first.
  Recorded as a Decision so the omission is legible as a choice.
- **Q:** Discussion review r1 [BLOCKING]: `append_phase` with a `fork-fallback-fix-*` literal
  overwrites `phase:` and breaks the entry gate's crash-resume table.
  How is the fallback recorded instead?
  **A:** [auto-pick] Via a new append-only `_status.append_fork_fallback_log` helper that writes its
  own `## Fork-fallback log` section and never touches `phase:`.
  **Why:** registering the literal in the base's widening table would require a `mill-go-base` edit,
  conflicting with `no-base-edits`;
  an audit section sidesteps the conflict and leaves `phase:` at `fixing-{scope}-r{N}`, which the
  existing widening regex already routes correctly.
  Accepted consequence: scope widens to include one production-code change.
- **Q:** Discussion review r1 [NIT]: does anything actually depend on the envelope's `role` field,
  given Override point A identifies the role by calling subsection?
  **A:** [auto-pick] Nothing does — the decision was replaced with
  `role-identification-is-structural`.
  **Why:** the per-role `### fixer` subsection already performs the discrimination;
  envelope-inspection prose would cost bytes and imply a step the base does not ask for.
- **Q:** Discussion review r2 [BLOCKING]: step 4's retry is an action inside step 4, not a fresh
  pass through step 3 — so what stops the override from being re-consulted and forking again
  instead of going cold?
  **A:** [auto-pick] The override text states its own applicability condition (first attempt per
  scope/round) and the Builder tracks a local `fork_attempted` flag.
  **Why:** Override point A is role-scoped and carries no attempt-number signal, and nothing in the
  envelope does either;
  without the condition the cold fallback silently becomes a re-fork.
  See Decision `override-applies-to-first-attempt-only`.
- **Q:** Discussion review r2 [BLOCKING]: the prescribed section-extraction rule runs to EOF and
  swallows the shared `mill:mill-go-base` loading paragraph, so the `mill-go`-is-`(none)` assertion
  fails on the unedited file.
  **A:** [auto-pick] Stop extraction at the next `## ` line, the ``Load the `mill:mill-go-base`
  skill`` line, or EOF — whichever comes first.
  **Why:** `## Dispatch overrides` is the last `##` header in both variant files, so the boilerplate
  has no header separating it from the section body.
- **Q:** Is the "a fork notifies identically to a cold `Agent()` call" claim spike-confirmed?
  **A:** No — it is a mechanical inference;
  `harness-tool-contracts.md` spiked the Agent tool generally, not `subagent_type: "fork"`.
  Stated as an inference in `Technical context` rather than as a confirmed fact, and named as the
  first thing a real run falsifies.
- **Q:** Does `mill-go-base` need any edits, including to its `Why not fork?` section?
  **A:** [auto-pick] None — the override is purely additive in the variant file.
  **Why:** Override point A already consults the variant at every dispatch, and naming a specific
  variant in the base would violate the parameterization lock the variant contract enforces.
