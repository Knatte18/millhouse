# handler/cluster reviewer support

```yaml
type: reviewer-extension (adds Gemini provider + cluster reviewer module + handler template)
layer: post-v2.0 follow-up for the review system
status: not started — captured from the backlog, not yet designed in detail
order: 12 — after mill-v2 core (02-11) is done. Does not block any earlier spec.
```

## Purpose

Cluster reviewers evaluate the same artefact via N parallel workers, then a handler aggregates their opinions into a single verdict. Cost wins come from provider-side prompt caching — upload the common bulk once, reference it cheaply from N worker calls + 1 handler call.

## Hard constraint: purely additive

No changes to existing templates, backends, `build_tool_rule`, or `render_prompt`. The cluster reviewer presents the same `run(prompt_text) -> str` interface as simple reviewers; cluster mechanics stay inside its module.

## Components to add

- **`_llm_gemini.py`** — Gemini provider with `cachedContent` API integration. Upload a context once, reference it in subsequent calls. Amortizes across the N workers + 1 handler call in a single review.
- **`_reviewer_cluster_g25flash_handler_sonnet.py`** (or similar naming) — cluster reviewer module. Has `MODE = "bulk"` from the backend's perspective. Internally:
  1. Receive the fully-rendered `prompt_text` from the backend.
  2. Upload to Gemini cache (once).
  3. Spawn N Gemini workers in parallel, each referencing the cache. Same prompt; variance comes from LLM non-determinism. Collect N outputs.
  4. Render the handler prompt from `templates/review-handler.md` with the N outputs injected.
  5. Call the handler (Claude or Gemini — configurable). Return the handler output as the reviewer's final response.
- **`templates/review-handler.md`** — handler/aggregator prompt. Lift from v1 `doc/prompts/handler.md` with verbatim-evidence requirement + finding-dedup rules. Handler sees N reviewer outputs and consolidates them into one verdict + finding list.

## Config wiring

`review.<type>.{reviewer|batch|holistic}: cluster_g25flash_handler_sonnet` — same config slot as simple reviewers. Zero changes to backends or schemas.
