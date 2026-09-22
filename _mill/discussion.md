# Discussion: compute_baseline: use the task worktree's own pre-edit state, not a parent-branch checkout

```yaml
task: 'compute_baseline: use the task worktree''s own pre-edit state, not a parent-branch checkout'
slug: baseline-uses-worktree-not-checkout
status: discussing
parent: main
```

## Problem

`plugins/mill/scripts/_verify_baseline.py` answers one question for the verify gate: "does this verify command already fail, independent of anything this task did?"
It answers it by materializing a throwaway git worktree under `.scratch/verify-baseline-<hash>/` at the parent branch's current tip, junctioning the task worktree's gitignored dependency dirs into it, and running the verify command there.

The task worktree at its branch point already *is* the pre-implementation tree.
`mill-start` and `mill-plan` write only under `_mill/`, so at the moment `millpy-implement.py --stage baseline` runs — before batch 1's implementer is ever dispatched — the worktree's source content is exactly the merge-base content.
The checkout re-derives, at real cost, a state that is already on disk.

Four consequences follow from that one wrong premise (GitHub issue [#1130](https://github.com/Knatte18/millhouse/issues/1130)):

- `_checkout_parent_branch` resolves the parent's *current tip* via `git rev-parse <parent>`, not `git merge-base HEAD <parent>`. A sibling task merging into the shared parent mid-run makes that drift part of this task's "baseline".
- The fresh checkout pays a full cold build on any compiled-language project. The dependency-dir junction list (`.venv`, `venv`, `node_modules`, `vendor`) only reuses *installed packages*, which helps interpreted ecosystems and does nothing for build output.
- The cost repeats per mill-go invocation whenever a baseline is not already cached.
- A whole support surface exists only to prop the checkout up: `millpy-cleanup.py`'s `.scratch/verify-baseline-*` orphan reaping, the `-c core.longpaths=true` scoping in `_checkout_parent_branch`, the 12-hex-char path-budget shortening, and the `pipeline.baseline_prepare_cmd` config key (a build-once warmup that exists solely because the checkout starts cold).

**Why now:** #1130 filed the analysis; the task is claimed and the worktree spawned.

## Scope

**In:**

- `plugins/mill/scripts/_verify_baseline.py` — remove the checkout entirely. `compute_baseline` and `compute_batch_baselines` run against the task worktree. Delete `_checkout_parent_branch`, `_link_dependency_dirs`, `_DEPENDENCY_DIR_CANDIDATES`, and `compute_batch_baseline_on_demand`.
- `plugins/mill/scripts/millpy-implement.py` — `--stage baseline` becomes an eager, in-worktree capture of the module-wide command *and* every distinct batch `verify:` command. Remove `_pin_baseline_parent_sha`.
- `plugins/mill/scripts/_implementer_common.py` — remove the on-demand compute prelude in `_run_verify_gates` and delete `_corroborate_batch_failure` plus its call site.
- `plugins/mill/scripts/_status.py` — delete `get_baseline_parent_sha` / `set_baseline_parent_sha`.
- `plugins/mill/scripts/millpy-merge-in-subagent.py` — `--recompute-baseline` runs the module-wide command in the post-merge task worktree with an asymmetric verdict rule (see Decision `merge-in-recompute`).
- `plugins/mill/scripts/millpy-cleanup.py` — delete `_scan_orphan_baseline_dirs`, `_apply_orphan_baseline_dir`, the `orphan_baseline_dirs` plan field, and its apply loop.
- `mill-config.yaml` (hub) and `plugins/mill/templates/mill-config.yaml` — delete `pipeline.baseline_prepare_cmd`. Keep `pipeline.baseline_verify_timeout_minutes`.
- `plugins/mill/skills/mill-go-base/SKILL.md` and `plugins/mill/skills/mill-merge-in/SKILL.md` — update the prose that describes the transient checkout, the `baseline_parent_sha` pin, and the dependency-state-matches-parent-tip rationale.
- Tests: `plugins/mill/unit_tests/test-verify-baseline.py`, `test-implementer-common.py`, `test-millpy-implement.py`, `test-millpy-merge-in-subagent.py`, `test-status.py`, `test-cleanup.py`, and `plugins/mill/integration_tests/test-verify-baseline.py`, `test-baseline-waiver.py`.

**Out:**

- The **semantics** of the verify gate itself — `"clean"` / `"pre-existing-failures"`, the subset-diff waiver in `_run_verify_gates`, `_normalize_failure_signature`, and `_extract_failure_signatures` are unchanged. Only *how the baseline is obtained* changes.
- `pipeline.done_gate_baseline_preflight` and the done-gate pre-flight in `mill-go-base/SKILL.md` §0.55 — a different mechanism that shares the word "baseline". Untouched.
- `_worktree.remove_safe`, `_junction.*`, `millpy-bg.py` — still used elsewhere; only *this* module's calls into them go away.
- The speculative early-launch mechanism (`.millhouse/baseline-preflight-log.txt`) in `mill-go-base/SKILL.md` — its trigger, guard, and consumption logic stay as they are; only the prose describing what the launched job does needs touching.
- Migration of in-flight `status.md` files carrying a `baseline_parent_sha:` row — the key is simply left unread (see Decision `delete-outright`).

## Decisions

### capture-site

- **Decision:** Keep the capture at `millpy-implement.py --stage baseline`, mill-go's existing first action (and its speculative early launch during the mill-plan entry-gate wait). Do not move it to `mill-spawn`.
- **Rationale:** At `--stage baseline` time the worktree is pre-edit (only `_mill/` has been written) *and* dependencies are installed and the tree is warm — which is the entire point of capturing in-worktree. At spawn time neither holds: no plan exists yet, so the verify commands are unknown, and nothing has been installed or built. The stage is already idempotent, already cached in `status.md`, and already wired into both the normal and speculative launch paths; reusing it means zero new skill surface.
- **Rejected:** mill-spawn (no plan → no verify commands → cannot capture anything meaningful); a new standalone `--stage` (duplicates the existing one's guards and caching for nothing).

### remove-all-three-checkouts

- **Decision:** All three checkout consumers go, not just the module-wide one: `compute_baseline` (module-wide, eager pre-flight), `compute_batch_baseline_on_demand` (per-batch, lazy), and `_corroborate_batch_failure` (per-batch control check at `start_sha`).
- **Rationale:** Leaving any one behind keeps `_checkout_parent_branch`, the dependency junctioning, `core.longpaths`, the `.scratch/verify-baseline-*` orphan surface, and `millpy-cleanup.py`'s reaper alive — i.e. the whole support surface the issue names, for a fraction of the benefit. The three consumers also motivate each other: the lazy path exists because the checkout was expensive, and the corroboration path exists because the lazy path's baseline is often absent.
- **Rejected:** Converting only the module-wide path (issue's own analysis says the checkout removal *is* the fix; a partial conversion leaves every listed symptom in place).

### eager-not-lazy

- **Decision:** `--stage baseline` eagerly captures every distinct `(command, cwd)` pair: the overview's module-wide `verify:` plus every batch `verify:` from `_plan_dag.iter_batch_verifies(plan_dir, hub_root, git_root)`. Results land in the existing `status.md` fields — `module_verify_baseline:` (scalar) and each batch's `verify_baseline_failures:` (signature list). Delete the lazy on-demand path (#1102) that the eagerness replaces.
- **Rationale:** Laziness (#1102) was introduced to avoid paying N cold checkouts before batch 1. Remove the checkout and that pressure is gone: an in-worktree capture runs against an already-built, already-installed tree, so the marginal cost is one test-suite run per distinct pair. In exchange the baseline is always present when a gate fails, which is what made the corroboration fallback necessary. Dedup on `(command, cwd)` — not on batch name — so a plan whose last batch verifies the union of earlier batches' commands pays once; `compute_batch_baselines`'s existing `pair_cache` already implements exactly this.
- **Rejected:** Keeping the lazy path (needs a pre-edit tree at an arbitrary later moment, which is precisely what the task worktree no longer is once batch 1 has committed — it would force the checkout back).

### merge-in-recompute

- **Decision:** `millpy-merge-in-subagent.py --recompute-baseline` clears `module_verify_baseline`, then runs the module-wide command in the post-merge task worktree with an **asymmetric** verdict rule: exit 0 → cache `"clean"`; non-zero → leave the field unset (strict gating), matching this module's existing "computation failed → gate strictly" fail-safe.
- **Rationale:** This is the one call site where the task worktree genuinely cannot answer the checkout's question: after a merge-in, the tree is *parent content merged with this task's changes*, so a failure cannot be attributed to either side. But the asymmetry is sound in one direction — if the merged tree passes, then nothing is red and `"clean"` is correct by construction. A failure degrades to strict gating, which is the safe direction (a false `"clean"` costs one over-strict gate later; a false `"pre-existing-failures"` disables the regression gate entirely). The only thing lost versus today is auto-waiving a genuinely red *new* parent, which now surfaces to the operator as a module-wide gate failure instead — visible rather than silent.
- **Rejected:** Keeping a checkout for this one site (post-merge-in the parent is an ancestor of HEAD, so the tip-vs-merge-base bug does not apply there and the checkout would be *correct* — but retaining it keeps the entire support surface alive for one fail-safe-able call site); dropping the recompute entirely and always gating strictly after a merge-in (loses the free, correct `"clean"` case).

### delete-corroboration

- **Decision:** Delete `_corroborate_batch_failure` and its call site in `_run_verify_gates`, along with the expanded-signature persistence and the `mill-go: persist corroborated verify baseline for <batch>` commit it drives.
- **Rationale:** With `eager-not-lazy` in place, every batch has a real pre-edit baseline from before batch 1, so genuinely pre-existing failures are already waived by the subset-diff check. What corroboration additionally waived was a failure introduced by an *earlier batch of this same task* — which is this task's own regression and should block, not be waived. Removing it makes the gate stricter in exactly the case where strictness is correct.
- **Rejected:** Replacing it with a rolling per-batch capture (record each batch's post-verify signatures as the next batch's reference) — buys back the same wrong waiver, and adds per-batch state writes for it.

### delete-outright

- **Decision:** No compatibility window. Delete `millpy-cleanup.py`'s `.scratch/verify-baseline-*` reaping (`_scan_orphan_baseline_dirs`, `_apply_orphan_baseline_dir`, the `orphan_baseline_dirs` plan field and apply loop) and the `core.longpaths` / path-budget handling together with the checkout, in one change. Likewise, do not migrate existing `status.md` files carrying a `baseline_parent_sha:` row — the key is left in place and simply never read again.
- **Rationale:** `.scratch/` is gitignored scratch; any orphan directories left on an operator's disk from the old code are removable by hand (`rm -rf .scratch/verify-baseline-*`, plus `git worktree prune` for any stale registry entry), and no *new* orphans can be produced once the checkout is gone. Keeping a reaper for code that no longer runs is dead weight. A stale `baseline_parent_sha:` row is an inert extra YAML key — `_status`'s readers are field-specific, so an unread key costs nothing.
- **Rejected:** Keeping the reaper for one release (permanent dead code guarding a one-line manual cleanup); writing a migration that strips `baseline_parent_sha:` (mutates in-flight task status files for zero behavioural gain).

### algorithm-simplification

- **Decision:** The module-wide algorithm becomes: run once in the task worktree → exit 0 → `"clean"`; non-zero → re-run once (flakiness guard) → exit 0 → `"clean"`; second non-zero → `"pre-existing-failures"`. Delete the third "control check" run and its `path/environment-induced` stderr warning. `compute_batch_baselines`'s union-of-two-runs shape is unchanged, including its skip-run-2-when-run-1-is-green optimization.
- **Rationale:** The third run existed to distinguish "the transient checkout's environment is broken" from "the parent branch is genuinely red" by re-running in `project_root`. With the first two runs now *already* in `project_root`, run 3 is the same command in the same directory — it can corroborate nothing. The flakiness-guard retry survives because flakiness is orthogonal to where the command runs.
- **Rejected:** Keeping run 3 as a third flakiness sample (two consecutive failures is already the established threshold in `compute_batch_baselines`; a third run triples the cost of the red case for no new information).

### preflight-dirt-warning

- **Decision:** `--stage baseline` takes a `git status --porcelain` snapshot before its first verify run and again after its last, and prints an ASCII-only stderr warning naming any path that is newly dirty. It never blocks, never reverts, and never fails the stage. Paths under `_mill/` are excluded from the comparison.
- **Rationale:** The pre-flight's verify runs now mutate the real task worktree rather than a throwaway checkout. Verify commands are expected to be non-mutating — they already run in-worktree at every batch gate — but a command that writes a tracked file would now do so *before* batch 1's `start_sha` is taken, silently attributing the dirt to batch 1's implementer and potentially tripping the in-scope dirty-tree gate in finalize. A porcelain diff plus a warning is a few lines and turns an opaque downstream failure into a named cause. `_mill/` is excluded because a concurrently-running mill-plan session writes there during the speculative early launch (see `mill-go-base/SKILL.md`'s entry-gate wait), which is legitimate and unrelated.
- **Rejected:** No guard at all (a real new failure mode, cheap to make debuggable); blocking or auto-reverting on detected dirt (the pre-flight's standing contract is that it never blocks the task, and reverting could destroy a legitimate concurrent write).

## Technical context

**The three checkout consumers, and what replaces each:**

| Call site | Today | After |
|---|---|---|
| `millpy-implement.py:_run_module_wide_standalone` → `_verify_baseline.compute_baseline` | checkout at parent tip, 3-run algorithm | in-worktree, 2-run algorithm |
| `_implementer_common._run_verify_gates` on-demand prelude → `compute_batch_baseline_on_demand` | lazy checkout at pinned `baseline_parent_sha` | deleted; eager capture at `--stage baseline` |
| `_implementer_common._corroborate_batch_failure` → `_verify_baseline._checkout_parent_branch(project_root, git_root, start_sha)` | checkout at batch's `start_sha` | deleted |
| `millpy-merge-in-subagent._run_recompute_baseline` → `compute_baseline` | checkout at parent tip | in-worktree, pass ⇒ `"clean"` / fail ⇒ unset |

**Key files and line anchors (as of `29a69040`):**

- `plugins/mill/scripts/_verify_baseline.py` — the whole module. `_checkout_parent_branch` (~line 90), `_link_dependency_dirs`, `compute_baseline`, `_run_module_wide_verify_algorithm`, `_run_verify_in`, `compute_batch_baselines`, `compute_batch_baseline_on_demand`, `_signatures_for_pair`. After the change, `_run_verify_in`, `_signatures_for_pair`, `compute_batch_baselines`, and a simplified `compute_baseline` survive; the module docstring's entire "transient worktree" framing must be rewritten, not patched.
- `plugins/mill/scripts/millpy-implement.py` — `_module_wide_skip_or_cached_payload` (~line 95), `_run_module_wide_standalone` (~line 126), `_pin_baseline_parent_sha` (~line 176, delete), `_run_baseline_stage` (~line 220). `_run_baseline_stage` currently `del`s its `plan_base` and `baseline_prepare_cmd` parameters as unused; `plan_base` becomes *used* again (it feeds `iter_batch_verifies`) and `baseline_prepare_cmd` is removed from the signature and both call sites (~line 477).
- `plugins/mill/scripts/_implementer_common.py` — `_corroborate_batch_failure` (~line 965, delete), `_run_verify_gates`'s on-demand prelude (~lines 1166–1225, delete), the corroboration branch and expanded-signature persistence (~lines 1240–1285, delete). The subset-diff waiver itself (~lines 1227–1240) stays. `_run_verify_gates`'s `start_sha` parameter may become unused at this call site — check its other readers before removing it from the signature.
- `plugins/mill/scripts/_status.py` — `get_baseline_parent_sha` (~line 432) / `set_baseline_parent_sha` (~line 458) and their two docstring mentions in the module's Public API block (~lines 38–39). `get/set/clear_module_verify_baseline` and the `verify_baseline_failures` batch field (~lines 602, 678) all stay.
- `plugins/mill/scripts/millpy-cleanup.py` — `_scan_orphan_baseline_dirs` (~line 121), `_apply_orphan_baseline_dir` (~line 503), the `orphan_baseline_dirs` field on the plan dataclass, its population in `build_plan`, and the apply loop (~line 801).
- `plugins/mill/scripts/millpy-fix.py` (~lines 423–495) — reads `module_verify_baseline` and `verify_baseline_failures` from `status.md` and forwards them. Pure consumer of the cached fields; no change needed, but verify it still type-checks after the `_run_verify_gates` signature edit.

**Helpers to reuse, not reinvent:**

- `_plan_dag.iter_batch_verifies(plan_dir, hub_root, git_root, status_path=...)` returns exactly the `(name, command, cwd)` triples `compute_batch_baselines` already accepts. It also drops batches whose `verify:` is null and batches whose verify target a strictly-later batch deletes — both correct for a baseline capture. Pass `status_path=None` at pre-flight: its approval filter is for merge-in replay, and at pre-flight no batch is approved yet.
- `_plan_dag.parse_verify_field(frontmatter, hub_root, git_root)` resolves the plain-string vs `{cwd, command}` mapping forms. `--stage baseline` already calls it for the module-wide command.
- `compute_batch_baselines`'s `pair_cache` parameter already implements cross-call `(command, cwd)` dedup. With a single eager call there is one list and one cache, so the module-wide command and any batch command that matches it string-for-string in the same cwd collapse to one run — feed the module-wide command into the same pair list rather than running it separately.
- `_status.set_batch_field(status_path, batch_name, "verify_baseline_failures", signatures)` is the existing writer; the field is already in `_status`'s known-batch-field list.
- `_subprocess_util.run` / `_subprocess_util.git_commit` for the porcelain snapshot and any status commit.

**Gotchas found during exploration:**

- **`cwd_override` coordinate spaces.** `compute_baseline`'s `cwd_override_relative` is a *hub-relative fragment* (re-anchored inside the temp checkout), while `compute_batch_baselines`'s `cwd_override` is an *already-resolved absolute path*. With the checkout gone there is no re-anchoring to do: both become "the absolute cwd to run in", and `millpy-implement.py`'s `_relative_cwd_fragment` helper exists only to produce the fragment form. Collapse to the absolute form; do not preserve the fragment parameter for symmetry.
- **`--stage baseline` needs the plan, and may run before it exists.** The speculative early launch fires during the mill-plan entry-gate wait and is skipped when the overview isn't present/approved. The non-speculative launch at §0.5 runs after the plan exists. Since the module-wide command *already* comes from `00-overview.md`, adding batch enumeration introduces no new dependency — but `iter_batch_verifies` must degrade to `[]` (not raise) if batch files are missing, matching the stage's standing "never raises, prints a JSON line" contract.
- **The stage's JSON output shape is consumed by SKILL.md prose.** `mill-go-base/SKILL.md` §0.5 parses `{"stage": "baseline", "substage": "module_wide", "result": ..., "value": ...}` and explicitly says the speculative launch's *single module-wide result IS the complete baseline computation*. Adding per-batch output means either a second `"substage": "per_batch"` JSON line (and a SKILL.md update telling the orchestrator to expect it) or folding batch counts into the existing line. Prefer a second line plus the SKILL.md edit — both §0.5's speculative branch and its main flow already extract with `grep '^{' <log-path>`, which tolerates multiple JSON lines, but both then describe parsing *the one* JSON line. Update both to select by the `substage` key rather than positionally.
- **Idempotence must survive the widening.** The stage no-ops when `module_verify_baseline` is already cached. With batch captures added, "already cached" is per-pair: skip any batch whose `verify_baseline_failures` is already set, and skip the module-wide run when its scalar is set. A resumed mill-go must not re-run a whole test suite it already captured.
- **`git_root` vs `project_root`.** The old code ran the verify in the checkout (mirroring `git_root`) and the control run in `project_root` (the task worktree / hub root). In-worktree, the correct cwd is whatever `parse_verify_field` resolved — `project_root` for `cwd: hub`, `git_root` for `cwd: git_root`, `project_root` by default. Nested-hub layouts are the case this distinction exists for; don't flatten it.
- **CLAUDE.md verify-command shape.** This is a Python project, so every plan batch's `verify:` must start with a literal empty `PYTHONPATH=` prefix (`_plan_validate.py`'s `verify-not-isolated` check).
- **No `sed`.** Use `Edit`/`Read`/`Write` or `awk`/`grep`/`cat` for all edits, including in any dispatched implementer's prompt.

## Testing

**`plugins/mill/unit_tests/test-verify-baseline.py`** — the heaviest rewrite. Today it fakes `git worktree add`/`rev-parse` and asserts checkout/teardown behaviour; all of that goes.

- TDD candidate: the simplified module-wide algorithm. Table-drive the run sequence — `(0)` → `"clean"` after one run; `(1, 0)` → `"clean"` after two; `(1, 1)` → `"pre-existing-failures"` after exactly two. Assert the *run count*, since deleting run 3 is a behavioural change a count assertion pins and an outcome assertion does not.
- Assert `compute_baseline` runs in the cwd it was handed and performs no git operation of any kind — a "no subprocess call whose argv[0] is `git`" assertion is the regression guard that keeps the checkout from creeping back.
- `compute_batch_baselines`'s existing `(command, cwd)` dedup, `pair_cache` sharing, skip-run-2-when-green, independent-list-per-name, and union-order-preservation tests carry over unchanged — they never depended on the checkout.
- `subprocess.TimeoutExpired` still propagates from both entry points.

**`plugins/mill/unit_tests/test-millpy-implement.py`**

- TDD candidate: eager capture. Given a fake plan with three batches where two share a `(command, cwd)` pair and one matches the module-wide command, assert each distinct pair runs exactly once and every batch name gets its own `verify_baseline_failures` entry.
- Idempotence: a second `--stage baseline` invocation with everything already cached runs zero verify commands.
- Partial idempotence: module-wide cached but batch B uncaptured → only B's command runs.
- Missing/unparseable plan → stage prints a JSON line and returns 0, runs nothing, raises nothing.
- `preflight-dirt-warning`: a verify command that touches a tracked file produces the stderr warning naming that path and still returns 0; one that touches only `_mill/` produces no warning.
- Assert `baseline_parent_sha` is never written.

**`plugins/mill/unit_tests/test-implementer-common.py`**

- Scenarios that previously exercised the on-demand prelude and corroboration must now assert the *absence* of that behaviour: a batch gate failure with no cached baseline gates strictly and performs no checkout.
- The subset-diff waiver's own tests (waive on subset, block on non-subset, never waive an empty replay set) stay and are the guard that this change didn't touch gate semantics.

**`plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`**

- TDD candidate: the asymmetric verdict. Post-merge verify exits 0 → `module_verify_baseline` set to `"clean"`; exits non-zero → field left unset (and explicitly *not* `"pre-existing-failures"`). The clear-first behaviour survives in both branches, so a stale pre-merge `"pre-existing-failures"` is never carried forward.
- Exit code stays 0 on every path; the JSON line still reports the outcome.

**`plugins/mill/unit_tests/test-status.py`** — delete the `baseline_parent_sha` accessor tests; leave the `module_verify_baseline` and `verify_baseline_failures` tests untouched.

**`plugins/mill/unit_tests/test-cleanup.py`** — delete the orphan-baseline-dir scan/apply tests. Assert the cleanup plan no longer carries the field, so a stray `.scratch/verify-baseline-*` directory is now simply ignored rather than reaped.

**`plugins/mill/integration_tests/`** — `test-verify-baseline.py` and `test-baseline-waiver.py` both drive real git. Rework them against a real task worktree with a real dirty/clean verify command and no second checkout; the waiver test's end-to-end assertion (a pre-existing failure is waived, a newly-introduced one blocks) is the highest-value surviving coverage and should be preserved in shape even though its setup changes completely.

**Full-suite gate:** `plugins/mill/unit_tests/run-all.py` must pass. Ad-hoc lint via `uvx ruff check .`.

## Q&A log

- **Q:** Where should the in-worktree pre-edit capture run — mill-go's `--stage baseline` (current position) or mill-spawn? **A:** [auto-pick] mill-go `--stage baseline`. **Why:** At spawn there is no plan, so no verify commands are known, and nothing is installed or built; at `--stage baseline` the tree is both pre-edit and warm, and the stage is already idempotent and wired into the speculative launch path.
- **Q:** Convert all three checkout consumers (module-wide, per-batch on-demand, `start_sha` corroboration), or only the module-wide one? **A:** [auto-pick] All three. **Why:** Leaving any one behind retains `_checkout_parent_branch`, the dependency junctioning, `core.longpaths`, and the cleanup reaper — the whole surface the issue names — for a fraction of the benefit.
- **Q:** After removing the on-demand path, capture per-batch baselines eagerly at pre-flight or keep them lazy? **A:** [auto-pick] Eagerly, deduped on `(command, cwd)`. **Why:** Laziness existed to avoid N cold checkouts; against an already-built worktree the marginal cost is one suite run per distinct pair, and an always-present baseline is what removes the need for the corroboration fallback.
- **Q:** What happens to `--recompute-baseline` after a merge-in, where the worktree is no longer pre-edit? **A:** [auto-pick] Run in-worktree with an asymmetric rule — pass ⇒ `"clean"`, fail ⇒ leave unset (gate strictly). **Why:** A passing merged tree proves nothing is red, so `"clean"` is correct by construction; a failure cannot be attributed to parent vs. task, and degrading to strict gating is the safe direction and matches the module's existing fail-safe.
- **Q:** Delete `_corroborate_batch_failure` or replace it with a rolling per-batch capture? **A:** [auto-pick] Delete it. **Why:** With an eager pre-edit baseline, genuinely pre-existing failures are already waived by the subset-diff check; what corroboration additionally waived was a regression introduced by an earlier batch of this same task, which should block.
- **Q:** Do `millpy-cleanup.py`'s `.scratch/verify-baseline-*` reaping, the `core.longpaths` handling, and existing `baseline_parent_sha:` status rows need a compatibility window? **A:** [auto-pick] No — delete outright, no migration. **Why:** `.scratch/` is gitignored and no new orphans can be produced once the checkout is gone; leftovers are a one-line manual `rm -rf`, and an unread YAML key is inert.
- **Q:** Keep the module-wide algorithm's third "control check" run? **A:** [auto-pick] Delete it; keep the single flakiness-guard retry. **Why:** Run 3 existed to compare the checkout's environment against the task worktree's; with runs 1 and 2 already in the task worktree it is the same command in the same directory and can corroborate nothing.
- **Q:** Does the pre-flight need a guard now that its verify runs mutate the real worktree? **A:** [auto-pick] A `git status --porcelain` before/after diff that warns on stderr, excluding `_mill/`; never blocks, never reverts. **Why:** Dirt created before batch 1's `start_sha` would be silently attributed to batch 1's implementer and could trip finalize's in-scope dirty-tree gate; a warning turns an opaque downstream failure into a named cause without violating the pre-flight's never-block contract.
- **Q:** Remove `pipeline.baseline_prepare_cmd` from the hub config and the template? **A:** [auto-pick] Yes; keep `baseline_verify_timeout_minutes`. **Why:** The prepare command exists solely to warm a cold transient checkout's build, which no longer happens; the timeout still guards against a hung test runner blocking the pre-flight.
