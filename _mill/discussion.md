# Discussion: mill-go / mill-plan loop hardening

```yaml
task: mill-go / mill-plan loop hardening
slug: mill-orchestration-loop-hardening
status: discussing
parent: main
```

## Problem

The `#000 mill-orchestrator` redesign (Thread A/B split, planning-as-subagent) is a
long-shot rewrite. The current mill-plan -> mill-go orchestration loop has to stay
runnable until then. Eight review-loop bugs filed during recent autonomous runs make the
current pipeline brittle: holistic review files are lost at merge, code-review NITs are
silently dropped on APPROVE, crash-recovery can pick up stale review files, the overstep
guard false-positives on a concurrent operator commit, mill-plan emits oversized batches
that blow the implementer's context budget, the plan-review worker can exit without a JSON
line and strand the loop, and an implementer pointed at a home-dir target mis-reports a
permanent block as a transient one.

**Why now:** these surfaced in real runs (e.g. a batch with 27/38 cards stuck on "token
budget reached"; a rate-limit ERROR path that mis-dispatched the implementer with a null
review file). Each one forces operator intervention in a loop that is supposed to run
autonomously. Hardening them keeps the current pipeline usable for the months until #000
lands.

## Scope

**In:**

- **#360** — Code-review NITs on APPROVE: mill-go must apply NITs instead of silently
  dropping them.
- **#362 / #378** — Holistic code-review APPROVE commit must stage the review file (not
  just `status.md`), and the same gap is fixed in any sibling APPROVE path that has it
  (discussion-review at minimum).
- **#363** — Plan-time detection of out-of-worktree edit targets (e.g.
  `C:\Users\hanf\.claude\CLAUDE.md`).
- **#371** — mill-plan batch-sizing gate (card-count cap + context-size estimate).
- **#372** — mill-plan review worker exit-without-JSON: treat as ERROR-equivalent and
  guarantee a JSON envelope from the CLI.
- **#373** — Crash-recovery stale review-file desync after an ERROR-only retry.
- **#374** — Holistic overstep guard false-positive on a concurrent operator commit.

**Out:**

- The `#000 mill-orchestrator` redesign. This task hardens the *current* loop; it does not
  restructure it. No Thread A/B split, no planning-as-subagent.
- Pushing the Builder's own state commits (Prepare/Approve/blocked/done). The existing
  push policy (CLI commits push; Builder commits do not) is unchanged — see mill-go
  "Board discipline". Adding Builder push is explicitly a separate follow-up.
- Re-reviewing after a NIT-only fix pass. Following the established mill-plan precedent
  (4b), an applied NIT does not trigger a fresh review round.
- Discussion-review NIT/NOTE handling semantics. Only the *review-file commit* gap in the
  discussion-review APPROVE path is in scope (see #362/#378), not its decision logic.
- Any change to `pipeline.autonomous_mode` semantics or `--auto` mode behaviour.

## Decisions

### nits-on-approve (#360)

- Decision: Add an aggregated top-level `nit_count` to the code-review JSON envelope
  (`millpy-review-code.py`, computed via `parse_blocking_count(raw_output, severity="NIT")`
  summed across `reviews[]`). On `APPROVE` with `nit_count > 0`, the Builder dispatches one
  cold-start NIT-only fix pass (`millpy-fix.py` with the APPROVE'd review file) and then
  approves. No extra review round is consumed; the NIT fix is trusted (not re-reviewed).
- Rationale: The Builder is intentionally lean and never reads findings, so it cannot apply
  NITs itself. Surfacing only a count keeps the lean-Builder invariant intact while still
  acting on the NITs. This mirrors mill-plan's already-correct 4b path ("apply NITs, then
  approve, single commit, no new round").
- Rejected: (a) Requiring the reviewer to upgrade every NIT to BLOCKING before APPROVE --
  defeats the purpose of the NIT severity and churns the loop. (b) Having the Builder read
  the findings inline -- breaks the lean-Builder invariant that lets Opus be the Builder.

### overstep-concurrent-commit (#374)

- Decision: `worktree_snapshot_guard` in `_review_common.py` flags overstep only when (a)
  the working tree is dirtied during the window (porcelain delta, filtered by
  `expected_paths` as today), OR (b) `after_sha` is NOT a descendant of `before_sha` (a
  history rewrite / reset). A plain fast-forward advance of HEAD (a concurrent operator
  commit on top of the reviewed commit) is allowed and emits a logged warning instead of
  raising `ReviewerOverstepError`.
- Rationale: A reviewer is a read-only role; the realistic overstep risks are file edits
  (caught by the porcelain check) and destructive history rewrites (caught by the
  non-descendant check). A benign operator commit during the review window is a
  fast-forward descendant and should not abort the run. Ancestry is checked via a pygit2
  ancestry test (`before_sha` is an ancestor of `after_sha`).
- Rejected: (a) Recording the implementer's commit SHAs and diffing the new-commit set
  against that list (the literal proposal wording) -- more state to thread through, and the
  descendant test captures the same intent more simply. (b) Dropping HEAD-SHA checking
  entirely -- would let a reviewer that rewrites history slip through undetected.

### crash-recovery-freshness (#373)

- Decision: The crash-recovery review-file probe (per-batch
  `*-code-review-{batch_name}-r{N}.md` in mill-go Execute step 3.1, and holistic
  `*-code-review-r{H}.md` in Holistic step 1 branch (a)) validates freshness: a candidate
  file counts only if its mtime is newer than the timestamp of the round's phase-entry row
  recorded in `status.md` (`reviewing-{batch_name}-r{N}` / `holistic-reviewing` for the
  current round). A stale file (mtime older than that timestamp) is ignored and the CLI is
  re-fired. ERROR-only retries continue to NOT consume the round counter.
- Rationale: ERROR retries deliberately do not consume the round, so the H/N counter and
  the on-disk file round-number can desync. Validating mtime against the recorded
  phase-entry timestamp distinguishes a fresh review from a stale pre-retry artifact without
  burning real review budget.
- Rejected: Making ERROR-only retries consume the round counter -- simpler, keeps counters
  in sync, but each transient ERROR (e.g. a rate-limit) would burn a real review round,
  shrinking the effective review budget.

### batch-sizing-gate (#371)

- Decision: Add a `_plan_validate` check `batch-oversized` combining (a) a hard card-count
  cap (default **10** cards per batch) and (b) a context-size estimate -- sum the byte size
  of every file in each card's `Context:` + `Edits:` + `Creates:`, take the per-batch union,
  divide bytes by 4 to estimate tokens, and flag if the union exceeds the budget (default
  **120000** token-equivalents). The planner (Opus) must satisfy the check at its own
  self-validation step (splitting oversized batches before committing); the step-1.5
  validator gate halts on `batch-oversized` because splitting is a structural change, not a
  mechanical fix.
- Rationale: A Sonnet implementer with a 200k window must hold its batch in its head; an
  oversized batch (observed: 27 cards) blows the budget mid-run. A combined card-count +
  context-size gate catches both "too many cards" and "few cards but each pulls in huge
  files". The `batch-oversized` row joins the existing "halt" rows in the step-1.5 fix table
  (alongside `missing-overview`, `batch-index-parse`) because auto-splitting would mask a
  structural planning bug.
- Rejected: Card-count cap only (misses few-but-heavy batches); token-estimate only (a
  pathological 50-tiny-card batch would pass yet still overwhelm the implementer's working
  memory).

### out-of-worktree-target (#363)

- Decision: Add a `_plan_validate` check `out-of-worktree-target` that resolves every
  `Edits:` and `Creates:` path (normalised, without requiring the target to exist for
  `Creates:`) and flags any path that does not resolve under the worktree root -- catching
  `~/.claude/CLAUDE.md`, `C:\Users\...`, and any absolute path outside the tree. It is a
  step-1.5 "halt" row (non-mechanical): the operator must handle such edits manually; the
  implementer must never be pointed at them.
- Rationale: The tool layer blocks home-dir edits, so an implementer card targeting one
  retries forever and mis-classifies as `transient`. Catching it at plan time -- before
  mill-go ever runs -- is strictly better than detecting it at runtime, because the
  validator gates every plan before implementation begins.
- Rejected: (a) Plan-time check plus a new runtime `stuck_type: infrastructure` (defense in
  depth) -- the plan-time gate catches it before runtime, so the runtime classification is
  YAGNI. (b) Runtime-only classification -- leaves the bad plan in place and only reacts
  after wasted implementer rounds.

### exit-without-json (#372)

- Decision: Two layers. (1) Wrap `millpy-review-plan.py`'s `main()` so any uncaught
  exception emits an error envelope (`print_error_envelope("plan", ...)`, exit 1) -- today
  only `ReviewError` is caught, so an unexpected exception exits with no JSON. (2) Extend
  mill-plan Phase: Plan Review step 4.5 so an *absent* JSON line in the bg log (worker
  killed / OOM, no envelope possible) is treated as ERROR-equivalent and routed through the
  existing two-pass retry; on the second consecutive absent-JSON, halt with
  `BLOCKED: plan review no-JSON round {N}`. This mirrors mill-go's "only treat exit 1 as
  unrecoverable when the JSON line is absent" rule.
- Rationale: A Python-level crash is recoverable by guaranteeing an envelope; a truly killed
  worker cannot print anything, so the SKILL-side absent-JSON handling is the backstop. Both
  layers together close the gap.
- Rejected: SKILL-side only (a clean Python exception would still produce a confusing raw
  traceback in the log); CLI-side only (cannot cover a killed/OOM worker).

### review-file-commit (#362 / #378)

- Decision: In mill-go Holistic step 4 (`APPROVE`), stage the holistic review file in the
  same commit as `status.md` -- use the `file` field from `reviews[0]` of the JSON envelope,
  or the crash-recovery scan path from branch (a). Audit the sibling APPROVE paths for the
  identical "commit status only, drop the review file" gap and fix any found; the
  discussion-review APPROVE path in mill-start Handoff has it and is fixed in the same pass.
- Rationale: Review files are task-state under `_mill/reviews/`; an uncommitted one is
  deleted silently at cleanup. The per-batch code-review APPROVE and the mill-plan APPROVE
  paths already stage their review files -- holistic and discussion-review are the
  stragglers. One-line `git add` fixes; cheap to fix the sibling at the same time rather than
  re-file it.
- Rejected: Strictly scoping to the holistic path only and re-filing the discussion-review
  gap separately -- needless churn for an identical one-line fix.

### new-config-keys

- Decision: The new batch-sizing thresholds are config keys with defaults, added to BOTH
  the hub `mill-config.yaml` and the plugin template `plugins/mill/templates/mill-config.yaml`
  (kept in sync per CLAUDE.md). They live under the `pipeline` namespace (batch sizing is a
  plan-synthesis concern, not a reviewer-role setting): `pipeline.max_cards_per_batch`
  (default 10) and `pipeline.max_batch_context_tokens` (default 120000). `_plan_validate`
  reads them with hardcoded fallbacks so a config missing the keys still validates.
- Rationale: mill is config-driven; operators tune per-project without code edits. The
  template-sync rule exists for exactly this. The `pipeline` namespace already holds plan/go
  orchestration knobs (`autonomous_mode`, `auto_merge`, `skip_validate`); the
  `roles.*-review.*` namespace is about reviewer dispatch, which the validator is not.
- Rejected: Module-level constants in `_plan_validate.py` -- simpler but untunable without a
  code edit, against the codebase's config-driven grain.

## Technical context

Key files and the role each plays:

- `plugins/mill/skills/mill-go/SKILL.md` -- the Builder loop. Relevant sections: Execute
  step 3 (per-batch Code Review loop: crash-recovery scan in 3.1; APPROVE branch at "4."
  already stages the review file); Holistic code review (step 1 crash-recovery branches
  a/b/c; step 4 APPROVE commits status ONLY -- the #362/#378 fix site). Touchpoints for
  #360 (APPROVE/NIT handling), #373 (probe freshness), #362/#378 (holistic commit).
- `plugins/mill/skills/mill-plan/SKILL.md` -- the planner. Phase: Plan ("Batch sizing"
  prose, self-validate via `_plan_dag`); Phase: Plan Review step 1.5 (validator gate + fix
  table) and step 4.5 (ERROR retry). Touchpoints for #371 (self-validate + step-1.5 row),
  #363 (step-1.5 row), #372 (step 4.5 absent-JSON).
- `plugins/mill/skills/mill-start/SKILL.md` -- discussion-review Phase. Handoff commits
  `status_path` only; APPROVE-no-NOTE path (4a) does not commit the discussion review file.
  Touchpoint for the #362/#378 sibling audit.
- `plugins/mill/scripts/_review_common.py` -- `worktree_snapshot_guard` (lines ~120-156:
  the #374 fix site), `_filter_porcelain`, `parse_verdict` (~1051), `parse_blocking_count`
  (~1149: reused for `nit_count` with `severity="NIT"`), `ReviewResult`/`to_dict` (~219-235:
  where `nit_count` is added to the envelope), `write_review_file` (filename scheme).
- `plugins/mill/scripts/_review_code.py` -- code-review engine; wires the snapshot guard and
  builds the per-scope review results that feed the envelope. Where `nit_count` is computed
  per review and aggregated.
- `plugins/mill/scripts/millpy-review-code.py` -- code-review CLI; emits the JSON envelope
  the Builder reads (must carry `nit_count`).
- `plugins/mill/scripts/millpy-review-plan.py` -- plan-review CLI; `main()` (lines ~80-128)
  catches only `ReviewError` -- the #372 guaranteed-envelope wrap goes here. Uses
  `print_error_envelope`.
- `plugins/mill/scripts/_plan_validate.py` -- the validator. `run(...)` returns a list of
  error dicts each shaped `{"check": <name>, "batch": <name|None>, "card": <int|None>, ...}`
  (see existing checks `non-existent-path`, `card-numbering`, `verify-not-isolated`, etc.).
  New checks `batch-oversized` and `out-of-worktree-target` are added here following the
  same dict shape and `errors.sort` ordering.
- `plugins/mill/scripts/millpy-fix.py` -- the cold-start fixer dispatched on REQUEST_CHANGES;
  reused unchanged for the #360 NIT-only pass (it applies findings from the supplied review
  file; on an APPROVE'd file those findings are all NITs).
- `plugins/mill/scripts/_pygit2_util.py` -- git ops (`head_sha`, `status_porcelain`); add an
  ancestry helper here for the #374 descendant test if one does not already exist.
- `plugins/mill/scripts/_status.py` -- `read_full` returns `{"yaml", "timeline"}`; the
  timeline rows carry the per-round phase-entry timestamps the #373 freshness probe compares
  against.

Gotchas:

- The Builder must stay lean: it reads only the JSON envelope and the structured
  `## Missing context` bullets, never findings. The #360 fix must surface a count, never
  push finding-reading into the Builder.
- Verdict parsing reads ONLY the first fenced ```yaml block; `parse_blocking_count` counts
  `^### [<severity>] ` ATX headings in the body. `nit_count` reuses that same counter with
  `severity="NIT"`.
- `_filter_porcelain` already normalises backslashes and splits rename arrows; the #374
  change is in the comparison logic at `_review_common.py` ~152, not in the filter.
- Code/plan severity labels are `BLOCKING` and `NIT`; discussion uses `GAP`/`NOTE`. The
  `nit_count` work is code-review-only.
- `Creates:` targets do not exist on disk at validate time -- the `out-of-worktree-target`
  resolver must normalise the path without requiring existence (resolve against the worktree
  root and compare, do not `Path.resolve(strict=True)`).
- The two new validator "halt" rows must be added to the mill-plan step-1.5 fix table with
  an explicit "halt -- not mechanically fixable" mapping, consistent with the existing halt
  rows, so the two-pass cap fires correctly.

## Constraints

- No `CONSTRAINTS.md` at the hub root (checked: absent).
- ASCII-only in any `print()` / `_log()` stdout (Windows cp1252). Use ` -- ` and ` -> `.
- All path resolution through `_paths.py`; recursive deletion strips junctions first (not
  expected to be touched here, but the out-of-worktree resolver must use `_paths`-style
  resolution, not inline `container / ...`).
- `verify:` commands in plan files must start with `PYTHONPATH= ` (enforced by the existing
  `verify-not-isolated` check) -- the new test files this task adds must be invoked that way.
- Hub `mill-config.yaml` and the plugin template must stay in sync (the new `pipeline.*`
  keys go in both).
- Helper signatures are documented inline in the SKILLs; do not Read/Grep helper source from
  a SKILL -- any new helper this task adds must get an inline `signature:` line where a SKILL
  calls it.

## Testing

TDD the Python changes; verify the SKILL.md prose changes by inspection (no harness). Each
batch's `verify:` runs only its touched test file(s) via
`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only <files>`.

- `_plan_validate.py` (`test-plan-validate.py`, extend existing):
  - `batch-oversized`: a batch exceeding the card cap flags; a batch exceeding the
    context-token estimate flags; a batch at/under both passes; cap/budget read from config
    with fallback when keys absent. TDD candidate.
  - `out-of-worktree-target`: an `Edits:`/`Creates:` path under `~`, an absolute path
    outside the tree, and a Windows `C:\Users\...` path each flag; an in-tree relative path
    and an in-tree `Creates:` (non-existent yet) pass. TDD candidate.
- `_review_common.py` (`test-review-guard.py`, extend existing):
  - overstep guard: a clean window passes; a working-tree dirtying raises
    `ReviewerOverstepError`; a fast-forward descendant HEAD advance passes (with warning, no
    raise); a non-descendant HEAD change (simulated reset/rewrite) raises. TDD candidate --
    this is the highest-risk change.
  - `nit_count` via `parse_blocking_count(raw, severity="NIT")`: output with N NIT headings
    returns N; zero NITs returns 0; mixed BLOCKING+NIT counts only NIT.
- Envelope (`millpy-review-code.py` / `_review_code.py`): the JSON envelope carries an
  aggregated top-level `nit_count`. Add/extend a CLI-or-engine test that asserts the field is
  present and equals the summed per-review NIT count.
- `millpy-review-plan.py`: an uncaught exception inside the reviewed `run(...)` produces an
  error envelope on stdout and exit 1 (assert JSON parses and carries `verdict: ERROR` /
  error string), rather than exiting with no JSON.
- Scenarios deliberately NOT unit-tested (verified by inspection): the mill-go/mill-plan/
  mill-start SKILL.md prose edits, the step-1.5 fix-table rows, and the crash-recovery mtime
  probe (a SKILL-level inline-Python branch, not a standalone helper). If the #373 freshness
  comparison is extracted into a small helper in `_status.py` or a probe module, that helper
  is unit-tested instead.

## Q&A log

- **Q:** #360 -- how to apply code-review NITs without breaking the lean Builder? **A:**
  Add `nit_count` to the envelope; on APPROVE + nit_count>0 dispatch one cold-start NIT-only
  fix pass, no re-review. Mirrors mill-plan 4b.
- **Q:** #374 -- how to tolerate a concurrent operator commit during a review? **A:** Flag
  overstep only on working-tree dirt or a non-descendant HEAD change; a fast-forward
  descendant advance is allowed with a warning.
- **Q:** #373 -- consume the round on ERROR retry, or validate file freshness? **A:**
  Validate freshness (review-file mtime newer than the round's phase-entry timestamp);
  preserve full review budget.
- **Q:** #371 -- card-count cap, token estimate, or both? **A:** Both -- 10-card cap plus a
  ~120k-token context-size estimate; halt row at step 1.5 (splitting is non-mechanical).
- **Q:** #363 -- plan-time check, runtime stuck_type, or both? **A:** Plan-time
  `out-of-worktree-target` validator halt only; runtime `infrastructure` classification is
  YAGNI once the plan gate catches it.
- **Q:** #362/#378 -- holistic only, or fix sibling APPROVE paths too? **A:** Fix holistic
  and audit/fix siblings with the same gap (discussion-review) in one pass.
- **Q:** #372 -- SKILL-side, CLI-side, or both? **A:** Both -- guarantee an envelope from the
  CLI on uncaught exceptions, and treat an absent JSON line in mill-plan as ERROR-equivalent
  via the two-pass retry.
- **Q:** New tunables -- config keys or constants? **A:** Config keys with defaults under the
  `pipeline` namespace, mirrored in the plugin template; `_plan_validate` reads them with
  hardcoded fallbacks.
