# Batch: mill-plan-skill-round-cap-and-skip-check-fixes

```yaml
task: "mill-plan: review-round cap and skip-check threading bugs"
batch: "mill-plan-skill-round-cap-and-skip-check-fixes"
number: 1
cards: 8
verify: null
depends-on: []
```

## Batch Scope

This batch edits `plugins/mill/skills/mill-plan/SKILL.md` only, closing three real gaps in Phase: Plan Review (`#981`, `#970`, `#948`) that discussion identified as still unresolved on `main`. It is one batch because it is one file with tightly interdependent edits (an operator-approval flag, a live round-cap override, and a validator re-run) that a single Sonnet session can hold in its head while implementing. There is no runnable surface — this is a documentation/orchestration-instructions change, not a code change, so `verify: null` (see Batch Tests below).

## Cards

### Card 1: Add `--approve` argument to Step 0.5

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the frontmatter, change `argument-hint: "[--revise]"` to `argument-hint: "[--revise|--approve]"`. In **Step 0.5 — Parse arguments**, add a new bullet immediately after the existing `- \`--revise\` — set a local \`revise_requested = True\`. May appear at most once.` bullet: `- \`--approve\` — set a local \`approve_requested = True\`. May appear at most once. Halt with a usage error if both \`--revise\` and \`--approve\` appear anywhere in \`$ARGUMENTS\` — the two are mutually exclusive.` Change the usage-hint block's `> usage: \`/mill-plan [--revise]\`` line to `> usage: \`/mill-plan [--revise|--approve]\``. Do not touch the "Step 0.5 does tokenization only" paragraph below the usage hint — it already correctly defers all `phase:`/`approved:` validation to Entry step 4, which Card 2 extends.
- **Commit:** `docs(mill-plan): add --approve argument to Step 0.5 argument parsing`

### Card 2: Add `--approve` Entry pre-check

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In Entry step 4, immediately after the existing `--revise` pre-check block ends (the bullet beginning "When `revise_requested` is not set, skip this entire pre-check and fall through to the existing table exactly as it is today.") and before the `| state | action |` table, insert a new `**`--approve` pre-check.**` block, structurally parallel to the `--revise` pre-check above it: state that it runs whenever `approve_requested` is set (from Card 1's Step 0.5 addition), that it is mutually exclusive with the `--revise` pre-check by construction (Step 0.5 already halts if both tokens appear), and that it reads `phase = _status.read_full(status_path)["yaml"].get("phase")` and `blocked_reason = _status.read_full(status_path)["yaml"].get("blocked_reason")` using the same `_status.read_full` call the `--revise` pre-check already uses. Then branch: (a) if **both** `phase == "blocked"` **and** `blocked_reason` starts with `"max-rounds exhausted"`: first parse `plan/00-overview.md`'s fenced-yaml frontmatter via the existing extraction pattern already used elsewhere in this file for the `approved:` field, and halt with an explicit message if `approved:` already reads the literal boolean `true` (a defensive guard — this state should not occur while `phase: blocked`, checked before any mutation); otherwise flip `approved: true` in `plan/00-overview.md`'s frontmatter via the same direct-`Edit` convention used elsewhere in this file for that field, commit **alone** on the task branch (`git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "mill-plan: --approve operator override for {slug} (max-rounds exhausted, outstanding findings accepted by operator)"`), push, then fall through directly into Phase: Handoff unmodified (its own guard re-reads `approved:`, now `true`, passes, and it appends the `"planned"` phase, commits, and reports exactly as it does for a normally-converged plan); (b) if `approve_requested` is set but condition (a) is not met (`phase` is not `"blocked"`, or `blocked_reason` does not start with `"max-rounds exhausted"`): halt with an explicit message naming the current `phase:`/`blocked_reason` and stating that `--approve` only applies to a plan blocked on max-rounds exhaustion; (c) when `approve_requested` is not set, skip this pre-check entirely and fall through to the table exactly as today. Then edit the table's `| phase: blocked | ... |` row text in two places: first, its action text — change "surface `blocked_reason` from status.md and tell the operator to re-run `/mill-plan --revise` to resume plan review (or resolve manually); halt." to "surface `blocked_reason` from status.md and tell the operator to re-run `/mill-plan --revise` to resume plan review, or (when `blocked_reason` starts with `\"max-rounds exhausted\"`) `/mill-plan --approve` to accept the plan as-is without another review round, or resolve manually; halt." — second, its trailing citation sentence — change "This row is reached only when `--revise` was NOT passed — the `--revise` pre-check above already intercepts the `phase: blocked` case when `--revise` is set." to "This row is reached only when neither `--revise` nor `--approve` was passed — the `--revise` pre-check intercepts `phase: blocked` when `--revise` is set, and the `--approve` pre-check above intercepts it when `--approve` is set."
- **Commit:** `feat(mill-plan): add --approve operator path for post-max-rounds approval (#948)`

### Card 3: Full-validate re-run in step 4b

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In Phase: Plan Review's step 4b, immediately after the existing sentence ending "`signature: _plan_dag.validate(batches: list[dict], batch_files: list[str]) -> None`" and before the sentence "This NIT-fix work, fixer report, and DAG re-validation happen regardless of `converged` — real work, safe either way.", insert a new sentence describing a full validator re-run: call `_plan_validate.run` with the identical 7 keyword arguments (`root`, `git_root`, `wiki_root`, `skip_checks=plan_skip_checks`, `parent_branch`, `max_cards_per_batch`, `max_batch_context_tokens`) that Phase: Plan's own self-validate call already uses (all already bound/resolvable at this point in Phase: Plan Review). If `_plan_validate.run` returns any errors, apply Step 1.5's existing mechanical-fix table (same table, same fix semantics — no new table) and re-run `_plan_validate.run` once more; if the second attempt still returns errors, call `_status.set_blocked(status_path, "plan-fix-r{N} validate non-progress", timestamp=_timestamp.now_utc_iso())`, commit on the task branch (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-plan: blocked (plan-fix-r{N} validate non-progress) for {slug}"`), push, and halt with `BLOCKED: plan-fix-r{N} validate non-progress` — a distinct message from Step 1.5's own `plan-validate non-progress` halt, so the two failure sites are distinguishable in status.md history. State explicitly that the mechanical fix applied on a first-attempt validator failure is NOT given its own interim commit (unlike Step 1.5's own CLI-driven cycle, which commits the mechanical fix separately before re-running the CLI) — it folds into 4b's own single terminal commit alongside the NIT fixes already described, since both are real work produced in the same round before that round's one commit; only the second-attempt failure path gets its own dedicated commit, via the `_status.set_blocked` halt already described. State that only after this full-validate gate passes clean does 4b proceed into the Convergence gate / commit / Handoff logic that follows. Reword the following sentence "This NIT-fix work, fixer report, and DAG re-validation happen regardless of `converged` — real work, safe either way." to "This NIT-fix work, fixer report, DAG re-validation, and full-validate gate happen regardless of `converged` — real work, safe either way." Do not change 4a, 4c, or 4d in this card.
- **Commit:** `fix(mill-plan): re-run full _plan_validate gate in step 4b's fix pass (#981)`

### Card 4: Full-validate re-run in step 4d

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In Phase: Plan Review's step 4d, insert a new bulleted item immediately after the existing bullet ending "`signature: _plan_dag.validate(batches: list[dict], batch_files: list[str]) -> None`" and before the bullet `- `_status.append_phase(status_path, f"plan-fix-r{N}", iso_ts)`.`: a bullet stating that 4d runs the identical full-validate gate Card 3 added to step 4b — call `_plan_validate.run` with the same 7 kwargs, apply Step 1.5's mechanical-fix table and retry once on error, and on a second consecutive failure call `_status.set_blocked(status_path, "plan-fix-r{N} validate non-progress", timestamp=_timestamp.now_utc_iso())`, commit, push, and halt with `BLOCKED: plan-fix-r{N} validate non-progress`, exactly as step 4b's own full-validate gate does — cross-reference step 4b rather than restating the full mechanics a second time. State that only after this gate passes clean does 4d proceed to the two bullets that follow (the `_status.append_phase` call and the commit). Do not change 4a, 4b, or 4c in this card.
- **Commit:** `fix(mill-plan): re-run full _plan_validate gate in step 4d's fix pass (#981)`

### Card 5: Live operator-raised round-cap override documentation

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In Phase: Plan Review, immediately after the existing paragraph beginning "**`--max-rounds` threading for blocked-resume (`revise_from_blocked` only).**" (ending "...more rounds than the loop's existing convergence/step-6 logic would otherwise allow.") and before the "**Tree-guard safeguard..." paragraph, insert one new paragraph headed "**Live operator-raised round-cap override.**". It documents that at any point during an actively-running Phase: Plan Review loop, the operator may give the orchestrator a live, natural-language instruction to raise or extend the round cap (e.g. "raise the cap to N", "allow one more round"); on receiving one, bind a session-local `operator_max_review_rounds = N` for the remainder of the run, never editing `mill-config.yaml`; once bound, `operator_max_review_rounds` becomes the single active round-cap override and supersedes whatever value was in effect before it (the bare config `max_review_rounds`, or blocked-resume's `local_max_review_rounds` if a blocked-resume loop was already active) at every site the "Resumed-loop round-cap substitution" paragraph enumerates, for the remainder of the run; every prepare/finalize CLI invocation dispatched from that point on — both the Agent-mode branch's `<args>` and the subprocess/psmux branch's `millpy-review-plan.py` invocation via `millpy-bg`, at every dispatch site in this phase including the Step 3.5 ERROR-only retry — must additionally pass `--max-rounds <operator_max_review_rounds>`, mirroring the blocked-resume paragraph's threading mechanics but for every remaining round rather than one; a later live raise simply replaces the prior `operator_max_review_rounds` value; a live raise is permitted at any time, including while a blocked-resume loop's own `local_max_review_rounds` is active, because the operator instruction is always the most recent and most explicit signal. Then, in the existing "**Resumed-loop round-cap substitution.**" paragraph, append one sentence after its final existing sentence ("...uses the unmodified config value everywhere, as always."): "If the operator later gives a live round-cap-raise instruction (see \"Live operator-raised round-cap override\" above) while this substitution is in effect, `operator_max_review_rounds` supersedes `local_max_review_rounds` at every one of these same sites for the remainder of the run." Do not add a step-6-waiver paragraph in this card — that is Card 6's independent addition, so the two instructions remain separately revertable.
- **Commit:** `feat(mill-plan): document live operator-raised round-cap override (#970)`

### Card 6: Live operator waiver of step 6 documentation

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In Phase: Plan Review, immediately after the "**Live operator-raised round-cap override.**" paragraph Card 5 adds and before the "**Tree-guard safeguard..." paragraph, insert one new paragraph headed "**Live operator waiver of step 6.**". It documents that the operator may separately give a live "waive remaining BLOCKINGs at cap" instruction; if given, the next time step 6's max-rounds-escape trigger condition would otherwise fire, treat it as an implicit-approve-at-cap instead of a halt — set overview frontmatter `approved: true` via direct Edit, commit on the task branch (`git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "mill-plan: approve plan for {slug} (operator waived remaining BLOCKINGs at round cap)"`), push, and proceed straight to Handoff, skipping step 6's `_status.set_blocked` halt for this occurrence; state this instruction is independent of the round-cap-raise override Card 5 added (an operator may raise the cap without waiving step 6, waive step 6 without raising the cap, or do both).
- **Commit:** `feat(mill-plan): document live operator waiver of step 6 (#970)`

### Card 7: Wire step 6's halt condition to the live waiver

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In Phase: Plan Review step 6 ("**Max-rounds escape**"), change the parenthetical condition "(only when round counter exhausts without APPROVE, BLOCKINGs still remain, AND non-progress did not fire)" to "(only when round counter exhausts without APPROVE, BLOCKINGs still remain, non-progress did not fire, AND the operator has not given a live step-6-waiver instruction — see \"Live operator waiver of step 6\" above; when that instruction was given, the implicit-approve-at-cap path documented there fires instead of this halt)". Do not change the rest of step 6's text (the `_status.set_blocked` call, the halt message, or the `{M}` explanation).
- **Commit:** `fix(mill-plan): make step 6's halt condition check the live waiver first (#970)`

### Card 8: Full-validate re-run in step 4c

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In Phase: Plan Review's step 4c ("On `REQUEST_CHANGES` AND `blocking_count == 0`"), immediately after the existing sentence "Apply NIT fixes per the `mill-receiving-review` Decision Tree (no different from a regular fix-pass), write the fixer report at `<reviews_dir>/<YYYYMMDD-HHMMSS>-plan-fix-r<N>.md` — this happens regardless of `converged`, real work either way." and before the sentence "Compute `converged` per the Convergence gate above (this branch is one of the gate's `APPROVE`-equivalent sites, per that section's opening sentence).", insert a new sentence: 4c runs the identical full-validate gate Cards 3/4 added to steps 4b/4d — call `_plan_validate.run` with the same 7 kwargs (`root`, `git_root`, `wiki_root`, `skip_checks=plan_skip_checks`, `parent_branch`, `max_cards_per_batch`, `max_batch_context_tokens`), apply Step 1.5's mechanical-fix table and retry once on error, and on a second consecutive failure call `_status.set_blocked(status_path, "plan-fix-r{N} validate non-progress", timestamp=_timestamp.now_utc_iso())`, commit on the task branch (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-plan: blocked (plan-fix-r{N} validate non-progress) for {slug}"`), push, and halt with `BLOCKED: plan-fix-r{N} validate non-progress`, exactly as step 4b's own full-validate gate does — cross-reference step 4b rather than restating the full mechanics a second time. State that only after this gate passes clean does 4c proceed into the Convergence gate check that follows. Do not change 4a, 4b, or 4d in this card.
- **Commit:** `fix(mill-plan): re-run full _plan_validate gate in step 4c's fix pass (#981)`

## Batch Tests

`verify: null` — this batch is a pure documentation/orchestration-instructions change to `plugins/mill/skills/mill-plan/SKILL.md`. No Python source, CLI argument parsing, or runtime behavior changes; every fix relies on capabilities `_plan_validate.run` and `millpy-review-plan.py` already expose. There is no runnable test surface for prose edits to a SKILL.md file, so no `verify:` command applies. Correctness is checked by mill-plan's own Phase: Plan self-validation (`_plan_dag.validate` + `_plan_validate.run`) before this plan is committed, and by holistic plan review during Phase: Plan Review.
