MILL_REVIEW_BEGIN
# Review: Merge-in conflict handling: silent marker-verification gaps, mill-config.yaml chicken-and-egg crash, and undocumented dirty-worktree squash failure

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-28
```

## Findings

### [GAP] Line-229 test spec asserts an unobservable effect
**Section:** Testing (config-yaml-crash-fallback / #706)
**Issue:** `template_cfg` (augmented at `_config.py:229-230`) is never merged into the returned `cfg` -- it only feeds `warn_unknown_keys`'s baseline at line 265, a stderr-only side channel (verified by reading the full function body). "assert load_config returns template-default values for the overridden keys," reused verbatim for the line-229 case, holds trivially regardless of whether the round-3-mandated fall-through-not-break loop fix actually works, so as written it verifies nothing about that fix.
**Fix:** Specify line-229's test as (a) no raise, (b) stderr warning printed, and (c) an assertion that actually exercises fall-through -- e.g. absence of a spurious "unknown key" warning for a key introduced only by hub_root's valid candidate when worktree_root's candidate is the broken one.

### [GAP] New finalize-stage gate has no guard for a None `--files`
**Section:** Decisions/merge-in-marker-verification (#713)
**Issue:** The new `--stage finalize --mode conflicts` gate code reads `args.files` to scope `git diff --cached --check`. The only existing "`--files` required" check lives in `_run_conflicts` (`millpy-merge-in-subagent.py:337`), which the finalize early-exit branch (lines 279-316) never reaches. An omitted `--files` at finalize would raise an unguarded `TypeError`, the same crash class already caught -- and fixed via the `is_file()` guard replication -- for `--agent-output`.
**Fix:** Add an explicit `args.files`-falsy guard to the new finalize-stage gate code, alongside the already-specified `is_file()` guard replication.

## Verdict
GAPS_FOUND
Two source-grounded gaps: an unverifiable test assertion for #706's line-229 fix, and an unguarded None-`--files` crash risk in #713's new finalize gate.
MILL_REVIEW_END
