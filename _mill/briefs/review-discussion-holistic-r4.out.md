MILL_REVIEW_BEGIN
# Review: Batch verify/baseline/completeness gates produce false positives or time out

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-16
```

## Findings

### [GAP] #638 hardcodes `main` as byte-identity reference
**Section:** Decisions → batch-verify-list-validation
**Issue:** The validator drops verify files that are byte-identical to `main` (`git diff main -- <file>`), but this task's own parent is `hanf/linux-port-more` (see discussion yaml), and `compute_baseline`/the other `_check_verify_*` machinery keys off `parent_branch`, not literal `main`; comparing to `main` when parent != main can drop files that differ from the batch's real base or fail to drop genuinely-pre-existing-failing ones.
**Fix:** State whether the reference is the batch's resolved parent branch (consistent with `compute_baseline`) or deliberately literal `main`, and why.

### [GAP] #642 gate undefined for compound `//go:build` expressions
**Section:** Decisions → go-build-tag-retiering-check
**Issue:** The removed-tag direction runs `go build -tags <removed-tag>` (singular), but `//go:build` constraints are boolean expressions (`a && b`, `a || b`, GOOS terms like `linux`) that do not map to a single `-tags` value; an unspecified translation risks the gate compiling with wrong tags and producing the very false positive this task targets.
**Fix:** Specify how compound/negated/GOOS constraints are handled — e.g. gate fires only on single custom-tag constraints and degrades to no-op (logged) otherwise.

### [NOTE] #650 preflight lacks Bash-tool timeout guidance
**Section:** Decisions → done-gate-baseline-preflight
**Issue:** The new Prepare-phase inline-Python block runs a full (dotnet, per the repro) regression suite via a Bash-tool `$MILL_PYTHON -c` call; `run_preflight`'s `subprocess.run` has no timeout and the enclosing Bash-tool call inherits the default 2-min limit — the exact timeout class #639/#624 address, yet not mentioned here (the Handoff block at SKILL.md:771 also omits it).
**Fix:** Note that the new Prepare block should carry the extended Bash-tool timeout, consistent with the finalize-timeout generalization.

## Verdict

GAPS_FOUND
Two reference/coverage gaps (#638 base ref, #642 compound tags) need resolution before planning.
MILL_REVIEW_END