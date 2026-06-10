MILL_REVIEW_BEGIN
# Review: golang-skills

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-10
```

## Findings

### [GAP] Reference file for go-comments placeholder contradicts constraint

**Section:** Constraints / Technical context
**Issue:** The Constraints section requires every SKILL.md to end with a `<!-- Project-specific ... -->` comment "same as C# and Python", yet the declared reference file `plugins/csharp/skills/csharp-comments/SKILL.md` does not contain that placeholder -- only `csharp-build` and `csharp-testing` do.
**Fix:** Either name a reference file that actually carries the placeholder (e.g. `csharp-build/SKILL.md`), or explicitly note that `go-comments` must add the placeholder despite the reference file omitting it, so the plan writer does not follow the reference literally and miss it.

### [NOTE] `cmp.Diff` import path and module dependency not stated

**Section:** Decisions -- Test library / Technical context
**Issue:** The decision mandates `cmp.Diff` from `google/go-cmp` but the discussion gives no module path (`github.com/google/go-cmp/cmp`) and does not mention whether a `go.mod` file must be present in the plugin tree or whether this is guidance-only (the plugin is a static text file, not runnable code).
**Fix:** Clarify that the skill file should quote the full import path `github.com/google/go-cmp/cmp` for copy-paste correctness, and note that the plugin files are documentation -- no `go.mod` is required.

### [NOTE] `golangci-lint` assumed installed; no fallback or discovery guidance

**Section:** Technical context -- Build tool chain
**Issue:** The build workflow prescribes `golangci-lint run` as the final step but gives no note on what to do when it is absent (it is not part of the Go standard tool chain and must be installed separately), unlike the C# build skill which includes test-discovery guidance for missing test projects.
**Fix:** Add a short note to the plan brief instructing the go-build SKILL.md to mention that `golangci-lint` must be installed separately (e.g. `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`) and what to do if it is not found.

## Verdict

GAPS_FOUND
Reference-file inconsistency on placeholder constraint must be resolved before plan writing.
MILL_REVIEW_END
