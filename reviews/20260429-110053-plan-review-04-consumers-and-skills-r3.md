# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — 04-consumers-and-skills

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 04-consumers-and-skills
date: 2026-04-29
```

## Findings

### [NIT] `resolve_container_path` not present in `_paths.py`
**Step:** Cards 16, 17, 18
**Issue:** All three cards call `_paths.resolve_container_path(git_root)`, described as "the new helper from Card 4". The current `_paths.py` has no such function in its body or `__all__`. Card 4 is in batch 01; if that batch's plan omitted this helper, all three cards break on prefix-form repos (where `main_root.parent.parent ≠ container`).
**Fix:** Before implementing batch 04, verify batch 01 adds and exports `resolve_container_path` (container-form: `main_root.parent.parent`; prefix-form: `main_root.parent`). Same check for `resolve_hub_relative_path` referenced in Card 17.

### [NIT] Card 18 `build_plan` — fate of `worktrees: list[dict]` unspecified
**Step:** Card 18 requirement (b)
**Issue:** The card says `active_dirs` is *renamed* to `active_worktrees`, implying `worktrees: list[dict]` stays. But orphan-worktree detection currently iterates `worktrees` (from `_worktree.list_worktrees`). If `worktrees` is removed silently, orphan detection drops; if kept, `main()` retains two redundant discovery paths.
**Fix:** Explicitly state whether `worktrees` is retained (for orphan detection, requiring a continued `_worktree.list_worktrees` call in `main`) or replaced (with a `wts/` directory scan against `discover_active_worktrees` results).

### [NIT] Card 21 — `mill-resume` phase display for fresh-machine resume is unaddressed
**Step:** Card 21, `mill-resume` Phase 3
**Issue:** Phase 3 shows `(phase: X)` by reading `wiki/active/<slug>/status.md`. After the path change, no local worktree exists yet during resume candidate listing (the point of `mill-resume`). The card says "replace those paths" but `<container>/wts/<slug>/status.md` doesn't exist on a fresh clone.
**Fix:** Add a note: show `(phase: unknown)` when the worktree dir is absent, or read via `git show <branch>:status.md` as a fallback. Either is acceptable; the card should not leave the implementer inferring.

### [NIT] Card 22 — "before the existing `spawn:` example" references non-existent content
**Step:** Card 22 requirements
**Issue:** The current `config.local.yaml` template has no `spawn:` example. The placement instruction is a forward-reference to an addition in a prior batch.
**Fix:** If no prior batch adds a `spawn:` example, change the instruction to "after the leading description block, before any other examples" to avoid ambiguity.

## Verdict

APPROVE
All cards are coherent with discussion.md decisions; four NITs to clarify before implementation.