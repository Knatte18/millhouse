# Review: Isolate verify PYTHONPATH so tests validate worktree code

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-25
```

## Findings

### [GAP] Error payload schema conflicts with run() sort key
**Section:** § Decisions → validator-check-shape
**Issue:** The decision specifies `{"check": "verify-not-isolated", "batch": "<batch_name>", "verify": "<full string>"}` — 3 keys, with a novel `verify` key. But `_plan_validate.py:855` sorts all errors by `(e["batch"] or "", e["card"] or 0, e["check"])`, which will `KeyError` on the missing `card` key. Every other check returns 5 keys: `{check, batch, card, path, message}`; the gotchas say "use the same JSON envelope shape," directly contradicting the decision body.
**Fix:** Conform to the existing 5-key schema: `card: None`, `path: <verify_string>`, `message: "verify command missing PYTHONPATH= prefix"`. Drop the novel `verify` key, or explicitly note that `run()` must be updated to handle it.

### [NOTE] "Batch Index DAG" phrasing points to the wrong source
**Section:** § Decisions → validator-check-shape
**Issue:** "Fires per batch entry in the overview's Batch Index DAG" could be read as checking the overview's `batches:` YAML entries' `verify:` fields; but `iter_batch_verifies` (`_plan_dag.py:318`) reads per-batch file frontmatter, not the overview batch index — these are separate fields and can diverge.
**Fix:** Clarify: the validator checks (a) the overview top-level `verify:` and (b) per-batch file frontmatter `verify:` (same source as `iter_batch_verifies`). The overview batch index `verify:` is documentation-only and is not checked.

## Verdict

GAPS_FOUND
Error payload schema (3-key vs 5-key) will cause a runtime KeyError in `run()`'s sort; must resolve before plan writing.