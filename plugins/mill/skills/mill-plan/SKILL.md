---
name: mill-plan
description: In a spawned worktree with a committed discussion.md, autonomously write a batch-based implementation plan, self-review it via mill-review-plan, and hand off to mill-go.
---

# mill-plan

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

You are an autonomous planner running on Opus. Your job is to turn `discussion.md` into an implementation plan detailed enough that a Sonnet-class builder can execute it with zero further human input. Never pause mid-phase to ask the user. Only the max-rounds escape (below) is allowed to break that rule.

## Entry

1. Resolve the wiki path via `_paths.resolve_wiki_path(_paths.resolve_git_root())`.
   `signature: _paths.resolve_git_root(start: Path | None = None) -> Path`
   `signature: _paths.resolve_wiki_path(git_toplevel: Path) -> Path`
2. Read the slug via `_marker.slug_from_branch(git_root, wiki_path, cfg)`. On `MarkerError` → halt with "this worktree was not created by mill-spawn".
3. Load config — deep-merge `<hub_root>/mill-config.yaml` with `.millhouse/config.local.yaml`. Read `roles.plan-review.holistic.rounds` as `max_review_rounds`.
   `signature: _config.load_config(hub_root: Path, worktree_root: Path) -> dict`

**Path Setup.** Derive from config: `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])`. `plan_dir` and `reviews_dir` will be derived during Phase: Plan (writes) or Phase: Plan Review (reads) as appropriate — see those phases for details.

4. Read `status_path` and inspect `phase:` + the plan state on disk (no `plan_dir` dir at worktree root, using `cfg['paths']['plan_dir']`). Decide entry branch:

   | state | action |
   | --- | --- |
   | `phase: discussed`, no `plan_dir` dir at worktree root | Phase: Plan (fresh write) |
   | `phase: planning`/`plan-review-*`/`plan-fix-*`, `plan_dir/00-overview.md` exists, `approved: false` | Phase: Plan Review (re-enter loop; do NOT rewrite plan files) |
   | `approved: true` in overview frontmatter | Tell user: "plan already approved, run `/mill-go`". Halt. |
   | any other phase (`discussing`, `planned`, …) | Tell user what phase is set and which skill should run instead. Halt. |

## Phases

Report the current phase to the user at each transition.

### Phase: Plan

Read `_mill/discussion.md` in full. Read `CONSTRAINTS.md` at the hub root if present (via `_constraints.read_if_exists()`). Then **think the plan through end-to-end before writing any file** — you are Opus and this is exactly where the planning budget pays off.

**Batch sizing.** A batch is a *smart unit*: code that logically belongs together and that a Sonnet builder with a 200k-token context window can hold in its head while implementing. Split on natural module/subsystem boundaries, not on file count. If a proposed batch would force Sonnet to load the entire codebase to understand its own `Context:` list, split it. If two adjacent batches share >80% of their `Context:`, merge them.

**Write the files.**

**YAML-quoted tokens for fenced blocks.** Tokens destined for YAML blocks must be pre-quoted; heading tokens remain raw. Heading tokens (`<TASK_TITLE>`, `<BATCH_NAME>`) substitute directly into H1 lines (raw form). YAML-block tokens (`<TASK_TITLE_YAML>`, `<BATCH_NAME_YAML>`) substitute into fenced yaml blocks (quoted form via `_yaml_writer.quote_scalar`). This separation lets templates use both forms without repeating quote logic. Concretely:

```python
from _yaml_writer import quote_scalar
tokens = {
    "TASK_TITLE":      task_title,
    "TASK_TITLE_YAML": quote_scalar(task_title),
    "SLUG":            quote_scalar(slug),
    "STARTED":         quote_scalar(_timestamp.now_utc_compact()),
    "PARENT_BRANCH":   quote_scalar(parent_branch),
}
overview_text = _render.render(template_path, tokens)
```

Apply the same pattern when rendering `plan-batch.md` for each batch:

```python
tokens["BATCH_NAME"]      = batch_name
tokens["BATCH_NAME_YAML"] = quote_scalar(batch_name)
tokens["BATCH_SLUG"]      = batch_slug
```

1. Render `plugins/mill/templates/plan-overview.md` into `<plan_dir>/00-overview.md` using the pre-quoted tokens dict.
2. Fill the Batch Index DAG, Shared Decisions, and All Files Touched sections in place. Set `number:` for each entry to the NN integer from the batch filename. Write `depends-on:` as a list of integers (e.g., `depends-on: [1]` meaning this batch depends on batch number 1). Leave `depends-on: []` for root batches.
3. For each batch, render `plugins/mill/templates/plan-batch.md` into `<plan_dir>/NN-<batch-slug>.md` using the pre-quoted tokens dict. Fill Batch Scope + Cards + Batch Tests. Set `number: NN` in the rendered frontmatter to the batch's integer (same as the filename prefix).

**Card numbering is global across batches**: card 1 lives in batch 01, card 7 might live in batch 02, etc. Never restart at 1 inside each batch — the reviewer and implementer cite cards by number and need uniqueness.

**Verify command shape.** Every non-null `verify:` in a per-batch file's frontmatter MUST start with the literal token `PYTHONPATH=` followed by a single space and then the command. The empty value on the same line scopes the `PYTHONPATH` reset to that one command, so the test subprocess does not inherit the mill cache scripts dir from the parent shell and tests load worktree modules instead of stale cache modules. The validator check `verify-not-isolated` enforces this; see the Step 1.5 fix table.

**Verify command scope.** `verify:` runs after every implementer round and every fixer round — many times per batch. Target only the tests affected by this batch's `Edits:` + `Creates:` — DO NOT use `run-all.py` without `--only` for a focused batch (the full 77-file suite is multiple minutes). Patterns:
- **Single test file:** `verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-fold.py`
- **Multiple files:** `verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-fold.py test-marker.py` — `run-all.py --only <basenames...>` runs only the named files (unknown names error out).

A batch that legitimately touches a cross-cutting helper that every test imports MAY use the unbounded `run-all.py` — but state the justification in `## Batch Tests` so the plan reviewer can validate the scope choice. The default expectation is per-batch scoping.

**Self-validate the DAG** before committing: call `_plan_dag.extract_batch_index(overview_text)` then `_plan_dag.validate(batches, sorted(p.name for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"))`. Any `PlanDAGError` → fix the plan files, then re-validate. Do not commit a plan that fails this check.

`signature: _status.read(status_path: Path) -> dict`

**Update `_mill/status.md`.**

- `plan_dir = worktree_root / cfg['paths']['plan_dir']` (config-canonical; write path).
- `_status.update_field(status_path, "plan", cfg['paths']['plan_dir'].rstrip('/'))` — pointer to the plan dir (worktree-relative).
- `_status.append_phase(status_path, "planning", _timestamp.now_utc_iso())`.

**Commit on the task branch.** `git -C <worktree> add <plan_dir> <status_path> && git commit -m "mill-plan: write plan for {slug}"`.

### Phase: Plan Review

**Path Setup (Plan Review).** Derive: `reviews_dir = _paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])`. Use this variable for all review file path references in this phase.

The new schema has two skip conditions: `rounds: 0` OR `reviewer: null` means "skip plan review". If `roles.plan-review.holistic.rounds == 0` OR `roles.plan-review.holistic.reviewer` is `None`: set overview frontmatter `approved: true` via direct Edit, commit on the task branch (`git -C <worktree> add <plan_dir> && git commit -m "mill-plan: skip plan review (reviewer null or rounds 0) for {slug}"`), push, and proceed straight to Handoff. The skip is recorded in commit history; no `status.md` phase flip beyond the existing Handoff `planned` row.

Loop up to `max_review_rounds` rounds. Each round:

1. Report: **"Plan Review — round N/max_review_rounds"**.

1.5. **Step 1.5: pre-review validator gate (auto-run, no round consumed)**

   - The CLI auto-runs `_plan_validate` before invoking the LLM. If the validator finds anything, the CLI exits 1 with a JSON envelope on stdout (`{"errors": [...], "summary": "<n> finding(s) across <m> batch(es)"}`). No review file is written; no LLM token is spent; no review round is consumed.
   - On validator-failure exit, mill-plan parses the JSON and applies one mechanical fix per error dict, per the mapping table below. After fixes, mill-plan re-runs the review CLI via millpy-bg (slug `plan-validator-fix`; still no round consumed). Poll `cat <log-path>` until `[mill-bg] EXIT`, then run `grep '^{' <log-path> | tail -1` to extract the JSON line.
   - **Two-pass cap:** if the validator fails again on the second pass, mill-plan halts with `BLOCKED: plan-validate non-progress` and writes the unresolved errors to the user. Do NOT auto-retry beyond the second pass. The two-pass cap matches the `roles.implementer.self_fix_rounds` self-fix pattern.
   - If `pipeline.skip_validate: true` ever appears in config (currently it does not; this is a future hook), pass `--skip-validate` to the CLI and skip step 1.5 entirely. mill-plan passes `--skip-check wiki-config-mutation` only when the fix table instructs it — see the `wiki-config-mutation` row.

   | check                          | mechanical fix                                                                                                  |
   | ------------------------------ | ----------------------------------------------------------------------------------------------------------- |
   | non-existent-path              | If the path is a typo of an existing file, correct it. If it is meant to be a Creates: target in this plan, move it from Context:/Edits: to Creates: in the appropriate card. If neither applies, the planner intended to read a file that does not exist — halt; this is not mechanically fixable. |
   | card-missing-field             | Add the missing field with a sensible default: Context: → list the file(s) the requirement names; Edits: → none if the card creates a new file only; Creates: → none if the card edits an existing file only; Requirements: → restate the card title as a one-sentence requirement; Commit: → derive from the card title using the existing conventional-commit prefix pattern. |
   | card-numbering                 | Renumber cards within the affected batch sequentially starting at the lowest existing number; if the conflict is across batches, re-number the later-batch's cards to start above the earlier batch's max. Update every "card N" reference inside the plan. |
   | depends-on-unknown             | If the unknown dep is an integer, compare it against the `number:` values in the Batch Index — if close to an existing number (likely a typo), correct it. If the unknown dep is a string (legacy format), compare it against the `name:` values — if it is a typo of an existing entry, correct it. If the dependency genuinely needs a new batch, halt — adding a batch is not a mechanical fix. |
   | parallel-modifies-overlap      | If one batch logically depends on the other, add the missing edge to the dependent's depends-on list. If the two batches truly need to write to the same file in parallel, the plan is structurally wrong — halt.        |
   | reads-not-backtick-path        | Re-format the bullet to backtick-only paths; move any inline parenthetical commentary to the card's Requirements: prose. Strip any line-range suffix (e.g. `:55-65`) from the path.                                       |
   | all-files-touched-mismatch     | Update the overview's All Files Touched to match the union of every card's Edits: + Creates:. (The overview list is derivative; the cards are the source of truth.)                                                |
   | verify-not-isolated            | Open the per-batch file named by the error payload's `batch:` field (resolve `_mill/plan/<batch>.md`). Read the offending command from the payload's `path:` field. Replace the frontmatter line `verify: <original>` with `verify: PYTHONPATH= <original>` (literal `PYTHONPATH=`, single space, original command). One row, one prepend. |
   | wiki-config-mutation           | This check cannot be fixed by editing plan files — the batch intentionally modifies `wiki/config.yaml`. To proceed, verify one of two conditions: (a) a bootstrap card is present — a card whose body explains why the config.yaml change is safe mid-flight for the currently-shipping task; or (b) the modified keys are provably unused — meaning key *removal or rename* where zero grep hits across `scripts/` and `skills/` confirm no existing code references them. (For key *addition* where consuming code is also being added in the same plan, zero grep hits does NOT satisfy condition (b); use (a) or halt.) If either condition holds: document the justification in the validator-fix commit message and re-run the CLI with `--skip-check wiki-config-mutation`. If `wiki-config-mutation` co-occurs with other fixable validator errors, fix those first per their rows, then re-run with `--skip-check wiki-config-mutation`. If neither condition holds: halt — the plan requires redesign. |
   | missing-overview               | Halt — the plan is structurally broken, not mechanically fixable.                                                                                                                                                       |
   | batch-index-parse              | Halt — the overview's fenced-yaml block is unparseable; not mechanically fixable.                                                                                                                                        |

   Rows where the fix is "halt" are deliberate: those errors signal a structural planning bug that auto-fixing would mask. The two-pass cap fires for these too (the second pass will produce the same error and trigger halt).

   After applying mechanical fixes for every error in the JSON, mill-plan commits the fix(es) on the task branch: `git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "mill-plan: validator-fix pass for {slug}"` and re-runs the CLI. The commit message uses `validator-fix` to distinguish it from `plan-fix-r{N}` commits (which are LLM-fix-pass commits).

   Before re-running via millpy-bg for the `plan-validator-fix` slug, verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

2. Invoke the CLI as a subprocess:

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug plan-review-r<N> -- \
       "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-plan.py"
   ```

   The CLI accepts two optional scope flags (mutually exclusive): `--holistic-only` skips per-batch reviews and runs only the holistic plan review; `--no-holistic` skips the holistic plan review and runs per-batch reviews only. Default — both run per the `roles.plan-review.batch.reviewer` and `roles.plan-review.holistic.reviewer` config keys. Append the flag to the inner `uv run …millpy-review-plan.py` portion of the millpy-bg invocation when needed.

   This returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then run `grep '^{' <log-path> | tail -1` to extract the JSON summary line.

   The script discovers the slug and round from disk. It prints one JSON line: `{"type": "plan", "round": N, "verdict": "APPROVE" | "REQUEST_CHANGES", "blocking_count": N, "reviews": [...]}` where each review entry has `{scope, verdict, file}`.

3. **BEFORE reading any review file, load the `mill-receiving-review` skill** (`plugins/mill/skills/mill-receiving-review/SKILL.md`). Non-negotiable. The VERIFY → HARM CHECK → FIX-or-PUSH-BACK decision tree is what keeps review loops useful.

4a. On `APPROVE` (verdict from JSON) with zero `[NIT]` findings (read the review file at `reviews[0].file` and confirm zero `[NIT]`-prefixed findings): set overview frontmatter `approved: true` via direct Edit. `_status.append_phase(status_path, f"plan-review-r{N}", iso_ts)`. Commit on the task branch: `git -C <worktree> add <plan_dir> <reviews_dir> <status_path> && git -C <worktree> commit -m "mill-plan: approve plan for {slug}"`. Push. Break loop → Handoff. `iso_ts` is `_timestamp.now_utc_iso()`.

4b. On `APPROVE` with one or more `[NIT]` findings: apply each NIT per the `mill-receiving-review` decision tree by editing the plan files directly. Write a fixer report at `<reviews_dir>/<YYYYMMDD-HHMMSS>-plan-fix-r<N>.md` (timestamp from `_timestamp.now_utc_compact()`) with two sections — `## Fixed` (one line per fixed NIT: short reference to the source review file + quoted finding title) and `## Pushed Back` (one line per rejected NIT: short reference + reason citing code, doc, or scope per `mill-receiving-review`'s legitimate-pushback rules). Re-validate the plan DAG via `_plan_dag.validate`. Call `_status.append_phase(status_path, f"plan-fix-r{N}", iso_ts)`. Set overview frontmatter `approved: true` via direct Edit. Single git commit covering exactly three pathspecs — `<plan_dir>`, `<reviews_dir>`, `<status_path>` — with message `mill-plan: plan-fix round {N} for {slug}` (matches existing 4d message shape; the round counter is NOT advanced). Push. Break loop → Handoff.

4.5. **Step 4.5: ERROR-only-aggregate retry (no round consumed)**

   When the JSON envelope from step 2 has a non-empty `reviews[]` array AND at least one entry's `verdict` is `"ERROR"`, skip steps 4a/4b/4c/4d entirely and immediately re-run:

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug plan-review-retry-r<N> -- \
       "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-plan.py"
   ```

   This returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then run `grep '^{' <log-path> | tail -1` to extract the JSON summary line.

   The round counter is **not** consumed — the round produced no reviewable output. On the **second** consecutive run that still contains any `"ERROR"` entry, halt with `BLOCKED: review ERROR-only round {N}` and surface each entry's `error` string to the user. Do NOT auto-retry beyond the second pass. The two-pass cap mirrors step 1.5's validator gate. *(Closes #84 — `verdict: ERROR` tracking was introduced so ERROR rounds never silently collapse into 4c's NIT path.)*

4c. On `REQUEST_CHANGES` AND `blocking_count == 0` (the JSON's top-level field): the round produced only NITs. Apply NIT fixes per the `mill-receiving-review` Decision Tree (no different from a regular fix-pass), write the fixer report at `<reviews_dir>/<YYYYMMDD-HHMMSS>-plan-fix-r<N>.md`, append `plan-fix-r{N}` to status timeline, set overview frontmatter `approved: true`, commit+push (single commit covering plan + reviews + status), break loop → Handoff. Do NOT run round N+1. Rationale: 0-BLOCKING means the planner and reviewer have converged; further rounds only churn cosmetic NITs.

4d. On `REQUEST_CHANGES` AND `blocking_count > 0`:
   - `_status.append_phase(status_path, f"plan-review-r{N}", iso_ts)`.
   - Read each review file. For each finding, run the `mill-receiving-review` decision tree.
   - Apply fixes to plan files.
   - Write a fixer report at `<reviews_dir>/<YYYYMMDD-HHMMSS>-plan-fix-r<N>.md` with two sections: `## Fixed` (each fixed finding, one-line reference to the review file + quoted finding title) and `## Pushed Back` (each rejected finding, same format + reason citing code/doc/scope).
   - Re-validate the plan DAG (`_plan_dag.validate`).
   - `_status.append_phase(status_path, f"plan-fix-r{N}", iso_ts)`.
   - Commit on the task branch: `git -C <worktree> add <plan_dir> <reviews_dir> <status_path> && git commit -m "mill-plan: plan-fix round {N} for {slug}"`.

5. **Non-progress check** (after writing each fixer report from round 2 onward): **Skip this check when the latest round's `## Pushed Back` section is empty.** Empty Pushed Back means the planner addressed every finding cleanly — that is convergence, not non-progress. The check only fires when both rounds have a non-empty Pushed Back AND the title set is identical. If the deep-merged config has `pipeline.autonomous_mode: true`: skip the user prompt; `_status.set_blocked(status_path, f"non-progress round {N}", timestamp=ts)`; commit `git -C <worktree> add <status_path> <reviews_dir> && git -C <worktree> commit -m "mill-plan: blocked (autonomous-mode non-progress) for {slug}"` and push; halt with "Autonomous mode: plan blocked on non-progress at round {N}. Task left as [active] for manual review." If the set is identical, halt with `BLOCKED: Plan review non-progress round {N}` and tell the user to look at the fixer reports. Do not escape-hatch — non-progress means the planner and reviewer are stuck in a stable disagreement; user intervention is required.

6. **Max-rounds escape** (only when round counter exhausts without APPROVE, BLOCKINGs still remain, AND non-progress did not fire): If the deep-merged config has `pipeline.autonomous_mode: true`: skip the user prompt; `_status.set_blocked(status_path, f"max-rounds exhausted after {N} rounds, {M} BLOCKINGs remain", timestamp=ts)`; commit and push; halt with "Autonomous mode: plan blocked after {N} rounds, {M} BLOCKINGs remain. Task left as [active]." present the user with the prompt below verbatim, computing `{N}` and `{M}` and a one-line recommendation. `{M}` is `result["blocking_count"]` from the most recent CLI invocation — do not re-count manually. If `blocking_count` was 0 in the latest round, this prompt should not have fired — verify step 4c logic before presenting.

   > After {N} rounds, {M} BLOCKING findings remain unresolved (blocking_count from latest round's review JSON). Options:
   > A) Deep problems — rethink approach. Go back to mill-start and revise discussion.
   > B) Shallow — one more review round. Invoke: `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-plan.py" --max-rounds {N+1}` (the `--max-rounds` flag overrides the configured cap; without it the script re-reads config and exits at the same cap again).
   > C) Override — accept findings and proceed to mill-go anyway.
   > Recommended: {A/B/C} based on {analysis of remaining findings}.

   Wait for the user's choice. A → halt and tell user to check out fresh after they revise. B → invoke `millpy-review-plan.py --max-rounds {N+1}` where `{N}` is the round count just reported (one extra round beyond the configured max). C → set `approved: true` and proceed to Handoff.

### Phase: Handoff

**Guard.** Read `plan_dir / "00-overview.md"` and parse the `approved:` field from the top fenced yaml block. If it is not the literal boolean `true`, halt with: `BLOCKED: mill-plan Handoff guard -- plan/00-overview.md has approved: false. Plan review did not complete. Re-run /mill-plan to enter Phase: Plan Review.` To parse: extract the YAML block via the existing pattern (`re.search(r"```yaml(.*?)```", overview_text, re.DOTALL)`), then read `approved:` with `yaml.safe_load(yaml_text)["approved"]`. Reject string `"true"` — the value must be the YAML boolean (overview template writes `approved: false`, the flip in step 4a/4b/4c writes `approved: true` as bare YAML). The guard runs *before* any `_status` mutation, so a guard failure leaves status.md untouched and the operator can re-enter cleanly.

`_status.append_phase(status_path, "planned", _timestamp.now_utc_iso())`. Commit+push.

If the deep-merged config has `pipeline.auto_report: true`, invoke `/mill-self-report --auto` and let it finish before reporting to the user. The skill checks `gh auth` itself and bails cleanly if absent, so this is always safe to call.

Report: **"Plan complete. Run `/mill-go` next to start autonomous implementation."** Do not invoke mill-go yourself — handoff to mill-go is always an explicit user decision, even when auto-report fired.

## Timestamps

Always use `_timestamp.now_utc_compact()` / `now_utc_iso()` for any generated timestamp (plan `started:`, fixer-report filenames, status.md timeline rows). Never hand-write or guess a date.

## Principles

- **Plan the full scope** — no "we'll add X later" phases inside the plan.
- **YAGNI ruthlessly** — don't plan for hypothetical requirements.
- **Follow `mill-receiving-review`'s decision tree** — never dismiss a finding with "low risk", "out of scope", "pre-existing".
- **Autonomous** — the only user interaction is the max-rounds escape and non-progress halt.
- **Card `Context:` is an allowlist** — list every file the implementer needs to read WITHOUT editing. An empty or terse `Context:` is a review-blocker. The implementer reads ONLY listed files; any unlisted file is a plan defect. `Edits:` files are implicitly read — do not repeat them in `Context:`. All paths must be backtick-wrapped, one per bullet; no inline prose, no line-range suffixes.
- **`Requirements:` must use stable identifiers** — name the specific function, class, or constant being changed. "Replace `_load_config` in `mill-claim.py` with `from _config import load_config`" is correct. "Refactor config loading to use the shared helper" is not — it forces the implementer to explore, defeating the cold-start guarantee.

## Board discipline

- Task-state writes (`status_path`, `plan_dir`, `reviews_dir`) are committed on the task branch via `git add` + `git commit`, then pushed to remote. They never go through the wiki.
- Phase transitions via `_status.append_phase`. Hand-editing the status.md yaml block is banned; use `update_field` for the plan pointer.
- The overview frontmatter's `approved:` field is the exception — it lives in `plan/00-overview.md`, not `status.md`, and is flipped by a direct Edit because `_status.py` only knows about status.md.
