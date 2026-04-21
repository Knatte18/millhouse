# Batch 04: Review backends — discussion / plan / code

```yaml
kind: plan-batch
batch-name: backends
batch-depends: [foundation, reviewers, templates]
approved: false
```

## Batch-Specific Context

Each review-type-specific backend orchestrates: slug/path resolution, round
discovery, reviewer loading, mode-compatibility check, prompt rendering
(with bulking where appropriate), reviewer dispatch (parallel for plan),
verdict parsing, file writing, ReviewResult assembly.

All three backends share the same signature:
```python
def run(cfg: dict, slug: str, mill_dir: Path, wiki_root: Path, project_root: Path) -> ReviewResult
```

`ReviewResult` is defined in Batch 01 / Step 1 (created together with the
file). Step 8 below extends `_review_common.py` with additional helpers
(`aggregate_verdict`, `load_reviewer`, `check_mode`, `load_config`) — it
does NOT re-define `ReviewResult`.

## Batch Files

- scripts/_review_common.py
- scripts/_review_discussion.py
- scripts/_review_plan.py
- scripts/_review_code.py

## Steps

### Step 8: Extend `_review_common.py` with dispatch helpers + config loader

- **Creates:** none
- **Modifies:** `scripts/_review_common.py`
- **Reads:** `scripts/_review_common.py`, `specs/active/layer-02/discussion.md`
- **Requirements:**
  (`ReviewResult` is already present from Step 1 — this step does not redefine it.)
  - `aggregate_verdict(sub_verdicts: list[str]) -> str`: if any is
    `REQUEST_CHANGES` or `ERROR` → `REQUEST_CHANGES`; else `APPROVE`.
    (Note: `ERROR` escalates to `REQUEST_CHANGES` at the aggregate; never
    appears at top level.)
  - `load_reviewer(name: str)`: `importlib.import_module(f"_reviewer_{name}")`.
    Raise `ReviewError(f"Unknown reviewer '{name}': no _reviewer_{name}.py found")`
    on `ModuleNotFoundError`.
  - `check_mode(reviewer, expected_mode: str, review_type: str) -> None`:
    compare `reviewer.MODE` to `expected_mode`. On mismatch raise
    `ReviewError(f"No {reviewer.MODE} template exists for {review_type} review. Configure a {expected_mode} reviewer.")`.
  - `load_config(wiki_root: Path, mill_dir: Path) -> dict`: load
    `wiki_root / "config.yaml"` as the base. If `mill_dir / "config.local.yaml"`
    exists, merge it in — local wins on any conflict.
    **Use PyYAML** (`import yaml; yaml.safe_load(...)`) — required dependency
    for v2. If PyYAML is not in the Python environment, add it to
    `plugins/mill/requirements.txt` (create if missing) so `pip install -r`
    resolves it. No stdlib fallback: we commit to PyYAML for all YAML parsing.
    Return a plain `dict`. Raise `ReviewError("Missing config at <path>")` if
    the shared config file is absent.
- **Explore:**
  - `scripts/_review_common.py` — extend; do not rewrite.
  - `specs/active/layer-02/discussion.md` — confirm the ReviewResult shape.
- **depends-on:** [1]
- **Test approach:** smoke-test.
- **Key test scenarios:**
  - Happy: `aggregate_verdict(["APPROVE", "APPROVE"])` → `"APPROVE"`.
  - Happy: `aggregate_verdict(["APPROVE", "REQUEST_CHANGES"])` → `"REQUEST_CHANGES"`.
  - Happy: `aggregate_verdict(["APPROVE", "ERROR"])` → `"REQUEST_CHANGES"`.
  - Error: `load_reviewer("nonexistent")` → ReviewError.
  - Error: `check_mode(reviewer_with_bulk, "tool-use", "discussion")` → ReviewError with message containing both modes.
  - Happy: `load_config(wiki_root, mill_dir)` returns merged dict with `review:` section.
  - Edge: `config.local.yaml` overrides `review.plan.rounds: 1` → merged config has `review.plan.rounds == 1`.
- **Commit:** `feat(review): add dispatch helpers and load_config to _review_common`

### Step 9: Create `_review_discussion.py` — single tool-use review

- **Creates:** `scripts/_review_discussion.py`
- **Modifies:** none
- **Reads:** `scripts/_review_common.py`, `scripts/_reviewer_sonnetmax_tool.py`, `scripts/_llm_claude.py`, `specs/active/layer-02/discussion.md`
- **Requirements:**
  - `def run(cfg: dict, slug: str, mill_dir: Path, wiki_root: Path, project_root: Path) -> ReviewResult`:
    1. `discussion_path = resolve_path(cfg["paths"]["discussion_file"], slug, wiki_root)`.
    2. `reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug, wiki_root)`.
    3. `round_n = discover_round(reviews_dir, "discussion")`.
    4. `max_rounds = cfg["review"]["discussion"]["rounds"]`. If `round_n > max_rounds` → raise `ReviewError(f"Round {round_n} exceeds max {max_rounds} for discussion review")`.
    5. `reviewer_name = cfg["review"]["discussion"]["holistic"]`. `reviewer = load_reviewer(reviewer_name)`. `check_mode(reviewer, "tool-use", "discussion")`.
    6. `prompt_text = render_prompt("review-discussion", task_title=load_task_title(mill_dir, slug), artefact_path=str(discussion_path), constraints=read_constraints_md(project_root), round=round_n, reviewer_model=reviewer_name)`.
     (No `<REVIEW_OUTPUT_PATH>` token — the backend owns file I/O; the LLM
     returns review as text. This applies to all three backends.)
    7. Try: `raw = reviewer.run(prompt_text)`. Except `LLMError` → return ReviewResult with single entry having `verdict: "ERROR"`, aggregate `REQUEST_CHANGES`, no file. Exit 0 (one entry succeeded/failed — total-fail check at step 8 if zero succeeded). For single-entry discussion, if it errors, caller treats as all-failed → exit 1 is handled by the API based on `ReviewResult` inspection.
    8. `verdict = parse_verdict(raw)`.
    9. `review_file = write_review_file(reviews_dir, "discussion", round_n, raw)`.
    10. `return ReviewResult(type="discussion", round=round_n, verdict=verdict, reviews=[{"scope": "holistic", "verdict": verdict, "file": str(review_file)}])`.
  - **Total-fail handling:** for discussion there is only one sub-review. If
    it fails with LLMError, the API script must exit 1 (per the spec:
    "zero sub-reviews succeeded → exit 1, empty stdout, stderr lists errors").
    Implementation: the backend catches the LLMError, builds the ReviewResult
    with the ERROR entry, but raises `ReviewError("All sub-reviews failed: <msg>")`
    so the API catches it and exits 1. Do not return the partial ReviewResult
    for discussion when the sole sub-review fails.
- **Explore:**
  - `scripts/_reviewer_sonnetmax_tool.py` — confirms `reviewer.MODE == "tool-use"` and `reviewer.run(text)` signature.
  - `scripts/_llm_claude.py` — understand `LLMError` conditions.
  - `specs/active/layer-02/discussion.md` — Task Flow 1 is the authoritative sequence.
- **depends-on:** [8, 3, 4]
- **Test approach:** integration (covered in Batch 06).
- **Key test scenarios:**
  - Happy: a seeded `discussion.md` → the backend returns ReviewResult with one `holistic` entry, file on disk, stdout JSON parses.
  - Error: LLM times out → ReviewError raised; API exits 1.
  - Edge: first invocation (round 1), reviews_dir does not exist yet → created.
- **Commit:** `feat(review): add _review_discussion.py backend`

### Step 10: Create `_review_plan.py` — parallel per-batch + holistic

- **Creates:** `scripts/_review_plan.py`
- **Modifies:** none
- **Reads:** `scripts/_review_common.py`, `scripts/_reviewer_sonnetmax.py`, `scripts/_llm_claude.py`, `specs/active/layer-02/discussion.md`
- **Requirements:**
  - `def run(cfg, slug, mill_dir, wiki_root, project_root) -> ReviewResult`:
    1. Resolve `plan_dir`, `reviews_dir`. `round_n = discover_round(reviews_dir, "plan")`. Check max rounds.
    2. `overview_path = plan_dir / "00-overview.md"`. Raise ReviewError if absent.
    3. `batch_files = sorted(p for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md")`.
    4. Load batch reviewer: `batch_reviewer = load_reviewer(cfg["review"]["plan"]["batch"])`; `check_mode(..., "bulk", "plan")`.
    5. Load holistic reviewer: `holistic_reviewer = load_reviewer(cfg["review"]["plan"]["holistic"])` (if not `~`); `check_mode(..., "bulk", "plan")`. If `holistic` is `None`, skip holistic section.
    6. `task_title = load_task_title(mill_dir, slug)`. `constraints = read_constraints_md(project_root)`.
    7. **Per-batch in parallel (only if `batch_files` is non-empty):**
       - `with ThreadPoolExecutor(max_workers=len(batch_files)) as ex`:
       - For each batch file: submit a function that:
         a. Parses `Reads:`/`Modifies:`/`Creates:` paths from the batch file. Resolves each to absolute paths. **`root:` resolution:** if `root:` is absent from `00-overview.md` frontmatter, resolve paths as `project_root / path`. If `root:` is present (e.g. `root: plugins/mill`), resolve as `project_root / root / path`. Drops nonexistent paths with stderr warning.
         b. `bulked = bulk_files([overview_path, batch, *reads])`.
         c. `prompt_text = render_prompt("review-plan-batch", task_title=..., batch_name=batch.stem, artefact_content=bulked, constraints=constraints, round=round_n, reviewer_model=cfg["review"]["plan"]["batch"])`.
         d. `raw = batch_reviewer.run(prompt_text)` (catches LLMError).
         e. On success: `verdict = parse_verdict(raw); path = write_review_file(reviews_dir, "plan", round_n, raw, scope=batch.stem)`.
         f. Return a `reviews[]` entry: `{scope: batch.stem, verdict, file: str(path)}`. Or on LLMError: `{scope: batch.stem, verdict: "ERROR", file: None, error: str(exc)}`.
       - Collect futures; wait all.
    8. **Holistic (if not skipped):**
       - Union all `Reads:`/`Modifies:`/`Creates:` across all batch files.
       - `bulked = bulk_files([overview_path, *batch_files, *unioned_reads])`.
       - `prompt_text = render_prompt("review-plan-holistic", ...)`.
       - Dispatch + write file with `scope="holistic"`.
       - Append result to `reviews[]`.
    9. `aggregate = aggregate_verdict([r["verdict"] for r in reviews])`.
    10. **Total-fail check.** The `reviews` list at this point contains ALL
        sub-review entries — every per-batch entry AND the holistic entry
        (if `holistic: ~` was not set). If **every** entry in `reviews` has
        `verdict == "ERROR"` (i.e., zero sub-reviews produced APPROVE or
        REQUEST_CHANGES), raise
        `ReviewError(f"All sub-reviews failed: {summary}")`. Otherwise
        proceed to step 11 — partial failure is fine, the aggregate carries it.
    11. Return `ReviewResult(type="plan", round=round_n, verdict=aggregate, reviews=reviews)`.
  - Use `from concurrent.futures import ThreadPoolExecutor`.
  - Parser for `Reads:`/`Modifies:`/`Creates:` in batch files. Explicit regex:
    - Match lines of the form `^-\s*\*\*(Reads|Modifies|Creates):\*\*\s+(?P<rest>.+)$`
    - From `<rest>`, extract backtick-wrapped path tokens via
      `re.findall(r"`([^`]+)`", rest)` (handles multiple tokens per line).
    - If no backticks on the line, fall back to splitting on `,` and stripping
      whitespace (handles plain `- **Reads:** path/a, path/b`).
    - Dedupe across all batches. Drop entries not existing on disk with
      a stderr warning (caller's data problem, not a crash).
- **Explore:**
  - `specs/active/layer-02/discussion.md` — Task Flow 2 is the authoritative sequence.
  - Any existing batch/plan file in the legacy repo to verify the Reads/Modifies parse is correct.
- **depends-on:** [8, 3, 5]
- **Test approach:** integration (Batch 06).
- **Key test scenarios:**
  - Happy: a plan with two batches → ReviewResult has 3 entries (2 batch + 1 holistic), aggregate = worst-case verdict.
  - Edge: plan with zero batches (only overview) → skip parallel, only holistic entry in reviews.
  - Error: one batch LLM times out → that entry has verdict=ERROR, aggregate becomes REQUEST_CHANGES, exit 0.
  - Error: all sub-reviews fail → ReviewError raised; API exits 1.
- **Commit:** `feat(review): add _review_plan.py backend with parallel batches`

### Step 11: Create `_review_code.py` — single bulk review of diff

- **Creates:** `scripts/_review_code.py`
- **Modifies:** none
- **Reads:** `scripts/_review_common.py`, `scripts/_reviewer_sonnetmax.py`, `specs/active/layer-02/discussion.md`
- **Requirements:**
  - `def run(cfg, slug, mill_dir, wiki_root, project_root) -> ReviewResult`:
    1. Resolve `plan_dir`, `reviews_dir`. `round_n = discover_round(reviews_dir, "code")`. Check max rounds.
    2. `plan_files = sorted(plan_dir.glob("*.md"))`. Raise ReviewError if empty.
    3. `plan_content = "\n\n".join(p.read_text() for p in plan_files)`.
    4. Compute diff using `_subprocess_util.run` (Layer 01 convention — handles
       UTF-8 on Windows, timeouts, breadcrumbs):
       `result = _subprocess_util.run(["git", "merge-base", "main", "HEAD"], cwd=project_root, timeout=30)`
       → `base_sha = result.stdout.strip()`. Then
       `result = _subprocess_util.run(["git", "diff", f"{base_sha}..HEAD"], cwd=project_root, timeout=30)`
       → `diff = result.stdout`. **`cwd=project_root` is required** on both
       calls or git may resolve the wrong repository. Raise
       `ReviewError(f"git failed: {stderr}")` on any non-zero exit.
    4b. **Empty-diff guard:** if `not diff.strip()`, raise
       `ReviewError("No diff between <base>..HEAD — are you on a task branch?")`.
       This covers the "invoked on main" edge case where merge-base == HEAD.
    5. Parse file paths from diff (`--- a/<path>` / `+++ b/<path>` lines).
    6. `style = cfg["review"]["code"]["style"]`. `template_name = f"review-code-{style}"`.
    7. `reviewer = load_reviewer(cfg["review"]["code"]["reviewer"])`. `check_mode(reviewer, "bulk", "code")`.
    8. `bulked = bulk_files([*plan_files, *[project_root / p for p in touched_files if (project_root / p).exists()]])`.
    9. `prompt_text = render_prompt(template_name, task_title=..., diff=diff, plan_content=plan_content, artefact_content=bulked, constraints=..., round=round_n, reviewer_model=cfg["review"]["code"]["reviewer"])`.
    10. `raw = reviewer.run(prompt_text)` (catch LLMError; raise ReviewError on failure since one sub-review = total failure for code).
    11. `verdict = parse_verdict(raw); path = write_review_file(reviews_dir, "code", round_n, raw)` — no `scope` kwarg; code review's canonical filename is `<ts>-code-review-r<N>.md` (no batch suffix). The `holistic` string appears only in the ReviewResult's `reviews[]` entry to match the unified shape across review types.
    12. Return `ReviewResult(type="code", round=round_n, verdict=verdict, reviews=[{"scope": "holistic", "verdict": verdict, "file": str(path)}])`.
  - Use `_subprocess_util.run` from Layer 01 for all git subprocess calls
    (consistent with `_llm_claude.py`). Never import `subprocess` directly
    for git in the backend.
- **Explore:**
  - `specs/active/layer-02/discussion.md` — Task Flow 3 authoritative.
  - `scripts/_subprocess_util.py` — reuse subprocess helpers if they fit.
- **depends-on:** [8, 3, 6]
- **Test approach:** integration (Batch 06).
- **Key test scenarios:**
  - Happy: running on a branch with a small diff → ReviewResult with one entry, file written, verdict parsed.
  - Error: running on `main` (no diff) → raise `ReviewError("No diff between <base>..HEAD — are you on a task branch?")`.
  - Error: LLM fails → ReviewError raised; API exits 1.
- **Commit:** `feat(review): add _review_code.py backend`
