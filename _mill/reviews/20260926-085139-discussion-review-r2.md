MILL_REVIEW_BEGIN
# Review: plan validator and wiki-guard hook false positives

```yaml
duration_s: 23.8
verdict: APPROVE
reviewer_model: sonnet
reviewed_file: /home/knatte/Code/millhouse/wts/tooling-false-positives/_mill/discussion.md
date: 2026-09-26
```

## Findings

### [NIT:consistency] `echo $(cat .wiki/x)` contradicts echo-skip rule
**Demoted-from:** BLOCKING
**Section:** Decisions / wiki-guard-detection-algorithm step 5 vs Testing (wiki-guard True list) **Issue:** Step 5 says that when the command word is `echo` or `printf`, no argument is tested, but the Testing section requires `echo $(cat .wiki/x)` to be True, and it is unspecified whether `$(...)` recursion (step 3) runs before or despite the echo skip; the punctuation tokenizer also splits the unquoted `$(cat .wiki/x)` into separate tokens, so it is not a whitespace-containing token either. **Fix:** State that command substitution inside echo/printf arguments is recursed into (or extracted before the echo skip), while plain-text arguments stay skipped, and say how substitutions are located when the tokenizer has split `$(`...`)` into separate tokens.

### [NIT:decision] Multi-hook entries in legacy reconcile
**Section:** wiki-guard-lives-in-repo **Issue:** Reconcile removes/replaces a Bash-matcher entry by command match but does not say what happens when the matching hook shares an entry's `hooks` list with unrelated hooks. **Fix:** State that only the matching hook object is replaced and the entry is dropped only if its `hooks` list becomes empty.

## Verdict

APPROVE
The echo/printf skip rule and the required-True `echo $(cat .wiki/x)` case conflict and need one stated resolution.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
