# Batch: html-unescape-agent-output

```yaml
task: "Fix agent-mode dispatch gaps: HTML escaping, missing flags, timeouts, and stale skill content"
batch: "html-unescape-agent-output"
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-review-finalize.py
depends-on: []
```

## Batch Scope

Fixes #605 (HTML-escaped `<task-notification>` payloads corrupting agent-output captures) at all four sites that read a `--agent-output` file back from disk: `_implementer_common.finalize_from_output` (shared by `millpy-implement.py` and `millpy-fix.py`), `millpy-review-code.py`, `millpy-review-discussion.py`, and `millpy-review-plan.py`. Each site gets the identical one-line fix (`html.unescape(...)` wrapping the `read_text(...)` call) plus one unit test proving the read site now unescapes. No external interface changes — the fix is purely internal to each CLI's finalize-stage parsing; downstream consumers (status.md, review files, JSON envelopes) see corrected text with no contract change. No batch-local decisions beyond the Shared Decision `html.unescape at read time, not write time` in the overview.

## Cards

### Card 1: Unescape HTML entities in `_implementer_common.finalize_from_output`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `import html` to `_implementer_common.py`'s imports. In `finalize_from_output` (currently `output = Path(agent_output_path).read_text(encoding="utf-8")`), wrap the read so `output` is the HTML-unescaped text: `output = html.unescape(Path(agent_output_path).read_text(encoding="utf-8"))`. This is the single shared read site for both `millpy-implement.py` and `millpy-fix.py` — no changes needed in either of those two CLI files. Add a new numbered test case to `test-implementer-common.py` (follow the existing `# Case N:` comment + `errors` counter pattern, e.g. placed after the existing Case 13 "finalize_from_output reads agent output and delegates to _forward_output"): write HTML-escaped text (e.g. `"Q&amp;A send &lt;guid&gt; Cards 20 &amp; 21"`) to the `agent_output_path` fixture file; patch `_implementer_common._forward_output` (module-level) to capture its first positional argument instead of running the real implementation; call `finalize_from_output(agent_output_path, project_root, ...)` with the same fixture pattern as Case 13; assert the captured first positional argument equals the fully-unescaped string (`"Q&A send <guid> Cards 20 & 21"`).
- **Commit:** `fix(implementer-common): unescape HTML entities in finalize_from_output agent-output read`

### Card 2: Unescape HTML entities in `millpy-review-code.py` finalize read site

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/unit_tests/test-review-finalize.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `import html` to `millpy-review-code.py`'s imports. In the `--stage finalize` branch (currently `raw_text = agent_output_path.read_text(encoding="utf-8")`), wrap the read: `raw_text = html.unescape(agent_output_path.read_text(encoding="utf-8"))`. Add a new test function `test_review_code_finalize_unescapes_html_entities` to `test-review-finalize.py`, modeled on the existing `test_review_code_finalize_no_prepare` mock-module setup (same `mock_modules` dict shape, same `importlib.util.spec_from_file_location` load pattern): write HTML-escaped text (e.g. `"Q&amp;A send &lt;guid&gt;"`) to `output_file`; mock `_review_code.finalize` with `unittest.mock.MagicMock(return_value=mock_result)` as the existing tests do; invoke `millpy_review_code.main(["--stage", "finalize", "--round", "1", "--agent-output", str(output_file)])`; assert the `finalize` mock's `call_args` contains the unescaped text (`"Q&A send <guid>"`) as the `raw_text` positional argument (third positional arg per `finalize(cfg, slug, raw_text, ...)`).
- **Commit:** `fix(review-code): unescape HTML entities in finalize agent-output read`

### Card 3: Unescape HTML entities in `millpy-review-discussion.py` finalize read site

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/unit_tests/test-review-finalize.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `import html` to `millpy-review-discussion.py`'s imports. In the `--stage finalize` branch (currently `raw_text = agent_output_path.read_text(encoding="utf-8")`), wrap the read: `raw_text = html.unescape(agent_output_path.read_text(encoding="utf-8"))`. Add a new test function `test_review_discussion_finalize_unescapes_html_entities` to `test-review-finalize.py`, modeled on the existing `test_review_discussion_finalize_no_prepare` mock-module setup: write HTML-escaped text to `output_file`; mock `_review_discussion.finalize`; invoke `millpy_review_discussion.main(["--stage", "finalize", "--round", "1", "--agent-output", str(output_file)])`; assert the `finalize` mock's `call_args` contains the unescaped `raw_text` positional argument (third positional per `finalize(cfg, slug, raw_text, round_n=..., ...)`).
- **Commit:** `fix(review-discussion): unescape HTML entities in finalize agent-output read`

### Card 4: Unescape HTML entities in `millpy-review-plan.py` finalize read site

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/unit_tests/test-review-finalize.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `import html` to `millpy-review-plan.py`'s imports. In the `--stage finalize` branch (currently `raw_text = agent_output_path.read_text(encoding="utf-8")`), wrap the read: `raw_text = html.unescape(agent_output_path.read_text(encoding="utf-8"))`. Add a new test function `test_review_plan_finalize_unescapes_html_entities` to `test-review-finalize.py`, modeled on the existing `test_review_plan_finalize_no_prepare` mock-module setup: write HTML-escaped text to `output_file`; mock `_review_plan.finalize`; invoke `millpy_review_plan.main(["--stage", "finalize", "--round", "1", "--agent-output", str(output_file)])`; assert the `finalize` mock's `call_args` contains the unescaped `raw_text` positional argument (third positional per `finalize(cfg, slug, raw_text, scope=None, round_n=..., ...)`).
- **Commit:** `fix(review-plan): unescape HTML entities in finalize agent-output read`

## Batch Tests

`verify:` runs `test-implementer-common.py` (Card 1's new case, plus the full existing case suite as a regression check since the file uses a single-process numbered-case runner, not per-case isolation) and `test-review-finalize.py` (Cards 2-4's three new test functions, plus the existing finalize-arg-wiring tests for all three review CLIs). Scoped via `--only` to these two files — not the full `run-all.py` suite — since this batch touches exactly the read sites these two files already cover; no other test file imports or exercises `finalize_from_output` or the three review CLIs' finalize-stage `--agent-output` handling.
