# Batch: bench-script

```yaml
task: "(A) -- Benchmark Gemini single-reviewers vs sonnetmax baseline"
batch: bench-script
number: 2
cards: 1
verify: "uv run --project plugins/mill python plugins/mill/integration_tests/bench-reviewers.py --reviewers test_stub --types discussion"
depends-on: [1]
```

## Batch Scope

This batch creates `plugins/mill/integration_tests/bench-reviewers.py` — the benchmark runner. It loads the reviewer registry, renders prompts from existing templates and fixtures, invokes reviewers via `_reviewer_single.run()`, collects metrics (verdict, finding count, format compliance, wall-clock time), and writes a results table to `.scratch/`. The script accepts `test_stub` as a zero-cost reviewer for smoke testing. The run-bench batch (batch 03) depends only on this script existing; no new Python interfaces are exported.

## Cards

### Card 3: Implement bench-reviewers.py benchmark harness

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_reviewer_single.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/integration_tests/fixtures/sample-discussion.md`
  - `plugins/mill/integration_tests/fixtures/sample-plan/00-overview.md`
  - `plugins/mill/integration_tests/fixtures/sample-plan/01-core.md`
  - `plugins/mill/integration_tests/fixtures/sample-code.py`
  - `plugins/mill/templates/review-discussion.md`
  - `plugins/mill/templates/review-plan-holistic.md`
  - `plugins/mill/templates/review-code-holistic.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/integration_tests/bench-reviewers.py`
- **Deletes:** none
- **Requirements:**

  Create `plugins/mill/integration_tests/bench-reviewers.py`. Add `sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))` so imports from `plugins/mill/scripts/` resolve when the script is invoked from the repo root.

  **CLI arguments** (use `argparse`):
  - `--reviewers`: space-separated reviewer names. Default: `g25flash g3flash_preview g25pro`.
  - `--types`: space-separated review types from `{discussion, plan, code}`. Default: all three.
  - `--timeout`: int seconds per call. Default: `300`.

  **Artefact construction** — read fixtures once before the reviewer loop; call `render_prompt` inside the reviewer loop (because `reviewer_model` changes per reviewer):
  - All fixture paths are resolved relative to the script file: `FIXTURES = Path(__file__).parent / "fixtures"`. Use `FIXTURES / "sample-discussion.md"`, `FIXTURES / "sample-plan" / "00-overview.md"`, etc.
  - `TOOL_RULE_BULK = _review_common.build_tool_rule("bulk")`.
  - DISCUSSION artefact: read `FIXTURES / "sample-discussion.md"`; build `artefact_section` as `"Evaluate the discussion document below.\n\n--- FILE: _mill/discussion.md ---\n" + discussion_text`. For each reviewer, render via `_review_common.render_prompt("review-discussion", task_title="Sample render module refactor", round=1, reviewer_model=reviewer_name, tool_rule=TOOL_RULE_BULK, artefact_section=discussion_artefact_section, constraints="(none)")`. Note: render inside the reviewer loop — `reviewer_model` changes per reviewer.
  - PLAN artefact: read `FIXTURES / "sample-plan" / "00-overview.md"` and `FIXTURES / "sample-plan" / "01-core.md"`; build `artefact_section` concatenating `"Evaluate the plan below. All plan files and referenced source files are inlined.\n\n## Files included\n\n- `_mill/plan/00-overview.md`\n- `_mill/plan/01-core.md`\n\n"` followed by `"--- FILE: _mill/plan/00-overview.md ---\n" + overview_text + "\n\n--- FILE: _mill/plan/01-core.md ---\n" + batch_text`. For each reviewer, render via `_review_common.render_prompt("review-plan-holistic", ...)`. Note: render inside the reviewer loop — `reviewer_model` changes per reviewer.
  - CODE artefact: plan files + `FIXTURES / "sample-code.py"`; build `artefact_section` with all three files using the same `--- FILE: path ---` delimiter pattern, using path label `plugins/mill/scripts/_render.py` for `sample-code.py` (it represents the implemented `_render.py`). Add `"## Files included"` manifest listing all three paths. For each reviewer, render via `_review_common.render_prompt("review-code-holistic", ...)`. Note: render inside the reviewer loop — `reviewer_model` changes per reviewer.

  **Reviewer spec resolution** per reviewer name:
  - If name is `"test_stub"`: spec = `{"type": "single", "provider": "test_stub", "model": "stub"}`. Before each `_reviewer_single.run()` call, seed the stub: `import _reviewer_test_stub as _stub; _stub.seed([(CANNED_APPROVE, "stub-sid")])`. `CANNED_APPROVE` is a module-level constant — a valid APPROVE response string that passes `format_ok` and `parse_verdict`. It must start with `# Review:`, contain a fenced yaml block with `verdict: APPROVE`, and contain `## Verdict`.
  - Otherwise: `registry = _reviewers.load(wiki_path); spec = _reviewers.resolve(registry, name)`. On `_reviewers.ReviewerError`: print to stderr, skip.

  **Per-run metrics**:
  - Wall-clock time via `time.monotonic()`.
  - On success: `verdict = _review_common.parse_verdict(text)` (catch exception → `"PARSE_FAIL"`).
  - Finding count per type:
    - discussion: `_review_common.parse_blocking_count(text, severity="GAP") + _review_common.parse_blocking_count(text, severity="NOTE")`
    - plan/code: `_review_common.parse_blocking_count(text, severity="BLOCKING") + _review_common.parse_blocking_count(text, severity="NIT")`
  - `format_ok = text.strip().startswith("# Review:") and "verdict:" in text and "## Verdict" in text`
  - Write raw response to `.scratch/bench-<timestamp>-<reviewer_name>-<review_type>.md` where `timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")` computed once at script start.
  - On exception/timeout: verdict `"ERROR"`, findings 0, format_ok False.

  **Output**: After all runs, print and write to `.scratch/bench-<timestamp>.md` a markdown results table with columns: `Reviewer | Type | Time | Verdict | Findings | Fmt`. Print each row immediately after completing (flush=True) so progress is visible.

  **Path resolution**: `from _paths import resolve_git_root, resolve_wiki_path; git_root = resolve_git_root(); wiki_path = resolve_wiki_path(git_root)` — call once before the loop.
- **Commit:** `feat(bench): add bench-reviewers.py benchmark harness`

## Batch Tests

`verify:` runs the bench script with `--reviewers test_stub --types discussion`. Passes if: (1) exits 0, (2) produces a results table with one row, (3) the row shows `verdict: APPROVE`, `findings: 0`, `fmt: True`. This exercises argument parsing, prompt rendering, reviewer dispatch, metric collection, and output formatting without any real LLM call.
