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

**Out:**

- `plugins/mill/skills/mill-go-base/SKILL.md` — **no edits at all**, including its `Why not fork?`
  section.
  See Decision `no-base-edits`.
- `plugins/mill/skills/mill-go/SKILL.md` — stays `(none)` for both override points.
  The production orchestrator is unchanged by this task, which is the entire reason the variant
  split exists.
- Every Python script.
  No change to `millpy-fix.py`, `_implementer_common.py`, `_agent_dispatch.py`, or any other
  helper.
  This task is SKILL.md text plus one test function.
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

### role-detection-via-envelope

- Decision: the Builder identifies a fixer dispatch by the prepare envelope's `role` field being
  `"fix"`.
- Rationale: `emit_prepare` sets `"role": role` unconditionally
  (`plugins/mill/scripts/_implementer_common.py:1362`), and `millpy-fix.py` passes the literal
  `"fix"` at its only prepare call site (`millpy-fix.py:653-666`).
  The field is already in the envelope the Builder parses at step 2, so no new discrimination
  logic and no script change is needed.
- Rejected: keying on the CLI name (`millpy-fix.py`) in the invocation text (works, but is a
  string the Builder would have to remember across the dispatch rather than a field it already
  parsed);
  keying on `subagent_type` (useless — fixer and implementer both resolve to
  `mill:mill-implementer`, see Technical context).

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

- Decision: immediately before the cold retry, emit both a notification and a status row, then
  commit the row:
  `_notify.notify("<VARIANT_LABEL>.fork-fallback", f"fixer {scope} r{N}", slug=slug)` and
  `_status.append_phase(status_path, f"fork-fallback-fix-{scope}-r{N}", _timestamp.now_utc_iso())`,
  followed by
  `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: fork-fallback for fixer {scope} r{N}"`.
  `{scope}` is the batch name for batch scope and the literal `holistic` for holistic scope,
  matching the `scope_label` the fix CLI already computes (`millpy-fix.py:655`).
- Rationale: how often a forked fixer dies is the single most valuable measurement this experiment
  produces, and an unrecorded fallback is invisible once the session ends.
  Both helpers are already used throughout the base, and committing the row immediately matches the
  base's own pattern for `self-resolved-verify-logic` and `self-resolved-terminal-dirt`.
- Rejected: `_notify` only (lost once the session ends);
  nothing at all (makes the experiment unmeasurable);
  folding the row into the fixer's own next commit (the fixer commits from a separate session and
  may never reach a commit if the cold retry also fails).

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
`agentId`, both of which a fork delivers identically to a cold `Agent()` call — see
`plugins/mill/docs/harness-tool-contracts.md:10-22` for the confirmed notification contract.
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

This task changes SKILL.md prose plus one test function;
there is no runtime Python behaviour to unit-test.
Coverage is therefore contract-locking, not behavioural.

**TDD candidate — the one new check in `test-mill-go-variants.py`.**
Write the check first against the current `(none)` state, watch it fail, then write the override
text and watch it pass.
This is a genuine TDD candidate because the assertion is fully specified before the prose exists.

Add a `_check_fork_override()` function following the file's established shape (module-level
function returning `list[str]` of `FAIL: ...` strings, registered in `main()`'s `checks` tuple).
It should extract the `## Dispatch overrides` section body — from that header line to the next line
beginning `## ` or end of file — for each variant, then assert:

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

**Regression coverage that comes for free** from the existing checks, once the file is edited:
the 4096-byte cap, the four machinery literals, the three required header lines, the
single-`VARIANT_LABEL`-binding rule, and the hardcoded-`mill-go`-literal ban.
These need no new assertions;
they simply must still pass.

**Verify command** (Python project, so the `PYTHONPATH=` isolation prefix is mandatory):

```
PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-mill-go-variants.py
```

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
- **Q:** Does `mill-go-base` need any edits, including to its `Why not fork?` section?
  **A:** [auto-pick] None — the override is purely additive in the variant file.
  **Why:** Override point A already consults the variant at every dispatch, and naming a specific
  variant in the base would violate the parameterization lock the variant contract enforces.
