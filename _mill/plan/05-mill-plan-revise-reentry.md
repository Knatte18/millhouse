# Batch: mill-plan-revise-reentry

```yaml
task: 'mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2)'
batch: mill-plan-revise-reentry
number: 5
cards: 3
verify: null
depends-on: []
```

## Batch Scope

`#786`: adds a new `--revise` re-entry mode to `mill-plan/SKILL.md`, letting an operator re-open Plan Review on an already-approved plan (e.g. after upstream `main` changes made the plan's Context:/Requirements: stale) without mill-go having started execution.
Three edits, in the order the file itself would encounter them: (1) a new "Step 0.5 — Parse arguments" section between Entry Step 0 and Step 1, recognizing `--revise` and setting a local `revise_requested` flag; (2) a new pre-check row in Entry step 4's phase-decision table, checked before every existing row, that validates `--revise` is only usable from `phase: planned` + `approved: true` and performs the revise action (flip `approved: false`, append `planning` phase, commit, fall through to the existing re-entry row); (3) a reviews-directory namespacing addition to Phase: Plan Review's "Path Setup (Plan Review)" subsection, giving each revision pass its own `revise-<N>/` subdirectory so `discover_round` (in `_review_common.py`) starts fresh at round 1 instead of silently inheriting whatever round budget the original approved pass already consumed.
This batch is the `SKILL.md`-prose half of `#786`; the companion `--reviews-subdir` CLI-flag plumbing through `_review_plan.py`'s `prepare()`/`run()` and `millpy-review-plan.py`'s `--stage finalize` handler lives in a separate batch (`review-plan-reviews-subdir-plumbing`, batch 6) — the two batches touch disjoint files and carry no DAG dependency; this batch's card 14 describes calling the CLI with `--reviews-subdir <name>` under the assumption the flag exists, exactly as it already describes calling with the existing `--reviewer` override flag today.
No batch-local decisions differ from `## Shared Decisions` in the overview — this batch is squarely governed by `doc-batches-preserve-file-conventions`: Entry Step 0/Step 0.5 use a bold-lead-in un-numbered-paragraph style (neither is part of the "1./2./3./4." numbered list that follows), matching Step 0's own existing style exactly; the numbered list itself (steps 1-4) is untouched and unrenumbered.

## Cards

### Card 12: Add Entry Step 0.5 — Parse arguments

- **Context:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the frontmatter block at the top of the file (between `name: mill-plan` and `description: ...`), add a new `argument-hint: "[--revise]"` line, matching `mill-setup/SKILL.md`'s frontmatter convention (its `argument-hint: "[--from-url <url>] [--branch <name>]"` line).
  In the `## Entry` section, immediately after Step 0's text ("**Step 0: Load `mill:conversation`.**" and its two sentences) and immediately before the numbered list item "1. Resolve and bind the path variables:", insert a new bold-lead-in paragraph "**Step 0.5 — Parse arguments.**" (not a numbered list item — Step 0 and Step 0.5 both precede the "1./2./3./4." list, matching Step 0's own existing un-numbered style).
  Follow `mill-setup/SKILL.md`'s "### Phase 0 — Parse arguments" token-walk convention exactly (read `$ARGUMENTS`; token-walk left-to-right; one bullet per recognized token; a final catch-all bullet with a blockquoted usage hint), adapted to mill-plan's single flag:
  "Read `$ARGUMENTS`. Token-walk left-to-right:" followed by a bullet "`--revise` — set a local `revise_requested = True`. May appear at most once." followed by a bullet "Any other token: halt with usage hint:" followed by a blockquoted two-line usage message ("Unknown argument: `<token>` in `$ARGUMENTS`" then "usage: `/mill-plan [--revise]`").
  State explicitly that Step 0.5 does tokenization only — it does not validate `phase:`/`approved:` itself, since `status_path` isn't resolved until "Path Setup" (which runs after Entry steps 1-3) and `plan_dir` isn't derived during Entry at all today; the actual `--revise` validation is Card 13's new step 4 table row, which already has both values in scope.
  Do not renumber the existing "1. Resolve and bind..." / "2. Load config..." / "3. Read the slug..." / "4. Read `status_path`..." list — Step 0.5 sits before it as an un-numbered paragraph, exactly like Step 0 does.
- **Commit:** `docs(mill-plan): add Entry Step 0.5 --revise argument parsing`

### Card 13: Add `--revise` pre-check row to Entry step 4's phase table

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  This card depends on Card 12 having already introduced the `revise_requested` local variable in Step 0.5 — this card consumes it.
  In Entry step 4 ("Read `status_path` and inspect `phase:` + the plan state on disk...Decide entry branch:"), immediately before the existing markdown table (`| state | action |` ... down through the `| any other phase (\`planned\`, …) | ... |` row), insert a new paragraph stating: whenever `revise_requested` is set (from Step 0.5), this pre-check runs **before** every row of the table below, as a distinct pre-check, not merely appended after it — this ordering is required because the table's existing `| approved: true in overview frontmatter | Tell user: "plan already approved, run /mill-go". Halt. |` row is unconditional on `phase:`, and its condition (`approved: true`) is also satisfied throughout the entire `phase: planned` window `--revise` targets (since `approved:` stays `true` for the whole duration of mill-go's later run too — mill-go's own Prepare step immediately overwrites `phase: planned` to `phase: implementing` the moment execution starts, so `phase: planned` is the narrow, correct window that can only be true in the intended pre-execution period); without this explicit precedence, `--revise` would always hit the pre-existing halt row before ever reaching the new logic.
  State the pre-check's condition and action precisely: read `phase = _status.read_full(status_path)["yaml"].get("phase")` and the overview frontmatter's `approved:` field (via the file's existing YAML-block-extraction pattern already used elsewhere in this file for the `approved:` field).
  If **both** `phase == "planned"` **and** `approved` is currently `true`: proceed with the revise action — (1) flip `approved: false` in `plan/00-overview.md` via the same direct-`Edit` convention already used elsewhere in this file for that field (no `_status.py` involvement, since `approved:` intentionally lives outside `status.md` per this file's own "## Board discipline" section); (2) call `_status.append_phase(status_path, "planning", <timestamp>)`; (3) commit both mutations together on the task branch in one commit (`git -C <worktree> add <plan_dir> <status_path> && git -C <worktree> commit -m "mill-plan: --revise re-open plan review for {slug}"`) and push; (4) fall through into the existing `phase: planning`/`plan-review-r{N}`/`plan-fix-r{N}` re-entry row (Phase: Plan Review; do NOT rewrite plan files) unmodified — do not duplicate that row's action text, just state that execution falls through to it.
  If `revise_requested` is set but the condition is **not** met (any phase other than `planned`, or `approved` is not `true`): halt with an explicit message naming the current `phase:` value and stating that revising a plan mill-go has already started executing (or has not yet been approved) is unsupported — do not silently force-flip `phase: planning` onto a task with committed/approved batches.
  When `revise_requested` is not set, skip this entire pre-check and fall through to the existing table exactly as it is today — do not alter any existing row's text.
- **Commit:** `docs(mill-plan): add --revise pre-check row to Entry step 4 phase table`

### Card 14: Give `--revise` its own reviews-directory round-numbering namespace in Phase: Plan Review

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  This card depends on Card 12/13 having threaded `revise_requested` forward from Step 0.5 through step 4's validated action.
  In "### Phase: Plan Review"'s "**Path Setup (Plan Review).**" subsection, which currently reads only "Derive: `reviews_dir = _paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])`. Use this variable for all review file path references in this phase.", insert new text immediately after that sentence: when `revise_requested` is set (carried forward from Step 0.5/step 4), compute a namespaced override before using `reviews_dir` for anything else in this phase — scan `<reviews_dir>/` for existing `revise-<N>` subdirectories (matching the literal pattern `revise-` followed by an integer), take the max `N` found (or `0` if none exist), and reassign `reviews_dir = reviews_dir / f"revise-{N+1}"` for the remainder of this phase.
  State that this mirrors `discover_round`'s own `max(found) + 1` pattern (in `_review_common.py`), applied one level up at the subdirectory level, and that this supports any number of `--revise` passes on the same task over time — a second `--revise` (e.g. after the first revision was re-approved and mill-go later needs another correction) resolves to `revise-2`, never colliding with or overwriting `revise-1`'s files, since `RE_SIMPLE`/`RE_BATCH` (the fixed-shape filename regexes `discover_round` matches against) have no room for a distinguishing prefix and only work correctly once scoped to a distinct directory.
  State that every prepare/finalize CLI invocation dispatched later in this same Plan Review round (both the Agent-mode branch's `--stage prepare`/`--stage finalize` calls and the subprocess/psmux branch's `millpy-review-plan.py` invocation via `millpy-bg`) must pass a new `--reviews-subdir revise-{N+1}` flag whenever `revise_requested` is set, mirroring the existing `--reviewer` flag's documented contract: "override for this invocation only, nothing written back to config." When `revise_requested` is not set, omit `--reviews-subdir` entirely and use `reviews_dir` exactly as resolved today — this override never activates for a normal (non-`--revise`) Plan Review run.
  Do not alter `reviews_dir`'s use anywhere else in this file (e.g. Phase: Plan's own writes, which are unaffected by `--revise` since `--revise` only ever re-enters Phase: Plan Review, never Phase: Plan).
- **Commit:** `docs(mill-plan): namespace --revise's reviews_dir into revise-<N> subdirectories`

## Batch Tests

`verify: null` — every card in this batch is a `SKILL.md` prose edit describing new orchestrator argument-parsing and re-entry behavior; there is no executable surface to run (per `_mill/discussion.md`'s Testing section: "End-to-end behavior (the full `--revise` flow) is not mechanically testable without a live mill-plan session").
Verification is a careful re-read confirming: Step 0.5 sits before the existing numbered list without renumbering it; the new step 4 pre-check row is evaluated strictly before the table's existing rows (so the unconditional `approved: true` halt row can never shadow it); and the `revise-<N+1>` subdirectory computation and `--reviews-subdir` flag-passing convention match batch 6's actual CLI-flag implementation once that batch lands.
