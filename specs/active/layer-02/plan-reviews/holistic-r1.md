# Plan Review — Layer 02 (holistic, r1)

```yaml
reviewer: claude-sonnet-4-6 (via Agent tool)
reviewed_plan: specs/active/layer-02/plan/
mode: holistic
date: 2026-04-20
round: 1
```

---

## Findings

### [BLOCKING] `ReviewResult` dataclass missing from Batch 01 — deferred to Batch 04

**Section:** Batch 01 (Step 1) / Batch 04 (Step 8)

**Issue:** Step 8 says "Add `ReviewResult` dataclass … to `_review_common.py` as part of this batch." But Steps 9/10/11 (`depends-on: [8, 3, 4]`) all import `ReviewResult` from `_review_common.py`. This is fine. The problem is that Step 1 (which creates `_review_common.py`) does NOT include `ReviewResult` — meaning `_review_common.py` as created by Batch 01 is missing the dataclass. Any smoke test run after Batch 01 that tries to import `ReviewResult` will fail. More critically, the `Reads:` for Steps 9/10/11 lists `scripts/_review_common.py` but `ReviewResult` will only be present after Step 8. The sequencing is technically correct (Step 8 `depends-on: [1]`) but the plan writer must know to add the dataclass in Step 8, not Step 1. This is a minor completeness gap in Step 1's requirements but it creates a real risk: an implementer of Step 1 may omit scaffolding that Step 8 then needs to extend, or may be confused by the overlap between what Step 1 creates and what Step 8 modifies.

**Suggested fix:** In Step 1's `Requirements:` list, add a note: "Do NOT include `ReviewResult` here — it is added by Step 8." Also add to Step 8's first sentence: "`ReviewResult` was intentionally left out of Step 1 to keep Batch 01 pure of dataclass concerns." This makes the split explicit and removes ambiguity.

---

### [BLOCKING] `_render.render()` signature mismatch in `render_prompt`

**Section:** Batch 01, Step 1 — `render_prompt` requirement

**Issue:** The plan specifies `render_prompt` calls `_render.render(template_path, uppercased_tokens)`. Looking at the actual `_render.py` in the repo (confirmed by reading the file), `render(template_path, values)` takes the `values` dict as the second positional argument — that part is correct. However, the plan does not mention that `_render.render` raises `KeyError` with the message `"Unresolved template tokens: [sorted list]"` (not a single key). The plan's test scenario says `render_prompt(...)` raises `KeyError` on unresolved tokens — but the plan's `parse_verdict` requirement says `raise ReviewError(...)` with a ReviewError. This is internally consistent. The issue is that `render_prompt` is specified to call `_render.render(template_path, uppercased_tokens)` but does not mention catching the `KeyError` from `_render` and re-raising it (or letting it propagate). The plan is silent on this. An implementer may either swallow it, wrap it in ReviewError, or let it propagate as raw `KeyError`. The discussion does not specify, but consistency with the rest of the error model (the API catches `ReviewError` only) suggests it should propagate as `KeyError` (a programming error, not a runtime config error). This must be clarified so all three backends handle it the same way.

**Suggested fix:** Add to Step 1's `render_prompt` requirement: "Let `KeyError` from `_render.render()` propagate unwrapped — it indicates a template/token mismatch that is a programming error, not a user error. The API does not catch `KeyError`."

---

### [BLOCKING] `review_output_path` token passed as `reviews_dir` (a directory) rather than the final file path

**Section:** Batch 04, Steps 9/10/11

**Issue:** In Steps 9 and 10 and implicitly Step 11, `render_prompt(...)` is called with `review_output_path=str(reviews_dir)`. The discussion's Task Flow 1 shows `review_output_path=<derived>` with a note that this is "informational only — where the backend will write it." The schema (`review-output.schema.md`, Step 7) includes `reviewed_file:` in frontmatter. But passing the *directory* (not the eventual file path) for `<REVIEW_OUTPUT_PATH>` means the LLM's template instruction ("the backend will write the review to `<REVIEW_OUTPUT_PATH>`") gives the reviewer a directory path, not a file path. The actual file name is only known after `write_review_file()` returns (because the timestamp is chosen then). This is an inherent tension. However, the plan should at minimum acknowledge this and specify what value to pass: either a placeholder path like `<reviews_dir>/<expected-filename>` computed before the call (which is possible since the timestamp can be computed once per backend run), or simply the directory. Passing the directory silently degrades the template's usefulness. Steps 9, 10, and 11 all pass `str(reviews_dir)` without noting the limitation.

**Suggested fix:** In Steps 9, 10, and 11, add a note: "Compute the canonical output path before rendering using the current UTC timestamp (same timestamp used by `write_review_file`), and pass it as `review_output_path`. Store the timestamp in a local variable so `write_review_file` uses the same value." Alternatively, explicitly state: "Passing `reviews_dir` (the directory) is intentional and acceptable for informational purposes — the template should say 'a file in `<REVIEW_OUTPUT_PATH>`'."

---

### [BLOCKING] `check_mode` error message is inverted relative to the discussion

**Section:** Batch 04, Step 8 — `check_mode` requirement

**Issue:** Step 8 specifies:
```
check_mode(reviewer, expected_mode, review_type) → None
raise ReviewError(f"No {reviewer.MODE} template exists for {review_type} review")
```

The discussion specifies the error message as:
```
"No bulk template exists for discussion review. Configure a tool-use reviewer."
```

The plan's formulation uses `reviewer.MODE` (the reviewer's declared mode) in the error message, not `expected_mode`. If the reviewer is `bulk` but `tool-use` is expected (e.g. for discussion), the message becomes `"No bulk template exists for discussion review"` — which is arguably the right thing to say ("we have no bulk template for discussion"), but the discussion's message suggests the message names the *incompatible* mode, not what is expected. This is close to correct, but the message in the plan does not include the second sentence "Configure a tool-use reviewer." from the discussion. More critically, the plan should explicitly state what `reviewer.MODE` vs `expected_mode` are in the error context so the message reads correctly in both directions (bulk-on-tool-use-only type, and tool-use-on-bulk-only type). Currently an implementer might get confused about which variable names which in the f-string.

**Suggested fix:** Rewrite the requirement as: "On mismatch (reviewer.MODE != expected_mode), raise `ReviewError(f'No {reviewer.MODE} template exists for {review_type} review. Configure a {expected_mode} reviewer.')`". This exactly matches the discussion's intent and covers both directions.

---

### [BLOCKING] Step 10 `depends-on` missing Step 4 (templates dependency)

**Section:** Batch 04, Step 10 — `depends-on`

**Issue:** Step 10 (`_review_plan.py`) has `depends-on: [8, 3]`. Step 3 is the reviewer module. The plan review backend calls `render_prompt("review-plan-batch", ...)` and `render_prompt("review-plan-holistic", ...)` — both template files are created in Steps 5 (plan-batch + plan-holistic templates). Step 5 is in Batch 03. The `depends-on` for Step 10 should include Steps 5 (plan templates) in addition to Step 8 and Step 3. In the current plan, Steps 4 through 7 are the template steps; Step 5 specifically creates the plan templates. Without an explicit `depends-on: [5]`, an implementer could theoretically implement Step 10 before Step 5 and encounter a missing template at test time.

Similarly, Step 11 (`_review_code.py`) has `depends-on: [8, 3]` and calls `render_prompt("review-code-single", ...)` / `render_prompt("review-code-multi", ...)` — those templates are created in Step 6. Step 11 should include `depends-on: [6]`.

Step 9 (`_review_discussion.py`) has `depends-on: [8, 3, 4]` — Step 4 is the discussion template; this is correct.

**Suggested fix:** Change Step 10's `depends-on` to `[8, 3, 5]`. Change Step 11's `depends-on` to `[8, 3, 6]`.

---

### [BLOCKING] `_load_config` placement is unresolved — creates Batch 04/05 ambiguity

**Section:** Batch 05, Step 13

**Issue:** Step 13 says "`_load_config(wiki_root, mill_dir)`: small helper (could live in `_review_common.py` as part of Batch 04 or here — decide during implementation)." The discussion's API contract shows `cfg = load_config(wiki_root, mill_dir)` called by the API script. But Step 8 (which extends `_review_common.py`) does not include `load_config` in its requirements. If `load_config` is placed in `_review_common.py`, Step 8 must add it; if placed inline in each API script, Step 13 must define it once and avoid duplication. An implementer of Step 13 faces an ambiguous choice with no guidance on the correct answer. This is an unimplementable card detail.

**Suggested fix:** Resolve the placement now: place `load_config` in `_review_common.py` (Step 8, since that is the batch that extends the file). Add it to Step 8's requirements with signature `load_config(wiki_root: Path, mill_dir: Path) -> dict`. Remove the "decide during implementation" note from Step 13.

---

### [BLOCKING] Integration test for code review uses a `.patch` file approach that is incompatible with the backend's `git merge-base` requirement

**Section:** Batch 06, Step 16

**Issue:** Step 16 says to create a scratch git repo in `$tmp/project/`, commit a base file, and apply the sample diff as a new commit on a task branch. The `_review_code.py` backend runs `git merge-base main HEAD` — this requires the scratch repo to have a `main` branch AND a different `HEAD` branch. The test setup as described: "commit a base file, apply the sample diff as a new commit on a task branch" — but the script does not explicitly say to (a) rename the initial commit's branch to `main`, and (b) create and checkout a new task branch for the applied patch. Without these steps, `git merge-base main HEAD` will fail or return the wrong result (if HEAD is already on main, `git diff <base>..HEAD` is empty). This is an underspecified fixture setup that will fail silently or produce an empty diff on the first attempt.

**Suggested fix:** Add explicit fixture setup steps to Step 16: "(a) Initialize repo; (b) commit base file on `main` branch (`git checkout -b main` or `git init --initial-branch=main`); (c) create task branch (`git checkout -b task`); (d) apply the diff as a commit. This ensures `git merge-base main task` is the initial commit and `git diff <base>..HEAD` yields the expected diff."

---

### [NIT] Batch 03 claims it "runs in parallel with Batch 01" but the batch-depends graph doesn't show this

**Section:** Batch 03 header / 00-overview.md Batch Graph

**Issue:** Batch 03's context says "No Python dependency. Batch runs in parallel with Batch 01." The `00-overview.md` batch graph shows `templates: depends-on: []` and `foundation: depends-on: []`, which is correct (both are independent). But the statement in Batch 03 should read "runs in parallel with Batch 01 **and Batch 02**" — since Batch 02 (reviewers) also depends on Batch 01, and templates are fully independent. Minor wording issue only.

**Suggested fix:** Change "Batch runs in parallel with Batch 01" to "Batch runs in parallel with Batches 01 and 02."

---

### [NIT] Step 2 `run_tool_use` tool list is undecided — "Write" mention is confusing

**Section:** Batch 01, Step 2 — `run_tool_use` requirement

**Issue:** The requirement says `--allowedTools Read,Grep,Write` then immediately notes "wait — Write is allowed generally but templates instruct the reviewer NOT to use it ... Decision to confirm during implementation: exact tool list. Start with `Read,Grep,Glob` (read-only)." The plan's own text contradicts itself within the same bullet. The discussion also says `Read,Grep,Write` in the architecture but the "who writes the review file" section explicitly says the LLM should not use Write. The plan should pick one and state it clearly rather than leaving it to implementation-time discovery.

**Suggested fix:** Remove the parenthetical contradiction. State: "Tool list: `Read,Grep,Glob` (read-only). The template explicitly prohibits the LLM from using Write on the review output file; allowing Write via CLI flag is unnecessary risk. This is the v2 default."

---

### [NIT] `discover_round` spec in Step 1 is incomplete for the "plan" type cross-type scenario

**Section:** Batch 01, Step 1 — `discover_round` requirement

**Issue:** The step says "try `RE_BATCH`; if match AND `review_type == 'plan'`, record `n`." But it also says "try `RE_SIMPLE` first; if match AND `type` group equals `review_type`, record `n`". For the plan type, `RE_SIMPLE` matches files like `20260418-143300-plan-review-r1.md` (holistic). `RE_BATCH` matches `20260418-143300-plan-review-01-setup-r1.md`. Both contribute to the round count for plan. The spec is accurate here. However, it does not specify what happens when `review_type == "discussion"` and a `RE_BATCH` match is found — the spec says "if match AND `review_type == 'plan'`" which correctly ignores batch files when reviewing code or discussion. This is correct but subtle. The test scenario for `discover_round` in Step 1 does not include a case where `review_type="discussion"` and a `plan-batch` file is in the reviews dir, confirming the non-plan batch files are ignored. Adding this case would strengthen the test suite.

**Suggested fix:** Add test scenario to Step 1: "Edge: `discover_round(reviews_dir, 'discussion')` where `reviews_dir` contains a plan-batch file → batch file is ignored, returns correct round for discussion only."

---

### [NIT] `write_review_file` filename logic for plan-holistic vs plan-batch is under-specified

**Section:** Batch 01, Step 1

**Issue:** The requirement says: "For plan batches (`scope` is a batch name like `'01-setup'` and `review_type == 'plan'` and scope != 'holistic'): `<ts>-plan-review-<scope>-r<N>.md`. For plan holistic (`scope == 'holistic'` and `review_type == 'plan'`): `<ts>-plan-review-r<N>.md`." This logic is correct per the discussion. But the condition "scope is a batch name" implicitly assumes no batch is ever named `"holistic"` — the discussion's regex constraint (`[a-z0-9-]+`) does not exclude that. The plan should add a note that `"holistic"` is a reserved scope name and batch files in `plan/` must not use it.

**Suggested fix:** Add: "Note: `'holistic'` is a reserved scope value. Batch files must not have the stem `'holistic'`."

---

### [NIT] Step 12 `depends-on: [1]` — should depend on Backends batch (Step 8 at minimum)

**Section:** Batch 05, Step 12

**Issue:** Step 12 (adding the config to `wiki/config.yaml`) has `depends-on: [1]` (Step 1, `_review_common.py`). However, the config's `review:` section reviewers refer to `sonnetmax` and `sonnetmax_tool`, which are created in Batch 02 (Step 3). The config depends on all reviewers existing conceptually, though it doesn't technically depend on their Python files. But the smoke-test for Step 12 (`import yaml; assert 'review' in c`) is independent of reviewers. The `depends-on: [1]` is arguably too early — the config change is normally done alongside or after the full stack is in place, since there's no point committing config for a stack that doesn't exist yet. This is a sequencing preference, not a hard error. But since the batch-graph shows `api-and-config: depends-on: [backends]`, the step-level dependency on Step 1 alone looks like an oversight.

**Suggested fix:** Change Step 12's `depends-on` to `[8]` (which transitively includes Batches 01 and 02) so the config is added only after the full foundation + reviewer stack is in place.

---

### [NIT] No test for `load_config` local override merge

**Section:** Batch 05, Step 13

**Issue:** The plan specifies that `_load_config` merges `wiki_root/config.yaml` with optional `mill_dir/config.local.yaml` (local wins). No test scenario validates this merge. It's easy to get wrong (Python dict merge order). Should have at least one key test scenario.

**Suggested fix:** Add test scenario: "Edge: `config.local.yaml` overrides `review.plan.rounds: 1` → merged config has `review.plan.rounds == 1`."

---

### [NIT] 00-overview.md lists `_render.py` and `mill-add.py` in "All Files Touched" but those files are only read, not written

**Section:** 00-overview.md, "All Files Touched"

**Issue:** The list includes `scripts/_render.py` and `scripts/mill-add.py`. These files are read as references (in `Reads:` fields of Steps 1, 3, 13) but are not modified. Including them in "All Files Touched" is misleading — it implies they will be changed, but no step Modifies them.

**Suggested fix:** Remove `scripts/_render.py` and `scripts/mill-add.py` from "All Files Touched". They are read-only references.

---

## Per-batch observations

**Batch 01 (foundation):** Well-structured. The regex patterns are exact and match the discussion. `discover_round`'s RE_SIMPLE-first ordering is faithfully reproduced. The primary issue is that `ReviewResult` is deferred to Batch 04 without stating this explicitly in Batch 01, risking implementer confusion. The `_subprocess_util.py` reference is correct — the file exists and provides exactly the subprocess wrapper the plan assumes.

**Batch 02 (reviewers):** Tight and correct. The two-line reviewer files exactly match the discussion's code examples. `LLMError` propagation is correctly specified (do not catch). No issues.

**Batch 03 (templates):** Template token sets match the discussion's token inventory exactly. The instruction to lift from v1 legacy prompts is pragmatic. The `review-output.schema.md` in Step 7 is well-specified. No missing tokens identified. The parallelism note is accurate (no Python deps). Minor wording NIT noted.

**Batch 04 (backends):** The most complex batch. The main issues cluster here: the `check_mode` error message inversion, the `review_output_path` directory-vs-file tension, and the missing template step numbers in `depends-on` for Steps 10 and 11. The parallel `ThreadPoolExecutor` guard for empty batch_files is correctly specified. The "all-sub-reviews-failed" path for discussion (raising `ReviewError` rather than returning a partial ReviewResult) is correctly handled. The `parse Reads:/Modifies:/Creates:` specification in Step 10 extends the discussion (which only mentions `Reads:/Modifies:`) — adding `Creates:` is reasonable but diverges slightly from the discussion; note this is a minor extension, not a conflict.

**Batch 05 (API and config):** Solid overall. The unresolved `_load_config` placement is the main gap. The three API scripts follow the discussion's pattern faithfully. The null-argument CLI design is correctly implemented. The `depends-on: [9, 10, 11]` for Step 13 is correct.

**Batch 06 (integration tests):** Good coverage of happy + error + edge scenarios per review type. The code-review test setup for `git merge-base` is the key gap (branch naming not fully specified). PowerShell fixture setup is appropriate for the Windows environment. The assertions (exit 0, JSON shape, file existence, frontmatter verdict match) exactly match the discussion's "Integration test assertions" section.

---

## Verdict

REQUEST_CHANGES

Six BLOCKING issues must be resolved before implementation begins: (1) `ReviewResult` split between Step 1 and Step 8 needs explicit documentation to prevent implementer confusion; (2) `render_prompt`'s `KeyError` propagation policy must be stated; (3) `review_output_path` token must pass a file path or the limitation must be acknowledged; (4) `check_mode` error message uses wrong variable and is missing the second sentence from the discussion; (5) Steps 10 and 11 are missing template step numbers in their `depends-on` lists; (6) `_load_config` placement is left unresolved and will block Step 13 implementation.
