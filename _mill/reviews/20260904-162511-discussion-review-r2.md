MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness check: false positives across gitignored/quoted/negated/citation/cross-reference prose

```yaml
duration_s: 250.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (per environment metadata)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] out-of-repo exemption mis-scopes wiki/-prefixed refs
**Section:** `### out-of-repo-literal-exemption` **Issue:** The resolved-location test checks only `project_root`/`git_root` via `Path.is_relative_to`. `resolve_existing_paths` routes any `wiki/`-prefixed raw token to `wiki_root` (`_review_common.py:1059-1066`), a sibling clone normally outside both roots — so a resolvable `` `wiki/Foo.md` `` Requirements: reference would be misclassified out-of-repo and wrongly exempted, silently suppressing the check for a legitimate, elsewhere-first-class dependency form (`resolve_ref_paths`'s own `wiki/` routing, #43). **Fix:** Either add `wiki_root` to the relative-root test set, or explicitly carve out `wiki/`-prefixed raw tokens from the out-of-repo test, and record the choice in the Decision block.

### [NIT:design] gitignored-exemption's source_root derivation unstated
**Section:** `### gitignored-exemption` / Technical context "Gitignore reference implementation" **Issue:** `resolve_ref_paths`'s `soft_fail_gitignored` branch pairs each candidate with its own `source_root` for the `-C` flag; `_check_context_completeness` instead resolves via `resolve_existing_paths`, which returns a flat `Path` list with no root attribution (verified `_review_common.py:1053-1082`) — the discussion never says how `source_root` is recovered for `git -C <source_root> check-ignore` in a `root`/`git_root`-fallback layout. **Fix:** State explicitly how `source_root` is derived from a resolved candidate (e.g. re-testing against `project_root`/`git_root`).

### [NIT:design] forward-creates exemption's pre-existing-file case unexamined
**Section:** `### forward-cross-card-creates-exemption` **Issue:** The decision says a token resolvable on disk that is also a later card's `Creates:` target is "still exempt," assuming the prose always refers to post-card content; nothing in the codebase stops a `Creates:` target from already existing on disk, so an earlier card genuinely reading the file's *current* content before the later card overwrites it would have the dependency silently suppressed. **Fix:** Either document this as an accepted edge case or narrow the exemption to tokens not already present in `existing_files`.

## Verdict

REQUEST_CHANGES
Fix the wiki/-prefixed out-of-repo false-negative before plan writing; the two NITs are non-blocking clarifications.
MILL_REVIEW_END
