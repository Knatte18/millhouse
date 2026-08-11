MILL_REVIEW_BEGIN
# Review: mill-go2: opt-in skill scaffold cloned from mill-go (no fork yet)

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: /home/knatte/Code/millhouse/wts/mill-go2-scaffold/_mill/discussion.md
date: 2026-08-11
```

## Findings

### [BLOCKING:consistency] variant-label-in-logs miscounts and omits a family
**Section:** `### variant-label-in-logs` vs `### Technical context` / "What is parameterized in the base"
**Issue:** The Decision states VARIANT_LABEL replaces "the 20 SKILL-authored `commit -m` messages and the 7 `_notify.notify(...)` event names." Verified against `mill-go/SKILL.md` directly: `commit -m "mill-go: ` occurs 26 times (matches the Technical-context table's "26", not the Decision's "20"), and `_notify.notify("mill-go.` occurs at 8 call sites / 5 distinct names (matches the table's "8", not the Decision's "7"). The Decision also never mentions the third family the table calls out — the `[mill-go]` echo/halt prefix (10 sites, verified) — even though Technical context labels all three "literal families" that "must be parameterized" and warns "a missed site silently keeps a `mill-go:` prefix under mill-go2, defeating `variant-label-in-logs`."
**Fix:** Correct the Decision's counts to match the grep-verified Technical-context table (26 / 8-sites-5-names) and explicitly add the `[mill-go]` echo/halt-prefix family (10 sites) to the Decision's scope, not just the grep-inventory subsection.

## Verdict

REQUEST_CHANGES
The variant-label-in-logs Decision's own counts contradict, and its scope omits a family from, the discussion's verified inventory.
MILL_REVIEW_END
