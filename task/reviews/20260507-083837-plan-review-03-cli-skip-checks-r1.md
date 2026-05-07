# Review: 28 (A) — review-plan robustness — 03-cli-skip-checks

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 03-cli-skip-checks
date: 2026-05-07
```

## Findings

### [BLOCKING] Card 10 test fixtures missing wiki/config.yaml on disk
**Step:** Card 10 (both new tests)
**Issue:** Both tests place `wiki/config.yaml` in a batch's `Edits:` field but never create the file in the temp fixture (`wiki_dir` is created as an empty directory). `_check_non_existent_path` calls `resolve_existing_paths` for every Edits token; the file does not exist under `project_root` or `wiki_root`, so a `non-existent-path` error fires. `--skip-check wiki-config-mutation` suppresses only the `wiki-config-mutation` finding, leaving the `non-existent-path` error in the list. Both `assert data["errors"] == []` assertions therefore fail.
**Fix:** Add `(wiki_dir / "config.yaml").write_text("")` (or `.touch()`) to the fixture setup of each test before the `os.chdir` / `_vp_mod.main(...)` call.

### [NIT] Card 10 Context repeats the Edits file
**Step:** Card 10 — Context/Edits fields
**Issue:** `plugins/mill/unit_tests/test-millpy-validate-plan.py` appears in both `Context:` and `Edits:`; Edits files are implicitly read and must not be duplicated in Context.
**Fix:** Remove `test-millpy-validate-plan.py` from `Context:` in Card 10; leave it only in `Edits:`.

## Verdict

REQUEST_CHANGES — one blocking test-fixture defect in Card 10; Cards 8 and 9 are sound.