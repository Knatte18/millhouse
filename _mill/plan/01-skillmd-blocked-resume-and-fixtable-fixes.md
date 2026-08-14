# Batch: skillmd-blocked-resume-and-fixtable-fixes

```yaml
task: 'mill-plan SKILL.md: step 6 max-rounds escape bugs, self-run validator citation errors, and Step 1.5 fix-table wrong remedies'
batch: skillmd-blocked-resume-and-fixtable-fixes
number: 1
cards: 7
verify: null
depends-on: []
```

## Rename mechanic

Not applicable — this batch contains no `Moves:` entries.

## Batch Scope

This batch makes every edit for both in-scope issues (#852, #853) in a single file, `plugins/mill/skills/mill-plan/SKILL.md`. It is one batch because every card targets the same file and the edits are all small, surgical, non-overlapping text replacements within that one file — splitting across batches would buy nothing and would force artificial dependency ordering between cards that don't actually depend on each other's diffs. Cards are ordered so that cards which reference text introduced or changed by an earlier card (e.g. card 3's cross-reference to the new `blocked` table row added by card 2) come after it; cards with no such relationship (e.g. card 7, the `#853` fix-table row rewrite) can be implemented in any order relative to the others, but are listed last since they belong to the unrelated `#853` decision.

No batch-local decisions beyond the two in `## Shared Decisions` (00-overview.md) — `revise_from_blocked` naming and "no Python code or test changes" both apply to every card here.

## Cards

### Card 1: Widen the `--revise` pre-check to accept a `blocked`-resume branch (#852)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In the `**\`--revise\` pre-check.**` block under `## Entry`, step 4, locate this exact current text (3-space indented, lines ~56-60 as of plan-writing time — locate by content, not by line number, since earlier cards in this same batch do not touch this block but line numbers may still drift):

```
   **`--revise` pre-check.** Whenever `revise_requested` is set (from Step 0.5), this pre-check runs **before** every row of the table below, as a distinct pre-check, not merely appended after it — this ordering is required because the table's existing `| approved: true in overview frontmatter | ... |` row is unconditional on `phase:`, and its condition (`approved: true`) is also satisfied throughout the entire `phase: planned` window `--revise` targets (since `approved:` stays `true` for the whole duration of mill-go's later run too — mill-go's own Prepare step immediately overwrites `phase: planned` to `phase: implementing` the moment execution starts, so `phase: planned` is the narrow, correct window that can only be true in the intended pre-execution period); without this explicit precedence, `--revise` would always hit the pre-existing halt row before ever reaching the new logic.
   Read `phase = _status.read_full(status_path)["yaml"].get("phase")` and the overview frontmatter's `approved:` field (via the file's existing YAML-block-extraction pattern already used elsewhere in this file for the `approved:` field).
   - If **both** `phase == "planned"` **and** `approved` is currently `true`: proceed with the revise action — (1) flip `approved: false` in `plan/00-overview.md` via the same direct-`Edit` convention already used elsewhere in this file for that field (no `_status.py` involvement, since `approved:` intentionally lives outside `status.md` per this file's own "## Board discipline" section); (2) call `_status.append_phase(status_path, "planning", <timestamp>)`; (3) commit both mutations together on the task branch in one commit (`git -C <worktree> add <plan_dir> <status_path> && git -C <worktree> commit -m "mill-plan: --revise re-open plan review for {slug}"`) and push; (4) fall through into the existing `phase: planning`/`plan-review-r{N}`/`plan-fix-r{N}` re-entry row (Phase: Plan Review; do NOT rewrite plan files) unmodified.
   - If `revise_requested` is set but the condition is **not** met (any phase other than `planned`, or `approved` is not `true`): halt with an explicit message naming the current `phase:` value and stating that revising a plan mill-go has already started executing (or has not yet been approved) is unsupported — do not silently force-flip `phase: planning` onto a task with committed/approved batches.
   - When `revise_requested` is not set, skip this entire pre-check and fall through to the existing table exactly as it is today.
```

  Replace it with (same 3-space indentation for every line):

```
   **`--revise` pre-check.** Whenever `revise_requested` is set (from Step 0.5), this pre-check runs **before** every row of the table below, as a distinct pre-check, not merely appended after it — this ordering is required because the table's existing `| approved: true in overview frontmatter | ... |` row is unconditional on `phase:`, and its condition (`approved: true`) is also satisfied throughout the entire `phase: planned` window `--revise` targets (since `approved:` stays `true` for the whole duration of mill-go's later run too — mill-go's own Prepare step immediately overwrites `phase: planned` to `phase: implementing` the moment execution starts, so `phase: planned` is the narrow, correct window that can only be true in the intended pre-execution period); without this explicit precedence, `--revise` would always hit the pre-existing halt row before ever reaching the new logic.
   Read `phase = _status.read_full(status_path)["yaml"].get("phase")` and the overview frontmatter's `approved:` field (via the file's existing YAML-block-extraction pattern already used elsewhere in this file for the `approved:` field).
   - If **both** `phase == "planned"` **and** `approved` is currently `true`: proceed with the revise action — (1) flip `approved: false` in `plan/00-overview.md` via the same direct-`Edit` convention already used elsewhere in this file for that field (no `_status.py` involvement, since `approved:` intentionally lives outside `status.md` per this file's own "## Board discipline" section); (2) call `_status.append_phase(status_path, "planning", <timestamp>)`; (3) commit both mutations together on the task branch in one commit (`git -C <worktree> add <plan_dir> <status_path> && git -C <worktree> commit -m "mill-plan: --revise re-open plan review for {slug}"`) and push; (4) bind `revise_from_blocked = False`; (5) fall through into the existing `phase: planning`/`plan-review-r{N}`/`plan-fix-r{N}` re-entry row (Phase: Plan Review; do NOT rewrite plan files) unmodified.
   - If `phase == "blocked"`: proceed with the blocked-resume action — (1) do NOT touch the overview's `approved:` field (it is already `false`); (2) call `_status.append_phase(status_path, "planning", <timestamp>)`; (3) commit on the task branch — `<plan_dir>` is deliberately NOT in this pathspec, unlike the `planned+approved` branch above, since this branch never touches `plan_dir` — `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-plan: --revise resume from blocked for {slug}"` and push; (4) bind `revise_from_blocked = True`; (5) fall through into the existing `phase: planning`/`plan-review-r{N}`/`plan-fix-r{N}` re-entry row (Phase: Plan Review; do NOT rewrite plan files) — same fallthrough target as the `planned+approved` branch above. `blocked_resume_round` is NOT computed here — it is deferred to Phase: Plan Review's own "Path Setup (Plan Review)" step, since `reviews_dir` does not exist yet at this point in Entry (see that section).
   - If `revise_requested` is set but neither of the two conditions above is met (`phase` is neither `"planned"` with `approved == true` nor `"blocked"`): halt with an explicit message naming the current `phase:` value and stating that revising a plan mill-go has already started executing, that has not yet been approved, or that is not currently blocked, is unsupported — do not silently force-flip `phase: planning` onto a task with committed/approved batches.
   - When `revise_requested` is not set, skip this entire pre-check and fall through to the existing table exactly as it is today.
```

- **Commit:** `docs(mill-plan): widen --revise pre-check to accept phase: blocked resume`

### Card 2: Add a `phase: blocked` row to the Entry step 4 phase table (#852)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  Depends on card 1 landing first (this card's row documents the no-`--revise` counterpart to card 1's pre-check branch, and both edit nearby but non-overlapping text in the same file — apply in card order to avoid Edit-tool ambiguity from a stale anchor).

  In the Entry step 4 phase table, locate this exact current text (3-space indented):

```
   | state | action |
   | --- | --- |
   | `phase: discussed`, no `plan_dir` dir at worktree root | Phase: Plan (fresh write) |
   | `phase: planning`/`plan-review-*`/`plan-fix-*`, `plan_dir/00-overview.md` exists, `approved: false` | Phase: Plan Review (re-enter loop; do NOT rewrite plan files) |
   | `approved: true` in overview frontmatter | Tell user: "plan already approved, run `/mill-go`". Halt. |
   | `phase: discussing` | wait for `phase: discussed` (see "Entry-gate wait for upstream mill-start" below) if `pipeline.entry_wait` is true; otherwise tell user what phase is set and halt |
   | any other phase (`planned`, …) | Tell user what phase is set and which skill should run instead. Halt. |
```

  Replace it with (same 3-space indentation for every line; the new row is inserted directly before the `any other phase` catch-all row):

```
   | state | action |
   | --- | --- |
   | `phase: discussed`, no `plan_dir` dir at worktree root | Phase: Plan (fresh write) |
   | `phase: planning`/`plan-review-*`/`plan-fix-*`, `plan_dir/00-overview.md` exists, `approved: false` | Phase: Plan Review (re-enter loop; do NOT rewrite plan files) |
   | `approved: true` in overview frontmatter | Tell user: "plan already approved, run `/mill-go`". Halt. |
   | `phase: discussing` | wait for `phase: discussed` (see "Entry-gate wait for upstream mill-start" below) if `pipeline.entry_wait` is true; otherwise tell user what phase is set and halt |
   | `phase: blocked` | surface `blocked_reason` from status.md and tell the operator to re-run `/mill-plan --revise` to resume plan review (or resolve manually); halt. This row is reached only when `--revise` was NOT passed — the `--revise` pre-check above already intercepts the `phase: blocked` case when `--revise` is set. |
   | any other phase (`planned`, …) | Tell user what phase is set and which skill should run instead. Halt. |
```

- **Commit:** `docs(mill-plan): add phase: blocked row to Entry step 4 phase table`

### Card 3: Fix the stale "no pre-existing blocked row" cross-reference in the Entry-gate wait section (#852)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  Depends on card 2 landing first (this card's rewritten sentence points at the row card 2 adds).

  In the `### Entry-gate wait for upstream mill-start` section, inside the `<event>` content branch list, locate this exact current text (4-space indented):

```
    - **`BLOCKED: <reason>`** — halt immediately, surfacing `<reason>` to the operator. mill-plan's phase table has no pre-existing `blocked` row to reuse the exact message shape from (unlike mill-go's side) — halt with a message of the same shape mill-plan already uses elsewhere for a `BLOCKED:`-prefixed halt (e.g. the Plan Review non-progress/max-rounds `_status.set_blocked` halts): state the phase is blocked and surface `<reason>` verbatim.
      Do not re-arm the wait automatically.
```

  Replace it with (same indentation: the first line at 4 spaces, the continuation line at 6 spaces):

```
    - **`BLOCKED: <reason>`** — halt immediately, surfacing `<reason>` to the operator. This halt is unrelated to the Entry-table's own `phase: blocked` row (see the phase table above) — that row reacts to this task's own `status.md` already being blocked before the wait even starts, whereas this branch reacts to the *upstream mill-start* wait's own script reporting a `BLOCKED:` line; halt with a message of the same shape mill-plan already uses elsewhere for a `BLOCKED:`-prefixed halt (e.g. the Plan Review non-progress/max-rounds `_status.set_blocked` halts): state the phase is blocked and surface `<reason>` verbatim.
      Do not re-arm the wait automatically.
```

- **Commit:** `docs(mill-plan): fix stale blocked-row cross-reference in entry-gate wait section`

### Card 4: Narrow the `revise-{N+1}` namespacing to exclude blocked-resume, and add the `blocked_resume_round`/`--max-rounds` threading rule (#852)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In `### Phase: Plan Review`, the `**Path Setup (Plan Review).**` section, locate this exact current text (no leading indentation — these are top-level paragraph lines):

```
**Path Setup (Plan Review).**
Derive: `reviews_dir = _paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])`.
Use this variable for all review file path references in this phase.

When `revise_requested` is set (carried forward from Step 0.5/step 4), compute a namespaced override before using `reviews_dir` for anything else in this phase: scan `<reviews_dir>/` for existing `revise-<N>` subdirectories (matching the literal pattern `revise-` followed by an integer), take the max `N` found (or `0` if none exist), and reassign `reviews_dir = reviews_dir / f"revise-{N+1}"` for the remainder of this phase.
This mirrors `discover_round`'s own `max(found) + 1` pattern (in `_review_common.py`), applied one level up at the subdirectory level, and supports any number of `--revise` passes on the same task over time — a second `--revise` (e.g. after the first revision was re-approved and mill-go later needs another correction) resolves to `revise-2`, never colliding with or overwriting `revise-1`'s files, since `RE_SIMPLE`/`RE_BATCH` (the fixed-shape filename regexes `discover_round` matches against) have no room for a distinguishing prefix and only work correctly once scoped to a distinct directory.
Every prepare/finalize CLI invocation dispatched later in this same Plan Review round (both the Agent-mode branch's `--stage prepare`/`--stage finalize` calls and the subprocess/psmux branch's `millpy-review-plan.py` invocation via `millpy-bg`) must pass a new `--reviews-subdir revise-{N+1}` flag whenever `revise_requested` is set, mirroring the existing `--reviewer` flag's documented contract: "override for this invocation only, nothing written back to config."
When `revise_requested` is not set, omit `--reviews-subdir` entirely and use `reviews_dir` exactly as resolved today — this override never activates for a normal (non-`--revise`) Plan Review run.
This namespacing does not alter `reviews_dir`'s use anywhere else in this file (e.g. Phase: Plan's own writes, which are unaffected by `--revise` since `--revise` only ever re-enters Phase: Plan Review, never Phase: Plan).
```

  Replace it with (no leading indentation, matching the original — a new paragraph is inserted before the namespacing paragraph, the namespacing paragraph's own condition is narrowed, and a new closing paragraph is appended):

```
**Path Setup (Plan Review).**
Derive: `reviews_dir = _paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])`.
Use this variable for all review file path references in this phase.

When `revise_from_blocked` is set (bound at Entry step 4's `--revise` pre-check), compute `blocked_resume_round = _review_common.discover_round(reviews_dir, "plan", "holistic")` against this plain, un-namespaced `reviews_dir`, before applying the namespacing override below.

When `revise_requested` is set **and `revise_from_blocked` is not set** (carried forward from Step 0.5/step 4), compute a namespaced override before using `reviews_dir` for anything else in this phase: scan `<reviews_dir>/` for existing `revise-<N>` subdirectories (matching the literal pattern `revise-` followed by an integer), take the max `N` found (or `0` if none exist), and reassign `reviews_dir = reviews_dir / f"revise-{N+1}"` for the remainder of this phase.
This mirrors `discover_round`'s own `max(found) + 1` pattern (in `_review_common.py`), applied one level up at the subdirectory level, and supports any number of `--revise` passes on the same task over time — a second `--revise` (e.g. after the first revision was re-approved and mill-go later needs another correction) resolves to `revise-2`, never colliding with or overwriting `revise-1`'s files, since `RE_SIMPLE`/`RE_BATCH` (the fixed-shape filename regexes `discover_round` matches against) have no room for a distinguishing prefix and only work correctly once scoped to a distinct directory.
Every prepare/finalize CLI invocation dispatched later in this same Plan Review round (both the Agent-mode branch's `--stage prepare`/`--stage finalize` calls and the subprocess/psmux branch's `millpy-review-plan.py` invocation via `millpy-bg`) must pass a new `--reviews-subdir revise-{N+1}` flag whenever `revise_requested` is set and `revise_from_blocked` is not set, mirroring the existing `--reviewer` flag's documented contract: "override for this invocation only, nothing written back to config."
When `revise_requested` is not set, or `revise_from_blocked` is set, omit `--reviews-subdir` entirely and use `reviews_dir` exactly as resolved today — this override never activates for a normal (non-`--revise`) Plan Review run, nor for a blocked-resume `--revise` (a blocked-resume is a continuation of the same never-approved round sequence, not a fresh revision pass over an approved plan — reviews continue writing into the plain `reviews_dir`, picking up at `blocked_resume_round` via the normal `discover_round` mechanism).
This namespacing does not alter `reviews_dir`'s use anywhere else in this file (e.g. Phase: Plan's own writes, which are unaffected by `--revise` since `--revise` only ever re-enters Phase: Plan Review, never Phase: Plan).

**`--max-rounds` threading for blocked-resume (`revise_from_blocked` only).** When `revise_from_blocked` is set **and** the current loop's `round == blocked_resume_round`: every prepare/finalize CLI invocation dispatched in step 2's dispatch below for that one round only (both the Agent-mode branch's `<args>` and the subprocess/psmux branch's `millpy-review-plan.py` invocation via `millpy-bg`) must additionally pass `--max-rounds <blocked_resume_round>`, mirroring the exact `--reviews-subdir revise-{N+1}` threading pattern above and mill-start's `--auto` extension-round mechanism (`--max-rounds <max_review_rounds + 1>`). Omit `--max-rounds` on every other round, including subsequent rounds within the same blocked-resume `--revise` invocation once `round` has advanced past `blocked_resume_round`. This override exists so the CLI's own round-cap guard (`round_n > max_rounds` raises a hard error) does not reject the resumed round — it is never itself a signal to run more rounds than the loop's existing convergence/step-6 logic would otherwise allow.
```

- **Commit:** `docs(mill-plan): narrow revise-subdir namespacing and add blocked-resume max-rounds threading`

### Card 5: Add the missing `_status.set_blocked` call to Step 1.5's two-pass cap (#852)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In `### Phase: Plan Review`, `**Step 1.5: pre-review validator gate (auto-run, no round consumed)**`, locate this exact current text (3-space indented):

```
   - **Two-pass cap:** if the validator fails again on the second pass, mill-plan halts with `BLOCKED: plan-validate non-progress` and writes the unresolved errors to the user.
     Do NOT auto-retry beyond the second pass.
     The two-pass cap matches the `roles.implementer.self_fix_rounds` self-fix pattern.
```

  Replace it with (same indentation: first line at 3 spaces, continuation lines at 5 spaces):

```
   - **Two-pass cap:** if the validator fails again on the second pass, immediately before halting, call `_status.set_blocked(status_path, "plan-validate non-progress", timestamp=_timestamp.now_utc_iso())`; commit on the task branch (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-plan: blocked (plan-validate non-progress) for {slug}"`) and push. Then mill-plan halts with `BLOCKED: plan-validate non-progress` and writes the unresolved errors to the user.
     Do NOT auto-retry beyond the second pass.
     The two-pass cap matches the `roles.implementer.self_fix_rounds` self-fix pattern.
```

- **Commit:** `docs(mill-plan): set_blocked before Step 1.5's two-pass-cap halt`

### Card 6: Add the missing `_status.set_blocked` calls to Step 4.5's two-pass cap (#852)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In `### Phase: Plan Review`, `**Step 4.5: ERROR-only-aggregate retry (no round consumed)**`, locate this exact current text (3-space indented):

```
   The round counter is **not** consumed — the round produced no reviewable output.
   Absent-JSON and `verdict: ERROR` share **one consecutive-non-reviewable-round counter**: any mix of two consecutive non-reviewable rounds (ERROR then absent-JSON, or vice versa) triggers the two-pass cap.
   On the **second** consecutive non-reviewable run, halt: if it was absent-JSON, report `BLOCKED: plan review no-JSON round {N}` and surface the last stderr line(s) from the bg log;
   if it was `verdict: ERROR`, report `BLOCKED: review ERROR-only round {N}` and surface each entry's `error` string to the user.
   Do NOT auto-retry beyond the second pass.
   The two-pass cap mirrors step 1.5's validator gate. *(Note: the CLI now emits a `verdict: ERROR` envelope on uncaught exceptions per millpy-review-plan.py, so a true absent-JSON line means the worker died before printing — mirroring mill-go's "only treat exit 1 as unrecoverable when the JSON line is absent" rule.
   Closes #84 — `verdict: ERROR` tracking was introduced so ERROR rounds never silently collapse into 4c's NIT path.)*
```

  Replace it with (same 3-space indentation for every line):

```
   The round counter is **not** consumed — the round produced no reviewable output.
   Absent-JSON and `verdict: ERROR` share **one consecutive-non-reviewable-round counter**: any mix of two consecutive non-reviewable rounds (ERROR then absent-JSON, or vice versa) triggers the two-pass cap.
   On the **second** consecutive non-reviewable run, immediately before halting: if it was absent-JSON, call `_status.set_blocked(status_path, f"plan review no-JSON round {N}", timestamp=_timestamp.now_utc_iso())`; commit (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-plan: blocked (plan review no-JSON round {N}) for {slug}"`) and push; then halt, reporting `BLOCKED: plan review no-JSON round {N}` and surfacing the last stderr line(s) from the bg log.
   If it was `verdict: ERROR`, call `_status.set_blocked(status_path, f"review ERROR-only round {N}", timestamp=_timestamp.now_utc_iso())`; commit (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-plan: blocked (review ERROR-only round {N}) for {slug}"`) and push; then halt, reporting `BLOCKED: review ERROR-only round {N}` and surfacing each entry's `error` string to the user.
   Do NOT auto-retry beyond the second pass.
   The two-pass cap mirrors step 1.5's validator gate. *(Note: the CLI now emits a `verdict: ERROR` envelope on uncaught exceptions per millpy-review-plan.py, so a true absent-JSON line means the worker died before printing — mirroring mill-go's "only treat exit 1 as unrecoverable when the JSON line is absent" rule.
   Closes #84 — `verdict: ERROR` tracking was introduced so ERROR rounds never silently collapse into 4c's NIT path.)*
```

- **Commit:** `docs(mill-plan): set_blocked before Step 4.5's two-pass-cap halts`

### Card 7: Correct the Go `-tags` remedy in the Step 1.5 fix table's `verify-excludes-edited-tagged-test` row (#853)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In the Step 1.5 fix table, locate this exact current row (3-space indented, single line):

```
   | verify-excludes-edited-tagged-test | Open the offending batch's verify: command (payload's batch/path fields name the batch and the tagged test file; the payload's message field names the missing tag in its trailing "naming '<tag>'" fragment). If a -tags flag already exists, append ,<tag> to its value; otherwise append " -tags <tag>" to the command. |
```

  Replace it with (same 3-space indentation, single line — only the "already exists" branch's remedy changes; the "otherwise" branch is kept verbatim):

```
   | verify-excludes-edited-tagged-test | Open the offending batch's verify: command (payload's batch/path fields name the batch and the tagged test file; the payload's message field names the missing tag in its trailing "naming '<tag>'" fragment). If a `-tags` flag already exists on the command: do not comma-join `<tag>` into its value. Note this is a defense-in-depth choice, not a correction of broken Go semantics — Go's `-tags` set is satisfied by ANY-membership (each file's own `//go:build` line is checked independently against the full enabled-tag set, so a plain single-tag `//go:build scout` file is compiled/run whenever `scout` is enabled, regardless of what else is also enabled; `-tags integration,scout` does NOT exclude it). The real risk is project-specific: some repos deliberately give tagged suites mutually exclusive semantics (a suite's own constraint combines its tag with a negation of a sibling suite's tag, e.g. to keep suites isolated for cost/reporting reasons) — comma-joining silently breaks that convention if it's in use, and this check cannot tell whether a given project relies on it. Instead, append a new ` && `-chained invocation of the same base command (same verb and package pattern as the existing invocation) carrying its own `-tags <tag>` flag — strictly safer, since it never assumes either way. Otherwise (no `-tags` flag anywhere in the command yet): append `" -tags <tag>"` to the command in place, unchanged. |
```

- **Commit:** `docs(mill-plan): fix Go -tags remedy in verify-excludes-edited-tagged-test row`

## Batch Tests

This batch edits only `plugins/mill/skills/mill-plan/SKILL.md` — a Markdown prose/control-flow file with no runnable surface, hence `verify: null` at both the module-wide (overview) and batch level. Per `_mill/discussion.md`'s Testing section, no new Python unit test is warranted: neither #852 nor #853 introduces a new executable code path, and the machinery this batch reuses or reorders (`_status.set_blocked`, `_status.append_phase`, `_review_common.discover_round`, `millpy-review-plan.py`'s existing `--max-rounds` flag, `_plan_validate.py`'s `_verify_command_has_any_tag`) is already covered by existing tests and is not itself modified.

Verification instead happens as a manual control-flow trace during mill-plan's own Phase: Plan Review self-checks, per the two traces `_mill/discussion.md`'s Testing section specifies:

- **#852 trace** (cards 1-6): confirm (a) the widened `--revise` pre-check's two conditions (`planned+approved==true` OR `blocked`) are mutually exclusive branches with a shared "neither met" halt; (b) `revise_from_blocked` is bound `True` only on the `blocked` branch, `revise_requested` is set on both branches, and `blocked_resume_round`/`--max-rounds` threading is gated on `revise_from_blocked` (not the bare `revise_requested`) into exactly one round's dispatch, both call sites (Agent-mode and subprocess); (c) the `revise-{N+1}` namespacing override at Phase: Plan Review Path Setup fires for a planned+approved `--revise` but NOT for a blocked-resume `--revise`; (d) the new Entry-table `blocked` row (no-`--revise` case) is reached only when the pre-check does *not* intercept; (e) all four `BLOCKED:`-halt sites (step 1.5, step 4.5 x2, step 5, step 6) now call `_status.set_blocked` before halting — trace at least one Category A site (step 6: single self-terminating round) and one Category B site (step 1.5 or step 5: resumes with the loop's full remaining budget) end-to-end through to a successful `--revise` resume.
- **#853 trace** (card 7): confirm the rewritten fix-table row still leaves the "no `-tags` yet" branch's example output identical to before (`go vet -tags scout ./...`), and that the "already exists" branch's example output for the issue's own repro (existing `-tags integration`, needs `scout`) produces `go vet -tags integration ./... && go vet -tags scout ./...`.
