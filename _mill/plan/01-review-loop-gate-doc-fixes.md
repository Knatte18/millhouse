# Batch: review-loop-gate-doc-fixes

```yaml
task: "mill-plan SKILL.md: Phase Plan Review gate, convergence, and DAG-validation correctness bugs"
batch: review-loop-gate-doc-fixes
number: 1
cards: 7
verify: null
depends-on: []
```

## Batch Scope

This batch fixes seven of the nine open GitHub issues (#896, #902, #890, #877, #886, #901, #861)
purely by editing `plugins/mill/skills/mill-plan/SKILL.md` prose (Card 7 also touches one comment
line in `plugins/mill/templates/mill-config.yaml`). No Python code changes — every fix here is a
documentation/instruction change the mill-plan orchestrator itself reads and follows; none of it is
independently unit-testable (see `_mill/discussion.md`'s Testing section for the per-issue hedge).
Cards are ordered so structural changes (Card 1's step relocation) land before cards whose own
Requirements reference the resulting post-relocation structure (Card 2). This batch is a root batch
(no dependencies) and Batch 2 depends on it, since both batches touch `mill-plan/SKILL.md` and must
not run in parallel.

## Cards

### Card 1: #896 — relocate step 4.5, add unconditional per-round Timeline append

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Relocate the entire current `### Phase: Plan Review` "Step 4.5: ERROR-only-aggregate retry (no
  round consumed)" section — the block starting at the `4.5.` heading line and running through its
  own final paragraph (the `*(Note: the CLI now emits a verdict: ERROR envelope...)*` sentence,
  ending "...Closes #84 — `verdict: ERROR` tracking was introduced so ERROR rounds never silently
  collapse into 4c's NIT path.)*") — to sit immediately after the existing numbered step `3.`
  ("**Confirm `mill-receiving-review` is loaded before evaluating or acting on this round's
  findings**...") and its one-sentence continuation ("Non-negotiable. The VERIFY → HARM CHECK →
  FIX-or-PUSH-BACK decision tree is what keeps review loops useful."), and immediately before the
  `**Guardrail:**` line ("NIT/BLOCKING fixes during Plan Review apply ONLY to files under
  `<plan_dir>`..."). Renumber the relocated section's own heading from the literal token `4.5.` to
  `3.5.` — this is purely a structural move: do not alter any other text inside the moved block,
  including its internal references to "steps 4a/4b/4c/4d" (those remain correct after the move —
  the block's own logic already treats itself as a screening gate that runs *before* 4a-4d, this
  relocation only makes the physical document order match that existing logical order, mirroring
  how step `1.5`'s pre-review validator gate already physically precedes step `2`'s dispatch by the
  same half-integer numbering convention).

  Immediately after the relocated `3.5.` section (i.e., as the new final paragraph before
  `**Guardrail:**`), insert this new paragraph verbatim:

  "**Unconditional round-recorded append.** Once step 3.5's screening above confirms this round
  produced a reviewable verdict (i.e., did NOT trigger the usage-error halt or the ERROR/absent-JSON
  retry-and-skip), and before branching into 4a/4b/4c/4d below: call
  `_status.append_phase(status_path, f"plan-review-r{N}", _timestamp.now_utc_iso())`, then commit
  immediately on the task branch (`git -C <worktree> add <status_path> && git -C <worktree> commit
  -m "mill-plan: record plan-review round {N} for {slug}"`) and push. This records every
  genuinely-reviewed round's Timeline row exactly once, decoupled from whichever of 4a/4b/4c/4d fires
  below and from the Convergence gate's `converged`/not-`converged` branching — closing the prior
  asymmetry where only 4a's converged-or-capped terminal path and 4d ever appended this row (4b and
  4c never did, and 4a's own not-converged-under-cap path also skipped it, per its 'take no action
  this round' branch)."

  Then, in the now-relocated-after `4a.` branch (the paragraph beginning "If `converged`, or `round
  >= max_review_rounds` (implicit-approve-at-cap): set overview frontmatter `approved: true` via
  direct Edit. `_status.append_phase(status_path, f"plan-review-r{N}", iso_ts)`."), delete the
  trailing sentence `` `_status.append_phase(status_path, f"plan-review-r{N}", iso_ts)`. `` in full,
  leaving the paragraph ending "...set overview frontmatter `approved: true` via direct Edit." — the
  row is now recorded by the new unconditional-append paragraph above, so this second append would
  double-write the same Timeline entry.

  Then, in `4d.`'s bullet list (`- \`_status.append_phase(status_path, f"plan-review-r{N}", iso_ts)\`.`
  is the FIRST bullet under the `4d. On \`REQUEST_CHANGES\` AND \`blocking_count > 0\`:` heading),
  delete that entire first bullet. The remaining bullets under 4d (Read each review file; Apply
  fixes; Write a fixer report; Re-validate the plan DAG; `_status.append_phase(...plan-fix-r{N}...)`;
  Commit) are unchanged and unaffected — 4d's `plan-fix-r{N}` append stays exactly as-is; only its
  now-redundant `plan-review-r{N}` bullet is removed.

  Finally, update the "**Tree-guard safeguard (applies to all `_status.append_phase` calls in this
  phase):**" paragraph's parenthetical citation — it currently reads "Before any
  `_status.append_phase` call in this phase (steps 4a/4b/4c/4d below), call
  `_treeguard.check_and_restore(...)`" — to instead read "Before any `_status.append_phase` call in
  this phase (the unconditional round-recorded append at step 3.5, and steps 4a/4b/4c/4d below),
  call `_treeguard.check_and_restore(...)`", so the citation stays accurate now that a new
  `_status.append_phase` call site exists earlier in the phase (this paragraph is well before the
  relocated 3.5 section in document order, so this is a separate, standalone edit at its own
  existing location — do not move this paragraph).
- **Commit:** `docs(mill-plan): relocate step 4.5 to 3.5 and append plan-review-r{N} unconditionally per round`

### Card 2: #902 — persist skip_checks across Phase: Plan / Phase: Plan Review

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  This card is implemented after Card 1 in the same batch, so its own edits below target the
  POST-Card-1 document structure (step 3.5 physically precedes 4a; read the file fresh before
  editing, do not assume pre-Card-1 line numbers).

  In Phase: Plan, immediately after the paragraph beginning "Fix any findings using the Step 1.5 fix
  table below, then re-run, before committing the plan." (which currently sits between the
  `_plan_validate.run(...)` code fence and the `signature: _status.read(status_path: Path) -> dict`
  line), insert a new paragraph:

  "**Persist `skip_checks` for Phase: Plan Review.** When `skip_checks` (computed above, after
  applying the `wiki-config-mutation` and `verify-full-suite` skip-check overrides) is non-empty,
  write it into `00-overview.md`'s fenced-yaml frontmatter as a new `skip_checks:` list field
  (parallel to the existing `approved:` field, e.g. `skip_checks: [\"wiki-config-mutation\"]`), via
  the same direct-`Edit` convention already used elsewhere in this file for the `approved:` field.
  Omit the field entirely (do not write `skip_checks: []`) when the frozenset is empty, matching the
  template's convention of omitting optional frontmatter keys that don't apply. Include this edit in
  the same 'Commit on the task branch' step below — no separate commit."

  In Phase: Plan Review's "**Path Setup (Plan Review).**" section, immediately after the paragraph
  beginning "Derive: `reviews_dir = _paths.resolve_task_path(worktree_root,
  cfg['paths']['reviews_dir'])`. Use this variable for all review file path references in this
  phase.", insert a new paragraph:

  "**Read persisted `skip_checks` from Phase: Plan.** Parse `00-overview.md`'s fenced-yaml frontmatter
  (the same extraction pattern already used elsewhere in this file for the `approved:` field) and
  read `plan_skip_checks = <parsed skip_checks: list, or [] if the key is absent>`. This is the
  `skip_checks` frozenset Phase: Plan already justified via the `wiki-config-mutation` /
  `verify-full-suite` two-condition tests — thread it into every round's CLI dispatch below as
  `--skip-check <name>` per entry (repeatable flag, one `--skip-check` per list entry), so Phase:
  Plan Review's own validator gate does not re-flag a finding Phase: Plan already resolved and
  committed against."

  Thread `plan_skip_checks` into every prepare/finalize dispatch site in this phase, by adding one
  clause to each of the following four existing sentences (append the clause to the END of each
  named sentence, do not otherwise alter the sentence):
  1. Step 2's Agent-mode dispatch sentence — "If `agent` (Claude provider only): follow the
     Agent-mode dispatch pattern (see \"## Agent-mode dispatch\" in `mill-go-base/SKILL.md`) with
     `<cli> = millpy-review-plan.py` and `<args> = --holistic-only`." — append: ", plus one
     `--skip-check <name>` per entry in `plan_skip_checks` (when non-empty)".
  2. Step 2's subprocess/psmux `millpy-bg` code fence's surrounding prose — the sentence "Append the
     flag to the inner `uv run …millpy-review-plan.py` portion of the millpy-bg invocation when
     needed." (referring to `--holistic-only`/`--no-holistic`) — append a new sentence immediately
     after it: "Append one `--skip-check <name>` per entry in `plan_skip_checks` (when non-empty) to
     that same inner invocation."
  3. Step 3.5's (relocated by Card 1) Agent-mode retry sentence — "**Agent-mode:** follow the
     Agent-mode dispatch pattern (see \"## Agent-mode dispatch\" in `mill-go-base/SKILL.md`) with
     `<cli> = millpy-review-plan.py` and `<args> = --holistic-only`." — append: ", plus one
     `--skip-check <name>` per entry in `plan_skip_checks` (when non-empty), exactly as step 2's
     dispatch above".
  4. Step 3.5's subprocess/psmux retry code fence's surrounding prose — immediately after the
     sentence "This returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until
     `[mill-bg] EXIT` appears, then run `grep '^{' <log-path> | tail -1` to extract the JSON summary
     line." that follows the `plan-review-retry-r<N>` code fence, insert: "Append one `--skip-check
     <name>` per entry in `plan_skip_checks` (when non-empty) to the inner
     `millpy-review-plan.py` invocation, exactly as step 2's subprocess branch above."

  Finally, update the Step 1.5 intro paragraph's sentence "If `pipeline.skip_validate: true` ever
  appears in config (currently it does not; this is a future hook), pass `--skip-validate` to the CLI
  and skip step 1.5 entirely. mill-plan passes `--skip-check wiki-config-mutation` only when the fix
  table instructs it — see the `wiki-config-mutation` row." — replace the final sentence ("mill-plan
  passes `--skip-check wiki-config-mutation` only when the fix table instructs it — see the
  `wiki-config-mutation` row.") with: "mill-plan threads `plan_skip_checks` (persisted from Phase:
  Plan, per the 'Read persisted `skip_checks` from Phase: Plan' paragraph in Path Setup above) into
  every round's dispatch proactively; the fix-table's own `--skip-check wiki-config-mutation` /
  `--skip-check verify-full-suite` rows (below) remain the reactive fallback for a check that becomes
  newly true *during* Plan Review itself (e.g. an LLM fix-pass in 4b/4c/4d that edits the hub config
  file), which `plan_skip_checks` — fixed at Phase: Plan's commit time — cannot have anticipated."
- **Commit:** `docs(mill-plan): thread Phase: Plan's skip_checks into every Plan Review dispatch`

### Card 3: #890 — explicit `_plan_dag.validate` call shape at steps 4b and 4d

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In step `4b.`, replace the sentence "Re-validate the plan DAG via `_plan_dag.validate`." with:
  "Re-validate the plan DAG: read `overview_text = (plan_dir / \"00-overview.md\").read_text(encoding=\"utf-8\")`,
  call `batches = _plan_dag.extract_batch_index(overview_text)`, then
  `_plan_dag.validate(batches, sorted(p.name for p in plan_dir.glob(\"??-*.md\") if p.name != \"00-overview.md\"))`.
  `signature: _plan_dag.validate(batches: list[dict], batch_files: list[str]) -> None`" — this
  mirrors the exact call shape already used and proven correct in Phase: Plan's own "Self-validate
  the DAG" step.

  In step `4d.`'s bullet list, replace the bullet `` - Re-validate the plan DAG (\`_plan_dag.validate\`). ``
  with: "- Re-validate the plan DAG: read `overview_text = (plan_dir / \"00-overview.md\").read_text(encoding=\"utf-8\")`,
  call `batches = _plan_dag.extract_batch_index(overview_text)`, then
  `_plan_dag.validate(batches, sorted(p.name for p in plan_dir.glob(\"??-*.md\") if p.name != \"00-overview.md\"))`.
  `signature: _plan_dag.validate(batches: list[dict], batch_files: list[str]) -> None`" — same
  replacement text as the 4b edit above, formatted as a bullet to match 4d's existing bullet-list
  structure.

  Do not edit Phase: Plan's own "Self-validate the DAG" paragraph — it already spells out this exact
  two-argument call and needs no change.
- **Commit:** `docs(mill-plan): add explicit _plan_dag.validate call shape at steps 4b and 4d`

### Card 4: #877 — ban cross-card "same commit" requirements

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the `## Principles` section, immediately after the bullet beginning "- **Express renames as
  `Moves:` pairs**..." (ending "...Keep naming the specific surgical edits (package declaration,
  import lines, identifier retargets) in `Requirements:` using stable identifiers.") and immediately
  before the bullet beginning "- **Phrase Requirements: prohibitions on one line; avoid double
  negatives**...", insert a new bullet:

  "- **Never require two separately-numbered cards to land in the same commit.** Each card produces
  its own commit at implementation time (see the per-card `Commit:` field; every per-card commit
  invokes the `git-commit` skill per `mill-go-base/SKILL.md`'s one-commit-per-card execution
  convention). Once a card's commit is made and pushed, the harness's git-safety protocol (always
  create a new commit rather than amending a prior one, absent explicit operator instruction
  otherwise) forbids folding a later card's diff into it. If two changes are genuinely atomic — must
  land together or not at all — express them as a SINGLE card with one `Commit:` message, never as
  two cards linked by a cross-card \"same commit\" or \"must be squashed into card N\" instruction in
  `Requirements:`."
- **Commit:** `docs(mill-plan): ban cross-card same-commit requirements in Principles`

### Card 5: #886 — drop the redundant `demoted` predicate from the Convergence gate

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the "**Convergence gate (min_rounds + demoted predicate)**" section, replace the formula code
  fence:
  ```
converged = (round >= min_review_rounds) and not any(f.get("demoted") for f in envelope["findings"])
  ```
  with:
  ```
converged = (round >= min_review_rounds)
  ```
  and delete the entire "**Exception — mill-plan's site only.**" paragraph that immediately follows
  the formula fence (the paragraph beginning "`envelope[\"findings\"]` is not safe to read directly
  at this site..." and ending "...so the filter cleanly excludes carryforward and keeps only this
  round's live findings.") in full — the `current_round_findings` filtering machinery it describes
  existed solely to make the now-deleted `demoted` predicate safe against stale carried-forward
  markers; with the predicate itself removed, the filtering has nothing left to protect and the whole
  paragraph is dead prose.

  Rename the section heading itself from "**Convergence gate (min_rounds + demoted predicate).**" to
  "**Convergence gate (min_rounds).**" — the "demoted predicate" no longer exists.

  Update the bullet "- `converged is False` AND `round >= max_review_rounds` (last allowed round):
  treat as an implicit approval — run the branch's existing terminal actions exactly as if
  `converged` were `True`, but append `\" (min_rounds/demoted-predicate not satisfied by round
  cap)\"` to that round's commit message..." — replace the quoted append text
  `" (min_rounds/demoted-predicate not satisfied by round cap)"` with
  `" (min_rounds not satisfied by round cap)"` in this bullet — this exact string also appears
  verbatim in steps 4a, 4b, and 4c's own commit-message instructions below the Convergence gate
  section (search for and replace every occurrence of the literal string
  `" (min_rounds/demoted-predicate not satisfied by round cap)"` with
  `" (min_rounds not satisfied by round cap)"` throughout `mill-plan/SKILL.md` — there are four
  occurrences total: one in the Convergence gate section itself, and one each in 4a, 4b, and 4c).

  Step 4c's own rationale sentence ("Rationale: 0-BLOCKING means the planner and reviewer have
  converged; further rounds only churn cosmetic NITs — this is exactly the premature-termination
  case a ceiling-demoted BLOCKING can otherwise mask, which is what the convergence gate now guards
  against.") becomes self-contradicting once the `demoted` predicate is removed — the gate no longer
  guards against ceiling-demoted findings at all. Replace the clause ", which is what the convergence
  gate now guards against" with nothing (delete it), leaving the sentence ending "...this is exactly
  the premature-termination case a ceiling-demoted BLOCKING can otherwise mask." — still a true,
  standalone justification for why 0-BLOCKING alone should terminate the loop, without the now-false
  claim that the gate specifically guards against that case.
- **Commit:** `docs(mill-plan): drop redundant demoted predicate from convergence gate`

### Card 6: #901 — `out-of-worktree-target` skip-check paragraph

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In Phase: Plan, immediately after the "**`verify-full-suite` skip-check escape hatch.**" paragraph
  and immediately before the `_plan_validate.run(...)` code fence, insert a new paragraph:

  "**`out-of-worktree-target` skip-check override.** If any batch's `Edits:`/`Creates:` includes an
  absolute path resolving outside the worktree, apply a two-condition test before calling
  `_plan_validate.run`, mirroring the `wiki-config-mutation` override's shape: (a) `discussion.md`
  contains an explicit statement recording the operator's cross-worktree authorization — naming the
  second worktree/repo path and the reason writes there are required for this task; and (b) the
  second worktree is itself a git worktree the operator created/cloned specifically for this task
  (not an incidental absolute path into an unrelated system directory). If both conditions hold, set
  `skip_checks = skip_checks | frozenset({\"out-of-worktree-target\"})` and record the justification
  in the plan commit message (see \"Commit on the task branch\" below). If either condition fails,
  leave `skip_checks` unchanged for this check — let it fire and halt per the
  `out-of-worktree-target` fix-table row instead."

  In the Step 1.5 fix table, replace the `out-of-worktree-target` row's mechanical-fix cell —
  currently "Halt — an `Edits:`/`Creates:` target resolves outside the worktree (home-dir or
  absolute path). The operator must handle such edits manually; the implementer can never be pointed
  at them. Not auto-fixable." — with: "If the plan's `discussion.md` records an explicit
  cross-worktree authorization and the target is itself a git worktree under legitimate task control
  (see the `out-of-worktree-target` skip-check override in Phase: Plan), re-run with `--skip-check
  out-of-worktree-target`. Otherwise: Halt — the operator must handle such edits manually; the
  implementer can never be pointed at them. Not auto-fixable."
- **Commit:** `docs(mill-plan): add out-of-worktree-target skip-check override`

### Card 7: #861 — Done-gate reminder verify-clean-first precondition

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `mill-plan/SKILL.md`'s "**Done-gate reminder.**" section, replace the second paragraph — "When
  the target language's build skill defines a lint command (Go: `golangci-lint run`; Python: `ruff
  check .`), default `done_gate` to include it — e.g. `go test ./... && golangci-lint run`. This
  applies even when a repo-wide *test* command is skipped as too slow: author `done_gate:
  golangci-lint run` (lint-only) rather than leaving it `null`, since linters are fast, unlike full
  regression suites. `csharp-build` defines no lint command today, so C# projects are unaffected by
  this default." — with: "Before defaulting `done_gate` to the target language's lint command (Go:
  `golangci-lint run`; Python: `ruff check .`), first run that candidate command against the current
  worktree tip (not the plan's own scoped changes) from `git_root` and confirm it exits 0. If it
  does, default `done_gate` to include it — e.g. `go test ./... && golangci-lint run` — applying even
  when a repo-wide *test* command is skipped as too slow: author `done_gate: golangci-lint run`
  (lint-only) rather than leaving it `null`, since linters are fast, unlike full regression suites.
  If the candidate command does NOT exit 0 (pre-existing repo-wide lint debt unrelated to this task),
  leave `done_gate: null` and record the finding in the plan overview's Shared Decisions instead of
  silently making every future task in the hub depend on unrelated debt being fixed first.
  `csharp-build` defines no lint command today, so C# projects are unaffected by this default."

  Leave the surrounding paragraphs (the first paragraph about `go test ./...`/`dotnet test`, and the
  final "Leave `done_gate: null` only when..." paragraph) unchanged.

  In `plugins/mill/templates/mill-config.yaml`, locate the `done_gate:` line (currently:
  ``  done_gate: null  # Repo-wide check command run from git_root before marking done; null =
  disabled. Default to including the language's lint command (e.g. golangci-lint run, ruff check .)
  even when a full test run is skipped as too slow. e.g. "go test ./... && golangci-lint run" or
  "dotnet test". (#561)``). Replace the trailing comment text starting at "Default to including the
  language's lint command" through "(#561)" with: "Default to including the language's lint command
  (e.g. golangci-lint run, ruff check .) ONLY after first confirming that command exits 0 against the
  current worktree tip — never set this to a command that is currently failing on pre-existing debt.
  e.g. \"go test ./... && golangci-lint run\" or \"dotnet test\". (#561, #861)" — keep the line's
  value (`null`) and the leading "Repo-wide check command run from git_root before marking done; null
  = disabled." clause unchanged, only the "Default to including..." clause onward is replaced.
- **Commit:** `docs(mill-plan): require verify-clean-first before defaulting done_gate to lint command`

## Batch Tests

Pure `mill-plan/SKILL.md` prose (plus one comment-line edit in `plugins/mill/templates/mill-config.yaml`)
— no Python code changes, nothing to run. `verify: null` per the overview's module-wide default and
this batch's own frontmatter. Each card's correctness is verified by re-reading the edited section
against this batch's own Requirements text during code review, and later, functionally, the first
time `/mill-plan` executes Phase: Plan Review after this task lands.
