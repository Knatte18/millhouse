# Plan: Remove batch review (plan-review.batch / code-review.batch)

```yaml
task: Remove batch review (plan-review.batch / code-review.batch)
slug: remove-batch-review
approved: true
started: 20260924-074604
parent: main
root: ""
verify: null
skip_checks: ["wiki-config-mutation", "verify-full-suite"]
discussion_sha: 9a0fd464c739c25040e511857220f4b536c4b81c
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: plan-review-backend
    file: 01-plan-review-backend.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-cli.py test-review-plan-finalize-round.py test-review-prepare-envelope.py
  - number: 2
    name: code-review-backend
    file: 02-code-review-backend.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-code-flow.py test-review-cli.py test-review-cli-error-envelope.py test-review-finalize.py
  - number: 3
    name: fixer-and-gates
    file: 03-fixer-and-gates.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-fix.py test-fix-finalize.py test-prior-blocking.py test-nit-gate.py test-language-skills-directive.py
  - number: 4
    name: review-common-and-templates
    file: 04-review-common-and-templates.md
    depends-on: [3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-class-taxonomy.py test-review-templates.py test-review-output-contract.py test-review-summary.py
  - number: 5
    name: config
    file: 05-config.md
    depends-on: [4]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-config.py test-reviewers.py test-large-prompt-switch.py
  - number: 6
    name: mill-go-skill-text
    file: 06-mill-go-skill-text.md
    depends-on: [5]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-phase-wait.py test-skill-helper-drift.py test-mill-go-variants.py test-mill-go-base-agent-only.py test-guards.py
  - number: 7
    name: remaining-skills-docs-and-gate
    file: 07-remaining-skills-docs-and-gate.md
    depends-on: [6]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: batch-parameters-dropped-from-internal-apis

- **Decision:** internal Python APIs drop their batch parameters outright instead of pinning them:
  - `_review_plan.prepare` / `_review_plan.finalize` and `_review_code.prepare` / `_review_code.finalize` lose the `scope` keyword; each always runs the holistic scope.
  - `_review_plan.run` loses `holistic_only` / `no_holistic`; `_review_code.run` loses `batch_name`.
  - `_prior_blocking.build_digest` becomes `build_digest(reviews_dir)`.
  - `_nit_gate._find_final_code_review` becomes `_find_final_code_review(reviews_dir)`.
  - `_review_code._collect_batch_files` becomes `_collect_batch_files(plan_dir)` (every batch file).

  `_review_common.discover_round(reviews_dir, review_type, scope)` and `_review_common.resolve_blocking_classes(cfg, review_type, scope)` keep their signatures (skills call `discover_round(..., "holistic")` directly; see `discover-round-holistic-only` in the discussion).
- **Rationale:** a pinned-but-unused parameter is dead surface that invites a future caller to pass a batch name again.
  Every caller of the dropped parameters is a script or test this plan already edits, so dropping costs no extra churn outside the plan.
- **Applies to:** all batches

### Decision: envelope-and-filename-formats-unchanged

- **Decision:** envelope `scope` fields stay the literal `"holistic"`; review filenames stay `<ts>-<type>-review-r<N>.md`; the `nits-fixed-holistic` timeline marker and the `holistic-reviewing` / `holistic-fixing` / `holistic-approved` phases are untouched.
- **Rationale:** `millpy-review-summary`, `_nit_gate`, `_prior_blocking` and the frontend skills read these formats; the discussion's `millpy-fix-scope-flag` Decision requires them byte-identical.
- **Applies to:** all batches

### Decision: non-holistic-scope-raises

- **Decision:** `_review_common.discover_round` raises `ValueError` for any `scope` other than `"holistic"`.
  `_review_common.write_review_file` keeps its `scope` keyword but raises `ValueError` when it is neither `None` nor `"holistic"`.
  `_review_common.resolve_blocking_classes` always reads the `holistic` scope key and ignores its `scope` argument (every remaining caller passes `None` or `"holistic"`).
- **Rationale:** a stray batch-name caller fails loudly instead of silently writing an unreadable filename or reading a config block that no longer exists.
- **Applies to:** review-common-and-templates

### Decision: diff-scoping-removed-with-batch-review

- **Decision:** the `start_sha` diff-scoping in `_review_code.prepare` only ever ran for a single batch.
  With it gone, `_review_common.bulk_files_with_diff` and the `roles.code-review.diff_scope_threshold` config key have no reader, so both are deleted too.
  `roles.code-review.diff_scope_threshold` joins the discussion's `stale-batch-config-keys-warn` list: it is removed from both config files and gets a `_config.RENAMED_KEY_HINTS` entry.
- **Rationale:** the discussion's scope removes "the `start_sha` diff-scoping for a single batch"; leaving its helper and config key behind would recreate the dead branch this task exists to remove.
  This follows the same reasoning as the discussion's `rename-check-deleted` Decision.
- **Applies to:** code-review-backend, review-common-and-templates, config

### Decision: stale-batch-config-keys-warn

- **Decision:** as recorded in the discussion: `roles.plan-review.batch`, `roles.code-review.batch`, `pipeline.rename_detect_pct` (and `roles.code-review.diff_scope_threshold`, per the Decision above) are removed from the template and the hub config, and added to `_config.RENAMED_KEY_HINTS` with a no-effect hint.
  An existing config that still carries them loads normally and prints the hint.
- **Rationale:** see discussion.
- **Applies to:** config

### Decision: batch-config-removal-safe-mid-flight

- **Decision:** batch 5 edits the hub `mill-config.yaml`; the `wiki-config-mutation` validator check is skipped for this plan.
- **Rationale:** the running mill-go for this task loads config through `_config.load_config`, which deep-merges the plugin-cache template first, then the hub file.
  The plugin cache is frozen at the pre-task version and still carries both `batch:` blocks (`rounds: 0`, `reviewer: null`) and `pipeline.rename_detect_pct`, so the merged config this task's own orchestrator sees keeps those keys after batch 5 removes them from the hub file.
  The cached `mill-go-base` skill therefore still takes its "reviewer is null" shortcut for the remaining batches.
  Card 15 restates this justification.
- **Applies to:** config

### Decision: approved-batch-phase-and-state-enum-kept

- **Decision:** as recorded in the discussion (`approved-batch-phase-kept`): the `approved-<batch>` phase string, its `^approved-.*$` phase-gate regex and `millpy-cleanup.py`'s `_LIVE_PHASE_PATTERNS` stay.
  The batch `state` values `reviewing` / `fixing` stay in `_status.py`, `millpy-status.py` and `millpy-inspect.py`.
  `mill-go-base/resume.md` treats a batch left in `reviewing` / `fixing` by an older plugin version as implementer-complete and routes it to the new `### 3. Complete batch` step.
- **Rationale:** old status.md files must stay readable; no new code writes these states, but a task started under an older plugin may still carry one.
- **Applies to:** mill-go-skill-text

### Decision: historical-readers-tolerant

- **Decision:** as recorded in the discussion: `millpy-review-summary.py` keeps its own `_RE_BATCH` parser; only its comment changes.
- **Rationale:** see discussion.
- **Applies to:** review-common-and-templates

### Decision: done-gate-recommendation

- **Decision:** recommendation for the operator: set `pipeline.done_gate` to `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`.
  The currently effective value is `null`.
  Not applied: mill-go gates on the effective config value, not this Decision.
  No lint command is recommended: `uvx ruff check .` exits non-zero on the current tip with pre-existing, unrelated lint debt.
- **Rationale:** the full unit suite runs in well under a minute and catches regressions outside each batch's scoped `verify:`.
- **Applies to:** all batches

### Decision: final-batch-runs-full-suite

- **Decision:** batch 7's `verify:` is the unscoped `run-all.py`; the `verify-full-suite` validator check is skipped for this plan.
- **Rationale:** the discussion's Testing section makes a green full unit suite the task's acceptance bar, and this task deletes shared helpers (`RE_BATCH`, `detect_resume_round`, `bulk_files_with_diff`, `_moves_check.py`) that any test module could import.
  The full suite runs in well under a minute.
  Batch 7's `## Batch Tests` records the same justification.
- **Applies to:** remaining-skills-docs-and-gate

## All Files Touched

- `doc/backlog.md`
- `mill-config.yaml`
- `plugins/mill/integration_tests/test-go-assets.py`
- `plugins/mill/integration_tests/test-review-plan.py`
- `plugins/mill/scripts/_config.py`
- `plugins/mill/scripts/_nit_gate.py`
- `plugins/mill/scripts/_prior_blocking.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/_reviewer_test_stub.py`
- `plugins/mill/scripts/_reviewers.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/scripts/millpy-review-summary.py`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-go-base/handoff.md`
- `plugins/mill/skills/mill-go-base/holistic-review.md`
- `plugins/mill/skills/mill-go-base/resume.md`
- `plugins/mill/skills/mill-go2/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/templates/review-code-holistic.md`
- `plugins/mill/templates/review-output.schema.md`
- `plugins/mill/templates/review-plan-holistic.md`
- `plugins/mill/unit_tests/_test_cfg.py`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-fix-finalize.py`
- `plugins/mill/unit_tests/test-language-skills-directive.py`
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-nit-gate.py`
- `plugins/mill/unit_tests/test-phase-wait.py`
- `plugins/mill/unit_tests/test-prior-blocking.py`
- `plugins/mill/unit_tests/test-review-class-taxonomy.py`
- `plugins/mill/unit_tests/test-review-cli-error-envelope.py`
- `plugins/mill/unit_tests/test-review-cli.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-finalize.py`
- `plugins/mill/unit_tests/test-review-output-contract.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
- `plugins/mill/unit_tests/test-review-summary.py`
- `plugins/mill/unit_tests/test-review-templates.py`
- `plugins/mill/unit_tests/test-reviewers.py`
