# Discussion: Fix agent error recovery, implementer/review false-success contracts, VS Code watcher, and plan-validator Deletes

```yaml
task: Fix agent error recovery, implementer/review false-success contracts, VS Code watcher, and plan-validator Deletes
slug: mill-agent-and-implement-contracts
status: discussing
parent: main
```

## Problem

A batch of seven independently-filed issues (GitHub #494, #498, #499, #500, #501, #502, #503) all sit in the mill plumbing: the plan validator, the VS Code worktree settings, the agent-mode dispatch error paths, the implementer/review finalize contracts, and the holistic fix loop. Each is a small, well-localised correctness or robustness bug. None depends on another conceptually, but two of them touch the same source file (`_implementer_common.py`), so they must be sequenced rather than parallelised.

**Why now:** these surfaced during real mill runs (mill-plan, mill-go, mill-start on the loomyard and codeguide-strip-signatures tasks) and were auto-filed by `/mill-self-report`. Several are active foot-guns: a haiku implementer can report `success` without committing (#500), an agent-mode API 500 strands a review loop with no scripted recovery (#499/#502), and a finished worktree can become undeletable until reboot (#498). Bundling them lets one task clear the backlog of plumbing defects.

## Scope

**In:**

- **#494** — `_plan_validate.py` check 8 (`all-files-touched-mismatch`) stops requiring `Deletes:`-only paths in the overview's "All Files Touched". Code is brought into line with the already-correct docs.
- **#498** — `templates/vscode-settings.json` gains a static `files.watcherExclude` block for `.portals` / `.wiki` / `.active`, so every worktree settings render seeds it.
- **#499 / #502** — define the agent-mode recovery contract for a raw Agent API error that arrives before any verdict: (a) SKILL prose in mill-go's "## Agent-mode dispatch" (+ the mill-start / mill-plan references); (b) a script-level guard in `_implementer_common.py` finalize; (c) a documented subprocess `--stage full` fallback for read-only reviewers.
- **#500** — `_implementer_common.py::_forward_output` rejects a self-reported `status:success` when `HEAD == start_sha` (no content commit), demoting it to `stuck`.
- **#501** — `templates/fixer-holistic-brief.md` instructs the holistic fixer to sweep the whole tree for a repeating/systemic pattern, not only the cited exemplars.
- **#503** — `_review_discussion.py::finalize` threads `nit_count` into the returned `ReviewResult` so the discussion-review JSON envelope reports `[NOTE]` counts accurately.
- Regression tests for each behavioural fix where a test gap was identified (#494, #500, #503, and the #499/#502 script guard).

**Out:**

- **#498 migration of existing worktrees** — no in-place JSON-merge migration code. Existing worktrees pick up the exclude the next time their settings are re-rendered (e.g. by re-running `/mill-color`). Decided in Q2.
- **#494 doc edits** — `plan-overview.md` and `mill-plan/SKILL.md` already say "Edits ∪ Creates"; they are NOT changed. Only the validator code + its two error-message strings change. Decided in Q1.
- **#501 reviewer/schema changes** — no new "systemic" finding flag in `review-code-holistic.md` / `review-output.schema.md`. The fixer infers the sweep from the finding text. Decided in Q4.
- **GitHub issue lifecycle** — the seven issues are already CLOSED; this task does not reopen, comment on, or re-close them. No `gh` interaction is in scope.
- Any change to the subprocess/psmux dispatch happy-path, the reviewer bulking logic, or the cleanliness gate (`_cleanliness.py`) beyond what the above requires.

## Decisions

### 494-align-validator-to-docs

- Decision: In `_plan_validate.py` `_check_all_files_touched_mismatch` (~L744), remove the line `cards_set |= _parse_deletes_only(batch_path)` (~L774) so the union is `Edits ∪ Creates` only. Fix the two error-message strings to drop "Deletes": the `overview_set - cards_set` message (~L787, "…but not in any card's Edits:, Creates:, or Deletes:" → "…Edits: or Creates:") and the `cards_set - overview_set` message (~L797-799, "in card Edits:/Creates:/Deletes: but missing…" → "in card Edits:/Creates: but missing…").
- Rationale: The module docstring (L28-29), `plan-overview.md:65`, and `mill-plan/SKILL.md:122` all define "All Files Touched" as `Edits ∪ Creates`. Only the code disagreed. The triggering case is a `git mv` rename (`Deletes: old/path`, `Creates: new/path`) — the deleted path and created path differ, so requiring the deleted path in All Files Touched adds noise with no conflict-detection value. The documented mechanical fix in the SKILL fix table never adds Delete-only paths, so a Delete-only mismatch was literally unfixable by the prescribed procedure.
- Rejected: Aligning docs to code (Edits ∪ Creates ∪ Deletes). Would force planners to list deleted paths in the conflict-detection list, contradicting the rename use case and changing two docs instead of one code path.
- Note: `_parse_deletes_only` stays — it is still used by check 1 (`non-existent-path`). Only its call inside check 8 is removed.

### 498-watcher-exclude-template-only

- Decision: Add a top-level `files.watcherExclude` key to `templates/vscode-settings.json` (static JSON, no new placeholder token):

  ```json
  "files.watcherExclude": {
      "**/.portals/**": true,
      "**/.wiki/**": true,
      "**/.active/**": true
  }
  ```

  Because `_vscode.render_settings` does pure token substitution on the static template and every writer (`millpy-spawn`, `millpy-color`, `millpy-claim`, mill-setup) re-renders the whole file, the exclude is seeded automatically on every future write. No `_vscode.py` logic change is required.
- Rationale: `files.watcherExclude` (not `files.exclude`) is the only setting that stops VS Code's recursive watcher from following the junctions and holding cross-worktree directory handles that block `git worktree remove`. The template is the single seam every writer flows through.
- Rejected: A one-shot JSON-merge migration that patches existing worktrees in place (wired into mill-cleanup or a standalone script). Heavier (needs real JSON parsing + key-preserving merge), and existing worktrees can be remediated by re-running `/mill-color`, which re-renders the file with the new template.
- Note: this also seeds the exclude into the hub's green settings via mill-setup — harmless and desirable (the hub also carries `.wiki` / `.portals` junctions).

### 499-502-agent-error-recovery

- Decision: Three coordinated changes for "Agent tool returns a raw API/infrastructure error before producing any verdict or reviewable output":
  1. **mill-go `## Agent-mode dispatch` (locate by step name, not line number — the section is a 6-step numbered list; "Call Agent tool" is step 3, "Capture output" is step 4):** add an explicit step between step 3 and step 4: if the Agent returns a raw API/infrastructure error (e.g. `API Error`, `Internal server error`, ~0 tokens / 0 tool uses, no `MILL_REVIEW`/JSON block), do **not** write it to `<brief>.out.md` and do **not** run `--stage finalize`. Classify as `stuck_type: transient` and apply the existing one-retry transient policy — re-dispatch the same brief once (no `--resume`). On a second consecutive error: implementer/fixer escalate per *Stuck escalation*; read-only reviewers fall back to the subprocess path (`millpy-review-*.py --stage full` via `millpy-bg`) before escalating, since a read-only reviewer writes no artifact to finalize. Update the "Agent-mode properties" bullets (L136-137) to point at this step. State that it applies to implementer, reviewer, and fixer dispatches.
  2. **mill-start (SKILL.md) and mill-plan (SKILL.md) references:** add a short note that the same agent-error one-retry + reviewer subprocess fallback applies even though mill-start is interactive and has no autonomous stuck machinery — after the one-retry, an interactive skill may fall back to subprocess `--stage full` or surface to the operator rather than auto-refiring.
  3. **`_implementer_common.py` finalize (defense-in-depth):** in the no-JSON fallback (~L402, currently `{"status":"stuck","stuck_type":"logic","reason":"no structured report"}`), if the captured output matches API-error markers (`API Error`, `Internal server error`, HTTP 5xx), return `stuck_type: transient` instead of `logic`. Plain prose-without-JSON keeps `logic`. This routes a captured API error to the one-retry path automatically if it ever does reach finalize. **Matcher spec (pin it in the plan):** apply a **case-insensitive substring** test for the markers against the **captured `.out.md` body**, and **only on the no-JSON-parsed branch** — never against a successfully-parsed report's `reason` string (so a legitimate `stuck` whose prose happens to contain "API Error" is not misrouted). The regression test asserts **both** directions: an API-error body → `transient`; the existing plain-garbage body (Case 2) → `logic`.
- Rationale: Today, an implementer/fixer API error captured to `.out.md` falls through to `stuck_type: logic` → "ask user" (wrong — it's a retriable infrastructure blip), while a reviewer error becomes `verdict: ERROR` (handled by the existing two-pass ERROR-aggregate retry). The SKILL never told the Builder what to do when the Agent itself dies before a verdict, so operators improvised. Making `transient` + one-retry the contract, with a subprocess fallback for read-only reviewers, gives every dispatch a scripted path forward.
- Rejected: SKILL-documentation-only (no script change) — leaves the finalize fallback mislabelling captured API errors as `logic`. Also rejected: unbounded retries — the one-retry-then-escalate cap mirrors the existing transient policy and mill-go's two-pass ERROR cap.
- Note: the API-error detection must be specific enough that existing `test-implementer-common.py` Case 2 (plain garbage + `HEAD == start_sha` → `stuck/logic`) still passes; only genuine API-error-shaped text routes to `transient`.

### 500-implementer-commit-sha-guard

- Decision: In `_implementer_common.py::_forward_output`, in the parsed `status:success` branch (~L297-322, after the verify gate passes and before emitting success), compare the current `HEAD` against the `start_sha` parameter (already passed in at L280 but unused in this branch). If `git rev-parse HEAD == start_sha`, the implementer reported success without making a content commit — demote to `{"status":"stuck","stuck_type":"logic","reason":"success reported but no content commit (HEAD == start_sha)", ...}` instead of accepting the report and overwriting `commit_sha = HEAD`. Add a one-line contract note to `templates/implementer-brief.md` (the success JSON shape, ~L72-89) stating that `commit_sha` must be a real content commit distinct from the batch start.
- Rationale: The inference fallback already guards on `start_sha` (~L328, L384), but the self-reported-success branch never did — so a haiku implementer that made edits, skipped the per-card `git-commit`, and echoed the batch-start SHA was accepted as `success`. The cleanliness gate caught the dirty tree by luck; the contract itself must reject a no-commit success.
- Rejected: relying on the mill-go cleanliness gate alone (step 2b) — it only checks for a dirty tree; a clean-tree no-commit batch would slip through if the gate were ever relaxed. The defect is in the implementer contract, so the fix belongs there.

### 501-holistic-fix-sweep

- Decision: In `templates/fixer-holistic-brief.md` (procedure list ~L45-54), add an instruction: when a finding describes a repeating/systemic pattern (the same violation class across multiple files — e.g. "strip X from all docs"), do not fix only the cited exemplars — grep the whole worktree for the pattern and fix every occurrence in one pass. Reaffirm the existing rule that any newly-touched file not already referenced by a batch plan must be added to that plan's allowlist first (~L50-53), and note the sweep in the commit message.
- Rationale: The reviewer cites specific `file:line` exemplars per finding (the output schema has no multi-file field), and the fixer brief scopes work to "any file mentioned in any finding". For sweep-style tasks the same pattern persists in un-cited files, which the next review round re-surfaces — whack-a-mole that can exhaust `holistic.rounds`. Telling the fixer to generalise from a systemic finding to a tree-wide sweep breaks the cycle.
- Rejected: adding a "systemic (sweep all)" flag to the reviewer output schema + `review-code-holistic.md`. More reliable but a larger surface across reviewer template + schema + parsing; the fixer can infer the sweep from the finding text for now (YAGNI).

### 503-discussion-nit-count

- Decision: In `_review_discussion.py::finalize` (~L166-177), thread `nit_count=review_entry["nit_count"]` into the constructed `ReviewResult`, mirroring `_review_code.py` (L389-394) and `_review_plan.py` (L522). `finalize_scope` already computes the correct `nit_count` for discussion reviews (`nit_severity = "NOTE"`); only the hand-off into `ReviewResult` dropped it, so it defaulted to 0.
- Rationale: The summary JSON reported `nit_count: 0` despite a real `[NOTE]` in the review file, misleading any automation that trusts the envelope. mill-start's step 4b is salvaged only because it re-reads the file for `[NOTE]` rather than trusting the count.
- Rejected: none — a one-line plumbing omission with an obvious correct value.

## Technical context

Key files and seams (all under `plugins/mill/`). **All cited line numbers are approximate** (captured during exploration); the planner should locate edit points by symbol/step name, not raw line number:

- **`scripts/_plan_validate.py`** — `_check_all_files_touched_mismatch` (~L744). Union built from `_parse_edits_only` + `_parse_deletes_only` + `compute_creates_union`; remove the Deletes term (#494). `_parse_deletes_only` is shared with check 1 — leave the function intact.
- **`templates/vscode-settings.json`** — static template, tokens `<COLOR_HEX>` / `<WINDOW_TITLE>` only. `scripts/_vscode.py` `render_settings`/`write_settings` do pure token substitution and overwrite wholesale — adding a static key to the template is sufficient (#498).
- **`skills/mill-go/SKILL.md`** — "## Agent-mode dispatch" (L105-138) is the canonical pattern; mill-start (SKILL.md:131) and mill-plan (SKILL.md:136) reference it by link. The one-retry transient policy lives in mill-go's Implement step 2 (~L235) and Stuck escalation (~L395-406); the holistic equivalent is ~L648 (#499/#502).
- **`scripts/_implementer_common.py`** — `_forward_output` (L276-406). Parsed-success branch (~L297-322) is where the #500 `start_sha` guard goes; the no-JSON fallback (~L402) is where the #499/#502 API-error→transient classification goes. **Both #500 and #499/#502 edit this file — they must be in the same batch (or sequenced), never parallel.**
- **`scripts/_review_discussion.py`** — `finalize` (L122-177) drops `nit_count`; `finalize_scope` in `scripts/_review_common.py` (L1345-1394) computes it correctly. `parse_blocking_count` (`_review_common.py` L1288-1306) counts `### [SEVERITY]` ATX headings (#503).
- **`templates/fixer-holistic-brief.md`** — scope language at L24, L46-54; rendered by `scripts/millpy-fix.py` holistic branch (L278-327). No schema/reviewer change needed (#501).
- **`templates/implementer-brief.md`** — success/stuck JSON shape at ~L72-89 (#500 contract note).

Batch/dependency guidance for mill-plan: `_implementer_common.py` is the only shared file (#500 + #499/#502 script guard) — group those two in one batch. Everything else (#494 validator, #498 template, #503 review-discussion, #501 fixer brief, the SKILL.md prose for #499/#502) touches disjoint files and can run in parallel batches.

## Testing

Python project — unit tests live in `plugins/mill/unit_tests/` (`test-<name>.py`, run via `run-all.py`); in-memory/tempfile fixtures, no real git/LLM. Per the repo convention, plan `verify:` commands MUST start with `PYTHONPATH=` (literal empty) so the test subprocess loads worktree code, not the cache.

- **#494** — `test-plan-validate.py`: add a check-8 regression test where a card has a `Deletes:`-only path (not in any Edits/Creates and absent from All Files Touched) and assert **no** `all-files-touched-mismatch` is raised. Existing check-8 tests (`test_check_all_files_touched_mismatch_clean_no_section`, `_dirty`) must still pass; no existing test pins the Deletes-including behaviour, so none should break.
- **#498** — `test-vscode.py` `_test_render_settings`: assert the rendered output contains `files.watcherExclude` and the three keys (`**/.portals/**`, `**/.wiki/**`, `**/.active/**`). Existing title/color assertions must still hold.
- **#499 / #502** — `test-implementer-common.py`: add a case where the captured output is an API-error string (e.g. `"API Error: Internal server error"`) and assert the finalize result is `stuck_type: transient` (not `logic`). Verify existing **Case 2** (plain garbage + `HEAD == start_sha` → `stuck/logic`) still passes — the API-error detection must be marker-specific. The SKILL prose changes are doc-only (no unit test); call them out in the plan as manual-review items.
- **#500** — `test-implementer-common.py`: add a regression mirroring Case 19/20 — a parsed `status:success` report with `HEAD == start_sha` must be demoted to `stuck/logic` ("no content commit"). The existing verify-gate demotion tests must still pass.
- **#501** — template-only; no unit test (templates aren't unit-tested). Plan verify = the template still renders via `millpy-fix.py --scope holistic --stage prepare` without error (or a markdown lint). Flag as manual-review.
- **#503** — `test-review-discussion-flow.py`: add a `nit_count` assertion mirroring the existing `blocking_count` test (L194-235) — a discussion review body with two `### [NOTE]` headings and zero `[GAP]` must yield `nit_count == 2`, `blocking_count == 0`. This is the TDD candidate that would have caught the bug.

TDD candidates (write the failing test first): #503 (nit_count), #500 (commit_sha guard), #494 (Deletes exclusion), #499/#502 script guard (API-error → transient). #498 is template+test; #501 and the SKILL.md prose are non-test changes verified by render/manual review.

## Q&A log

- **Q:** #494 — fix the validator or the docs? **A:** Align the validator to the docs (remove `Deletes` from check 8); docs already say Edits ∪ Creates and the git-mv rename case proves Deletes-in-AFT is noise.
- **Q:** #498 — migrate existing worktrees in place, or template-only? **A:** Template-only. No JSON-merge migration code; existing worktrees re-seed via `/mill-color`.
- **Q:** #499/#502 — how deep? **A:** SKILL recovery step + `_implementer_common.py` API-error→`transient` classification + documented subprocess `--stage full` fallback for read-only reviewers. Covers implementer/reviewer/fixer; updates mill-start + mill-plan references.
- **Q:** #501 — fixer-brief only, or also a reviewer "systemic" flag? **A:** Fixer-brief only — instruct the fixer to grep + sweep the whole tree for a repeating pattern; no schema/reviewer change.
- **Q:** Are #500 and #499/#502 safe to parallelise? **A:** No — both edit `_implementer_common.py`; mill-plan must place them in the same batch or sequence them.
- **Q:** GitHub issue lifecycle? **A:** Out of scope — the seven issues are already CLOSED; no `gh` reopen/comment/close in this task.
