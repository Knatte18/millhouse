MILL_REVIEW_BEGIN
# Review: Fix config unknown-key warning on git namespace and commit _mill/briefs/ after dispatch — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-19
```

## Findings

### [BLOCKING] Card 2 tests fail against the minimal fixture template
**Location:** Batch 1 / Card 2
**Issue:** The new tests are modeled on `test_via_psmux_...`, which uses `_setup_plugin_template` (test-config.py L56-80) — a minimal template string with **no `git:` block**. `walk_unknown_keys` validates against that fixture, not the real template Card 1 edits, so `git` is still flagged: the positive test's `"unknown key: git" NOT in stderr` assertion fails.
**Fix:** Card 2 must instruct adding a `git:` block (with the three subkeys) to the `_setup_plugin_template` fixture string so the fixture matches the registered schema.

### [BLOCKING] Negative test asserts a subkey path that cannot be emitted
**Location:** Batch 1 / Card 2 (`test_git_unknown_subkey_still_warns`)
**Issue:** `walk_unknown_keys` (L104-109) recurses into a key only when both actual AND template have it as a dict. With no `git:` in the fixture template, a `git: {bogus-key: x}` actual yields top-level `"unknown key: git"`, never `"unknown key: git.bogus-key"`. The asserted substring will not appear even though the negative test is conceptually correct.
**Fix:** Same as above — registering `git` in the fixture template is the precondition that makes the recursive subkey warning (`git.bogus-key`) reachable; without it both new tests fail.

### [NIT] `parent-branch` is read from a different file than the warning source
**Location:** Batch 1 / Card 1
**Issue:** git-pr reads `git.parent-branch` from `.millhouse/config.yaml` (git-pr SKILL L88), not the merged `mill-config.yaml` that the unknown-key check validates; registering it is harmless self-documentation but is not strictly needed to silence #511.
**Fix:** None required — the inline comment already states the `.millhouse/config.yaml` source accurately; keep as-is or drop the net-new key if minimalism is preferred.

## Verdict

REQUEST_CHANGES
Card 2's two tests will fail unless the fixture template registers the git block.
MILL_REVIEW_END
