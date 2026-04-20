# Layer 02 — Review API discussion

```yaml
status: in-design
slug: layer-02
written: 2026-04-20
revised: 2026-04-20 (r4 — after discussion-review-r3)
supersedes-partially: [specs/layer-02-review.md, specs/roadmap/M2-review.md, specs/ref-formats.md (pipeline section, format inventory count), specs/00-overview.md (Provider plugin pattern section)]
```

## Context

This file captures the design discussion for the v2 review system. The original
specs (`layer-02-review.md`, `roadmap/M2-review.md`) were written before this
discussion and are **partially superseded** by the decisions below.

Revision history:
- r1: initial architecture (4-layer, bulk-only, `<slug>` lowercase)
- r2: split mode by review type (discussion=tool-use, plan/code=bulk), dropped
  LOC-budget concern, added explicit supersession notes, specified failure
  modes
- r3: moved mode out of the per-call parameter into the reviewer itself
  (each reviewer declares `MODE`), split `_llm_claude` into `run_bulk` and
  `run_tool_use`, uppercased `<SLUG>` for internal consistency, added
  concrete task-flow diagrams per review type
- r4: added `ReviewError` and `resolve_path` to `_review_common.py`; moved
  `LLMError` to `_llm_claude.py` (correct layering); guarded empty-batch
  edge case; **dropped `plan_start_hash`** (use `git merge-base main HEAD`
  for code-review diff baseline); task title loaded from `.<slug>.slug.md`
  frontmatter (new field `task_title`); renamed `code.batch` → `code.reviewer`;
  removed `<RELEVANT_FILES>` as an unused token; added `read_constraints_md`
  to common; specified integration-tests as local-dev-only for v2

## Supersession notes — THIS FILE IS THE CANONICAL SPEC

**This discussion is the ground truth for Layer 02.** The files listed below
are legacy documentation that predates this discussion. They will be rewritten
to match this file once implementation lands. **On any conflict, this file
wins** — do not file bugs or raise review objections citing those files as
the source of truth.

- `specs/ref-formats.md` → the `pipeline:` config section is replaced by
  the `review:` + `reviewers:` structure below. The "Total: 12 canonical
  formats" inventory will be updated to include `review-output.schema.md` and
  the 5 review-prompt templates. The `slug.md` format gains a new `task_title`
  field in its YAML frontmatter, loaded by `load_task_title()` in
  `_review_common.py` (falls back to slug if absent).
- `specs/00-overview.md` → the "Provider plugin pattern" (with
  `review(prompt, model, effort) -> ReviewResult` signature) is replaced by
  the 4-layer architecture below. The LLM-provider only returns raw text; the
  backend assembles `ReviewResult`.
- `specs/layer-02-review.md` → the single-script `mill-review --type` design
  is replaced by three separate scripts. The 750 LOC budget claim is dropped.
- `specs/roadmap/M2-review.md` → sub-milestones M2.1–M2.5 will be redrawn to
  match the new architecture once implementation planning starts.

## Process note — `specs/active/<layer>/` convention

Active layer design discussions live under `specs/active/<layer>/` while the
layer is **in design**. Once implementation begins, the artefacts in this
directory are frozen in place (for history), and the canonical spec files
(`specs/layer-NN-*.md`) are rewritten to match the converged design.

Files typically present:
- `discussion.md` — the design discussion (this file)
- `discussion-review-rN.md` — one file per review round
- (possibly) `open-questions.md` — if questions accumulate

## Goal

Build a review API that Claude Code (orchestrator) calls to request reviews.
Under the hood is Python logic that can be swapped out — different LLM
backends, cache strategies, even non-LLM implementations (e.g., email-to-human).
The caller doesn't know or care.

Three review types: `discussion`, `plan`, `code`.

## Terminology

| Term | Meaning |
|---|---|
| **Frontend** | The orchestrator — the caller (e.g. a `mill-go` session in Claude Code) |
| **API** | The three CLI scripts (`mill-review-discussion.py`, `mill-review-plan.py`, `mill-review-code.py`) |
| **Backend** | Everything behind the API — templates, bulking, file-writing, reviewer dispatch, parsing, ReviewResult assembly |
| **Reviewer** | A named strategy module (simple LLM, cluster, round-switching hybrid). Declares `MODE` constant and exposes `run(prompt_text)`. |
| **LLM-provider** | Thin wrapper around a specific model call. Exposes one function per mode (`run_bulk`, `run_tool_use`). |
| **prompt_text** | The fully-rendered prompt string passed to the LLM. Built by the backend from a template + tokens + bulked content. |

Claude is **not** a backend — it is an LLM. The backend could in principle be
an email-based reviewer that sends Henrik a mail and waits for a reply. The
API contract doesn't change.

## Architecture — 4 layers

```
Orchestrator (frontend)
    ↓  CLI call, null args
API (mill-review-*.py)              ← thin, ~15 LOC each
    ↓  function call
Review backend (_review_*.py)       ← type-specific orchestration:
                                       templates, bulking, rendering,
                                       parallelism, file-writing
    ↓  reviewer.run(prompt_text)
Reviewer (_reviewer_<name>.py)      ← declares MODE; forwards prompt_text
                                       to LLM-provider via mode-specific fn
    ↓  _llm_claude.run_bulk(...)
    ↓  _llm_claude.run_tool_use(...)
LLM-provider (_llm_<name>.py)       ← one function per mode;
                                       subprocess/HTTP to actual model
```

Each layer is swappable independently.

## Mode mechanics

Two modes:
- **`bulk`** — all relevant content is inlined in the prompt. LLM does not use
  tools. Faster, cheaper, predictable.
- **`tool-use`** — the LLM may Read/Grep/Write files during the review.
  Natural fit when the reviewer needs to explore beyond pre-determined files.

**Every reviewer declares its mode** as a module-level `MODE` constant:

```python
# _reviewer_sonnetmax.py
MODE = "bulk"
def run(prompt_text: str) -> str:
    return _llm_claude.run_bulk(prompt_text, model="claude-sonnet-4-5", effort="max")

# _reviewer_sonnetmax_tool.py
MODE = "tool-use"
def run(prompt_text: str) -> str:
    return _llm_claude.run_tool_use(prompt_text, model="claude-sonnet-4-5", effort="max")
```

**The backend reads `reviewer.MODE`** before calling the reviewer, to decide:
1. Which template variant to use (bulk vs. tool-use variants differ in
   instructions — e.g., "here's the content" vs. "read the file yourself")
2. Whether to pre-bulk referenced files into the prompt

**Incompatible combinations** (no matching template in v2) cause a clear error:

> `"No bulk template exists for discussion review. Configure a tool-use reviewer."`

## File structure (flat)

All scripts live directly under `plugins/mill/scripts/`. **No submodules.**

```
plugins/mill/scripts/
  # API (null-arg CLI)
  mill-review-discussion.py
  mill-review-plan.py
  mill-review-code.py

  # Review backend (type-specific orchestration)
  _review_discussion.py       # 1 tool-use call
  _review_plan.py             # N per-batch (parallel, bulk) + 1 holistic (bulk)
  _review_code.py             # 1 bulk call (style: single | multi)
  _review_common.py           # shared: round discovery, rendering,
                              #   bulking, verdict parsing, slug lookup,
                              #   file writing, ReviewError exception,
                              #   regex patterns RE_SIMPLE / RE_BATCH

  # Reviewers (named strategies — v2 ships both)
  _reviewer_sonnetmax.py      # MODE = "bulk"
  _reviewer_sonnetmax_tool.py # MODE = "tool-use"
  # _reviewer_g25flash_x3_sonnet.py             future (cluster, bulk)
  # _reviewer_sonnetmax_round_switching.py      future (hybrid)

  # LLM-providers (v2 ships only Claude)
  _llm_claude.py              # run_bulk() and run_tool_use()
  # _llm_gemini.py                              future
  # _llm_ollama.py                              future
```

### What `_review_common.py` contains

```python
def discover_round(reviews_dir: Path, review_type: str) -> int:
    """Scan reviews_dir, find highest -r<N>.md for the type, return N+1.
       Implementation: for each file: try RE_SIMPLE; if match → record and
       skip RE_BATCH; otherwise try RE_BATCH. This ordering prevents a
       plan-holistic file (e.g. …-plan-review-r1.md) from being mis-
       identified as a batch.
       If reviews_dir does not exist, return 1."""

def bulk_files(file_paths: list[Path]) -> str:
    """Concat file contents with '--- FILE: <path> ---' delimiters."""

def parse_verdict(raw_output: str) -> str:
    """Extract 'APPROVE' or 'REQUEST_CHANGES' from YAML frontmatter. Fail loudly."""

def render_prompt(template_name: str, **tokens) -> str:
    """Wrapper around _render.render(). Auto-uppercases tokens' keys:
       artefact_path='...' becomes ARTEFACT_PATH='...' before substitution.
       Template path resolution:
           Path(__file__).parent.parent / "templates" / f"{template_name}.md"
       i.e. relative to the scripts directory, up one level to the plugin
       root, into the templates folder. Raises FileNotFoundError if missing."""

def resolve_path(path_tmpl: str, slug: str, wiki_root: Path) -> Path:
    """Resolve a config path template to an absolute path.
       Simple string replace — does NOT use _render.render() (that reads files).
       Example: ('active/<SLUG>/discussion.md', 'my-slug', <wiki>)
                → <wiki>/active/my-slug/discussion.md"""

def write_review_file(
    reviews_dir: Path, review_type: str, round_num: int,
    content: str, scope: str | None = None
) -> Path:
    """Build canonical filename, create dirs, write, return path."""

def find_active_slug(mill_dir: Path) -> str:
    """Find the single .<slug>.slug.md in .millhouse/. Zero or >1 → raise."""

def load_task_title(mill_dir: Path, slug: str) -> str:
    """Read `task_title` from .<slug>.slug.md's YAML frontmatter.
       Fall back to the slug itself if the field is missing."""

def read_constraints_md(project_root: Path) -> str:
    """Read CONSTRAINTS.md from the project root. Return empty string if absent."""

class ReviewError(Exception):
    """Raised by the backend on config / slug / reviewer / round errors.
       Caught by the API, which prints str(exc) to stderr and exits 1."""
```

### `LLMError` — in the LLM-provider module

```python
# _llm_claude.py
class LLMError(Exception):
    """Raised on timeout, auth failure, or non-zero exit from claude CLI."""
```

`LLMError` lives with the LLM-provider (not in `_review_common`) because the
LLM-provider is the layer that raises it. Backends `import LLMError from _llm_claude`
and catch it at the per-sub-review boundary to populate
`{verdict: "ERROR", file: null, error: "<msg>"}` in the ReviewResult.

(When a second LLM-provider lands, `LLMError` is lifted into a shared
`_llm_common.py` or similar. For v2 with only Claude, one file is enough.)

## CLI contract

**Input:** null arguments. The script finds everything itself.

**Stdout:** single JSON `ReviewResult` line on success. On failure: **empty**.

**Stderr:** progress/logging. On failure: human-readable error message.

**Exit code:** `0` on success, `1` on failure.

### ReviewResult shape (stdout on success)

```json
{
  "type": "plan",
  "round": 2,
  "verdict": "REQUEST_CHANGES",
  "reviews": [
    {"scope": "batch-01-setup",  "verdict": "APPROVE",         "file": "<abs>"},
    {"scope": "batch-02-core",   "verdict": "REQUEST_CHANGES", "file": "<abs>"},
    {"scope": "holistic",        "verdict": "APPROVE",         "file": "<abs>"}
  ]
}
```

- `reviews` is always a list. One entry for discussion/code; N+1 for plan.
- Aggregate top-level `verdict` is worst-case across sub-reviews:
  `REQUEST_CHANGES` > `APPROVE`. An `ERROR` sub-verdict escalates to
  `REQUEST_CHANGES` at the aggregate (never `ERROR` at top level).
- `round` is determined by the script from filesystem state.

### Partial vs total failure

| Situation | Behaviour |
|---|---|
| All sub-reviews succeed | exit 0, full JSON on stdout |
| ≥1 sub-review succeeds AND ≥1 sub-review fails | exit 0, JSON with the failed entries as `{verdict: "ERROR", file: null, error: "<msg>"}`; aggregate verdict = `REQUEST_CHANGES` |
| Zero sub-reviews succeed (all fail) | exit 1, stdout empty, stderr lists errors |

### Verdict vocabulary

`APPROVE` / `REQUEST_CHANGES` unified across all three review types. `ERROR`
only appears inside `reviews[]` entries, never at the aggregate.

### Failure modes on stderr

| Failure | Exit | Stdout | Stderr |
|---|---|---|---|
| Success | 0 | JSON ReviewResult | progress |
| No active slug | 1 | empty | `"No active task: no .slug.md file found in .millhouse/"` |
| Multiple active slugs | 1 | empty | `"Multiple .slug.md files; expected exactly one"` + list |
| Unknown reviewer name | 1 | empty | `"Unknown reviewer 'X': no _reviewer_X.py found"` |
| Incompatible reviewer/type | 1 | empty | `"No <mode> template exists for <type> review"` |
| Round exceeds max | 1 | empty | `"Round N exceeds max M for <type> review"` |
| All sub-reviews failed | 1 | empty | `"All sub-reviews failed: <list of errors>"` |

## Config contract

Lives in `wiki/config.yaml` (shared) with optional overrides in
`.millhouse/config.local.yaml`. This **supersedes** the `pipeline:` section
in `ref-formats.md`.

```yaml
paths:
  discussion_file: active/<SLUG>/discussion.md
  plan_dir:        active/<SLUG>/plan/
  reviews_dir:     active/<SLUG>/reviews/
  # paths are relative to wiki root.
  # <SLUG> (uppercase) is substituted by the script using _render.render().

review:
  discussion:
    rounds: 2
    holistic: sonnetmax_tool    # reviewer name; MODE must be "tool-use"

  plan:
    rounds: 3
    batch: sonnetmax            # reviewer name; MODE must be "bulk"
    holistic: sonnetmax         # reviewer name; MODE must be "bulk"

  code:
    rounds: 3
    reviewer: sonnetmax         # reviewer name; MODE must be "bulk"
                                # (renamed from 'batch' — code review is not batched)
    style: single               # or 'multi' — selects template variant
```

- **`<SLUG>`** (uppercase): placeholder in path strings, substituted by
  `resolve_path()` using plain `str.replace("<SLUG>", slug)`. **Not** via
  `_render.render()` (that reads files; config paths are strings). Uppercase
  is for internal consistency with the rest of the token convention.
- **`rounds: N`** is the max. Scripts refuse to start round > N.
- **`~`** (YAML null) means skip that call entirely.
- **`style: single | multi`** on `code` selects template; no auto-detection.
- **Reviewer names** resolve to `_reviewer_<name>.py`. Unknown → error.

## Contracts between layers

### API → Review backend

```python
# mill-review-plan.py (representative)
project_root = Path.cwd()                                   # or derived from script location
mill_dir     = project_root / ".millhouse"
wiki_root    = (mill_dir / "wiki").resolve()                # through the wiki junction
cfg          = load_config(wiki_root, mill_dir)
slug         = _review_common.find_active_slug(mill_dir)
try:
    result = _review_plan.run(cfg, slug, mill_dir, wiki_root, project_root)
    print(json.dumps(result.to_dict()))
    sys.exit(0)
except ReviewError as exc:
    print(str(exc), file=sys.stderr)
    sys.exit(1)
```

Each backend's `run()` signature is:
```python
def run(cfg: dict, slug: str, mill_dir: Path, wiki_root: Path, project_root: Path) -> ReviewResult:
    ...
```

`mill_dir` and `project_root` feed `load_task_title()` and `read_constraints_md()`.
`wiki_root` feeds `resolve_path()`.

### Review backend → Reviewer

```python
# Each reviewer implements
MODE: str          # module-level constant: "bulk" or "tool-use"
def run(prompt_text: str) -> str: ...    # returns raw LLM text (post-parsing of stream-json)
```

The reviewer receives **already-rendered `prompt_text`**. No template logic
lives in the reviewer. The reviewer's sole job is to pick the right
`_llm_claude.run_*` function based on its declared `MODE`.

### Reviewer → LLM-provider

```python
# _llm_claude.py
def run_bulk(prompt_text: str, *, model: str, effort: str | None = None) -> str:
    """Subprocess `claude -p` with no tool access.
       On timeout/auth/non-zero exit: raise LLMError."""
    # claude -p --allowedTools "" --model <model> [--effort <effort>]
    #   stdin ← prompt_text
    #   parse stream-json, return final text

def run_tool_use(prompt_text: str, *, model: str, effort: str | None = None) -> str:
    """Subprocess `claude -p` with Read/Grep/Write tools enabled.
       On timeout/auth/non-zero exit: raise LLMError."""
    # claude -p --allowedTools Read,Grep,Write --model <model> [--effort <effort>]
    #   stdin ← prompt_text
    #   parse stream-json, return final text
```

### Error propagation

`_llm_claude.run_*` raises `LLMError` on timeout / auth failure / non-zero
exit. The reviewer does not catch it — it propagates through. The backend
catches `LLMError` at the per-sub-review boundary and populates
`{verdict: "ERROR", file: null, error: "<msg>"}` in the corresponding
`reviews[]` entry.

### Who writes the review file

**Always the backend**, even in tool-use mode. Templates instruct the LLM to
*return* the review as text (via normal response), not to use the Write tool
on the review output file. The backend calls `_review_common.write_review_file()`
after the reviewer returns. This keeps the 4-layer contract clean: the
reviewer returns raw text, the backend owns file I/O.

(In tool-use mode, the LLM may still use Read/Grep to navigate. It should
not use Write on the review output path — the template says so explicitly.)

## Templates

Located under `plugins/mill/templates/`. Rendered via existing `_render.py`
(uppercase-identifier token grammar, `<TOKEN>`).

v2 ships:

```
templates/
  review-discussion.md        # tool-use — reviewer reads files itself
  review-plan-batch.md        # bulk — per-batch
  review-plan-holistic.md     # bulk — whole plan
  review-code-single.md       # bulk — single file in diff
  review-code-multi.md        # bulk — multiple files in diff
  review-output.schema.md     # canonical output schema (shared)
```

Placeholder tokens (uppercase):
- `<TASK_TITLE>`, `<ARTEFACT_PATH>`, `<ARTEFACT_CONTENT>`, `<CONSTRAINTS>`,
  `<REVIEW_OUTPUT_PATH>`, `<ROUND>`, `<REVIEWER_MODEL>`,
  `<DIFF>` (code only), `<PLAN_CONTENT>` (code only), `<BATCH_NAME>` (plan-batch only).

Each template uses only the tokens relevant to its review type. A template that
references a token not passed to `render_prompt()` raises `KeyError` (see
`_render.py` semantics) — this is a hard error, not a silent fallthrough.

`_review_common.render_prompt(template_name, **kwargs)` **auto-uppercases**
the keyword-argument keys (`artefact_path="..."` → `ARTEFACT_PATH`) so callers
can use idiomatic Python kwarg style.

Templates are drafted by Claude from v1's `millpy/doc/prompts/*.md` (which
"funka ganske bra"). Henrik reviews each draft before it lands.

## Round discovery

The script scans `reviews_dir` and returns `max(N) + 1` (or 1 if empty).

### Canonical filenames

- Discussion / code / plan-holistic: `<ts>-<type>-review-r<N>.md`
  - `20260418-001200-discussion-review-r1.md`
  - `20260418-143300-code-review-r2.md`
  - `20260418-143300-plan-review-r1.md` (holistic)
- Plan per-batch: `<ts>-plan-review-<batch-name>-r<N>.md`
  - `20260418-143300-plan-review-01-setup-r1.md`

`<ts>` = `YYYYMMDD-HHMMSS` UTC.

### Regex patterns

```python
RE_SIMPLE = re.compile(
    r"^\d{8}-\d{6}-(?P<type>discussion|code|plan)-review-r(?P<n>\d+)\.md$"
)
RE_BATCH = re.compile(
    r"^\d{8}-\d{6}-plan-review-(?P<batch>[a-z0-9-]+)-r(?P<n>\d+)\.md$"
)
```

**Match ordering (mandatory):** `RE_SIMPLE` is checked first. A filename that
matches `RE_SIMPLE` is **excluded** from `RE_BATCH` matching. This prevents
`…-plan-review-r1.md` (holistic) from being mis-identified as a batch with
name `r` and number `1`.

For plan: highest `N` across all simple + batch matches determines next round.
All reviews in a given round share the same `N`.

`RE_SIMPLE` and `RE_BATCH` are module-level constants defined at the top of
`_review_common.py` (not duplicated in each backend, not inlined inside
`discover_round`).

**Batch-filename constraint:** Batch files in `plan/` must be named
`NN-<name>.md` where `<name>` matches `[a-z0-9-]+` (lowercase alphanumerics
plus hyphens). This ensures `batch.stem` round-trips through `RE_BATCH`.
The constraint is stated here; `mill-plan` (Layer 04) will enforce it when
writing plans. For Layer 02 integration tests, fixtures must follow this rule.

### Round cap

After discovery, compare against `cfg.review.<type>.rounds`. If greater,
exit 1.

## Parallelism

Per-batch plan reviews run in parallel via `concurrent.futures.ThreadPoolExecutor`.

**Worker pool size = `max(1, len(batch_files))`**. In practice 2–5 batches per
plan. If a plan has 50 batches one day, we revisit. **If `batch_files` is empty
(a plan with only `00-overview.md`), the parallel section is skipped entirely
and the backend proceeds straight to the holistic review.** This avoids the
`ThreadPoolExecutor(max_workers=0)` crash.

## Path resolution

Scripts do NOT rely on `.millhouse/.active` (Henrik's personal shortcut).

Scripts DO rely on `.millhouse/wiki` junction (Layer 01 contract).

Active slug discovered by scanning `.millhouse/` for files matching
`.<slug>.slug.md`. Exactly one must exist.

Full review output path:
```
<project>/.millhouse/wiki/active/<slug>/reviews/<ts>-<type>-review[-<batch>]-r<N>.md
```

Resolved via `resolve_path()` on the config path templates (plain `str.replace`
on `<SLUG>`) — see the Config contract and the `_review_common.py` helper
list for the exact signature.

---

## Task flows (concrete)

### 1) Discussion review

```
Orchestrator: python .millhouse/mill-review-discussion.py
    │
mill-review-discussion.py  [API]
  ├─ cfg  = load_config()
  ├─ slug = _review_common.find_active_slug()
  └─ result = _review_discussion.run(cfg, slug)
    │
_review_discussion.run(cfg, slug, mill_dir, wiki_root, project_root)  [BACKEND]
  ├─ discussion_path  = resolve_path(cfg.paths.discussion_file, slug, wiki_root)
  ├─ reviews_dir      = resolve_path(cfg.paths.reviews_dir, slug, wiki_root)
  ├─ round_n          = discover_round(reviews_dir, "discussion")
  ├─ check round_n <= cfg.review.discussion.rounds
  ├─ reviewer_name    = cfg.review.discussion.holistic          # → "sonnetmax_tool"
  ├─ reviewer         = importlib.import_module("_reviewer_" + reviewer_name)
  ├─ check reviewer.MODE == "tool-use"                          (required for discussion)
  │
  ├─ # Render prompt (tool-use variant):
  ├─ prompt_text = render_prompt(
  │     "review-discussion",
  │     task_title        = load_task_title(mill_dir, slug),
  │     artefact_path     = discussion_path,
  │     constraints       = read_constraints_md(),
  │     review_output_path= <derived>,
  │     round             = round_n,
  │     reviewer_model    = reviewer_name,
  │   )
  │
  ├─ try: raw = reviewer.run(prompt_text)         # may raise LLMError
  ├─ verdict = parse_verdict(raw)
  ├─ path    = write_review_file(reviews_dir, "discussion", round_n, raw)
  └─ return ReviewResult(
       type="discussion", round=round_n, verdict=verdict,
       reviews=[{scope:"holistic", verdict, file: path}]
     )
    │
_reviewer_sonnetmax_tool.run(prompt_text)  [REVIEWER]
  └─ return _llm_claude.run_tool_use(prompt_text, model="claude-sonnet-4-5", effort="max")
    │
_llm_claude.run_tool_use(prompt_text, model, effort)  [LLM-PROVIDER]
  ├─ spawn: claude -p --allowedTools Read,Grep,Write --model <model> (+ effort)
  ├─ stdin ← prompt_text
  ├─ parse stream-json
  └─ return final_text
```

### 2) Plan review (with batches)

```
_review_plan.run(cfg, slug, mill_dir, wiki_root, project_root)  [BACKEND]
  ├─ plan_dir     = resolve_path(cfg.paths.plan_dir, slug, wiki_root)
  ├─ overview     = plan_dir / "00-overview.md"
  ├─ batch_files  = sorted(plan_dir.glob("??-*.md"))    # excluding 00-overview
  ├─ reviews_dir  = resolve_path(cfg.paths.reviews_dir, slug, wiki_root)
  ├─ round_n      = discover_round(reviews_dir, "plan")
  │
  ├─ # Per-batch in parallel:
  ├─ batch_reviewer = importlib.import_module("_reviewer_" + cfg.review.plan.batch)
  ├─ check batch_reviewer.MODE == "bulk"
  │
  ├─ if batch_files:
  │   with ThreadPoolExecutor(max_workers=len(batch_files)):
  │     for each batch in batch_files:
  │         reads_files    = parse Reads:/Modifies: from batch (deduped, existing)
  │         bulked         = bulk_files([overview, batch, *reads_files])
  │         prompt_text    = render_prompt(
  │             "review-plan-batch",
  │             task_title       = load_task_title(mill_dir, slug),
  │             batch_name       = batch.stem,
  │             artefact_content = bulked,
  │             constraints      = read_constraints_md(),
  │             review_output_path = <derived>,
  │             round            = round_n,
  │             reviewer_model   = cfg.review.plan.batch,
  │         )
  │         try: raw = batch_reviewer.run(prompt_text)
  │         verdict = parse_verdict(raw)
  │         path    = write_review_file(reviews_dir, "plan", round_n, raw, scope=batch.stem)
  │
  ├─ # Holistic (if not skipped):
  ├─ if cfg.review.plan.holistic is not None:
  │     holistic_reviewer = importlib.import_module("_reviewer_" + cfg.review.plan.holistic)
  │     check holistic_reviewer.MODE == "bulk"
  │     all_reads       = union of Reads:/Modifies: across all batches
  │     bulked_all      = bulk_files([overview, *batch_files, *all_reads])
  │     prompt_text     = render_prompt(
  │         "review-plan-holistic",
  │         artefact_content = bulked_all,
  │         ...)
  │     raw             = holistic_reviewer.run(prompt_text)
  │     write scope="holistic"
  │
  └─ return ReviewResult with per-batch + holistic entries
    │
_reviewer_sonnetmax.run(prompt_text)  [REVIEWER — bulk]
  └─ return _llm_claude.run_bulk(prompt_text, model="claude-sonnet-4-5", effort="max")
    │
_llm_claude.run_bulk(prompt_text, model, effort)  [LLM-PROVIDER]
  ├─ spawn: claude -p --allowedTools "" --model <model> (+ effort)
  ├─ stdin ← prompt_text
  └─ return final_text
```

### 3) Code review

```
_review_code.run(cfg, slug, mill_dir, wiki_root, project_root)  [BACKEND]
  ├─ reviews_dir     = resolve_path(cfg.paths.reviews_dir, slug, wiki_root)
  ├─ round_n         = discover_round(reviews_dir, "code")
  ├─ check round_n <= cfg.review.code.rounds
  ├─ plan_dir        = resolve_path(cfg.paths.plan_dir, slug, wiki_root)
  ├─ plan_files      = sorted(plan_dir.glob("*.md"))          # whole plan dir bulked
  ├─ base_sha        = `git merge-base main HEAD`             # base of task branch
  ├─ diff            = `git diff <base_sha>..HEAD`
  ├─ touched_files   = parse paths from diff
  ├─ style           = cfg.review.code.style                  # → "single" | "multi"
  ├─ reviewer        = importlib.import_module("_reviewer_" + cfg.review.code.reviewer)
  ├─ check reviewer.MODE == "bulk"
  │
  ├─ template_name = "review-code-" + style
  ├─ bulked        = bulk_files([*plan_files, *touched_files])
  ├─ plan_content  = "\n\n".join(f.read_text() for f in plan_files)
  ├─ prompt_text   = render_prompt(
  │     template_name,
  │     task_title       = load_task_title(mill_dir, slug),
  │     diff             = diff,
  │     plan_content     = plan_content,
  │     artefact_content = bulked,
  │     constraints      = read_constraints_md(),
  │     review_output_path = <derived>,
  │     round            = round_n,
  │     reviewer_model   = cfg.review.code.reviewer,
  │   )
  ├─ raw = reviewer.run(prompt_text)
  ├─ write file scope="holistic"
  └─ return ReviewResult
```

---

## Scope for v2 Layer 02

**Implemented:**
- 3 API scripts (`mill-review-discussion.py`, `-plan.py`, `-code.py`)
- 3 review backends (`_review_discussion.py`, `-plan.py`, `-code.py`) + `_review_common.py`
- 2 reviewers: `_reviewer_sonnetmax.py` (MODE=bulk), `_reviewer_sonnetmax_tool.py` (MODE=tool-use)
- 1 LLM-provider: `_llm_claude.py` with `run_bulk()` and `run_tool_use()`
- 6 template files (5 prompts + 1 schema)
- `review:` section in `wiki/config.yaml`
- Integration tests (one per review type minimum)

### Integration test fixtures (per-test minimum)

Each integration test must provide:
- `.millhouse/.<slug>.slug.md` pre-seeded with a test slug AND `task_title` in frontmatter
- `.millhouse/wiki/` junction pointing to a test wiki directory
- Test wiki `config.yaml` with the `paths:` and `review:` sections
- `active/<slug>/` populated with a sample artefact
  (discussion.md / plan/ / or a test diff fixture)
- A real Claude CLI invocation — no stubs (we want to shake out integration
  bugs early)

**Local-dev only for v2.** These tests are not run in CI. CI integration for
real Claude CLI calls (auth, rate-limits, cost control) is deferred to
post-v2.0. Running the suite requires `claude` in PATH and a valid subscription.

### Integration test assertions (minimum per test)

- Exit code 0
- Stdout is valid JSON with `type`, `round`, `verdict`, `reviews` fields
- `verdict` is `APPROVE` or `REQUEST_CHANGES` (never `ERROR`)
- Each `reviews[]` entry has a `file` that exists on disk
- Each review file has YAML frontmatter with `verdict:` matching its entry

**Deferred (post-v2.0):**
- Gemini / Ollama LLM-providers
- Cluster / hybrid reviewers
- Ensemble review as a separate wrapper script
- Finer-grained error exit codes

## Decisions log

1. Flat script layout. No submodules under `scripts/`.
2. 4-layer architecture: API → Review backend → Reviewer → LLM-provider.
3. Three CLI scripts, not one with `--type`.
4. CLI takes no arguments. Scripts find everything from config + filesystem.
5. Backend owns templates, bulking, rendering, file-writing, round discovery.
6. Reviewers are named; one file per reviewer. `MODE` declared as constant.
7. Two modes: `bulk` and `tool-use`. Each reviewer is one or the other.
8. LLM-provider exposes two functions: `run_bulk` and `run_tool_use`. No
   mode parameter threads through the call chain.
9. Mode by review type (v2 defaults): discussion = tool-use, plan = bulk,
   code = bulk. Configurable via reviewer name.
10. `reviews` in ReviewResult is always a list.
11. Round auto-discovered from filesystem; `rounds: N` is max.
12. Parallelism via ThreadPoolExecutor from day one. No worker cap.
13. Paths in config, relative to wiki root, `<SLUG>` uppercase, substituted
    via `_render.render()`.
14. Verdicts: `APPROVE` / `REQUEST_CHANGES` unified. `ERROR` only inside
    `reviews[]` entries, never at aggregate.
15. Cluster / hybrid reviewers are post-v2.0.
16. Templates drafted from v1's `doc/prompts/*.md`, reviewed by Henrik per file.
17. Active task identified via `.<slug>.slug.md`, not the `.active` junction.
18. `_review_common.py` exists (~6 functions + 1 exception class).
19. Partial failure: failed sub-review entry gets `verdict: ERROR`;
    aggregate = `REQUEST_CHANGES`; exit 0. All failed → exit 1, empty stdout.
20. Canonical review filenames: `<ts>-<type>-review-r<N>.md` for
    discussion/code/plan-holistic; `<ts>-plan-review-<batch>-r<N>.md` for
    plan per-batch. Match `RE_SIMPLE` first, exclude from `RE_BATCH`.
21. Failure semantics: exit 1, empty stdout, human-readable stderr.
    Orchestrator reads stdout only on exit 0.
22. This discussion supersedes the `pipeline:` section in `ref-formats.md`
    (incl. format inventory count), the "Provider plugin pattern" in
    `00-overview.md`, and the CLI parts of `layer-02-review.md`.
23. `render_prompt()` auto-uppercases keyword-argument keys.
24. The backend always writes the review file. Templates instruct the LLM
    to **return** the review text, not to use the Write tool for it.
25. `_llm_claude.run_*` raises `LLMError` on timeout/auth/non-zero exit.
    Backend catches at the per-sub-review boundary.
26. `code.style: single | multi` (renamed from `code.mode` to avoid overloading
    the word "mode", which now refers exclusively to reviewer MODE).
27. v2 implements Claude only. `_llm_claude.py` uses `claude -p` CLI subprocess
    with stream-json output.
28. `ReviewError` lives in `_review_common.py`. `LLMError` lives in `_llm_claude.py`.
    Backend imports `LLMError` from `_llm_claude.py`. Correct layer direction.
29. `resolve_path(path_tmpl, slug, wiki_root) -> Path` uses plain `str.replace`
    for `<SLUG>` substitution. It does NOT use `_render.render()` (that reads
    files; config paths are strings).
30. Task title comes from `.<slug>.slug.md`'s YAML frontmatter via a new
    `task_title` field (added to the slug.md format — see supersession notes).
    Loaded by `load_task_title()` in `_review_common.py`. Falls back to slug.
31. Code review dropped `plan_start_hash`. Baseline diff: `git merge-base main HEAD`.
    `git diff <base>..HEAD` is the code-review scope.
32. `code.batch` renamed to `code.reviewer` — code review is not batched.
33. `<RELEVANT_FILES>` token removed — unused; bulking goes into `<ARTEFACT_CONTENT>`.
34. Integration tests are local-dev-only for v2. CI integration post-v2.0.
35. Empty batch files → skip parallel section, go straight to holistic. No crash.

## Open questions

- Whether `.millhouse/scratch/` holds materialized prompt files for debugging.
  Leaning toward yes for debuggability. Decide during implementation.
- Exact template content — drafted during implementation, each reviewed by
  Henrik before merging.

## Process notes

This file is the source of truth for Layer 02 design until implementation
begins. Decisions that invalidate sections above should be updated here, not
buried in commits.

`specs/layer-02-review.md` and `specs/roadmap/M2-review.md` will be rewritten
to match once implementation starts. Until then, this file wins on conflict.
Same applies to the superseded sections of `ref-formats.md` and `00-overview.md`.
