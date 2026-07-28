MILL_REVIEW_BEGIN
# Review: Merge-in conflict handling: silent marker-verification gaps, mill-config.yaml chicken-and-egg crash, and undocumented dirty-worktree squash failure

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-28
```

## Findings

### [GAP] Line-229 fall-through test assertion still unfalsifiable
**Section:** Testing / `_config.load_config` (line-229 cache-lag case)
**Issue:** Verified against `_config.py`: `template_cfg` (what the augmentation loop builds) is never merged into the returned `cfg`, and `warn_unknown_keys(check_cfg, template_cfg, ...)` only walks keys present in `check_cfg` — so a key introduced solely by `hub_root`'s source-tree candidate never reaches `check_cfg` regardless of whether the loop falls through. Assertion (c) ("no spurious unknown-key warning") passes trivially whether or not the round-3 fall-through fix actually works — the same "verifies nothing" flaw round-4 already flagged for this test's original spec, now reintroduced in its replacement.
**Fix:** Fixture must also set that same new key via a source that actually feeds `cfg` (e.g. repo-layer `mill-config.yaml`), exactly as the existing `test_worktree_template_augments_template_cfg` (test-config.py:749, which sets `pipeline.max_cards_per_batch` in both the source-tree template AND the repo-layer config) already does — without that second write, assertion (c) can't distinguish fixed from broken.

### [GAP] Marker gate scoped to `--cached` may miss a never-staged file
**Section:** Decisions / merge-in-marker-verification (#713)
**Issue:** `git diff --cached --check` inspects only staged (index) content. A sub-agent that edits a conflicted file but never runs `git add`/`git rm` on it leaves that path in an unmerged index state with no normal cached-vs-HEAD diff to scan, so residual markers in a never-staged file may not surface as "conflict marker" text — a different failure shape than the staged-but-marked #713 incident this gate is designed around.
**Fix:** State whether the gate also re-checks `git diff --name-only --diff-filter=U -- <files>` for remaining unmerged paths — the idiom mill-merge-in SKILL.md step 3 and `millpy-wikipush.py` already use for "still unresolved" — or explicitly confirm `git merge --continue`'s native refusal on unmerged paths is the accepted backstop for this case.

## Verdict

GAPS_FOUND
Two source-grounded gaps: an unfalsifiable test assertion (line-229 case) and an unaddressed never-staged-file path in the #713 marker gate.
MILL_REVIEW_END
