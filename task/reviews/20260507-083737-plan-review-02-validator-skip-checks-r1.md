# Review: 28 (A) — review-plan robustness — 02-validator-skip-checks

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 02-validator-skip-checks
date: 2026-05-07
```

## Findings

### [BLOCKING] Card 7 Context lists Edits file; omits _plan_validate.py
**Step:** Card 7
**Issue:** `Requirements:` calls `_plan_validate.run(...)` — a function in `_plan_validate.py` — but that file is absent from Card 7's `Context:` and `Edits:`. Instead, `Context:` repeats `test-plan-validate.py`, which is already in `Edits:` and must not be in `Context:` per the "Edits files are implicitly read" rule.
**Fix:** Replace the `Context:` entry with `plugins/mill/scripts/_plan_validate.py`.

### [NIT] Card 7 Test 1 uses wiki_dir without defining it
**Step:** Card 7, Test "skip_checks filters wiki-config-mutation"
**Issue:** Requirements specify `run(..., wiki_root=wiki_dir, ...)` but never tell the implementer to create `wiki_dir` or write `config.yaml` within it. Without `wiki/config.yaml` on disk, Check 1 fires for that token and the result is non-empty, breaking the `assert result == []`.
**Fix:** Add to the requirements: create `wiki_dir = tmp / "wiki"`, `wiki_dir.mkdir()`, and write a placeholder `wiki_dir / "config.yaml"` before calling `run` (matching the pattern in `test_wiki_config_mutation_modifies`).

## Verdict

REQUEST_CHANGES
Card 7 Context field is wrong; swap the listed file to `_plan_validate.py`.