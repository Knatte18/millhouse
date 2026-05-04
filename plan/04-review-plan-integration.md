# Batch: review-plan-integration

```yaml
task: 'review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure'
batch: review-plan-integration
cards: 6
verify: uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"
depends-on: [content-helpers]
```

## Batch Scope

Wires the new helpers from `content-helpers` into the plan-review backend. Bumps `wiki/config.yaml` timeouts (Card 13). Plumbs `bulk_timeout` and `holistic_timeout` through reviewer calls (Card 14). Surfaces deletes via `compute_deletes_union` and `build_deletes_section` in plan-batch and plan-holistic prompts (Card 15). Adds mid-round resume via `detect_resume_round` (Card 16; closes #87). Removes the total-fail `raise ReviewError` block so an all-ERROR plan run still emits valid JSON (Card 17; backend prerequisite for the SKILL.md step 4.5 retry in B08). Adds backend integration tests covering all four behaviour changes (Card 18).

## Cards

### Card 13: Update `wiki/config.yaml` timeouts

- **Reads:**
  - `wiki/config.yaml`
- **Modifies:**
  - `wiki/config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the `llm:` block: change `bulk_timeout: 600` to `bulk_timeout: 900` (closes #83 — covers `effort max` per-batch with cold cache). Add a new line under `bulk_timeout` reading `holistic_timeout: 1800          # holistic plan/code review (5–10× per-batch prompt size, #80)`. Update the section's leading comment block to mention both knobs and their consumers (`_review_plan.run` and `_review_code.run` read `holistic_timeout`; both backends read `bulk_timeout` for per-batch calls). Keep `tool_use_timeout: 900` and `implementer_timeout: 3600` unchanged.
- **Commit:** `chore(wiki): bump bulk_timeout to 900, add holistic_timeout=1800`

### Card 14: Plumb timeouts through `_review_plan.run`

- **Reads:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_common.py`
  - `wiki/config.yaml`
- **Modifies:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Read `bulk_timeout = cfg["llm"]["bulk_timeout"]` and `holistic_timeout = cfg["llm"]["holistic_timeout"]` near the top of `run()` (after step 1's path resolution, before per-batch dispatch). Pass `bulk_timeout` into every per-batch dispatch path: thread the value into `_review_one_batch` as a new positional argument (after `wiki_root`) and use it on both `batch_reviewer.run(prompt_text, timeout=bulk_timeout)` (initial call) and `batch_reviewer.run(retry_prompt, session_id=session_id, resume=True, timeout=bulk_timeout)` (NEED_CONTEXT resume retry). Pass `holistic_timeout` into the holistic block: `holistic_reviewer.run(prompt_text, timeout=holistic_timeout)` and `holistic_reviewer.run(retry_prompt, session_id=session_id, resume=True, timeout=holistic_timeout)`. The reviewer modules already accept the `timeout` kwarg per Card 7; this card is purely the call-site change.
- **Commit:** `feat(review-plan): plumb bulk_timeout and holistic_timeout from config`

### Card 15: Plumb `deletes_union` + surface `## Intentionally deleted` in plan-review prompts

- **Reads:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_common.py`
- **Modifies:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Compute `deletes_union = compute_deletes_union(plan_dir)` once near the existing `creates_union = compute_creates_union(plan_dir)` line. Thread `deletes_union` into `_review_one_batch` as a new positional argument (after `creates_union`) and use it: pass `deletes_union=deletes_union` keyword to the `resolve_ref_paths(...)` call inside the function. Inside the per-batch artefact build (both `tool-use` and `bulk` MODE branches): when `deletes_union` is non-empty, append `\n\n` followed by `build_deletes_section(sorted(deletes_union))` to the `artefact_section` string. Repeat the same surface in the holistic block: pass `deletes_union=deletes_union` to the holistic `resolve_ref_paths(...)` call (line ~379-382 today); when `deletes_union` is non-empty, append `build_deletes_section(sorted(deletes_union))` to the holistic `artefact_section`. Sorting keeps the prompt stable for cache-friendliness.
- **Commit:** `feat(review-plan): surface intentional deletes to reviewer prompts`

### Card 16: Mid-round resume in `_review_plan.run`

- **Reads:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_common.py`
- **Modifies:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** After resolving `plan_dir` and `reviews_dir` and after computing `creates_union` / `deletes_union`, before the per-batch dispatch block: call `resume_round = detect_resume_round(reviews_dir, "plan")`. When `resume_round is not None`: bypass the per-batch ThreadPoolExecutor entirely; instead, scan `reviews_dir` for every plan-batch file at round `resume_round` (use `RE_BATCH` to match — same as `_scan_approved_batches` does), parse the verdict from each via `parse_verdict(file.read_text(encoding="utf-8"))` and the blocking count via `parse_blocking_count(file_text, severity="BLOCKING")`, and append one entry to `reviews[]` per disk file: `{"scope": batch_stem, "round": resume_round, "verdict": parsed_verdict, "blocking_count": parsed_blocking, "file": str(path), "session_id": None}`. Skip the `_scan_approved_batches` carryforward in the resume path (mid-round resume supersedes it for round `resume_round`). NEED_CONTEXT verdicts on disk propagate as-is — do not re-fire any reviewer. After the disk-scan, fall through to the existing holistic block; the holistic's `discover_round("plan", "holistic")` returns `resume_round` because no holistic file exists at that round, so it fires at the right round. When `resume_round is None`, the existing per-batch + carryforward logic runs unchanged. Add a stderr breadcrumb on the resume path: `[_review_plan] resuming round {resume_round} from {len(reviews)} on-disk per-batch files; firing holistic only`.
- **Commit:** `feat(review-plan): mid-round resume when holistic missing (#87)`

### Card 17: Remove total-fail check in `_review_plan.run`

- **Reads:**
  - `plugins/mill/scripts/_review_plan.py`
- **Modifies:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Delete the block that currently lives at lines 529–534 of `_review_plan.py`: the `if reviews and all(r["verdict"] == "ERROR" for r in reviews): errors_summary = ...; raise ReviewError(f"All sub-reviews failed: {errors_summary}")` lines. The function falls through to the existing `aggregate_verdict([r["verdict"] for r in reviews])` call which already maps ERROR → `REQUEST_CHANGES`, so an all-ERROR run returns a valid `ReviewResult(verdict="REQUEST_CHANGES", reviews=[…ERROR entries…])` and the CLI prints valid JSON. No other lines change in this card; the surrounding `aggregate = aggregate_verdict(...)` line and onward stay as-is. This is the load-bearing prerequisite for the SKILL.md step 4.5 ERROR-only retry that B08 adds — without removing this raise the orchestrator has no JSON to evaluate.
- **Commit:** `fix(review-plan): drop total-fail raise so all-ERROR run emits JSON (#84)`

### Card 18: Tests for `_review_plan.run` integration

- **Reads:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add tests covering each of cards 14–17. Use the existing `_reviewer_test_stub` plus the existing `_make_plan_fixture` / `_make_overview` / `_make_batch_file` helpers in `test-review-plan-flow.py`; extend the helpers as follows: (i) extend `_make_batch_file` to accept a `deletes` keyword argument (default `None → "none"`) emitting `- **Deletes:**` content next to existing `Reads/Modifies/Creates`; (ii) extend `_make_plan_fixture` so the returned `cfg` includes a top-level `"llm": {"bulk_timeout": None, "holistic_timeout": None}` block (None passes through to the reviewer-default `timeout` kwarg added in B01 Card 7) — Card 14 reads these keys unconditionally, so without this fixture update every existing test in the file breaks with `KeyError`; (iii) update existing tests 6 and 7's exact-equality assertions on `retry_kwargs` to expect the additional `"timeout": None` key the stub now captures (per B01 Card 7's stub signature change). (a) all-ERROR returns valid `ReviewResult` — monkey-patch `stub.run = lambda *a, **kw: (_ for _ in ()).throw(LLMError("seeded boom"))` (or define a named `_raises_llmerror(*a, **kw)` function and assign it to `stub.run`) inside a `try/finally` that restores the original `stub.run` afterwards; assert `plan_run` returns `ReviewResult(verdict="REQUEST_CHANGES", reviews=[…each entry verdict==ERROR…])` rather than raising `ReviewError`. (b) mid-round resume — pre-populate `reviews_dir` with two per-batch round-1 files (one APPROVE, one REQUEST_CHANGES — fixtures inline; matching the `RE_BATCH` filename shape) and no holistic round-1 file; seed the stub with one APPROVE response (for the holistic only); call `plan_run`; assert the stub's `captured_prompts()` length is exactly 1 (only the holistic was called); assert the returned `reviews[]` has 3 entries — the two disk-loaded per-batch + the new holistic — and the verdicts from disk are preserved. (c) deletes surface — fixture batch declares `Deletes:` token `\`old/file.py\``; assert the stub's first captured prompt contains `## Intentionally deleted` and the substring `old/file.py`. (d) timeout plumbing — use a single-batch fixture (one `batch_specs` entry) so `captured_prompts()` ordering is deterministic; ThreadPoolExecutor completion order across multiple batches would otherwise scramble the per-batch index. Override the fixture's cfg via `cfg["llm"]["bulk_timeout"] = 900` and `cfg["llm"]["holistic_timeout"] = 1800` (the helper added the keys with `None`; this test overrides them); call `plan_run`; assert `captured_prompts()[0][1]["timeout"] == 900` (the single per-batch call) and `captured_prompts()[1][1]["timeout"] == 1800` (the holistic call). Existing tests in the file must continue to pass after the fixture-helper updates — extend, don't replace.
- **Commit:** `test(review-plan): cover ERROR-only, resume, deletes, timeouts`

## Batch Tests

`uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"` — `test-review-plan-flow.py` covers Cards 14–18; `test-review-common.py` (from B01) provides regression coverage for the helpers this batch consumes. The whole suite must be green at end of batch.
