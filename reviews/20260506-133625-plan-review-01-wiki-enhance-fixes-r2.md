# Review: 9 (B) — Wiki-enhance: small wiki cleanups — 01-wiki-enhance-fixes

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 01-wiki-enhance-fixes
date: 2026-05-06
```

## Findings

None.

All three cards are correctly scoped and internally consistent:

**Card 1** — `_config.py` confirmed generic `yaml.safe_load` with no special handling of `implementers`, `pipeline.builder`, or `pipeline.implementer`. `test-config.py` has no assertions on those keys. Both `wiki/config.yaml` and the template carry the same keys; the plan covers both. Comment-removal scope (inline + banner) matches the shared decision on no tombstones.

**Card 2** — Both regex patterns (`_HEADING_RE` in `_tasks_md.py`, `_TASK_HEADING_RE` in `_sidebar.py` and `millpy-add.py`) use `[^)]+` in the proposal capture group, so they already accept both suffix forms. `set_phase` verbatim-reconstructs from the captured group; it will round-trip `.md` correctly after the generator change. The hardcoded `(Home)` Navigation entry in `render_sidebar` is untouched as required.

**Card 3** — `test-millpy-add.py` asserts only proposal file content and mutual-exclusion CLI behaviour, no slug-line format in Home.md — no change needed. `test_multi_select_groom_then_claim_with_proposal` in `test-spawn-core.py` checks proposal file creation, not the slug-line format — no change needed. The new `test-sidebar.py` spec (sys.path pattern, two-task fixture, both assertions, standalone PASS line) matches every other test file in the directory. `run-all.py` auto-discovers via `glob("test-*.py")`; no registration step needed.

## Verdict

APPROVE — zero BLOCKINGs; plan is complete, correct, and ready to implement.