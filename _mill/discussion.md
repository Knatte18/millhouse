# Discussion: mill-plan: review-round cap and skip-check threading bugs

```yaml
task: mill-plan: review-round cap and skip-check threading bugs
slug: mill-plan-review-round-cap-and-skip-check-threading
status: discussing
parent: main
```

## Problem

`mill-plan/SKILL.md`'s Phase: Plan Review has three real, currently-unresolved gaps, originally reported as five separate GitHub issues (#981, #970, #948, #934, #913). Two of those five (#934, #913 — skip-check threading) are **already fixed on `main`** by prior commits `3f6b5305` and `78dd2eef`; see "Already resolved" below. The three still-open gaps:

1. **#981** — Steps 4b and 4d (the NIT-fix and BLOCKING-fix paths in the review loop) only re-run `_plan_dag.validate()` after applying a fix — a narrow, DAG-structure-only check. They never re-run the full `_plan_validate.run` gate that Phase: Plan's own pre-commit self-validation, and Phase: Plan Review's own Step 1.5 pre-review gate, both already use. A fix pass (LLM-authored, applying a NIT or BLOCKING finding) can introduce any non-DAG validator error — e.g. `context-completeness` (a Requirements: prose line referencing a file not in Context:) — and nothing in 4b/4d catches it before the fix commit is pushed. It only surfaces on the *next* round's Step 1.5 gate, costing an extra round.
2. **#970** — There is no documented mechanism for an operator to raise the review-round cap *while a Phase: Plan Review loop is actively running* (as opposed to after a `blocked` halt, which the existing `--revise`/blocked-resume path already covers). mill-plan is autonomous and never pauses to prompt, but an operator can still interject a live instruction into a running session — this needs a documented session-local override, parallel to the existing "`--max-rounds` threading for blocked-resume" mechanism but not gated on `revise_from_blocked`. A related, currently-undocumented follow-on: whether the operator may also live-waive step 6's max-rounds escape (accept outstanding BLOCKINGs without spending another round).
3. **#948** — After step 6's max-rounds halt, the only documented resumption is `/mill-plan --revise`, which re-enters Phase: Plan Review for a *fresh full round budget*. There is no lighter path for an operator who has already read the last round's outstanding BLOCKING(s), judged them acceptable or already independently fixed, and wants to approve the plan as-is without spending another review round. Today this requires hand-editing `plan/00-overview.md`'s `approved:` field directly, bypassing every skill.

### Already resolved (dropped from scope)

**#934** ("`--skip-check` not threaded across review rounds") and **#913** ("verify-full-suite skip-check not carried into Phase: Plan Review prepare") are both already fixed on `main`. Confirmed by reading the current `mill-plan/SKILL.md` in the task worktree (not the plugin cache) and diffing against `main` (zero diff on this branch so far):

- `SKILL.md:275` — "Persist `skip_checks` for Phase: Plan Review" — Phase: Plan writes its `skip_checks` frozenset into `00-overview.md`'s `skip_checks:` frontmatter field.
- `SKILL.md:295` — "Read persisted `skip_checks` from Phase: Plan" — Phase: Plan Review reads it back as `plan_skip_checks` and threads it into "every round's CLI dispatch below as `--skip-check <name>` per entry".
- Threaded into every actual dispatch site: Agent-mode round dispatch (`SKILL.md:404`), subprocess round dispatch (`SKILL.md:460`), Agent-mode ERROR-retry (`SKILL.md:481`), subprocess ERROR-retry (`SKILL.md:501`).
- `millpy-review-plan.py` already accepts `--skip-check` (argparse at line 87, `dest="skip_checks"`) and `--max-rounds` (line 59) as CLI flags; both are already consumed (lines 220/327/345).
- `git log -S "Persist \`skip_checks\` for Phase: Plan Review" -- plugins/mill/skills/mill-plan/SKILL.md` → commit `3f6b5305`. `git log -S "max-rounds\` threading for blocked-resume" -- plugins/mill/skills/mill-plan/SKILL.md` → commit `78dd2eef`. Both already on `main`.

No further action needed for these two. mill-start does not close/comment on GitHub issues — that bookkeeping is out of scope for this skill.

## Scope

**In:**
- `plugins/mill/skills/mill-plan/SKILL.md` — Phase: Plan Review steps 4b and 4d (re-validation fix, #981); a new documented live-operator-override mechanism for the round cap and for waiving step 6 (#970); a new `--approve` argument, Entry pre-check, and fall-through path (#948).

**Out:**
- `_plan_validate.py`, `millpy-review-plan.py`, `_plan_dag.py`, `millpy-validate-plan.py` — no Python changes. All three fixes are expressible with capabilities these scripts already have (`_plan_validate.run`'s existing 7-kwarg signature; `millpy-review-plan.py`'s already-accepted `--max-rounds`/`--skip-check` flags).
- `#934`, `#913` — already resolved on `main`; no action.
- Any change to `mill-start/SKILL.md`, `mill-go-base/SKILL.md`, or `mill-go/SKILL.md` — this task touches mill-plan's own review-loop logic only. (mill-plan's existing text already cites mill-start's `--auto` extension-round mechanism and mill-go-base's shared dispatch pattern as precedent; neither of those files needs edits.)
- Editing `mill-config.yaml` (hub or template) — the operator-raised cap override is explicitly per-run only, never persisted to config, per #970's own text.

## Decisions

### #981 — full-validate re-run in 4b/4d

- Decision: In both step 4b (NIT-only APPROVE path) and step 4d (BLOCKING path), immediately after the existing `_plan_dag.validate()` call (kept unchanged — it and `_plan_validate.run` are non-redundant; confirmed `_plan_validate.run` never internally calls `_plan_dag.validate`, importing only `extract_batch_index`/`resolve_deps_as_names`/`PlanDAGError` from `_plan_dag`), add a call to `_plan_validate.run` using the identical 7 kwargs Phase: Plan's own self-validate uses (`root`, `git_root`, `wiki_root`, `skip_checks=plan_skip_checks`, `parent_branch`, `max_cards_per_batch`, `max_batch_context_tokens` — all already bound/resolvable at this point in Phase: Plan Review). If it returns errors, apply Step 1.5's existing mechanical-fix table (same table, same fix semantics — no new table), then re-run `_plan_validate.run` once more. If the second attempt still returns errors, call `_status.set_blocked(status_path, "plan-fix-r{N} validate non-progress", ...)`, commit, push, and halt with `BLOCKED: plan-fix-r{N} validate non-progress` — a distinct message from Step 1.5's own `plan-validate non-progress` halt, so the two failure sites are distinguishable in status.md history. Only after this full-validate gate passes clean does 4b/4d proceed into its existing convergence-gate / commit / Handoff logic.
- Rationale: This is exactly what #981 requests ("4b/4d re-run the same `_plan_validate.run` call Phase: Plan uses"), and it reuses Step 1.5's already-established two-pass-then-halt shape rather than inventing new failure semantics.
- Rejected: Narrowing the re-run to specific check classes (risks missing an unanticipated category — the exact failure mode #981 reports); hard-halting on any new finding with no fix-retry (would make trivial, mechanically-fixable NIT-introduced errors — e.g. a missing `Context:` entry — halt the whole task instead of self-correcting, when the fix table already knows how to handle them).

### #970 — operator-raised round-cap override (live, mid-loop)

- Decision: Document that at any point during an actively-running Phase: Plan Review loop, an operator may give the orchestrator a live, natural-language instruction to raise or extend the round cap (e.g. "raise the cap to N", "allow one more round"). On receiving such an instruction, the orchestrator binds a session-local `operator_max_review_rounds = N` and substitutes it for `max_review_rounds` at every site the existing "Resumed-loop round-cap substitution" paragraph already enumerates (loop-length cap, the step 1 round-report line, the Convergence gate's `round >= / < max_review_rounds` bullets, every 4a/4b/4c inline restatement, step 6's `{N} rounds` message) for the remainder of the run, and threads `--max-rounds <operator_max_review_rounds>` into every subsequent prepare/finalize CLI invocation (both Agent-mode `<args>` and the subprocess branch), exactly mirroring the existing blocked-resume threading pattern but without the `revise_from_blocked` gate. `mill-config.yaml` is never edited — the override is per-run only, exactly as blocked-resume's `local_max_review_rounds` already behaves.
- Rationale: mill-plan is autonomous and has no pause point to receive a CLI flag mid-run, so a stop-and-reinvoke design doesn't fit #970's actual reported scenario ("operator raised the cap ... mid-loop"). A live in-session instruction is also exactly how this task's own mill-start discussion phase is being conducted right now.
- Rejected: Requiring the operator to stop mill-plan and re-invoke with a new top-level `--max-rounds N` flag — doesn't address the mid-loop case the issue describes, and would need a second, separate CLI-flag design just for this.

### #970 — precedence between the live operator override and blocked-resume's `local_max_review_rounds`

- Decision: The live operator-raised override is permitted at any time, including while a blocked-resume loop (which already substitutes its own `local_max_review_rounds` for `max_review_rounds`) is active. Once the operator gives a live round-cap-raise instruction, `operator_max_review_rounds` becomes the single active override for the remainder of the run and supersedes whatever value was substituted before it — whether that was the bare config `max_review_rounds` or blocked-resume's `local_max_review_rounds` — at every site "Resumed-loop round-cap substitution" already enumerates. The operator instruction always wins because it is strictly the most recent and most explicit signal; there is no scenario where reverting to an older, lower-precedence cap after a live raise is correct. If the operator later raises the cap again, the new value simply replaces the prior `operator_max_review_rounds` the same way.
- Rationale: This was flagged as a BLOCKING gap by discussion-review round 1 — the original #970 decision left it undefined whether the two override mechanisms compose, conflict, or one takes precedence, and whether a live raise is even permitted mid-blocked-resume. A single "most-recent-wins" rule resolves all three questions with one sentence and requires no new state beyond the two variables already introduced.
- Rejected: Requiring the two overrides to be summed or otherwise combined — no scenario justifies a compound cap, and it would make the effective round count harder to reason about than either override alone. Declaring the live-raise instruction inapplicable during blocked-resume — rejected because it would leave the operator no way to extend a blocked-resume run that itself turns out to need more rounds, forcing another full `blocked` → `--revise` cycle for no reason.

- Decision: Also document a live "waive remaining BLOCKINGs at cap" instruction, distinct from but adjacent to the round-cap-raise instruction above. If the operator gives this instruction, the *next* time step 6's max-rounds-escape trigger condition would otherwise fire, treat it as an implicit-approve-at-cap instead of a halt: set `approved: true`, using the same `" (min_rounds not satisfied by round cap)"`-style commit-message-suffix convention already used elsewhere in this phase for cap-driven implicit approvals (adapted wording, e.g. `" (operator waived remaining BLOCKINGs at round cap)"`), and proceed straight to Handoff.
- Rationale: #970 explicitly flags this as a natural follow-on request with "no documented disposition today" — resolving it alongside the round-cap-raise mechanism avoids a near-identical follow-up bug report.
- Rejected: Leaving step 6 unconditional and requiring the post-halt `--approve` flag (#948) for every such case — correct as a fallback, but costs a guaranteed extra round-trip (one more prepare/finalize cycle) for a case the operator could resolve live.

### #948 — post-max-rounds `--approve` operator path

- Decision: Add `--approve` to Step 0.5's argument-parsing token walk, mutually exclusive with `--revise` (halt with a usage error if both tokens appear in `$ARGUMENTS`). Add a new Entry pre-check (parallel in shape to the existing `--revise` pre-check, but its own separate branch — not folded into the `--revise` pre-check's conditions): valid only when `phase == "blocked"` **and** `blocked_reason` starts with `"max-rounds exhausted"` (read via the same `_status.read_full(status_path)["yaml"]` pattern the existing "Entry: resuming after a max-rounds block" section already uses); halt with an explicit message if `phase` is not `blocked` or `blocked_reason` doesn't match that prefix (naming the actual phase/reason and stating `--approve` only applies to a max-rounds-exhausted block); also halt (defensively, even though the state should already guarantee this) if `plan/00-overview.md`'s `approved:` field somehow already reads `true`. On the valid path: flip `approved: true` in `00-overview.md`'s frontmatter via the same direct-Edit convention used for that field elsewhere in this file, commit **alone** (not combined with any other pending mutation) with a message recording it as an explicit operator override — e.g. `mill-plan: --approve operator override for {slug} (max-rounds exhausted, outstanding findings accepted by operator)` — push, then fall through directly into Phase: Handoff unmodified (its own guard re-reads `approved:`, now `true`, passes, and it appends the `"planned"` phase / commits / reports exactly as it does for a normally-converged plan).
- Rationale: Matches #948's own suggested design essentially verbatim, and reuses the `--revise` pre-check's established fall-through shape (flip a field, commit, fall through into the next phase) rather than inventing a new control-flow pattern.
- Rejected: None seriously considered — the issue's proposed shape was already well-formed and consistent with existing conventions in this file.

## Technical context

- `plugins/mill/skills/mill-plan/SKILL.md` is the sole file to edit. Relevant existing sections/line numbers (task-worktree copy, not plugin cache — may drift slightly once earlier edits in this same task shift line numbers, but section headings are unique anchors):
  - Step 0.5 (argument parsing) — `--revise` handling, ~line 20-30.
  - Entry step 4's phase-table and the `--revise` pre-check — ~line 53-70.
  - "Entry: resuming after a max-rounds block" — ~line 108-129 (existing `blocked_reason.startswith("max-rounds exhausted")` check to mirror for `--approve`'s guard).
  - Phase: Plan's own self-validate call (`_plan_validate.run` with 7 kwargs) — ~line 259-271 — the exact call shape to replicate in 4b/4d.
  - "`--max-rounds` threading for blocked-resume (`revise_from_blocked` only)" — ~line 305 — the exact pattern to generalize for the live operator-raised case.
  - "Resumed-loop round-cap substitution" — ~line 323 — enumerates every site a round-cap override must be substituted at; the new operator-raised override reuses this same enumeration.
  - Steps 4a/4b/4c/4d and the Convergence gate — ~line 387-570 — where 4b (~522-533) and 4d (~544-553) get the new full-validate call, and where the "implicit-approve-at-cap" commit-message-suffix convention (already used for `" (min_rounds not satisfied by round cap)"`) is extended for the step-6-waive case.
  - Step 1.5's mechanical-fix table — ~line 344-374 — reused unchanged by 4b/4d's new full-validate call; no new table needed.
  - Phase: Handoff — ~line 572-588 — the fall-through target for `--approve`, unmodified.
- `_plan_validate.run` signature (`_plan_validate.py:2872`): `run(plan_dir, project_root, *, root=None, wiki_root=None, git_root=None, skip_checks=frozenset(), max_cards_per_batch=10, max_batch_context_tokens=120000, parent_branch=None) -> list[dict]`. Returns a list of error dicts (empty list = clean), never raises.
- `_plan_dag.validate(batches, batch_files) -> None` (`_plan_dag.py:647`) raises `PlanDAGError` on failure; this is the check already run (unchanged) in 4b/4d today.
- `millpy-review-plan.py` already has working `--max-rounds` (line 59) and `--skip-check` (line 87, `dest="skip_checks"`, repeatable) CLI flags — no script changes needed for either #970 or the already-resolved #934/#913.
- No `_codeguide/Overview.md` exists to navigate from; exploration was done directly against `plugins/mill/skills/mill-plan/SKILL.md` and its cited scripts in the task worktree.

## Constraints

No `CONSTRAINTS.md` present at the hub root.

## Testing

- This task is a SKILL.md prose/instructions change only — no Python source changes, so no new unit tests are needed for `_plan_validate.py`, `_plan_dag.py`, or `millpy-review-plan.py` (their public signatures/behavior are unchanged; existing tests in `plugins/mill/unit_tests/` remain the regression safety net and should still pass, run via `run-all.py` as a sanity check since the task edits a file none of them directly parses).
- The real "test" for this task is internal consistency of the new SKILL.md text: the `--approve`/`--revise` mutual-exclusion halt is stated in exactly one place (Step 0.5) and referenced consistently; the new 4b/4d full-validate call's kwargs match Phase: Plan's self-validate call verbatim; the "Resumed-loop round-cap substitution" enumeration is either reused as-is or explicitly extended (not silently diverged) for the new live-operator-override case; every new cross-reference (e.g. "mirrors the existing blocked-resume threading pattern") resolves to text that still says what it's claimed to say after the edit.
- No TDD candidates in the traditional sense; mill-plan (the plan-writer) should still identify concrete plan cards that let mill-go's own SKILL.md-consistency conventions (if any exist) or a manual read-through catch inconsistencies — mill-plan's own job to detail.

## Q&A log

- **Q:** How should #934/#913 (skip-check threading) be treated, given investigation shows they're already fixed on `main`? **A:** [auto-pick] Drop from active scope; discussion.md records an "already resolved" note citing the exact lines/commits. **Why:** verification already thorough across every dispatch site; redoing settled work wastes the plan budget, and mill-start doesn't touch GitHub issue state.
- **Q:** Does this task need any Python changes? **A:** [auto-pick] No — SKILL.md-only; `_plan_validate.run`'s 7-kwarg signature and `millpy-review-plan.py`'s `--max-rounds`/`--skip-check` flags already exist. **Why:** confirmed by reading the actual function signatures and argparse definitions.
- **Q:** What should 4b/4d's re-validation become for #981? **A:** [auto-pick] Add the full `_plan_validate.run` call (same 7 kwargs as Phase: Plan's self-validate) in addition to the existing DAG-only check, with mechanical-fix-then-retry-once-then-halt semantics mirroring Step 1.5. **Why:** matches #981's literal ask; reuses an already-established failure-handling shape instead of a new one.
- **Q:** How should an operator raise the round cap mid-loop (#970)? **A:** [auto-pick] A live, natural-language, in-session instruction binds a session-local `operator_max_review_rounds` override, threaded through every subsequent prepare/finalize call and every "Resumed-loop round-cap substitution" site, never written to config. **Why:** mill-plan has no pause point to receive a CLI flag mid-run; the issue's own scenario is explicitly "mid-loop".
- **Q:** Should the operator also be able to waive step 6's max-rounds block live? **A:** [auto-pick] Yes — a distinct live instruction that converts the next step-6 trigger into an implicit-approve-at-cap. **Why:** #970 flags this as an explicit, currently-undocumented follow-on.
- **Q:** [Round 1 review, BLOCKING] Which override wins if the operator live-raises the cap while a blocked-resume loop's own `local_max_review_rounds` is already active? **A:** [auto-pick] The live operator override always wins and supersedes whatever was substituted before it, for the remainder of the run; a live raise is permitted at any time including mid-blocked-resume. **Why:** most-recent-explicit-signal wins is the simplest rule that resolves precedence without introducing compound-cap state; forbidding it mid-blocked-resume would force an unnecessary full `blocked` → `--revise` cycle instead.
- **Q:** What shape should the post-halt approval path take for #948? **A:** [auto-pick] `/mill-plan --approve`, mutually exclusive with `--revise`, narrow guard (phase must be `blocked` with a `max-rounds exhausted` reason; refuse otherwise or if already approved), flips `approved: true`, commits as an explicit operator-override record, falls through to unmodified Handoff. **Why:** matches the issue's own proposed design; reuses the existing `--revise` pre-check's fall-through pattern.
