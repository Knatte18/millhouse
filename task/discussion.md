# Discussion: 44 (A) — Bug-fix batch 4

```yaml
task: 44 (A) — Bug-fix batch 4
slug: mill-misc-fixes-4
status: discussing
parent: main
```

## Problem

A batch of independent bug fixes accumulated from the 2026-05-09 and 2026-05-11 issue triages. None block any single workflow on their own, but together they erode reliability: mill-go's TodoWrite items are hard to correlate with plan files; reviewer rate-limit hits get mis-classified as `REQUEST_CHANGES` and burn implementer rounds; the merge-in verify-fix sub-agent reports stuck even on success; SKILL.md commands reference paths that no longer exist after the `task/`-on-branch migration; the `wiki-config.yaml` template ships an old design. The fixes are mechanical or shallow, but each one touches a different module or skill, so we batch them under one mill-go run instead of opening 14 separate PRs.

**Why now:** issue queue cleanup before task 46 (Home.md state machine + mill-cleanup split) lands and refactors the surrounding orchestration. Several of these bugs (notably #229, #228) would amplify if folded into 46 unaddressed.

## Scope

**In:**

- **#214** mill-go SKILL.md: replace bare `status.md` with `task/status.md` in the two stale git-add commands (lines 106, 170).
- **#217** Add `.claude/scheduled_tasks.lock` to `.gitignore` so the lockfile stops appearing as untracked.
- **#221** Name `_config.load_config(wiki_path, worktree_root)` inline in mill-start SKILL.md step 3 and mill-plan SKILL.md step 3.
- **#153** Wrap `_llm_claude._invoke` with a single-retry-on-immediate-exit-1 guard (duration < 2s AND empty stdout → one fresh-session retry).
- **TodoWrite batch-number Principle** — add a mill-go SKILL.md Principle prescribing `Implement batch N (<name>)` format.
- **Implement-via-millpy-bg** — update mill-go SKILL.md Execute step 1 (Implement) and step 3-`REQUEST_CHANGES` (fix dispatch) to wrap `millpy-implement.py` invocations in `millpy-bg.py`, matching the reviewer-CLI pattern. Builder reads the final JSON line from the log file instead of stdout.
- **#231** Strengthen `merge-in-verify-brief.md` and `merge-in-conflict-brief.md` to mirror `implementer-brief.md`'s explicit "Anything other than this JSON on the last line is a protocol violation; mill-go treats that as `stuck_type: logic`" sentence.
- **#229** Add a `## Resume` section to mill-go SKILL.md immediately after Execute, documenting the resume playbook per non-terminal batch state (`running` / `reviewing` / `fixing`) including the `--resume` vs fresh-session policy.
- **#228** Change `_review_code.py`: when every entry in `reviews[]` has `verdict: ERROR`, set the top-level `verdict` to `"ERROR"` (instead of `"REQUEST_CHANGES"`). Add a mill-go SKILL.md step 4.5 ("ERROR-only-aggregate retry") mirroring mill-plan's existing step 4.5: re-fire the review CLI without consuming a round; two-pass cap; on second consecutive ERROR-only round, halt with `BLOCKED: code review ERROR-only round N`.
- **#226** Fix unit-test fixtures: the 3 failing review-flow tests (test-review-code-flow, test-review-plan-flow, test-review-discussion-flow per `_review_common.load_config` invariant) must seed `<tempdir>/container/wiki/config.yaml` from `plugins/mill/templates/wiki-config.yaml` so `load_config` passes.
- **#225** Add a stderr warning in `_review_common.parse_blocking_count` (or its caller) when the prose verdict ("Five blocking issues remain") diverges from the heading count.
- **#235** Sync `plugins/mill/templates/wiki-config.yaml` with production conventions: remove `hardlinks:` block, change junction key `.millhouse/wiki` → `.wiki`, drop "Layer 02/03/04" subheading relics from comments, verify `_setup.create_hub_links` reads `cfg.get("hardlinks", {})` gracefully, document the template-mirror rule in CLAUDE.md.

**Out:**

- **#216** (cleanliness module reportedly missing) — verified stale: `plugins/mill/scripts/_cleanliness.py` exists with `compute_new_dirt`. Issue #216 should be closed; no code change.
- **Reviewer terminal-window flash (bullet 8)** — commit `a9d2081` dropped `DETACHED_PROCESS` and kept `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB`. Trust that fix; do not pre-emptively switch to direct `claude.exe` lookup or PowerShell `Start-Process`. If the flash persists after this batch lands, open a follow-up issue.
- Full sync of `wiki-config.yaml` template to production's `paths: task/...` and `review:`/`roles:` schema convergence. Scope is the user-specified subset for #235 only.
- Audit of every `status.md` reference across the SKILLs corpus. Only mill-go SKILL.md is in scope (the two locations grep already identified).
- Restructuring `_review_code.py`'s verdict aggregation beyond the ERROR-only-aggregate change.
- Migration to a typed rate-limit verdict (`BACKEND_FAILURE`) — the top-level `"ERROR"` propagation is enough for the orchestrator's retry logic.

## Decisions

### D1 — #216 declared stale, no code change

- **Decision:** Verify `plugins/mill/scripts/_cleanliness.py` exists with `compute_new_dirt`. It does. Close issue #216 manually after this PR merges; no code or doc change.
- **Rationale:** The bug report predated the module's introduction. Grep confirms the file exists and exposes the API mill-go SKILL.md references (line 93 + 100 signature). Spending plan budget here is waste.
- **Rejected:** Deeper investigation — the grep is conclusive; further digging is theatre.

### D2 — `.gitignore` over relocation for `.claude/scheduled_tasks.lock`

- **Decision:** Add `.claude/scheduled_tasks.lock` to the project `.gitignore` (the repo-root one). Do not move the lockfile.
- **Rationale:** Single-line ignore entry. Moving the lockfile would require updating every consumer (Claude Code itself owns the location; we don't control it).
- **Rejected:** Move to `.scratch/scheduled_tasks.lock` — would diverge from Claude Code's expected location and break the harness contract.

### D3 — Single-retry wrapper for `_llm_claude` immediate-exit-1

- **Decision:** In `_llm_claude._invoke`, when the subprocess exits non-zero AND `duration < 2.0s` AND stdout is empty AND `resume=False`, retry once (fresh session, no `session_id` parameter on the second call). If the second call also fails fast, propagate `LLMError` as before. Add a stderr breadcrumb `[_llm_claude] fast-fail retry`. Do NOT apply the retry when `resume=True` (a fast-fail on resume already raises `LLMSessionError`, which callers expect).
- **Rationale:** The shim's known failure mode is "claude.cmd exits 1 immediately with empty stdout after a prior interrupt". A bounded retry recovers without masking real LLM errors (which take time and produce stderr).
- **Rejected:** Unbounded retry (could mask persistent auth failures), or documentation-only (the bug is reproducible and silent).

### D4 — Reviewer terminal flash: trust a9d2081

- **Decision:** No code change in this batch. Add a one-line `Verify:` instruction in the implementer brief for #153's batch: after running through one mill-go cycle, confirm no terminal flash. If it persists, open a follow-up bug.
- **Rationale:** Commit a9d2081 dropped `DETACHED_PROCESS`. That was the well-known offender. Pre-emptively replacing `cmd /c claude` invites a new class of bugs (direct `claude.exe` lookup fails when PATH is truncated under debugpy, per `_llm_claude._claude_argv_prefix` docstring).
- **Rejected:** Pre-emptive switch to direct `claude.exe` invocation (PATH-truncation risk) or PowerShell `Start-Process` (extra subprocess layer).

### D5 — `millpy-bg` wraps `millpy-implement` invocations

- **Decision:** Update mill-go SKILL.md Execute step 1 (Implement) and step 3's `REQUEST_CHANGES` branch (fix dispatch) to invoke `millpy-implement.py` via `millpy-bg.py` with slug `implement-<batch_name>` (initial) and `fix-<batch_name>-r<N>` (resume). Builder polls `cat <log-path>` until `[mill-bg] EXIT` and extracts the JSON summary line from the log file (last non-sentinel line). `millpy-implement.py` itself is unchanged — its stdout JSON contract still holds; the JSON simply lands in the log file because the inner process's stdout is captured there. mill-go's stuck-type parsing logic is unchanged (`stuck_type: transient` retry, etc.); only the dispatch mechanism changes.
- **Rationale:** Bash-tool max foreground timeout (~10 min) is shorter than `implementer_timeout` (30 min). Without `millpy-bg`, mill-go always falls back to `run_in_background: true`, which routes the log to `%TEMP%/claude/...` — out of reach for crash-recovery and out-of-band inspection. Wrapping in `millpy-bg` puts the log under `<worktree>/.scratch/bg-<ts>-implement-<batch>.log`, which is the same pattern the reviewer CLIs already use. Behaviour is consistent and recoverable.
- **Rejected:** Increasing Bash-tool timeout (out of mill-v2's control — it's a Claude Code harness setting). Adding `--background` flag to `millpy-implement.py` directly (duplicates `millpy-bg` functionality).

### D6 — Strengthen merge-in briefs, not the parser

- **Decision:** Add the sentence "Anything other than the bare JSON object on the last line is a protocol violation; mill-go (or the merge-in dispatcher) treats that as `stuck_type: logic` with reason `no structured report`." to both `merge-in-verify-brief.md` and `merge-in-conflict-brief.md`, immediately after the JSON example block. Match the wording from `implementer-brief.md`'s line 87.
- **Rationale:** The brief templates are the contract. Loosening `_forward_output`'s regex would silently accept malformed reports across all callers (`millpy-implement.py`, `millpy-implement-holistic.py`, `millpy-merge-in-subagent.py`) — risk of masking real bugs.
- **Rejected:** Loosening the regex (cross-cutting risk); both (no need — fixing the brief addresses the user's reported failure mode).

### D7 — Resume section added to mill-go SKILL.md

- **Decision:** Add a `## Resume` section to mill-go SKILL.md, positioned between `## Execute — sequential loop` and `## Holistic code review`. Content:
  - **Entry condition:** phase is `implementing` / `reviewing` / `fixing`.
  - **Step 1:** Read `task/status.md`; locate the current batch entry (the one whose `state` is non-terminal).
  - **Step 2:** Branch on the batch's `state`:
    - `running` — the implementer was mid-implementation. Re-invoke `millpy-implement.py <batch_name> --resume` (with `--resume`, the CLI re-attaches the warm session via stored `implementer_session`). If `LLMSessionError` is propagated as `stuck_type: transient` → apply the standard one-retry-fresh policy; if the second fresh attempt also fails → escalate per *Stuck escalation*.
    - `reviewing` — the implementer report was already consumed; the reviewer was running. Re-invoke the per-batch code-review CLI from the start of round `review_round` (the round counter is the source of truth; the CLI's crash-recovery scan handles a written-but-uncommitted review file).
    - `fixing` — the reviewer returned `REQUEST_CHANGES`; the fix-implementer was running. Re-invoke `millpy-implement.py <batch_name> --resume --round <review_round> --review-file <abs-path>`.
  - **Step 3:** Continue the loop from the resumed step's natural successor (parse JSON → next code-review round → etc.).
  - **No state mutation before resume.** The CLI handles state transitions atomically; Builder must NOT pre-emptively flip `state` or append phase entries before re-invoking.
- **Rationale:** Entry-step 5 table already points to "*Resume*" but the section is missing — confused engineers in #229. The resume policy is non-obvious because the CLI's atomic state-write means Builder mustn't double-write.
- **Rejected:** Inlining resume guidance into the Entry-step 5 table (cells become unreadable). Skipping (#229's reporter explicitly asked for a Resume section).

### D8 — Top-level `verdict: "ERROR"` when all sub-reviews are ERROR

- **Decision:**
  - In `_review_code.py`, after constructing the `reviews[]` list (whether from try/except fallbacks or the normal path), compute: if every entry has `verdict == "ERROR"`, set the top-level `verdict = "ERROR"`. Otherwise keep the current behaviour (parsed verdict from `parse_verdict(raw)` or `REQUEST_CHANGES` fallback).
  - This matches mill-plan's existing convention (`_review_plan.py:281`: "all-ERROR → REQUEST_CHANGES; no raise" is actually inconsistent — verify and align both modules to "all-ERROR → top-level ERROR, no raise"). If `_review_plan.py` needs updating to match, do that in the same batch.
  - In mill-go SKILL.md, add a new step 4.5 ("ERROR-only-aggregate retry") in the Execute → Code Review loop, between step 4 and step 5 (max-rounds exhaustion). Mirror mill-plan's step 4.5 verbatim adapted for code review: when the JSON's `reviews[]` contains any entry with `verdict == "ERROR"` AND the top-level `verdict == "ERROR"`, re-invoke `millpy-review-code.py` via `millpy-bg.py` with slug `review-code-<batch_name>-retry-r<N>`. Round counter NOT consumed. Two-pass cap. On second consecutive ERROR-only result, halt with `BLOCKED: code review ERROR-only round {N}` and surface each entry's `error` string.
  - In holistic code review (mill-go SKILL.md `## Holistic code review`), add the same step.
- **Rationale:** Currently mill-go dispatches the implementer on `REQUEST_CHANGES` with a `null` review file when the LLM rate-limits — implementer can't proceed. ERROR retry-with-backoff is the proven mill-plan pattern.
- **Rejected:**
  - Keep top-level `REQUEST_CHANGES` and have mill-go scan `reviews[]` — splits the verdict-branch logic across two places.
  - Implement rate-limit backoff inside `_llm_claude` — masks the failure from the orchestrator, which prevents user override (option B in mill-plan's step 4.5 prompt).

### D9 — Fix unit-test fixtures to seed `config.yaml`

- **Decision:** Identify the 3 failing review-flow tests by running `python plugins/mill/unit_tests/run-all.py` and grepping output for "Missing config at". For each test, locate the fixture helper that constructs the `<tempdir>/container/wiki/` tree and add a seed step that writes the contents of `plugins/mill/templates/wiki-config.yaml` (or a minimal stub if the tests don't exercise reviewer-role keys) to `<tempdir>/container/wiki/config.yaml` before `load_config` is called. Prefer reusing `_test_helpers.py` if it has a `seed_wiki_config` helper; otherwise add one.
- **Rationale:** The fixtures predated `load_config`'s "missing config = error" invariant. The tests are correct to require config; the fixtures are wrong. Production callers always have config.
- **Rejected:**
  - `load_config` with default-on-missing — silently breaks the invariant; production bugs would be silent.
  - `xfail` — preserves the regression risk; mill-merge-in's verify-replay can't `xfail` past these tests cleanly.

### D10 — `parse_blocking_count`: stderr divergence warning

- **Decision:** In `_review_common.parse_blocking_count`, after counting headings, scan the raw output for prose-numeric phrases that suggest a count ("Five blocking issues remain", "There are 3 BLOCKING findings", etc.). If a numeric match is found that disagrees with the heading count, emit `[_review_common] warning: heading count <N> diverges from prose count <M> in review output` to stderr. Do NOT change the returned count. Verdict and verdict-branch logic are unchanged.
- **Rationale:** Surfaces the divergence for log inspection without changing the orchestrator's behaviour. Strengthening the prompt template would require coordinated rollout across every reviewer. Returning ERROR on divergence is too aggressive — undercount is a soft failure, not a fatal one.
- **Rejected:**
  - Strengthen the prompt template alone — slower rollout, no signal when reviewers regress.
  - Set `verdict = ERROR` when divergence — could cause false-positive task blocks on minor reviewer prose-rewording.

### D11 — `#214` mill-go SKILL.md: two bare `status.md` → `task/status.md`

- **Decision:** Edit `plugins/mill/skills/mill-go/SKILL.md` lines 106 and 170. Change `git -C <worktree> add status.md` to `git -C <worktree> add task/status.md` in both. No other SKILL.md files require this change (grep confirms only these two locations).
- **Rationale:** Direct grep already located both instances. Bare `status.md` no longer exists at worktree root after the `task/`-on-branch migration — git add fails.
- **Rejected:** Audit all SKILLs (over-engineering — grep is exhaustive).

### D12 — `#221` Name `_config.load_config` inline

- **Decision:**
  - mill-start SKILL.md step 3: append after the "Load config — deep-merge..." sentence: `Helper: _config.load_config(wiki_path, worktree_root) -> dict.` Match the inline-signature pattern used elsewhere in mill-start (e.g. step 1's `_wiki.sync_pull` signature line).
  - mill-plan SKILL.md step 3: same addition.
  - Do NOT add a "Helper signatures" subsection — the inline-signature pattern is established.
- **Rationale:** mill-start step 1 and mill-plan step 1 already have inline `signature:` lines for `_wiki.sync_pull`. Step 3's omission is a doc inconsistency.
- **Rejected:** A standalone "Helpers" subsection — disrupts the existing pattern.

### D13 — TodoWrite Principle in mill-go SKILL.md

- **Decision:** Add a new bullet under mill-go SKILL.md's `## Principles` section: `- **TodoWrite items name batches by number.** Emit items as "Implement batch N (<batch-slug>)" — e.g. "Implement batch 1 (foundations)" — so progress in the todo list correlates 1:1 with plan files (NN-<batch-slug>.md). Bare names without a number force the operator to cross-reference the Batch Index every time.`
- **Rationale:** Principles are read on every mill-go invocation; the format becomes habit. Inline notes in Execute would be missed because TodoWrite emission isn't a discrete step in the SKILL.
- **Rejected:** Inline note (gets lost), skip (regresses operator UX).

### D14 — `#235` wiki-config.yaml template sync

- **Decision:**
  - Edit `plugins/mill/templates/wiki-config.yaml`:
    - Remove the entire `hardlinks:` block (lines 51–52) and its preceding comment header.
    - Change `junctions:` entry `.millhouse/wiki: <WIKI_PATH>` → `.wiki: <WIKI_PATH>`.
    - Remove the "Layer 02/03/04" subheading relics in section dividers (e.g. `# Layer 02: file-path templates ...` → `# File-path templates ...`).
  - Verify `_setup.create_hub_links` reads `cfg.get("hardlinks", {})` (returns empty dict on absence). If it uses `cfg["hardlinks"]` directly, change to the `.get(...)` form.
  - Add a "Template-mirror rule" subsection to `CLAUDE.md` (project root) under `## Constraints` or `## Conventions worth carrying`: `Generated config templates under \`plugins/mill/templates/\` must stay in sync with production wiki/config.yaml's schema. When changing a config key in wiki/config.yaml's production copy, mirror the change in the template. Use the production copy as the source of truth for valid schema; the template as the source of truth for documentation comments.`
- **Rationale:** Matches the user-supplied bullet's exact wording for #235. Documenting the rule in CLAUDE.md prevents future drift.
- **Rejected:**
  - Full template-to-production sync (out of scope — would also require `paths: task/...` change and `roles:` vs `review:` schema convergence).
  - Keep template as-is (the drift will keep biting new setups).

## Technical context

**Relevant modules and skills:**

- `plugins/mill/skills/mill-go/SKILL.md` — three independent edits: #214 (two `task/status.md` replacements), #229 (new Resume section), #228 (new step 4.5), TodoWrite Principle.
- `plugins/mill/skills/mill-start/SKILL.md` — one edit: #221 inline signature on step 3.
- `plugins/mill/skills/mill-plan/SKILL.md` — one edit: #221 inline signature on step 3.
- `plugins/mill/scripts/_llm_claude.py` — `_invoke` function gets the fast-fail-retry guard. Look at `_invoke` (line 219). The retry path adds a `time.monotonic()` check and falls through to a second `_subprocess_util.run` call with `session_id=None`.
- `plugins/mill/scripts/_review_code.py` — `verdict` aggregation logic. The two `return ReviewResult(...verdict="REQUEST_CHANGES"...)` blocks (lines 302, 340) and the normal-path `verdict=verdict` (line 372). Add an aggregation step before the final return: if every entry in the constructed `reviews[]` has `verdict == "ERROR"`, override top-level to `"ERROR"`.
- `plugins/mill/scripts/_review_plan.py` — verify the same aggregation pattern is consistent. The docstring at line 281 already mentions "all-ERROR → REQUEST_CHANGES" — that may need updating to "all-ERROR → ERROR" to match the new code-review convention.
- `plugins/mill/scripts/_review_common.py` — `parse_blocking_count` (line 857). Add the prose-divergence warning AFTER the existing `findall` count but BEFORE returning. Use a separate function `_warn_if_prose_diverges(raw_output, severity, heading_count)` so it's testable.
- `plugins/mill/scripts/_implementer_common.py` — `_forward_output` unchanged (D6 decision keeps the parser strict).
- `plugins/mill/templates/merge-in-verify-brief.md` and `merge-in-conflict-brief.md` — append the protocol-violation sentence.
- `plugins/mill/templates/wiki-config.yaml` — three edits per D14.
- `plugins/mill/scripts/_setup.py` — verify `create_hub_links` uses `cfg.get("hardlinks", {})`.
- `plugins/mill/unit_tests/_test_helpers.py` — likely the central fixture builder for review-flow tests; add `seed_wiki_config(container_dir)` helper if absent.
- `plugins/mill/unit_tests/test-review-code-flow.py`, `test-review-plan-flow.py`, `test-review-discussion-flow.py` — call the new helper.
- `.gitignore` (project root) — add `.claude/scheduled_tasks.lock` line near the existing `.scratch/` and `nul` block.
- `CLAUDE.md` (project root) — add the template-mirror rule.

**Existing patterns to follow:**

- mill-plan SKILL.md's "step 1.5 pre-review validator gate" and "step 4.5 ERROR-only-aggregate retry" are the templates for mill-go's new step 4.5 — copy the structure (millpy-bg slug, JSON-line poll, two-pass cap, halt message format).
- mill-go SKILL.md's "Crash-recovery check" at step 3.1 in Code Review loop is the template for Resume's per-state branching — scan disk for the artefact, infer state from presence.
- The reviewer CLI's `millpy-bg.py` invocation pattern (Background → Poll log → Parse JSON line) is the template for wrapping `millpy-implement.py`.
- `_implementer_common._forward_output` is the canonical JSON-line parser; the merge-in briefs already share it via the import in `millpy-merge-in-subagent.py:38`.
- mill-go SKILL.md's "Principles" section already has bullets in the format `- **Title.** Body.` — match that style for the TodoWrite addition.

**Gotchas discovered during exploration:**

1. `_cleanliness.py` does exist (capture_snapshot + compute_new_dirt). Issue #216 is stale.
2. The `cmd /c claude` dependency on Windows is intentional — direct `claude.exe` lookup fails under debugpy/Bash-tool PATH truncation (per `_claude_argv_prefix` docstring). Don't change this.
3. `_subprocess_util.popen_detached` already uses `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB` (post a9d2081). The terminal-flash fix is in.
4. Production `wiki/config.yaml` uses the OLD `review:` schema; the template uses the NEWER `roles:` schema. The two are NOT being reconciled in this batch — only the user-listed subset of #235.
5. mill-plan SKILL.md line 6 already names `_config.load_config` indirectly via `_review_common.load_config`. Verify whether the planner reads `_review_common.load_config(...)` (which delegates to `_config.load_config`) or the canonical `_config.load_config` directly. mill-start should use `_config.load_config` (no review-coupling).
6. `_review_plan.py` says "all-ERROR → REQUEST_CHANGES" (line 281 docstring); cross-check the current return value to confirm if this is accurate or aspirational. The change in D8 may need to update `_review_plan.py` too.
7. `merge-in-verify-brief.md` and `merge-in-conflict-brief.md` use a slightly different JSON-block format than `implementer-brief.md` (no triple-backtick fence around the example). When adding the protocol-violation sentence, match the brief's existing example style.

**File paths the implementer will need:**

- All `plugins/mill/skills/*/SKILL.md` edits listed above.
- All `plugins/mill/scripts/_*.py` files listed above.
- `plugins/mill/templates/merge-in-*.md`, `wiki-config.yaml`.
- `plugins/mill/unit_tests/_test_helpers.py` + the three failing test files.
- `.gitignore`, `CLAUDE.md` (project root).

## Constraints

No `CONSTRAINTS.md` is present at the hub root (`_constraints.read_if_exists()` returns None).

Discovered constraints:

- **Mill scripts use `${CLAUDE_PLUGIN_ROOT}`.** Every new invocation example in mill-go SKILL.md (Resume section, step 4.5, millpy-bg-wrapped implement) must use `${CLAUDE_PLUGIN_ROOT}`, not `plugins/mill/...`. (CLAUDE.md project-level rule.)
- **Junctions are IDE convenience.** The `.wiki` rename in the template (D14) does not change any code paths — all path resolution flows through `_paths.resolve_wiki_path`. (CLAUDE.md `## Path invariants`.)
- **Task-state writes commit on the task branch.** Every new commit command in the Resume section and step 4.5 must use `git -C <worktree> add task/status.md` (not bare `status.md`). This means the Resume section's example commits also follow the #214 fix.
- **mill-receiving-review skill load is non-negotiable** before reading review output. The Resume section's `reviewing` branch must include the explicit load instruction.
- **Plugin templates are tracked.** `plugins/mill/templates/wiki-config.yaml` is checked in (the `.gitignore` exclusion `!plugins/*/templates/*.local.*` covers the `.local.*` variant; `wiki-config.yaml` itself is not excluded — it's a tracked template).

## Testing

**Per-module test approach:**

- **`_llm_claude` fast-fail retry (D3)** — add a unit test in `test-llm-claude.py`: monkey-patch `_subprocess_util.run` to return exit-1 with empty stdout and duration < 2s on the first call, then success on the second. Assert `_invoke` returns successfully and emits the breadcrumb. Also assert that `resume=True` does NOT trigger retry (must raise `LLMSessionError` immediately).

- **`_review_code` ERROR aggregation (D8)** — extend `test-review-code-flow.py`: build a fixture where `_reviewer_single.run` raises `LLMError` for both batch and holistic calls. Assert the returned `ReviewResult` has `verdict == "ERROR"` (top-level) AND `all(r["verdict"] == "ERROR" for r in reviews)`.

- **`_review_common.parse_blocking_count` divergence warning (D10)** — add a unit test in `test-review-common.py`: pass raw output containing 3 `### [BLOCKING]` headings and the prose "Five blocking issues remain"; assert stderr captured via `capsys` contains the warning string. Also assert the returned count is unchanged at 3.

- **Test-fixture seeding (D9)** — verify the 3 review-flow tests pass after the fixture update. No new test added — the existing tests ARE the assertion that the fix works.

- **`_setup.create_hub_links` graceful absence (D14)** — extend `test-setup-hub-links.py`: build a config with no `hardlinks:` key; assert `create_hub_links` runs without error and creates only the junctions.

- **Resume section (D7)** — no automated test. Manual verification path documented in the implementer brief: after mill-go is interrupted mid-batch, re-run `/mill-go` and confirm the documented resume behaviour for each of the three non-terminal states.

- **mill-go SKILL.md doc-only changes (D11, D12, D13)** — no test. Verified by `markdownlint` (if present) and human read-through.

- **Template edits (D14, D6, D9 fixture)** — no test. Smoke-verified by mill-setup running cleanly on a fresh container (out of scope for this batch but flagged for the reporter).

- **gitignore + CLAUDE.md edits** — no test. `git status` after applying confirms `.claude/scheduled_tasks.lock` no longer shows.

**TDD candidates:**

- D3 (`_llm_claude` retry) — write the test first; the retry logic is small and the assertion is mechanical.
- D8 (`_review_code` ERROR aggregation) — write a failing test first that exercises the all-ERROR path; the aggregation logic is then a one-liner.
- D10 (`parse_blocking_count` warning) — write the test first; the warning emission is trivial once the divergence-detection regex is settled.

**Key scenarios to cover:**

1. `_llm_claude` retry: fast-fail then success; fast-fail then fast-fail (propagate); slow-fail (no retry); `resume=True` fast-fail (no retry, raises `LLMSessionError`).
2. ERROR aggregation: all-ERROR `reviews[]` → top-level ERROR; mixed (some ERROR + some valid) → top-level keeps current behaviour (parsed verdict); no-ERROR → unchanged.
3. parse_blocking_count divergence: prose count > heading count → warn; prose count == heading count → no warn; no prose count phrase → no warn; multiple prose count phrases (use the one nearest the verdict block).
4. Resume: `running` resume re-attaches session; `LLMSessionError` on resume → one fresh-session retry (existing mill-go logic); `reviewing` resume re-fires CLI; `fixing` resume re-attaches via `--review-file`.

## Q&A log

- **Q:** Tackle all 14 items, or sub-select? **A:** [auto-pick] All 14 items. **Why:** These are all from triage; folding any out is just deferred toil.
- **Q:** #216 (`_cleanliness` module missing) — actionable or stale? **A:** [auto-pick] Verify + close as stale, no code change. **Why:** File exists at `plugins/mill/scripts/_cleanliness.py` and exposes `compute_new_dirt`; issue predates the module.
- **Q:** #217 (`.claude/scheduled_tasks.lock`) — gitignore or relocate? **A:** [auto-pick] Add `.claude/scheduled_tasks.lock` to `.gitignore`. **Why:** Single-line ignore; Claude Code owns the lockfile location, not us.
- **Q:** Bullet 8 (terminal flash) — trust a9d2081 or pre-empt with alternative spawn? **A:** [auto-pick] Trust a9d2081; verify and add follow-up only if flash persists. **Why:** `DETACHED_PROCESS` was the known offender; speculative alternatives risk new bugs.
- **Q:** #153 (`cmd /c claude` exits 1 after interrupt) — wrap, document, or defer? **A:** [auto-pick] Single-retry-on-immediate-exit-1 wrapper in `_llm_claude._invoke` (duration < 2s + empty stdout + not `resume=True`). **Why:** Shim flake is reproducible; bounded retry recovers without masking real errors.
- **Q:** Bullet 7 — wrap `millpy-implement.py` in `millpy-bg.py`? **A:** [auto-pick] Yes; mill-go SKILL.md Execute step 1 + REQUEST_CHANGES branch invoke via millpy-bg; Builder reads JSON from log. **Why:** Bash-tool 10-min foreground timeout < 30-min `implementer_timeout`; matches existing reviewer pattern.
- **Q:** #231 (verify-fix parser/template) — strengthen template, parser, or both? **A:** [auto-pick] Strengthen `merge-in-verify-brief.md` and `merge-in-conflict-brief.md` to match `implementer-brief.md`'s protocol-violation sentence. **Why:** Template change is contract-level; loosening the regex risks silent acceptance.
- **Q:** #228 (rate-limit propagation) — top-level ERROR verdict, REQUEST_CHANGES scan, or LLM-layer backoff? **A:** [auto-pick] Top-level `verdict: "ERROR"` when all sub-reviews ERROR; add mill-go step 4.5 (ERROR-only-aggregate retry, two-pass cap, no round consumed). **Why:** Mirrors mill-plan's existing step 4.5; orchestrator stays in control of retry budget and user override.
- **Q:** #225 (parse_blocking_count undercount) — stderr warn, stricter prompt, or ERROR on divergence? **A:** [auto-pick] stderr warning on divergence; count and verdict unchanged. **Why:** Non-invasive surfacing; doesn't mask real findings or break the orchestrator's verdict branch.
- **Q:** #226 (unit-test fixtures missing config.yaml) — fixture seed, lenient load_config, or xfail? **A:** [auto-pick] Update fixtures to seed `<tempdir>/container/wiki/config.yaml` from the template. **Why:** Fixtures are wrong, not the code; production callers must have config.
- **Q:** #214 (mill-go SKILL.md bare `status.md`) — direct fix or audit-wide? **A:** [auto-pick] Direct fix at lines 106 and 170. **Why:** Grep confirmed exactly 2 bare occurrences.
- **Q:** #221 (config-helper inline) — inline signature or separate subsection? **A:** [auto-pick] Inline `_config.load_config(wiki_path, worktree_root)` signature alongside existing "Load config" sentence. **Why:** Matches mill-go SKILL.md's existing inline-signature pattern.
- **Q:** TodoWrite batch-numbers — Principle, inline note, or skip? **A:** [auto-pick] Principle in mill-go SKILL.md. **Why:** Principles are read every invocation; inline notes get lost.
- **Q:** #229 (Resume section missing) — add section, inline into Entry table, or skip? **A:** [auto-pick] Add `## Resume` section after Execute, with per-state playbook. **Why:** Entry table already points to "*Resume*"; cells would become unreadable inline.
- **Q:** #235 (wiki-config.yaml template) — user-listed subset, full sync, or skip? **A:** [auto-pick] User-listed subset: drop hardlinks, change `.millhouse/wiki` → `.wiki`, drop "Layer 02/03/04" relics, verify `_setup.create_hub_links` graceful, document template-mirror rule in CLAUDE.md. **Why:** Matches the bullet's exact scope; full sync would require schema-convergence work out of scope.
