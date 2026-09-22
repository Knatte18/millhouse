MILL_REVIEW_BEGIN
# Review: compute_baseline: use the task worktree's own pre-edit state, not a parent-branch checkout

```yaml
duration_s: 200.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-22
```

## Findings

### [BLOCKING:design] pair_cache seeding cannot survive the two-half split
**Section:** Decisions — `module-wide-verdict-source` x `two-half-stage-ownership` **Issue:** `pair_cache` is an in-process dict, but in the speculative-launch path the module-wide half runs in one `--stage baseline` process (`millpy-bg --slug baseline-preflight-early`) and the per-batch half in a later §0.5 process where module-wide reports `"cached"` and does not run — so nothing seeds the cache and a batch declaring the identical command re-pays a whole module-wide suite, while Testing asserts "runs once, not twice" unconditionally. **Fix:** State whether the seeding is explicitly best-effort (single-invocation only, with the test narrowed to that path) or whether the module-wide run's signature set must be persisted in `status.md` to cross the process boundary.

### [NIT:scope] mill-merge-in SKILL.md update list omits the two new behaviours
**Demoted-from:** BLOCKING
**Section:** Scope → In (`mill-merge-in/SKILL.md`) **Issue:** The doc-update inventory names only the transient checkout, the `baseline_parent_sha` pin and the dependency-state rationale, but step 3.5's prose also asserts `--recompute-baseline` "runs the same deterministic computation `millpy-implement.py --stage baseline` uses" (`SKILL.md:113`) — false once the asymmetric rule lands — and nowhere states the new unconditional clearing of every batch's `verify_baseline_failures`, an operator-visible change that makes all remaining batch gates strict. **Fix:** Add both items to that scope bullet.

### [NIT:design] "already captured" must be key presence, not truthiness
**Section:** Technical context — "Idempotence must survive the widening" **Issue:** A green batch's baseline is `[]`, which `set_batch_field`/`_write_batches` store as a present key (`_status.py:685,694`) but which is falsy; a truthiness-based skip test would re-run every green batch's whole suite on a restarted mill-go, which is exactly the case this bullet forbids. **Fix:** Say the skip test is "key present in `read_batches` entry", not "non-empty".

### [NIT:design] merge-in recompute leaves the verdict producer unnamed
**Section:** Decisions — `merge-in-recompute` **Issue:** "exit 0 → clean; non-zero → unset" reads as a raw exit code, but reusing the simplified `compute_baseline` inserts the flakiness retry (fail-then-pass ⇒ `"clean"`), so the named unit test "exits non-zero → field left unset" is satisfied by one implementation and not the other. **Fix:** State whether the recompute calls `compute_baseline` and maps `"pre-existing-failures"` → unset, or runs the command once via `_run_verify_in`.

## Verdict

REQUEST_CHANGES
Two cross-decision gaps: pair_cache seeding across invocations, and mill-merge-in doc inventory.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 1._
MILL_REVIEW_END
