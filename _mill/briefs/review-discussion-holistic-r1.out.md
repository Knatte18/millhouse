MILL_REVIEW_BEGIN
# Review: millpy-implement/fix.py: stuck-type false positives and session-hygiene gaps

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (exact point-version unconfirmed)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] 956 reuse-gate mishandles retry-after-self-resolve
**Section:** Decision `956-fresh-session-after-self-resolve` **Issue:** The gate checks only whether the timeline's most-recent entry is a self-resolve marker. Verified: the fresh-mint branch (`millpy-implement.py:812-870`) never calls `_status.append_phase`, so once self-resolve fires, the marker stays the "most recent" entry through any *subsequent* transient-dispatch-failure re-fire of that same fresh session — every later `--stage prepare` call will keep re-detecting the stale marker and re-mint a new `session_id`/`start_sha` again, reintroducing the #625/#635/#643 churn the decision's own Rejected bullet says must not return. **Fix:** disambiguate "self-resolve just happened, not yet re-fired" from "already fresh-minted once since the self-resolve" — e.g. have the fresh-mint branch also append a phase entry, or otherwise bound the check to entries strictly newer than the current `implementer_session`'s mint event.

### [BLOCKING:design] 954 commit-after-write needs git identity not available in `_implementer_common.py`
**Section:** Decision `954-commit-baseline-write-before-dirty-check` **Issue:** The idiom cited (`millpy-implement.py:857`) calls `_subprocess_util.git_commit(project_root, msg, name=git_name, email=git_email)`, and `git_commit`'s `name`/`email` kwargs are mandatory (`_subprocess_util.py:219-225`, no defaults). Verified: `_implementer_common.py` has zero references to `git_name`/`git_email` anywhere in the file — `_run_verify_gates`/`finalize_from_output` have no such parameters, and both callers (`millpy-implement.py:565-577`, `millpy-fix.py:302-309`) resolve identity locally but never thread it into `finalize_from_output`. **Fix:** name this as new plumbing (add `git_name`/`git_email` params to `_run_verify_gates`/`finalize_from_output` and both call sites) rather than a drop-in reuse of the cited idiom.

### [BLOCKING:scope] 916 forwards `module_verify_baseline` without its required `module_wide_verify_cmd`
**Section:** Scope "In:" bullet / Decision `916-forward-verify-baselines-both-scopes` **Issue:** `_run_verify_gates` skips the module-wide gate entirely whenever `module_wide_verify_cmd is None` (`_implementer_common.py:1194-1196`), before `module_verify_baseline` is ever consulted. Verified: `millpy-fix.py` has no existing derivation of `module_wide_verify_cmd`/`module_wide_cwd_override` anywhere in the file (unlike `millpy-implement.py:662`, which parses `00-overview.md`'s frontmatter for it) — the finalize call at 445-457 passes neither today. Forwarding `module_verify_baseline` alone, as the discussion currently scopes it, is inert. **Fix:** add `module_wide_verify_cmd`/`module_wide_cwd_override` derivation (mirroring `millpy-implement.py:662`) to the in-scope work list, or explicitly state module-wide gating stays disabled for fixer finalizes.

## Verdict

REQUEST_CHANGES
Three BLOCKING gaps: 956's marker check misses compound retry, 954's commit needs unavailable git identity, 916 forwards a dead parameter.
MILL_REVIEW_END
