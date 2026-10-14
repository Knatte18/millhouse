# Discussion: Drop the eager verify-baseline pre-flight

```yaml
task: Drop the eager verify-baseline pre-flight
slug: drop-verify-baseline-preflight
status: discussing
parent_branch: main
```

## Problem

Before batch 1 of every task, mill-go runs `millpy-implement.py --stage baseline`.
It executes the plan's verify commands against the task worktree, records which tests already fail
(`module_verify_baseline` / `module_verify_baseline_signatures` at task scope, `verify_baseline_failures` per batch in status.md),
and the batch verify gates then waive exactly those failures.
`mill-merge-in` recomputes the same cache after every parent sync (`millpy-merge-in-subagent.py --recompute-baseline`),
and the holistic fixer's finalize (`millpy-fix.py`) forwards the cache into its own verify replay.

The effect is "keep implementing on a red parent, with the regression gate off for the tests that are already red" —
the tests most likely to be touched by the work in flight.
The owner's principle: a test that fails on parent should not exist, and a verify that fails on parent is a stop condition, not a fact to work around.
Evidence: in NORCE-DrillingAndWells/Models the cache has never been non-empty (156 recorded values, all `[]`);
in millhouse it fired six times, each time disabling the gate for already-red tests.
Issue #1191 measured the pre-flight at 22, 87 and 7 minutes for a ~2-minute `dotnet test`.
Removing it moves the first-test-run penalty onto batch 1's own verify instead of eliminating it;
the case for removal is what the mechanism does to the gate, not the clock.

Why now: #1102 argued for removal and was closed as consolidated into a wiki task that was never created, so the pre-flight kept running.

## Scope

**In:**

- Delete `plugins/mill/scripts/_verify_baseline.py`.
- `plugins/mill/scripts/millpy-implement.py`: remove the `baseline` choice from `--stage`, the `--stage baseline` branch in `main()`, and every helper serving only it:
  `_baseline_exclusion_prefixes`, `_baseline_preflight_skip_reason`, `_porcelain_snapshot`, `_warn_new_dirt`, `_module_wide_skip_or_cached_payload`, `_run_module_wide_standalone`, `_run_per_batch_baseline_standalone`, `_run_baseline_stage`
  (plan must confirm each has no other caller before deleting — `_porcelain_snapshot`/`_warn_new_dirt` in particular).
  Remove the `import _verify_baseline`, the `module_verify_baseline` / `batch_verify_baseline` reads and their forwarding into finalize/full,
  and the `batch_name is required unless --stage baseline` special case (batch_name becomes plainly required for every remaining stage).
  Drop the `pipeline.baseline_verify_timeout_minutes` read.
- `plugins/mill/scripts/_status.py`: remove `get/set/clear_module_verify_baseline`, `get/set_module_verify_baseline_signatures`, `_MODULE_VERIFY_BASELINE_STATES`, `_baseline_anchor_index`, the module docstring's API lines for them,
  and `verify_baseline_failures` from `_BATCH_ALLOWED_KEYS` and the batch writer's key `order` list (plus the comment citing it as the list-value example).
- `plugins/mill/scripts/_implementer_common.py`: remove the `module_verify_baseline` and `batch_verify_baseline` parameters from `_run_verify_gates` and from every function that only threads them through (the call sites around the gate-calling functions and their docstrings);
  delete the subset-diff waiver and the `"pre-existing-failures"` module-wide skip, so `_run_verify_gates` means "batch verify passes, then module-wide verify passes", full stop.
  Remove the stuck dict's `"signatures"` field from `_run_verify_gate` and delete `_normalize_failure_signature` (see Decision `signatures-field`).
  `_extract_failure_signatures` stays.
- `plugins/mill/scripts/millpy-fix.py`: remove the holistic-finalize reads of `module_verify_baseline` and the per-batch union of `verify_baseline_failures`, and stop passing both kwargs to `finalize_from_output`.
  The module-wide verify derivation (`module_wide_verify_cmd`, `module_wide_cwd_override`) stays — rewrite the comment above it, which currently justifies it by the waiver.
- `plugins/mill/scripts/millpy-merge-in-subagent.py`: remove the `--recompute-baseline` flag, `_run_recompute_baseline`, `import _verify_baseline`, the docstring lines, and the `--mode is required unless --recompute-baseline` special case (`--mode` becomes plainly required).
- `plugins/mill/skills/mill-merge-in/SKILL.md`: delete section `### 3.5. Baseline recompute` in full, including its trailing Rationale paragraph; fix any prose elsewhere in that file that refers to step 3.5 or the recompute.
- `plugins/mill/skills/mill-go-base/SKILL.md`:
  delete section `### 0.5. Baseline pre-flight (first batch of the task only)` in full;
  delete the `**Speculative baseline launch.**` bullet (and its sub-bullets) in `### Entry-gate wait for upstream mill-plan`;
  rewrite the `### 0.55.` section's references to "0.5. Baseline pre-flight" so it points at `### 1. Implement` as the next step and no longer describes its guard as "same guard shape as 0.5".
  Grep the whole file (and `plugins/mill/skills/mill-go-base/*.md`) for `0.5`, `baseline-preflight`, `--stage baseline`, `module_verify_baseline`, `verify_baseline_failures` afterwards.
- `mill-config.yaml` (hub) and `plugins/mill/templates/mill-config.yaml`: remove the `baseline_verify_timeout_minutes` line from both, in sync.
- Tests: delete `plugins/mill/integration_tests/test-baseline-waiver.py`, `plugins/mill/integration_tests/test-verify-baseline.py`, `plugins/mill/unit_tests/test-verify-baseline.py`;
  remove baseline cases from `test-millpy-implement.py`, `test-implementer-common.py`, `test-status.py`, `test-millpy-fix.py`, `test-fix-finalize.py`, `test-millpy-merge-in-subagent.py` (see Testing).
- Present-tense comments that cite removed code: `plugins/mill/scripts/_long_path.py:7`, `plugins/mill/scripts/_worktree.py:272`, `plugins/mill/unit_tests/test-worktree.py:547` and `:597`.
  Rephrase to describe the still-real failure mode (a lingering dotnet testhost/MSBuild handle after a verify run) without naming `_verify_baseline.py` or `--stage baseline`.

**Out:**

- `pipeline.done_gate_baseline_preflight`, `_done_gate.run_preflight`, and mill-go-base `### 0.55. Done-gate baseline pre-flight` — a different, opt-in mechanism that shares the word "baseline". It stays; only its cross-references to 0.5 change.
- `_done_gate.py` and its use of `_implementer_common._extract_failure_signatures`.
- Anything in consuming repos (e.g. NORCE-DrillingAndWells/Models' `NORCE.Models.NumericalBaseline`, `-p:RunBaseline=true`). Mill does not invoke them and must not start.
- Fixing millhouse's nine already-failing unit tests on `main` (`test-bg-liveness.py`, `test-long-path.py`, `test-mill-go-base-agent-only.py`, `test-junction.py`, `test-millpy-validate-plan.py`, `test-phase-wait.py`, `test-shortcut-wrapper.py`, `test-safe-rmtree.py`, `test-plan-validate.py`). Sequenced as a follow-up task.
- Any replacement check — no lazy baseline, no cheaper parent-branch probe.
- Historical/measurement docs that mention the mechanism: `doc/turn-reduction-audit.md`, `plugins/mill/unit_tests/BENCHMARK.md`, and history-describing comments in `test-cleanup.py:157` and `test-long-path.py:7`.
- Migrating existing status.md files (see Decision `no-status-migration`).
- The companion task on instrumenting/bounding the verify runner.

## Decisions

### outright-removal

- Decision: remove the pre-flight, the waiver, the merge-in recompute and the status fields outright; add nothing in their place.
- Rationale: the owner's principle — whatever keeps the parent green (CI, the merging PR, `mill-merge`'s verify) is responsible for that; a per-task re-check duplicates it and its only payoff is disabling the gate.
- Rejected: lazy baseline on first gate failure (still waives red tests); a cheaper parent-branch probe (duplicates parent's own gate).

### strict-gate-semantics

- Decision: `_run_verify_gates` runs the batch verify; any failure returns the stuck dict. If it passes and a module-wide verify is configured, it runs that; any failure returns the stuck dict with the `[module-wide verify]` reason prefix (unchanged). No other branches.
- Rationale: a gate means "this batch's verify passes". A batch whose verify covers an already-broken test halts the task, which is the intended stop condition.
- Rejected: keeping the `"pre-existing-failures"` module-wide skip as a separate opt-in — it is the same waiver at module scope.

### merge-in-recompute-removed

- Decision: delete `millpy-merge-in-subagent.py --recompute-baseline` and mill-merge-in `### 3.5. Baseline recompute` entirely.
- Rationale: its only job was refreshing the cache this task deletes. Not named in the task body's list, but the body's "remove the mechanism outright" covers it — leaving it would import a deleted module.
- Rejected: keeping a no-op step for symmetry.

### fix-finalize-forwarding-removed

- Decision: `millpy-fix.py` holistic finalize stops reading and forwarding both cached baselines; the fixer's verify replay gates strictly, same as the implementer's.
- Rationale: the forwarded values would no longer exist and the kwargs are removed from `finalize_from_output`'s gate chain.
- Rejected: none viable.

### signatures-field

- Decision: drop the `"signatures"` key from `_run_verify_gate`'s non-zero-exit stuck dict and delete `_normalize_failure_signature`. Keep `_extract_failure_signatures` (used by `_done_gate.py` and by `_run_verify_gate`'s own tail-truncation fail-line recovery).
- Rationale: the waiver was the sole consumer of both (verified by grep across `plugins/mill/scripts` and `plugins/mill/skills`). YAGNI.
- Rejected: keeping the field "for diagnostics" — nothing reads it.
- Plan must re-grep for `"signatures"` / `.get("signatures")` and `_normalize_failure_signature` before deleting, and adjust `_extract_failure_signatures`' docstring which currently describes its output as feeding baseline/finalize comparison.

### no-status-migration

- Decision: no migration of existing status.md files.
- Rationale: `_status`'s batch writer serializes only keys in its fixed `order` list, so a legacy `verify_baseline_failures` key in an in-flight task's `## Batches` block is dropped on the next batch-field write; `read_batches` uses `yaml.safe_load` and tolerates the stale key until then. Top-level `module_verify_baseline:` / `module_verify_baseline_signatures:` rows become inert text nothing reads.
- Rejected: a one-shot migration script — no reader left to protect.
- Plan must confirm `set_batch_field`/`set_batch_fields` don't re-validate keys of *existing* entries read back from disk (they validate only the key being written, per `_status.py` around lines 1180 and 1212).

### historical-docs-untouched

- Decision: rephrase only comments that describe removed code in the present tense; leave measurement reports and history-describing comments.
- Rationale: `prose`'s measurement-report exception; history comments stay true.
- Rejected: scrubbing every mention of "baseline".

## Technical context

- **Name collision hazard.** `grep baseline` hits the kept done-gate mechanism (`_done_gate.py`, `pipeline.done_gate_baseline_preflight`, mill-go-base 0.55, `test-done-gate.py`), the snapshot "baseline" in `millpy-implement.py`'s cleanliness-snapshot comments (around its lines 11, 842, 910 — unrelated, keep), and `.vscode/*.json` (slug in task names). Use the specific identifiers listed in Scope, not the bare word.
- `_run_verify_gates` lives in `plugins/mill/scripts/_implementer_common.py` (around line 1015); the waiver block is around lines 1104–1129. The `module_verify_baseline` / `batch_verify_baseline` kwargs are threaded through at least three wrapper functions (signatures around lines 1556, 1707, 1789) and five internal `_run_verify_gates` call sites (around 1892, 2074, 2175, 2284, 2393). Every docstring Args entry for them goes too.
- `millpy-implement.py` reads `module_verify_baseline` once in `main()` (around line 739) and `verify_baseline_failures` from the batch entry in the finalize branch (~813) and full branch (~1094).
- `millpy-merge-in-subagent.py`: `_run_recompute_baseline` at ~199, flag at ~333, dispatch at ~379 and ~413.
- mill-go-base's entry-gate speculative launch is the `**Speculative baseline launch.**` bullet in `### Entry-gate wait for upstream mill-plan` (~line 193); `.millhouse/baseline-preflight-log.txt` is its handshake with 0.5 and needs no cleanup code (local, gitignored).
- `CLAUDE.md`: `mill-config.yaml` hub file and the plugin template must stay in sync.
- The deploy copy under `${CLAUDE_PLUGIN_ROOT}` keeps the old behaviour for dispatched sessions until `./update-plugins.sh` runs after merge; not this task's concern beyond noting it.
- No `_codeguide/` or `CONSTRAINTS.md` in this repo.

## Constraints

- **Verify commands must avoid `main`'s nine known-red tests.** With strict gates (this task's own outcome) and `main` red, a batch verify that runs `run-all.py` or any of the nine files listed under Scope/Out will fail. Batch `verify:` commands target the specific test files each batch touches, via the `PYTHONPATH=` prefix (Python project), e.g. `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-status.py`. Plan must check the exact single-file invocation form `run-all.py` and existing plans use.
- `test-long-path.py` is one of the nine red tests; this task does not edit it (see historical-docs-untouched), so no batch verify should include it.
- Never use `sed` in any generated brief or script (CLAUDE.md).
- `print()` output ASCII-only.

## Testing

- **Deletions:** `unit_tests/test-verify-baseline.py`, `integration_tests/test-verify-baseline.py`, `integration_tests/test-baseline-waiver.py` go whole.
- **`test-implementer-common.py`:** remove waiver/pre-existing-failures cases; keep or add cases asserting strict semantics — batch failure returns the stuck dict; batch pass + module-wide failure returns the prefixed stuck dict; batch pass + no module-wide returns None; stuck dict carries no `"signatures"` key. TDD candidate: write the strict-semantics assertions first, watch the waiver-era code fail the no-`signatures` one, then strip.
- **`test-millpy-implement.py`:** remove `--stage baseline` and preflight-guard tests; add one asserting argparse rejects `--stage baseline` and that a missing `batch_name` errors for every remaining stage.
- **`test-status.py`:** remove module-baseline getter/setter/clear and signatures tests; add one asserting `set_batch_field(..., "verify_baseline_failures", ...)` raises `ValueError`, and one asserting a status.md whose `## Batches` entry carries a legacy `verify_baseline_failures` key reads fine and loses the key after an unrelated `set_batch_field` write.
- **`test-millpy-fix.py` / `test-fix-finalize.py`:** remove the union-forwarding cases (`test-fix-finalize.py` Test 7 around line 520; `test-millpy-fix.py` around 979–1045); assert `finalize_from_output` is called without `module_verify_baseline` / `batch_verify_baseline` kwargs.
- **`test-millpy-merge-in-subagent.py`:** remove the `--recompute-baseline` cases (around lines 1130–1290); add one asserting `--mode` is required and `--recompute-baseline` is rejected by argparse.
- **Final grep check** (plan's last batch or a holistic step): no remaining hit for `_verify_baseline`, `verify_baseline_failures`, `module_verify_baseline`, `baseline_verify_timeout_minutes`, `--stage baseline`, `recompute-baseline`, `baseline-preflight-log` under `plugins/` and `mill-config.yaml`, except the out-of-scope historical files listed under Scope/Out.

## Q&A log

- **Q:** `millpy-fix.py`'s holistic finalize forwards both cached baselines — remove that too, though the task body doesn't list it? **A:** [auto-pick] Remove the forwarding. **Why:** the values and kwargs cease to exist; the fixer's gate must be as strict as the implementer's.
- **Q:** `millpy-merge-in-subagent.py --recompute-baseline` and mill-merge-in §3.5 — remove the whole mode/step, or only the `--stage baseline` mentions? **A:** [auto-pick] Remove the whole mode and step. **Why:** its sole purpose is refreshing the deleted cache; it imports `_verify_baseline`.
- **Q:** Stuck dict `"signatures"` field and `_normalize_failure_signature` — remove or keep? **A:** [auto-pick] Remove both, keep `_extract_failure_signatures`. **Why:** the waiver was their only consumer; `_done_gate` still needs the extractor.
- **Q:** In-flight status.md files carrying the legacy fields — migrate? **A:** [auto-pick] No migration. **Why:** the batch writer drops unknown keys on rewrite and top-level rows become inert.
- **Q:** Stale prose mentioning the mechanism — scrub everything or only present-tense code comments? **A:** [auto-pick] Only present-tense comments in `_long_path.py`, `_worktree.py`, `test-worktree.py`; leave historical docs. **Why:** measurement reports and history comments stay true; `test-long-path.py` is red on `main` and shouldn't enter a verify.
