# Layer 02 discussion — Review Round 4

```yaml
reviewer: claude-sonnet-4-6 (independent)
round: 4
date: 2026-04-20
verdict: GAPS_FOUND
```

---

## Scope reminder

Evaluated against the discussion's **own internal coherence and implementability
only**. No findings cite legacy spec files. All GAPs point to contradictions or
ambiguities within `discussion.md` itself, or to places where `_render.py`
behaviour contradicts the discussion's claims.

---

## Findings

### [GAP-1] `render_prompt()` wraps `_render.render()` incorrectly — the wrapper signature conflicts with the engine's interface

**Section:** "What `_review_common.py` contains" + "Templates" section + `_render.py`

**Issue:**
The discussion says:

> `render_prompt(template_name, **tokens)` — Wrapper around `_render.render()`.
> Auto-uppercases tokens' keys: `artefact_path='...'` becomes `ARTEFACT_PATH='...'`
> before substitution.

`_render.render(template_path, values)` takes a `Path` and a `dict[str, str]`.
`render_prompt` takes a **template name** (string), not a path. So `render_prompt`
must also resolve the template name to a file path before calling `_render.render()`.
That resolution step is nowhere defined in the discussion:

- Where does `render_prompt` know to look? `plugins/mill/templates/`? Relative to what?
- How is the scripts directory related to the templates directory at runtime?

The discussion never specifies the base path from which `render_prompt` resolves
`template_name → Path`. A plan writer cannot implement this function without
inventing that mapping.

**Suggested fix:** Add one sentence to `render_prompt`'s doc: "Resolves
`template_name` to `Path(SCRIPTS_DIR, '..', 'templates', template_name + '.md').resolve()`"
(or equivalent, referencing the known relative layout).

---

### [GAP-2] `_review_common.py` comment says `LLMError` is in common; body disagrees

**Section:** "What `_review_common.py` contains" (the inline comment on line listing)

**Issue:**
The function-listing block's trailing comment reads:

```
_review_common.py           # shared: round discovery, rendering,
                            #   bulking, verdict parsing, slug lookup,
                            #   file writing, LLMError exception
```

The immediately following section titled "`LLMError` — in the LLM-provider module"
and Decision 28 both say `LLMError` lives in `_llm_claude.py`, **not** in
`_review_common.py`. The comment in the file-listing table was not updated in r4
and now contradicts the rest of the document.

A reader who only reads the file-listing (common for quick orientation) will place
`LLMError` in the wrong module.

**Suggested fix:** Remove `, LLMError exception` from the trailing comment in the
file-listing block for `_review_common.py`.

---

### [GAP-3] `resolve_path` docstring says it uses `_render.render()`; Decision 29 says it does NOT

**Section:** "What `_review_common.py` contains" vs. Config contract + Decision 29

**Issue:**
The `resolve_path` docstring says:

> Simple string replace — does NOT use `_render.render()` (that reads files).

That is consistent with Decision 29. But the Config contract section says:

> **`<SLUG>`** (uppercase): placeholder in path strings, substituted by
> `_render.render()` with the active slug.

The Config contract text implies `_render.render()` is used for path substitution,
which directly contradicts both the `resolve_path` docstring and Decision 29. A
plan writer reading the Config contract section first will implement path
resolution using `_render.render()` (wrong), while one reading the `resolve_path`
docstring will correctly use plain `str.replace`.

**Suggested fix:** Amend the Config contract text: change "substituted by
`_render.render()`" to "substituted by `resolve_path()` via plain `str.replace`"
(or similar unambiguous wording).

---

### [GAP-4] Plan task flow: `ThreadPoolExecutor` called with `max_workers=len(batch_files)` — crashes when `batch_files` is empty

**Section:** Task flow 2 (Plan review), Parallelism section

**Issue:**
The Parallelism section correctly notes:

> If `batch_files` is empty (a plan with only `00-overview.md`), the parallel
> section is skipped entirely.

But the task flow code diagram shows:

```
with ThreadPoolExecutor(max_workers=len(batch_files)):
```

with **no guard** before it. The surrounding prose says to skip, but the code
flow never shows an `if batch_files:` check. `ThreadPoolExecutor(max_workers=0)`
raises `ValueError` in Python's stdlib. A plan writer following the task flow
diagram literally will produce crashing code.

**Suggested fix:** Add `if batch_files:` around the `ThreadPoolExecutor` block
in the task flow diagram, matching the guarantee stated in the Parallelism section.

---

### [GAP-5] Code review task flow references `plan_file` path as `plan_dir / "plan.md" (or similar)` — too vague to implement

**Section:** Task flow 3 (Code review)

**Issue:**
The code review flow contains:

```
plan_file = resolve_path(cfg.paths.plan_dir, slug) / "plan.md"  (or similar)
```

The parenthetical `(or similar)` means the plan writer must invent:
- whether the file is actually called `plan.md`,
- whether it is the overview (`00-overview.md`), or
- whether it is the whole plan directory bulked.

The config section defines `plan_dir` but not a `plan_file` path key, and the
discussion never defines a canonical name for the "whole plan" document used in
code review. This is the only task flow that uses an undefined path.

**Suggested fix:** Either (a) add a `plan_file` config key alongside `plan_dir`,
or (b) explicitly state that code review bulks the entire plan dir using
`bulk_files(sorted(plan_dir.glob("*.md")))`, matching plan review's behaviour.

---

### [GAP-6] `discover_round` docstring references `RE_SIMPLE` / `RE_BATCH` but those names only appear in the "Regex patterns" subsection — import/scope not specified

**Section:** "What `_review_common.py` contains" vs. Round discovery section

**Issue:**
`discover_round` is documented in `_review_common.py`'s listing. `RE_SIMPLE` and
`RE_BATCH` are defined in the "Round discovery → Regex patterns" section. Both
obviously live in `_review_common.py`, but the discussion never explicitly states
this. This is minor but creates a genuine ambiguity: a plan writer could place
the regex constants in a separate `_review_patterns.py` file or inline them only
inside `discover_round`. The current wording does not make the module placement
unambiguous.

**Suggested fix:** Add a one-liner to the regex block: "These module-level
constants are defined at the top of `_review_common.py`."

---

### [NOTE-1] `batch.stem` used as `scope` — may produce a filename with unexpected characters

**Section:** Task flow 2 (Plan review), `write_review_file` call

**Issue:**
The plan task flow passes `scope=batch.stem` (e.g. `"01-setup"`) to
`write_review_file`, which builds the canonical filename
`<ts>-plan-review-<batch-name>-r<N>.md`. `RE_BATCH` requires
`[a-z0-9-]+` for `<batch>`. If a batch file is named `01_Setup.md`
(underscore, uppercase), `batch.stem` would be `01_Setup`, which `RE_BATCH`
would not match on re-scan, breaking round discovery for that batch.

The discussion does not specify what characters are allowed in batch filenames,
nor does it sanitise `batch.stem` before use. This is not a hard blocker (Henrik
controls plan file naming) but the constraint should be stated.

**Suggested fix:** Add a note under the Round discovery section: "Batch files
must be named `[0-9]{2}-[a-z0-9-]+.md` to round-trip through `RE_BATCH`. The
backend asserts this on startup or documents the convention."

---

### [NOTE-2] `render_prompt` auto-uppercase: digits in key names

**Section:** "What `_review_common.py` contains", Config contract

**Issue:**
The discussion says `render_prompt` uppercases kwarg keys. `_render.py`'s token
regex is `<([A-Z][A-Z0-9_]*)>`, matching uppercase letters, digits, and
underscores after the first character. Python's `str.upper()` on a kwarg key
like `round` → `ROUND` works fine. But a key like `batch_name` → `BATCH_NAME`
and `reviewer_model` → `REVIEWER_MODEL` also work. No actual problem — just
confirm that all lowercase kwarg names used in the three task flows are valid
identifiers that `.upper()` maps to tokens matching `[A-Z][A-Z0-9_]*`. They
do. This is a NOTE, not a GAP.

---

### [NOTE-3] `import` of reviewer modules uses string interpolation — no specification of the mechanism

**Section:** Task flows (all three), file structure

**Issue:**
All three task flows show `reviewer = import("_reviewer_" + reviewer_name)`.
Python has no built-in `import()` function. The actual mechanism would be
`importlib.import_module("_reviewer_" + reviewer_name)`. This is obvious to any
Python developer and is unlikely to cause implementation errors, but the
pseudo-code pattern is imprecise. This is a NOTE, not a GAP.

---

### [NOTE-4] `exc.message` used in API snippet, but `ReviewError` only defines `Exception`

**Section:** "API → Review backend" contract snippet

**Issue:**
The API snippet prints `exc.message`, but the `ReviewError` class inherits from
`Exception` with no custom `message` attribute. Standard `Exception` instances
use `str(exc)` or `exc.args[0]`. The surrounding prose says the API "prints
`str(exc)` to stderr", which is correct. The code snippet uses `.message`
instead of `str(exc)`. This is a minor inconsistency.

**Suggested fix:** Change `print(exc.message, ...)` to `print(str(exc), ...)` in
the API snippet, consistent with the prose description.

---

## Verdict

**GAPS_FOUND**

Six real implementability issues found. Four are genuine blockers (GAP-1 through
GAP-5 excluding NOTE-level items): missing template-path resolution in
`render_prompt`, a stale `LLMError` placement comment, a self-contradicting
path-substitution mechanism description, and a crash-inducing missing guard in
the plan task flow. GAP-5 (vague `plan.md` reference in code review) and GAP-6
(module placement of regex constants) are minor but require a decision before
cards can be written unambiguously.

No legacy-spec citations were used in any finding above.
