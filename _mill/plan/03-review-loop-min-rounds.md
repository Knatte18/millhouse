# Batch: review-loop-min-rounds

```yaml
task: '_review_common/_review_plan: verdict/count consistency and path-suppression gaps'
batch: review-loop-min-rounds
number: 3
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py
depends-on: []
```

## Batch Scope

Two additive, orthogonal changes to review-loop termination, applied uniformly to the 4 review-loop sites in the codebase (mill-start's discussion-review loop, mill-plan's single plan-review loop, mill-go's per-batch and holistic code-review loops): (1) a new optional `min_rounds` config floor per `roles.<role>.<scope>` — the loop may not terminate on `APPROVE` before this round; (2) a new termination predicate — a round terminates the loop only if its findings carry no entry with `demoted: true` (a field the JSON envelope already exposes, see `00-overview.md`'s `no-backend-change-for-798` Shared Decision). Per `#798`'s observed run, a single lucky round-1 ceiling demotion previously ended a 5-round-configured loop while 17 further findings (including a BLOCKING in every subsequent round) remained undiscovered. `min_rounds` is added only under `roles.plan-review.holistic` (not `roles.plan-review.batch`) — mill-plan's `SKILL.md` has no site that ever independently reaches SKILL-level termination logic for the batch scope (batch findings feed the same shared round counter mill-plan's holistic scope terminates), so a batch-scoped floor would never be consumed. Cards 9-10 add the config field (bootstrap-justified mid-flight `mill-config.yaml` mutation, see each card's Requirements); Cards 11-13 wire the convergence gate into the 4 loop sites across 3 `SKILL.md` files.

**Convergence gate (shared design, applied identically at every site below).** Read `min_rounds = cfg.get("roles", {}).get("<role>", {}).get("<scope>", {}).get("min_rounds", 1)` at the same place each file already reads its round cap. On any round whose envelope's top-level verdict is `APPROVE` (or, at mill-plan's Card 12 site only, also its `REQUEST_CHANGES`-with-`blocking_count == 0` step 4c — see that card), compute:

```
converged = (round >= min_rounds) and not any(f.get("demoted") for f in envelope["findings"])
```

`envelope["findings"]` is the top-level field every `millpy-review-*.py` CLI already prints (`ReviewResult.findings`, aggregated across every sub-review) — no backend change needed to read it.

**Exception — mill-plan's site only (Card 12).** `envelope["findings"]` is not safe to read directly at mill-plan's site: `_review_plan.py`'s `_scan_approved_batches` (called from `run()`) splices already-approved, carried-forward batches' own `findings` — which can carry a stale `demoted: true` marker written by an earlier round's ceiling, re-read verbatim off disk via `extract_findings` — into the same `reviews[]` list every round, and `aggregate_findings = [f for r in reviews for f in r.get("findings", [])]` folds those stale entries into the envelope's top-level `findings` unconditionally. If `plan-review.batch` is ever enabled, a demotion from an unrelated, already-approved batch would make `not any(f.get("demoted") for f in envelope["findings"])` permanently `False`, so the gate could never converge before the round cap forces the implicit-approve fallback, every round. At Card 12's site only, replace `envelope["findings"]` with a round-filtered variant: `current_round_findings = [f for r in envelope["reviews"] if r.get("round") == envelope["round"] for f in r.get("findings", [])]`, then `converged = (round >= min_rounds) and not any(f.get("demoted") for f in current_round_findings)`. This works because `_scan_approved_batches`' carryforward entries retain their own original approval round (`"round": n`, always < the current round once a fresh round has run), while every entry produced by the current round (freshly-reviewed batches plus the holistic scope) shares the current round number — and `envelope["round"]` is `_review_plan.run()`'s own `agg_round = max(r["round"] for r in reviews)`, i.e. the current round, so the filter cleanly excludes carryforward and keeps only this round's live findings. mill-start (Card 11) and mill-go (Card 13) have no carryforward concept at their single-scope-per-round loops, so they read `envelope["findings"]` directly, unfiltered, as specified below.

- `converged is True`: proceed exactly as today's terminal branch (no behavior change).
- `converged is False` AND the round cap has not yet been reached: still apply any `[NIT]` fixes the branch already describes (the fixes are real and safe to apply now), but do NOT execute the branch's terminal phase-transition / approve-commit / break-loop actions. Instead continue the loop to round N+1 exactly as the file's own next-round-continuation path already does — no operator gap-prompt (there are zero BLOCKING findings to present).
- `converged is False` AND the round cap HAS been reached (this is the last allowed round): treat as an implicit approval — run the branch's existing terminal actions exactly as if `converged` were `True`, but append a short note to that round's commit message (e.g. append `" (min_rounds/demoted-predicate not satisfied by round cap)"`) so the shortfall is auditable. This is the only case an unconverged round is allowed to terminate the loop — treating a zero-BLOCKING round as a hard block would strand the task on a condition nobody can act on.
- The gate only ever fires on a round that would otherwise terminate the loop with zero surviving BLOCKING findings. It never applies to a genuine `REQUEST_CHANGES` round with `blocking_count > 0` — those already continue (or exhaust) by existing logic, untouched.
- The gate is orthogonal to `mill-start --auto`'s `prev_blocking_titles`/`extension_used` non-progress-extension machinery — that machinery only reads BLOCKING-finding titles across `REQUEST_CHANGES` rounds; the convergence gate never reads or writes `prev_blocking_titles`/`extension_used`.

## Cards

### Card 9: Add `min_rounds` to the config template

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `roles:` block, insert `min_rounds: 1` immediately after each of these 4 `rounds:` lines (leave every other `rounds:` line, including `plan-review.batch`'s at line 151, untouched — no `min_rounds` under `plan-review.batch`, per the discussion's `review-loop-min-rounds-and-demoted-predicate` Decision):
  - line 138, `discussion-review.holistic.rounds: 4` → add `min_rounds: 1` after it, and above it add the doc comment (matching this file's existing inline-comment convention, e.g. the `blocking_classes` comment at lines 143-146): `# min_rounds -- floor: the review loop may not terminate on APPROVE before this round, regardless of verdict. Optional; defaults to 1 (today's unfloored behavior) when absent.`
  - line 155, `plan-review.holistic.rounds: 4` → add `min_rounds: 1` after it (no repeated comment — the field is now self-explanatory from the first occurrence).
  - line 165, `code-review.batch.rounds: 0` → add `min_rounds: 1` after it.
  - line 169, `code-review.holistic.rounds: 4` → add `min_rounds: 1` after it.

  **`mill-config.yaml` bootstrap justification (this card IS the bootstrap card for both Card 9 and Card 10's `wiki-config-mutation` validator check):** this is a key *addition* with default `1`, read via `.get("min_rounds", 1)` at every consuming site (Cards 11-13, shipping in this same plan) — no existing code path reads or depends on the key's absence, so the field is inert to every session that has not yet picked up Cards 11-13's SKILL.md changes, and becomes live only once those land, in the same plan. Safe mid-flight for any concurrently-running mill-start/mill-plan/mill-go session on another task worktree sharing this hub's `mill-config.yaml`: an old (pre-this-plan) session's `.get("rounds", ...)`-style reads never inspect `min_rounds` and are unaffected by its presence.
- **Commit:** `feat(config): add roles.<role>.holistic/batch.min_rounds to hub-config template (#798)`

### Card 10: Add `min_rounds` to this hub's config

- **Context:** none
- **Edits:**
  - `mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Mirror Card 9's 4 insertions in this repo's own hub `mill-config.yaml` (no inline comments in this file — insert bare `min_rounds: 1` lines only, matching this file's terser existing style):
  - line 37, `discussion-review.holistic.rounds: 8` → add `min_rounds: 1` after it.
  - line 46, `plan-review.holistic.rounds: 7` → add `min_rounds: 1` after it.
  - line 51, `code-review.batch.rounds: 0` → add `min_rounds: 1` after it.
  - line 55, `code-review.holistic.rounds: 5` → add `min_rounds: 1` after it.

  Same bootstrap justification as Card 9 applies to this file (see Card 9's Requirements) — record it once for both files when applying the `wiki-config-mutation` validator skip.
- **Commit:** `feat(config): add roles.<role>.holistic/batch.min_rounds to hub mill-config.yaml (#798)`

### Card 11: Wire the convergence gate into mill-start's Discussion Review loop

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In Entry step 2 (line 73, which currently reads `Read roles.discussion-review.holistic.rounds as max_review_rounds.`), add reading `roles.discussion-review.holistic.min_rounds` into a new local `min_review_rounds` (default `1` when absent), alongside `max_review_rounds`. Insert the Batch Scope's convergence-gate paragraph (adapted with `role=discussion-review`, `scope=holistic`) as new prose in `### Phase: Discussion Review`, positioned after step 3.5 (ends ~line 317) and before step `4a.` (line 319). Apply the gate to both terminal branches:
  - **4a** (lines 319-322, APPROVE with zero NIT — "Break the loop and proceed to Handoff"): gate the break/Handoff on `converged`; when not converged and the round cap is not yet reached, continue to round N+1 instead (no fixer report needed — 4a has no NITs to fix).
  - **4b** (lines 324-335, APPROVE with NIT(s)): apply the NIT fixes and fixer-report write (per 4b's existing text) regardless of `converged` — real work, safe either way. Gate only the terminal actions — `_status.append_phase(status_path, "discussed", ...)`, the 4-pathspec commit, the Handoff completion report, and the loop break — on `converged`; when not converged and the round cap is not yet reached, still call `_status.append_phase(status_path, f"discussion-fix-r{N}", ...)` and commit the fix (the fix genuinely happened), but skip the `"discussed"` phase append and Handoff report, and continue to round N+1 instead of breaking.
  - Also apply the same conditional split to the `--auto` mode's on-`APPROVE` branch (lines 47-49 in the `## Auto mode` section, which currently states "If zero `[NIT]` findings: break the loop... If one or more `[NIT]` findings: take the interactive 4b path verbatim... then push and break loop per 4b") — reference the same `converged` gate rather than duplicating its definition a second time in that section; state explicitly there that the gate is orthogonal to `prev_blocking_titles`/`extension_used` (per the Batch Scope's last bullet).
  - The implicit-approve-at-cap fallback (Batch Scope's third bullet) uses this file's existing commit-message conventions for 4a's Handoff commit (at `### Phase: Handoff`, line 360) and 4b's own commit (line 327) — append the note to whichever of those two fires.
- **Commit:** `feat(mill-start): wire min_rounds + demoted-predicate convergence gate into Discussion Review (#798)`

### Card 12: Wire the convergence gate into mill-plan's Plan Review loop

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In Entry step 2 (currently reading `roles.plan-review.holistic.rounds` into `max_review_rounds`), add reading `roles.plan-review.holistic.min_rounds` into a new local `min_review_rounds` (default `1` when absent). Insert the Batch Scope's convergence-gate paragraph (adapted with `role=plan-review`, `scope=holistic`) as new prose in `### Phase: Plan Review`, positioned after Step 1.5 and before step `4a.` — including the Batch Scope's "Exception — mill-plan's site only" paragraph verbatim (the `current_round_findings` round-filter construction, NOT the plain `envelope["findings"]` read the other two sites use), since this is the one site where the plain read is unsafe (approved-batch carryforward via `_scan_approved_batches`). Apply the gate to THREE terminal branches (this file's loop has one more converged-termination path than mill-start's or mill-go's, per the Batch Scope's note that mill-plan's step 4c needs the same gate — this is the direct fix for the `#798`-observed scenario, where a ceiling-demoted BLOCKING in an otherwise-0-blocking-count round previously ended the loop prematurely):
  - **4a** (APPROVE, zero NIT): gate the break/Handoff-transition on `converged`; not-converged-and-cap-not-reached continues to round N+1.
  - **4b** (APPROVE with NIT(s)): apply NIT fixes and the fixer report regardless of `converged` (real work); gate only the terminal actions (`approved: true` Edit, the 4-pathspec commit, Handoff transition, loop break) on `converged`; not-converged-and-cap-not-reached still commits the NIT fixes (drop the `approved: true` flip and the loop-break/Handoff step for this round) and continues to round N+1.
  - **4c** (`REQUEST_CHANGES` AND `blocking_count == 0`): this branch's own existing rationale ("0-BLOCKING means converged; further rounds only churn cosmetic NITs. Do NOT run round N+1.") is exactly the premature-termination case `#798` observed — gate it the same way as 4b (apply NIT fixes unconditionally, gate the `approved: true` flip / commit / Handoff / break on `converged`).
  - Do NOT apply the gate to step 4d (`REQUEST_CHANGES` AND `blocking_count > 0`) or step 6 (max-rounds escape with BLOCKINGs remaining) — those already continue/hard-block by existing logic and are orthogonal to a zero-BLOCKING convergence question.
  - The implicit-approve-at-cap fallback appends its note to whichever of 4a/4b/4c's existing commit message fires when the round cap is reached without convergence.
- **Commit:** `feat(mill-plan): wire min_rounds + demoted-predicate convergence gate into Plan Review, incl. step 4c (#798)`

### Card 13: Wire the convergence gate into mill-go's two code-review loops

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** This file has two independent loop sites; wire the gate into both, each reading its own scope's `min_rounds`.
  - **Per-batch loop** (`### 3. Code Review loop`, heading at line 637; round loop `for N from 1 to roles.code-review.batch.rounds` at line 645; Entry already reads `roles.code-review.batch.rounds` at line 45 — add `roles.code-review.batch.min_rounds` into a new local, default `1`). Apply the convergence gate (`role=code-review`, `scope=batch`) to the `APPROVE` branch (line 731 — "If `nit_count > 0`... dispatch one cold-start NIT-only fix pass... set batch state → `approved`... Commit... Break out of the loop → next batch."): the NIT-fix dispatch (if `nit_count > 0`) runs regardless of `converged` (real work); gate the terminal actions — `_status.append_phase(status_path, f"approved-{batch_name}", ...)`, the approve-commit, the per-batch cleanup block, and the loop break — on `converged`; not-converged-and-cap-not-reached continues to round N+1 (re-dispatch code review for this batch) instead. The rounds-exhausted branch (step 5, lines 817-820) is untouched — it only fires when verdict never reached `APPROVE` (BLOCKINGs remained the whole time), orthogonal to the convergence gate's implicit-approve-at-cap fallback (which lives inside the `APPROVE` branch itself, per the Batch Scope).
  - **Holistic loop** (`## Holistic code review`, heading at line 935; round loop `for H from 1 to max_holistic_rounds` at line 960; guard/read at lines 954-957 already computing `max_holistic_rounds` — add reading `roles.code-review.holistic.min_rounds` into a new local `min_holistic_rounds`, default `1`, alongside it). Apply the convergence gate (`role=code-review`, `scope=holistic`) to the `APPROVE` branch (line 1151 — same NIT-fix-then-approve shape as the per-batch branch, ending with `_status.append_phase(status_path, "holistic-approved", ...)`, the holistic approve-commit, the holistic cleanup block, and "Proceed to Handoff"): same split — NIT-fix dispatch runs regardless of `converged`; gate the terminal actions on `converged`; not-converged-and-cap-not-reached continues to round H+1 instead. The rounds-exhausted branch (step 7, lines 1200-1205) is untouched for the same orthogonality reason as the per-batch site.
  - Both sites' implicit-approve-at-cap fallback appends its note to that site's existing approve-commit message (the per-batch site's `"mill-go: approve batch {batch_name}"` or the holistic site's `"mill-go: holistic approve {slug}"`).
- **Commit:** `feat(mill-go): wire min_rounds + demoted-predicate convergence gate into per-batch and holistic code review (#798)`

## Batch Tests

`verify:` runs `test-review-common.py`... deliberately not chosen: no Python code changes in this batch (config YAML + `SKILL.md` prose only — per `00-overview.md`'s `no-backend-change-for-798` Shared Decision, `min_rounds`/the demoted-predicate are read via plain `.get()` at orchestrator level with no new Python helper). `test-config.py` is run instead as a sanity regression guard that `_config.load_config`'s deep-merge still parses both edited YAML files cleanly after the `min_rounds` insertions (Cards 9-10) — it does not and cannot assert anything about the new key itself, since `_config.py` has no schema-validation layer for `roles.*` (confirmed: zero `roles[` / `schema` grep hits in `_config.py`), consistent with `rounds`/`blocking_classes` having no dedicated validator either. Cards 11-13's `SKILL.md` prose changes are verified by careful review of the edited sections against `#798`'s observed-run table during Plan Review and Code Review, not by an automated test, per discussion.md's Testing section.
