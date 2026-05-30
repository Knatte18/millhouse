# Review: task-deps-and-isolation

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-30
```

## Findings

### [GAP] `layer` enrichment owner is contradictory
**Section:** `brief-shape` decision + `_store.py` Technical Context bullet vs. `derivation-single-source` decision
**Issue:** `brief-shape` and the `_store.py` Technical Context bullet both say to update `list_tasks_brief`'s returned dict to include `layer`, but `derivation-single-source` explicitly rejected "Computing in `_store` on read (couples storage to presentation)" — and `compute_layers` lives in `_render.py`. The `_server.py` Technical Context bullet lists no change to `_handle_list_tasks_brief`. A plan writer must choose between putting a `_render` import in `_store` (contradicts the stated rejection) or enriching in `_server._handle_list_tasks_brief` (undescribed change).
**Fix:** Add one sentence clarifying that `_server._handle_list_tasks_brief` calls `compute_layers(self._store.all_tasks())` and merges the `layer` key into each row before returning — `_store.list_tasks_brief` returns only the raw stored fields (`depends_on`, `isolated`, `deferred`).

## Verdict

GAPS_FOUND
One implementation ambiguity requires resolution before plan writing can proceed.