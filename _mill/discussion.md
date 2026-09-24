# Discussion: Remove batch review (plan-review.batch / code-review.batch)

```yaml
task: Remove batch review (plan-review.batch / code-review.batch)
slug: remove-batch-review
status: discussing
parent: main
```

## Problem

mill has two per-batch review stages: per-batch plan review (`roles.plan-review.batch`) and per-batch code review (`roles.code-review.batch`).
Both were turned off almost as soon as they shipped because they cost too much.
The hub config sets `rounds: 0` and `reviewer: null` for both, and no workflow uses them.
They still add code paths, config keys, templates, skill text and tests.
Every change to the review backends or to `mill-go-base` has to work around this dead branch, and new readers mistake it for live behaviour.
This task removes both stages for good.
The holistic reviews do the real review work and stay.

## Scope

**In:**

- Config: `roles.plan-review.batch` and `roles.code-review.batch` blocks in the hub `mill-config.yaml` and `plugins/mill/templates/mill-config.yaml`.
  Also the `MILL_PLAN_BATCH_REVIEWER` and `MILL_CODE_BATCH_REVIEWER` env overrides: the template header comment and the `ENV_REGISTRY` entries in `plugins/mill/scripts/_config.py`.
  Also `pipeline.rename_detect_pct` in both config files, because only per-batch code review uses it (see Decisions).
- Templates: delete `review-plan-batch.md`, `review-code-batch.md` and `fixer-batch-brief.md`.
  Both `review-plan-holistic.md` and `review-code-holistic.md` currently say "Severity / verdict rules match review-<type>-batch.md".
  Inline those rules into each holistic template before deleting the batch templates (see Decisions).
- Update `plugins/mill/templates/review-output.schema.md`: remove the "Plan per-batch" filename row, the `<batch-name>` naming bullet, and "batch file" from the `reviewed_file` description.
- Scripts, per-batch branches only:
  - `_review_plan.py`: `_scan_approved_batches`, `_review_one_batch`, the per-batch branch of `prepare`, the per-batch fan-out, mid-round resume and approved-batch carryforward in `run`, and the `holistic_only` / `no_holistic` parameters.
  - `_review_code.py`: the per-batch branch of `prepare`, the `start_sha` diff-scoping for a single batch, `_splice_rename_nit_findings`, the `batch_name` path of the legacy `run()`, and the `review-code-batch` template selection.
  - `_review_common.py`: `RE_BATCH`, `detect_resume_round`, the per-batch branch of `discover_round`, the per-batch review filename form, and the `"batch"` scope key in `resolve_blocking_classes`.
  - `_prior_blocking.py`: the `batch` scope and `batch_name` parameter.
  - `_nit_gate.py`: the `approved-<batch>` scope discovery and the `RE_BATCH` file lookup.
  - `_moves_check.py`: delete it; its only consumer is `_review_code._splice_rename_nit_findings`.
  - `millpy-review-plan.py`: drop the `--holistic-only` and `--no-holistic` flags and the batch wording in `--max-rounds` / `--reviewer` help.
  - `millpy-review-code.py`: drop the `--batch` flag, its status.md guard, and the batch wording in `--max-rounds` help.
  - `millpy-fix.py`: drop `--batch-name`, restrict `--scope` to `holistic`, and remove the `fixer-batch-brief.md` render path.
  - `_reviewers.py`: fix the docstring example `(e.g. "batch")`.
- Skills:
  - `mill-go-base/SKILL.md` Entry: the `roles.code-review.batch.*` config reads.
  - `mill-go-base/SKILL.md` "Mid-execution phase-gate widening": the `reviewing-{batch}-rN` / `fixing-{batch}-rN` routes and regexes.
  - `mill-go-base/SKILL.md` `### 3. Code Review loop`: replace it with a batch-completion step (see Decisions).
  - `mill-go-base/SKILL.md` Agent-mode dispatch: the `--batch-name (batch scope only)` wording.
  - `mill-go-base/resume.md`: the batch-review resume branches (batch `state` `reviewing` / `fixing`, which re-dispatch `millpy-review-code.py --batch` / `millpy-fix.py --scope batch`).
  - `mill-go-base/handoff.md`: the per-batch forms in the prior-blocking digest and NIT-fix re-dispatch.
  - `mill-plan/SKILL.md`: grep the file for `--holistic-only|--no-holistic|plan-review\.batch|per-batch` and fix every hit, not just the descriptive ones.
    Known today:
    - two operative dispatch sites pass `<args> = --holistic-only` (Phase: Plan Review step 2's Agent-mode dispatch, ~line 471, and the ERROR-only retry, ~line 558); drop the flag from both, keeping the `--skip-check` args;
    - the "plan batch review is disabled in this hub" note (~line 473);
    - the cost-line aside about a per-batch scope printing one line per scope (~line 510);
    - the scope-flag description (~lines 528–530).
  - `mill-go2/SKILL.md` line ~50: narrow "`{scope}` is the batch name, or `holistic`" to "`{scope}` is `holistic`" for the fixer fork-fallback log, notify and commit-message forms.
    The implementer fork-fallback text there (`{batch_name}`, "once per batch") is about plan batches and stays.
  - Any other skill text that describes batch review as a live stage, found by grep during planning.
- Tests: delete or rewrite every test that exercises the batch stage, then extend the tests listed under Testing.
  Known files:
  - `test-config.py`
  - `test-review-plan-flow.py`
  - `test-review-code-flow.py`
  - `test-review-common.py`
  - `test-review-templates.py`
  - `test-review-output-contract.py`
  - `test-prior-blocking.py`
  - `test-nit-gate.py`
  - `test-millpy-fix.py`
  - `test-language-skills-directive.py` (its `fixer-batch-brief.md` case)
  - `test-moves-check.py` (delete)
  - `test-fix-finalize.py`: Test 5 (nested-layout batch-scope verify `cwd_override` at finalize) and Test 6 (`--scope batch` forwards `batch_verify_baseline`) both invoke `millpy-fix.py --scope batch --batch-name test-batch`.
    Delete Test 6, since Test 7 already covers baseline forwarding for holistic scope.
    Rewrite Test 5 against `--scope holistic`, so that `cwd_override` threading at the finalize stage keeps coverage; mock `iter_batch_verifies` to return one batch with the nested-hub cwd.
    Drop it only if an existing holistic test already asserts that threading.
  - `test-reviewers.py`, `test-review-cli.py`, `test-review-cli-error-envelope.py`, `test-review-prepare-envelope.py` and `_test_cfg.py`, where they reference batch-scope config or flags

**Out:**

- The holistic reviews (`discussion-review.holistic`, `plan-review.holistic`, `code-review.holistic`): their behaviour is unchanged.
- Other uses of the word "batch":
  - plan batches and the batch DAG (`_plan_dag`);
  - `pipeline.max_cards_per_batch` and `pipeline.max_batch_context_tokens`;
  - per-batch `verify:`;
  - implementer and fixer dispatch per batch;
  - the `Moves:` / `Edits:` / `Creates:` / `Deletes:` plan fields and `parse_moves` / `parse_batch_refs` / `compute_*_union` in `_review_common.py` (holistic review and the plan validator still use them);
  - the `## Batches` table in status.md and its `state` values;
  - the wiki `upsert_tasks_batch` operation;
  - `millpy-status.py`'s `BATCH` column.
- `millpy-review-summary.py`'s own `_RE_BATCH` parser and `millpy-cleanup.py`'s `_LIVE_PHASE_PATTERNS`: both stay (see Decisions).
- `doc/turn-reduction-audit.md`: a point-in-time audit report that records the pipeline as it was measured; it is not edited.
- The batch `state` values `reviewing` / `fixing` in `_status.py`, `millpy-status.py` and `millpy-inspect.py` stay.
  `millpy-fix.py` sets `state: fixing` on the holistic path too, so the plan must check each consumer before removing any state value.
  The default is to leave the enum alone.

## Decisions

### stale-batch-config-keys-warn

- Decision: after the `batch:` blocks are gone from the template, a hub or `config.local.yaml` that still carries `roles.plan-review.batch` or `roles.code-review.batch` loads normally.
  `_config.warn_unknown_keys` reports the block through its existing unknown-key path.
  Add both paths, plus `pipeline.rename_detect_pct`, to `_config.RENAMED_KEY_HINTS`, with a hint that per-batch review was removed and the key has no effect.
  `walk_unknown_keys` reports a whole unknown subtree as one dotted block path (`roles.plan-review.batch`), not per leaf, so a `RENAMED_KEY_HINTS` entry on the block path matches.
- Rationale: many hubs and local overrides still carry these blocks, because the template seeded them.
  A hard failure would break every existing hub on its next plugin update.
  The warn path already exists for `pipeline.max_review_rounds`, so this follows an established pattern.
- Rejected: raising `ConfigError`, because it breaks existing hubs for no benefit.
  Silently ignoring the keys, because users would never learn to clean them up.

### approved-batch-phase-kept

- Decision: `mill-go-base`'s `### 3. Code Review loop` becomes a short batch-completion step with the same effect as today's "reviewer is null" shortcut:
  - set batch state → `approved`;
  - `_status.append_phase(status_path, f"approved-{batch_name}", ...)`;
  - commit with the message `<VARIANT_LABEL>: approve batch {batch_name}`, without the "(per-batch review disabled)" suffix;
  - continue to the next batch.

  Rename the heading so it no longer says "Code Review", for example `### 3. Complete batch`, and update cross-references to it.
  The `approved-<batch>` phase string and the `^approved-.*$` phase-gate regex stay.
- Rationale: `approved-<batch>` is the marker between batches that entry-gate resume and `millpy-cleanup` rely on, and every run already writes it.
  Renaming it would break resume for in-flight tasks and would need cleanup-pattern changes, and nothing would be gained.
- Rejected: renaming the phase to something like `completed-<batch>`.

### millpy-fix-scope-flag

- Decision: `millpy-fix.py` keeps `--scope` but accepts only `holistic`.
  `--batch-name` and the `fixer-batch-brief.md` render path are removed.
  Internal Python APIs drop their batch parameters outright:
  - `_prior_blocking.build_digest(reviews_dir, scope)` keeps `scope` but asserts `scope == "holistic"`, or drops it; the planner picks one and updates every caller;
  - `_review_plan.prepare` / `finalize` and `_review_code.prepare` / `finalize` drop the `scope` parameter, or pin it to holistic.

  Envelope `scope` fields, review filenames (`<ts>-<type>-review-r<N>.md`) and the `nits-fixed-holistic` timeline marker stay byte-identical.
- Rationale: the `--scope holistic` CLI contract is written into skill text, into resume and handoff dispatches, and into the `nits-fixed-<scope>` marker that `_implementer_common` derives from the scope.
  Keeping the flag avoids churn in callers and in-flight tasks.
  The envelope and filename formats are read by `millpy-review-summary`, `_nit_gate`, `_prior_blocking` and the frontend skills, so they must not change.
- Rejected: removing `--scope` entirely, which means churn in every skill call site and in marker naming for no behaviour gain.

### rename-check-deleted

- Decision: delete `_review_code._splice_rename_nit_findings`, `_insert_nit_blocks_before_verdict` (if nothing else uses it), `_moves_check.py`, `test-moves-check.py` and the `pipeline.rename_detect_pct` config key.
- Rationale: the advisory rename-NIT check only runs inside per-batch code review finalize.
  It needs a single batch's `start_sha` and `Moves:`, and the holistic path never calls it.
  With batch review gone it is dead code.
- Rejected: porting it to holistic review.
  That is new behaviour, out of scope for a removal task, and can be filed separately if wanted.

### holistic-templates-self-contained

- Decision: before deleting `review-plan-batch.md` / `review-code-batch.md`, copy the severity and verdict rule text those files hold into `review-plan-holistic.md` / `review-code-holistic.md`.
  That is the `Severity:` / `Verdict:` definitions, for example `review-code-batch.md` lines ~121–131.
  The copy replaces the "Severity / verdict rules match review-<type>-batch.md" line in each holistic template.
  Skip any rule a holistic template already states; the "Severity vocabulary is closed" and class-axis paragraphs are already in both.
- Rationale: the holistic reviewer gets only its rendered template.
  The pointer names a file the reviewer never sees, so the rules must live inline once the batch file is gone.
- Rejected: dropping the pointer line without inlining, which would silently lose the severity/verdict definitions.

### historical-readers-tolerant

- Decision: `millpy-review-summary.py` keeps its own `_RE_BATCH` regex so that `_mill/reviews/` directories from older tasks that ran batch review still summarise correctly.
  Update its comment so it no longer says per-batch reviews are "written for every mill-go batch"; they are historical.
  `millpy-cleanup.py`'s `_LIVE_PHASE_PATTERNS` (`reviewing-.+-r\d+`, `fixing-.+-r\d+`, `approved-.+`) stay unchanged so that old status.md files still classify.
  `_review_common.RE_BATCH` is removed; `millpy-review-summary.py` does not import it.
- Rationale: the task brief requires that status and phase history written by older tasks stays readable.
  These two scripts are the ones that read old history; everything else only acts on the current task.
- Rejected: stripping batch parsing from the summary, which would break the task brief's care point.

### discover-round-holistic-only

- Decision: `_review_common.discover_round(reviews_dir, review_type, scope)` keeps its signature, so the callers in mill-start and mill-go skills stay unchanged.
  Its per-batch branch (the `RE_BATCH` match for non-holistic scopes) is removed.
  A non-`"holistic"` scope raises `ValueError`.
  `resolve_blocking_classes` always resolves the `holistic` scope key and ignores any non-holistic scope argument, as long as every caller passes `None` or `"holistic"`.
  The planner checks the call sites.
- Rationale: `mill-start` and `mill-go` call `discover_round(..., "holistic")` directly from skill text, so a signature change would ripple into skills for no gain.
- Rejected: dropping the `scope` parameter from `discover_round`.

## Technical context

- Config loading: `_config.load_config(hub_root, worktree_root)` deep-merges the plugin template, the hub `mill-config.yaml` and `.millhouse/config.local.yaml`, then calls `warn_unknown_keys(check_cfg, template_cfg, ...)`.
  `walk_unknown_keys` walks the actual config against the template, so any key missing from the template is reported as unknown.
  `RENAMED_KEY_HINTS` maps dotted paths to hint text.
  `ENV_REGISTRY` (lines ~45–52) maps `MILL_*` env vars to config paths.
- `_review_common.py` wrapper `load_config` and `resolve_blocking_classes` (~line 2873) choose the scope key `"holistic"` vs `"batch"`.
  `DEFAULT_BLOCKING_CLASSES` is keyed per role, not per scope.
- `_review_plan.run` (~line 789) is the subprocess `--stage full` legacy API.
  It does a parallel per-batch fan-out (`ThreadPoolExecutor`, `_reviewer_test_stub` notes this) followed by holistic.
  `detect_resume_round` and `_scan_approved_batches` exist only for that fan-out.
  After removal `run` reviews only the holistic scope.
  Keep its all-ERROR → ERROR aggregation and its `reviewer_override` / `reviews_subdir` / `allow_missing_refs` parameters.
- `_review_code.prepare` (~line 212) branches on `scope is not None` for:
  - round-cap lookup (`roles.code-review.batch.rounds`);
  - `_collect_batch_files(plan_dir, scope, ...)`, where `None` means every batch;
  - `start_sha` diff-scoping;
  - reviewer lookup;
  - template choice;
  - the `batch_name` prompt token.

  Keep `_collect_batch_files` for the all-batches case only.
  `_review_code.run` (~line 648) is the legacy entry point with `batch_name`.
  Both finalize and `run` call `_splice_rename_nit_findings` only when `scope` / `batch_name` is set.
- `millpy-fix.py` supports `--scope {batch,holistic}`; the batch path renders `templates/fixer-batch-brief.md` (~line 580).
  Holistic uses `fixer-holistic-brief.md`, and that path joins every batch's verify command via `_plan_dag.iter_batch_verifies`, which stays.
- `_nit_gate.compute_unfixed_nits` scans the timeline for `approved-<batch>` and `holistic-approved` scopes and finds each scope's final code-review file via `RE_BATCH` / `RE_SIMPLE`.
  After removal it checks the holistic scope only.
  `approved-<batch>` rows are still written but no longer create a NIT-gate scope, because no per-batch review file can exist.
- `mill-go-base/SKILL.md`, `### 3. Code Review loop` (~lines 735–873): the first paragraph is the disabled shortcut; everything after it is per-batch review machinery (convergence gate, rounds, NIT-fix, REQUEST_CHANGES fixer, round-cap handling).
  `### Stuck escalation` (~line 874) may be referenced only from the removed loop.
  The planner checks whether implementer-stage stuck handling still uses it and removes only what becomes unreachable.
- `mill-go-base/SKILL.md`'s Entry-gate phase predicate (~line 146) and `_phase_wait` trigger sets list `reviewing-.*-r\d+` / `fixing-.*-r\d+`.
  Those phases are written only by per-batch review; holistic uses `holistic-reviewing` / `holistic-fixing` / `holistic-approved`.
  Grep `_phase_wait.py`, `mill-plan/SKILL.md` and `mill-go-base` for every copy of the pattern.
- `mill-plan/SKILL.md` ~line 473 notes that "plan batch review is disabled in this hub"; ~lines 528–530 describe `--holistic-only` / `--no-holistic`.
- `review-output.schema.md` lists review filename forms (~line 142) and `reviewed_file` (~line 54).
- `SKILLS.md` at the repo root is generated by `mill-skills-index` from SKILL.md frontmatter.
  Regenerate it only if a changed skill's `description:` mentions batch review.
  A grep today finds none.
- `doc/backlog.md` ~line 332 names a `{reviewer|batch|holistic}` config slot.
  Drop `batch` from that list.
- Per CLAUDE.md, the hub `mill-config.yaml` and the plugin template must stay in sync.

## Testing

- Run the whole unit suite with `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`, or the repo's equivalent `run-all.py` invocation; it must be green.
- `test-config.py`:
  - A config carrying `roles.plan-review.batch` / `roles.code-review.batch` blocks and `pipeline.rename_detect_pct` loads without raising and prints the removed-key hint to stderr.
  - The template no longer contains either batch block.
  - `MILL_PLAN_BATCH_REVIEWER` / `MILL_CODE_BATCH_REVIEWER` are gone from `ENV_REGISTRY`.
  - Replace `test_load_config_rename_detect_pct_key_present` with the stale-key warning test.
- `test-review-common.py`: `discover_round` for holistic scope still counts `RE_SIMPLE` files, and ignores a leftover per-batch-named file in the reviews dir.
  `resolve_blocking_classes` resolves holistic for `None` and `"holistic"`.
  Delete the `detect_resume_round` tests.
- `test-review-plan-flow.py`, `test-review-code-flow.py`: remove the per-batch flows.
  Keep and adjust the holistic flows so they still cover prepare, finalize and the legacy `run`.
- `test-review-templates.py` / `test-review-output-contract.py`: drop the batch template names.
  Add an assertion that each holistic template renders with the inlined severity/verdict rules and no longer mentions `review-*-batch.md`.
- `test-millpy-fix.py`: remove batch-scope cases and the `fixer-batch-brief.md` content test.
  Add a case where `--scope batch` is rejected by argparse.
- `test-prior-blocking.py`, `test-nit-gate.py`: remove batch-scope cases.
  Add a NIT-gate case where a timeline with `approved-<batch>` rows and a holistic review with NITs requires only `nits-fixed-holistic`.
- `test-review-summary.py`: add a case where a reviews dir with historical per-batch filenames still parses.
- Grep gate as a final check: `git grep -n -E "plan-review\.batch|code-review\.batch|BATCH_REVIEWER|review-(plan|code)-batch|fixer-batch-brief|rename_detect_pct|--holistic-only|--no-holistic|--batch-name"` returns hits only in:
  - `doc/turn-reduction-audit.md`;
  - `_mill/`;
  - `RENAMED_KEY_HINTS` and its test.

## Q&A log

- **Q:** Stale `batch:` blocks in existing configs — warn or reject? **A:** [auto-pick] Warn via `RENAMED_KEY_HINTS`, no crash. **Why:** existing hubs were seeded with these blocks; a hard failure breaks every hub on plugin update.
- **Q:** Keep or rename the `approved-<batch>` phase? **A:** [auto-pick] Keep it as the batch-completion marker. **Why:** entry-gate resume and cleanup depend on it; renaming breaks in-flight tasks for no gain.
- **Q:** `millpy-fix.py --scope`: remove or restrict? **A:** [auto-pick] Keep, restricted to `holistic`; drop `--batch-name`. **Why:** skill call sites and the `nits-fixed-<scope>` marker depend on the flag.
- **Q:** What happens to the rename check (`rename_detect_pct`, `_moves_check.py`)? **A:** [auto-pick] Delete it. **Why:** only per-batch code-review finalize calls it; porting it to holistic is new behaviour.
- **Q:** Historical readers (`millpy-review-summary`, `millpy-cleanup` phase patterns)? **A:** [auto-pick] Keep them tolerant of old batch-review files and phases. **Why:** the task brief requires old history to stay readable.
