# Discussion: Auto-approve on review-round cap

```yaml
task: Auto-approve on review-round cap
slug: review-cap-auto-approve
status: discussing
parent: main
```

## Problem

Three review loops in mill v2 (mill-plan's Phase: Plan Review, and mill-go-base's per-batch and holistic Code Review loops) run up to a configured round cap while a `REQUEST_CHANGES` verdict persists.
In all three, the last round's suggested changes are already applied by the fixer before the cap is checked — what's actually missing at cap-exhaustion is only the *confirming re-review* that would push the verdict to `APPROVE`.
Today, hitting the cap with `REQUEST_CHANGES` still outstanding is a hard stop: `_status.set_blocked` halts the run and waits for a human to intervene (mill-plan already has a manual escape hatch for its own loop — a live "waive remaining BLOCKINGs at cap" operator instruction — but mill-go-base's two Code Review loops have no equivalent, and none of the three can be pre-authorized for an unattended run).

For low-stakes or time-pressured runs, the user wants an opt-in config flag that removes the wait: at cap-exhaustion with fixes already applied, treat the round as approved and proceed straight to handoff, instead of halting.

## Scope

**In:**
- A new per-role/scope boolean config flag, `auto_approve_on_cap`, under:
  - `roles.plan-review.holistic`
  - `roles.code-review.batch`
  - `roles.code-review.holistic`
- Wiring the flag into each of the three round-cap-exhaustion halt sites (below), so that when true, cap-exhaustion with `REQUEST_CHANGES` still outstanding is treated as an implicit approval and the run proceeds to handoff/next-batch instead of halting.
- Adding `auto_approve_on_cap: false` to the plugin config template (`plugins/mill/templates/mill-config.yaml`) for all three blocks, so hubs that opt in don't trigger the `[config] unknown key:` stderr warning (see Technical context — `_config.warn_unknown_keys` diffs actual config against the template).
- Keeping this hub's own `mill-config.yaml` in sync with the template per this repo's own convention (documented in this repo's `CLAUDE.md`).
- A unit test confirming the three new keys don't trigger the unknown-key warning (mirrors the existing pattern in `plugins/mill/unit_tests/test-config.py`).

**Out:**
- `roles.plan-review.batch` — this key exists in config and is read by mill-plan's Phase: Plan Review dispatch, but batch-scope plan review is dispatched *inside* the same holistic-round loop (see Technical context); there is no independent batch-scope round-cap halt site to wire. Only `roles.plan-review.holistic.rounds` drives the loop's own cap and step 6's halt.
- mill-start's Phase: Discussion Review (discussion-review loop). Not named in the task's own "which loop(s)" open question, and its round-cap-exhaustion behavior is already a materially different shape — a non-progress/extension mechanism (`prev_blocking_titles`/`extension_used`) under `--auto`, or an operator gap-prompt in plain interactive mode — rather than a single hard halt. Retrofitting the same flag there would mean redesigning that machinery, not reusing it.
- The **non-progress halt** (mill-plan step 5: identical pushed-back finding set across two rounds). This signals a stable disagreement between planner and reviewer, not a cap running out on an otherwise-converging loop, and stays a hard stop regardless of this flag. mill-go-base's two Code Review loops have no equivalent non-progress check today, so this exclusion is only actionable for mill-plan.
- **ERROR-only-round halts** and **usage-error halts** (all three loops' Step 3.5/4.5-equivalent sections) — infrastructure/LLM failures, not a persisting `REQUEST_CHANGES` verdict. Unaffected by this flag.
- The `min_rounds`/demoted-predicate **convergence gate** that already exists on the `APPROVE` path in all three loops (and mill-start's `--orch` two-consecutive-APPROVE rule). This flag never touches that machinery — see Decisions.
- Fixing the separately-tracked `_config.load_config` bug where `pipeline.max_review_rounds` (a stale/incorrect key name) is silently ignored from `config.local.yaml` (GitHub issue #1007, consolidated into wiki task `shared-helper-script-validation-gaps`, still unclaimed). See Decisions for why this is not a blocking dependency.

## Decisions

### Which loops get the flag

- Decision: `roles.plan-review.holistic`, `roles.code-review.batch`, `roles.code-review.holistic` — all three loops whose round-cap-exhaustion-with-`REQUEST_CHANGES` halt already discards a completed fix pass. mill-start's discussion-review loop is excluded (see Scope/Out).
- Rationale: the task's own open question named exactly "mill-plan's Phase: Plan Review, mill-go-base's Code Review loop, or both" — investigation confirmed mill-go-base's Code Review loop is actually two structurally-identical loops (per-batch and holistic), both with the same halt shape, so both get the flag rather than picking one arbitrarily.
- Rejected: discussion-review-only or all-four-loops — discussion-review's round-cap handling is a different, more elaborate mechanism (see Scope/Out); folding it in was rejected as scope creep the source issue didn't ask for.

### Config shape: per-role/scope flag, not a single pipeline-wide flag

- Decision: `auto_approve_on_cap: bool` (default `false`/absent) added independently to each of the three `roles.<role>.<scope>` blocks named above — not a single `pipeline.auto_approve_on_cap` switch.
- Rationale: matches the existing schema convention exactly — `rounds`, `min_rounds`, `reviewer`, `blocking_classes` are all already per-role/scope, not global. A hub may reasonably want auto-approve on code review but not on plan review (or vice versa); a single global flag would force an all-or-nothing choice the existing schema doesn't force for anything else. The source issue itself offered this as its example (`pipeline.auto_approve_on_cap` "or scoped per review role") — the per-role form is the better fit.
- Rejected: single `pipeline.auto_approve_on_cap` flag — simpler to add but a worse fit for the existing schema shape, and no way to opt in narrowly.

### Trigger condition: cap-exhausted with fixes already applied, not "apply fixes now"

- Decision: the flag only changes what happens *after* the last round's fixer has already run and the round-cap re-check finds no budget left for another review round. It does not add any new "apply outstanding changes" step — that step (a fresh fixer dispatch against the review's BLOCKING findings) already exists as the normal `REQUEST_CHANGES` handling in all three loops, and already runs before the cap is checked.
- Rationale: verified against the current code (not just the source issue's framing) — mill-plan's step 6 fires "only when round counter exhausts without APPROVE, BLOCKINGs still remain" but its own text clarifies "Step 4d's fixer pass already ran on those exact findings before this round-cap check fires." mill-go-base's holistic step 7 ("Rounds exhausted... `REQUEST_CHANGES` still returned") is reached the same way, through step 5's normal `REQUEST_CHANGES` → fixer-dispatch → loop-increment path. So "apply every suggested change from the most recent review round" (the source issue's wording) is already true by the time either of these two halts would fire; the flag only decides whether to stop and wait for a human to confirm that with a re-review, or skip the wait.
- Rejected: having the flag also dispatch an extra ad-hoc fix pass at cap-time — unnecessary, since the last round's fix pass already covered the findings that would otherwise trigger the halt.

### Per-batch site: gate explicitly on the last round's verdict, since the halt condition itself is verdict-agnostic

- Decision: unlike mill-plan's step 6 and mill-go-base's holistic step 7 (both explicitly conditioned on the exhausted round's verdict having been `REQUEST_CHANGES` with BLOCKINGs remaining), mill-go-base's **per-batch** step 5 ("Max-rounds exhaustion... After `roles.code-review.batch.rounds` rounds without APPROVE") fires on round-count alone, regardless of the last round's verdict. Step 4's `NEED_CONTEXT` branch never dispatches a fixer — it only records `extra_files` and increments the round — so a cap reached on a trailing `NEED_CONTEXT` round means step 5 fires with **no fix pass having run at all** for that batch. `auto_approve_on_cap` must therefore carry its own explicit verdict guard at this one site: treat cap-exhaustion as an implicit approval **only when the immediately preceding round's verdict was `REQUEST_CHANGES`** (i.e. a fixer did run against real findings before the cap hit) — mirroring holistic step 7's own condition. When the preceding round's verdict was `NEED_CONTEXT` (nothing was ever reviewed for correctness — the reviewer was still waiting on missing files), cap-exhaustion stays today's hard halt (`blocked`, `blocked_reason: "review rounds exhausted"`) regardless of the flag.
- Rationale: caught by discussion-review round 1 (BLOCKING, class `design`) — the original wording implied the trigger condition was uniformly "verdict was `REQUEST_CHANGES`, budget exhausted" across all three sites, which is true for mill-plan and holistic but not for per-batch as currently written. "Auto-approve" only makes sense when there was something to approve, i.e. a reviewer verdict that findings were addressed; a `NEED_CONTEXT`-only history never produced that.
- Rejected: extending `auto_approve_on_cap` to also cover the `NEED_CONTEXT`-exhausted case (e.g. treating "ran out of budget waiting for context" as an approval too) — there is no finding-set to have "applied," so calling the result "approved" would be fabricating a review outcome that never happened. Left as a hard halt, unchanged by this flag.

### Reuse mill-plan's existing manual escape hatch, don't invent a new one

- Decision: for mill-plan, `auto_approve_on_cap: true` firing at step 6 performs exactly the same terminal actions as the existing "Live operator waiver of step 6" mechanism (set `approved: true` in `plan/00-overview.md` frontmatter via direct Edit, commit on the task branch, push, proceed straight to Handoff) — just auto-triggered from config instead of requiring a live operator instruction mid-run. Use a distinct commit message noting the config-driven trigger, e.g. `"mill-plan: approve plan for {slug} (auto-approved on round-cap exhaustion, config auto_approve_on_cap)"`, so it's distinguishable in history from a live operator waiver.
- Rationale: mill-plan already has this exact mechanism for a human; making it fireable from config instead of a live instruction is the minimal change, and keeps one code path instead of two nearly-identical ones.
- Rejected: writing a separate parallel implicit-approve path for the config-triggered case — would duplicate logic mill-plan already has.

### mill-go-base: mirror the existing implicit-approve-at-cap shape, applied to a REQUEST_CHANGES-at-cap round

- Decision: for both mill-go-base loops, when `auto_approve_on_cap: true` and the round-cap is exhausted with the last round's verdict `REQUEST_CHANGES` (per-batch: gated additionally on that being the *immediately preceding* round's verdict specifically, per the "Per-batch site" Decision below — a `NEED_CONTEXT`-exhausted cap never qualifies), run the same terminal actions the loop already runs on a normal `APPROVE`: per-batch → set batch state → `approved`, `_status.append_phase(status_path, f"approved-{batch_name}", ...)`; holistic → `_status.append_phase(status_path, "holistic-approved", ...)`. Each commit message appends the literal suffix `" (auto-approved on round-cap exhaustion, config auto_approve_on_cap)"` — parallel in form to the existing `" (min_rounds/demoted-predicate not satisfied by round cap)"` suffix already used for the APPROVE-path implicit-approve-at-cap case, but distinct text so the two triggers are distinguishable in history — and each keeps its existing `_notify.notify(...)` call so the auto-approval is still observable, not silent.
- Rationale: both loops already have an "implicit approval at cap" concept — today it only fires on the `APPROVE` branch when the `min_rounds`/demoted-predicate convergence gate isn't satisfied (see next Decision for why that's a separate, untouched mechanism). Reusing the same terminal-action shape for the new REQUEST_CHANGES-at-cap trigger keeps the two "approved via the round cap" cases visually and mechanically consistent in status.md/commit history.
- Rejected: a bespoke terminal-action sequence distinct from the existing APPROVE path — no reason found in the code for the two cases to diverge in what "approved" means for the batch/holistic state machine.

### This flag never touches the `min_rounds`/demoted-predicate convergence gate

- Decision: `auto_approve_on_cap` is a deliberate, narrow override of a *different* halt path than the convergence gate governs, and the plan must keep the two mechanisms structurally separate. The convergence gate (`converged = round >= min_rounds and not any(demoted)`) only ever evaluates on a round whose verdict is already `APPROVE`; `auto_approve_on_cap` only ever fires on a round whose verdict is `REQUEST_CHANGES` and the round budget is exhausted. The two conditions are mutually exclusive per round (a round can't be both `APPROVE` and `REQUEST_CHANGES`), so there's no ordering or precedence question to resolve — they simply never fire on the same round.
- Rationale: this is the "substituted review round needs min 2" constraint the task body called out explicitly — a single APPROVE (human, auto-substituted, or otherwise) must never alone satisfy convergence. `auto_approve_on_cap` doesn't relax `min_rounds`, doesn't touch the `demoted` predicate, and doesn't interact with mill-start's `--orch` two-consecutive-APPROVE rule (which lives in a different, excluded loop anyway). It is a targeted override of the *hard-stop-on-persisting-REQUEST_CHANGES* behavior only.
- Rejected: folding `auto_approve_on_cap` into the convergence-gate formula (e.g. as an OR-clause) — would blur two conceptually distinct situations ("the reviewer keeps approving but the floor isn't met yet" vs. "the reviewer keeps finding BLOCKING issues and we're out of budget") under one flag, in a case the task body specifically warned against conflating.

### The separately-tracked `max_review_rounds` config-read bug is not a blocking dependency

- Decision: proceed without waiting for or bundling a fix for the `pipeline.max_review_rounds`-from-`config.local.yaml` bug (GitHub issue #1007, now folded into unclaimed wiki task `shared-helper-script-validation-gaps`).
- Rationale: verified against the current code, overriding the source issue's own assumption. That bug is about a **different, non-existent config key** — a hub operator trying to set `pipeline.max_review_rounds` in `config.local.yaml` gets silently ignored because that key was never real; the actual round cap all three loops read is `roles.<role>.<scope>.rounds` (confirmed live in `mill-config.yaml` at this hub: `roles.code-review.holistic.rounds: 5`, `roles.plan-review.holistic.rounds: 7`, etc., and confirmed read correctly by mill-start/mill-plan/mill-go-base's own Entry steps). `auto_approve_on_cap` is being added under that same, already-correctly-read `roles.*.*` block — it has no dependency on the broken `pipeline.max_review_rounds` alias ever being fixed.
- Rejected: sequencing this task after `shared-helper-script-validation-gaps` — would delay this task for a bug that, on inspection, doesn't actually affect the round cap this flag builds on.

## Technical context

- **mill-plan** (`plugins/mill/skills/mill-plan/SKILL.md`):
  - Entry reads `roles.plan-review.holistic.rounds` as `max_review_rounds` and `roles.plan-review.holistic.min_rounds` as `min_review_rounds`.
  - Phase: Plan Review's step 4d handles `REQUEST_CHANGES AND blocking_count > 0`: applies fixes to plan files, writes a fixer report, re-validates, commits as `plan-fix round {N}`.
  - Step 6 "Max-rounds escape" is the halt to wire: fires "only when round counter exhausts without APPROVE, BLOCKINGs still remain, non-progress did not fire, AND the operator has not given a live step-6-waiver instruction." The existing "Live operator waiver of step 6" paragraph (in the phase's preamble, near "Live operator-raised round-cap override") is the terminal-action template to reuse — same actions, config-triggered instead of live-instruction-triggered.
  - Step 5 "Non-progress check" is a distinct, earlier-firing halt — never touched by this flag (see Scope/Out).
  - `roles.plan-review.batch.reviewer`/`.rounds` are read too (step 2's dispatch-mode branch references `roles.plan-review.batch.reviewer` when non-null) but batch-scope plan review shares the same round loop and round-cap as holistic — there's no separate batch-scope halt site.

- **mill-go-base** (`plugins/mill/skills/mill-go-base/SKILL.md`, per-batch Code Review section):
  - Reads `roles.code-review.batch.rounds` per batch.
  - Step 4's `REQUEST_CHANGES` branch dispatches `millpy-fix.py --scope batch ...` (a fixer session) before looping to round N+1.
  - Step 5 "Max-rounds exhaustion" is the halt to wire: "After `roles.code-review.batch.rounds` rounds without APPROVE," sets batch state → `blocked`, halts. This condition is verdict-agnostic — it fires the same way whether the last round was `REQUEST_CHANGES` (fixer already ran) or `NEED_CONTEXT` (no fixer ever dispatched, per step 4's `NEED_CONTEXT` branch). Wiring `auto_approve_on_cap` here must additionally check that the immediately preceding round's verdict was `REQUEST_CHANGES` before treating the cap as an implicit approval — see Decisions ("Per-batch site: gate explicitly on the last round's verdict").
  - The `APPROVE` branch (step 4, first bullet) already has an "implicit-approve-at-cap" precedent for the *convergence-gate* case (`N >= roles.code-review.batch.rounds` when `not converged`) — same terminal actions (`approved` state, `approved-{batch_name}` phase, commit) to mirror for the new trigger, per Decisions above.
  - In this hub's own `mill-config.yaml`, `roles.code-review.batch.rounds: 0` / `reviewer: null` (batch code review is currently dormant here) — the flag must still be added to the schema/template even though this hub doesn't exercise it today; other hubs may enable batch code review.

- **mill-go-base holistic Code Review loop** (`plugins/mill/skills/mill-go-base/holistic-review.md`):
  - Reads `roles.code-review.holistic.rounds`/`.min_rounds`.
  - Step 5 `REQUEST_CHANGES` dispatches `millpy-fix.py --scope holistic ...` before looping to round H+1.
  - Step 7 "Rounds exhausted" is the halt to wire: fires when `H > max_holistic_rounds` and `REQUEST_CHANGES` was still returned, after step 5's fixer already ran. Sets `_status.set_blocked`, halts.
  - Step 4's `APPROVE` branch already documents the convergence-gate implicit-approve-at-cap precedent to mirror (`H >= max_holistic_rounds` when `not converged`): `_status.append_phase(status_path, "holistic-approved", ...)`, commit, "Proceed to Handoff."

- **Config plumbing** (`plugins/mill/scripts/_config.py`):
  - `load_config` deep-merges plugin template → hub `mill-config.yaml` → worktree `.millhouse/config.local.yaml`.
  - `warn_unknown_keys`/`walk_unknown_keys` diff the merged config against the **plugin template** (`plugins/mill/templates/mill-config.yaml`) and print a non-fatal stderr warning for any key absent from the template. Adding `auto_approve_on_cap: false` under all three `roles.*.*` blocks in the template is required to avoid spurious warnings once any hub sets the key to `true`.
  - `plugins/mill/unit_tests/test-config.py` already has the pattern to extend (e.g. around lines 944/1057/1383/1435/1498/1529): assert a given key does/doesn't produce an `"unknown key: ..."` stderr line.

- **Existing "Live operator waiver of step 6"** (mill-plan/SKILL.md, Phase: Plan Review preamble, near "Live operator-raised round-cap override"): the exact terminal-action sequence this task's mill-plan wiring should reuse.

## Testing

- **`_config.py` / template sync**: extend `plugins/mill/unit_tests/test-config.py` with a case (or extend an existing parametrized case) asserting that `roles.plan-review.holistic.auto_approve_on_cap`, `roles.code-review.batch.auto_approve_on_cap`, and `roles.code-review.holistic.auto_approve_on_cap` do NOT produce `[config] unknown key: ...` stderr warnings once the template is updated — mirrors the existing `pipeline.max_cards_per_batch`/`pipeline.test_probe_key` assertions in that file.
- **No new Python behavior to unit-test beyond config plumbing**: the halt-vs-auto-approve decision at each of the three sites is orchestrator-level SKILL.md instruction, not code the mill scripts execute — there is no `_review_*.py`/`_status.py` function that currently decides "halt or proceed," so this task has no corresponding Python unit-test surface for the auto-approve branching itself. (If the implementer finds an existing test harness that does simulate SKILL.md branching — e.g. a scenario/integration test — extend it instead of skipping verification; this bullet only rules out inventing new pure-Python unit tests for behavior that isn't implemented in Python.)
- **Manual/integration verification** (documented, not necessarily automated in this task): the same acceptance shape applies at all three flag sites — a hub with the relevant `rounds` set low (e.g. 1) and `auto_approve_on_cap: true`, run against a change that reliably draws a `REQUEST_CHANGES` verdict, should reach Handoff (mill-plan) / approve the batch and continue (mill-go-base per-batch) / approve and proceed to Handoff (mill-go-base holistic) instead of a `blocked` status after the single round's fix pass — vs. the same setup with the flag absent/false, which should still halt as today for all three. For the per-batch site specifically, also cover the `NEED_CONTEXT`-exhausted case (see Decisions "Per-batch site: gate explicitly on the last round's verdict") to confirm it still halts even with the flag set. This is the acceptance scenario mill-plan should design its own batches' `## Batch Tests` around, per this repo's plan-quality conventions — one scenario per flag site plus the per-batch `NEED_CONTEXT` exclusion case.

## Q&A log

- **Q:** Which review loop(s) should `auto_approve_on_cap` apply to — mill-plan's Plan Review only, mill-go-base's Code Review loop only, both, or all four loops including mill-start's discussion-review?
  1) Both mill-plan's Plan Review (holistic) and mill-go-base's Code Review (batch + holistic) — three flag sites total. (Recommended)
  2) mill-plan's Plan Review only.
  3) mill-go-base's Code Review loop(s) only.
  4) All four loops, including mill-start's discussion-review.
  **A:** [auto-pick] Option 1. **Why:** the source issue's own open question named exactly "mill-plan's Phase: Plan Review, mill-go-base's Code Review loop, or both" — it did not raise discussion-review as a candidate, and investigation confirmed mill-go-base's Code Review loop is actually two structurally-identical halt sites (per-batch, holistic), both fitting the same shape as mill-plan's. See Decisions ("Which loops get the flag").

- **Q:** Should this be one global `pipeline.auto_approve_on_cap` flag, or a flag scoped per review role/scope (matching the existing `rounds`/`reviewer` schema shape)?
  1) Scoped per role/scope: `roles.<role>.<scope>.auto_approve_on_cap`, added independently to the three blocks named above. (Recommended)
  2) One global `pipeline.auto_approve_on_cap` switch covering all three loops uniformly.
  **A:** [auto-pick] Option 1. **Why:** every other loop-behavior knob (`rounds`, `min_rounds`, `reviewer`, `blocking_classes`) is already per-role/scope in this schema; a global flag would be the only outlier and would force an all-or-nothing choice the rest of the schema doesn't force. See Decisions ("Config shape").

- **Q:** Does `auto_approve_on_cap` need to relax or interact with the `min_rounds`/demoted-predicate convergence gate (or mill-start `--orch`'s two-consecutive-APPROVE rule) to work?
  1) No — it fires on a structurally distinct condition (`REQUEST_CHANGES` verdict, round budget exhausted) that can never coincide with a round the convergence gate evaluates (`APPROVE` verdict); the two mechanisms stay fully separate. (Recommended)
  2) Yes — fold it into the convergence-gate formula as an additional OR-clause.
  **A:** [auto-pick] Option 1. **Why:** the task body explicitly warned against relaxing the "substituted review round needs min 2" gate in general — this flag is documented as "a deliberate override of that gate specifically at cap-exhaustion, not a general relaxation of it." Keeping the mechanisms structurally disjoint (different verdict, mutually exclusive per round) is the only way to honor that boundary without special-casing the gate's formula. See Decisions ("This flag never touches the convergence gate").

- **Q:** Is the separately-tracked `pipeline.max_review_rounds`-silently-ignored bug (GitHub #1007 / wiki task `shared-helper-script-validation-gaps`) a blocking dependency for this task?
  1) No — verify against current code before assuming so. (Recommended)
  2) Yes — sequence this task after that one lands.
  **A:** [auto-pick] Option 1, after verification. **Why:** read `_config.py` and the actual `roles.*.*.rounds` reads in mill-start/mill-plan/mill-go-base directly rather than trusting the issue text's framing (per this repo's own CLAUDE.md rule on verifying against real code). The broken key (`pipeline.max_review_rounds`) is not the key any loop's round cap actually reads (`roles.<role>.<scope>.rounds`, confirmed correct in code and in this hub's live config) — the two are unrelated, so no sequencing dependency exists. See Decisions.
