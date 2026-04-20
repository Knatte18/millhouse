---
kind: plan-batch
batch-name: foundation
batch-depends: []
approved: false
---

# Batch 01: Foundation — `_review_common.py` + `_llm_claude.py`

## Batch-Specific Context

These two files are the plumbing every higher layer calls into. No
dependencies on any other Layer 02 file. Pure helpers + one LLM-provider.

## Batch Files

- scripts/_review_common.py
- scripts/_llm_claude.py

## Steps

### Step 1: Create `_review_common.py` with shared helpers, regex, and `ReviewError`

- **Creates:** `scripts/_review_common.py`
- **Modifies:** none
- **Reads:** `scripts/_render.py`, `scripts/mill-add.py`
- **Requirements:**
  - `class ReviewError(Exception)`: plain Exception subclass; callers raise
    with a message; API catches and prints `str(exc)` to stderr.
  - `@dataclass ReviewResult`:
    ```python
    from dataclasses import dataclass, field
    from typing import Any

    @dataclass
    class ReviewResult:
        type: str                              # "discussion" | "plan" | "code"
        round: int
        verdict: str                           # "APPROVE" | "REQUEST_CHANGES"
        reviews: list[dict] = field(default_factory=list)

        def to_dict(self) -> dict[str, Any]:
            return {
                "type": self.type,
                "round": self.round,
                "verdict": self.verdict,
                "reviews": self.reviews,
            }
    ```
    Defined here (not in Step 8) so the file is self-consistent from
    creation and Step 8 can extend with other helpers without reopening
    data-shape decisions.
  - Module-level regex constants:
    - `RE_SIMPLE = re.compile(r"^\d{8}-\d{6}-(?P<type>discussion|code|plan)-review-r(?P<n>\d+)\.md$")`
    - `RE_BATCH  = re.compile(r"^\d{8}-\d{6}-plan-review-(?P<batch>[a-z0-9-]+)-r(?P<n>\d+)\.md$")`
  - `find_active_slug(mill_dir: Path) -> str`: scan `mill_dir` for files
    matching `.<slug>.slug.md`. Exactly one must exist. Zero → raise
    `ReviewError("No active task: no .slug.md file found in .millhouse/")`.
    More than one → raise `ReviewError("Multiple .slug.md files; expected exactly one: <list>")`.
  - `load_task_title(mill_dir: Path, slug: str) -> str`: open
    `mill_dir / f".{slug}.slug.md"`; parse YAML frontmatter; return
    `task_title` field; fall back to `slug` if absent.
  - `read_constraints_md(project_root: Path) -> str`: read
    `project_root / "CONSTRAINTS.md"`; return file contents if exists, else
    empty string.
  - `resolve_path(path_tmpl: str, slug: str, wiki_root: Path) -> Path`:
    return `wiki_root / path_tmpl.replace("<SLUG>", slug)`. No `_render.render()`.
  - `discover_round(reviews_dir: Path, review_type: str) -> int`: if
    `reviews_dir` does not exist, return 1. Otherwise iterate entries: for
    each file, try `RE_SIMPLE` first; if match AND `type` group equals
    `review_type`, record `n`; skip `RE_BATCH` for this file. Otherwise try
    `RE_BATCH`; if match AND `review_type == "plan"`, record `n`. Return
    `max(found) + 1` or 1 if nothing matched.
  - `bulk_files(file_paths: list[Path]) -> str`: concat contents with
    `f"--- FILE: {p} ---\n{contents}\n"` per file, joined by empty lines.
    Paths that don't exist → skip with a stderr warning.
  - `render_prompt(template_name: str, **tokens) -> str`: resolve template
    path as `Path(__file__).parent.parent / "templates" / f"{template_name}.md"`.
    Auto-uppercase kwarg keys (`artefact_path` → `ARTEFACT_PATH`). Call
    `_render.render(template_path, uppercased_tokens)`. **Let `KeyError` from
    `_render.render()` propagate unwrapped** — it indicates a template/token
    mismatch that is a programming error, not a user error. The API does not
    catch `KeyError`.
  - `parse_verdict(raw_output: str) -> str`: extract `verdict:` from YAML
    frontmatter at the top of `raw_output`. Return `"APPROVE"` or
    `"REQUEST_CHANGES"`. If frontmatter missing or `verdict:` absent or
    value invalid → raise `ReviewError("Could not parse verdict: <reason>")`.
  - `write_review_file(reviews_dir: Path, review_type: str, round_num: int, content: str, scope: str | None = None) -> Path`:
    build canonical filename using current UTC timestamp
    (`datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")` — do NOT use
    the deprecated `datetime.utcnow()`). For simple reviews:
    `<ts>-<type>-review-r<N>.md`. For plan batches (`scope` is a batch name
    like `"01-setup"` and `review_type == "plan"` and scope != "holistic"):
    `<ts>-plan-review-<scope>-r<N>.md`. For plan holistic (`scope == "holistic"` and `review_type == "plan"`):
    `<ts>-plan-review-r<N>.md`. Create `reviews_dir` (mkdir parents) if
    absent; write `content`; return the absolute path.
    **`"holistic"` is a reserved scope value.** Batch files in `plan/` must
    not have the stem `"holistic"` (would cause filename collision with the
    holistic review). Not enforced by `write_review_file` but stated here.
- **Explore:**
  - `scripts/_render.py` — learn the existing template-rendering interface
    and uppercase-token grammar. `render_prompt` wraps it.
  - `scripts/mill-add.py` — learn the flat-script style used by Layer 01
    (imports, argparse, error handling, print-to-stderr convention).
- **depends-on:** []
- **Test approach:** smoke-test (import the module, call a few functions
  against known inputs; no pytest). Integration tests in Batch 06 cover
  the full path.
- **Key test scenarios:**
  - Happy: `render_prompt("review-discussion", artefact_path="/tmp/x", round=1, ...)` — returns rendered string.
  - Error: `find_active_slug()` on empty `.millhouse/` → raises ReviewError.
  - Edge: `discover_round()` on nonexistent dir → returns 1.
  - Edge: `RE_SIMPLE` matches `20260418-001200-plan-review-r1.md`; `RE_BATCH`
    is skipped for the same file (not double-counted).
  - Edge: `discover_round(reviews_dir, "discussion")` where reviews_dir
    contains a plan-batch file → batch file is ignored, returns correct
    round for discussion only (cross-type isolation).
- **Commit:** `feat(review): add _review_common.py with helpers, regex, ReviewError`

### Step 2: Create `_llm_claude.py` with `run_bulk`, `run_tool_use`, `LLMError`

- **Creates:** `scripts/_llm_claude.py`
- **Modifies:** none
- **Reads:** `scripts/_subprocess_util.py`
- **Requirements:**
  - `class LLMError(Exception)`: plain Exception subclass. Attributes: none
    special. Callers use `str(exc)`.
  - `run_bulk(prompt_text: str, *, model: str, effort: str | None = None, timeout: int = 600) -> str`:
    spawn `claude -p --allowedTools "" --output-format stream-json --model <model>`
    (add `--effort <effort>` if set). Pass `prompt_text` on stdin. Parse
    stream-json line-by-line; extract the final text response (the `"result"`
    or final assistant text event — check `_subprocess_util` helpers if
    they fit). Return the full assistant text. Raise `LLMError` on:
    - Subprocess timeout (from `subprocess.TimeoutExpired`) → `LLMError("Claude CLI timed out after <N>s")`.
    - Non-zero exit → `LLMError(f"claude exited {code}: {stderr[:500]}")`.
    - Stream-json parse error on a line → print warning to stderr, continue.
    - Stream-json empty (no assistant text at all) → `LLMError("claude returned no content")`.
  - `run_tool_use(prompt_text: str, *, model: str, effort: str | None = None, timeout: int = 900) -> str`:
    same as `run_bulk` but with `--allowedTools Read,Grep,Glob` (read-only
    tools only). No `Write`, no `Bash` — templates explicitly instruct the
    reviewer to return the review as text, never write files. Allowing Write
    via CLI flag is unnecessary risk. Longer default timeout (900s) because
    tool-use sessions explore files.
    **Note:** discussion.md lists `Read,Grep,Write` as the tool-use tools,
    but Decision 24 ("backend always writes the review file") makes `Write`
    unnecessary; `Glob` is substituted to aid file discovery. This is a
    deliberate implementation refinement of the discussion.
  - Do NOT catch `LLMError` internally. Raise and let the backend handle.
  - Minimal logging to stderr: on entry print `claude <model> (bulk|tool-use) starting…`; on exit print `claude <model> returned <len> chars in <dt>s`.
- **Explore:**
  - `scripts/_subprocess_util.py` — learn the subprocess utilities lifted
    from v1 (timeout handling, stdin piping). Reuse instead of reinventing.
- **depends-on:** []
- **Test approach:** smoke-test (call both functions against a trivial prompt
  like "respond with APPROVE"; verify stream-json parsed text is returned).
  Requires `claude` in PATH. Skip if absent with clear message.
- **Key test scenarios:**
  - Happy: `run_bulk("Respond with 'APPROVE'", model="claude-sonnet-4-5")` returns a string containing "APPROVE".
  - Error: non-existent model → LLMError raised.
  - Edge: empty prompt → claude handles; our wrapper passes through the result.
- **Commit:** `feat(review): add _llm_claude.py with run_bulk, run_tool_use, LLMError`
