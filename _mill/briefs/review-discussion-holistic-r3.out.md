MILL_REVIEW_BEGIN
# Review: mill-plan/review validation false-positives, hard-fails, and truncated failure reasons

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetxhigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Fix 2 self-run instruction under-specifies `_plan_validate.run` kwargs
**Section:** Decisions > Fix 2 — fix-table wording plus self-run-validator instruction
**Issue:** The proposed self-run call `_plan_validate.run(plan_dir, project_root)` (and its fallback "invoke the standalone validator CLI", i.e. `millpy-validate-plan.py`) omits `wiki_root`/`git_root`/`parent_branch`. Verified against `millpy-review-plan.py:154-164` (the actual step-1.5 gate), which passes `root=`, `git_root=git_root`, `wiki_root=wiki_root`, and a resolved `parent_branch=` — none of which the Decision's suggested self-run call includes, and `millpy-validate-plan.py:47` (the "standalone CLI" fallback) *also* omits `git_root`/`parent_branch`. Concretely: omitting `wiki_root` makes `resolve_existing_paths` (in `_review_common.py`) silently drop `wiki/`-prefixed refs, so `_check_non_existent_path` would false-positive on any legitimately-existing `wiki/`-prefixed `Context:`/`Edits:` ref during self-validation; omitting `git_root` reintroduces the nested-layout footgun this same discussion calls "first-class" elsewhere (Fix 4's Decision); omitting `parent_branch` silently no-ops `verify-unrelated-test-file`. `git_root`/`wiki_path` are already bound at SKILL.md's Entry step (lines 15-16), so this is avoidable.
**Fix:** Specify the self-run call with all four kwargs, reusing the already-bound `git_root`/`wiki_path` and a `_parent_branch.resolve(status_path)` call mirroring `millpy-review-plan.py`'s own pattern, or explicitly note the standalone-CLI alternative needs the same kwargs added before it can be trusted as equivalent to the real gate.

### [NOTE] Fix 4 rationale's ".wiki/" generalization claim is unsubstantiated by the described mechanism
**Section:** Decisions > Fix 4 — Rationale / Rejected
**Issue:** Rationale claims the git-check-ignore approach "generalizes to any conventionally-ignored path (`.scratch/`, `.wiki/`, ...)", and Rejected repeats `.wiki/` as an allowlist example — but the described mechanism only iterates the non-wiki `candidates` list built by `resolve_ref_paths`'s general branch (lines 893-909); the `wiki/`-prefix routing branch (lines 874-892, resolved against `wiki_root`) is untouched by Fix 4 and the Rejected paragraph itself notes "the wiki has its own separate ignore conventions" — casting doubt on whether `git -C git_root check-ignore` would even give a correct answer for wiki-routed content.
**Fix:** Either drop the `.wiki/` example from the rationale/rejected text, or clarify whether a literal `.wiki`-segment path (distinct from the `wiki/`-prefix convention) is the intended scenario, since `.gitignore` does list `**/.wiki` at the git-root level.

## Verdict

GAPS_FOUND
Fix 2's self-run instruction, as worded, would silently under-validate nested-layout and wiki-referencing plans.
MILL_REVIEW_END
