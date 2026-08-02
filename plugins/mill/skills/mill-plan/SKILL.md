---
name: mill-plan
description: In a spawned worktree with a committed discussion.md, autonomously write a batch-based implementation plan, self-review it via mill-review-plan, and hand off to mill-go.
---

# mill-plan

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

You are an autonomous planner running on Opus. Your job is to turn `discussion.md` into an implementation plan detailed enough that a Sonnet-class builder can execute it with zero further human input. mill-plan never pauses mid-phase to ask the user — every halt (non-progress, max-rounds exhaustion) is a clean `_status.set_blocked` stop, not a prompt.

## Entry

**Step 0: Load `mill:conversation`.** Load the `mill:conversation` skill via the Skill tool, unconditionally, immediately — before any other Entry step or phase. mill-plan no longer surfaces any operator-facing prompt (the former Max-rounds-escape prompt at step 6 is now an unconditional halt — see Phase: Plan Review); this skill is loaded defensively in case a future addition needs its numbered-options convention.

1. Resolve and bind the path variables:
   - `git_root = _paths.resolve_git_root()`
   - `wiki_path = _paths.resolve_wiki_path(git_root)`
   `signature: _paths.resolve_git_root(start: Path | None = None) -> Path`
   `signature: _paths.resolve_wiki_path(git_toplevel: Path) -> Path`
2. Load config — deep-merge `<hub_root>/mill-config.yaml` with `.millhouse/config.local.yaml`. Read `roles.plan-review.holistic.rounds` as `max_review_rounds`. Entry step 4's `phase: discussing` row additionally reads two `pipeline.*` keys at the point of use (see "Entry-gate wait for upstream mill-start" below): `pipeline.entry_wait` — master on/off switch for the entry-gate blocking wait (default `true` if the key is absent) — and `pipeline.entry_wait_timeout_minutes` — give-up timeout in minutes for the entry-gate wait (default `120` if the key is absent).
   `signature: _config.load_config(hub_root: Path, worktree_root: Path) -> dict`
3. Read the slug via `_marker.slug_from_branch(git_root, wiki_path, cfg)`. On `MarkerError` → halt with "this worktree was not created by mill-spawn".

**Path Setup.** Derive:
- `git_root = _paths.resolve_git_root()`
- `worktree_root = _paths.resolve_hub_path()` (the hub root; used to anchor `_mill/` paths in nested layouts)
- `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])` (resolves against the hub root)

`plan_dir` and `reviews_dir` will be derived during Phase: Plan (writes) or Phase: Plan Review (reads) as appropriate — see those phases for details.

4. Read `status_path` and inspect `phase:` + the plan state on disk (no `plan_dir` dir at worktree root, using `cfg['paths']['plan_dir']`). Decide entry branch:

   | state | action |
   | --- | --- |
   | `phase: discussed`, no `plan_dir` dir at worktree root | Phase: Plan (fresh write) |
   | `phase: planning`/`plan-review-*`/`plan-fix-*`, `plan_dir/00-overview.md` exists, `approved: false` | Phase: Plan Review (re-enter loop; do NOT rewrite plan files) |
   | `approved: true` in overview frontmatter | Tell user: "plan already approved, run `/mill-go`". Halt. |
   | `phase: discussing` | wait for `phase: discussed` (see "Entry-gate wait for upstream mill-start" below) if `pipeline.entry_wait` is true; otherwise tell user what phase is set and halt |
   | any other phase (`planned`, …) | Tell user what phase is set and which skill should run instead. Halt. |

### Entry-gate wait for upstream mill-start

Whenever the phase-table lookup above lands on the `phase: discussing` row,
run this procedure instead of jumping straight to its listed action:

- Compute the match:
  ```python
  matched = _phase_wait.matches_wait_trigger(phase, {"discussing"}, [])
  ```
  No regex widening on this side. This is deliberate, not an oversight:
  mill-start's `discussion-fix-r{N}` phase value (written mid-loop during
  its own Discussion Review, per `mill-start/SKILL.md`'s step 4b) is
  always folded into the same commit as the immediately following
  `discussed` write and is never itself pushed as a standalone,
  externally observable phase; and mill-start's GAPS_FOUND loop makes no
  `_status.append_phase` call at all. The entire span of mill-start's
  active work — including every round of its own review loop, in both
  branches — is therefore already fully covered by the single exact
  value `discussing`, unlike mill-go's side, where mill-plan's own Plan
  Review loop commits its approve-phase and its Handoff-phase as
  separate, independently observable commits.
- Read `entry_wait = (cfg.get("pipeline") or {}).get("entry_wait", True)`.
- **If `matched` is `True` and `entry_wait` is `True`:**
  - Read `timeout_minutes = (cfg.get("pipeline") or {}).get("entry_wait_timeout_minutes", 120)` and compute `giveup_s = timeout_minutes * 60`.
  - Build the command: `cmd = _phase_wait.build_wait_command(status_path, "discussed", 10, giveup_s)`.
  - State one sentence to the user: waiting for the upstream mill-start
    run to reach `phase: discussed`.
  - Call the `Monitor` tool with `command=cmd`, `persistent: true`,
    `description` naming the slug and the target phase (e.g. "waiting for
    phase: discussed (mill-start handoff) for `<slug>`"). Do not set a
    `timeout_ms` value distinct from the default — `persistent: true`
    makes it irrelevant. This is never a decision point: state what is
    being waited for, then wait, with no `AskUserQuestion` or free-text
    prompt in between (mill-plan is autonomous outside its own documented
    escape hatches; this wait introduces no new one).
  - **Record the `task_id` the `Monitor` tool call returns** in a local
    orchestrator variable and retain it for the duration of this wait.
  - Wait for the `<task-notification>`. A `Monitor` run of this poll script
    delivers exactly one per-line event notification (the single `READY` /
    `BLOCKED: ...` / `TIMEOUT after ...` line the script echoes before
    exiting, carried in that notification's `<event>` tag), immediately
    followed by a second, separate terminal notification
    (`<status>completed</status>`, no `<event>` tag) once the script's
    process actually exits — this two-notification shape (confirmed by a
    live spike during this task's plan review, not assumed from the Agent
    tool's differently-shaped single-result notification) is expected and
    requires no special handling: act on the first notification's
    `<event>` content; the second, event-less completion notification for
    the same `task_id` carries no further information and needs no
    separate branch. See `plugins/mill/docs/harness-tool-contracts.md`
    for this contract's canonical write-up. Branch on the `<event>` content:
    - **`READY`** — re-run Entry step 4 from its top: re-read
      `status_path` fresh and re-evaluate the whole entry-branch table
      again from scratch (do not assume `discussed` is now the phase and
      jump straight to Phase: Plan).
    - **`BLOCKED: <reason>`** — halt immediately, surfacing `<reason>` to
      the operator. mill-plan's phase table has no pre-existing `blocked`
      row to reuse the exact message shape from (unlike mill-go's side) —
      halt with a message of the same shape mill-plan already uses
      elsewhere for a `BLOCKED:`-prefixed halt (e.g. the Plan Review
      non-progress/max-rounds `_status.set_blocked` halts): state the
      phase is blocked and surface `<reason>` verbatim. Do not re-arm the
      wait automatically.
    - **`TIMEOUT after <N>s waiting for phase: discussed`** — halt with a
      message distinct from the `BLOCKED` case: state that the configured
      give-up period (`pipeline.entry_wait_timeout_minutes`) elapsed
      without mill-start reaching `phase: discussed`, and that the
      operator should check on the upstream mill-start session (it may be
      abandoned, still legitimately working past the give-up window, or
      never started) and re-run `/mill-plan` to re-arm the wait if it is
      in fact still in progress.
  - **If the wait itself is stopped/interrupted at the harness level** (a
    `TaskStop` or equivalent operator-level cancellation of the recorded
    `task_id`, rather than one of the three outcomes above): no automatic
    retry. Halt with a short message telling the operator the wait was
    cancelled and that re-running `/mill-plan` will re-evaluate the phase
    (proceeding immediately if it has since become ready, or re-arming the
    wait if not).
- **If `matched` is `True` but `entry_wait` is `False`:** fall back to the
  original catch-all action for this phase — tell the user what phase is
  set (`discussing`) and which skill should run instead (mill-start), and
  halt.
- **If `matched` is `False`:** the phase is not `discussing`; fall through
  to the narrowed catch-all row above.

## Phases

Report the current phase to the user at each transition.

### Phase: Plan

Read `_mill/discussion.md` in full. Read `CONSTRAINTS.md` at the hub root if present (via `_constraints.read_if_exists()`). Then **think the plan through end-to-end before writing any file** — you are Opus and this is exactly where the planning budget pays off.

**Fork scope guardrail.** mill-plan has no fork-dispatch guidance today; prefer a cold, non-fork agent (`Explore`, or `general-purpose` when the research needs a tool beyond Explore's read-only grant) over `Agent(subagent_type: "fork")` whenever the research does not genuinely need the parent's already-in-context reasoning. `Explore`'s tool grant excludes `Edit`/`Write`/`Bash`-mutation (making unauthorized writes to shared plan/config state structurally impossible), whereas a fork always inherits the parent's full tool access — see the "Why not fork?" paragraph in `plugins/mill/skills/mill-go/SKILL.md`'s "## Agent-mode dispatch" section for that inheritance behavior.

Reserve `Agent(subagent_type: "fork")` for research that genuinely depends on the parent's in-flight reasoning to be useful. When a fork IS used under that narrower justification, all of the following apply:
(a) The fork's prompt must explicitly forbid Edit/Write calls, forbid mutating Bash commands, and forbid touching `plan_dir`, `status_path`, or any `mill-config.yaml`/`config.local.yaml`.
(b) Immediately BEFORE dispatching the fork, capture a `git status --porcelain` snapshot (scoped to the worktree) as a baseline. This is necessary because Phase: Plan's only commit happens at the very end (see the "**Commit on the task branch.**" step below), so the orchestrator's own in-progress, not-yet-committed plan files are routinely dirty in the working tree at fork-dispatch time — a bare post-return snapshot cannot distinguish that legitimate dirt from a fork's unauthorized writes.
(c) Immediately AFTER the fork returns, run `git status --porcelain` again and diff it against the pre-dispatch baseline. Treat only entries that are NEW in the post-return snapshot as a scope violation; the fork's report is not trusted until this diff is empty.
(d) On a detected violation, revert the unauthorized changes (`git checkout --` / delete untracked files as appropriate) before proceeding, and never silently incorporate a fork's unauthorized writes into the plan.
(e) When multiple research investigations are needed, dispatch them serially, not in parallel — complete one dispatch and confirm a clean git-status diff before starting the next. Serial dispatch is the only sanctioned path for concurrent research forks in mill-plan; there is no `isolation: "worktree"` fallback for parallel dispatch, since the Agent tool's `isolation` parameter's accepted values and exact semantics are not documented anywhere in this repo (only that the parameter exists).

**Batch sizing.** A batch is a *smart unit*: code that logically belongs together and that a Sonnet builder with a 200k-token context window can hold in its head while implementing. Split on natural module/subsystem boundaries, not on file count. If a proposed batch would force Sonnet to load the entire codebase to understand its own `Context:` list, split it. If two adjacent batches share >80% of their `Context:`, merge them. The planner must keep each batch within `pipeline.max_cards_per_batch` (default 10) cards and within the `pipeline.max_batch_context_tokens` (default 120000) context estimate (sum of each card's `Context:` + `Edits:` + `Creates:` file bytes / 4); the `batch-oversized` validator enforces this at step 1.5, so split proactively.

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

**Renames and Moves.** Express file renames as `Moves:` pairs — never as a `Creates:` + `Deletes:` combination (that breaks git history and inflates diffs). A rename-plus-extraction is one `Moves:` pair (the relocated file) plus a separate `Creates:` entry (the newly extracted file). Include a `## Rename mechanic` section in any batch that has at least one non-empty `Moves:` entry; the `move-mechanic-missing` validator check enforces this.

**Card numbering is global across batches**: card 1 lives in batch 01, card 7 might live in batch 02, etc. Never restart at 1 inside each batch — the reviewer and implementer cite cards by number and need uniqueness.

**Verify command shape.** For Python/mill projects: every non-null `verify:` in a per-batch file's frontmatter MUST start with the literal token `PYTHONPATH=` followed by a single space and then the command. The empty value on the same line scopes the `PYTHONPATH` reset to that one command, so the test subprocess does not inherit the mill cache scripts dir from the parent shell and tests load worktree modules instead of stale cache modules. For non-Python projects (e.g. Go, C#): use the native test runner directly without the prefix (e.g. `verify: go test ./...` or `verify: dotnet test`). The validator check `verify-not-isolated` enforces this conditionally based on project language; see the Step 1.5 fix table.

**Verify `cwd` mapping form.** `verify:` also accepts a `{cwd: hub|git_root, command: <string>}` mapping as an alternative to the plain-string form above. The plain string implies `cwd: git_root` (today's default, unchanged); the mapping form lets a batch pin its verify command to a specific root. `_plan_dag.parse_verify_field(frontmatter, hub_root, git_root)` is the single normalizer for both forms — every runtime read site routes through it. When authoring a batch (or the overview's module-wide `verify:`) for a task where `_paths.resolve_hub_path() != _paths.resolve_git_root()` (a nested layout), check whether the verify command you are about to write is naturally hub-relative — e.g. it assumes cwd is the mill hub directory rather than the git repository toplevel. If so, write it as the mapping form with `cwd: hub` instead of the plain-string form, which would incorrectly imply `cwd: git_root`. When the natural verify command is git-root-relative even in a nested layout, the plain-string form (or an explicit `cwd: git_root` mapping) remains correct — this field exists to describe how the command is actually written, not to force a specific choice.

**Verify command scope.** `verify:` runs after every implementer round and every fixer round — many times per batch. Target only the tests affected by this batch's `Edits:` + `Creates:` — DO NOT use `run-all.py` without `--only` for a focused batch (the full 77-file suite is multiple minutes). Patterns (Python projects):
- **Single test file:** `verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-fold.py`
- **Multiple files:** `verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-fold.py test-marker.py` — `run-all.py --only <basenames...>` runs only the named files (unknown names error out).

A batch that legitimately touches a cross-cutting helper that every test imports MAY use the unbounded `run-all.py` — but state the justification in `## Batch Tests` so the plan reviewer can validate the scope choice. The default expectation is per-batch scoping.

**Coverage profiling guidance.** If a `verify:` command collects coverage (e.g. `go test -cover`), write the profiling output to a scratch path (e.g. `-coverprofile=.scratch/coverage.out`) so it does not leave an untracked `coverage.out` at the repo root. The Handoff terminal gate auto-cleans common ephemeral artifacts (`coverage.out`, `.test`, `.test.exe`, `.prof`, `.cover` suffixes) as a backstop.

**Done-gate reminder.** If the plan's batch-verify scopes do not cover the entire module tree (the common case for scoped plans), consider setting `pipeline.done_gate` in `mill-config.yaml` to a cheap repo-wide test command (e.g. `go test ./...` for Go repos, `dotnet test` for .NET solutions). mill-go runs this command from `git_root` before marking the task `done`, catching regressions in packages outside the batch-verify scope. Leave `done_gate: null` (the default) if a repo-wide test would be too slow or is not meaningful for the project.

**Self-validate the DAG** before committing: call `_plan_dag.extract_batch_index(overview_text)` then `_plan_dag.validate(batches, sorted(p.name for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"))`. Any `PlanDAGError` → fix the plan files, then re-validate. Do not commit a plan that fails this check.

**Self-run the validator gate** before committing: call `_plan_validate.run` directly. This mirrors `millpy-review-plan.py`'s own step-1.5 gate exactly — same seven keyword arguments (`root`, `git_root`, `wiki_root`, `skip_checks`, `parent_branch`, `max_cards_per_batch`, `max_batch_context_tokens`). `git_root` and `wiki_path` are already bound at mill-plan's Entry step, and `worktree_root` at Path Setup, so this needs no new path resolution. There is no "or invoke the standalone CLI" fallback for this self-run — call `_plan_validate.run` directly.

```python
from _review_common import _load_root_from_overview

skip_checks = frozenset()
```

**`wiki-config-mutation` skip-check override.** If any batch's `Edits:`/`Creates:` includes `mill-config.yaml`, apply the same two-condition test as Step 1.5's `wiki-config-mutation` fix-table row before calling `_plan_validate.run`: (a) a bootstrap card is present in the plan explaining why the `mill-config.yaml` change is safe mid-flight; or (b) the modified keys are provably unused — zero grep hits across `scripts/` and `skills/` for key *removal or rename* only; a key *addition* whose consuming code ships in this same plan never satisfies (b), even with zero grep hits. If either condition holds, set `skip_checks = frozenset({"wiki-config-mutation"})` and record the justification in the plan commit message (see "Commit on the task branch" below). If neither condition holds, leave `skip_checks` as the empty frozenset from above — let the check fire and halt per the `wiki-config-mutation` fix-table row instead.

```python
errors = _plan_validate.run(
    plan_dir,
    worktree_root,
    root=_load_root_from_overview(plan_dir / "00-overview.md"),
    git_root=git_root,
    wiki_root=wiki_path,
    skip_checks=skip_checks,
    parent_branch=<_parent_branch.resolve(status_path, interactive=False), falling back to None on any exception>,
    max_cards_per_batch=cfg.get("pipeline", {}).get("max_cards_per_batch", 10),
    max_batch_context_tokens=cfg.get("pipeline", {}).get("max_batch_context_tokens", 120000),
)
```

Fix any findings using the Step 1.5 fix table below, then re-run, before committing the plan.

`signature: _status.read(status_path: Path) -> dict`

**Update `_mill/status.md`.**

- `plan_dir = worktree_root / cfg['paths']['plan_dir']` (config-canonical; write path).
- `_status.update_field(status_path, "plan", cfg['paths']['plan_dir'].rstrip('/'))` — pointer to the plan dir (worktree-relative).
- `_status.append_phase(status_path, "planning", _timestamp.now_utc_iso())`.

**Commit on the task branch.** `git -C <worktree> add <plan_dir> <status_path> && git -C <worktree> commit -m "mill-plan: write plan for {slug}"`. Push.

### Phase: Plan Review

**Path Setup (Plan Review).** Derive: `reviews_dir = _paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])`. Use this variable for all review file path references in this phase.

**Tree-guard safeguard (applies to all `_status.append_phase` calls in this phase):** Before any `_status.append_phase` call in this phase (steps 4a/4b/4c/4d below), call `_treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root)`. If the returned dict's `"triggered"` field is `True`, call `_status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"])` immediately after — this records the detection non-blockingly; it never halts the phase. mill-plan runs a structurally identical review-loop architecture to mill-start and mill-go and had no equivalent safeguard before this task (see `_mill/discussion.md`'s "Wiring point: all three review loops, not just mill-start" Decision).

Load the `mill-receiving-review` skill now, unconditionally, before round 1's dispatch below — this is what makes step 3's "before evaluating or acting on findings" rule structurally satisfiable. Under Agent-mode dispatch the reviewer's findings arrive only in the review file it writes, not embedded in the `<task-notification>` payload (which now carries only a one-line ack); the orchestrator must read that review file to present BLOCKING findings or NITs to the user, so the skill must already be active in context before that file is ever read. Loading it this early is still correct, it is just no longer motivated by the payload containing the findings.

The new schema has two skip conditions: `rounds: 0` OR `reviewer: null` means "skip plan review". If `roles.plan-review.holistic.rounds == 0` OR `roles.plan-review.holistic.reviewer` is `None`: set overview frontmatter `approved: true` via direct Edit, commit on the task branch (`git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "mill-plan: skip plan review (reviewer null or rounds 0) for {slug}"`), push, and proceed straight to Handoff. The skip is recorded in commit history; no `status.md` phase flip beyond the existing Handoff `planned` row.

Loop up to `max_review_rounds` rounds. Each round:

1. Report: **"Plan Review — round N/max_review_rounds"**.

1.5. **Step 1.5: pre-review validator gate (auto-run, no round consumed)**

   - The CLI auto-runs `_plan_validate` before invoking the LLM. If the validator finds anything, the CLI exits 1 with a JSON envelope on stdout (`{"errors": [...], "summary": "<n> finding(s) across <m> batch(es)"}`). No review file is written; no LLM token is spent; no review round is consumed.
   - On validator-failure exit, mill-plan parses the JSON and applies one mechanical fix per error dict, per the mapping table below. After fixes, mill-plan re-runs the review CLI via millpy-bg (slug `plan-validator-fix`; still no round consumed). Poll `cat <log-path>` until `[mill-bg] EXIT`, then run `grep '^{' <log-path> | tail -1` to extract the JSON line.
   - **Two-pass cap:** if the validator fails again on the second pass, mill-plan halts with `BLOCKED: plan-validate non-progress` and writes the unresolved errors to the user. Do NOT auto-retry beyond the second pass. The two-pass cap matches the `roles.implementer.self_fix_rounds` self-fix pattern.
   - If `pipeline.skip_validate: true` ever appears in config (currently it does not; this is a future hook), pass `--skip-validate` to the CLI and skip step 1.5 entirely. mill-plan passes `--skip-check wiki-config-mutation` only when the fix table instructs it — see the `wiki-config-mutation` row.

   | check                          | mechanical fix                                                                                                  |
   | ------------------------------ | ----------------------------------------------------------------------------------------------------------- |
   | non-existent-path              | A path declared as a `Creates:` target anywhere in this plan counts as existing for `Context:`/`Edits:` purposes; this row fires only for paths that are neither on disk nor declared as a `Creates:` target anywhere in the plan. If the path is a typo of an existing file, correct it. If it is meant to be a new `Creates:` target that does not yet appear anywhere in the plan, add it as a `Creates:` entry in the appropriate card. If neither applies, the planner intended to read a file that does not exist — halt; this is not mechanically fixable. |
   | card-missing-field             | Add the missing field with a sensible default: Context: → list the file(s) the requirement names; Edits: → none if the card creates a new file only; Creates: → none if the card edits an existing file only; Moves: → `Moves: none` if the card has no renames; Requirements: → restate the card title as a one-sentence requirement; Commit: → derive from the card title using the existing conventional-commit prefix pattern. |
   | commit-none-with-content       | Halt — a card declares Commit: none but also has non-none Edits:/Creates:/Deletes:/Moves:. The planner must either give the card a real Commit: message (if the content is genuinely this card's own work) or move the non-none content to a separate card and leave this card as a true zero-diff verification-only card. Not mechanically fixable — either resolution changes the plan's structure. |
   | card-numbering                 | Renumber cards within the affected batch sequentially starting at the lowest existing number; if the conflict is across batches, re-number the later-batch's cards to start above the earlier batch's max. Update every "card N" reference inside the plan. |
   | depends-on-unknown             | If the unknown dep is an integer, compare it against the `number:` values in the Batch Index — if close to an existing number (likely a typo), correct it. If the unknown dep is a string (legacy format), compare it against the `name:` values — if it is a typo of an existing entry, correct it. If the dependency genuinely needs a new batch, halt — adding a batch is not a mechanical fix. |
   | parallel-modifies-overlap      | If one batch logically depends on the other, add the missing edge to the dependent's depends-on list. If the two batches truly need to write to the same file in parallel, the plan is structurally wrong — halt.        |
   | reads-not-backtick-path        | Re-format the bullet to backtick-only paths; move any inline parenthetical commentary to the card's Requirements: prose. Strip any line-range suffix (e.g. `:55-65`) from the path.                                       |
   | move-format                    | Re-format the `Moves:` sub-bullet to `` `old/path` -> `new/path` `` (backtick-wrapped paths, ASCII ` -> ` arrow, no extra whitespace or commentary). |
   | move-redundant                 | Remove the duplicated path from `Creates:` or `Deletes:`, keeping it only in `Moves:`. If the path appears in both `Moves:` and `Creates:`, remove it from `Creates:` (unless it is the *target* of a rename-plus-extraction, in which case the `Creates:` entry is correct and `Moves:` is the error). |
   | move-source-missing            | If the source path is a typo of an existing file, correct it in the `Moves:` sub-bullet. If the source path genuinely does not exist on disk and is not a `Creates:` target in an earlier batch, halt — the planner must verify the path before proceeding. |
   | move-target-collision          | Rename the colliding target path so each card has a unique `Moves:` destination, or fix the duplicate if one card's `Moves:` target is an accidental copy of another's. If two cards genuinely require the same destination file, halt — the plan requires redesign. |
   | move-mechanic-missing          | Add the canonical `## Rename mechanic` section (copied from `plugins/mill/templates/plan-batch.md`) to the offending batch file, placed before `## Batch Scope`. |
   | all-files-touched-mismatch     | Update the overview's All Files Touched to match the union of every card's Edits: + Creates: + Moves: target paths (Move source paths are excluded — they disappear, like Deletes: tokens). (The overview list is derivative; the cards are the source of truth.) |
   | plugin-manifest-context-missing | Add `plugins/mill/.claude-plugin/plugin.json` to the offending batch's `Context:` list (unless the batch's own `Edits:` already includes it, in which case the check should not have fired — re-verify the check's `Creates:`/`Edits:`/`Deletes:` prefix match before editing the plan). |
   | context-completeness           | Add the referenced file to the card's `Context:` list (unless the card's own `Edits:`/`Creates:`/`Deletes:`/`Moves:` already covers it, in which case re-verify the check's own-list cross-reference before editing — the "add to Context:" remedy applies only when the token is absent from all five fields; a token that legitimately belongs to `Deletes:`/`Moves:`-source means the check should not have fired at all). The error dict's `line` field carries the exact offending `Requirements:` line (stripped), so the fixer can locate it directly without re-deriving it from the batch file. |
   | requirements-quote-indent-drift | Locate the card's `Requirements:` fence identified by the error payload's `message` (its fence index and the reported strip amount `N` — the message carries no content snippet). Strip exactly `N` leading space characters from each line of the fence body (not necessarily to column 0 — preserve whatever baseline indentation remains after the strip) so its content is a literal byte-exact substring of the target `Edits:` file named in the payload's `path` field. |
   | verify-not-isolated            | Open the per-batch file named by the error payload's `batch:` field (resolve `_mill/plan/<batch>.md`). Read the offending command from the payload's `path:` field. Replace the frontmatter line `verify: <original>` with `verify: PYTHONPATH= <original>` (literal `PYTHONPATH=`, single space, original command). One row, one prepend. |
   | verify-unrelated-test-file     | Remove the named token (the payload's `path:` field) from the offending batch's `verify:` command frontmatter (identified by the payload's `batch:` field). Log what was dropped and why in the validator-fix commit message, so the drop is auditable rather than silent. |
   | verify-excludes-edited-tagged-test | Open the offending batch's verify: command (payload's batch/path fields name the batch and the tagged test file). If a -tags flag already exists, append ,integration to its value; otherwise append " -tags integration" to the command. |
   | wiki-config-mutation           | This check cannot be fixed by editing plan files — the batch intentionally modifies `mill-config.yaml`. To proceed, verify one of two conditions: (a) a bootstrap card is present — a card whose body explains why the mill-config.yaml change is safe mid-flight for the currently-shipping task; or (b) the modified keys are provably unused — meaning key *removal or rename* where zero grep hits across `scripts/` and `skills/` confirm no existing code references them. (For key *addition* where consuming code is also being added in the same plan, zero grep hits does NOT satisfy condition (b); use (a) or halt.) If either condition holds: document the justification in the validator-fix commit message and re-run the CLI with `--skip-check wiki-config-mutation`. If `wiki-config-mutation` co-occurs with other fixable validator errors, fix those first per their rows, then re-run with `--skip-check wiki-config-mutation`. If neither condition holds: halt — the plan requires redesign. |
   | batch-oversized                | Halt — the batch exceeds `pipeline.max_cards_per_batch` cards and/or the `pipeline.max_batch_context_tokens` context estimate. Splitting a batch is a structural change, not a mechanical fix; the planner must re-split at Phase: Plan. Not auto-fixable. |
   | out-of-worktree-target         | Halt — an `Edits:`/`Creates:` target resolves outside the worktree (home-dir or absolute path). The operator must handle such edits manually; the implementer can never be pointed at them. Not auto-fixable. |
   | missing-overview               | Halt — the plan is structurally broken, not mechanically fixable.                                                                                                                                                       |
   | batch-index-parse              | Halt — the overview's fenced-yaml block is unparseable; not mechanically fixable.                                                                                                                                        |

   Rows where the fix is "halt" are deliberate: those errors signal a structural planning bug that auto-fixing would mask. The two-pass cap fires for these too (the second pass will produce the same error and trigger halt).

   After applying mechanical fixes for every error in the JSON, mill-plan commits the fix(es) on the task branch: `git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "mill-plan: validator-fix pass for {slug}"`. Push. Then re-runs the CLI. The commit message uses `validator-fix` to distinguish it from `plan-fix-r{N}` commits (which are LLM-fix-pass commits).

   Before re-running via millpy-bg for the `plan-validator-fix` slug, verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

2. **Waiting is never a decision point.** Waiting on this dispatch — either branch — is never a decision point: state in one sentence what you're waiting for, then wait. `AskUserQuestion` (or any equivalent free-text operator prompt) is banned here unconditionally — both the max-rounds escape (step 6) and the non-progress check (step 5) resolve by halting via `_status.set_blocked`, never by prompting. **Dispatch mode:** Resolve dispatch mode via `_agent_dispatch.resolve_dispatch_mode(cfg)`. Tree-guard checkpoint (Agent-mode only, pre-dispatch): call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) — and, on trigger, _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"]) — immediately before the Agent-mode dispatch below. This does not apply to the subprocess/psmux branch, which keeps its existing worktree_snapshot_guard coverage unchanged. If `agent` (Claude provider only): follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" in `plugins/mill/skills/mill-go/SKILL.md`) with `<cli> = millpy-review-plan.py` and `<args> = --holistic-only`. Because plan batch review is disabled in this hub (`roles.plan-review.batch.reviewer: null`), the agent-mode branch targets the holistic scope only. If per-batch plan review is ever enabled, the SKILL loops the three-step flow once per enabled scope. If `subprocess` or `psmux`: use the subprocess branch below.

   **Agent-mode error recovery:** A raw Agent API error before any verdict is classified as `stuck_type: transient` and the brief is re-dispatched once. On a second consecutive error, the read-only reviewer dispatch (which writes no review file) falls back to the subprocess `--stage full` path via `millpy-bg` before surfacing to the operator. This recovery applies even though mill-plan is autonomous and normally has no user interaction or stuck machinery; the one-retry plus subprocess fallback is the defined recovery, after which the skill surfaces to the operator.

   **Agent-mode prepare-envelope handling:** When the prepare stage returns a JSON envelope, inspect the response for the **presence of an `errors` key**:
   - **If `errors` key is present** (validator failure): The envelope contains `{"errors": [...], "summary": "..."}`. Parse the JSON and apply one mechanical fix per error dict, using the fix table in Step 1.5 below as the source of truth for all fix semantics. After fixes, commit on the task branch: `git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "mill-plan: validator-fix pass for {slug}"`. Push. Then re-invoke the prepare stage via the same three-step Agent-mode dispatch (re-render brief, call Agent, finalize; the same cycle repeats). Use the two-pass cap: if the second prepare invocation also fails validator, halt with `BLOCKED: plan-validate non-progress` and write the unresolved errors to the user.
   - **If `errors` key is absent** (validator success): The envelope contains `{"stage": "prepare", "brief_path": ..., ...}`. Proceed with the Agent → finalize flow as documented in the Agent-mode dispatch pattern (step 3–6 in `plugins/mill/skills/mill-go/SKILL.md` "## Agent-mode dispatch").

   The discriminator is the **presence of the `errors` key in the JSON**, not the exit code or any other field. Validator errors emit exit code 1 with `errors` in the JSON; validator success emits exit code 0 with `stage: prepare` and `brief_path`.

   **Pre-review validator gate:** The pre-review validator (step 1.5) runs unchanged in BOTH modes. In agent mode, the CLI's `--stage prepare` branch now invokes `_plan_validate` before rendering the review prompt (previously it did not, which was the #465 bug). In subprocess/psmux mode, step 1.5 is the standalone Python gate. Both branches run the same validator using the same fix table; the difference is placement. The claim at line 104 — "The CLI auto-runs `_plan_validate` before invoking the LLM" — is now accurate in agent mode because the prepare stage runs the validator before returning a brief to the Agent.

   Tree-guard checkpoint (Agent-mode only, post-dispatch): when this round used the Agent-mode branch, call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) again immediately after the Agent-mode dispatch pattern above returns (prepare through finalize, including any validator-fix re-invocation cycle), and on trigger call _status.append_recovery_log the same way. This brackets the whole out-of-process reviewer-execution window that worktree_snapshot_guard cannot see under Agent-mode dispatch (see _mill/discussion.md's "Closing the Agent-mode bracketing gap" Decision). Do not add this checkpoint inside the shared "## Agent-mode dispatch" section itself in mill-go/SKILL.md — it belongs at this call site only, since that shared section also serves non-review Implement/Fix/merge-in dispatch, which is out of scope.

   **Subprocess/psmux branch — Invoke the CLI as a subprocess:**

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug plan-review-r<N> -- \
       "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-plan.py"
   ```

   The CLI accepts two optional scope flags (mutually exclusive): `--holistic-only` skips per-batch reviews and runs only the holistic plan review; `--no-holistic` skips the holistic plan review and runs per-batch reviews only. Default — both run per the `roles.plan-review.batch.reviewer` and `roles.plan-review.holistic.reviewer` config keys. Append the flag to the inner `uv run …millpy-review-plan.py` portion of the millpy-bg invocation when needed.

   This returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then run `grep '^{' <log-path> | tail -1` to extract the JSON summary line.

   The script discovers the slug and round from disk. It prints one JSON line: `{"type": "plan", "round": N, "verdict": "APPROVE" | "REQUEST_CHANGES", "blocking_count": N, "reviews": [...]}` where each review entry has `{scope, verdict, file}`.

3. **Confirm `mill-receiving-review` is loaded before evaluating or acting on this round's findings** (`plugins/mill/skills/mill-receiving-review/SKILL.md`; it was already loaded unconditionally at the start of this phase — see the note immediately after the `### Phase: Plan Review` heading above). Non-negotiable. The VERIFY → HARM CHECK → FIX-or-PUSH-BACK decision tree is what keeps review loops useful.

**Guardrail:** NIT/BLOCKING fixes during Plan Review apply ONLY to files under `<plan_dir>` — never to the actual source files the plan describes editing, even when a finding quotes an exact source location.

4a. On `APPROVE` (verdict from JSON) with zero `[NIT]` findings (read the review file at `reviews[0].file` and confirm zero `[NIT]`-prefixed findings): set overview frontmatter `approved: true` via direct Edit. `_status.append_phase(status_path, f"plan-review-r{N}", iso_ts)`. Commit on the task branch: `git -C <worktree> add <plan_dir> <reviews_dir> <status_path> _mill/briefs/ && git -C <worktree> commit -m "mill-plan: approve plan for {slug}"`. Push. Break loop → Handoff. `iso_ts` is `_timestamp.now_utc_iso()`.

4b. On `APPROVE` with one or more `[NIT]` findings: apply each NIT per the `mill-receiving-review` decision tree by editing the plan files directly. Write a fixer report at `<reviews_dir>/<YYYYMMDD-HHMMSS>-plan-fix-r<N>.md` (timestamp from `_timestamp.now_utc_compact()`) with two sections — `## Fixed` (one line per fixed NIT: short reference to the source review file + quoted finding title) and `## Pushed Back` (one line per rejected NIT: short reference + reason citing code, doc, or scope per `mill-receiving-review`'s legitimate-pushback rules). Re-validate the plan DAG via `_plan_dag.validate`. Call `_status.append_phase(status_path, f"plan-fix-r{N}", iso_ts)`. Set overview frontmatter `approved: true` via direct Edit. Single git commit covering exactly four pathspecs — `<plan_dir>`, `<reviews_dir>`, `<status_path>`, `_mill/briefs/` — with message `mill-plan: plan-fix round {N} for {slug}` (matches existing 4d message shape; the round counter is NOT advanced). Push. Break loop → Handoff.

4.5. **Step 4.5: ERROR-only-aggregate retry (no round consumed)**

   When the JSON envelope from step 2 has a non-empty `reviews[]` array AND at least one entry's `verdict` is `"ERROR"`, OR when no JSON line appears in the bg log (no `^{` summary line after `[mill-bg] EXIT`, indicating the worker died before printing — e.g. killed, OOM), skip steps 4a/4b/4c/4d entirely and immediately re-run:

   Tree-guard checkpoint (Agent-mode only, pre-dispatch): call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) — and, on trigger, _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"]) — immediately before this retry's Agent-mode dispatch. Does not apply to the Subprocess/psmux branch immediately below.

   **Agent-mode:** follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" in `plugins/mill/skills/mill-go/SKILL.md`) with `<cli> = millpy-review-plan.py` and `<args> = --holistic-only`.

   Tree-guard checkpoint (Agent-mode only, post-dispatch): when this retry used the Agent-mode branch, call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) again immediately after it returns, and on trigger call _status.append_recovery_log the same way.

   **Subprocess/psmux branch:**

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug plan-review-retry-r<N> -- \
       "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-plan.py"
   ```

   This returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then run `grep '^{' <log-path> | tail -1` to extract the JSON summary line.

   The round counter is **not** consumed — the round produced no reviewable output. Absent-JSON and `verdict: ERROR` share **one consecutive-non-reviewable-round counter**: any mix of two consecutive non-reviewable rounds (ERROR then absent-JSON, or vice versa) triggers the two-pass cap. On the **second** consecutive non-reviewable run, halt: if it was absent-JSON, report `BLOCKED: plan review no-JSON round {N}` and surface the last stderr line(s) from the bg log; if it was `verdict: ERROR`, report `BLOCKED: review ERROR-only round {N}` and surface each entry's `error` string to the user. Do NOT auto-retry beyond the second pass. The two-pass cap mirrors step 1.5's validator gate. *(Note: the CLI now emits a `verdict: ERROR` envelope on uncaught exceptions per millpy-review-plan.py, so a true absent-JSON line means the worker died before printing — mirroring mill-go's "only treat exit 1 as unrecoverable when the JSON line is absent" rule. Closes #84 — `verdict: ERROR` tracking was introduced so ERROR rounds never silently collapse into 4c's NIT path.)*

4c. On `REQUEST_CHANGES` AND `blocking_count == 0` (the JSON's top-level field): the round produced only NITs. Apply NIT fixes per the `mill-receiving-review` Decision Tree (no different from a regular fix-pass), write the fixer report at `<reviews_dir>/<YYYYMMDD-HHMMSS>-plan-fix-r<N>.md`, append `plan-fix-r{N}` to status timeline, set overview frontmatter `approved: true`, commit+push (single commit covering plan + reviews + status + `_mill/briefs/`), break loop → Handoff. Do NOT run round N+1. Rationale: 0-BLOCKING means the planner and reviewer have converged; further rounds only churn cosmetic NITs.

4d. On `REQUEST_CHANGES` AND `blocking_count > 0`:
   - `_status.append_phase(status_path, f"plan-review-r{N}", iso_ts)`.
   - Read each review file. For each finding, run the `mill-receiving-review` decision tree.
   - Apply fixes to plan files.
   - Write a fixer report at `<reviews_dir>/<YYYYMMDD-HHMMSS>-plan-fix-r<N>.md` with two sections: `## Fixed` (each fixed finding, one-line reference to the review file + quoted finding title) and `## Pushed Back` (each rejected finding, same format + reason citing code/doc/scope).
   - Re-validate the plan DAG (`_plan_dag.validate`).
   - `_status.append_phase(status_path, f"plan-fix-r{N}", iso_ts)`.
   - Commit on the task branch: `git -C <worktree> add <plan_dir> <reviews_dir> <status_path> _mill/briefs/ && git -C <worktree> commit -m "mill-plan: plan-fix round {N} for {slug}"`. Push.

5. **Non-progress check** (after writing each fixer report from round 2 onward): **Skip this check when the latest round's `## Pushed Back` section is empty.** Empty Pushed Back means the planner addressed every finding cleanly — that is convergence, not non-progress. The check only fires when both rounds have a non-empty Pushed Back AND the title set is identical. When it fires: `_status.set_blocked(status_path, f"non-progress round {N}", timestamp=ts)`; commit `git -C <worktree> add <status_path> <reviews_dir> && git -C <worktree> commit -m "mill-plan: blocked (non-progress) for {slug}"` and push; halt with "Plan blocked on non-progress at round {N}. Task left as [active] for manual review." Do not escape-hatch — non-progress means the planner and reviewer are stuck in a stable disagreement; user intervention is required.

6. **Max-rounds escape** (only when round counter exhausts without APPROVE, BLOCKINGs still remain, AND non-progress did not fire): `_status.set_blocked(status_path, f"max-rounds exhausted after {N} rounds, {M} BLOCKINGs remain", timestamp=ts)`; commit and push; halt with "Plan blocked after {N} rounds, {M} BLOCKINGs remain. Task left as [active] for manual review." `{M}` is `result["blocking_count"]` from the most recent CLI invocation — do not re-count manually. If `blocking_count` was 0 in the latest round, this halt should not have fired — verify step 4c logic before proceeding.

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
- **Autonomous** — mill-plan never waits for an operator reply. The max-rounds escape and non-progress check resolve by halting via `_status.set_blocked` instead of prompting.
- **Card `Context:` is an allowlist** — list every file the implementer needs to read WITHOUT editing. An empty or terse `Context:` is a review-blocker. The implementer reads ONLY listed files; any unlisted file is a plan defect. `Edits:` files are implicitly read — do not repeat them in `Context:`. All paths must be backtick-wrapped, one per bullet; no inline prose, no line-range suffixes.
- **`Requirements:` must use stable identifiers** — name the specific function, class, or constant being changed. "Replace `_load_config` in `mill-claim.py` with `from _config import load_config`" is correct. "Refactor config loading to use the shared helper" is not — it forces the implementer to explore, defeating the cold-start guarantee. Any fenced block quoting exact source text inside `Requirements:` must reproduce the source's own original indentation byte-for-byte and must NOT pick up extra leading whitespace from the surrounding list item's continuation indent — author such fences so their content, read literally, is already a byte-exact substring of the file being quoted, regardless of how deeply the enclosing list item is nested (the source excerpt may legitimately have its own nonzero baseline indentation — e.g. quoting an indented method body — the rule is "no *extra* indentation beyond the source's own," not "no indentation at all").
- **Express renames as `Moves:` pairs** — never encode a rename as a `Creates:` + `Deletes:` combination; that destroys git rename history and inflates the diff. A rename-plus-extraction is the `Moves:` pair for the relocated file plus a separate `Creates:` for the newly extracted file. Include a `## Rename mechanic` section in any batch that has a non-empty `Moves:` field. Keep naming the specific surgical edits (package declaration, import lines, identifier retargets) in `Requirements:` using stable identifiers.

## Board discipline

- Task-state writes (`status_path`, `plan_dir`, `reviews_dir`) are committed on the task branch via `git add` + `git commit`, then pushed to remote. They never go through the wiki.
- Phase transitions via `_status.append_phase`. Hand-editing the status.md yaml block is banned; use `update_field` for the plan pointer.
- The overview frontmatter's `approved:` field is the exception — it lives in `plan/00-overview.md`, not `status.md`, and is flipped by a direct Edit because `_status.py` only knows about status.md.
