# Discussion Review — Layer 02 (r3)

```yaml
reviewer: claude-sonnet-4-6 (via Agent tool)
reviewed_file: specs/active/layer-02/discussion.md
date: 2026-04-20
round: 3
```

---

## Findings

### [GAP] `ReviewError` is caught by the API but never defined or raised

**Section:** "Contracts between layers" → "API → Review backend"

**Issue:** The API pseudocode catches `ReviewError`:

```python
except ReviewError as exc:
    print(exc.message, file=sys.stderr)
    sys.exit(1)
```

`ReviewError` does not appear in the `_review_common.py` listing, which defines only `LLMError`. No module is named as the home for `ReviewError`. A plan writer cannot write the API scripts without knowing where to import it from, what fields it has (`.message` is used — is this a custom attribute or `str(exc)`?), and which backend conditions raise it vs. let other exceptions propagate.

**Suggested fix:** Either add `class ReviewError(Exception): ...` to `_review_common.py` (the natural home alongside `LLMError`), or explicitly state it is a module alias for `LLMError`. Document the exact attribute: `.message` implies a named attribute, but standard Python exceptions use `str(exc)`. Enumerate which error conditions the backend raises `ReviewError` for (vs. letting `LLMError` propagate up directly).

---

### [GAP] `<SLUG>` substitution in config path strings — mechanism unspecified

**Section:** "Config contract" → `<SLUG>` note; "Path resolution"

**Issue:** The config stores paths like `active/<SLUG>/discussion.md`. The discussion states these are "substituted by `_render.render()`". However, `_render.render(template_path: Path, values: dict)` takes a **file path** as its first argument — it reads a file from disk and substitutes tokens. A bare string from a YAML value is not a file. There is no helper defined anywhere for string-level token substitution.

The task flows call `resolve_path(cfg.paths.discussion_file, slug)` without defining `resolve_path`. Is this the missing bridge? If so, `resolve_path` must be listed as a function in `_review_common.py` (it is not). If `_render.render()` is used directly, the caller must write the config string to a temp file first — that is cumbersome and not mentioned.

**Suggested fix:** Add `resolve_path(path_template: str, slug: str) -> Path` to `_review_common.py`'s function list. Define it: does it call `_render.render()` on a temp file, or does it do its own inline replacement (e.g., `path_template.replace("<SLUG>", slug)`)? The latter is simpler and doesn't require file I/O. Either way, the function must appear in the spec as a named helper.

---

### [GAP] `LLMError` ownership — cross-module import direction is inverted

**Section:** "What `_review_common.py` contains"; "Error propagation"

**Issue:** `class LLMError` is defined in `_review_common.py`. But `_llm_claude.py` raises it (`_llm_claude.run_*` raises `LLMError` on failure). This means `_llm_claude.py` must import `LLMError` from `_review_common.py`. However, `_review_common.py` is a **review-domain** module; `_llm_claude.py` is an **LLM-provider** module. Having the LLM provider import from the review common module creates an upward dependency from the lowest layer back into the mid-layer.

A reviewer that wraps a non-Claude LLM provider would also need to raise `LLMError` from `_review_common.py`, meaning every LLM provider must depend on the review-common module — which breaks the stated goal of each layer being independently swappable.

**Suggested fix:** Move `LLMError` to `_llm_claude.py` (or a future `_llm_common.py`), and have the backend catch any `LLMError` by importing it from the LLM provider. Alternatively, define `LLMError` in a standalone `_exceptions.py`. Whichever choice is made, the import direction must be stated explicitly.

---

### [GAP] Empty `batch_files` causes `ThreadPoolExecutor(max_workers=0)` crash

**Section:** "Parallelism"; "Task flows" → Plan review

**Issue:** The plan review task flow sets `max_workers=len(batch_files)`. If a plan has no batch files (only `00-overview.md` — a legitimate edge case for a very small plan, or a plan in early state), then `max_workers=0`. In Python's `concurrent.futures.ThreadPoolExecutor`, `max_workers=0` raises `ValueError: max_workers must be greater than 0`. The script would crash with an unhandled exception rather than gracefully completing with zero per-batch entries and proceeding to the holistic review.

**Suggested fix:** Add a guard: `if not batch_files: skip the parallel section and go directly to holistic`. Or use `max_workers=max(1, len(batch_files))`. Whichever approach is chosen, state it explicitly in the spec.

---

### [GAP] `plan_start_hash` in plan frontmatter — not defined in `ref-formats.md`

**Section:** "Task flows" → Code review

**Issue:** The code review flow reads `plan_start_hash` from plan frontmatter:

```
plan_start_hash = read from plan frontmatter
```

The canonical `plan.md` format in `ref-formats.md` shows only `task`, `created`, and `approved` in the YAML frontmatter. `plan_start_hash` does not appear there. A plan writer implementing `_review_code.py` cannot extract a field that the plan format doesn't specify as existing. It is also unclear when/who writes this field: is it written by `mill-plan` at plan creation time? By `mill-start` when implementation begins? If it doesn't exist, what is the fallback?

**Suggested fix:** Either add `plan_start_hash: <git-sha>` to the `plan.md` format in `ref-formats.md` (and note when it is written and by whom), or specify it differently (e.g., derive it from a `.millhouse/` state file). A plan writer needs to know the exact key name, the field owner, and the failure behaviour when absent.

---

### [GAP] Mode compatibility check — location and error message for mismatched types partially underspecified

**Section:** "Mode mechanics"; "Config contract"

**Issue:** The discussion says misconfigured reviewer/type combinations produce a "clear error" and gives an example message. The task-flow diagrams show `check reviewer.MODE == "tool-use"` (for discussion) and `check reviewer.MODE == "bulk"` (for plan, code). However:

1. Where exactly does this check live? The task flows show it in the backend, but neither `_review_common.py`'s function list nor the backend files list a shared `check_mode_compatibility()` helper. If the check is inlined in each backend, the error message format may drift.
2. The config comment says `"holistic: sonnetmax_tool   # reviewer name; MODE must be 'tool-use'"` but there is no stated mechanism that validates this at config-load time vs. only at call time (at the point of `import("_reviewer_" + name)`). If the check happens lazily at import time, a misconfigured reviewer won't be caught until the LLM call is about to be made — potentially after writing partial results.

**Suggested fix:** Specify whether mode compatibility checking happens eagerly (at backend startup, before any LLM calls) or lazily (just before calling the reviewer). Ideally specify a shared helper in `_review_common.py` or document the inline check pattern so all three backends emit the same error message format.

---

### [GAP] Reviews directory doesn't exist on round 1 — `discover_round` behaviour undefined

**Section:** "Round discovery"

**Issue:** On the very first invocation (round 1), `reviews_dir` does not exist yet (it is created by `write_review_file`). The `discover_round(reviews_dir, "discussion")` function scans `reviews_dir`. If the directory doesn't exist, `os.scandir()` / `Path.iterdir()` raises `FileNotFoundError`. The function's docstring says "Scan reviews_dir, find highest -r<N>.md for the type, return N+1" — it does not address the nonexistent directory case.

**Suggested fix:** Add to `discover_round`'s specification: "If `reviews_dir` does not exist, return 1." A single sentence in the docstring or the spec text is sufficient.

---

### [GAP] `cfg.task.title` — config key undefined

**Section:** "Task flows" (all three); "Config contract"

**Issue:** All three task-flow `render_prompt` calls pass `task_title = cfg.task.title`. The config structure shown in the discussion has `paths:` and `review:` top-level keys — there is no `task:` section. `cfg.task.title` would raise `AttributeError`. The task title must come from somewhere (likely the slug file or `status.md`), but the source is not specified.

**Suggested fix:** Either add a `task:` section to the config schema (e.g., `task: { title: "<str>" }`), or specify that `cfg.task.title` is populated at load time by reading the active slug file or `status.md`. Name the loader function and where it lives (likely `_review_common.py`).

---

### [NOTE] `read_constraints_md()` called but not defined as a `_review_common.py` function

**Section:** "Task flows" (all three)

**Issue:** All three task flows call `read_constraints_md()` without arguments. This function is not listed in `_review_common.py`'s function inventory. It presumably reads a project-level `CONSTRAINTS.md` file (the v1 pattern), but the file's location is not stated, nor is there a definition of what happens if the file does not exist (return empty string? raise?). The `<CONSTRAINTS>` token appears in the template token list, so this is a required input.

**Suggested fix:** Add `read_constraints_md(wiki_dir: Path) -> str` (or equivalent signature) to `_review_common.py`'s function listing, and specify the lookup path and the absent-file behaviour.

---

### [NOTE] `<RELEVANT_FILES>` token listed but unused in task flows

**Section:** "Templates" → token list; "Task flows"

**Issue:** The template token list includes `<RELEVANT_FILES>`. None of the three task-flow `render_prompt` calls pass a `relevant_files` kwarg. For the plan review, `artefact_content` carries the bulked content (which already contains the relevant files merged in). For discussion (tool-use), there are no pre-bulked files at all. `<RELEVANT_FILES>` either belongs to a template that doesn't appear in the flows, or it is an unused token that will trigger `_render.render()`'s "unresolved tokens" hard error if the template references it.

**Suggested fix:** Either (a) remove `<RELEVANT_FILES>` from the token list if it is vestigial, or (b) add it to the appropriate `render_prompt` call with a definition of what it contains (e.g., the list of file paths parsed from `Reads:`/`Modifies:` headers, separate from `<ARTEFACT_CONTENT>` which is their contents). Clarify which templates use which tokens.

---

### [NOTE] Integration test practicality — "real Claude CLI, no stubs" in CI is unresolved

**Section:** "Scope for v2 Layer 02" → Integration test fixtures

**Issue:** The integration test requirement states "real Claude CLI invocation — no stubs (we want to shake out integration bugs early)." This is reasonable for local dev but raises a practical question for any CI/CD pipeline: running real Claude CLI in CI requires auth credentials and incurs API cost and non-deterministic latency. The discussion doesn't address whether CI will run these tests or skip them, how credentials will be provided, or what the expected test runtime is. This is deferred but touches on the implementability of the CI task cards.

**Suggested fix:** A single sentence clarifying intent would suffice: e.g., "Integration tests are local-dev only; CI runs only a dry-run flag check. CI integration is post-v2.0." If CI is intended to run them, note the auth mechanism (env var, secret store).

---

### [NOTE] `RE_BATCH` could match plan-holistic filename despite RE_SIMPLE exclusion — verify regex priority is enforced

**Section:** "Round discovery" → Regex patterns

**Issue:** The discussion correctly states RE_SIMPLE is checked first and matching files are excluded from RE_BATCH. However, the `discover_round` docstring says "RE_SIMPLE is checked first; files matching it are excluded from RE_BATCH" but this ordering is a **caller responsibility**, not a `re.compile()` property. The spec doesn't show the implementation pseudocode clearly enough to verify the exclusion logic will be implemented correctly. A plan writer might implement RE_SIMPLE and RE_BATCH as two independent passes over the directory listing without the exclusion guard.

**Suggested fix:** Add a one-line pseudocode note to `discover_round`'s description, e.g.: "For each file: try RE_SIMPLE; if it matches, record and skip RE_BATCH check; otherwise try RE_BATCH." This is minimal but removes the ambiguity.

---

### [NOTE] `batch.stem` used as `scope` — may produce wrong canonical filename

**Section:** "Task flows" → Plan review; "Round discovery" → Canonical filenames

**Issue:** The plan batch task flow passes `scope=batch.stem` to `write_review_file`. `Path("01-setup.md").stem` is `"01-setup"`. The canonical batch filename pattern is `<ts>-plan-review-<batch-name>-r<N>.md`. `RE_BATCH` expects `(?P<batch>[a-z0-9-]+)`. The stem `"01-setup"` contains only `[a-z0-9-]` characters, so it matches. However if a plan batch file were named `01_setup.md` (underscore), `batch.stem` = `"01_setup"` would fail the regex. The plan file naming convention isn't constrained in `ref-formats.md`. This is low-risk but worth confirming.

**Suggested fix:** Confirm in the plan format spec or here that batch filenames use only `[a-z0-9-]` (hyphens only, no underscores). Alternatively, normalise `batch.stem` in `write_review_file` before building the filename.

---

### [NOTE] `cfg.review.code.batch` — config key uses `batch` for single code review

**Section:** "Config contract" → `code:` section; "Task flows" → Code review

**Issue:** The code config block names the reviewer `batch: sonnetmax`, and the code review task flow reads `cfg.review.code.batch`. But code review is a single call (not batched) — there is only one reviewer, writing one file with `scope="holistic"`. Using `batch` as the config key for a single reviewer is potentially confusing and inconsistent with the `code.holistic: ~` key (which is skipped). Consider whether code review should use `holistic:` instead of `batch:`, or at least document why the `batch` key was chosen for a non-batched review type.

**Suggested fix:** Rename `code.batch` → `code.reviewer` (or `code.holistic`) for clarity, or add a comment in the config block explaining the choice. This is a naming issue, not a blocking gap, but it may cause confusion when a plan writer reads the config schema.

---

## Verdict

GAPS_FOUND

Six blocking gaps remain: `ReviewError` is undefined; `resolve_path` / `<SLUG>` string substitution has no specified mechanism; `LLMError` import direction violates layer independence; empty `batch_files` causes a Python crash; `plan_start_hash` is absent from the plan format; and `cfg.task.title` references a config key that doesn't exist in the specified config schema. The design is substantially more concrete than a naive starting point and the overall architecture is sound, but these six items each require a concrete decision before a plan writer can produce unambiguous implementation cards.
