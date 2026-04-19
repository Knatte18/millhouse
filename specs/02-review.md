# Layer 02 — Review system

```yaml
status: draft
depends-on: 01-bootstrap
delivers: [mill-review, providers/claude.py, providers/gemini.py]
loc-budget: 750
```

## Goal

Single-shot review on demand. Given a file and a model name, produce a review artefact with a clear verdict and findings. No multi-round loops, no ensembles in the core CLI, no bulk-vs-tool-use dispatch decisions in the wrapper.

## Why this matters

v1's review system was the biggest source of pain:
- Reviewer invocation differed by type (bulk / tool-use / cluster)
- Multi-round loops amplified bugs
- Ensemble handlers synthesised N outputs unreliably
- Prompt materialisation was inconsistent (sometimes `mill-go` did it, sometimes `spawn_reviewer`)
- Verdict extraction had three fallback formats and still failed silently

v2 collapses this to one entry point that does one round.

## v1 reuse for this layer

From `C:\Code\millhouse-legacy\plugins\mill\scripts\millpy\`:

| v1 source | v2 target | What to take |
|---|---|---|
| `backends/claude.py` | `providers/claude.py` | **Reference, don't copy.** Read the stream-json event handling. Rewrite against v2's ReviewResult dataclass. Drop the WorkerExecResult/BulkResult split. |
| `backends/gemini.py` | `providers/gemini.py` | **Reference only.** v1's Gemini client is bulk-only. We need tool-use, so rewrite. Lift: the endpoint URL, auth header format, error-code handling. |
| `core/verdict.py` | `providers/claude.py` + `providers/gemini.py` | The YAML-frontmatter verdict extraction. Inline it in each provider. Drop the legacy-VERDICT-line and JSON-last-line branches unless we need them (probably don't). |
| `reviewers/base.py` | — | **Do NOT carry over.** Class hierarchy and Protocol. Replace with plain `ReviewResult` dataclass. |
| `doc/prompts/*.md` | `templates/review-prompt-*.md` | **Reference.** The v1 prompts have been iterated on. Lift the evaluation criteria wording, drop the dispatch-mode-specific variants. |

See `06-v1-reuse.md` for the full lifting protocol.

## Deliverables

### 1. `mill-review` — single-shot review CLI

**Arguments:**
```
mill-review --type <discussion|plan|code> \
            --file <path> \
            --model <model-id> \
            [--out <review-file-path>] \
            [--mode bulk|tool-use]       # override the default for the review type
```

- `plan` and `code` default to `bulk` — override with `--mode tool-use` for reviewer to explore beyond Reads/Modifies
- `discussion` is always `tool-use` — `--mode bulk` errors out

**Behaviour:**

1. Load `<type>` prompt template from `plugins/mill/templates/review-prompt-<type>.md`
2. Load the artefact file (`<path>`)
3. **Determine relevant files** (what gets bulked into the prompt):
   - `--type plan`: parse the plan's `Reads:` and `Modifies:` fields across all cards; load each file
   - `--type code`: parse the diff (from `git diff` or provided patch); load the changed files
   - `--type discussion`: no pre-bulking — reviewer uses tool-use to discover files itself (see below)
4. Look up `<model-id>` in config (`models:` mapping) → resolve to `(provider, model_id, effort)`
5. Substitute placeholders in template:
   - `<ARTEFACT_PATH>` → `<path>`
   - `<ARTEFACT_CONTENT>` → full artefact content
   - `<RELEVANT_FILES>` → concatenated contents of the bulked files with clear delimiters
   - `<REVIEW_OUTPUT_PATH>` → `<out>` or derived default
6. Call provider's `review()` function:
   - Default: `mode="bulk"` — prompt already includes all relevant files
   - If `--explore`: `mode="tool-use"` — reviewer can fetch more via Read/Grep tools
7. Parse provider's returned ReviewResult
8. Write the review output to `<out>` using `review-output.md` template
9. Print single-line JSON result to stdout: `{"verdict": "...", "review_file": "..."}`
10. Exit 0 on success, 1 on provider error, 2 on missing inputs

**Model dispatcher:**

Single function, ~30 LOC:
```python
def dispatch(model_id: str, prompt: str) -> ReviewResult:
    cfg = load_config()
    entry = cfg["models"].get(model_id)
    if entry is None:
        raise ValueError(f"Unknown model: {model_id}")
    provider_mod = import_provider(entry["provider"])
    return provider_mod.review(prompt, entry["model_id"], entry.get("effort"))
```

No if/elif chains, no class hierarchy. One lookup, one call.

### 2. Two providers from the start

Shipping with *two* providers at Layer 02 forces the provider abstraction to be real, not theoretical. If we only had Claude, we wouldn't know if the dispatcher works for anything else. With Claude + Gemini working on day one, adding Ollama later is a proven 1-file extension.

**Provider contract (both must satisfy):**

```python
def review(prompt: str, model: str, effort: str | None) -> ReviewResult:
    """
    Dispatch prompt to the provider. Return a ReviewResult.

    ReviewResult(
        verdict: str,            # "APPROVE" | "REQUEST_CHANGES" | "ERROR"
        findings_path: Path | None,
        raw_output: str,
        tokens_used: dict | None # {prompt, completion} if provider reports it
    )
    """
```

Any provider-specific behaviour (tool-use, caching, auth) is internal to the provider module. The dispatcher doesn't know or care.

### 3. `providers/claude.py` — Claude provider

**Public function:**
```python
def review(prompt: str, model: str, effort: str | None, mode: str) -> ReviewResult:
    ...
```

`mode` (required):
- `"bulk"` — prompt includes all files; Claude just evaluates and writes the review
- `"tool-use"` — Claude may use Read/Grep/Write tools during review (natural for Claude CLI)

**Behaviour:**

1. Spawn `claude.exe -p "<prompt>" --output-format stream-json --model <model>` (plus `--effort <effort>` if set)
2. In `bulk` mode, the prompt explicitly instructs "do not use tools, just write the review based on the provided content"
3. In `tool-use` mode, the prompt allows free tool usage
2. Parse stream-json output line-by-line, capturing:
   - Tool-call events (especially `Write` calls — the agent may write the review file itself)
   - Final text response
3. Extract verdict from the result:
   - **If agent called `Write`:** read the written file, look for `VERDICT:` line or YAML frontmatter `verdict:`
   - **If agent only produced text:** treat the last 100 lines as the review; look for `VERDICT:` / JSON object
4. Return `ReviewResult(verdict=..., raw_output=..., findings_path=...)`

**Hard requirements:**
- Must handle both tool-use and free-text responses. Agent is not guaranteed to use the `Write` tool.
- Must handle timeouts gracefully. Claude CLI can hang; wrap in `subprocess.run(timeout=...)`.
- Must handle authentication errors (claude.exe returns specific stderr for missing auth) with a clear error message.

### 4. `providers/gemini.py` — Gemini provider (bulk + tool-use)

**Public function:**
```python
def review(prompt: str, model: str, effort: str | None, mode: str) -> ReviewResult:
    ...
```

`mode` is required (no default) — caller decides based on review type and user flag:
- `"bulk"` — prompt already contains all the files the reviewer should see, embedded inline. Single API call.
- `"tool-use"` — reviewer can call `Read`/`Grep` tools to fetch files as needed.

(`effort` is ignored for Gemini — no equivalent parameter.)

**Not in v2.0 defaults:** Gemini is implemented but not the default for any review type. SonnetMax handles all reviews in v2.0. Gemini becomes attractive when cost or rate-limit constraints kick in, or when Gemini 3 Pro's exploration style proves better for discussion-review.

**Mode per review type:**

| Review type | Default | Other modes allowed | Why |
|---|---|---|---|
| `plan` | **bulk** | `tool-use` (via `--mode tool-use`) | `Reads:`/`Modifies:` lists every relevant file — bulk is cheap and sufficient. Opt into tool-use when reviewer should verify claims beyond specified scope. |
| `code` | **bulk** | `tool-use` (via `--mode tool-use`) | Diff is the scope. Tool-use available for broader verification. |
| `discussion` | **tool-use** | none — forced | Reviewer's explicit job includes discovering affected files *not yet mentioned*. Cannot be pre-bulked. `--mode bulk` is rejected with error. |

User can explicitly choose mode with `--mode bulk|tool-use` on `mill-review`. For `discussion`, `--mode bulk` errors out.

**Default model per review type (v2.0):**

| Review type | Default model | Provider | Notes |
|---|---|---|---|
| `plan` | `sonnet-max` | claude | Tool-use capable; bulk works natively |
| `code` | `sonnet-max` | claude | Same |
| `discussion` | `sonnet-max` | claude | Tool-use capable |

SonnetMax is the default across all review types in v2.0.

**Gemini 3 Pro for discussion (future):** Gemini 3 Pro supports tool-use and works well for the explorer-style discussion-review. Once the Gemini provider is battle-tested (post-v2.0), `discussion-review-model: gemini-3-pro` becomes a reasonable default for that review type specifically. Config supports this by having a separate `<type>-review-model` key — no code change needed to swap.

**Bulk mode (default) behaviour:**

1. Read `GEMINI_API_KEY` from `.env`
2. POST to `https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent`
   - `contents`: the prompt (files already embedded by caller)
   - No tools, no loops
3. Extract verdict from the response text (YAML frontmatter or `VERDICT:` line)
4. Return `ReviewResult`

**Tool-use mode behaviour (when `mode="tool-use"`):**

1. POST with `tools`: `Read`, `Grep` function declarations, `toolConfig.mode: AUTO`
2. Loop: if response has `functionCall`, execute tool locally (read file / grep), append `functionResponse`, POST again
3. Loop until plain-text response or `max_turns` (default 20)
4. Extract verdict from final text

**Tool implementations (only needed for tool-use mode):**

- `Read(path: str) -> str` — refuse if path is outside project root (security)
- `Grep(pattern: str, path: str) -> str` — simple text search

Each tool is ~15 LOC. Total tool suite: ~40 LOC, in `providers/_tools.py`.

**Auth error handling:**
- No API key set → clear error message pointing to config.local.yaml
- Rate limit (429) → retry with backoff, give up after 3 attempts
- Invalid model → error with suggestion

**Caching:**
Not in v2.0 of this provider. Add later if Gemini usage grows. Design consideration: prompt templates are already structured with shared prefix first, task-specific bits last — this makes it cache-friendly when we do add caching (implicit caching activates on identical 1024+-token prefixes).

### 5. Templates

```
plugins/mill/templates/
  review-prompt-discussion.md
  review-prompt-plan.md
  review-prompt-code.md
  review-output.md
  review-prompt.schema.md      ← shared schema for all prompts
  review-output.schema.md
```

Each prompt template has clearly marked placeholders:
- `<ARTEFACT_PATH>`, `<ARTEFACT_CONTENT>`, `<REVIEW_OUTPUT_PATH>`
- `<TASK_TITLE>` (optional, used when context available)
- `<CONSTRAINTS>` (optional, from wiki)

**Prompt template rules:**
- No provider-specific wording
- No conditional branches ("if bulk then..., if tool-use then...")
- Short enough to read at a glance (target: under 3000 tokens including placeholders)
- Output contract is explicit: final output is a JSON line with `{"verdict": "...", "review_file": "..."}`, preceded by the review report

### 6. Review output format

Fixed structure (enforced by `review-output.schema.md`):

```markdown
---
verdict: APPROVE | REQUEST_CHANGES
reviewer_model: <model-id>
reviewed_file: <path>
date: <iso-8601>
---

# Review: <artefact-name>

## Findings

### [BLOCKING|NIT] <short title>
<section or line reference>
<issue>
<suggested fix>

### ...

## Verdict

APPROVE | REQUEST_CHANGES
<one-sentence summary>
```

One format for all review types. Differences between plan/code/discussion are in the *prompt*, not the output.

## File layout for this layer

```
plugins/mill/
  scripts/
    mill-review.py           ← ~150 LOC
    providers/
      claude.py              # ~200 LOC (stream parser + subprocess + extraction)
    gemini.py                ← ~250 LOC (API client + tool-use loop + extraction)
    _tools.py                ← ~60 LOC (shared tool implementations: Read/Write/Grep)
  templates/
    review-prompt-plan.md
    review-prompt-code.md
    review-prompt-discussion.md
    review-output.md
    (schemas)
  skills/
    mill-review/SKILL.md
  integration_tests/
    test-review-plan-claude.ps1
    test-review-code-claude.ps1
    test-review-discussion-gemini.ps1
```

## Acceptance criteria

After this layer ships:

1. `mill-review --type plan --model sonnet --file sample-plan.md` runs through Claude, returns verdict
2. `mill-review --type discussion --model gemini-3-pro --file sample-discussion.md` runs through Gemini with tool-use, returns verdict
3. Both providers can return APPROVE and REQUEST_CHANGES verdicts on sample inputs
4. Exit codes are consistent: 0 on success, non-zero on auth/network/timeout errors
5. Gemini tool-use loop terminates cleanly (max-turns cap works)
6. Stream-json parsing for Claude works when agent uses `Write` tool AND when it only produces text
7. Same abstraction (`dispatch(model_id, prompt) → ReviewResult`) works for both providers without special-casing in `mill-review.py`

## Future extensions (not in v2.0)

### Adding Gemini caching

Layer 02 ships Gemini with tool-use but no explicit caching. Adding it later: `providers/gemini.py` handles explicit caching via `/cachedContents` API internally. The prompt templates are already ordered for cacheability (shared prefix first, task-specific bits last) — this makes implicit caching also work when we activate it.

### Adding Ollama (local models)

One file: `providers/ollama.py` with the same signature. Hits `http://localhost:11434/api/generate`. No tool-use support in current Ollama versions, so it's bulk-only (text in, text out). Dispatcher doesn't care.

### Adding ensemble review (separate script)

`scripts/mill-review-ensemble.py` with its own args:
```
mill-review-ensemble --type <t> --file <f> --workers <worker-spec> --handler <model>
```

Calls `mill-review` N times (workers) then calls `mill-review` once more on the concatenated outputs (handler). Not part of the core CLI. Separate script, separate skill. Opt-in per task.

### Adding a wrapper-orchestrator (if needed)

If it turns out we need LLM-mediated routing (e.g., "if this plan is complex, use ensemble; if simple, single-shot"), we can add a thin `mill-review-auto` that asks a cheap model which strategy to use. But **not in v2.0.** Keep routing config-driven until we have evidence that LLM routing adds value.

## Non-goals for Layer 02

- Multi-round reviewer loops (REQUEST_CHANGES triggers a second round): not here. Handled by Layer 03 (mill-go) which loops by re-invoking `mill-review`.
- Ensemble in core CLI (separate script later)
- Ollama provider (no tool-use yet in Ollama; add when it matters)
- Gemini explicit caching (tool-use first, optimize later)

## Open questions

- [ ] Where exactly does the review output file land by default? Options:
  - `.millhouse/wiki/active/<slug>/reviews/<timestamp>-<type>-review.md` (in wiki, committed)
  - `.millhouse/scratch/reviews/<timestamp>-...` (local only)
  - Per-invocation `--out` argument required (no default)
- [ ] How do we decide model's `effort` parameter for v2.0 when it's relevant only for Claude? Keep it in the model config, nullable for providers that don't use it?
- [ ] Template substitution: Python `str.replace()` on `<TOKEN>` is simplest. Jinja2 is overkill. Agreed?
