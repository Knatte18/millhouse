# Plan Review — Layer 02 (holistic, r2)

```yaml
reviewer: claude-sonnet-4-6 (via Agent tool)
reviewed_plan: specs/active/layer-02/plan/
mode: holistic
date: 2026-04-20
round: 2
```

## Findings

### [NIT] `run_tool_use` allows `Glob` in the plan but the discussion says `Read,Grep,Write`

**Section:** `02-reviewers.md` / `01-foundation.md` Step 2 vs. `discussion.md` "Reviewer → LLM-provider"

**Issue:** The discussion's CLI call reads `--allowedTools Read,Grep,Write` for tool-use mode. Step 2 in `01-foundation.md` specifies `--allowedTools Read,Grep,Glob`. The plan also drops `Write` (intentionally; it adds `Glob`). The plan's rationale is sound (read-only tools, `Glob` is useful for file discovery) but the discrepancy with discussion.md decision 33 / the tool-use section should be noted as a deliberate deviation, not an inconsistency.

**Suggested fix:** Add a one-line note in Step 2 that this is a deliberate choice over the discussion draft (`Glob` instead of `Write`; `Write` was rejected per "always the backend" decision). No code change needed.

---

### [NIT] `discover_round` cross-type isolation: batch files for "code" type are silently handled but the spec only mentions "plan"

**Section:** `01-foundation.md` Step 1, `discover_round` requirements

**Issue:** The plan's `discover_round` correctly ignores batch files when `review_type != "plan"`. But `RE_BATCH` matches `plan-review-<batch>` filenames exclusively — it could never match a `code-review-...` or `discussion-review-...` filename anyway. The isolation is thus guaranteed structurally, not just by the `review_type == "plan"` guard. The test scenario "cross-type isolation" is still worth having, but the implementation note overstates the risk.

**Suggested fix:** Minor clarification in Step 1 note; no logic change.

---

### [BLOCKING] `_review_code.py` has no handling for the "on main, no diff" edge case at the `git merge-base` level — only the `diff` level is checked

**Section:** `04-backends.md` Step 11, Key test scenarios

**Issue:** Step 11 lists the scenario "running on `main` (no diff) → raise ReviewError". However, `git merge-base main HEAD` on `main` returns the current commit (HEAD == merge-base), so `git diff <sha>..HEAD` produces an empty diff string rather than an error. The plan says "raise `ReviewError(...)`" but no guard is specified for an empty diff in the requirements body — only in the scenario name. The actual guard (check `if not diff.strip()` → raise ReviewError) is not written out.

**Suggested fix:** Add to Step 11 requirements: after computing `diff`, check `if not diff.strip(): raise ReviewError("No diff between <base>..HEAD — are you on a task branch?")`. This should appear in the numbered implementation steps, not just in the test scenarios.

---

### [BLOCKING] `_review_code.py` Step 11 uses `project_root / p` for touched files, but `git diff` outputs repo-relative paths — the cwd used for the subprocess is unspecified

**Section:** `04-backends.md` Step 11, requirement step 8

**Issue:** Step 11 runs `git merge-base main HEAD` and `git diff <base>..HEAD` via `subprocess.run`. The plan does not specify the `cwd` for these subprocess calls. If invoked from `project_root`, it works. If invoked from `plugins/mill/scripts/` (where the script lives), git would look for a repo there (which may or may not be the project repo). Step 8 then constructs `project_root / p` for touched files — which relies on `project_root` being the repo root. This is stated as `Path.cwd()` in the API template (Step 13), but the backend itself receives `project_root` as a parameter; the actual subprocess `cwd` for the git commands is not stated.

**Suggested fix:** Add `cwd=project_root` to the `subprocess.run` calls for `git merge-base` and `git diff` in Step 11's requirements. One line of clarity.

---

### [BLOCKING] `load_config` in Step 8 references `ref-v1-reuse.md` for YAML parsing, but that file is not in scope — and PyYAML availability is not confirmed

**Section:** `04-backends.md` Step 8, `load_config` requirements

**Issue:** The requirement says "Use PyYAML if available; otherwise lift `_parse_yaml_mapping` from v1's `core/config.py` per `ref-v1-reuse.md`." `ref-v1-reuse.md` is not listed in any `Reads:` entry for this batch, and the discussion does not reference it. The fallback path is vague ("lift … if available"). The plan should either commit to PyYAML as a hard dependency (acceptable for a Python 3.11+ dev environment) or specify the exact fallback. Leaving it as "or maybe lift from v1" is not implementable without guessing.

**Suggested fix:** Declare PyYAML as a required dependency (it is a standard PyPI package available in the project's Python environment). Remove the vague v1-fallback. If the project has a `requirements.txt` or similar, add `pyyaml` there and note it in the step.

---

### [NIT] `write_review_file` uses `datetime.utcnow()` which is deprecated in Python 3.12+

**Section:** `01-foundation.md` Step 1

**Issue:** The requirement specifies `datetime.utcnow().strftime(...)`. This method is deprecated since Python 3.12 (replaced by `datetime.now(timezone.utc)`). On Python 3.12 it still works but emits a `DeprecationWarning`. Given the target environment (Windows 11 with modern Python), this is a NIT but will generate noise.

**Suggested fix:** Use `datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")` instead.

---

### [NIT] Code review integration test (Step 16) sets up the git repo inside `$tmp/project/` but the API scripts derive `project_root = Path.cwd()`

**Section:** `06-integration-tests.md` Step 16

**Issue:** Step 16 creates the git repo at `$tmp/project/` and instructs invoking the script from "the project root". However, the test setup also places `.millhouse/` presumably at `$tmp/.millhouse/` (mirroring Steps 14 and 15). If `Push-Location $tmp/project`, the mill_dir becomes `$tmp/project/.millhouse/` which does not match where the slug file and wiki junction were set up. If the `.millhouse/` is placed inside `$tmp/project/`, this needs to be stated explicitly. The test could be ambiguous about where `Push-Location` lands.

**Suggested fix:** Clarify Step 16 that `.millhouse/`, the wiki junction, and the slug file all live inside `$tmp/project/`, and that `Push-Location $tmp/project` is the invocation directory. One sentence.

---

### [NIT] Discussion review template (Step 4) does not include `<REVIEW_OUTPUT_PATH>` token — but the discussion's placeholder list includes it

**Section:** `03-templates.md` Step 4, `discussion.md` "Templates" section

**Issue:** The discussion lists `<REVIEW_OUTPUT_PATH>` as one of the placeholder tokens available. Step 4 specifies that the discussion template uses: `<TASK_TITLE>`, `<ARTEFACT_PATH>`, `<CONSTRAINTS>`, `<ROUND>`, `<REVIEWER_MODEL>`. The plan's Step 9 (`_review_discussion.py`) also explicitly drops this token with a comment: "No `<REVIEW_OUTPUT_PATH>` token — the backend owns file I/O." This is a deliberate and correct choice, but the discussion's token list is exhaustive across all templates, not per-template. No bug — but worth confirming during template authoring that the schema file does not expect this token either.

**Suggested fix:** Confirm during template authoring. No plan change needed — this is self-consistent.

---

### [NIT] Plan batch backend (Step 10): "Creates:" paths parsed from batch files — parsing heuristic is underspecified

**Section:** `04-backends.md` Step 10

**Issue:** Step 10 specifies that `Reads:`/`Modifies:`/`Creates:` paths are parsed from batch files using "simple line-matching — `- **Reads:** <path>` entries. Handle both backtick-wrapped and plain paths; strip whitespace; split comma-separated if present." The plan also adds `Creates:` to the union for holistic review. However, the existing plan files (including this Layer 02 plan) use the format `- **Reads:** ` `scripts/_render.py`  with backticks. The regex/heuristic for extracting backtick-wrapped paths (especially comma-separated lists with mixed backtick/plain) could produce silent misses. This is a NIT because the parsing is internal and failures just drop paths (with stderr warning), but the heuristic could be made more explicit.

**Suggested fix:** Provide an explicit regex in Step 10, e.g. `re.findall(r"[`']?([^\s`',]+\.\w+)[`']?", line)` or similar. This prevents implementer drift.

---

### [BLOCKING] `_review_plan.py` Step 10: total-fail detection logic is incomplete — holistic failure alone can cause all-ERROR result with no raise

**Section:** `04-backends.md` Step 10, steps 10–11

**Issue:** Step 10 says "If zero sub-reviews succeeded (all ERROR), raise `ReviewError`." The check at step 10 is `aggregate_verdict(...)` then at step 10 "if zero succeeded → raise ReviewError." However, the holistic review runs *after* collecting per-batch results. If all batches succeed but the holistic LLM call fails, the holistic entry would be ERROR, but `all ERROR` check (step 10) counts only the holistic if it is the only failed entry — unless the counting logic explicitly checks across both batch and holistic entries. The "zero sub-reviews succeeded" condition must account for the combined list including holistic. This is implied but not stated: does "zero succeeded" mean zero across the full `reviews[]` list, or zero batches?

**Suggested fix:** Clarify in Step 10 that the `reviews` list assembled at step 9 includes all batch entries AND the holistic entry (if run), and "zero succeeded" means no entry in that combined list has `verdict` of `APPROVE` or `REQUEST_CHANGES` (i.e., all are `ERROR`). Two sentences of clarification.

---

### [NIT] `check_mode` error message in Step 8 inverts the phrasing compared to the discussion

**Section:** `04-backends.md` Step 8

**Issue:** The discussion says the error should read: `"No bulk template exists for discussion review. Configure a tool-use reviewer."` Step 8 specifies: `"No {reviewer.MODE} template exists for {review_type} review. Configure a {expected_mode} reviewer."` When `reviewer.MODE == "bulk"` and `expected_mode == "tool-use"`, this produces: `"No bulk template exists for discussion review. Configure a tool-use reviewer."` — exactly matching the discussion. No bug. This is just a confirmation.

**Suggested fix:** No change.

---

## Summary of Counts

- BLOCKING: 4
- NIT: 6

## Verdict

REQUEST_CHANGES

The plan is substantially complete and internally coherent. Four blocking items need resolution before implementation begins: (1) the empty-diff guard in the code backend needs to be written out as a requirement step, not just a test scenario; (2) the `cwd` for git subprocess calls in `_review_code.py` must be explicitly specified as `project_root`; (3) the `load_config` PyYAML-or-fallback ambiguity must be resolved to a concrete dependency decision; (4) the "all-ERROR" detection logic in `_review_plan.py` needs to explicitly state it counts across all sub-reviews including holistic. Fix these four, and the plan is ready to implement.
