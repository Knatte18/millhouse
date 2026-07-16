MILL_REVIEW_BEGIN
# Review: mill-finalize/mill-merge corrupt or mishandle _mill/status.md and task_dir on stacked branches — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-16
```

## Findings

### [BLOCKING] Card 10 "prove the fix" asserts checkout exits 0 but it errors
**Location:** Batch 4 (integration-test-coverage) / Card 10, sub-step 2
**Issue:** `_setup_trio`'s hub tracks no `_mill/` on any branch and the child squash brings none, so `git -C str(hub) checkout -- "_mill"` fails with `pathspec '_mill' did not match any file(s) known to git` (exit 1) — the card's "assert both exit 0" will make the test go red before it reaches the `commit -m "Demo merge"` line, breaking the whole flat-hub scenario.
**Fix:** Either seed a committed `_mill/` on hub's `main` before this sub-step so the checkout has something to restore, or drop the checkout-exit-0 assertion and assert only that the corrected relative-form commands do NOT emit `outside repository` (the reset already proves that).

### [NIT] Card 7 read_slug cannot honor "absent slug = no-op" semantics
**Location:** Batch 3 (merge-slug-check-and-pathspec) / Card 7
**Issue:** Card 1 makes an absent `slug:` row a no-op, but Card 7's phase gate uses `_status.read_slug`, which never returns `None` — on an absent field it falls back to `status_path.parent.name` (`_mill` in real worktree layout), which never equals the task slug, so a legit slug-less status.md is treated as a mismatch and always routed to the wiki fallback. Behavior is safe (fallback direction) and the flat-hub fixture happens to coincide because its `status.md` lives in `active/<slug>/`, but it diverges from the plan's own absent-slug semantics.
**Fix:** Note in Card 7 that `read_slug`'s dir-name fallback means only a present-and-differing `slug:` yields a true mismatch and that absent-slug in worktree layout falls through to wiki — or read the raw field so absent is a genuine no-op.

## Verdict

REQUEST_CHANGES
Card 10's checkout-exit-0 assertion will fail against the no-_mill hub; fix before implementing.
MILL_REVIEW_END
