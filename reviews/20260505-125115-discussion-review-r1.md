I have all the information needed. Writing the review now.

---

# Review: 3 (A) — codeguide improvements: sibling placement + --branch flag

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: discussion.md
date: 2026-05-05
```

## Findings

### [GAP] --branch decision tree: detection mechanism unspecified
**Section:** `## Technical context` → New step 4
**Issue:** The two branch paths (`git clone -b <branch>` vs. orphan init) require first knowing whether `<branch>` exists on the remote, but no detection command is specified — neither `git ls-remote --heads <url> <branch>` upfront nor a try-and-fallback pattern.
**Fix:** Add one line to the step-4 spec stating the detection approach: e.g. "Check via `git ls-remote --heads <url> <branch>`; if exit 0, use clone path; otherwise use orphan path."

## Verdict

GAPS_FOUND
The `--branch` decision tree is missing the detection mechanism that gates which clone path to execute.