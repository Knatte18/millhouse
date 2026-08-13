MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: entry, phase-gate, finalize, and re-entry path gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5-class (harness-reported ID: claude-sonnet-5)
reviewed_file: plan/
date: 2026-08-13
```

## Findings

### [BLOCKING:design] Card 1's new `_config.load_config(hub_root, worktree_root)` call swaps the two arguments
**Location:** Batch 01, Card 1 (Entry step 2 insertion). **Issue:** Card 1 binds `hub_root = _paths.resolve_main_worktree_root(git_root)` and `worktree_root = _paths.resolve_hub_path()`, then calls `cfg = _config.load_config(hub_root, worktree_root)`. This is backwards: `_config.py`'s `load_config(hub_root, worktree_root)` docstring defines `hub_root` as "the hub directory" used to locate `mill-config.yaml`, and every existing call site in the repo (`mill-go-base/SKILL.md`'s `hub_root = _paths.resolve_hub_path(); cfg = _config.load_config(hub_root, git_root)`; `git-commit/SKILL.md`; `mill-quick/SKILL.md`'s explicit "`(hub_root, git_root)` argument shape for consistency") feeds `resolve_hub_path()`'s result as the *first* argument and the git worktree root as the *second*. Card 1's own file, `mill-plan/SKILL.md` line 37, already says "deep-merge `<hub_root>/mill-config.yaml`" — confirming `hub_root` means the `resolve_hub_path()` result. Card 2 (this same plan, sequenced immediately after Card 1 to jointly fix #839/#826) makes this explicit: `resolve_hub_path()` "return[s] the task worktree root where mill-config.yaml lives, not the git checkout's main worktree." So Card 1's `hub_root` variable is bound to exactly the function Card 2 says is *not* the hub, and its `worktree_root` variable is bound to exactly the function that *is* the hub — and both are then fed into `load_config` in that inverted order. Net effect: config resolution is pointed at the main worktree's `mill-config.yaml` instead of the task worktree's own (possibly locally-modified, per the `wiki-config-mutation` scenario Card 6 itself documents), breaking exactly the nested/in-flight-config case this pair of cards claims to fix. **Fix:** Feed `_paths.resolve_hub_path()`'s result as `load_config`'s first argument and `git_root` as the second — e.g. `cfg = _config.load_config(worktree_root, git_root)` using Card 1's own bound names — matching the established `mill-go-base`/`git-commit`/`mill-quick` pattern and Card 2's own corrected docstring; reconsider whether a separate `hub_root := resolve_main_worktree_root(git_root)` binding is even needed, since nothing else in this batch consumes it.

### [NIT:consistency] Card 7's "step 2" citation for `output_path` doesn't match `mill-go-base/SKILL.md`'s numbering
**Location:** Batch 01, Card 7. **Issue:** The inserted sentence cites "the general Agent-mode dispatch pattern's step 2 in `mill-go-base/SKILL.md`" for where `output_path` is "read verbatim," but in that file `output_path` is *extracted* in step 1 ("Run prepare stage") and *used verbatim* in step 5 ("Run finalize stage": "`<path>` is the `output_path` field read verbatim from step 1's prepare envelope"). Step 2 is "Call Agent tool," which never mentions `output_path`. This is an existing inaccuracy already present verbatim in `mill-start/SKILL.md` (both of its own two occurrences), which Card 7 is explicitly instructed to copy "verbatim except for the CLI filename" — so it's inherited, not introduced, and out of this plan's scope to fix (mill-start isn't edited here). **Fix:** No action required for this plan's scope; flagging for awareness only, since fixing it would require also editing `mill-start/SKILL.md`.

## Verdict

REQUEST_CHANGES
Card 1's swapped `_config.load_config` arguments is a genuine functional bug contradicting Card 2 and established codebase convention.
MILL_REVIEW_END
