# Discussion: mill-plan SKILL.md: Phase Plan Review gate, convergence, and DAG-validation correctness bugs

```yaml
task: mill-plan SKILL.md: Phase Plan Review gate, convergence, and DAG-validation correctness bugs
slug: mill-plan-review-round-and-gate-bugs
status: discussing
parent: main
```

## Problem

`mill-plan/SKILL.md` and its supporting scripts (`_plan_validate.py`, `_plan_dag.py`,
`millpy-review-plan.py`, and the shared `_phase_wait.py` / `mill-go-base/SKILL.md` Agent-mode
dispatch machinery) have accumulated 12 self-reported correctness bugs, all clustered around the
Phase: Plan Review review-round machinery: the pre-review validator gate, the convergence/round-cap
logic, the DAG re-validation calls, the entry-gate wait for upstream mill-start, and several
validator checks that are too narrow (Python-only, no cross-batch dependency awareness, no
gitignore awareness) or missing an escape hatch entirely.

Every issue traces to a real GitHub bug report filed via `/mill-self-report` during live mill-plan
runs on this or sibling repos (`loomyard`, `NORCE-DrillingAndWells/Models`). Because this repo
self-reports and self-fixes continuously, a pre-plan verification pass against the CURRENT
task-worktree source (not the plugin cache — see CLAUDE.md's source-verification rule) found that
**2 of the 12 are already fully fixed** and **2 are partially fixed** by prior unrelated work; the
remaining 8 are still open and need this task's plan.

**Why now:** these bugs surface mid-flight during real planning sessions (validator/reviewer
disagreements after a plan is already committed, wasted review rounds, TypeErrors during DAG
re-validation, false permanent halts on transient upstream state) — each one either wastes review
round budget or forces a manual operator recovery that the SKILL should handle autonomously.

## Scope

**In:**
- #902 — thread Phase: Plan's `skip_checks` into every Phase: Plan Review CLI dispatch (persisted via `00-overview.md` frontmatter).
- #896 — fix status.md Timeline undercounting plan-review rounds (4b/4c never append `plan-review-r{N}`).
- #895 — add a grace-window to the entry-gate wait's `blocked` handling in the shared `_phase_wait.py`, threaded into mill-plan's own call site.
- #890 — add missing `signature:` lines for `_plan_dag.validate` at Phase: Plan Review steps 4b and 4d.
- #887 — new `_plan_validate.py` check: cross-batch `Creates:` reference with no `depends-on` edge to the creating batch.
- #886 — convergence gate: drop the `demoted` predicate, rely solely on `blocking_count == 0`.
- #881 — generalize `_check_verify_full_suite` to a language-aware unbounded-verify heuristic (Go, C#, in addition to existing Python `run-all.py` detection).
- #877 — new Principles rule in `mill-plan/SKILL.md`: never require two separately-numbered cards to land in the same commit.
- #868 — extend `_check_non_existent_path` to soft-fail gitignored, not-yet-existing `Context:`-only refs via the reviewer's existing `soft_fail_gitignored` mechanism.
- #861 — add a "verify it currently passes clean" precondition to the Done-gate reminder, synced into the `mill-config.yaml` template comment.
- #901 — new documented skip-check paragraph + fix-table row for `out-of-worktree-target` (two-condition test, mirroring `wiki-config-mutation`).
- #888 — verify-only: confirm the already-shipped Agent-mode liveness-probe recovery (mill-go-base/SKILL.md step 3(c)) fully covers this issue; close with no code change.

**Out:**
- mill-start's discussion-review loop's own (worse) version of #896's Timeline-undercounting bug — same bug family, but out of scope for this mill-plan-titled task; file as a separate follow-up.
- mill-go-base's own copy of the #895 entry-gate-wait `blocked_grace_s` threading — the shared `_phase_wait.py` fix benefits it for free once adopted, but this task only threads the new parameter into mill-plan's call site. `blocked_grace_s` defaults to `0`, so mill-go-base's behavior is unchanged (no regression) until it's threaded there separately.
- Any change to `_plan_validate.py`'s `out-of-worktree-target` check logic itself (#901 Option B, config-driven authorized-roots) — rejected in favor of Option A (skip-check row, zero code change).
- Any change to the Handoff "Pre-done gate" step's baseline semantics (#861's rejected Option 3 — making `done_gate` baseline-aware for all commands) — the process-fix (verify-clean-first precondition) is sufficient; baseline-awareness is a "belt and suspenders" follow-up only if repeat incidents occur.
- Re-litigating any of `_plan_validate.py`'s other existing checks not named in one of the 12 source issues.

## Decisions

### #902 — persist skip_checks across the Phase: Plan / Phase: Plan Review boundary

- Decision: at Phase: Plan's commit (`mill-plan/SKILL.md` ~line 249-270, before the "Commit on the
  task branch" step at line 283), when `skip_checks` is non-empty, write it as a new `skip_checks:`
  list field in `00-overview.md`'s fenced-yaml frontmatter (parallel to the existing `approved:`
  field), via the same direct-`Edit` convention already used for `approved:`. At Phase: Plan
  Review's "Path Setup (Plan Review)" section, read it back as `plan_skip_checks` (empty list if
  absent, for pre-existing plans). Thread `plan_skip_checks` into **every** round's dispatch — both
  the Agent-mode `<args>` and the subprocess/psmux `millpy-bg` invocation, and the 4.5
  ERROR-only-aggregate retry's re-dispatch — as `--skip-check <name>` per entry, mirroring how
  `--reviews-subdir`/`--max-rounds` are already threaded for analogous per-round overrides. Update
  the Step 1.5 intro paragraph to clarify the reactive fix-table `--skip-check` rows now cover only
  a check that becomes newly true *during* Plan Review (e.g. an LLM fix-pass that itself edits
  `mill-config.yaml`), not the common case Phase: Plan already resolved.
- Rationale: root-cause fix — the justification is computed once (per the existing two-condition
  tests for `wiki-config-mutation`/`verify-full-suite`) and reused, rather than re-derived or
  reactively recovered after an already-committed plan fails a second, disagreeing gate.
- Rejected: re-deriving independently at Phase: Plan Review (risks the two condition-test copies
  drifting apart over time, and must be duplicated into the 4.5 retry path anyway); threading only
  on round 1 (a later LLM fix-pass in round 2+ could re-touch the flagged file and re-trigger the
  gap).

### #896 — unconditional per-round Timeline append

- Decision: move the `plan-review-r{N}` `_status.append_phase` call out of the verdict branches —
  but NOT immediately after step 2's dispatch returns. Step 4.5 (ERROR-only-aggregate retry) sits
  between step 2 and 4a-4d: on `error_kind: usage`, `verdict: ERROR`, or absent-JSON, the round is
  explicitly "not consumed" and 4a-4d are skipped for a same-N retry. Appending right after step 2
  would write a Timeline row for a round that produced no reviewable output, then write a second,
  duplicate `plan-review-r{N}` row when the retry actually resolves — the file's own Entry
  "resuming after a max-rounds block" section already documents exactly this hazard
  (`_status.append_phase` never dedupes). Instead, append the single unconditional
  `plan-review-r{N}` call immediately AFTER step 4.5's screening confirms the round is reviewable
  (i.e., after ruling out a usage error, an ERROR verdict, and absent-JSON — all of which retry
  without consuming the round) and BEFORE branching into 4a/4b/4c/4d. Remove the now-duplicate calls
  currently in 4a (line 469) and 4d (line 537).
- Rationale: collapses four independent call sites into one, still structurally preventing recurrence
  if a hypothetical 4e branch is ever added, while correctly excluding non-reviewable retried rounds
  from getting a premature or duplicate Timeline row. (The originally-cited precedent —
  `mill-go-base/holistic-review.md` appending its per-round marker unconditionally — does not
  actually match this placement: that file appends its marker BEFORE dispatch, every round, with no
  equivalent post-dispatch retry-screening step in its loop shape; it is not a precedent for "append
  after verdict is known," only for "append unconditionally somewhere in the loop." The design here
  stands on its own reasoning, not on that analogy.)
- Rejected: minimal patch (add the missing append only to 4b/4c at their existing sites) — cheaper
  diff, but keeps four independent call sites in sync going forward instead of one; scope decision
  above also rejects extending this fix to mill-start's own (worse, zero-branch) version of the same
  bug class.

### #895 — entry-gate wait grace window for transient `blocked`

- Decision: add a `blocked_grace_s: int = 0` parameter to `_phase_wait.build_wait_command()`
  (default `0` preserves exact current behavior for any caller that doesn't opt in — this is the
  mechanism that keeps mill-go-base's own call site unaffected per the Scope section above). Bash
  poll-loop change: on first observing `phase: blocked`, do not exit immediately — record
  `blocked_since` and continue polling. If `phase:` moves off `blocked` before the grace window
  elapses, clear `blocked_since` and resume normal polling. If still `blocked` once
  `elapsed - blocked_since >= blocked_grace_s`, echo `BLOCKED: <reason>` and exit 1 exactly as
  today. `READY` is checked first every iteration and always wins immediately, unaffected. Thread a
  new `blocked_grace_s` argument into mill-plan's own "Entry-gate wait for upstream mill-start" call
  site (`mill-plan/SKILL.md` line 86), sourced from a new config key `pipeline.entry_wait_blocked_grace_s`
  (default ~20s = 2x the existing 10s poll interval — comfortably wider than a single-poll
  coin-flip window, far short of the ~3-minute transient window in the reported repro). Add a
  template-comment line for `pipeline.entry_wait_blocked_grace_s` in
  `plugins/mill/templates/mill-config.yaml`, alongside its two existing siblings
  `entry_wait`/`entry_wait_timeout_minutes` (lines 127-128 today, both already have an inline
  explanatory comment) — per CLAUDE.md's "hub file and plugin template must stay in sync" rule,
  matching #861's own explicit template-sync step below.
- Rationale: only approach that satisfies both "tolerate a transient blocked window" and "still halt
  promptly and unconditionally for a genuinely persistent block" simultaneously. The default-0
  parameter design lets the shared script change ship without forcing mill-go-base's own copy of
  this wait pattern to change behavior in the same task. **The suggested ~20s default is
  intentionally conservative — it guards only against a single-poll coin-flip race, not the full
  ~2m41s window actually observed in the reported repro.** This hub's own `pipeline.entry_wait_blocked_grace_s`
  should therefore be configured explicitly larger than the ~20s baseline (e.g. 300s) if it wants to
  tolerate the specific mill-start convergence-gate transient the issue reports; the plan should not
  assume the bare 20s default alone closes that exact repro, and should either set a larger value in
  this hub's `mill-config.yaml`/`config.local.yaml` as part of the same batch, or explicitly document
  in the plan's Shared Decisions that the default is a conservative baseline only, with a pointer to
  raising the config value for hubs that need more coverage.
- Rejected: fixed re-check-once (simpler, no new parameter/state, but only guards a blocked window
  narrower than one poll interval — the actual reported repro's ~3-minute window would still
  false-halt under this option); never-exit-early-on-blocked (removes the fast-fail benefit for a
  genuinely stuck upstream task, overcorrects); threading the new parameter into mill-go-base's call
  site in this same task (rejected per the Scope section — out of scope, zero-regression follow-up).

### #890 — explicit `_plan_dag.validate` call shape at all three call sites

- Decision: at both `mill-plan/SKILL.md` line 477 (step 4b) and line 543 (step 4d), replace the bare
  `_plan_dag.validate` reference with the same explicit two-arg call shape already used and proven
  correct at line 235 (Phase: Plan's own "Self-validate the DAG" step): read `overview_text`, call
  `_plan_dag.extract_batch_index(overview_text)`, then
  `_plan_dag.validate(batches, sorted(p.name for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"))`,
  paired with `signature: _plan_dag.validate(batches: list[dict], batch_files: list[str]) -> None`.
- Rationale: mechanical, no design choice — this mirrors the file's own established convention
  (every other cited helper carries a `signature:` line) and reuses the exact expression already
  correct at line 235 rather than inventing new phrasing. No script changes needed.
- Rejected: n/a — single correct fix, answerable directly from the codebase.

### #888 — verify Agent-mode reviewer-stopped-without-output recovery is already fixed

- Decision: no code change. `mill-go-base/SKILL.md`'s "## Agent-mode dispatch" step 3(c) (lines
  321-340) already implements the exact recovery #888 requested: for a non-clean terminal reviewer
  notification, `test -f <output_path>` first (the #888 scenario — file absent — falls through to
  `TaskOutput`); if `TaskOutput` reports the agent no longer running, "proceed to the existing
  one-retry transient classification... and re-dispatch exactly as today" — happening entirely
  inside step 2's dispatch, before any round is consumed, matching #888's own suggested fix
  verbatim. The section is explicitly motivated by the same incident class (#587/#595).
  `mill-plan/SKILL.md`'s own "Agent-mode error recovery" note (lines 407-410) already documents the
  one-retry-then-subprocess-fallback contract this produces.
- Rationale: verified against current code; the fix already shipped as part of a prior, broader
  Agent-mode dispatch hardening pass.
- Rejected: n/a — closing as already-fixed, recorded here so the fixer/implementer doesn't
  re-investigate it.

### #887 — new validator check: cross-batch Creates: reference requires a depends-on edge

- Decision: add a new check `cross-batch-creates-no-depends-on` to `_plan_validate.py`.
  `_compute_transitive_ancestors(batches)` returns a dict keyed by batch `entry["name"]` (the
  human `<batch-name>` field from the Batch Index), NOT by file stem — `name` and the `NN-<slug>.md`
  file stem are distinct strings. So `batch_creates` MUST be keyed the same way, mirroring the exact
  `batch_name_to_path` bridging step `_check_parallel_modifies_overlap` already uses to go from
  name-keyed ancestors to stem-derived per-file parsing: build `batch_name_to_path: dict[str, Path]`
  by mapping each `entry["name"]` to its batch file (via the stem), then build
  `batch_creates: dict[str, set[str]] = {name: _parse_creates_only(path) for name, path in
  batch_name_to_path.items()}` — keyed by `entry["name"]`, not by stem. Build
  `ancestors = _compute_transitive_ancestors(batches)` (already defined and used by the existing
  `_check_parallel_modifies_overlap` check — reuse, don't reimplement; also reuse its
  `batch_name_to_path` construction rather than rederiving it). For each batch B (iterating
  `batch_name_to_path.items()` so B is always a name, matching `ancestors`' and `batch_creates`' key
  space), for each token in `_parse_context_only(path) | _parse_edits_only(path)`
  (Context: and Edits: refs ONLY — deliberately narrower than `_check_non_existent_path`'s own
  `general_refs`, which also includes B's own `Creates:` tokens and would incorrectly scan a batch's
  own deliverables against other batches' `creates` sets): if the token is in some OTHER
  batch C's `creates` set (C != B, both `entry["name"]` values) and C is not in `ancestors[B]`, emit
  an error dict naming the missing edge (reporting the batch's file stem, not its name, in the error
  dict's `batch` field, to match every other check's error-dict convention — resolve back via
  `batch_name_to_path[B].stem`). Wire into `run()` alongside `_check_non_existent_path` (same input
  shape). Add a
  Step 1.5 fix-table row mirroring `parallel-modifies-overlap`'s remedy shape: add the missing
  `depends-on` edge (both the per-batch file's frontmatter and the overview's Batch Index entry, per
  the existing `depends-on-batch-mismatch` discipline) if legitimate; halt if genuinely ambiguous.
- Rationale: the DAG machinery this check needs (`_compute_transitive_ancestors`, per-batch
  `Creates:` parsing) already exists in the same file for a structurally similar check — this closes
  a real gap where mill-go could schedule a dependent batch before its dependency, handing the
  implementer a cold start against files that don't exist yet.
- Rejected: n/a — no genuine design alternative surfaced; straightforward extension of existing
  machinery.

### #886 — convergence gate: drop the redundant `demoted` predicate

- Decision: in the "Convergence gate (min_rounds + demoted predicate)" section (`mill-plan/SKILL.md`
  lines 381-393), remove the `not any(f.get("demoted") for f in current_round_findings)` clause from
  the `converged` formula. At every 4a/4b/4c site (all of which are already gated on
  `blocking_count == 0` or zero-NIT/APPROVE by their own branch conditions), `converged = (round >=
  min_review_rounds)`.
- Rationale: the "Exception — mill-plan's site only" carve-out already added (filtering to
  `current_round_findings` to exclude stale carried-forward `demoted` markers from already-approved
  batches) solved the real problem that motivated adding the `demoted` predicate in the first place.
  With that fixed, the `demoted` check now only fires on a *live, current-round* ceiling demotion
  (e.g. a `consistency`-class finding when `blocking_classes` excludes it) — which, by the hub's own
  config, is not supposed to gate approval. Keeping the predicate means such a round can never
  converge early and always burns to `max_review_rounds` before the implicit-approve-at-cap fallback
  rescues it — not a deadlock (the round-cap always saves it), but a real, unnecessary token/round
  cost the issue's own repro observed (rounds 4 and 5 both hit this).
- Rejected: leave as-is (the round-cap escape hatch already prevents a true deadlock and is now
  clearly documented/auditable via the commit-message note) — rejected because it leaves a
  repeatable, avoidable cost every time a hub's `blocking_classes` config excludes a class the
  reviewer keeps raising, which is exactly the reported scenario, not a one-off.

### #881 — language-aware unbounded-verify guard

- Decision: generalize `_check_verify_full_suite` (`_plan_validate.py`) beyond its current
  Python-only `run-all.py`-without-`-k`/`--only` detection. Detect project language the same way
  mill-plan's own "Verify command shape" section already does for `verify-not-isolated`'s conditional
  enforcement — reuse `_plan_validate.py`'s existing `is_python_project` detection verbatim (line
  ~1986), which ORs **four** markers, not three: `pyproject.toml`, `setup.py`, `setup.cfg`, AND
  `plugins/mill/pyproject.toml` (a nested-plugin marker). This 4th marker is not optional to
  reproduce — this repo (`millhouse`) has no root-level `pyproject.toml`/`setup.py`/`setup.cfg` and
  is detected as a Python project *solely* via the nested `plugins/mill/pyproject.toml` marker, so a
  shared language-detection helper that drops it would misdetect this very self-hosted repo. (CLAUDE.md's
  own "Python/mill projects" language for the `PYTHONPATH=` verify-prefix rule has the same
  three-marker drift; out of scope to fix here, but the plan should not propagate the omission into
  new code.) Build or reuse a shared language-detection helper so both checks stay consistent. Add
  per-language unbounded-command
  heuristics: Go — `go test ./...` with no `-run <pattern>`; C#/.NET — `dotnet test <project>` with
  no `--filter`; Python — extend to bare `pytest`/`python -m pytest` with no `-k` and no explicit
  path, for parity outside the `run-all.py` wrapper. Keep the check name `verify-full-suite`
  unchanged (do not rename) so the existing skip-check flag, Step 1.5 fix-table row, and SKILL.md's
  "cross-cutting helper" justification prose continue to apply verbatim — only the *detection*
  widens, not the remedy contract.
- Rationale: strict widening of one existing check; the language-detection precedent and the
  skip-check/remedy plumbing already exist and are reused as-is.
- Rejected: n/a — no trade-off between approaches; this is a detection-coverage gap, not a design
  choice.

### #877 — ban cross-card "same commit" requirements

- Decision: add a new rule to `mill-plan/SKILL.md`'s "## Principles" section (alongside "Express
  renames as `Moves:` pairs" and "Card `Context:` is an allowlist"): a plan must never require two
  separately-numbered cards to land in the same commit. Each card produces its own commit at
  implementation time; once a card's commit is made and pushed, the harness's git-safety protocol
  (always create a new commit rather than amending a prior one, absent explicit operator
  instruction otherwise) forbids folding a later card's diff into it. If two changes are genuinely
  atomic, express them as a single card with one `Commit:` message, not two cards linked by a
  cross-card "same commit" instruction.
- Rationale: planning-discipline gap, not a code bug — confirmed no rule governing cross-card commit
  merging exists anywhere in the file today (grepped "same commit"/"amend"/"atomic": one incidental,
  unrelated "same commit" hit in the Entry-gate wait section describing phase-transition commit
  coupling, not cross-card commits; zero hits for "amend"/"atomic"). The confirmed one-commit-per-card
  execution convention (`mill-go-base/SKILL.md` line 871: "every per-card commit invokes the
  `git-commit` skill") combined with the harness's standing git-safety protocol against amending
  prior commits makes a cross-card same-commit instruction structurally unsatisfiable once the
  earlier card is committed.
- Rejected: a mechanical validator regex check flagging `\bsame commit\b` + a card-number reference
  in `Requirements:` — flagged as a nice-to-have only; the SKILL.md prose rule is the sufficient,
  minimum-viable fix, since this is fundamentally a planning-discipline gap the planner should never
  author in the first place, not a pattern that needs runtime detection.

### #868 — gitignore-aware Context: refs in the pre-review validator

- Decision: extend `_check_non_existent_path` (`_plan_validate.py`) to parse `Context:` refs
  separately from `Edits:`/`Creates:`/`Deletes:` refs (reusing the already-present
  `_parse_context_only` / `_parse_edits_only` / `_parse_creates_only` helpers). For the
  `Context:`-only subset, resolve missing paths via `_review_common.resolve_ref_paths(...,
  soft_fail_gitignored=True)` instead of the gitignore-blind `resolve_existing_paths`, catching the
  `ReviewError` it raises on a genuine (non-ignored) miss and converting that into today's
  `non-existent-path` error dict — so the error contract for a real problem is unchanged. Keep
  `Edits:`/`Creates:`/`Deletes:` resolution exactly as today (no gitignore leniency — those name
  files the batch produces or touches, a hard requirement). Update this check's docstring and the
  Step 1.5 fix-table's `non-existent-path` row to document the new Context:-only carve-out.
- Rationale: `_review_plan.py` (the LLM reviewer backend) already has and tests this exact leniency
  (`soft_fail_gitignored`, shipped for #733/#808) — the pre-review static validator gate, which runs
  BEFORE the reviewer and hard-blocks first, was simply never updated to match. Reusing the
  already-shipped, already-tested mechanism closes the gap at its actual source.
- Rejected: doc-only fix sanctioning the parent-directory-listing workaround in the fix table and
  telling the reviewer prompt not to NIT it — leaves a real directory-vs-file semantic hole (the
  directory doesn't actually name what's read) and doesn't fix the root cause (the validator still
  can't distinguish a gitignored runtime artefact from a genuine typo for any future similar case).

### #861 — Done-gate reminder: verify-clean-first precondition

- Decision: rewrite the "Done-gate reminder" section (`mill-plan/SKILL.md` lines 230-233) to require
  running the candidate lint/test command (e.g. `PYTHONPATH= <lint_cmd>` from `git_root`) against the
  current worktree tip *before* defaulting `done_gate` to it. If it exits 0, proceed as today
  (default `done_gate` to include it). If it does NOT exit 0 (pre-existing repo-wide debt), leave
  `done_gate: null` and record the finding in the plan's Shared Decisions instead of silently making
  every future task's Handoff gate depend on unrelated debt being fixed first. Sync the same
  precondition wording into `plugins/mill/templates/mill-config.yaml`'s `done_gate` comment (line
  122), per CLAUDE.md's "hub file and plugin template must stay in sync" convention.
- Rationale: confirmed the risk is real and unconditional — `mill-go-base/handoff.md`'s "Pre-done
  gate" step runs `done_gate` fresh at every task's done-marking time and blocks on any non-zero
  exit, with no baseline diffing. The separate `done_gate_baseline_preflight` mechanism doesn't help
  here — it exists only for self-capturing snapshot/regression suites with their own internal
  baseline concept, which a stateless lint command doesn't have.
- Rejected: making the Handoff "Pre-done gate" step itself baseline-aware for all `done_gate`
  commands (auto-capture at Prepare time, diff at Handoff) — closes the gap even for a carelessly-set
  `done_gate`, but is materially bigger scope (new persisted-baseline storage, new code paths in
  `_done_gate.py` and `handoff.md`) versus the cheap process-fix; flagged as a "belt and suspenders"
  follow-up only if repeat incidents occur despite the guidance fix.

### #901 — out-of-worktree-target skip-check (Option A)

- Decision: add a third documented skip-check paragraph to `mill-plan/SKILL.md`'s Phase: Plan
  (alongside the `wiki-config-mutation` and `verify-full-suite` paragraphs), mirroring
  `wiki-config-mutation`'s two-condition-test shape: (a) `discussion.md` contains an explicit
  statement recording the operator's cross-worktree authorization (naming the second
  worktree/repo path and the reason writes there are required); and (b) the second worktree is one
  the operator created/cloned specifically for this task (not an incidental absolute path into an
  unrelated system directory) — i.e. it's itself a git worktree under legitimate task control. If
  both hold, set `skip_checks = skip_checks | frozenset({"out-of-worktree-target"})` and record the
  justification in the plan commit message, exactly like the other two skip-checks. Update the
  Step 1.5 fix-table's `out-of-worktree-target` row to reference this new paragraph instead of "Halt
  — not auto-fixable."
- Rationale: `_plan_validate.py`'s generic `skip_checks` filter and the CLI's `--skip-check` flag
  already accept any check name unrestricted — confirmed the workaround already reported in #901
  works mechanically today with zero code change; the only missing piece is a documented
  justification test, matching the precedent the other two skip-checks already set.
- Rejected: Option B (a `mill-config.yaml` key naming authorized worktree roots, with
  `_check_out_of_worktree_target` resolving against a list instead of just `project_root`) — real
  schema/code surface for what the issue itself frames as a one-off, task-specific authorization;
  persisting it in the committed hub config also conflicts with the existing convention that ad-hoc
  config tweaks belong in gitignored `config.local.yaml`, not the committed hub file. Revisit only if
  repeat cross-worktree-authorized tasks make per-`--revise` re-justification a real friction point.

## Technical context

- `mill-plan/SKILL.md` is 624 lines; all line-number citations above are against the CURRENT
  task-worktree copy at `/home/knatte/Code/millhouse/wts/mill-plan-review-round-and-gate-bugs/plugins/mill/skills/mill-plan/SKILL.md`
  as of this discussion (commit `ee597d9a`) — re-verify line numbers at plan-writing time, since
  earlier batches in this same plan will shift later line numbers within the file.
- Key scripts: `plugins/mill/scripts/_plan_validate.py` (all the `_check_*` validator functions,
  `run()` wiring at ~line 2708, and `_compute_transitive_ancestors` at line 985), `plugins/mill/scripts/_plan_dag.py` (`validate`, `extract_batch_index`),
  `plugins/mill/scripts/millpy-review-plan.py` (CLI prepare/finalize
  stages, `--skip-check` argparse handling at lines ~86-93), `plugins/mill/scripts/_phase_wait.py`
  (`build_wait_command`, `matches_wait_trigger`), `plugins/mill/scripts/_review_common.py`
  (`resolve_ref_paths` with `soft_fail_gitignored`, `resolve_existing_paths` — gitignore-blind),
  `plugins/mill/scripts/_review_plan.py` (LLM reviewer backend; already calls `resolve_ref_paths`
  with `soft_fail_gitignored=True` for `Context:`-only refs).
  Also `plugins/mill/skills/mill-go-base/SKILL.md` ("## Agent-mode dispatch" step 3(c), the
  already-fixed #888 mechanism) and `plugins/mill/skills/mill-go-base/holistic-review.md` (the
  unconditional pre-dispatch phase-append pattern #896's fix should mirror).
- `_plan_validate.py` already has the parsing/graph helpers several fixes need:
  `_parse_context_only`, `_parse_edits_only`, `_parse_creates_only` (per-file token parsing),
  `_compute_transitive_ancestors(batches: list[dict]) -> dict[str, set[str]]` (already used by
  `_check_parallel_modifies_overlap`), `compute_creates_union(plan_dir)` (plan-wide union, used by
  `run()`).
- Regression test precedent for the #868 fix already exists and should be extended, not
  reinvented: `test-review-code-flow.py::test_context_only_gitignored_ref_soft_fails_prepare` and
  the equivalent scenario in `test-review-plan-flow.py` (~line 2546, citing #808) already cover the
  reviewer side of this exact leniency — mirror the same two-scenario shape (soft-fail on confirmed
  gitignore, hard-fail on a genuine non-ignored miss) for the new validator-side test.
- `_check_verify_full_suite`'s existing frontmatter parsing (`_plan_dag.parse_verify_field`,
  `_plan_dag._read_batch_frontmatter`) is the scaffold the #881 fix should extend, not replace.
- Unit tests for `_plan_validate.py` live in `plugins/mill/unit_tests/test-plan-validate.py` — any
  new/changed check needs corresponding test coverage there (see `mill:testing`/`python:python-testing`
  skills for conventions).
- The Step 1.5 fix table in `mill-plan/SKILL.md` is the single source of truth for validator-error
  remedies — every new check (#887) or widened check (#881) or new skip-check (#901) needs both the
  script-side change AND a corresponding fix-table row update in the same batch, since the two must
  stay in sync (a check with no fix-table row leaves the orchestrator with no documented remedy).

## Constraints

No `CONSTRAINTS.md` present at the hub root (checked via `_constraints.read_if_exists()` equivalent
directory listing — file absent).

- Per CLAUDE.md: `print()`/`_log()` output must stay ASCII-only.
- Per CLAUDE.md: `mill-config.yaml` hub file and plugin template must stay in sync — the #861 fix
  touches both.
- Per CLAUDE.md: verify commands for this Python project must start with the literal `PYTHONPATH=`
  prefix (empty value) per the existing `verify-not-isolated` convention — applies to every new
  batch's `verify:` field in the eventual plan.
- Never use `sed` in any generated batch card or fixer/implementer instruction.

## Testing

- **#902**: unit test on `millpy-review-plan.py`'s prepare-stage CLI-argument handling confirming
  `--skip-check` values threaded from a fixture `00-overview.md` frontmatter reach the underlying
  `_plan_validate.run` call; a SKILL.md-level behavior is not independently unit-testable, but the
  round-dispatch threading (Agent-mode `<args>`, subprocess `millpy-bg` invocation, 4.5 retry) should
  each get a fixture/mock-level check if the existing test suite has an analog for `--reviews-subdir`
  threading (mirror that test's shape).
- **#896**: no unit test — same hedge as #902 above. The 4a-4d verdict dispatch and the moved-out
  unconditional `plan-review-r{N}` append are entirely `mill-plan/SKILL.md` prose interpreted by the
  orchestrating LLM; no Python module implements this branching (`grep` for
  `plan-review-r|plan-fix-r` across `scripts/` hits only regex-constant/docstring references, e.g.
  `millpy-cleanup.py`'s cleanup-pattern list and `_status.py`'s docstring example — never the actual
  branch logic), so there is no code-level call site to assert against. If a future refactor extracts
  the round-append logic into a standalone, testable helper, add unit coverage then; until that
  extraction happens, this is verified by manual/reviewer inspection of the SKILL.md text only, same
  as #890's documentation-only fix below.
- **#895**: unit test for `_phase_wait.build_wait_command`'s new `blocked_grace_s` parameter — cover
  (a) `blocked_grace_s=0` behaves identically to today (immediate halt), (b) a `blocked` window
  shorter than the grace period followed by a phase change to something other than `blocked`
  resumes polling without halting, (c) a `blocked` window that persists past the grace period still
  halts with the same `BLOCKED: <reason>` message. This is the clearest TDD candidate in the whole
  batch — the bash-loop logic is precise and mechanically verifiable.
- **#890**: no test — documentation-only fix (SKILL.md prose), nothing to assert against at the
  script level (the script's actual signature is unchanged).
- **#888**: no test needed — verify-only, no code change.
- **#887**: unit test for the new `cross-batch-creates-no-depends-on` check — fixture plans covering
  (a) legitimate cross-batch Context: reference WITH a correct depends-on edge (no finding), (b) the
  same reference with the edge missing (finding fires), (c) the edge present but only as a transitive
  (not direct) ancestor via `_compute_transitive_ancestors` (no finding — transitivity honored).
- **#886**: unit test on the convergence-gate helper/formula (wherever `converged` is computed, once
  extracted or if already isolated in a testable helper) confirming a round with
  `blocking_count == 0` but a live ceiling-demoted NIT converges immediately (no round-cap wait) once
  `round >= min_review_rounds`.
- **#881**: unit tests per new language heuristic — Go `go test ./...` with/without `-run`, C#
  `dotnet test <project>` with/without `--filter`, extending the existing Python `run-all.py` test
  fixtures in `test-plan-validate.py` with sibling fixtures for the new languages.
- **#877**: no test — SKILL.md prose rule only, nothing to assert against mechanically (explicitly
  rejected the mechanical-regex-check alternative).
- **#868**: unit test extending `test-plan-validate.py`'s `non-existent-path` coverage — (a) a
  missing `Context:` ref confirmed gitignored soft-fails (no finding), (b) a missing `Context:` ref
  NOT gitignored still hard-fails (finding fires, unchanged), (c) a missing `Edits:`/`Creates:` ref
  that happens to be gitignored still hard-fails (no leniency outside Context:). Mirror the existing
  `test_context_only_gitignored_ref_soft_fails_prepare` test's fixture shape from the reviewer-side
  test suite.
- **#861**: no test — SKILL.md prose + template-comment sync only; the actual precondition-check
  behavior (run lint, check exit code) is something mill-plan performs live during planning, not a
  unit-testable code path.
- **#901**: no test — SKILL.md prose (new skip-check paragraph + fix-table row) only; the underlying
  `skip_checks` filter mechanism is generic and already covered by existing tests for the other two
  skip-checks.

## Q&A log

- **Q:** #902 — How should Phase: Plan's `skip_checks` reach Phase: Plan Review's CLI dispatch? **A:** [auto-pick] Persist as `skip_checks:` in `00-overview.md` frontmatter at Phase: Plan's commit; thread `--skip-check <name>` into every round's dispatch. **Why:** root-cause fix; reuses the existing `--reviews-subdir`/`--max-rounds` per-round-override threading pattern already established in this file.
- **Q:** #896 — How should mill-plan record every review round in status.md's Timeline? **A:** [auto-pick] Move the append out of the branches — append unconditionally right after the verdict is known, before branching on 4a/4b/4c/4d; remove the now-duplicate appends in 4a/4d. **Why:** collapses 4 independent call sites into 1, matches the pattern mill-go-base's holistic-review.md already uses for the identical problem shape.
- **Q:** #896 scope — Should this task's plan also fix mill-start's own (worse) version of the Timeline-undercounting bug? **A:** [auto-pick] Stay scoped to mill-plan only; file mill-start's gap as a separate follow-up. **Why:** every one of the 12 source issues is filed against mill-plan specifically; keeps this plan's batches cohesive.
- **Q:** #895 — How should the entry-gate wait tolerate a transient upstream `blocked`? **A:** [auto-pick] Add `blocked_grace_s` to `_phase_wait.build_wait_command()`; keep polling through a `blocked` window shorter than the grace period, only halt if still-blocked past it. **Why:** only approach satisfying both "tolerate transient" and "still halt promptly on a persistent block."
- **Q:** #895 scope — Should the new grace-window parameter also be threaded into mill-go-base's own entry-gate wait call site in this task? **A:** [auto-pick] Fix the shared script only; thread the parameter into mill-plan's call site only (default preserves mill-go-base's current behavior, zero regression). **Why:** consistent with the #896-scope decision; task is scoped to mill-plan.
- **Q:** #886 — Fix the convergence gate's redundant `demoted` predicate now, or accept the current documented round-cap-fallback behavior? **A:** [auto-pick] Fix — drop the `demoted` predicate, rely solely on `blocking_count == 0` as the convergence signal. **Why:** the `current_round_findings` filter already solved the real (stale-carryforward) problem; the `demoted` predicate is now redundant and blocks early convergence on findings that, per the hub's own `blocking_classes` config, aren't supposed to gate approval.
- **Q:** #868 — Extend the validator's gitignore-awareness to match the reviewer's existing leniency, or sanction a doc-only workaround? **A:** [auto-pick] Extend `_check_non_existent_path` to use the reviewer's existing `soft_fail_gitignored` mechanism for `Context:`-only refs. **Why:** reuses an already-shipped, already-tested mechanism and fixes the gap at its actual source (the validator gate, which runs first).
- **Q:** #901 — Skip-check row (Option A) or config-driven authorized-roots list (Option B) for `out-of-worktree-target`? **A:** [auto-pick] Option A — a third documented skip-check paragraph, zero `_plan_validate.py` code change. **Why:** matches the issue's own framing, no code change needed, and the generic `skip_checks` filter already accepts arbitrary check names today.
