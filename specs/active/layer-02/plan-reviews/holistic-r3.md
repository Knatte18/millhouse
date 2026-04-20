---
review-type: holistic
round: 3
reviewer: independent-plan-reviewer
date: 2026-04-20
verdict: APPROVE
---

# Holistic Plan Review — Round 3

## Summary

The plan is substantially implementable from the cards plus the repo. Round 3
finds no new BLOCKING issues. A small set of NITs remain — low-friction
clarifications that would smooth implementation but do not prevent a
competent writer from producing correct code.

---

## Findings

### [NIT] 01 — `_llm_claude.py` Step 2: tool list deviates from discussion without surfacing as a decision

**Section:** `01-foundation.md` → Step 2, `run_tool_use` requirements.

**Issue:** The card drops `Write` and substitutes `Glob` (`--allowedTools Read,Grep,Glob`). The discussion lists `Read,Grep,Write`. The card flags this as "a deliberate implementation refinement" inline, but it is buried in a NOTE rather than in the plan's Shared Decisions section. A writer implementing Step 2 from this card alone has no trouble, but a reviewer of the written code might raise a spurious conflict against the discussion.

**Suggested fix:** Either promote the `Write → Glob` substitution to a numbered Shared Decision in `00-overview.md`, or add a one-line back-reference note in `00-overview.md`'s "Shared Decisions" section that this refinement is intentional.

---

### [NIT] 02 — Step 8 `check_mode` error message: logic vs. message mismatch

**Section:** `04-backends.md` → Step 8, `check_mode` requirements.

**Issue:** The spec for the error message reads:
```
f"No {reviewer.MODE} template exists for {review_type} review.
 Configure a {expected_mode} reviewer."
```
This is confusing: `reviewer.MODE` is what the reviewer *has*, not what the template needs. If a bulk reviewer is passed to a discussion backend (which needs tool-use), the message would say "No bulk template exists for discussion review" — which is correct, but the phrase "Configure a tool-use reviewer" follows the wrong antecedent. Discussion.md specifies the message format as:
```
"No <mode> template exists for <type> review. Configure a <mode> reviewer."
```
where `<mode>` = `expected_mode` in both places, making the sentence coherent. The plan card uses `reviewer.MODE` in the first slot where `expected_mode` belongs.

**Suggested fix:** Change to `f"No {expected_mode} template exists for {review_type} review. Configure a {expected_mode} reviewer."` — or just surface the mismatch clearly: `f"Reviewer MODE '{reviewer.MODE}' is incompatible with {review_type} review (requires '{expected_mode}')."`.

---

### [NIT] 03 — Step 10 `_review_plan.py`: `root:` frontmatter resolution is underspecified

**Section:** `04-backends.md` → Step 10, per-batch parallel section, item (a).

**Issue:** The card says paths from `Reads:`/`Modifies:`/`Creates:` are resolved "using `root:` from overview frontmatter if set." There is no definition of what `root:` looks like in the frontmatter, whether it is absolute or wiki-relative, or what fallback to use when it is absent. The regex parser is specified, but the resolution step is not.

**Suggested fix:** Add one sentence: "If `root:` is absent from `00-overview.md` frontmatter, resolve paths relative to `project_root`. If `root:` is present, treat it as a path relative to `project_root`." (Or relative to wiki root — whichever is correct. Pick one and name it.)

---

### [NIT] 04 — `_review_code.py` Step 11: `subprocess.run` vs `_subprocess_util.run` inconsistency

**Section:** `04-backends.md` → Step 11, git commands.

**Issue:** The card specifies `subprocess.run([..., "git", "merge-base", ...], cwd=project_root, capture_output=True, text=True, check=True)`. However, the repo has `_subprocess_util.py` which already wraps `subprocess.run` with UTF-8 enforcement, spawn/exit breadcrumbs, and timeout support. `_llm_claude.py` is told to read `_subprocess_util.py` in its Explore section, but the code backend's git calls are specified using raw `subprocess.run`. On Windows this can cause encoding issues (cp1252 fallback on git stderr). Using `_subprocess_util.run` is the Layer 01 convention.

**Suggested fix:** Change the two git calls in Step 11 to use `_subprocess_util.run(["git", ...], cwd=project_root, timeout=30)` — consistent with `_llm_claude.py`'s expected pattern and Layer 01 style.

---

### [NIT] 05 — Integration test Step 16: `git apply` on bare patch may fail without prior file

**Section:** `06-integration-tests.md` → Step 16.

**Issue:** The test creates a scratch git repo, writes a "base file," commits it, then applies `sample-code-diff.patch` via `git apply`. The patch file is not yet specified (it's a fixture yet to be written). If the patch references a file that does not exist in the base commit, `git apply` will fail. The card does not specify what the base file's contents or name should be, nor that the fixture patch must reference it.

**Suggested fix:** Add a note: "The fixture patch must modify a file that exists in the base commit. Create `base-file.py` (or similar) in the base commit and write `sample-code-diff.patch` as a modification of that file." This keeps the test deterministic.

---

### [NIT] 06 — `write_review_file` scope routing: "holistic" scope for code review

**Section:** `01-foundation.md` → Step 1, `write_review_file` requirements.

**Issue:** `write_review_file` is specified to produce `<ts>-plan-review-r<N>.md` when `scope == "holistic"` AND `review_type == "plan"`. But the code backend calls `write_review_file(reviews_dir, "code", round_n, raw)` with no `scope` argument (Step 11 item 11). The function's `scope: str | None = None` defaults to `None`, which routes to `<ts>-code-review-r<N>.md` via the simple-review branch — correct. However Step 11 later says `write file scope="holistic"` in plain text (item 10 note). This contradicts the call in item 11 (no scope kwarg). No real ambiguity for an experienced writer, but worth aligning.

**Suggested fix:** Remove the `scope="holistic"` notation from Step 11 item 10, or make explicit that scope is omitted for code review (matching discussion.md's canonical filename `<ts>-code-review-r<N>.md`).

---

## Edge-case coverage checklist

| Edge case | Covered? |
|---|---|
| `reviews_dir` does not exist on round 1 | Yes — `discover_round` returns 1; `write_review_file` does `mkdir parents` |
| `batch_files` empty (plan with only overview) | Yes — Step 10 guards with `if batch_files` |
| `ThreadPoolExecutor(max_workers=0)` crash | Avoided — pool only created when batch_files non-empty |
| All sub-reviews fail (plan) | Yes — Step 10 total-fail check |
| All sub-reviews fail (discussion, code) | Yes — Step 9/11 raise `ReviewError` on LLMError |
| Empty diff (on main) | Yes — Step 11 empty-diff guard |
| `cwd=project_root` for git | Yes — Step 11 specifies it |
| PyYAML dependency | Yes — Step 8 names `requirements.txt` |
| `<SLUG>` in config paths substituted by `str.replace` not `_render` | Yes — explicitly noted multiple times |
| Round cap check | Yes — all three backends check max_rounds |
| `RE_SIMPLE` matched first, `RE_BATCH` excluded for same file | Yes — Step 1 ordering specified |

All material edge cases from the discussion are covered.

---

## Internal consistency check

- All symbols used by backends (`ReviewResult`, `ReviewError`, `load_reviewer`, `check_mode`, `aggregate_verdict`, `load_config`, `discover_round`, `render_prompt`, `resolve_path`, `write_review_file`, `bulk_files`, `parse_verdict`, `find_active_slug`, `load_task_title`, `read_constraints_md`) are defined in Batch 01/Step 1 or Step 8 before any backend in Batch 04 consumes them. Depends-on graph is correct.
- `LLMError` defined in `_llm_claude.py` (Step 2), imported by backends. Import direction is correct (backend → provider).
- `ReviewResult.to_dict()` defined in Step 1, used by API scripts in Step 13. OK.
- Template token sets match between template specs (Steps 4–6) and backend render calls (Steps 9–11) with one minor exception: Step 9 explicitly drops `<REVIEW_OUTPUT_PATH>` and this is correctly justified by Decision 24/33.
- `load_config` in Step 8 is imported by API scripts in Step 13. Consistent.
- Batch depends-on chain: foundation → reviewers → (templates parallel) → backends → api-and-config → integration-tests. Valid.

---

## Alignment with discussion.md

All major architectural choices in the discussion are faithfully reflected:
- 4-layer architecture, flat file layout, null-arg CLI, MODE on reviewer, backend writes files, ReviewResult shape, partial/total-fail semantics, round discovery with RE_SIMPLE-first ordering, ThreadPoolExecutor for plan, `git merge-base main HEAD` for code diff baseline, `<SLUG>` via `str.replace`, `task_title` from slug frontmatter.

The only intentional deviation (Write → Glob in tool-use allowed-tools) is documented inline in the card. NIT 01 recommends surfacing it more visibly.

---

## Verdict

**APPROVE**

The plan is implementable end-to-end without guessing on any blocking question. Six NITs remain — all are minor: an error-message logic nit, a `root:` resolution gap, a subprocess-style inconsistency, a git-patch determinism note, and two surface-level consistency cleanups. None prevents a writer from producing correct, spec-compliant code.
