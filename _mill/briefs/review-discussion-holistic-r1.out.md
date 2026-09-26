MILL_REVIEW_BEGIN
# Review: plan validator and wiki-guard hook false positives

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: /home/knatte/Code/millhouse/wts/tooling-false-positives/_mill/discussion.md
date: 2026-09-26
```

## Findings

### [BLOCKING:design] Grep-pattern false positive (the motivating case) is not fixed
**Section:** wiki-guard-detection-algorithm, step 3; Problem #1161 **Issue:** A `grep` whose pattern is `.wiki` or `\.wiki` (no whitespace) tokenizes to a bare `.wiki` component (posix shlex strips the backslash; step 3 also splits on `\`), so it is still denied, yet the Problem section cites exactly this case as blocking the discussion phase. **Fix:** Decide whether pattern arguments of grep/rg/awk/etc. and non-path-shaped bare `.wiki` args are exempt, or explicitly scope the case out; add a test scenario either way (none exists for a quoted or unquoted `.wiki` grep pattern).

### [BLOCKING:decision] Hook command form and plugin path resolution undecided
**Section:** wiki-guard-lives-in-repo; Technical context (hook CLI env) **Issue:** The hook command must supply `PYTHONPATH` and an absolute `millpy-wiki-guard.py` path, but the discussion only says "resolved the same way that phase already resolves the venv" and that it "runs with PYTHONPATH set"; the exact command string is unstated, and if the path is a versioned cache dir, `reconcile_wiki_guard_hook` idempotence and staleness after plugin updates are unaddressed. **Fix:** State the exact hook command template, how it is kept current across plugin cache refreshes, and what the "already correct" comparison keys on.

### [NIT:decision] Script-naming/skill-generator disposition left open
**Section:** Technical context, Script-naming bullet **Issue:** "verify ... and, if that skill enumerates every millpy script, keep the CLI out of its scope or add whatever the generator requires" is an unresolved either/or. **Fix:** Pick one, or leave it to plan-time verification and say so.

### [NIT:design] Framework list has duplicates and language-blind entries
**Section:** framework-types-never-resolve **Issue:** `Object`, `Array`, `Math` appear twice, and short names (`Map`, `Set`, `Error`, `List`, `Task`, `File`, `Path`) are applied to every language, so a Go/Python plan citing a repo symbol with such a name is skipped unless a cited file type-declares it. Type-declaration forms listed omit Go `type` and other languages. **Fix:** Dedupe, and state whether the set is language-scoped by the resolving file's extension or accepted as cross-language.

### [NIT:design] Failure-mode gaps in the tokenizer
**Section:** wiki-guard-detection-algorithm **Issue:** A whitespace-free quoted argument (`--body ".wiki/x"`, `echo .wiki`) is still denied, and `$(...)` inside single quotes is recursed into although never executed; neither is called out as accepted. **Fix:** Record both as accepted conservative behaviour, or add scenarios.

## Verdict

REQUEST_CHANGES
The motivating grep false positive remains unfixed, and the hook command form is unspecified.
MILL_REVIEW_END
