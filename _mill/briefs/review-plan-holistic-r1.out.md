MILL_REVIEW_BEGIN
# Review: _plan_validate.py _resolve_symbol_files: naive whole-file text search, no declaration-form check — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-09-18
```

## Findings

### [NIT:consistency] Card 2's "one call site" framing conflates two separate code regions
**Location:** batch `resolve-symbol-engine`, card 2. **Issue:** Requirements text calls `search_key = _symbol_candidate_shape(token)` / `if search_key is None: continue` "the `is_path_shaped` branch's `else:` arm" and says the `search_cache` lookup / `_resolve_symbol_files` call / `len(matches) != 1` guard / `matches[0].relative_to(...)` live "in that arm" too — but in `_plan_validate.py`, the shape-gate call is at lines ~2335-2338 (inside `if not is_path_shaped:`, before the four shared exemption checks), while the cache/resolve/guard code is a separate `else:` block ~130 lines later (lines ~2468-2481), with the path-branch's own `if is_path_shaped:` arm in between. **Fix:** Describe these as two distinct edit sites (the early shape-gate call, and the later resolution `else:` arm) rather than one contiguous "arm" — the individually-quoted current-code snippets already anchor each edit unambiguously, so this is a description-accuracy nit, not a location an implementer could actually get wrong.

## Verdict

APPROVE
Decisions faithfully implemented, cards complete, DAG/sequencing correct; one minor source-description inaccuracy noted, no functional risk.
MILL_REVIEW_END
