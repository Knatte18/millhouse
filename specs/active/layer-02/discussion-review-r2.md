# Discussion Review — Layer 02 (r2)

```yaml
reviewer: claude-sonnet (via Agent tool)
reviewed_file: specs/active/layer-02/discussion.md
date: 2026-04-20
round: 2
```

## Findings

### [GAP] `_llm_claude.py` tool-use mode: what tool permissions are actually passed to Claude CLI

**Section:** Contracts between layers → Reviewer → LLM-provider / Mode-split for discussion-review

**Issue:** The discussion specifies that `mode="tool-use"` lets Claude "use Read/Grep/Write during the review," but it never says *how* `_llm_claude.py` enables those tools. Claude CLI requires explicit `--allowedTools` flags (or equivalent) to grant tool access. In bulk mode the prompt explicitly says "do not use tools." In tool-use mode, what exact flags does `_llm_claude.py` pass to `claude -p`? Without this the implementer must guess — and getting it wrong means tool-use silently falls back to text-only responses. The discussion names this as a key architectural differentiator between discussion review and plan/code review, so the gap is consequential.

**Suggested fix:** Add a line to the `_llm_claude.py` contract snippet specifying the CLI flags for each mode. Example: `mode="tool-use"` → add `--allowedTools Read,Write,Grep` (or `--tool-use auto`); `mode="bulk"` → add `--allowedTools ""` or no tool flags. State whether the prompt instructions alone are sufficient to suppress tool use in bulk mode, or whether a flag is also required.

---

### [GAP] `render_prompt` wrapper's token grammar vs. `_render.py` actual behavior

**Section:** Templates / `_review_common.py`

**Issue:** The discussion lists placeholder tokens as mixed-case with underscores in some cases (e.g., `<TASK_TITLE>`, `<ARTEFACT_PATH>`, `<REVIEW_OUTPUT_PATH>`, `<REVIEWER_MODEL>`). The actual `_render.py` regex is `r"<([A-Z][A-Z0-9_]*)>"` — uppercase only, with underscores allowed. All the listed tokens are in uppercase, so they appear to be fine. However, `render_prompt` is described as a thin wrapper around `_render.render()` "with template-dir resolution." The discussion gives the wrapper signature as `render_prompt(template_name: str, **tokens) -> str` — note `**tokens` implies keyword-argument names that get uppercased or passed as-is. `_render.render()` takes `values: dict[str, str]` with bare token names (no angle brackets). If the wrapper passes `**tokens` directly as `values`, a caller writing `render_prompt("review-plan-bulk", artefact_path="…")` would need to pass `ARTEFACT_PATH="…"` (uppercase) to match the template. This is a latent API usability trap: a plan writer implementing the wrapper has two plausible interpretations (auto-uppercase the keys, or require the caller to uppercase). The discussion is silent on this.

**Suggested fix:** Specify that `render_prompt` auto-uppercases the token keys before passing them to `_render.render()` (the natural ergonomic choice), or state the caller is responsible for uppercasing. One sentence resolves this.

---

### [GAP] Filename mismatch between canonical pattern definition and round-discovery regex for plan-holistic

**Section:** Round discovery → Canonical filename pattern / Round-discovery regex

**Issue:** The canonical filename for a plan holistic review is defined as `<ts>-plan-review-r<N>.md` (e.g., `20260418-143300-plan-review-r1.md`). The simple regex `RE_SIMPLE` matches filenames of the form `^\d{8}-\d{6}-(?P<type>discussion|code|plan)-review-r(?P<n>\d+)\.md$`. This regex would match `…-plan-review-r1.md` — so for the holistic case, `RE_SIMPLE` handles it. However, `RE_BATCH` also uses `plan-review-(?P<batch>[a-z0-9-]+)-r<N>` with a batch group that matches any lowercase-alphanumeric-with-hyphens string. This means a holistic file `…-plan-review-r1.md` could also partially match `RE_BATCH` if `r1` is interpreted as the batch name (it matches `[a-z0-9-]+`). In other words, `RE_BATCH` is not anchored to require a separator before `r<N>` — the suffix `-r1` satisfies `[a-z0-9-]+-r\d+` with `batch=r` and `n=1`. A naive implementation that checks `RE_BATCH` first (or both) would double-count holistic files. The regex needs a tighter anchor: the batch name should not itself look like `r\d+`.

**Suggested fix:** Add a negative lookahead or a stricter batch-name pattern to `RE_BATCH`. For example, require the batch name to contain at least one non-`r` character or to not match `^r\d+$`: `r"^\d{8}-\d{6}-plan-review-(?P<batch>(?!r\d+$)[a-z0-9-]+)-r(?P<n>\d+)\.md$"`. Or state explicitly that `RE_SIMPLE` is checked first and a file that matches `RE_SIMPLE` is excluded from `RE_BATCH` matching.

---

### [GAP] Config `<slug>` substitution mechanics not specified

**Section:** Config contract / Config → script linkage

**Issue:** The config defines paths with a `<slug>` placeholder (e.g., `active/<slug>/discussion.md`). The discussion says these are "substituted by the script," but it does not say *how or where* that substitution happens. The active slug is discovered by scanning `.millhouse/` for `.<slug>.slug.md`. Once found, what is the substitution call? Does `_review_common.find_active_slug()` return the bare slug string, and each backend does a plain `str.replace("<slug>", slug)`? Does it go through `_render.render()`? The token `<slug>` starts with a lowercase letter — but `_render.py`'s regex only matches tokens starting with an uppercase letter (`[A-Z]`). If the path strings go through `_render.render()`, `<slug>` would be left unresolved and raise a `KeyError` on any `<UPPER>` tokens while silently leaving `<slug>` in place — the opposite of a useful error. This is an implementability gap with a concrete failure mode.

**Suggested fix:** State explicitly: the slug substitution for config path strings uses a plain `path_template.replace("<slug>", slug)` (not `_render.render()`), and specify where this happens (e.g., in `load_config()`, or in each backend after calling `find_active_slug()`). Alternatively, change the placeholder convention in the config to uppercase (`<SLUG>`) to align with `_render.py`'s grammar — but then document that the config paths are rendered via `_render.render()`.

---

### [GAP] `_llm_claude.py` timeout and authentication handling not specified

**Section:** Contracts between layers → Reviewer → LLM-provider / Failure modes

**Issue:** The failure mode table covers config-level errors (unknown reviewer, slug ambiguity, round cap) but not LLM-level failures. The original `layer-02-review.md` explicitly required: handle timeouts gracefully with `subprocess.run(timeout=...)`, handle Claude CLI authentication errors with a clear message. The discussion's `_llm_claude.py` contract snippet shows only `def run(text, *, model, mode, effort) -> str` with no mention of what happens on timeout, Claude CLI authentication failure, or non-zero exit from the subprocess. A plan writer implementing `_llm_claude.py` has no guidance on these cases. The partial-failure handling section covers what happens when a sub-review fails at the batch level, but it doesn't say what `_llm_claude.py` should raise/return to trigger that path.

**Suggested fix:** Add a brief paragraph or table entry to `_llm_claude.py`'s contract section: on timeout → raise `LLMError("timeout")`, on non-zero exit → raise `LLMError(stderr)`, on auth failure → raise `LLMError("not authenticated")`. Specify that `_reviewer_sonnetmax.py` propagates this exception upward and that the backend catches it to populate the `verdict: ERROR` entry.

---

### [NOTE] `review-output.schema.md` not added to `ref-formats.md` format inventory

**Section:** Scope for v2 Layer 02 / Templates

**Issue:** The discussion adds `review-output.schema.md` as a new template file. `ref-formats.md` maintains a "Total: 12 canonical formats" inventory with the rule "No additions without a spec update." The discussion's supersession note covers the `pipeline:` config section but does not mention the schema file addition to the format inventory. This creates a drift between the frozen inventory count (12) and the actual state after Layer 02 lands.

**Suggested fix:** Either add a supersession note for the format inventory table (noting that the template file list in `ref-formats.md` will be updated to include `review-output.schema.md` when implementation begins), or note that this update is deferred to the spec-rewrite phase. No action needed before planning, but worth acknowledging.

---

### [NOTE] `review-discussion.md` template instructs the reviewer to write its output — but the backend also writes

**Section:** Templates / Contracts between layers

**Issue:** The discussion says the `review-discussion.md` template "instructs the reviewer to read the discussion file itself, follow references in the `## Technical Context` section, and write the review to the canonical path." This mirrors v1's tool-use prompt design where the reviewer used the `Write` tool to create the output file. However, `write_review_file()` in `_review_common.py` is also supposed to write the file. In v1 this tension was present too (as `layer-02-review.md` noted: "If agent called `Write`: read the written file, look for verdict"). For tool-use mode, it is unclear whether: (a) the template instructs Claude to write the file and the backend reads it back, or (b) Claude returns the review text and the backend writes it. The design says the reviewer returns "raw review text" to the backend, which implies (b) — but then the template should not instruct Claude to write the file. If Claude writes the file in tool-use mode, the backend's `write_review_file()` call would either duplicate the file or be a no-op, and `parse_verdict()` would need to read the written file rather than the return value.

**Suggested fix:** Clarify which party writes the review file in tool-use mode: either (a) state that in tool-use mode the template instructs Claude to write the file, the reviewer returns the raw text only, and the backend skips `write_review_file()` (reads and re-uses the Claude-written path); or (b) state that the template does NOT instruct Claude to write the file, Claude returns its review as text, and the backend writes it via `write_review_file()`. Option (b) is simpler and more consistent with the 4-layer contract.

---

### [NOTE] `review-plan-bulk.md` used for both per-batch and holistic — but per-batch needs batch context

**Section:** Templates / File structure

**Issue:** The discussion states `review-plan-bulk.md` is used for "per-batch and holistic both use bulk variant." The placeholder list includes `<ARTEFACT_CONTENT>` (singular). In per-batch mode the backend needs to bulk multiple files: the batch file content and the plan overview. In holistic mode it's the whole plan. The template cannot straightforwardly serve both unless the backend concatenates everything into `<ARTEFACT_CONTENT>`. This is workable, but the mapping from "what does the backend put in `<ARTEFACT_CONTENT>` for per-batch vs. holistic" is unspecified. A plan writer would have to invent this.

**Suggested fix:** Add one sentence specifying how the backend populates `<ARTEFACT_CONTENT>` for the per-batch case: e.g., "For per-batch reviews, the backend concatenates the plan overview + the batch file content into a single `ARTEFACT_CONTENT` block using `bulk_files()`." Alternatively, have a separate `review-plan-batch-bulk.md` template with different tokens — but that contradicts the one-template design.

---

### [NOTE] LOC cap override not fully explained

**Section:** Decisions log — Decision 22

**Issue:** Decision 22 states the LOC budget from `00-overview.md` (1500 LOC total hard cap) is overridden for Layer 02. The rationale given is "we do this properly and count LOC only if it becomes a concern." This is one-directional: it removes a constraint without giving a replacement bound. A plan writer implementing all 3 API scripts, 4 backend files, 1 reviewer, 1 LLM-provider, and 5 templates has no target size. Without any stated bound, "properly" is undefined and there's no signal when a card implementation should stop and ask for a minimum version.

**Suggested fix:** Add an informal expected range, e.g., "Expected total: ~400–600 LOC across all Python files, well within the v2 spirit even without enforcing the cap." This isn't binding but gives the plan writer a reference point.

---

### [NOTE] Interaction with Layer 01: `find_active_slug()` depends on `.millhouse/` being scanned, but no Layer 01 function for this exists

**Section:** Interaction with Layer 01 / Path resolution

**Issue:** Layer 01 delivers `mill-setup`, `mill-add`, and `mill-list`. The `.<slug>.slug.md` file is listed in `ref-formats.md` and `00-overview.md` as created by `mill-spawn` (Layer 04). The discussion depends on `find_active_slug()` scanning `.millhouse/` for `.<slug>.slug.md`. In a Layer 02 test context, the slug file must be placed manually or by a test fixture — the Layer 01 scripts don't create it. This is acknowledged implicitly (integration test instructions say "real Claude CLI invocation required") but the test setup (how the test environment provides a `.slug.md` and the required wiki structure) is not described.

**Suggested fix:** Add a sentence to the integration test acceptance section noting the test fixture requirements: a `.millhouse/.<slug>.slug.md` must be pre-seeded, a `wiki/` junction must be present pointing at a wiki directory with the required `config.yaml`, and `active/<slug>/` subdirectories must exist. This removes ambiguity from test planning.

---

### [NOTE] `all sub-reviews failed` edge case — exit code inconsistency with partial failure

**Section:** Failure modes → Failure modes on stdout/stderr table

**Issue:** The table shows "All sub-reviews failed" → exit 1, stdout empty. But partial failure (some sub-reviews fail) → exit 0, stdout JSON. This creates an asymmetry: a single failed sub-review out of 5 produces a usable `ReviewResult` (exit 0), while all 5 failing produces no JSON (exit 1). The orchestrator's behavior is different in each case. This is a reasonable design, but the boundary condition is underdefined: if `N-1` of `N` sub-reviews fail, is that partial failure (exit 0) or "all failed" (exit 1)? The text of the partial failure section says "other sub-reviews that succeeded write their files normally" — implying at least one succeeded. But the threshold is not stated explicitly.

**Suggested fix:** State the rule explicitly: "All sub-reviews failed" means zero succeeded; exit 1, stdout empty. If at least one succeeded, exit 0 with JSON (and the aggregate verdict escalates to `REQUEST_CHANGES`).

---

## Verdict

GAPS_FOUND

Five GAPs require resolution before implementation planning: the tool-use mode CLI flags for `_llm_claude.py`, the `render_prompt` token-casing contract, the `RE_BATCH` regex ambiguity that can double-count plan-holistic files, the `<slug>` substitution mechanism incompatibility with `_render.py`'s uppercase-only grammar, and the `_llm_claude.py` error propagation contract. The remaining five findings are NOTEs that do not block planning.
