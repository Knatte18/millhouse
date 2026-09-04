MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness check: misses bare symbol/identifier references entirely, only matches path tokens

```yaml
duration_s: 154.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (per environment metadata)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] Reverse path-canonicalization step for symbol matches is never decided
**Section:** Resolvability gate / Membership check against the card's own refs
**Issue:** The membership check claims to reuse the path branch's comparison "exactly the way the existing path branch already does," but that branch only ever compares an *author-typed token string* against `own_refs`/`moves_sources` (`resolve_existing_paths` goes token-string -> filesystem Path purely to test existence, per `_review_common.py:1023`'s own docstring — it never converts a filesystem Path back into a token string). The symbol branch's filesystem walk runs in the opposite direction: it discovers an absolute `Path` and must convert it into whatever relative-string form (`root`-relative? `project_root`-relative? forward-slashed?) the card author actually typed under `Context:`/`Edits:` to do a literal string-membership test. No such conversion utility exists, and none is decided here. Without it, the "Clean, symbol in own Context" test case (Testing §, first bullet) cannot deterministically pass or the check risks false-positive flags on every genuinely-covered symbol.
**Fix:** Add a Decision specifying exactly how the found file's absolute Path is normalized back to the canonical token string (which root, which separator) before the `in own_refs` / basename-fallback comparison runs; note that the existing basename-fallback (lines 1765–1768) is guarded on `"/" not in token`, which a normalized file path will almost always violate, so state explicitly whether that fallback is expected to fire for symbols at all.

## Verdict

REQUEST_CHANGES
Reverse path-canonicalization for symbol-branch membership comparison is undecided and correctness-critical.
MILL_REVIEW_END
