# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — state-on-worktree

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: state-on-worktree
date: 2026-04-29
```

## Findings

### [BLOCKING] `wiki/config.yaml` file-header comment still claims `<SLUG>` in `resolve_path`
**Location:** `wiki/config.yaml:6-7`
**Issue:** The file header retains `# Path placeholders use <SLUG> (uppercase). Substituted via str.replace in _review_common.resolve_path() — NOT via _render.render().` Card 14 explicitly requires dropping this line because the `paths:` templates no longer contain `<SLUG>` — it is now misleading to any reader of the config.
**Fix:** Delete the two stale comment lines; the junctions-block token table already documents `<SLUG>` semantics inline for the entries that still use it.

### [BLOCKING] `mill-start` SKILL.md Phase: Discussion Review still cites wiki path for review files
**Location:** `plugins/mill/skills/mill-start/SKILL.md`, Phase: Discussion Review, step 2
**Issue:** The prose still says "The script writes the review file under `<WIKI_PATH>/active/<slug>/reviews/`". Card 15 requires every `<WIKI_PATH>/active/<slug>/…` reference for review paths to be converted in place; this one was missed. After Cards 12–14 land, review files are written to `<worktree_root>/reviews/`.
**Fix:** Replace `<WIKI_PATH>/active/<slug>/reviews/` with `<worktree_root>/reviews/`.

### [NIT] Flow tests assert filename pattern but not full worktree-relative path prefix
**Location:** `test-review-discussion-flow.py`, `test-review-plan-flow.py`, `test-review-code-flow.py` (review file assertions in each test)
**Issue:** Card 13 requires asserting review files land at `<container>/wts/<slug>/reviews/…` rather than the old wiki path. The assertions check filename patterns (e.g. `"discussion-review-r1" in fname`) but never verify the full path prefix. Round-counter increment provides implicit consistency but the explicit cross-check is absent.
**Fix:** Add e.g. `assert str(project_root / "reviews") in r.reviews[0]["file"]` after the round assertions in each flow test's happy-path block.

### [NIT] `mill-plan` SKILL.md Plan Review On APPROVE: stale variable label `overview_path_rel_to_wiki`
**Location:** `plugins/mill/skills/mill-plan/SKILL.md`, Phase: Plan Review, step 4 On APPROVE
**Issue:** `_status.update_field(overview_path_rel_to_wiki, "approved", "true")` uses `_rel_to_wiki` suffix — a naming artifact from the pre-batch shape. The Board Discipline section is correct, but the per-step prose implies the overview file is wiki-located.
**Fix:** Rename the reference to `overview_path` (or `plan_overview_path`) to match the worktree-root context.

### [NIT] `test-millpy-spawn.py` wiki filesystem absence check is mock-level only
**Location:** `plugins/mill/unit_tests/test-millpy-spawn.py`, `test_main_happy_path_calls_spawn_core_in_order`
**Issue:** Card 11 requires asserting `wiki/active/<slug>/` does NOT appear. The test checks `"wiki_path" not in status_call.kwargs` via mock inspection — a reasonable proxy — but no fixture-level assertion confirms the wiki directory was not touched on disk.
**Fix:** Add a comment noting the mock-level check is intentional, or extend a fixture-based test to verify the wiki subtree is absent.

## Verdict

REQUEST_CHANGES — two stale cross-references (config.yaml header comment, mill-start SKILL.md review-path prose) must be fixed before the batch is fully coherent end-to-end.