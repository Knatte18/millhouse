I have verified all key claims against the source files. The dispatch chain (resolve_scope.py lines 189-206), `_no_arg_scope` (113), `_detect_base_branch` (94), `_parent_branch.resolve`/`_read_parent_from_status`, git-commit Step 2 (line 19, no-arg Skill invocation), mill-merge-in Step 5 (line 110, literal `git diff "$CHK"..HEAD`), codeguide-update Step 2 (`resolve_scope.py $ARGUMENTS` passthrough, line 32), and the 13-scenario test file all match the discussion's descriptions. One feasibility point confirmed positively: `--parent` does reach resolve_scope.py because codeguide-update forwards `$ARGUMENTS` verbatim.

MILL_REVIEW_BEGIN
# Review: Fix codeguide-update scope resolution on stacked branches and resolve_scope.py branch-name parsing

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-09
```

## Findings

### [GAP] resolve_for_codeguide signature/path is self-contradictory
**Section:** Decisions § "New helper: _parent_branch.resolve_for_codeguide" (line 71); Scope (line 24); Technical context (81a)
**Issue:** Line 24 and line 71 declare `resolve_for_codeguide(hub_root: Path)` that internally hardcodes `hub_root / "_mill" / "status.md"`, but the same sentence says git-commit "will pass the already-resolved `status_path`", and 81a says git-commit resolves the path via "config's `status_md` path" -- three incompatible statements about the signature and who resolves status.md. Hardcoding `_mill/status.md` also conflicts with the CLAUDE.md invariant "all path resolution through `_paths.py`" and mill-merge-in's `_paths.resolve_task_path(...)` pattern.
**Fix:** Pin one contract: either the helper takes `status_path` (caller resolves via `_paths` + config `status_md`), or it takes `hub_root` and resolves the sub-path through `_paths`, not a hardcoded literal -- and make Scope/Decision/Technical-context agree.

### [NOTE] `..HEAD` stripping rule stated two conflicting ways
**Section:** Decisions § "mill-merge-in Step 5" (line 54) vs Technical context (line 77)
**Issue:** Line 54 says "strip a trailing `..HEAD` suffix"; line 77 says "if the token contains `..`, split at the last `..` and use the left side." These diverge for any `<ref>..<ref>` range (line 77 silently drops the right endpoint). Only `..HEAD` is produced by real callers, so impact is latent.
**Fix:** State that only a literal trailing `..HEAD` is stripped; any other `..`-containing token falls through unchanged.

### [NOTE] Single-token explicit-path regression not covered
**Section:** Testing (lines 94-97); Technical context (82)
**Issue:** The broadened dispatch means a single-token explicit path that also resolves as a ref (e.g. a file named `HEAD` or matching a branch/tag) now routes to head-rev instead of explicit. The regression guard only re-tests the two-token case (scenario 10); no single-token explicit-path (non-ref) assertion is named.
**Fix:** Add a single-token explicit-path scenario (a path that does not resolve as a ref) asserting `mode == "explicit"`.

## Verdict

GAPS_FOUND
Helper signature/path-resolution contract is internally contradictory and must be pinned before planning.
MILL_REVIEW_END
