# Batch: mill-plan-discussion-drift-and-interpreter-naming

```yaml
task: 'mill-plan: entry-gate, timeline, and script-portability bugs'
batch: mill-plan-discussion-drift-and-interpreter-naming
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-skill-helper-drift.py test-guards.py
depends-on: []
```

## Batch Scope

Fixes #939 (mill-plan's Phase: Plan self-run validator snippets don't name an interpreter, so a fresh orchestrator reaching for ambient `python3` hits `ModuleNotFoundError: No module named 'pygit2'`) and #938 (mill-plan's entry gate can plan/review against a `discussion.md` that was rewritten after Phase: Plan started reading it, since mill-start's interactive gap-fix fallback can rewrite the file while leaving `phase:` at `discussed`). Both fixes live entirely in `plugins/mill/skills/mill-plan/SKILL.md` — one small clarifying instruction (#939) and a persisted blob-sha drift guard threaded through every LLM-dispatch site in Phase: Plan Review (#938). No batch-local decisions beyond `00-overview.md`'s Shared Decisions.

## Cards

### Card 1: Name `$MILL_PYTHON` explicitly for Phase: Plan's narrative Python calls

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the `### Phase: Plan` section, locate the sentence "Leave `done_gate: null` only when the project has neither a meaningful repo-wide test nor a defined lint command." — this is the last sentence of the "**Done-gate reminder.**" paragraph, immediately before the "**Self-validate the DAG** before committing: call `_plan_dag.extract_batch_index(overview_text)` then `_plan_dag.validate(batches, ...)`." bullet.
  Insert a new paragraph between them, verbatim:

  "**Interpreter-naming note.** Every narrative Python call from this point through the end of Phase: Plan (`_plan_dag.extract_batch_index`/`_plan_dag.validate`, `_plan_validate.run`, `_status.update_field`/`_status.append_phase`, and any other `_<module>.<fn>(...)` reference in this phase) is executed by the orchestrator via `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON"` — never bare `python3` — matching CLAUDE.md's `## Script invocation` convention and the way every `millpy-bg`/`millpy-review-plan.py` invocation elsewhere in this file already names `$MILL_PYTHON` explicitly. A fresh orchestrator session with no other context has previously hit `ModuleNotFoundError: No module named 'pygit2'` here by reaching for the ambient `python3` instead."

  Do not touch any other section of the file for this card.
- **Commit:** `docs(mill-plan): name $MILL_PYTHON explicitly for Phase: Plan's narrative Python calls`

### Card 2: Capture and persist discussion.md blob sha (Phase: Plan)

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Three separate insertions, all within `### Phase: Plan`:

  1. Locate the section's opening sentence "Read `_mill/discussion.md` in full." (immediately followed by "Read `CONSTRAINTS.md` at the hub root if present (via `_constraints.read_if_exists()`)."). Insert a new sentence immediately after it, before the `CONSTRAINTS.md` sentence, verbatim:

     "Immediately capture `discussion_sha = git -C <git_root> rev-parse HEAD:_mill/discussion.md` (or the config-derived relative path from `cfg['paths']['discussion_file']` if it differs) — this pins the exact committed content this plan is written against, before any further reads, forks, or file writes that could race with a concurrent rewrite."

  2. Locate the paragraph beginning "**Persist `skip_checks` for Phase: Plan Review.**" (it ends "...matching the template's convention of omitting optional frontmatter keys that don't apply. Include this edit in the same 'Commit on the task branch' step below — no separate commit."). Insert a new paragraph immediately after it, before the `signature: _status.read(status_path: Path) -> dict` line, verbatim:

     "**Persist `discussion_sha` for drift detection.** Write the `discussion_sha` captured above into `00-overview.md`'s fenced-yaml frontmatter as a new `discussion_sha:` field (parallel to `approved:`/`skip_checks:`), via the same direct-`Edit` convention already used elsewhere in this file for the `approved:` field. Unlike `skip_checks:`, this field is never optional — write it unconditionally on every Phase: Plan run, since every Phase: Plan Review dispatch site (see that phase's own drift-guard subsection, added in batch 1 card 3) depends on it being present. Include this edit in the same 'Commit on the task branch' step below — no separate commit."

  3. Locate the paragraph "**Commit on the task branch.** `git -C <worktree> add <plan_dir> <status_path> && git -C <worktree> commit -m \"mill-plan: write plan for {slug}\"`. Push." — the final paragraph of `### Phase: Plan`, immediately before the `### Phase: Plan Review` heading. Insert a new paragraph immediately before this "**Commit on the task branch.**" paragraph, verbatim:

     "**Pre-commit drift check.** Immediately before committing, re-run `git -C <git_root> rev-parse HEAD:_mill/discussion.md` and compare against the `discussion_sha` captured at the top of this phase. On a mismatch: discard the written-but-uncommitted plan files (`git -C <worktree> clean -fd <plan_dir>`, since nothing under `plan_dir` has been added/committed yet), halt via `_status.set_blocked(status_path, \"discussion.md changed after Phase: Plan entry (blob sha drift)\", timestamp=_timestamp.now_utc_iso())`, commit that status change alone on the task branch (`git -C <worktree> add <status_path> && git -C <worktree> commit -m \"mill-plan: blocked (discussion.md blob sha drift) for {slug}\"`), push, and halt with: `BLOCKED: discussion.md changed after Phase: Plan entry (blob sha drift). Delete _mill/plan/ and re-run /mill-plan for a fresh plan against the current discussion.md.` Do not proceed to commit the plan when this fires."

  Do not touch `### Phase: Plan Review` in this card — that is card 3.
- **Commit:** `feat(mill-plan): capture and persist discussion.md blob sha for drift detection`

### Card 3: Enforce discussion drift guard at every Plan Review LLM-dispatch site

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  This card depends on card 2's `discussion_sha:` frontmatter field already existing (same batch, prior card — implement in card order). All insertions are within `### Phase: Plan Review`.

  1. **Define the reusable guard.** Locate the paragraph "**Read persisted `skip_checks` from Phase: Plan.**" (it ends "...so Phase: Plan Review's own validator gate does not re-flag a finding Phase: Plan already resolved and committed against."), immediately followed by a paragraph beginning "When `revise_from_blocked` is set (bound at Entry step 4's `--revise` pre-check)...". Insert a new paragraph between them, verbatim:

     "**Discussion drift guard (reused at every LLM-dispatch site in this phase).** Parse `00-overview.md`'s fenced-yaml frontmatter (same extraction pattern used for `approved:`/`skip_checks:`) and read `plan_discussion_sha = <parsed discussion_sha: field>`. Before every point in this phase where an LLM is actually dispatched or re-dispatched — in both Agent-mode and subprocess/psmux-mode, with no exception for a call that doesn't consume the round counter — re-run `git -C <git_root> rev-parse HEAD:_mill/discussion.md` and compare against `plan_discussion_sha`. Known dispatch points today (audit this file's current LLM-dispatch call sites at implementation time if this file has changed since this plan was written): step 2's initial per-round dispatch (both branches); Step 1.5's validator-fix re-invocation, in both its Agent-mode form ('Agent-mode prepare-envelope handling', the re-render-brief/call-Agent/finalize cycle) and its subprocess/psmux form (the `millpy-bg` re-run under slug `plan-validator-fix`); and step 3.5's ERROR-only-aggregate retry re-dispatch (both branches). On a mismatch at any of these: halt via `_status.set_blocked(status_path, \"discussion.md changed after Phase: Plan entry (blob sha drift)\", timestamp=_timestamp.now_utc_iso())`, commit that status change alone on the task branch (`git -C <worktree> add <status_path> && git -C <worktree> commit -m \"mill-plan: blocked (discussion.md blob sha drift) for {slug}\"`), push, and halt with: `BLOCKED: discussion.md changed after Phase: Plan entry (blob sha drift). Delete _mill/plan/ and re-run /mill-plan for a fresh plan against the current discussion.md.` Do not proceed with the dispatch about to happen. Recovery is manual, matching this file's own pattern for every non-max-rounds blocked state — neither a bare `/mill-plan` re-run (hard-stopped by the Entry table's `phase: blocked` row) nor `/mill-plan --revise` (which resumes the existing plan without recapturing `discussion_sha`) reaches Phase: Plan again on its own; the operator must delete `plan_dir` and start fresh."

  2. **Step 2, Agent-mode branch.** Locate the sentence "Tree-guard checkpoint (Agent-mode only, pre-dispatch): call _treeguard.check_and_restore(worktree_root, \"_mill\", git_root=git_root) — and, on trigger, _status.append_recovery_log(result[\"timestamp\"], result[\"restored_paths\"]) — immediately before the Agent-mode dispatch below." (immediately preceded by "**Dispatch mode:** Resolve dispatch mode via `_agent_dispatch.resolve_dispatch_mode(cfg)`." and immediately followed by "This does not apply to the subprocess/psmux branch, which keeps its existing worktree_snapshot_guard coverage unchanged."). Insert immediately before this sentence, verbatim: "Run the discussion drift guard (see 'Discussion drift guard' above) now, before this checkpoint."

  3. **Step 2, subprocess/psmux branch.** Locate the blockquote "> **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree..." that immediately precedes the `millpy-review-plan.py` invocation under "**Subprocess/psmux branch — Invoke the CLI as a subprocess:**" (the one followed shortly by `--slug plan-review-r<N> --`). Insert immediately before this blockquote, verbatim: "Run the discussion drift guard (see 'Discussion drift guard' above) now, before invoking `millpy-bg`."

  4. **Step 1.5, Agent-mode form.** Locate the sentence "Then re-invoke the prepare stage via the same three-step Agent-mode dispatch (re-render brief, call Agent, finalize; the same cycle repeats)." inside "**Agent-mode prepare-envelope handling:**". Insert immediately before this sentence, verbatim: "Run the discussion drift guard (see 'Discussion drift guard' above) now, before this re-invocation."

  5. **Step 1.5, subprocess form.** Locate the sentence "After fixes, mill-plan re-runs the review CLI via millpy-bg (slug `plan-validator-fix`; still no round consumed)." inside step 1.5's numbered list. Insert immediately before this sentence, verbatim: "Run the discussion drift guard (see 'Discussion drift guard' above) now, before this re-run."

  6. **Step 3.5, Agent-mode branch.** Locate the sentence "Tree-guard checkpoint (Agent-mode only, pre-dispatch): call _treeguard.check_and_restore(worktree_root, \"_mill\", git_root=git_root) — and, on trigger, _status.append_recovery_log(result[\"timestamp\"], result[\"restored_paths\"]) — immediately before this retry's Agent-mode dispatch." (immediately followed by "Does not apply to the Subprocess/psmux branch immediately below."). Insert immediately before this sentence, verbatim: "Run the discussion drift guard (see 'Discussion drift guard' above) now, before this checkpoint."

  7. **Step 3.5, subprocess/psmux branch.** Locate the second occurrence of the blockquote "> **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree..." — the one under Step 3.5's own "**Subprocess/psmux branch:**" heading, immediately preceding the `--slug plan-review-retry-r<N> --` invocation. Insert immediately before this blockquote, verbatim: "Run the discussion drift guard (see 'Discussion drift guard' above) now, before invoking `millpy-bg`."

  Do not modify `plugins/mill/skills/mill-go-base/SKILL.md` (read-only Context: for confirming the shared Agent-mode dispatch pattern's step numbering referenced above) — all edits in this card are confined to `plugins/mill/skills/mill-plan/SKILL.md`.
- **Commit:** `feat(mill-plan): enforce discussion drift guard at every Plan Review LLM-dispatch site`

## Batch Tests

`verify:` runs `test-skill-helper-drift.py` (asserts every `_<module>.<fn>(` reference this batch introduces — `_status.set_blocked`, `_status.append_phase` — resolves to a real shipped function; both are already used elsewhere in this same file, so no new helper is introduced) and `test-guards.py` (catches anti-patterns like stray non-ASCII arrows or unguarded venv checks that a careless prose edit could introduce). No Python source files are touched by this batch, so the broader suite is out of scope per mill-plan's "Verify command scope" guidance.
