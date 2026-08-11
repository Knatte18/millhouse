MILL_REVIEW_BEGIN
# Review: mill-go: quality-gate coverage gaps (NIT-fix regressions, missing lint gate) — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-08-11
```

## Findings

### [NIT:consistency] Card 1 misattributes RE_SIMPLE/RE_BATCH check-order precedent
**Location:** batch 01 / card 1 **Issue:** Requirements say the classify-then-exclude algorithm "mirrors `_nit_gate._find_final_code_review`'s own check-order," but that function is scope-parameterized — it picks exactly one of `RE_SIMPLE`/`RE_BATCH` based on the `scope` argument and never tries both per file; the "checked first / excluded from second" convention actually lives in `_review_common.py`'s comment beside `RE_BATCH` (lines 103–104). **Fix:** cite `_review_common.py`'s own comment instead of (or alongside) `_find_final_code_review`; the algorithm itself is correctly specified either way.

### [NIT:consistency] Card 5 cites a testing convention that doesn't yet exist
**Location:** batch 02 / card 5 **Issue:** Requirements say to reuse "`unittest.mock.patch.object(millpy_fix._render, "render", ...)` ... patching already used by its `--nits-only` / `NITS_ONLY_CARVEOUT` tests" — but `test-millpy-fix.py` currently has no `NITS_ONLY_CARVEOUT`-testing tests at all, and its existing `_render.render` patches all use `return_value="Brief text"`, never a bare `Mock()` with `call_args` inspection. **Fix:** drop the false "already used by" premise; the concrete new-test instructions (bare `Mock`, inspect `call_args[0][1]["PRIOR_BLOCKING"]`) are self-sufficient and correct as written.

### [NIT:scope] Card 1 cites `_pygit2_util.py` outside its Context
**Location:** batch 01 / card 1 **Issue:** Requirements name `_pygit2_util.py` as a second precedent for the ASCII-fold convention, but that file isn't listed in the card's `Context:` (only `_review_common.py`, `_nit_gate.py`, `_treeguard.py` are). **Fix:** either add `_pygit2_util.py` to `Context:` or drop the citation — the inline `.encode("ascii", errors="replace").decode("ascii")` instruction is already fully specified without it.

## Verdict

APPROVE
Plan is well-grounded in source; findings are minor citation/consistency nits, no blocking issues.
MILL_REVIEW_END
