---
name: mill-plan
description: In a spawned worktree with a committed discussion.md, autonomously write a batch-based implementation plan, self-review it via mill-review-plan, and hand off to mill-go.
argument-hint: "[--revise]"
---

# mill-plan

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

You are an autonomous planner running on Opus.
Your job is to turn `discussion.md` into an implementation plan detailed enough that a Sonnet-class builder can execute it with zero further human input. mill-plan never pauses mid-phase to ask the user — every halt (non-progress, max-rounds exhaustion) is a clean `_status.set_blocked` stop, not a prompt.

## Entry

**Step 0: Load `mill:conversation`.**
Load the `mill:conversation` skill via the Skill tool, unconditionally, immediately — before any other Entry step or phase. mill-plan no longer surfaces any operator-facing prompt (the former Max-rounds-escape prompt at step 6 is now an unconditional halt — see Phase: Plan Review);
this skill is loaded defensively in case a future addition needs its numbered-options convention.

**Step 0.5 — Parse arguments.**
Read `$ARGUMENTS`. Token-walk left-to-right:

- `--revise` — set a local `revise_requested = True`. May appear at most once.
- Any other token: halt with usage hint:

  > Unknown argument: `<token>` in `$ARGUMENTS`
  >
  > usage: `/mill-plan [--revise]`

Step 0.5 does tokenization only — it does not validate `phase:`/`approved:` itself, since `status_path` isn't resolved until "Path Setup" (which runs after Entry steps 1-3) and `plan_dir` isn't derived during Entry at all today; the actual `--revise` validation is Entry step 4's new pre-check row, which already has both values in scope.

1. Resolve and bind the path variables:
   - `git_root = _paths.resolve_git_root()`
   - `wiki_path = _paths.resolve_wiki_path(git_root)`
   - `worktree_root = _paths.resolve_hub_path()` (the task worktree root; used to anchor `_mill/` paths in nested layouts)
   `signature: _paths.resolve_git_root(start: Path | None = None) -> Path`
   `signature: _paths.resolve_wiki_path(git_toplevel: Path) -> Path`
2. Load config — deep-merge `<hub_root>/mill-config.yaml` with `.millhouse/config.local.yaml`.
   Call `cfg = _config.load_config(worktree_root, git_root)`.
   Read `roles.plan-review.holistic.rounds` as `max_review_rounds`.
   Read `roles.plan-review.holistic.min_rounds` as `min_review_rounds` (default `1` when absent — see "Convergence gate" in Phase: Plan Review below).
   Entry step 4's `phase: discussing` row additionally reads two `pipeline.*` keys at the point of use (see "Entry-gate wait for upstream mill-start" below): `pipeline.entry_wait` — master on/off switch for the entry-gate blocking wait (default `true` if the key is absent) — and `pipeline.entry_wait_timeout_minutes` — give-up timeout in minutes for the entry-gate wait (default `120` if the key is absent). `signature: _config.load_config(hub_root: Path, worktree_root: Path) -> dict`
3. Read the slug via `_marker.slug_from_branch(git_root, wiki_path, cfg)`.
   On `MarkerError` → halt with "this worktree was not created by mill-spawn".

**Path Setup.**
Derive:
- `git_root = _paths.resolve_git_root()`
- `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])` (resolves against the task worktree root; `worktree_root` is already bound at Entry step 1 above)

`plan_dir` and `reviews_dir` will be derived during Phase: Plan (writes) or Phase: Plan Review (reads) as appropriate — see those phases for details.

4. Read `status_path` and inspect `phase:` + the plan state on disk (no `plan_dir` dir at worktree root, using `cfg['paths']['plan_dir']`).
   Decide entry branch:

   **`--revise` pre-check.** Whenever `revise_requested` is set (from Step 0.5), this pre-check runs **before** every row of the table below, as a distinct pre-check, not merely appended after it — this ordering is required because the table's existing `| approved: true in overview frontmatter | ... |` row is unconditional on `phase:`, and its condition (`approved: true`) is also satisfied throughout the entire `phase: planned` window `--revise` targets (since `approved:` stays `true` for the whole duration of mill-go's later run too — mill-go's own Prepare step immediately overwrites `phase: planned` to `phase: implementing` the moment execution starts, so `phase: planned` is the narrow, correct window that can only be true in the intended pre-execution period); without this explicit precedence, `--revise` would always hit the pre-existing halt row before ever reaching the new logic.
   Read `phase = _status.read_full(status_path)["yaml"].get("phase")` and the overview frontmatter's `approved:` field (via the file's existing YAML-block-extraction pattern already used elsewhere in this file for the `approved:` field).
   - If **both** `phase == "planned"` **and** `approved` is currently `true`: proceed with the revise action — (1) flip `approved: false` in `plan/00-overview.md` via the same direct-`Edit` convention already used elsewhere in this file for that field (no `_status.py` involvement, since `approved:` intentionally lives outside `status.md` per this file's own "## Board discipline" section); (2) call `_status.append_phase(status_path, "planning", <timestamp>)`; (3) commit both mutations together on the task branch in one commit (`git -C <worktree> add <plan_dir> <status_path> && git -C <worktree> commit -m "mill-plan: --revise re-open plan review for {slug}"`) and push; (4) bind `revise_from_blocked = False`; (5) fall through into the existing `phase: planning`/`plan-review-r{N}`/`plan-fix-r{N}` re-entry row (Phase: Plan Review; do NOT rewrite plan files) unmodified.
   - If `phase == "blocked"`: proceed with the blocked-resume action — (1) do NOT touch the overview's `approved:` field (it is already `false`); (2) call `_status.append_phase(status_path, "planning", <timestamp>)`; (3) commit on the task branch — `<plan_dir>` is deliberately NOT in this pathspec, unlike the `planned+approved` branch above, since this branch never touches `plan_dir` — `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-plan: --revise resume from blocked for {slug}"` and push; (4) bind `revise_from_blocked = True`; (5) fall through into the existing `phase: planning`/`plan-review-r{N}`/`plan-fix-r{N}` re-entry row (Phase: Plan Review; do NOT rewrite plan files) — same fallthrough target as the `planned+approved` branch above. `blocked_resume_round` is NOT computed here — it is deferred to Phase: Plan Review's own "Path Setup (Plan Review)" step, since `reviews_dir` does not exist yet at this point in Entry (see that section).
   - If `revise_requested` is set but neither of the two conditions above is met (`phase` is neither `"planned"` with `approved == true` nor `"blocked"`): halt with an explicit message naming the current `phase:` value and stating that revising a plan mill-go has already started executing, that has not yet been approved, or that is not currently blocked, is unsupported — do not silently force-flip `phase: planning` onto a task with committed/approved batches.
   - When `revise_requested` is not set, skip this entire pre-check and fall through to the existing table exactly as it is today.

   | state | action |
   | --- | --- |
   | `phase: discussed`, no `plan_dir` dir at worktree root | Phase: Plan (fresh write) |
   | `phase: planning`/`plan-review-*`/`plan-fix-*`, `plan_dir/00-overview.md` exists, `approved: false` | Phase: Plan Review (re-enter loop; do NOT rewrite plan files) |
   | `approved: true` in overview frontmatter | Tell user: "plan already approved, run `/mill-go`". Halt. |
   | `phase: discussing`, or matching `^discussion-fix-r\d+$` | wait for `phase: discussed` (see "Entry-gate wait for upstream mill-start" below) if `pipeline.entry_wait` is true; otherwise tell user what phase is set and halt |
   | `phase: blocked` | surface `blocked_reason` from status.md and tell the operator to re-run `/mill-plan --revise` to resume plan review (or resolve manually); halt. This row is reached only when `--revise` was NOT passed — the `--revise` pre-check above already intercepts the `phase: blocked` case when `--revise` is set. |
   | any other phase (`planned`, …) | Tell user what phase is set and which skill should run instead. Halt. |

### Entry-gate wait for upstream mill-start

Whenever the phase-table lookup above lands on the `phase: discussing` row, run this procedure instead of jumping straight to its listed action:

- Compute the match:
  ```python
  matched = _phase_wait.matches_wait_trigger(phase, {"discussing"}, [r"^discussion-fix-r\d+$"])
  ```
  The trigger is now widened to also match `discussion-fix-r{N}`.
  This closes a real gap: GitHub issue #821 has a concrete repro (commit `ab1786d6`) showing mill-start's own convergence-gate not-converged branch (Phase: Discussion Review step 4b, per `mill-start/SKILL.md`) appends+commits+pushes `discussion-fix-r{N}` and continues to the next round *without* the `discussed` phase following in the same commit — so `discussion-fix-r{N}` genuinely is pushed as a standalone, externally observable phase, not always folded into the same commit as the following `discussed` write.
  This mirrors mill-go's own copy of this exact wait pattern for mill-plan's own phases (`mill-go-base/SKILL.md`: `{"discussed", "discussing", "planning"}, [r"^plan-review-r\d+$", r"^plan-fix-r\d+$"]`) — same mechanism, same file family.
- Read `entry_wait = (cfg.get("pipeline") or {}).get("entry_wait", True)`.
- **If `matched` is `True` and `entry_wait` is `True`:**
  - Read `timeout_minutes = (cfg.get("pipeline") or {}).get("entry_wait_timeout_minutes", 120)` and compute `giveup_s = timeout_minutes * 60`.
  - Build the command: `cmd = _phase_wait.build_wait_command(status_path, "discussed", 10, giveup_s)`.
  - State one sentence to the user: waiting for the upstream mill-start run to reach `phase: discussed`.
  - Call the `Monitor` tool with `command=cmd`, `persistent: true`, `description` naming the slug and the target phase (e.g. "waiting for phase: discussed (mill-start handoff) for `<slug>`").
    Do not set a `timeout_ms` value distinct from the default — `persistent: true` makes it irrelevant.
    This is never a decision point: state what is being waited for, then wait, with no `AskUserQuestion` or free-text prompt in between (mill-plan is autonomous outside its own documented escape hatches;
    this wait introduces no new one).
  - **Record the `task_id` the `Monitor` tool call returns** in a local orchestrator variable and retain it for the duration of this wait.
  - Wait for the `<task-notification>`.
    A `Monitor` run of this poll script delivers exactly one per-line event notification (the single `READY` / `BLOCKED: ...` / `TIMEOUT after ...` line the script echoes before exiting, carried in that notification's `<event>` tag), immediately followed by a second, separate terminal notification (`<status>completed</status>`, no `<event>` tag) once the script's process actually exits — this two-notification shape (confirmed by a live spike during this task's plan review, not assumed from the Agent tool's differently-shaped single-result notification) is expected and requires no special handling: act on the first notification's `<event>` content;
    the second, event-less completion notification for the same `task_id` carries no further information and needs no separate branch.
    See `../../docs/harness-tool-contracts.md` for this contract's canonical write-up.
    Branch on the `<event>` content:
    - **`READY`** — re-run Entry step 4 from its top: re-read `status_path` fresh and re-evaluate the whole entry-branch table again from scratch (do not assume `discussed` is now the phase and jump straight to Phase: Plan).
    - **`BLOCKED: <reason>`** — halt immediately, surfacing `<reason>` to the operator. This halt is unrelated to the Entry-table's own `phase: blocked` row (see the phase table above) — that row reacts to this task's own `status.md` already being blocked before the wait even starts, whereas this branch reacts to the *upstream mill-start* wait's own script reporting a `BLOCKED:` line; halt with a message of the same shape mill-plan already uses elsewhere for a `BLOCKED:`-prefixed halt (e.g. the Plan Review non-progress/max-rounds `_status.set_blocked` halts): state the phase is blocked and surface `<reason>` verbatim.
      Do not re-arm the wait automatically.
    - **`TIMEOUT after <N>s waiting for phase: discussed`** — halt with a message distinct from the `BLOCKED` case: state that the configured give-up period (`pipeline.entry_wait_timeout_minutes`) elapsed without mill-start reaching `phase: discussed`,
      and that the operator should check on the upstream mill-start session (it may be abandoned, still legitimately working past the give-up window, or never started) and re-run `/mill-plan` to re-arm the wait if it is in fact still in progress.
  - **If the wait itself is stopped/interrupted at the harness level** (a `TaskStop` or equivalent operator-level cancellation of the recorded `task_id`, rather than one of the three outcomes above): no automatic retry.
    Halt with a short message telling the operator the wait was cancelled and that re-running `/mill-plan` will re-evaluate the phase (proceeding immediately if it has since become ready, or re-arming the wait if not).
- **If `matched` is `True` but `entry_wait` is `False`:** fall back to the original catch-all action for this phase — tell the user what phase is set (`discussing`) and which skill should run instead (mill-start), and halt.
- **If `matched` is `False`:** the phase is not `discussing`;
  fall through to the narrowed catch-all row above.

### Entry: resuming after a max-rounds block

Whenever the phase-table lookup above lands on the `phase: blocked` row, run this procedure instead of jumping straight to its listed action:

- Read `blocked_reason = _status.read_full(status_path)["yaml"].get("blocked_reason")`.
- **If `blocked_reason` does not start with `"max-rounds exhausted"`:** this is a hard stop exactly as today — surface `blocked_reason` to the operator and halt.
  Manual `status.md` intervention is required (matches this file's own "## Board discipline" ban on hand-editing the status.md yaml block — the operator investigates and clears `blocked_reason` themselves, mill-plan does not).
- **If `blocked_reason` starts with `"max-rounds exhausted"`:** this is a resource-exhaustion block, safe to resume automatically now that the operator has explicitly re-invoked `/mill-plan`.
  - Derive `reviews_dir = _paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])` (the same expression Phase: Plan Review's own "**Path Setup (Plan Review).**" section uses — `worktree_root` and `cfg` are already bound by this point in Entry step 4).
  - **`--revise` mid-block detection (check before deriving `N`):** list any `reviews_dir/revise-*` subdirectories.
    If the most-recently-modified review file across all of them is newer than the most-recently-modified review file directly in the plain `reviews_dir` (or the plain directory has no review files at all), the block occurred mid-`--revise`.
    Halt: state the block occurred during a `--revise` session and that resuming it is unsupported (the ordinary `--revise` pre-check cannot be re-supplied to recover the namespace, since it requires `phase == "planned"`, which is false once `phase: blocked`).
    Do not derive `N` or proceed below when this fires.
  - Otherwise, derive `N = _review_common.discover_round(reviews_dir, "plan", "holistic")` (the file's own established round-discovery helper — scans `reviews_dir` for existing review files and returns `max(found) + 1`, or `1` if none exist).
  - Compute `local_max_review_rounds = N + max_review_rounds - 1` (a fresh, full `max_review_rounds`-sized budget starting at round `N`).
    Because `set_blocked`'s `"max-rounds exhausted"` reason is only ever written when `round == max_review_rounds`, `N` will typically equal `max_review_rounds + 1` — without this extension, every one of Phase: Plan Review's existing `round >= max_review_rounds` checks would already be satisfied on the very first resumed iteration, immediately re-triggering an implicit-approve-at-cap or a fresh max-rounds halt without ever running a real review round.
    `local_max_review_rounds` substitutes for `max_review_rounds` at every site named in Phase: Plan Review's "Resumed-loop round-cap substitution" paragraph, for the remainder of this resumed loop only — the config-derived `max_review_rounds` value itself is never mutated, and a subsequent fresh `/mill-plan` invocation (no `blocked` re-entry involved) uses the unmodified config value as always.
  - Call `_status.append_phase(status_path, "planning", _timestamp.now_utc_iso())` — **not** `f"plan-review-r{N}"`, since round `N` has not run yet; `_status.append_phase` never dedupes against an existing identical Timeline row, so pre-writing round N's own completion marker before round N has even run would leave two identical `plan-review-r{N}` entries with different timestamps once the round actually completes and 4a/4d append it again for real.
    `"planning"` is already one of the phase values the Entry step-4 table's ordinary re-entry row matches, so it correctly signals "resume the review loop" without claiming a round completed.
    This call also auto-clears `blocked_reason` per `_status.append_phase`'s existing transition-away-from-blocked behavior — no separate clearing step is needed.
  - Commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-plan: resume plan review after max-rounds block for {slug}"`. Push.
  - Fall through into Phase: Plan Review, entering the loop at round `N` with `local_max_review_rounds` in effect.

## Phases

Report the current phase to the user at each transition.

### Phase: Plan

Read `_mill/discussion.md` in full.
Read `CONSTRAINTS.md` at the hub root if present (via `_constraints.read_if_exists()`).
Then **think the plan through end-to-end before writing any file** — you are Opus and this is exactly where the planning budget pays off.

**Fork scope guardrail.** mill-plan has no fork-dispatch guidance today;
prefer a cold, non-fork agent (`Explore`, or `general-purpose` when the research needs a tool beyond Explore's read-only grant) over `Agent(subagent_type: "fork")` whenever the research does not genuinely need the parent's already-in-context reasoning. `Explore`'s tool grant excludes `Edit`/`Write`/`Bash`-mutation (making unauthorized writes to shared plan/config state structurally impossible), whereas a fork always inherits the parent's full tool access — see the "Why not fork?" paragraph in `mill-go-base/SKILL.md`'s "## Agent-mode dispatch" section for that inheritance behavior.

Reserve `Agent(subagent_type: "fork")` for research that genuinely depends on the parent's in-flight reasoning to be useful.
When a fork IS used under that narrower justification, all of the following apply: (a) The fork's prompt must explicitly forbid Edit/Write calls, forbid mutating Bash commands, and forbid touching `plan_dir`, `status_path`, or any `mill-config.yaml`/`config.local.yaml`. (b) Immediately BEFORE dispatching the fork, capture a `git status --porcelain` snapshot (scoped to the worktree) as a baseline.
This is necessary because Phase: Plan's only commit happens at the very end (see the "**Commit on the task branch.**" step below), so the orchestrator's own in-progress, not-yet-committed plan files are routinely dirty in the working tree at fork-dispatch time — a bare post-return snapshot cannot distinguish that legitimate dirt from a fork's unauthorized writes. (c) Immediately AFTER the fork returns, run `git status --porcelain` again and diff it against the pre-dispatch baseline.
Treat only entries that are NEW in the post-return snapshot as a scope violation;
the fork's report is not trusted until this diff is empty. (d) On a detected violation, revert the unauthorized changes (`git checkout --` / delete untracked files as appropriate) before proceeding, and never silently incorporate a fork's unauthorized writes into the plan. (e) When multiple research investigations are needed, dispatch them serially, not in parallel — complete one dispatch and confirm a clean git-status diff before starting the next.
Serial dispatch is the only sanctioned path for concurrent research forks in mill-plan;
there is no `isolation: "worktree"` fallback for parallel dispatch, since the Agent tool's `isolation` parameter's accepted values and exact semantics are not documented anywhere in this repo (only that the parameter exists).

**Batch sizing.**
A batch is a *smart unit*: code that logically belongs together and that a Sonnet builder with a 200k-token context window can hold in its head while implementing.
Split on natural module/subsystem boundaries, not on file count.
If a proposed batch would force Sonnet to load the entire codebase to understand its own `Context:` list, split it.
If two adjacent batches share >80% of their `Context:`, merge them.
The planner must keep each batch within `pipeline.max_cards_per_batch` (default 10) cards and within the `pipeline.max_batch_context_tokens` (default 120000) context estimate (sum of each card's `Context:` + `Edits:` + `Creates:` file bytes / 4);
the `batch-oversized` validator enforces this at step 1.5, so split proactively.

**Write the files.**

**YAML-quoted tokens for fenced blocks.**
Tokens destined for YAML blocks must be pre-quoted;
heading tokens remain raw.
Heading tokens (`<TASK_TITLE>`, `<BATCH_NAME>`) substitute directly into H1 lines (raw form).
YAML-block tokens (`<TASK_TITLE_YAML>`, `<BATCH_NAME_YAML>`) substitute into fenced yaml blocks (quoted form via `_yaml_writer.quote_scalar`).
This separation lets templates use both forms without repeating quote logic.
Concretely:

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
2. Fill the Batch Index DAG, Shared Decisions, and All Files Touched sections in place.
   Set `number:` for each entry to the NN integer from the batch filename.
   Write `depends-on:` as a list of integers (e.g., `depends-on: [1]` meaning this batch depends on batch number 1).
   Leave `depends-on: []` for root batches.
3. For each batch, render `plugins/mill/templates/plan-batch.md` into `<plan_dir>/NN-<batch-slug>.md` using the pre-quoted tokens dict.
   Fill Batch Scope + Cards + Batch Tests.
   Set `number: NN` in the rendered frontmatter to the batch's integer (same as the filename prefix).

**Renames and Moves.**
Express file renames as `Moves:` pairs — never as a `Creates:` + `Deletes:` combination (that breaks git history and inflates diffs).
A rename-plus-extraction is one `Moves:` pair (the relocated file) plus a separate `Creates:` entry (the newly extracted file).
Include a `## Rename mechanic` section in any batch that has at least one non-empty `Moves:` entry;
the `move-mechanic-missing` validator check enforces this.

**Card numbering is global across batches**: card 1 lives in batch 01, card 7 might live in batch 02, etc. Never restart at 1 inside each batch — the reviewer and implementer cite cards by number and need uniqueness.

**Verify command shape.**
For Python/mill projects: every non-null `verify:` in a per-batch file's frontmatter MUST start with the literal token `PYTHONPATH=` followed by a single space and then the command.
The empty value on the same line scopes the `PYTHONPATH` reset to that one command, so the test subprocess does not inherit the mill cache scripts dir from the parent shell and tests load worktree modules instead of stale cache modules.
For non-Python projects (e.g. Go, C#): use the native test runner directly without the prefix (e.g. `verify: go test ./...` or `verify: dotnet test`).
The validator check `verify-not-isolated` enforces this conditionally based on project language;
see the Step 1.5 fix table.

**Verify `cwd` mapping form.** `verify:` also accepts a `{cwd: hub|git_root, command: <string>}` mapping as an alternative to the plain-string form above. The plain string implies `cwd: git_root` (today's default, unchanged); the mapping form lets a batch pin its verify command to a specific root. `_plan_dag.parse_verify_field(frontmatter, hub_root, git_root)` is the single normalizer for both forms — every runtime read site routes through it. When authoring a batch (or the overview's module-wide `verify:`) for a task where `_paths.resolve_hub_path() != _paths.resolve_git_root()` (a nested layout), check whether the verify command you are about to write is naturally hub-relative — e.g. it assumes cwd is the mill hub directory rather than the git repository toplevel. If so, write it as the mapping form with `cwd: hub` instead of the plain-string form, which would incorrectly imply `cwd: git_root`. When the natural verify command is git-root-relative even in a nested layout, the plain-string form (or an explicit `cwd: git_root` mapping) remains correct — this field exists to describe how the command is actually written, not to force a specific choice.

**Verify command scope.** `verify:` runs after every implementer round and every fixer round — many times per batch.
Target only the tests affected by this batch's `Edits:` + `Creates:` — DO NOT use `run-all.py` without `--only` for a focused batch (the full 77-file suite is multiple minutes).
Patterns (Python projects):
- **Single test file:** `verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-fold.py`
- **Multiple files:** `verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-fold.py test-marker.py` — `run-all.py --only <basenames...>` runs only the named files (unknown names error out).

A batch that legitimately touches a cross-cutting helper that every test imports MAY use the unbounded `run-all.py` — but state the justification in `## Batch Tests` so the plan reviewer can validate the scope choice.
The default expectation is per-batch scoping.

**Coverage profiling guidance.**
If a `verify:` command collects coverage (e.g. `go test -cover`), write the profiling output to a scratch path (e.g. `-coverprofile=.scratch/coverage.out`) so it does not leave an untracked `coverage.out` at the repo root.
The Handoff terminal gate auto-cleans common ephemeral artifacts (`coverage.out`, `.test`, `.test.exe`, `.prof`, `.cover` suffixes) as a backstop.

**Done-gate reminder.**
If the plan's batch-verify scopes do not cover the entire module tree (the common case for scoped plans), consider setting `pipeline.done_gate` in `mill-config.yaml` to a cheap repo-wide test command (e.g. `go test ./...` for Go repos, `dotnet test` for .NET solutions). mill-go runs this command from `git_root` before marking the task `done`, catching regressions in packages outside the batch-verify scope.
When the target language's build skill defines a lint command (Go: `golangci-lint run`; Python: `ruff check .`), default `done_gate` to include it — e.g. `go test ./... && golangci-lint run`. This applies even when a repo-wide *test* command is skipped as too slow: author `done_gate: golangci-lint run` (lint-only) rather than leaving it `null`, since linters are fast, unlike full regression suites. `csharp-build` defines no lint command today, so C# projects are unaffected by this default.
Leave `done_gate: null` only when the project has neither a meaningful repo-wide test nor a defined lint command.

**Self-validate the DAG** before committing: call `_plan_dag.extract_batch_index(overview_text)` then `_plan_dag.validate(batches, sorted(p.name for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"))`.
Any `PlanDAGError` → fix the plan files, then re-validate.
Do not commit a plan that fails this check.

**Self-run the validator gate** before committing: call `_plan_validate.run` directly.
This mirrors `millpy-review-plan.py`'s own step-1.5 gate exactly — same seven keyword arguments (`root`, `git_root`, `wiki_root`, `skip_checks`, `parent_branch`, `max_cards_per_batch`, `max_batch_context_tokens`). `git_root` and `wiki_path` are already bound at mill-plan's Entry step, and `worktree_root` at Path Setup, so this needs no new path resolution.
There is no "or invoke the standalone CLI" fallback for this self-run — call `_plan_validate.run` directly.

```python
from _review_common import _load_root_from_overview

skip_checks = frozenset()
```

**`wiki-config-mutation` skip-check override.**
If any batch's `Edits:`/`Creates:` includes `mill-config.yaml`, apply the same two-condition test as Step 1.5's `wiki-config-mutation` fix-table row before calling `_plan_validate.run`: (a) a bootstrap card is present in the plan explaining why the `mill-config.yaml` change is safe mid-flight;
or (b) the modified keys are provably unused — zero grep hits across `scripts/` and `skills/` for key *removal or rename* only;
a key *addition* whose consuming code ships in this same plan never satisfies (b), even with zero grep hits.
If either condition holds, set `skip_checks = skip_checks | frozenset({"wiki-config-mutation"})` and record the justification in the plan commit message (see "Commit on the task branch" below).
If neither condition holds, leave `skip_checks` as the empty frozenset from above — let the check fire and halt per the `wiki-config-mutation` fix-table row instead.

**`verify-full-suite` skip-check escape hatch.** Keep the "Verify command scope" section's carve-out (a batch that legitimately touches a cross-cutting helper every test imports MAY use the unbounded `run-all.py`) — but only when the batch's own `## Batch Tests` section documents that justification. If it does, set `skip_checks = skip_checks | frozenset({"verify-full-suite"})` and record the justification in the plan commit message (see "Commit on the task branch" below). If the justification is absent or unconvincing, leave `skip_checks` unchanged for this check — let it fire and halt per the `verify-full-suite` fix-table row (Phase: Plan Review Step 1.5) instead.

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

- `plan_dir = worktree_root / cfg['paths']['plan_dir']` (config-canonical;
  write path).
- `_status.update_field(status_path, "plan", cfg['paths']['plan_dir'].rstrip('/'))` — pointer to the plan dir (worktree-relative).
- `_status.append_phase(status_path, "planning", _timestamp.now_utc_iso())`.

**Commit on the task branch.** `git -C <worktree> add <plan_dir> <status_path> && git -C <worktree> commit -m "mill-plan: write plan for {slug}"`.
Push.

### Phase: Plan Review

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

**Tree-guard safeguard (applies to all `_status.append_phase` calls in this phase):** Before any `_status.append_phase` call in this phase (steps 4a/4b/4c/4d below), call `_treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root)`.
If the returned dict's `"triggered"` field is `True`, call `_status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"])` immediately after — this records the detection non-blockingly;
it never halts the phase. mill-plan runs a structurally identical review-loop architecture to mill-start and mill-go and had no equivalent safeguard before this task (see `_mill/discussion.md`'s "Wiring point: all three review loops, not just mill-start" Decision).

Load the `mill-receiving-review` skill now, unconditionally, before round 1's dispatch below — this is what makes step 3's "before evaluating or acting on findings" rule structurally satisfiable.
Under Agent-mode dispatch the reviewer's findings arrive only in the review file it writes, not embedded in the `<task-notification>` payload (which now carries only a one-line ack);
the orchestrator must read that review file to present BLOCKING findings or NITs to the user, so the skill must already be active in context before that file is ever read.
Loading it this early is still correct, it is just no longer motivated by the payload containing the findings.

The new schema has two skip conditions: `rounds: 0` OR `reviewer: null` means "skip plan review".
If `roles.plan-review.holistic.rounds == 0` OR `roles.plan-review.holistic.reviewer` is `None`: set overview frontmatter `approved: true` via direct Edit, commit on the task branch (`git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "mill-plan: skip plan review (reviewer null or rounds 0) for {slug}"`), push, and proceed straight to Handoff.
The skip is recorded in commit history;
no `status.md` phase flip beyond the existing Handoff `planned` row.

Loop up to `max_review_rounds` rounds.

**Resumed-loop round-cap substitution.** When this loop was entered via the Entry `blocked` re-entry row (see "Entry: resuming after a max-rounds block"), `local_max_review_rounds` substitutes for `max_review_rounds` at every site in this phase that compares against it, for the remainder of that resumed loop only: the loop-length cap just stated above, the step 1 round-report line ("Plan Review — round N/max_review_rounds" prints as "round N/local_max_review_rounds" instead), the Convergence gate's two `round >= max_review_rounds` / `round < max_review_rounds` bullets, every 4a/4b/4c inline `round >= max_review_rounds` (implicit-approve-at-cap) / `round < max_review_rounds` restatement, and step 6's `{N} rounds` in its halt message. The config-derived `max_review_rounds` value itself is never mutated by this substitution — a subsequent fresh `/mill-plan` invocation (no `blocked` re-entry involved) uses the unmodified config value everywhere, as always.

Each round:

1. Report: **"Plan Review — round N/max_review_rounds"**.

1.5.
**Step 1.5: pre-review validator gate (auto-run, no round consumed)**

   - The CLI auto-runs `_plan_validate` before invoking the LLM.
     If the validator finds anything, the CLI exits 1 with a JSON envelope on stdout (`{"errors": [...], "summary": "<n> finding(s) across <m> batch(es)"}`).
     No review file is written;
     no LLM token is spent;
     no review round is consumed.
   - On validator-failure exit, mill-plan parses the JSON and applies one mechanical fix per error dict, per the mapping table below. After fixes, mill-plan re-runs the review CLI via millpy-bg (slug `plan-validator-fix`; still no round consumed). Poll `cat <log-path>` until `[mill-bg] EXIT`, then run `grep '^{' <log-path> | tail -1` to extract the JSON line.
   - **Two-pass cap:** if the validator fails again on the second pass, immediately before halting, call `_status.set_blocked(status_path, "plan-validate non-progress", timestamp=_timestamp.now_utc_iso())`; commit on the task branch (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-plan: blocked (plan-validate non-progress) for {slug}"`) and push. Then mill-plan halts with `BLOCKED: plan-validate non-progress` and writes the unresolved errors to the user.
     Do NOT auto-retry beyond the second pass.
     The two-pass cap matches the `roles.implementer.self_fix_rounds` self-fix pattern.
   - If `pipeline.skip_validate: true` ever appears in config (currently it does not;
     this is a future hook), pass `--skip-validate` to the CLI and skip step 1.5 entirely. mill-plan passes `--skip-check wiki-config-mutation` only when the fix table instructs it — see the `wiki-config-mutation` row.

   | check                          | mechanical fix                                                                                                  |
   | ------------------------------ | ----------------------------------------------------------------------------------------------------------- |
   | non-existent-path              | A path declared as a `Creates:` target anywhere in this plan counts as existing for `Context:`/`Edits:` purposes; this row fires only for paths that are neither on disk nor declared as a `Creates:` target anywhere in the plan. If the path is a typo of an existing file, correct it. If it is meant to be a new `Creates:` target that does not yet appear anywhere in the plan, add it as a `Creates:` entry in the appropriate card. If neither applies, the planner intended to read a file that does not exist — halt; this is not mechanically fixable. |
   | card-missing-field             | Add the missing field with a sensible default: Context: → list the file(s) the requirement names; Edits: → none if the card creates a new file only; Creates: → none if the card edits an existing file only; Moves: → `Moves: none` if the card has no renames; Requirements: → restate the card title as a one-sentence requirement; Commit: → derive from the card title using the existing conventional-commit prefix pattern. |
   | commit-none-with-content       | Halt — a card declares Commit: none but also has non-none Edits:/Creates:/Deletes:/Moves:. The planner must either give the card a real Commit: message (if the content is genuinely this card's own work) or move the non-none content to a separate card and leave this card as a true zero-diff verification-only card. Not mechanically fixable — either resolution changes the plan's structure. |
   | card-numbering                 | Renumber cards within the affected batch sequentially starting at the lowest existing number; if the conflict is across batches, re-number the later-batch's cards to start above the earlier batch's max. Update every "card N" reference inside the plan. |
   | depends-on-unknown             | If the unknown dep is an integer, compare it against the `number:` values in the Batch Index — if close to an existing number (likely a typo), correct it. If the unknown dep is a string (legacy format), compare it against the `name:` values — if it is a typo of an existing entry, correct it. If the dependency genuinely needs a new batch, halt — adding a batch is not a mechanical fix. |
   | depends-on-batch-mismatch      | The payload's `batch:` field names the batch whose per-batch file frontmatter `depends-on:` disagrees with the overview's Batch Index entry for that same batch (payload's `message:` field shows both sides). Edit whichever side is stale so the per-batch file's `depends-on:` and the overview Batch Index entry's `depends-on:` name the identical dependency set. |
   | parallel-modifies-overlap      | If one batch logically depends on the other, add the missing edge to the dependent's depends-on list. If the two batches truly need to write to the same file in parallel, the plan is structurally wrong — halt.        |
   | reads-not-backtick-path        | Re-format the bullet to backtick-only paths; move any inline parenthetical commentary to the card's Requirements: prose. Strip any line-range suffix (e.g. `:55-65`) from the path.                                       |
   | move-format                    | Re-format the `Moves:` sub-bullet to `` `old/path` -> `new/path` `` (backtick-wrapped paths, ASCII ` -> ` arrow, no extra whitespace or commentary). |
   | move-redundant                 | Remove the duplicated path from `Creates:` or `Deletes:`, keeping it only in `Moves:`. If the path appears in both `Moves:` and `Creates:`, remove it from `Creates:` (unless it is the *target* of a rename-plus-extraction, in which case the `Creates:` entry is correct and `Moves:` is the error). |
   | move-source-missing            | If the source path is a typo of an existing file, correct it in the `Moves:` sub-bullet. If the source path genuinely does not exist on disk and is not a `Creates:` target in an earlier batch, halt — the planner must verify the path before proceeding. |
   | move-target-collision          | Rename the colliding target path so each card has a unique `Moves:` destination, or fix the duplicate if one card's `Moves:` target is an accidental copy of another's. If two cards genuinely require the same destination file, halt — the plan requires redesign. |
   | move-mechanic-missing          | Add the canonical `## Rename mechanic` section (copied from `plugins/mill/templates/plan-batch.md`) to the offending batch file, placed before `## Batch Scope`. |
   | all-files-touched-mismatch     | Update the overview's All Files Touched to match the union of every card's Edits: + Creates: + Moves: target paths (Move source paths are excluded — they disappear, like Deletes: tokens). (The overview list is derivative; the cards are the source of truth.) |
   | plugin-manifest-context-missing | Add `plugins/mill/.claude-plugin/plugin.json` to the offending batch's `Context:` list (unless the batch's own `Edits:` already includes it, in which case the check should not have fired — re-verify the check's `Creates:`/`Edits:`/`Deletes:` prefix match before editing the plan). |
   | context-completeness           | Add the referenced file to the card's `Context:` list (unless the card's own `Edits:`/`Creates:`/`Deletes:`/`Moves:`-source already covers it, in which case re-verify the check's own-list cross-reference before editing — the "add to Context:" remedy applies only when the token is absent from all five fields; a token that legitimately belongs to `Deletes:`/`Moves:`-source means the check should not have fired at all). The error dict's `line` field carries the exact offending `Requirements:` line (stripped), so the fixer can locate it directly without re-deriving it from the batch file. |
   | requirements-quote-indent-drift | Locate the card's `Requirements:` fence identified by the error payload's `message` (its fence index and the reported strip amount `N` — the message carries no content snippet). Strip exactly `N` leading space characters from each line of the fence body (not necessarily to column 0 — preserve whatever baseline indentation remains after the strip) so its content is a literal byte-exact substring of the target `Edits:` file named in the payload's `path` field. |
   | verify-not-isolated            | Open the per-batch file named by the error payload's `batch:` field (resolve `_mill/plan/<batch>.md`). Read the offending command from the payload's `path:` field. Replace the frontmatter line `verify: <original>` with `verify: PYTHONPATH= <original>` (literal `PYTHONPATH=`, single space, original command). One row, one prepend. |
   | verify-unrelated-test-file     | Remove the named token (the payload's `path:` field) from the offending batch's `verify:` command frontmatter (identified by the payload's `batch:` field). Log what was dropped and why in the validator-fix commit message, so the drop is auditable rather than silent. |
   | verify-excludes-edited-tagged-test | Open the offending batch's verify: command (payload's batch/path fields name the batch and the tagged test file; the payload's message field names the missing tag in its trailing "naming '<tag>'" fragment). If a `-tags` flag already exists on the command: do not comma-join `<tag>` into its value. Note this is a defense-in-depth choice, not a correction of broken Go semantics — Go's `-tags` set is satisfied by ANY-membership (each file's own `//go:build` line is checked independently against the full enabled-tag set, so a plain single-tag `//go:build scout` file is compiled/run whenever `scout` is enabled, regardless of what else is also enabled; `-tags integration,scout` does NOT exclude it). The real risk is project-specific: some repos deliberately give tagged suites mutually exclusive semantics (a suite's own constraint combines its tag with a negation of a sibling suite's tag, e.g. to keep suites isolated for cost/reporting reasons) — comma-joining silently breaks that convention if it's in use, and this check cannot tell whether a given project relies on it. Instead, append a new ` && `-chained invocation of the same base command (same verb and package pattern as the existing invocation) carrying its own `-tags <tag>` flag — strictly safer, since it never assumes either way. Otherwise (no `-tags` flag anywhere in the command yet): append `" -tags <tag>"` to the command in place, unchanged. |
   | verify-malformed-cwd           | Open the offending `verify:` field named by the error payload's `path:` field (a batch file path or the overview path) and `batch:` field (batch stem, or `None` for the overview). Fix the malformed `{cwd, command}` mapping per the payload's `message:` field (e.g. a bad `cwd` value that isn't `hub`/`git_root`, or a mapping missing `command:`). |
   | verify-mixed-cwd               | Each error dict's `message:` field states only that batch's own resolved cwd plus the sorted list of conflicting batch names; read all `verify-mixed-cwd` error dicts emitted for this plan together to see every batch's individual cwd. Change the outlier batch(es)' `verify:` mapping's `cwd:` value (or convert to the plain-string form, which implies `cwd: git_root`) so every batch in the plan resolves the `{cwd, command}` mapping form to the same root — all `hub` or all `git_root`. |
   | verify-full-suite              | The payload's `path:` field carries the offending `verify:` command (`batch:` names the offending batch, or `None` for the overview's module-wide `verify:`). If the batch's own `## Batch Tests` section already documents the cross-cutting-helper justification (see the `verify-full-suite` skip-check escape hatch in Phase: Plan), re-run with `--skip-check verify-full-suite`. Otherwise scope the command via `-k <pattern>` or `--only <every affected test file>`. |
   | wiki-config-mutation           | This check cannot be fixed by editing plan files — the batch intentionally modifies `mill-config.yaml`. To proceed, verify one of two conditions: (a) a bootstrap card is present — a card whose body explains why the mill-config.yaml change is safe mid-flight for the currently-shipping task; or (b) the modified keys are provably unused — meaning key *removal or rename* where zero grep hits across `scripts/` and `skills/` confirm no existing code references them. (For key *addition* where consuming code is also being added in the same plan, zero grep hits does NOT satisfy condition (b); use (a) or halt.) If either condition holds: document the justification in the validator-fix commit message and re-run the CLI with `--skip-check wiki-config-mutation`. If `wiki-config-mutation` co-occurs with other fixable validator errors, fix those first per their rows, then re-run with `--skip-check wiki-config-mutation`. If neither condition holds: halt — the plan requires redesign. |
   | batch-oversized                | Halt — the batch exceeds `pipeline.max_cards_per_batch` cards and/or the `pipeline.max_batch_context_tokens` context estimate. Splitting a batch is a structural change, not a mechanical fix; the planner must re-split at Phase: Plan. Not auto-fixable. |
   | out-of-worktree-target         | Halt — an `Edits:`/`Creates:` target resolves outside the worktree (home-dir or absolute path). The operator must handle such edits manually; the implementer can never be pointed at them. Not auto-fixable. |
   | missing-overview               | Halt — the plan is structurally broken, not mechanically fixable.                                                                                                                                                       |
   | batch-index-parse              | Halt — the overview's fenced-yaml block is unparseable; not mechanically fixable.                                                                                                                                        |

   Rows where the fix is "halt" are deliberate: those errors signal a structural planning bug that auto-fixing would mask.
   The two-pass cap fires for these too (the second pass will produce the same error and trigger halt).

   After applying mechanical fixes for every error in the JSON, mill-plan commits the fix(es) on the task branch: `git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "mill-plan: validator-fix pass for {slug}"`.
   Push.
   Then re-runs the CLI.
   The commit message uses `validator-fix` to distinguish it from `plan-fix-r{N}` commits (which are LLM-fix-pass commits).

   Before re-running via millpy-bg for the `plan-validator-fix` slug, verify `pwd` in the Bash terminal matches the task worktree.
   If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

**Convergence gate (min_rounds + demoted predicate).** On any round whose envelope's top-level `verdict` is `APPROVE`, or (at step 4c only) `REQUEST_CHANGES` with `blocking_count == 0` (see step 4c below), compute:

```
converged = (round >= min_review_rounds) and not any(f.get("demoted") for f in envelope["findings"])
```

**Exception — mill-plan's site only.** `envelope["findings"]` is not safe to read directly at this site: `_review_plan.py`'s `_scan_approved_batches` (called from `run()`) splices already-approved, carried-forward batches' own `findings` — which can carry a stale `demoted: true` marker written by an earlier round's ceiling, re-read verbatim off disk via `extract_findings` — into the same `reviews[]` list every round, and `aggregate_findings = [f for r in reviews for f in r.get("findings", [])]` folds those stale entries into the envelope's top-level `findings` unconditionally. If `plan-review.batch` is ever enabled, a demotion from an unrelated, already-approved batch would make `not any(f.get("demoted") for f in envelope["findings"])` permanently `False`, so the gate could never converge before the round cap forces the implicit-approve fallback, every round. At this site, replace `envelope["findings"]` with a round-filtered variant: `current_round_findings = [f for r in envelope["reviews"] if r.get("round") == envelope["round"] for f in r.get("findings", [])]`, then `converged = (round >= min_review_rounds) and not any(f.get("demoted") for f in current_round_findings)`. This works because `_scan_approved_batches`' carryforward entries retain their own original approval round (`"round": n`, always < the current round once a fresh round has run), while every entry produced by the current round (freshly-reviewed batches plus the holistic scope) shares the current round number — and `envelope["round"]` is `_review_plan.run()`'s own `agg_round = max(r["round"] for r in reviews)`, i.e. the current round, so the filter cleanly excludes carryforward and keeps only this round's live findings.

- `converged is True`: proceed exactly as the branch's terminal actions describe below (no behavior change).
- `converged is False` AND `round < max_review_rounds`: still apply any `[NIT]` fixes the branch describes (real, safe work), but do NOT execute the branch's terminal phase-transition / approve-commit / break-loop actions. Instead continue the loop to round N+1 exactly as the file's own next-round-continuation path already does — no operator gap-prompt (there are zero BLOCKING findings to present).
- `converged is False` AND `round >= max_review_rounds` (last allowed round): treat as an implicit approval — run the branch's existing terminal actions exactly as if `converged` were `True`, but append `" (min_rounds/demoted-predicate not satisfied by round cap)"` to that round's commit message (whichever of 4a/4b/4c fires) so the shortfall is auditable.
- The gate applies only to 4a, 4b, and 4c — never to 4d (`REQUEST_CHANGES` AND `blocking_count > 0`) or step 6 (max-rounds escape with BLOCKINGs remaining) — those already continue/hard-block by existing logic, untouched.
- The gate is orthogonal to `mill-start --auto`'s `prev_blocking_titles`/`extension_used` non-progress-extension machinery — that machinery is specific to mill-start and is never read or written here.

2. **Waiting is never a decision point.**
   Waiting on this dispatch — either branch — is never a decision point: state in one sentence what you're waiting for, then wait. `AskUserQuestion` (or any equivalent free-text operator prompt) is banned here unconditionally — both the max-rounds escape (step 6) and the non-progress check (step 5) resolve by halting via `_status.set_blocked`, never by prompting.
   **Dispatch mode:** Resolve dispatch mode via `_agent_dispatch.resolve_dispatch_mode(cfg)`.
   Tree-guard checkpoint (Agent-mode only, pre-dispatch): call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) — and, on trigger, _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"]) — immediately before the Agent-mode dispatch below.
   This does not apply to the subprocess/psmux branch, which keeps its existing worktree_snapshot_guard coverage unchanged.
   If `agent` (Claude provider only): follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" in `mill-go-base/SKILL.md`) with `<cli> = millpy-review-plan.py` and `<args> = --holistic-only`.
   Thread `--round <round>` from the prepare envelope into the finalize invocation unchanged (finalize has no round-cap check and never needs `--max-rounds`), and also pass `--agent-output <output_path>`, where `<output_path>` is the prepare envelope's `output_path` field read verbatim (extracted at the general Agent-mode dispatch pattern's step 1 in `mill-go-base/SKILL.md`, used verbatim at its step 5) — `millpy-review-plan.py --stage finalize` exits 1 with `"ERROR: --agent-output required for finalize stage"` when this flag is omitted.
   Because plan batch review is disabled in this hub (`roles.plan-review.batch.reviewer: null`), the agent-mode branch targets the holistic scope only.
   If per-batch plan review is ever enabled, the SKILL loops the three-step flow once per enabled scope.
   The finalize invocation also carries `--duration-s`, supplied by the shared "## Agent-mode dispatch" section's reviewer-only elapsed-time measurement in `mill-go-base/SKILL.md`; `--tool-calls` and `--cost-usd` are never passed under agent-mode.
   If `subprocess` or `psmux`: use the subprocess branch below.

   **Agent-mode error recovery:** A raw Agent API error before any verdict is classified as `stuck_type: transient` and the brief is re-dispatched once.
   On a second consecutive error, the read-only reviewer dispatch (which writes no review file) falls back to the subprocess `--stage full` path via `millpy-bg` before surfacing to the operator.
   This recovery applies even though mill-plan is autonomous and normally has no user interaction or stuck machinery;
   the one-retry plus subprocess fallback is the defined recovery, after which the skill surfaces to the operator.

   **Agent-mode prepare-envelope handling:** When the prepare stage returns a JSON envelope, inspect the response for the **presence of an `errors` key**:
   - **If `errors` key is present** (validator failure): The envelope contains `{"errors": [...], "summary": "..."}`.
     Parse the JSON and apply one mechanical fix per error dict, using the fix table in Step 1.5 below as the source of truth for all fix semantics.
     After fixes, commit on the task branch: `git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "mill-plan: validator-fix pass for {slug}"`.
     Push.
     Then re-invoke the prepare stage via the same three-step Agent-mode dispatch (re-render brief, call Agent, finalize;
     the same cycle repeats).
     Use the two-pass cap: if the second prepare invocation also fails validator, halt with `BLOCKED: plan-validate non-progress` and write the unresolved errors to the user.
   - **If `errors` key is absent** (validator success): The envelope contains `{"stage": "prepare", "brief_path": ..., ...}`.
     Proceed with the Agent → finalize flow as documented in the Agent-mode dispatch pattern (step 3–6 in `mill-go-base/SKILL.md` "## Agent-mode dispatch").

   The discriminator is the **presence of the `errors` key in the JSON**, not the exit code or any other field.
   Validator errors emit exit code 1 with `errors` in the JSON;
   validator success emits exit code 0 with `stage: prepare` and `brief_path`.

   **Pre-review validator gate:** The pre-review validator (step 1.5) runs unchanged in BOTH modes.
   In agent mode, the CLI's `--stage prepare` branch now invokes `_plan_validate` before rendering the review prompt (previously it did not, which was the #465 bug).
   In subprocess/psmux mode, step 1.5 is the standalone Python gate.
   Both branches run the same validator using the same fix table;
   the difference is placement.
   The claim at line 104 — "The CLI auto-runs `_plan_validate` before invoking the LLM" — is now accurate in agent mode because the prepare stage runs the validator before returning a brief to the Agent.

   Tree-guard checkpoint (Agent-mode only, post-dispatch): when this round used the Agent-mode branch, call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) again immediately after the Agent-mode dispatch pattern above returns (prepare through finalize, including any validator-fix re-invocation cycle), and on trigger call _status.append_recovery_log the same way.
   This brackets the whole out-of-process reviewer-execution window that worktree_snapshot_guard cannot see under Agent-mode dispatch (see _mill/discussion.md's "Closing the Agent-mode bracketing gap" Decision).
   Do not add this checkpoint inside the shared "## Agent-mode dispatch" section itself in mill-go-base/SKILL.md — it belongs at this call site only, since that shared section also serves non-review Implement/Fix/merge-in dispatch, which is out of scope.

   Print this round's cost line per the shared "## Review cost line" section in `mill-go-base/SKILL.md`, with `<type> = plan` and `<scope> = holistic` (the hub runs holistic-only plan review; a per-batch scope, should batch plan review ever be enabled, prints one line per scope).

   **Subprocess/psmux branch — Invoke the CLI as a subprocess:**

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   > Only when this loop was entered via the Entry `blocked` re-entry row (see "Entry: resuming after a max-rounds block"), append ` --max-rounds <local_max_review_rounds>` to the inner `millpy-review-plan.py` invocation below; omit it on every other round.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug plan-review-r<N> -- \
       "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-plan.py"
   ```

   The CLI accepts two optional scope flags (mutually exclusive): `--holistic-only` skips per-batch reviews and runs only the holistic plan review;
   `--no-holistic` skips the holistic plan review and runs per-batch reviews only.
   Default — both run per the `roles.plan-review.batch.reviewer` and `roles.plan-review.holistic.reviewer` config keys.
   Append the flag to the inner `uv run …millpy-review-plan.py` portion of the millpy-bg invocation when needed.

   This returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then run `grep '^{' <log-path> | tail -1` to extract the JSON summary line.

   The script discovers the slug and round from disk. It prints one JSON line: `{"type": "plan", "round": N, "verdict": "APPROVE" | "REQUEST_CHANGES", "blocking_count": N, "reviews": [...]}` where each review entry has `{scope, verdict, file, duration_s, tool_calls, cost_usd}`.

3. **Confirm `mill-receiving-review` is loaded before evaluating or acting on this round's findings** (`mill-receiving-review/SKILL.md`;
   it was already loaded unconditionally at the start of this phase — see the note immediately after the `### Phase: Plan Review` heading above).
   Non-negotiable.
   The VERIFY → HARM CHECK → FIX-or-PUSH-BACK decision tree is what keeps review loops useful.

**Guardrail:** NIT/BLOCKING fixes during Plan Review apply ONLY to files under `<plan_dir>` — never to the actual source files the plan describes editing, even when a finding quotes an exact source location.

4a. On `APPROVE` (verdict from JSON) with zero `[NIT]` findings (read the review file at `reviews[0].file` and confirm zero `[NIT]`-prefixed findings — the heading may carry a class suffix, so `### [NIT:consistency]` counts as a NIT exactly like a bare `### [NIT]` and is never missed; equivalently, this check can be made against the envelope's `findings` list by counting entries whose `severity` is `NIT`): compute `converged` per the Convergence gate above.
If `converged`, or `round >= max_review_rounds` (implicit-approve-at-cap): set overview frontmatter `approved: true` via direct Edit. `_status.append_phase(status_path, f"plan-review-r{N}", iso_ts)`.
Commit on the task branch: `git -C <worktree> add <plan_dir> <reviews_dir> <status_path> _mill/briefs/ && git -C <worktree> commit -m "mill-plan: approve plan for {slug}"` — when not `converged` (implicit-approve-at-cap fired), append `" (min_rounds/demoted-predicate not satisfied by round cap)"` to the commit message.
Push.
Break loop → Handoff. `iso_ts` is `_timestamp.now_utc_iso()`.
If not `converged` and `round < max_review_rounds`: 4a has no NITs to fix, so take no action this round — continue to round N+1.

4b. On `APPROVE` with one or more `[NIT]` findings (the heading may carry a class suffix, so `### [NIT:consistency]` counts as a NIT exactly like a bare `### [NIT]` and is never missed; equivalently, this check can be made against the envelope's `findings` list by counting entries whose `severity` is `NIT`): apply each NIT per the `mill-receiving-review` decision tree by editing the plan files directly.
Write a fixer report at `<reviews_dir>/<YYYYMMDD-HHMMSS>-plan-fix-r<N>.md` (timestamp from `_timestamp.now_utc_compact()`) with two sections — `## Fixed` (one line per fixed NIT: short reference to the source review file + quoted finding title) and `## Pushed Back` (one line per rejected NIT: short reference + reason citing code, doc, or scope per `mill-receiving-review`'s legitimate-pushback rules).
Re-validate the plan DAG via `_plan_dag.validate`.
This NIT-fix work, fixer report, and DAG re-validation happen regardless of `converged` — real work, safe either way.
Compute `converged` per the Convergence gate above.
If `converged`, or `round >= max_review_rounds` (implicit-approve-at-cap): `_status.append_phase(status_path, f"plan-fix-r{N}", iso_ts)`.
Set overview frontmatter `approved: true` via direct Edit.
Single git commit covering exactly four pathspecs — `<plan_dir>`, `<reviews_dir>`, `<status_path>`, `_mill/briefs/` — with message `mill-plan: plan-fix round {N} for {slug}` (matches existing 4d message shape;
the round counter is NOT advanced) — when not `converged` (implicit-approve-at-cap fired), append `" (min_rounds/demoted-predicate not satisfied by round cap)"` to the commit message.
Push.
Break loop → Handoff.
If not `converged` and `round < max_review_rounds`: still call `_status.append_phase(status_path, f"plan-fix-r{N}", iso_ts)` and commit the NIT fixes (same single commit shape as above, without the `approved: true` flip and without the loop-break/Handoff transition) and push — the fix genuinely happened — then continue to round N+1 instead of breaking.

4.5.
**Step 4.5: ERROR-only-aggregate retry (no round consumed)**

   **Usage-error immediate halt (checked first, every round).** Before evaluating the trigger condition below, inspect the JSON envelope's `reviews[]` array (when present) for any entry with `error_kind: "usage"`. If found, halt immediately on this occurrence — no retry, no round consumed — regardless of what any other entry in the same `reviews[]` list contains: call `_status.set_blocked(status_path, f"plan review usage error: <message>", timestamp=ts)` (where `<message>` is the offending entry's `error` field); commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-plan: blocked (plan review usage error) for {slug}"` and push; halt with `BLOCKED: plan review usage error: <message>` — distinct wording from the existing `BLOCKED: review ERROR-only round {N}` halt below.

   When no entry in `reviews[]` is `error_kind: "usage"` (per the immediate halt above), and the JSON envelope from step 2 has a non-empty `reviews[]` array AND at least one remaining entry's `verdict` is `"ERROR"`, OR when no JSON line appears in the bg log (no `^{` summary line after `[mill-bg] EXIT`, indicating the worker died before printing — e.g. killed, OOM), skip steps 4a/4b/4c/4d entirely and immediately re-run:

   Tree-guard checkpoint (Agent-mode only, pre-dispatch): call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) — and, on trigger, _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"]) — immediately before this retry's Agent-mode dispatch.
   Does not apply to the Subprocess/psmux branch immediately below.

   **Agent-mode:** follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" in `mill-go-base/SKILL.md`) with `<cli> = millpy-review-plan.py` and `<args> = --holistic-only`.
   Thread `--round <round>` from the prepare envelope into the finalize invocation unchanged (finalize has no round-cap check and never needs `--max-rounds`), and also pass `--agent-output <output_path>`, where `<output_path>` is the prepare envelope's `output_path` field read verbatim (extracted at the general Agent-mode dispatch pattern's step 1 in `mill-go-base/SKILL.md`, used verbatim at its step 5) — `millpy-review-plan.py --stage finalize` exits 1 with `"ERROR: --agent-output required for finalize stage"` when this flag is omitted.

   Tree-guard checkpoint (Agent-mode only, post-dispatch): when this retry used the Agent-mode branch, call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) again immediately after it returns, and on trigger call _status.append_recovery_log the same way.

   Print this retry's cost line per the shared "## Review cost line" section in `mill-go-base/SKILL.md`, with `<type> = plan` and `<scope> = holistic`.

   **Subprocess/psmux branch:**

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   > Only when this loop was entered via the Entry `blocked` re-entry row (see "Entry: resuming after a max-rounds block"), append ` --max-rounds <local_max_review_rounds>` to the inner `millpy-review-plan.py` invocation below; omit it on every other round.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug plan-review-retry-r<N> -- \
       "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-plan.py"
   ```

   This returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then run `grep '^{' <log-path> | tail -1` to extract the JSON summary line.

   The round counter is **not** consumed — the round produced no reviewable output.
   Absent-JSON and `verdict: ERROR` share **one consecutive-non-reviewable-round counter**: any mix of two consecutive non-reviewable rounds (ERROR then absent-JSON, or vice versa) triggers the two-pass cap.
   On the **second** consecutive non-reviewable run, immediately before halting: if it was absent-JSON, call `_status.set_blocked(status_path, f"plan review no-JSON round {N}", timestamp=_timestamp.now_utc_iso())`; commit (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-plan: blocked (plan review no-JSON round {N}) for {slug}"`) and push; then halt, reporting `BLOCKED: plan review no-JSON round {N}` and surfacing the last stderr line(s) from the bg log.
   If it was `verdict: ERROR`, call `_status.set_blocked(status_path, f"review ERROR-only round {N}", timestamp=_timestamp.now_utc_iso())`; commit (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-plan: blocked (review ERROR-only round {N}) for {slug}"`) and push; then halt, reporting `BLOCKED: review ERROR-only round {N}` and surfacing each entry's `error` string to the user.
   Do NOT auto-retry beyond the second pass.
   The two-pass cap mirrors step 1.5's validator gate. *(Note: the CLI now emits a `verdict: ERROR` envelope on uncaught exceptions per millpy-review-plan.py, so a true absent-JSON line means the worker died before printing — mirroring mill-go's "only treat exit 1 as unrecoverable when the JSON line is absent" rule.
   Closes #84 — `verdict: ERROR` tracking was introduced so ERROR rounds never silently collapse into 4c's NIT path.)*

4c. On `REQUEST_CHANGES` AND `blocking_count == 0` (the JSON's top-level field): the round produced only NITs.
Apply NIT fixes per the `mill-receiving-review` Decision Tree (no different from a regular fix-pass), write the fixer report at `<reviews_dir>/<YYYYMMDD-HHMMSS>-plan-fix-r<N>.md` — this happens regardless of `converged`, real work either way.
Compute `converged` per the Convergence gate above (this branch is one of the gate's `APPROVE`-equivalent sites, per that section's opening sentence).
If `converged`, or `round >= max_review_rounds` (implicit-approve-at-cap): append `plan-fix-r{N}` to status timeline, set overview frontmatter `approved: true`, commit+push (single commit covering plan + reviews + status + `_mill/briefs/`; when not `converged`, append `" (min_rounds/demoted-predicate not satisfied by round cap)"` to the commit message), break loop → Handoff.
Do NOT run round N+1.
Rationale: 0-BLOCKING means the planner and reviewer have converged;
further rounds only churn cosmetic NITs — this is exactly the premature-termination case a ceiling-demoted BLOCKING can otherwise mask, which is what the convergence gate now guards against.
If not `converged` and `round < max_review_rounds`: commit the NIT fixes and the fixer report (same single commit shape as above, without the `approved: true` flip and without the loop-break/Handoff transition) and push, then continue to round N+1 instead of breaking.

4d. On `REQUEST_CHANGES` AND `blocking_count > 0`:
   - `_status.append_phase(status_path, f"plan-review-r{N}", iso_ts)`.
   - Read each review file.
     The `findings` list in the envelope is post-ceiling: a finding shown as `[NIT:scope]` in the review file with a `**Demoted-from:** BLOCKING` line was demoted by the stage ceiling and is handled as a NIT, not as a BLOCKING.
     For each finding, run the `mill-receiving-review` decision tree.
   - Apply fixes to plan files.
   - Write a fixer report at `<reviews_dir>/<YYYYMMDD-HHMMSS>-plan-fix-r<N>.md` with two sections: `## Fixed` (each fixed finding, one-line reference to the review file + quoted finding title) and `## Pushed Back` (each rejected finding, same format + reason citing code/doc/scope).
   - Re-validate the plan DAG (`_plan_dag.validate`).
   - `_status.append_phase(status_path, f"plan-fix-r{N}", iso_ts)`.
   - Commit on the task branch: `git -C <worktree> add <plan_dir> <reviews_dir> <status_path> _mill/briefs/ && git -C <worktree> commit -m "mill-plan: plan-fix round {N} for {slug}"`.
     Push.

5. **Non-progress check** (after writing each fixer report from round 2 onward): **Skip this check when the latest round's `## Pushed Back` section is empty.**
   Empty Pushed Back means the planner addressed every finding cleanly — that is convergence, not non-progress.
   The check only fires when both rounds have a non-empty Pushed Back AND the title set is identical.
   When it fires: `_status.set_blocked(status_path, f"non-progress round {N}", timestamp=ts)`;
   commit `git -C <worktree> add <status_path> <reviews_dir> && git -C <worktree> commit -m "mill-plan: blocked (non-progress) for {slug}"` and push;
   halt with "Plan blocked on non-progress at round {N}.
   Task left as [active] for manual review."
   Do not escape-hatch — non-progress means the planner and reviewer are stuck in a stable disagreement;
   user intervention is required.

6. **Max-rounds escape** (only when round counter exhausts without APPROVE, BLOCKINGs still remain, AND non-progress did not fire): `_status.set_blocked(status_path, f"max-rounds exhausted after {N} rounds, {M} BLOCKINGs remain", timestamp=ts)`;
   commit and push;
   halt with "Plan blocked after {N} rounds, the last round's {M} BLOCKING finding(s) were acted on (fixed or pushed back) but not yet re-reviewed.
   Task left as [active] for manual review." `{M}` is `result["blocking_count"]` from the most recent CLI invocation — do not re-count manually.
   Step 4d's fixer pass already ran on those exact findings before this round-cap check fires, so "BLOCKINGs remain" would be misleading at the moment this halt prints — this operator-facing halt text is reworded accordingly; `_status.set_blocked`'s own `blocked_reason` argument keeps its existing, unreworded text (a machine field consumed only by the Entry `blocked` re-entry row's `.startswith("max-rounds exhausted")` prefix check, never read verbatim by a human at that point).
   If `blocking_count` was 0 in the latest round, this halt should not have fired — verify step 4c logic before proceeding.

### Phase: Handoff

**Guard.**
Read `plan_dir / "00-overview.md"` and parse the `approved:` field from the top fenced yaml block.
If it is not the literal boolean `true`, halt with: `BLOCKED: mill-plan Handoff guard -- plan/00-overview.md has approved: false. Plan review did not complete. Re-run /mill-plan to enter Phase: Plan Review.` To parse: extract the YAML block via the existing pattern (`re.search(r"```yaml(.*?)```", overview_text, re.DOTALL)`), then read `approved:` with `yaml.safe_load(yaml_text)["approved"]`.
Reject string `"true"` — the value must be the YAML boolean (overview template writes `approved: false`, the flip in step 4a/4b/4c writes `approved: true` as bare YAML).
The guard runs *before* any `_status` mutation, so a guard failure leaves status.md untouched and the operator can re-enter cleanly.

`_status.append_phase(status_path, "planned", _timestamp.now_utc_iso())`.
Commit+push.

If the deep-merged config has `pipeline.auto_report: true`, invoke `/mill-self-report --auto` and let it finish before reporting to the user.
The skill checks `gh auth` itself and bails cleanly if absent, so this is always safe to call.

Report: **"Plan complete.
Run `/mill-go` next to start autonomous implementation."**
Do not invoke mill-go yourself — handoff to mill-go is always an explicit user decision, even when auto-report fired.

## Timestamps

Always use `_timestamp.now_utc_compact()` / `now_utc_iso()` for any generated timestamp (plan `started:`, fixer-report filenames, status.md timeline rows).
Never hand-write or guess a date.

## Principles

- **Plan the full scope** — no "we'll add X later" phases inside the plan.
- **YAGNI ruthlessly** — don't plan for hypothetical requirements.
- **Follow `mill-receiving-review`'s decision tree** — never dismiss a finding with "low risk", "out of scope", "pre-existing".
- **Autonomous** — mill-plan never waits for an operator reply.
  The max-rounds escape and non-progress check resolve by halting via `_status.set_blocked` instead of prompting.
- **Card `Context:` is an allowlist** — list every file the implementer needs to read WITHOUT editing.
  An empty or terse `Context:` is a review-blocker.
  The implementer reads ONLY listed files;
  any unlisted file is a plan defect. `Edits:` files are implicitly read — do not repeat them in `Context:`.
  All paths must be backtick-wrapped, one per bullet;
  no inline prose, no line-range suffixes.
- **`Requirements:` must use stable identifiers** — name the specific function, class, or constant being changed.
  "Replace `_load_config` in `mill-claim.py` with `from _config import load_config`" is correct.
  "Refactor config loading to use the shared helper" is not — it forces the implementer to explore, defeating the cold-start guarantee.
  Any fenced block quoting exact source text inside `Requirements:` must reproduce the source's own original indentation byte-for-byte and must NOT pick up extra leading whitespace from the surrounding list item's continuation indent — author such fences so their content, read literally, is already a byte-exact substring of the file being quoted, regardless of how deeply the enclosing list item is nested (the source excerpt may legitimately have its own nonzero baseline indentation — e.g. quoting an indented method body — the rule is "no *extra* indentation beyond the source's own," not "no indentation at all").
- **Existing-test-impact check for contract changes** — when a card's `Requirements:` states that it changes an exported function's, method's, or class's existing behavior/contract (not just adding new code), grep the codebase for existing callers and tests of that symbol before finalizing the plan, and add any found to that card's `Context:` (read-only) or `Edits:` (if the test itself needs updating to match the new contract). "Intentionally changes an exported symbol's contract" is a judgment call about the card's own stated design intent — only the planning agent, already reading the full `Requirements:` prose, can reliably make it; a mechanical validator check can't distinguish an intentional contract change from an incidental edit to the same function.
- **Express renames as `Moves:` pairs** — never encode a rename as a `Creates:` + `Deletes:` combination;
  that destroys git rename history and inflates the diff.
  A rename-plus-extraction is the `Moves:` pair for the relocated file plus a separate `Creates:` for the newly extracted file.
  Include a `## Rename mechanic` section in any batch that has a non-empty `Moves:` field.
  Keep naming the specific surgical edits (package declaration, import lines, identifier retargets) in `Requirements:` using stable identifiers.
- **Phrase Requirements: prohibitions on one line; avoid double negatives** — `_plan_validate.py`'s `context-completeness` check exempts a prohibition via a same-line, lexical word-set match (a negation word/phrase paired with a verb form, anywhere on one physical line), not a structural or semantic parse.
  Write "Do not touch `foo.py`" on a single line (negation, verb, and path together) rather than a nested-bullet form (negation on a parent bullet, path on a child bullet) — the check never looks across bullet lines.
  Avoid double-negative phrasing such as "do not skip touching `foo.py`" or "do not forget to read `bar.py`" — the check misreads these as prohibited (a false exemption) even though the path SHOULD be touched/read.
  State prohibitions directly instead.

## Board discipline

- Task-state writes (`status_path`, `plan_dir`, `reviews_dir`) are committed on the task branch via `git add` + `git commit`, then pushed to remote.
  They never go through the wiki.
- Phase transitions via `_status.append_phase`.
  Hand-editing the status.md yaml block is banned;
  use `update_field` for the plan pointer.
- The overview frontmatter's `approved:` field is the exception — it lives in `plan/00-overview.md`, not `status.md`, and is flipped by a direct Edit because `_status.py` only knows about status.md.
