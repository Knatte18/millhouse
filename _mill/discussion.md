# Discussion: mill-go2: fork-based implementer dispatch

```yaml
task: 'mill-go2: fork-based implementer dispatch'
slug: mill-go2-fork-implementer
status: discussing
parent: main
```

## Problem

`mill-go` dispatches a fresh, cold `Agent()` call for every per-batch implementer.
Each implementer re-orients from scratch: it reads its brief, its batch file, and the overview's Shared Decisions with no memory of anything the orchestrator already learned.
The sibling repo Loomyard runs its "Webster" implementer on Claude Code's `Agent(subagent_type: "fork")` instead, where each batch's implementer is forked in-session from the long-lived driver and inherits everything the driver already read.
That raised the question this task answers: can mill get the same benefit, and at what cost?

**Why now:** the dependency `mill-go2-scaffold` landed at commit `6cda129c`.
It split the orchestrator into `plugins/mill/skills/mill-go-base/SKILL.md` (1481 lines of machinery) plus two thin variant wrappers, `mill-go/SKILL.md` and `mill-go2/SKILL.md` (28 lines each).
The scaffold created two named extension points specifically so fork experiments could land without touching the production orchestrator:

- **Override point A** — a variant's `## Dispatch overrides` section, consulted per-role at Agent-mode dispatch step 3 (`plugins/mill/skills/mill-go-base/SKILL.md:238-242`).
- **Override point B** — a variant's `## Driver preamble` section, injected ahead of `## Entry` (`plugins/mill/skills/mill-go-base/SKILL.md:30-33`).

Both are the literal text `(none)` in `mill-go2/SKILL.md` today.
This task fills Override point A for the implementer role only.

**A correction to the task proposal's premise, established during exploration.**
The proposal's stated benefit is that forked batches "inherit the driver's already-loaded plan/codebase context."
That is not true of mill's orchestrator.
`mill-go-base/SKILL.md:10-15` and its `Lean Builder` principle (`:1445-1447`) state that the Builder reads only `status.md`, the Batch Index DAG in `00-overview.md`, and the fenced yaml verdict block of each code review — never card bodies, diffs, or source files.
So a mill fork inherits roughly 40k tokens of *orchestrator instructions* and approximately zero code orientation.
Loomyard's own `internal/websterengine/fork-prefix.md` is explicit that its Master session does carry "the codebase orientation, the plan's framing, and every constraint Master already read up front" — mill's Builder deliberately does not.

This task proceeds anyway, as a measurable proof of concept, with the premise correction recorded rather than silently inherited.
See Decision `lean-builder-premise-correction` for the full reasoning and for the follow-up that would make the fork rationale actually hold.

## Scope

**In:**

- `plugins/mill/skills/mill-go2/SKILL.md` — replace the `(none)` body of `## Dispatch overrides` with an implementer-role override that dispatches `Agent(subagent_type: "fork")`, carries a de-briefing prompt, and defines the cold fallback.
- `plugins/mill/skills/mill-go-base/SKILL.md` — prose-only edit to the `**Why not fork?**` paragraph (`:423-431`): add a cross-reference to mill-go2 and correct the factually-wrong disqualifier #3.
- `plugins/mill/unit_tests/test-mill-go-variants.py` — extend with mill-go2 fork-override assertions and a lock that mill-go's own overrides stay `(none)`.

**Out:**

- **The fixer role.** Sibling task `mill-go2-fork-fixer` owns it, same pattern. This task must not touch fixer dispatch.
- **The reviewer role.** Forking a reviewer would give it the driver's `Edit`/`Write`/`Bash` grant and destroy its read-only guarantee. Disqualifier #2 has no accepted mitigation for review.
- **The merge-in role.** Not mentioned in the proposal; unchanged.
- **`mill-go/SKILL.md`.** Its `## Dispatch overrides` stays `(none)`. The production orchestrator's behaviour must not change.
- **Any Python behaviour change.** `millpy-implement.py`, `_agent_dispatch.py`, `_status.py`, and `templates/implementer-brief.md` are all unchanged. The brief is rendered identically for forked and cold dispatch.
- **Parallel/concurrent forks.** Sequential only, one fork in flight, matching both Webster's production behaviour and mill-go-base's already-sequential batch loop.
- **Driver context-growth mitigation.** Recorded as a known risk (Decision `driver-context-bloat-out-of-scope`), not addressed.
- **A `## Driver preamble` for mill-go2.** Stays `(none)`. See Decision `lean-builder-premise-correction`.
- **Any new per-role model config key.** See Decision `model-and-effort-loss-is-documentation-only`.

## Decisions

### lean-builder-premise-correction

- **Decision:** implement the fork as a mechanical dispatch swap and keep the Builder lean. The implementer brief stays fully self-contained; nothing is removed from it on the assumption that the fork will already know it. Record in `mill-go2/SKILL.md` that the inherited context is predominantly orchestrator instructions, not code orientation, so the PoC's outcome can be read honestly.
- **Rationale:** the proposal's benefit claim does not survive contact with `mill-go-base`'s `Lean Builder` principle (`:1445-1447`). Making the claim true would require a `## Driver preamble` that has the driver read the plan overview and key source before batch 1 — deliberately breaking Lean Builder, which is the principle that "lets Opus be a legitimate Builder choice" (`:1447`). That is a materially larger change than the proposal's stated "minimal proof-of-concept scope preferred for the first pass," and it should be decided by measurement rather than assumed up front.
- **Rejected:** (a) adding a Webster-style orientation `## Driver preamble` now — larger, breaks a stated principle, and pre-commits to an unmeasured benefit; (b) abandoning the fork entirely — the measurement is cheap and the scaffold exists precisely to run it.
- **Follow-up (not this task):** if the PoC shows the fork underperforms cold dispatch, the next experiment is Override point B carrying up-front orientation. Note this explicitly in the variant file so a later reader does not conclude "fork does not help" when what was actually measured is "fork with nothing useful to inherit does not help."

### fork-dispatch-shape

- **Decision:** the implementer override replaces Agent-mode dispatch step 3's default `Agent()` call with `Agent(subagent_type: "fork")`. The `model` argument from the prepare envelope is not passed (a fork ignores it). Everything else in the Agent-mode dispatch pattern — step 2 prepare, step 4 classification, step 5 `.out.md` capture, step 6 finalize, step 6.5 `incomplete` recovery, step 7 branching — is followed unchanged.
- **Rationale:** the override point is defined as "follow it instead of the default `Agent()` call below" (`mill-go-base/SKILL.md:238-242`), which scopes the override to step 3 alone. A fork returns an `agentId` and delivers a completion `<task-notification>` exactly as a cold agent does, so step 4's `TaskOutput` liveness probe and step 6.5's warm `SendMessage` resume both work unmodified.
- **Rejected:** overriding more of the dispatch pattern — nothing else in it is fork-sensitive, and widening the override would duplicate base machinery into a variant file that is byte-capped and literal-banned (see `variant-byte-cap`).

### de-briefing-lives-in-the-fork-prompt

- **Decision:** the fork's inline `prompt` is a short de-briefing followed by the existing brief pointer, rather than the bare `"Read this file and follow the instructions exactly: <brief_path>"`. It must state that the fork is the implementer and not the orchestrator, that every mill-go-base instruction it inherited belongs to the driver and not to it, that it must not drive the batch loop or invoke any orchestration CLI, and that it must not dispatch further agents or workflows. It then points at `<brief_path>` as the authoritative instruction set.
- **Rationale:** the fork inherits `mill-go-base/SKILL.md` in full, including instructions that directly contradict its job — most sharply `Lean Builder`'s "You never read card bodies, diffs, or source files" (`:1446`), which is the exact opposite of what the implementer brief requires. Loomyard hit this same hazard and mitigated it the same way: `fork-prefix.md` carries a dedicated section titled "You are the IMPLEMENTER, not the driver — never run `lyx webster`", ending "Ignore any inherited instinct to drive the webster loop." The same section also covers the tool-grant hazard, since a fork inherits the driver's full grant (`Agent`, `Workflow`, `TaskCreate`, …) far beyond mill-implementer's declared `Read, Edit, Write, Bash, Grep, Glob, Skill` — a fork's grant cannot be narrowed structurally, so a prompt-level prohibition is the only available mitigation.
- **Rejected:** (a) rendering the de-briefing into `templates/implementer-brief.md` — that template is shared with mill-go, so the change would leak into the production orchestrator, and the text would arrive *after* the inherited instructions rather than overriding them at the prompt level; (b) putting it in `## Driver preamble` — wrong layer entirely, since the preamble becomes part of the driver context that the de-briefing exists to override; (c) no de-briefing — Webster's own source shows this is a real, encountered failure mode, not a hypothetical.
- **Literal hazard:** the de-briefing text must not contain the exact string `You are the **Builder**`, which `test-mill-go-variants.py`'s `MACHINERY_LITERALS` bans from variant files. Phrasings without the bold markers are safe.

### cold-fallback-on-dead-fork

- **Decision:** when a forked implementer dispatch reaches a terminal-failure re-dispatch, re-dispatch **cold** — a non-fork `Agent()` call using the prepare envelope's `subagent_type` and `model` — instead of re-forking. One cold fallback per batch; after that, the base's normal escalation applies unchanged. The triggering classification is entirely the base's existing step-4 logic; no new liveness machinery is added.
- **Rationale:** this directly answers fork disqualifier #3 and mirrors Webster's own cold "recovery-strand". The base's step 4(b) already runs a `TaskOutput(task_id: <agentId>, block: false)` liveness probe that distinguishes a still-running agent from a dead one before treating any notification as terminal, so the fork path inherits a correct death signal for free. Building a second, fork-specific probe would duplicate machinery the base already owns and that two live incidents (`#587`, `#595`) already hardened.
- **Rejected:** (a) Webster's two-tier recovery (warm re-fork once, then cold) — one extra attempt per batch plus a re-fork-already-used state variable to thread, for a retry that has no reason to succeed where the first fork failed; (b) also falling back cold on a malformed or missing report — finalize's completeness recount already resolves missing-JSON by counting commits against the batch's card count, without needing a re-dispatch at all.

### which-dispatch-points-fork

- **Decision:** the fork override applies to the initial implement dispatch (`### 1. Implement`, `mill-go-base/SKILL.md:572`) and to the transient one-retry re-dispatch. It does **not** apply to step 6.5.2's `--resume-incomplete` re-dispatch, which stays cold. Step 6.5.1's warm `SendMessage` resume is unaffected either way: it addresses the already-running agent by `agentId`, which works identically for a fork.
- **Rationale:** step 6.5.2 is already named "cold re-dispatch" in the base and exists as the escape hatch from a dispatch that failed to complete. Making it fork would re-enter the failure mode it exists to escape.
- **Rejected:** (a) forking all three points — uniform, but a resume-after-incomplete that already failed under fork would retry under fork; (b) forking only the initial dispatch — discards the fork on a single transient API blip, which would systematically bias the PoC's measurement against fork.

### model-and-effort-loss-is-documentation-only

- **Decision:** no new config key. `mill-go2/SKILL.md` documents that its own driver-session model becomes the effective implementer model, and that `roles.implementer.model` (currently `sonnetmedium` in this hub) no longer applies under fork. The documentation must state that **effort** is lost alongside model: `_agent_dispatch.resolve_subagent_type` encodes the resolved alias's effort tier as a `subagent_type` suffix (`sonnetmedium` → `mill:mill-implementer-medium`), and each of the six per-tier agent-definition files under `plugins/mill/agents/` pins a fixed `effort:` in its own frontmatter. A fork inherits the driver's effort, so both halves of the tier assignment are lost, not just the model half.
- **Rationale:** nothing inside a session can enforce that session's own model, so any config key would be advisory text with extra surface area. The user explicitly accepted the model consequence when scoping the task ("mill-go2 må typisk kjøre på en grei modell øverst"). The effort half was not previously called out and is recorded here because it is the same loss and equally invisible.
- **Rejected:** (a) a `roles.mill-go2.model` key — advisory-only, compared against nothing enforceable; (b) an Entry-time hard gate requiring operator confirmation — adds an operator prompt to a skill that is otherwise autonomous end to end.

### reuse-existing-report-contract

- **Decision:** no new fork report contract. The forked implementer reads the same `templates/implementer-brief.md`-rendered brief as a cold implementer, writes the same `<brief_path>.out.md`, and emits the same final-line JSON report. Finalize's existing completeness recount is the authority on partial-versus-complete.
- **Rationale:** the recount inspects actual commit count against the batch's card count, which is strictly stronger evidence than Webster's 3-field `status`/`head_sha`/`deviations` report. Adopting a second contract would mean a second parser, second test surface, and a divergence risk against mill-go for zero gain.
- **Rejected:** adopting Webster's 3-field report — it is the weaker signal, and mill already has the stronger one wired through `--stage finalize`.

### fork-fallback-status-marker

- **Decision:** append a status marker on the cold-fallback path only, via `_status.append_phase(status_path, f"fork-fallback-{batch_name}", _timestamp.now_utc_iso())`. The fork path itself gets no marker.
- **Rationale:** forking is mill-go2's documented default, so a marker on the fork path carries no information; the fallback is the event worth auditing. One-sided marking also costs the fewest bytes against the variant byte cap. The free-form phase-name shape matches existing base usage such as `f"approved-{batch_name}"` (`:805`).
- **Rejected:** (a) marking both paths — doubles the byte cost to record a non-event; (b) no marker at all — leaves the PoC's most interesting outcome invisible in the audit trail.

### variant-byte-cap

- **Decision:** the override text must fit inside the existing 4096-byte cap on variant SKILL.md files. Do not raise the cap.
- **Rationale:** `test-mill-go-variants.py`'s `_check_variants_carry_no_machinery` asserts every variant file is under 4096 bytes and free of the literals `## Agent-mode dispatch`, `## Holistic code review`, `## Execute`, and `You are the **Builder**`; `_check_parameterization_lock` additionally bans `"mill-go: `, `_notify.notify("mill-go.`, and `[mill-go]` from variant files. The cap is the scaffold's own regression guard against someone re-inlining base machinery into a variant. Raising it to accommodate the very first override would defeat it at the first opportunity. `mill-go2/SKILL.md` is roughly 1KB today, leaving roughly 3KB of budget — enough for a terse per-role override plus the de-briefing prompt text.
- **Rejected:** (a) raising the cap; (b) moving the override text into a separate file the variant references — adds an indirection the base's override contract does not define, and the base consults the *section*, not a pointer.

### correct-why-not-fork-in-base

- **Decision:** edit the `**Why not fork?**` paragraph in `plugins/mill/skills/mill-go-base/SKILL.md:423-431` — prose only. Add a sentence recording that mill-go2 accepts these trade-offs for the implementer role, and correct disqualifier #3. The heading text `**Why not fork?**` and the disqualifier-#2 claim that a fork inherits the parent's tools must both survive verbatim.
- **Rationale:** disqualifier #3 as written ("a fork has **no on-disk brief**, so a forked dispatch cannot be resumed after a crash the way `--resume-incomplete` resumes a briefed dispatch") is factually wrong for this design. `millpy-implement.py --stage prepare` renders the brief to disk via `_agent_dispatch.write_brief` regardless of dispatch shape, and `--resume-incomplete` re-runs prepare, so the brief is present and resume works. Leaving a claim in the shared base that a shipped variant contradicts is worse than a prose-only edit to shared text. Two other skills cite this paragraph by name and by claim — `mill-start/SKILL.md:179` cites all three disqualifiers, and `mill-plan/SKILL.md:119` cites the tool-inheritance claim specifically — so both must keep resolving.
- **Rejected:** (a) leaving it unchanged as a record of mill-go's own choice — it is not scoped as a mill-go-only statement, and it is wrong on the facts; (b) rewriting it wholesale — would break the two inbound citations.

### driver-context-bloat-out-of-scope

- **Decision:** the proposal's open question about the long-lived driver's own context growth across many batches is out of scope. Record it in the variant file as a known, unmeasured risk.
- **Rationale:** YAGNI. Forks are per-batch and short-lived; the driver's growth across a long plan is pre-existing mill-go behaviour that fork neither causes nor worsens. Adding a periodic driver-reset mechanism would be speculative design against an unobserved failure.
- **Rejected:** adding a driver context reset now.

## Technical context

**The variant contract (read this first).**
`plugins/mill/skills/mill-go2/SKILL.md` is a 28-line wrapper. It declares three sections — `## Variant binding` (binding `VARIANT_LABEL: mill-go2` in a fenced yaml block), `## Driver preamble`, and `## Dispatch overrides` — then loads `mill:mill-go-base` and defers all behaviour to it. `mill-go/SKILL.md` is byte-for-byte the same shape with `VARIANT_LABEL: mill-go`. Only the `## Dispatch overrides` body changes in this task.

**Where the override is consulted.**
`plugins/mill/skills/mill-go-base/SKILL.md:238-242`, inside step 3 of `## Agent-mode dispatch`:

> Override point A: consult your variant's `## Dispatch overrides` for this role; if it declares one, follow it instead of the default `Agent()` call below. The role for the current dispatch is the one named by the calling subsection (implementer, fixer, reviewer, or merge-in). A variant whose `## Dispatch overrides` section contains only `(none)` declares no override for any role, and the default `Agent()` call below applies unchanged.

The override therefore has to name the role it applies to (`implementer`) explicitly, and must leave fixer, reviewer, and merge-in unclaimed.

**Override point A is only live under agent dispatch.**
`## Agent-mode dispatch` runs only when `_agent_dispatch.resolve_dispatch_mode(cfg)` returns `"agent"` (reading `cfg["llm"]["claude"]["dispatch"]`, defaulting to `"agent"`). This hub is currently configured `dispatch: agent`. Under `subprocess` or `psmux` the entire section is skipped and `### 1. Implement` uses the `millpy-bg` path instead, where no fork is possible. The override must not attempt to change subprocess/psmux behaviour, and the variant file should say so, so a later reader does not report "fork did not engage" when the real cause is a dispatch-mode setting.

**The Agent-mode dispatch pattern, and which parts are fork-sensitive.**
Full pattern at `mill-go-base/SKILL.md:217-392`. Only step 3 changes. The parts that matter for review:

- Step 2 (`--stage prepare`) yields `brief_path`, `subagent_type`, `model`, `session_id`, `round`, `start_sha`, `effort`. Under fork, `subagent_type` and `model` go unused for the dispatch itself but are still needed for the cold fallback, so they must be retained.
- Step 3 instructs recording the returned `agentId` and retaining it for the batch. This is load-bearing for step 4's liveness probe and step 6.5's warm resume, and a fork returns one just as a cold agent does.
- Step 4(b) splits implementer notifications into clean turn-exhaustion (routes straight to Clean mid-work stop) and non-clean terminal (`<status>` present and not `completed`), the latter gated by a `TaskOutput(task_id: <agentId>, block: false)` probe. Unchanged under fork.
- Step 5 writes the notification message to `<brief_path>.out.md` for implementer dispatches. Unchanged.
- Step 6 (`--stage finalize`) passes `--agent-output <brief_path>.out.md`, `--session-id`, and `--start-sha`. Needs an extended Bash timeout (600000ms) because implementer finalize replays every batch's `verify:` command. Unchanged.
- Step 6.5 recovers `stuck_type: incomplete` via warm `SendMessage` then `--resume-incomplete`. See Decision `which-dispatch-points-fork` for the fork boundary here.

**The implementer brief is already self-contained — verify this claim before relying on it.**
A fork does not receive `plugins/mill/agents/mill-implementer.md`'s system prompt; it inherits the driver's. Everything that system prompt contributes is already duplicated in the rendered brief:

- The Test Integrity Guardrail is at `plugins/mill/templates/implementer-brief.md:102-106`.
- Language-specific skills are injected as the `<LANGUAGE_SKILLS>` token, built by `_agent_dispatch.language_skills_directive`, which detects languages from the batch's `Edits`/`Creates`/`Moves` and always names `code-quality`.
- The no-`sed` rule is inherited from `CLAUDE.md` and `mill:conversation`, both of which a fork also inherits from the driver.

What is genuinely lost is only the *tool restriction* — see Decision `de-briefing-lives-in-the-fork-prompt` for the mitigation.

**Webster's source, for the reviewer's benefit.**
`/home/knatte/Code/loomyard/wts/loomyard/internal/websterengine/fork-prefix.md` is the closest prior art and is worth reading directly. Two things in it are load-bearing for this design: its opening comment states the fork "inherits Master's whole context — the codebase orientation, the plan's framing, and every constraint Master already read up front" (which mill's Builder does not provide), and its `## You are the IMPLEMENTER, not the driver` section is the de-briefing pattern this task copies.

**Files this task touches:**

- `plugins/mill/skills/mill-go2/SKILL.md` — the override.
- `plugins/mill/skills/mill-go-base/SKILL.md:423-431` — prose-only correction.
- `plugins/mill/unit_tests/test-mill-go-variants.py` — new assertions.

## Constraints

No `CONSTRAINTS.md` exists at the hub root. Constraints discovered during discussion:

- **4096-byte cap per variant SKILL.md**, plus the banned-literal sets described in Decision `variant-byte-cap`. Enforced by `test-mill-go-variants.py`. This is the binding constraint on how much the override can say.
- **`mill-go` must not change behaviour.** Its `## Dispatch overrides` stays `(none)`, and the base edit is prose-only.
- **Two inbound citations of the base's `**Why not fork?**` paragraph** must keep resolving: `mill-start/SKILL.md:179` and `mill-plan/SKILL.md:119`.
- **Verify commands must start with `PYTHONPATH=`** (literal, empty value) per root `CLAUDE.md`, because Python markers (`plugins/mill/pyproject.toml`) are present. Enforced by `_plan_validate.py`'s `verify-not-isolated` check.
- **No `sed`**, in this repo or in any prompt this task generates for a dispatched sub-agent.
- **ASCII-only in `print()` / `_log()` output** — applies to any test output added.
- **Fork is unavailable under `subprocess`/`psmux` dispatch.** Not a bug to fix; a boundary to document.

## Testing

This is a markdown-only change to two SKILL.md files, so conformance assertions in the existing unit-test suite are the only executable verification available. There is no runtime behaviour to unit-test — the override is instructions an LLM orchestrator follows.

**Primary test surface: `plugins/mill/unit_tests/test-mill-go-variants.py`** (extend, do not create a new file — it already owns the variant contract and its `main()` aggregates check functions into a single PASS/FAIL summary).

TDD candidates, all in that file:

- **mill-go2 declares a real implementer override.** Its `## Dispatch overrides` section body is not the bare literal `(none)`, and names the implementer role.
- **The override dispatches a fork.** The file contains the fork `subagent_type` literal.
- **The de-briefing directive is present.** Assert on a stable substring of the de-briefing text rather than the whole paragraph, so wording can be tuned without churning the test.
- **The cold fallback is declared.** The file names the fallback path.
- **mill-go stays unforked.** Its `## Dispatch overrides` body remains exactly `(none)`. This is the regression guard that keeps the production orchestrator out of the experiment, and it is the single most important new assertion.
- **The byte cap and banned literals still hold** for both variants. Already covered by `_check_variants_carry_no_machinery` and `_check_parameterization_lock`; the point is that they must keep passing after the override lands, which they will exercise automatically.

**Base-file assertions:**

- The `**Why not fork?**` heading literal still exists in `mill-go-base/SKILL.md` after the prose edit, since `mill-start/SKILL.md` and `mill-plan/SKILL.md` both cite it by name.
- The disqualifier-#2 tool-inheritance claim survives, since `mill-plan/SKILL.md:119` cites it specifically.

**Scenarios that must be covered but are not unit-testable**, and should be recorded in the plan as manual/PoC observations rather than faked as assertions: that a forked implementer actually completes a batch; that the cold fallback fires on a dead fork; that the de-briefing prevents the fork from acting on inherited Builder instructions. These are the PoC's actual subject matter and are observed by running `/mill-go2` on a real task, not by a test.

**Verify command shape**, matching the precedent set by the `mill-go2-scaffold` plan's own `00-overview.md`:

- Override/test batches: `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-mill-go-variants.py`
- Final batch: `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`

## Q&A log

- **Q:** Given that mill's Builder is lean by design and never reads plan cards or source, what is mill-go2's fork actually for? **A:** [auto-pick] Mechanical dispatch swap, keep Builder lean. **Why:** matches the proposal's own stated preference for minimal PoC scope; the Webster-style orientation preamble is a materially larger change that should be decided by measurement, not assumed.
- **Q:** Where does the "you are the implementer, not the orchestrator" de-briefing text live? **A:** [auto-pick] Inline in the fork's Agent prompt, defined in mill-go2's `## Dispatch overrides`. **Why:** no shared-code or template change, so mill-go is untouched, and the text overrides the inherited instructions at the prompt level rather than arriving after them.
- **Q:** How is the model/effort consequence of forking handled? **A:** [auto-pick] Document-only, no config key. **Why:** nothing inside a session can enforce that session's own model, so a config key would be advisory anyway; the effort half of the loss is newly recorded because it is equally invisible.
- **Q:** What triggers the cold fallback, and how deep does recovery go? **A:** [auto-pick] Reuse the base's step-4 classification verbatim; one cold fallback per batch, then normal escalation. **Why:** the base's existing `TaskOutput` liveness probe already distinguishes still-running from dead, hardened by two live incidents; no new machinery is warranted.
- **Q:** Which of the three implementer dispatch points fork? **A:** [auto-pick] Initial dispatch and transient retry fork; `--resume-incomplete` stays cold. **Why:** step 6.5.2 is already the documented cold escape hatch from a failed dispatch; forking it would re-enter the failure mode it exists to escape.
- **Q:** How does the override fit the 4096-byte variant cap? **A:** [auto-pick] Keep it terse and inline within the cap. **Why:** the cap is the scaffold's own regression guard against re-inlining base machinery; raising it for the first override defeats it immediately.
- **Q:** Should the base's now-partly-false `**Why not fork?**` paragraph be updated? **A:** [auto-pick] Add a cross-reference and correct disqualifier #3. **Why:** #3 is factually wrong for this design (the brief is written to disk regardless of dispatch shape), and leaving a claim a shipped variant contradicts is worse than a prose-only shared-file edit.
- **Q:** How is the fork's widened tool grant mitigated? **A:** [auto-pick] Prompt-level prohibition in the fork's inline prompt. **Why:** a fork's grant cannot be narrowed structurally; Webster mitigates the identical hazard identically.
- **Q:** What shape should the fork's report contract take? **A:** [auto-pick] Reuse the existing JSON envelope and finalize completeness-recount unchanged. **Why:** the recount is strictly stronger evidence than Webster's 3-field report, and a second contract adds a parser and divergence risk for no gain.
- **Q:** Should driver context bloat across many batches be addressed? **A:** [auto-pick] Out of scope; document as a known unmeasured risk. **Why:** YAGNI — forks are per-batch and short-lived, and driver growth is pre-existing mill-go behaviour that fork neither causes nor worsens.
- **Q:** What is the testing approach for a SKILL.md-only change? **A:** [auto-pick] Extend `test-mill-go-variants.py` with fork assertions plus a lock that mill-go's overrides stay `(none)`. **Why:** conformance assertions are the only executable verification available, and that file already owns the variant contract.
- **Q:** What verify command shape do the batches use? **A:** [auto-pick] `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-mill-go-variants.py`, with `run-all.py` on the final batch. **Why:** byte-for-byte the shape the `mill-go2-scaffold` plan used, and the `PYTHONPATH=` prefix is mandatory because Python markers are present.
- **Q:** Is a prose-only edit to the shared `mill-go-base` acceptable in a task scoped to mill-go2? **A:** [auto-pick] Yes. **Why:** no behavioural literal changes, and both inbound citations keep resolving.
- **Q:** How is fork-versus-cold-fallback made visible in the audit trail? **A:** [auto-pick] Status marker on the cold-fallback path only. **Why:** forking is the documented default and carries no information; the fallback is the event worth auditing, and one-sided marking costs the fewest bytes against the cap.
