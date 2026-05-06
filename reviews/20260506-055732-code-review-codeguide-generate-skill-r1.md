# Review: 3 (A) — codeguide improvements: sibling placement + --branch flag — codeguide-generate-skill

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: codeguide-generate-skill
date: 2026-05-06
```

## Findings

No findings. Both cards are correctly implemented.

**Card 1 — Step 1:** The old bare `resolve.py` call is replaced with `--json` parsing of `{mode, cg_root, sibling_anchor, found}`, `git rev-parse --show-toplevel` is bound as `git_toplevel`, and the exit-on-error guard (`found == false`) is preserved. Matches the codeguide-setup Step 3 pattern as required.

**Card 2 — Step 9:** Placement rule is at the top of the step, branches correctly on `mode`, uses `<sibling_anchor> / <project_path>.relative_to(<git_toplevel>)` for sibling mode, explicitly prohibits the flat `_codeguide/modules/` collapse, references `resolve.py`'s `_sibling_walk`, and includes the exact monorepo example from `discussion.md`. Sub-bullets downstream of the rule are updated to `<placement_root>` throughout. Only the pre-existing "repo-level `_codeguide/Overview.md`" line retains its unqualified form — intentionally, since it refers to the cross-project index at `<sibling_anchor>/_codeguide/`, not the per-project path.

Only `plugins/codeguide/skills/codeguide-generate/SKILL.md` is modified; no scripts touched. Shared decisions honoured.

## Verdict

APPROVE — both cards fully satisfy their requirements with no deviations.