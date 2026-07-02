I have verified the key claims. The line references, `_run_verify_gates`, the `nits_only` guard, the template sentences, the token maps, `_render` flat substitution, and the mill-go delegation are all accurate. Two findings warrant GAP severity based on source verification.

MILL_REVIEW_BEGIN
# Review: Fix agent-mode dispatch races and pipeline gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-02
```

## Findings

### [GAP] Implementer probe vs. clean-stop/finalize ordering unspecified
**Section:** Scope In (liveness probe) + Decisions §stopped/interrupted probe
**Issue:** Scope includes the implementer in the probe ("implementer, reviewer, and fixer dispatches alike"), but `mill-go/SKILL.md:129` already routes an implementer's non-error non-JSON notification (which a "stopped/interrupted" notification typically is) to `--stage finalize` / `incomplete` recovery without any probe; the discussion never says whether a *stopped* implementer notification goes to the new probe or the existing finalize-first path, and these conflict.
**Fix:** Specify the implementer decision tree explicitly — e.g., probe applies only to reviewer/fixer, while the implementer's stopped/no-JSON case continues to route through finalize/incomplete (step 6.5) unchanged — or state the ordering when both could match.

### [GAP] Baseline dependency-reuse safety premise is factually wrong
**Section:** Decisions §baseline-aware verify gate (rationale for dependency reuse)
**Issue:** The load-bearing claim "the first module-wide gate call fires before any batch has modified dependency manifests" is inaccurate: `_run_verify_gates` runs the module-wide gate inside `finalize_from_output` (per-batch), so the first invocation is at batch 1's *finalize* — after batch 1 may have changed `pyproject.toml`/`requirements`/`package.json`. Reusing the (now-mutated) task-worktree venv against the parent-tip manifests can yield a spurious non-zero exit, silently cached as `"pre-existing-failures"` and disabling #541's gate for the whole task — the exact "never silently disable" outcome the design elsewhere forbids (a clean non-zero exit is not the exception-only inconclusive fallback).
**Fix:** Either trigger baseline computation truly at task start (before batch 1's implementation) or explicitly justify superset-venv reuse and describe how a mismatch-induced spurious `"pre-existing-failures"` is prevented from disabling the gate.

### [NOTE] strip_all_in_worktree no longer reads junctions_cfg
**Section:** Decisions §baseline gate + Constraints (junction stripping)
**Issue:** `_junction.strip_all_in_worktree(worktree, junctions_cfg)` docstring states `junctions_cfg` "is retained for backward compatibility; it is no longer read" — it scans the whole tree for any junction/symlink. The instruction to "pass a junctions_cfg dict describing the `.venv`/`node_modules`/`vendor` junctions just created" is unnecessary and misleading, though the scan-and-strip outcome is safe.
**Fix:** Drop the "construct a descriptive junctions_cfg dict" guidance; note the arg is vestigial (pass `{}`) and the function auto-detects the created junctions.

### [NOTE] NITS_ONLY_CARVEOUT empty-string collapse yields dangling prose
**Section:** Decisions §fixer-brief carve-out (template mechanism)
**Issue:** The example "...no new commit was made, unless `<NITS_ONLY_CARVEOUT>`" collapses to a dangling "unless ." when the token is empty (nits_only false), producing malformed brief prose.
**Fix:** Have the token carry the entire trailing clause including leading conjunction and terminal punctuation, so the false case leaves a clean, complete sentence.

## Verdict

GAPS_FOUND
Two unresolved gaps: implementer probe ordering and an incorrect baseline dependency-reuse timing premise.
MILL_REVIEW_END