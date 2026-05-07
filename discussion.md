# Discussion: 24 (A) — mill-misc-fixes

```yaml
task: 24 (A) — mill-misc-fixes
slug: mill-misc-fixes
status: discussing
parent: main
```

## Problem

A bundle of four small infrastructure bugs, each blocking a slice of mill workflows on Windows. They were filed as separate GitHub issues (#175, #177, #179, #180) and folded into one task because each fix is small and they share the same review/test surface. Why now: every one of them either fails the unit test suite, blocks `mill-plan` runs, or silently degrades operator-visible diagnostics.

The four bugs:

- **A (#179)** — `test-review-plan-flow.py` was not updated when batch-card field names were renamed (`Reads:`/`Modifies:` → `Context:`/`Edits:`). Four unit tests fail. A previous commit (`2ca26bd fix(tests): update fixtures for Context/Edits field rename from parent merge`) caught two test files but missed this one. The `plan-batch.md` template itself, the validator, and `parse_batch_refs` are already on the new names. Two related tests (6, 7) also fail because the test stub gained an `effort` kwarg that those test assertions don't include.
- **B (#177)** — On Windows, `${CLAUDE_PLUGIN_ROOT}` does not expand correctly in Bash-tool subshells when an autonomous agent (mill-plan, mill-go) generates **new** Bash commands referencing it as a shell variable. CC's SKILL.md substitution does work for code copied verbatim from skill text, but agents who construct their own commands re-introduce the literal `${CLAUDE_PLUGIN_ROOT}` and hit `error: a value is required for '--project <PROJECT>'`.
- **C (#175)** — Rate-limit errors from the Claude CLI surface as `ERROR: claude rate-limited (exit 1): ` with no detail. The rate-limit signal is in `result.stdout` (stream-json), but the error builder only reads `result.stderr`, which is empty in this case.
- **D (#180)** — The CC Monitor tool runs bash, not PowerShell, but `mill:cli` SKILL.md only covers the Bash tool's syntax rule. Agents on Windows who follow the global "use PowerShell syntax" instruction can pass PS syntax to Monitor and get exit 127 with no warning.

## Scope

**In:**

- Update `plugins/mill/unit_tests/test-review-plan-flow.py`:
  - `_make_batch_file` helper: rename single-line bullets from `- **Reads:** ...` / `- **Modifies:** none` to `- **Context:** ...` / `- **Edits:** none`. Keep `Creates:`/`Deletes:` as-is. Update the docstring on line 71 so it says `Context:/Edits:/Creates:/Deletes:`.
  - Test 6 assertion (around line 442) and Test 7 assertion (around line 487): expected retry-kwargs dict gains `"effort": None`.
- Update `plugins/mill/integration_tests/fixtures/sample-plan/01-core.md` to use `Context:` and `Edits:` instead of `Reads:` and `Modifies:`.
- Update `plugins/mill/templates/review-code-holistic.md` line 18 (`Reads:`/`Modifies:`/`Creates:` → `Context:`/`Edits:`/`Creates:`).
- Update `plugins/mill/scripts/_llm_claude.py` rate-limit error builder (lines 261-264): when `result.stderr` is empty, fall back to `result.stdout` so the rate-limit message contains the diagnostic stream-json.
- Update `plugins/mill/skills/cli/SKILL.md` PowerShell section: add a bullet stating that the Monitor tool also runs bash, so commands passed to Monitor must use bash syntax even though the user's IDE terminal is PowerShell.
- Update `plugins/mill/skills/cli/SKILL.md` PowerShell section: add a bullet warning that `${CLAUDE_PLUGIN_ROOT}` is a CC template token, not a Bash subshell variable — autonomous agents must copy the resolved path from loaded SKILL.md text rather than reconstruct `${CLAUDE_PLUGIN_ROOT}` references in new Bash commands.
- Change every `${CLAUDE_PLUGIN_ROOT}` occurrence inside fenced code blocks in mill SKILL.md files to `$CLAUDE_PLUGIN_ROOT` (no braces). The brace form may be the form CC's Windows substitution path drops; the un-braced form is more robustly handled.

**Out:**

- No changes to `plan-batch.md` template (already correct).
- No changes to the validator (`_plan_validate.py`) or `parse_batch_refs` (already on new names).
- No changes to test comments that mention `Reads:`/`Modifies:` purely as documentation of legacy behavior (e.g. `unit_tests/test-plan-validate.py` test names like `test_dirty_reads_nonexistent_path`). Renaming test names is churn; test bodies already use the new field syntax.
- No CC-framework changes. Bug B is a Windows-side CC behavior we work around in mill skills, not in CC itself.
- No changes to `_llm_claude.py` beyond the rate-limit error builder. The `_scan_rate_limit` detector and the LLMRateLimitError class are unchanged.
- No new tests for bug C unless the existing rate-limit test (if any) needs updating to assert the stdout snippet appears in the error message. If no such test exists, we add one targeted unit test in `test-llm-claude.py`.
- No changes to the `mill-go` / `mill-plan` SKILL.md polling instructions — they already say `cat <log-path>` (bash), which is correct.

## Decisions

### A1 — Fix all stale `Reads:`/`Modifies:` references in test/integration assets, not just the failing tests

- Decision: Update `_make_batch_file` in `test-review-plan-flow.py`, the integration fixture `01-core.md`, and `review-code-holistic.md` in one batch.
- Rationale: These three files are the remaining holdouts after `2ca26bd fix(tests): update fixtures for Context/Edits field rename from parent merge`. Leaving them stale guarantees a future bug report. Cost is small — three files, three replacements.
- Rejected: Fix only `test-review-plan-flow.py` (the file with red tests). Pros: smallest diff. Cons: integration fixture would silently produce plans the validator rejects when run; review template shows wrong field names to reviewers.

### A2 — Fix tests 6 and 7 by adding `"effort": None` to the assertion, not by removing `effort` from the stub

- Decision: Update the assertions at lines 442 and 487 in `test-review-plan-flow.py` to expect `{"session_id": ..., "resume": True, "timeout": None, "effort": None}`.
- Rationale: The stub's `effort` capture mirrors the real reviewer signature in `_reviewer_sonnetmax.py`. Removing it would make the tests less faithful. The reviewer change is intentional; the test was just not updated.
- Rejected: Drop `effort` from `_reviewer_test_stub.run`. Pros: would not need to change tests 6/7. Cons: stub diverges from reviewer signature, hiding future kwarg-related bugs.

### B1 — Combined SKILL.md edits + brace-form change for `CLAUDE_PLUGIN_ROOT`

- Decision: Two-pronged fix.
  1. Replace every `${CLAUDE_PLUGIN_ROOT}` inside fenced code blocks in mill SKILL.md files with `$CLAUDE_PLUGIN_ROOT` (no curly braces). Plain-text references stay as-is so prose still reads naturally.
  2. Add a bullet to `mill:cli` SKILL.md PowerShell section explaining that `$CLAUDE_PLUGIN_ROOT` is a CC template token resolved at skill-load time, not a Bash subshell variable. Agents who generate new Bash commands must use the resolved literal path (visible in their loaded SKILL.md context), not reconstruct `${CLAUDE_PLUGIN_ROOT}` references.
- Rationale: The brace form may be what trips Windows CC substitution on (a known quirk in some templating engines is curly-brace handling). The un-braced form is the most-supported convention. Even if it doesn't fix the substitution bug directly, the cli-skill bullet teaches agents to recognize and avoid the failure mode. Together these reduce both the substitution-skip surface and the agent-induced reintroduction surface.
- Rejected: Only the cli-skill bullet (no brace change). Pros: smallest diff. Cons: leaves the substitution failure mode in place; agents who don't read or apply the bullet still hit it. Also rejected: have the agent run a Python helper to resolve the plugin root via `__file__`. Pros: 100% reliable. Cons: requires PYTHONPATH to be set in the subshell, which CLAUDE.md flags as not always inherited on Windows; would add a multi-line preamble to every Bash block in SKILL.md.

### B2 — Scope of the brace-form change

- Decision: Apply the `${CLAUDE_PLUGIN_ROOT}` → `$CLAUDE_PLUGIN_ROOT` change inside fenced bash code blocks across `plugins/mill/skills/*/SKILL.md` and `plugins/codeguide/skills/*/SKILL.md`. Plain-prose mentions stay braced (consistent with markdown conventions for env-var styling).
- Rationale: codeguide skills are subject to the same Windows CC substitution behavior as mill skills, and they live in this same plugin tree. Skipping codeguide leaves a known-broken pattern for the next person who copies a snippet.
- Rejected: Mill-only scope. Pros: smaller diff. Cons: codeguide and mill share the substitution bug; fixing one and not the other is inconsistent.

### C1 — Use `stdout` as fallback for rate-limit error message

- Decision: Change line 261 from `stderr_snippet = (result.stderr or "")[:500]` to `stderr_snippet = (result.stderr or result.stdout or "")[:500]` (rename the local to `error_detail` for clarity).
- Rationale: The `_scan_rate_limit` function detects rate-limiting from stdout stream-json; the stderr is empty in that case. Falling back to stdout means the error message carries the actual rate_limit_event JSON, which is the most relevant diagnostic available. The 500-char cap protects log readability.
- Rejected: Extract only the `rate_limit_event` line from stdout. Pros: cleaner error message. Cons: more code, and if the format changes (e.g. `is_error: true` with `subtype: "rate_limited"` instead of a top-level event), the extractor breaks while the simple fallback still surfaces the raw signal. YAGNI.

### C2 — Apply the same fix to non-rate-limit errors

- Decision: Apply the same fallback-to-stdout pattern at lines 266-270 (LLMSessionError and the generic LLMError raises). All three branches use `stderr_snippet`; centralize by computing `error_detail = (result.stderr or result.stdout or "")[:500]` once before the branches.
- Rationale: The stderr-empty / stdout-has-detail pattern can plausibly occur for other claude-CLI failure modes (e.g. when the CLI emits an error event in stream-json but the process exits non-zero without writing stderr). Defensive fallback is consistent across all error paths and removes a class of empty-message bugs we'd otherwise discover one at a time.
- Rejected: Only fix the rate-limit branch. Pros: smallest diff, exact match to the bug report. Cons: invites the same bug to recur on the other branches the next time stderr is empty.

### D1 — Single-line addition to `mill:cli` SKILL.md, not a per-skill instruction

- Decision: Add a bullet to the existing PowerShell section in `mill:cli` SKILL.md: "Commands CC executes via the Monitor tool: use bash syntax — Monitor runs bash, not PowerShell."
- Rationale: `mill:cli` is the canonical place for shell-tool guidance. Adding the rule there means it covers all skills that use Monitor (current and future) without duplicating instructions. The SKILL.md is loaded on startup per the conversation skill's table.
- Rejected: Add the instruction inline in `mill-go` and `mill-plan` SKILL.md polling sections. Pros: in-context where the bug occurs. Cons: duplicated in multiple places, has to be repeated for each new skill that uses Monitor, and `mill:cli` is the documented owner of shell-tool guidance.

### Cross-cutting — Single PR / batch structure

- Decision: One PR, one task. Group fixes into batches by file area:
  - **Batch 1 — test fixtures** (bug A test side): `test-review-plan-flow.py`, `01-core.md`, `review-code-holistic.md`.
  - **Batch 2 — runtime + SKILL.md** (bugs B, C, D): `_llm_claude.py`, `cli/SKILL.md`, the `${CLAUDE_PLUGIN_ROOT}` → `$CLAUDE_PLUGIN_ROOT` sweep across SKILL.md files.
- Rationale: Bugs are independent fixes but share review surface (same operator, same area of the codebase). A single PR is faster to review than four. Splitting batches by file area avoids one batch touching the full surface.
- Rejected: Four separate PRs. Pros: each fix bisectable. Cons: 4× PR overhead for changes a reviewer reads in five minutes total.

## Technical context

### Files involved

**Bug A — test fixtures:**

- `plugins/mill/unit_tests/test-review-plan-flow.py` — `_make_batch_file` (lines 64-85), test 6 assertion (line 442), test 7 assertion (line 487).
- `plugins/mill/integration_tests/fixtures/sample-plan/01-core.md` — lines 25-26 use old field names.
- `plugins/mill/templates/review-code-holistic.md` — line 18 mentions `Reads:`/`Modifies:`/`Creates:` in the holistic-review prompt.

**Bug B — `${CLAUDE_PLUGIN_ROOT}` brace form + cli skill:**

- `plugins/mill/skills/cli/SKILL.md` — PowerShell section gets one new bullet (or possibly two, see D1).
- All `plugins/mill/skills/*/SKILL.md` and `plugins/codeguide/skills/*/SKILL.md` files: replace `${CLAUDE_PLUGIN_ROOT}` with `$CLAUDE_PLUGIN_ROOT` inside fenced ```bash code blocks. A grep across both subtrees identifies the call sites; expect ~30+ locations.

**Bug C — rate-limit error message:**

- `plugins/mill/scripts/_llm_claude.py` — `_invoke` function around lines 257-270.
- Optional new test in `plugins/mill/unit_tests/test-llm-claude.py` (depends on existing test surface).

**Bug D — Monitor tool guidance:**

- `plugins/mill/skills/cli/SKILL.md` — PowerShell section gets one new bullet covering Monitor (and possibly the same bullet covers B's plugin-root note, see D1).

### Helpers / shared code to reuse

- `_yaml_writer.quote_scalar` — used when writing YAML scalar values that may contain risky characters. The discussion file rendering already uses it; mill-plan will too. No need for new helpers.
- `_scan_rate_limit(stdout)` in `_llm_claude.py` (lines 126-154) — already detects rate-limit signals from stdout stream-json; the bug C fix re-uses this function unchanged and only updates the error-message-construction code that runs after `_scan_rate_limit` returns True.

### Gotchas discovered during exploration

- The validator (`_plan_validate.py`) uses a regex `(Context|Edits|Creates|Deletes)` (line 50) which deliberately does **not** match `Reads:` / `Modifies:`. That is the right behavior; the bug is purely in the test fixture that pre-dates the rename. Do not loosen the validator regex.
- `_make_batch_file` in `test-review-plan-flow.py` uses **single-line** field syntax (`- **Reads:** \`a\`, \`b\`` on one line). When updating, preserve that single-line form. The validator and `parse_batch_refs` both support single-line and multi-line forms; tests rely on single-line to keep fixtures terse.
- The `cards: 1` count in `_make_batch_file`'s yaml block is informational, not validated. The validator counts cards by parsing `### Card N:` headings, not by reading the yaml `cards:` value. No change needed.
- `_subprocess_util.run` already captures both stdout and stderr (lines 75-83) — the bug C fix is purely in how the captured strings are used in the error builder.
- The `run_in_background: true` on the Bash tool routes output to CC's temp dir, which the SKILL.md instructions explicitly forbid. The `millpy-bg.py` worker is the project-local equivalent — its log path is under `<worktree>/.millhouse/bg/`.

## Constraints

- **Do not change the validator's accepted field names.** `Context:`, `Edits:`, `Creates:`, `Deletes:` are canonical and load-bearing across the validator, `parse_batch_refs`, the plan template, and the plan-overview template.
- **Do not introduce new test helpers for bug A.** The existing `_make_batch_file` is the only fixture-builder; updating it in place is the entire fix on the test side.
- **Bug B's brace-form change must not affect plain-text mentions of `${CLAUDE_PLUGIN_ROOT}` in prose** (Markdown convention is to use braces for env-var styling). Only fenced bash code blocks change.
- **Bug C must not change `_scan_rate_limit`'s detection logic.** The detection already works correctly; only the error-construction code is wrong.
- **Bug D must respect the existing `mill:cli` PowerShell section structure** (bullet list with PS5/bash equivalents). New bullets follow the same one-line format.
- **No CC-framework changes.** The `${CLAUDE_PLUGIN_ROOT}` substitution behavior is owned by Anthropic's CC; we work around it in plugin SKILL.md files.

## Testing

**Bug A — test fixtures:**

- TDD candidate: re-running `python plugins/mill/unit_tests/test-review-plan-flow.py` after the fixture update is the verify step. Pre-fix: 4 failures (tests 4, 5, 6, 7). Post-fix: 0 failures. No new test cases are added — the existing tests are the regression net.

**Bug B — `${CLAUDE_PLUGIN_ROOT}` SKILL.md sweep:**

- No new automated tests. The verify step is `git grep -n '\${CLAUDE_PLUGIN_ROOT}' plugins/mill/skills plugins/codeguide/skills` returning only matches inside HTML comments, plain prose, or quoted-pattern lines (any remaining matches must be inspected manually). The `mill:cli` skill update is verified by reading the resulting bullet and confirming it matches the existing format.

**Bug C — rate-limit error message:**

- Add one targeted unit test in `plugins/mill/unit_tests/test-llm-claude.py` that monkey-patches `_subprocess_util.run` to return a `CompletedProcess` with `returncode=1`, `stderr=""`, and `stdout` containing a synthetic `{"type":"rate_limit_event",...}` JSON line. Assert the raised `LLMRateLimitError`'s message contains a non-empty detail snippet derived from stdout. The existing `_scan_rate_limit` tests (if any) cover detection; this new test covers error-message construction.

**Bug D — Monitor tool guidance:**

- No automated tests. Verify by reading the resulting `mill:cli` SKILL.md bullet.

**Cross-cutting:**

- Run the full unit test suite (`python plugins/mill/unit_tests/run-all.py`) at the end of each batch to catch any regression introduced by the fixture/source changes. Pre-fix: 1 of 47 test files fails (`test-review-plan-flow.py` — 4 of its test cases fail: tests 4, 5, 6, 7). Post-fix: 47/47 test files passing.

## Q&A log

- **Q:** Should the integration fixture `01-core.md` and the holistic review template `review-code-holistic.md` (which still mention `Reads:`/`Modifies:`) be in scope, or only the directly-failing test? **A:** In scope — recommended fix-all to prevent the rename from leaving more stale corners.
- **Q:** Should bug B's fix change `${CLAUDE_PLUGIN_ROOT}` to `$CLAUDE_PLUGIN_ROOT`, add a CLAUDE.md note, or document in `mill:cli`? **A:** Both — the brace-form change in fenced code blocks across SKILL.md files, plus a `mill:cli` bullet that explains why agents should not reconstruct `${CLAUDE_PLUGIN_ROOT}` references. No CLAUDE.md edit; `mill:cli` is the canonical home for shell-tool guidance.
- **Q:** Should the rate-limit error message use `result.stdout` raw (verbose) or extract only the rate_limit_event line? **A:** Use the simple `stderr or stdout` fallback. The 500-char cap protects readability; extraction adds a fragility that doesn't pay off.
- **Q:** Should bug D's fix add a Monitor-tool bullet to `mill:cli`, or update individual mill-go/mill-plan SKILL.md polling sections? **A:** Add to `mill:cli` only — that's the canonical owner of shell-tool guidance.
- **Q:** Should bug C's `stderr or stdout` fallback also apply to the LLMSessionError and generic LLMError branches, or only the rate-limit branch? **A:** All three branches — extract `error_detail` once before the if/elif/else and reuse. The bug pattern (empty stderr but useful stdout) is not unique to rate-limit.
