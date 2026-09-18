MILL_REVIEW_BEGIN
# Review: _plan_validate.py _resolve_symbol_files: naive whole-file text search, no declaration-form check

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (best-effort; cannot verify precisely)
reviewed_file: _mill/discussion.md
date: 2026-09-18
```

## Findings

### [BLOCKING:consistency] Go const/var-block tracking contradicts Python's rejected mini-parser
**Section:** Decision `declaration-form-regex`, Go bullet vs. Python bullet.
**Issue:** The Go bullet requires matching "a SYMBOL-leading member line inside a grouped `const ( … )` / `var ( … )` block" — this needs tracking whether the current line falls inside an open, unclosed `const (`/`var (` group, i.e. cross-line enclosing-scope state. The Python bullet explicitly rejects an equivalent capability for the class-body-attribute case, calling it "enclosing-scope tracking — the mini-parser the `declaration-form-regex` decision already rejects," and leaves it as an accepted residual gap instead.
**Fix:** Either justify why const/var-group tracking is not "the mini-parser" the Python case forbids (e.g. bounded single-level paren-depth counter vs. general indentation/scope tracking), or apply the same residual-gap treatment to Go grouped blocks and drop that clause, so the two language bullets rest on the same rule for what counts as acceptable state-tracking.

### [NIT:consistency] Exemption line-range citation includes code outside the cited range
**Section:** Technical context, bullet 4 ("Every existing exemption ... lines 2340-2359").
**Issue:** The quoted-material (fence/blockquote) exemption is implemented at `_plan_validate.py:2323-2327` (the `line_is_quoted` check), before the cited `2340-2359` range, which actually only spans prohibition-marker through contrast-citation. The underlying claim (all five exemptions run before the branch split) is still correct — only the line span is imprecise.
**Fix:** Widen the cited range to `2317-2359` (or cite quoted-material separately) so a plan writer spot-checking the claim doesn't get a false miss.

## Verdict

REQUEST_CHANGES
One unresolved self-contradiction on what counts as disallowed "mini-parser" state-tracking.
MILL_REVIEW_END
