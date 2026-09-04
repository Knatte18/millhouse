MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness check: misses bare symbol/identifier references entirely, only matches path tokens

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:consistency] Resolvability-gate walk names 2 roots, canonicalization assumes 3
**Section:** Resolvability gate / Reverse path-canonicalization for symbol matches
**Issue:** "Resolvability gate" defines the walk's roots as only `git_root/root` → `project_root/root` precedence, but `resolve_existing_paths` (`_review_common.py:1023`, verified) actually tries a third candidate — bare `git_root/raw` (no `root` joined) — whenever `git_root` is set, regardless of `root`. The later "Reverse path-canonicalization" decision explicitly references all three roots (`git_root/root`, `project_root/root`, "or `git_root`") as possible match origins for its `.relative_to()` step, but the walk that's supposed to have produced that match was never told to search under bare `git_root`.
**Fix:** Either add the bare-`git_root` fallback root to the walk's precedence list in "Resolvability gate" (fully mirroring `resolve_existing_paths`'s 3-candidate order), or strike the "or `git_root`" branch from the canonicalization decision so both sections agree on exactly which roots the walk searches.

### [BLOCKING:consistency] Technical Context overclaims reuse of creates/deletes/moves_targets for symbols
**Section:** Technical context / Resolvability gate / Membership check against the card's own refs
**Issue:** Technical Context states "the new branch consults the same plan-wide sets" for `creates_union`, `deletes_union`, `moves_sources`, `moves_targets`. Verified against the existing path branch (`_plan_validate.py:1744-1768`): the path branch's *resolvability* step (not just membership) treats `creates_union`/`deletes_union`/`moves_targets` membership as alternate proof of existence for not-yet-created files. The symbol branch's "Resolvability gate" decision defines resolvability purely as a filesystem-walk zero/one/many-file count — it never consults `creates_union`/`deletes_union`/`moves_targets`, and "Membership check" only uses `moves_sources` (for the exemption, matching the path branch's parallel usage there, not its resolvability usage). Net effect: a `Requirements:` symbol reference to a function that will be defined in a file this same plan `Creates:` (not yet on disk) can never resolve under the decided design and is silently skipped forever — an asymmetry with the path branch's behavior that Technical Context's blanket claim papers over rather than states as an accepted limitation.
**Fix:** Either state explicitly (as an accepted Scope/Decision limitation) that symbol resolution never covers not-yet-created Creates:/Moves-target files, or correct Technical Context to say only `moves_sources` is actually consulted by the new branch and remove the "consults the same plan-wide sets" phrasing.

## Verdict

REQUEST_CHANGES
Two consistency gaps between Technical Context/Decisions on which roots and which plan-wide sets the symbol branch actually uses.
MILL_REVIEW_END
