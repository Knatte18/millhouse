MILL_REVIEW_BEGIN
# Review: Fix unit test suite failures, spurious review warning, and implementer verify-gate gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-16
```

## Findings

### [GAP] #488 verify_cmd source path uses unsafe dict key
**Section:** Decisions / 488-always-reverify-on-success (line 138)
**Issue:** Decision specifies `_read_batch_frontmatter(batch_file)["verify"]`, but the helper returns `{}` on missing/malformed frontmatter (verified `_plan_dag.py:262-282`), so `["verify"]` raises `KeyError` — and a valid batch with no `verify:` key also KeyErrors, defeating the intended `verify: null` -> no-op branch.
**Fix:** State `.get("verify")` so absent/malformed frontmatter yields `None` (the documented no-verify behaviour the Technical Context at line 211 already assumes).

### [GAP] #488 prepare/full-vs-finalize: which process runs the verify gate
**Section:** Decisions / 488-always-reverify-on-success
**Issue:** `_forward_output` is called from BOTH `millpy-implement.py:301` (full stage) and the `finalize` branch via `finalize_from_output` (line 192). The discussion threads `verify_cmd` into both, but does not say whether the `prepare`-stage split (where the implementer runs out-of-process and finalize happens in a separate invocation) re-runs verify in the same `cwd`/HEAD state the implementer left — verify must run against the post-implementer worktree, not a stale one.
**Fix:** State that the gate runs in the finalize/full process against `project_root` at its current HEAD (post-implementer commits), confirming the prepare path's later finalize call carries `verify_cmd`.

### [NOTE] #488 verify gate vs inferred-success that auto-commits formatter drift
**Section:** Decisions / 488-always-reverify-on-success
**Issue:** Decision says re-run verify on "all inferred-success fallback paths" (emits at `_implementer_common.py:290, 299, 310`), but line 290 fires only after an in-path formatter-drift auto-commit; ordering of verify relative to that commit is unspecified.
**Fix:** Note verify runs after any drift commit, on the final clean HEAD, so all four success emits are gated uniformly.

### [NOTE] #488 reason payload size when verify output is large
**Section:** Decisions / 488-verify-execution-mechanism
**Issue:** `reason = (stdout+stderr).strip()` from a full `run-all.py` failure can be large; emitted as a single JSON line consumed by mill-go. No truncation policy stated (merge-in precedent has the same trait but its scope differs).
**Fix:** Decide whether to cap/elide verify output in `reason` or accept full passthrough explicitly.

## Verdict

GAPS_FOUND
Two implementation-blocking ambiguities in the #488 verify gate (dict-key safety, which-process-runs-verify); #486/#487/#489/#492 are sound.
MILL_REVIEW_END
