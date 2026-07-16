# Discussion: Miscellaneous small tooling and doc/template accuracy gaps

```yaml
task: Miscellaneous small tooling and doc/template accuracy gaps
slug: mill-misc-tooling-and-docs-gaps
status: discussing
parent: hanf/linux-port-more
```

## Problem

Five small, independent tooling/documentation gaps were reported against the mill plugin
(each sourced from a closed GitHub issue, listed below). None share a root cause; they are
bundled into one task purely because each is too small to justify its own task branch.

1. **#651** — `roles.fixer.model` (consumed only by `millpy-fix.py`'s code-review fixer
   dispatch) is a config key fully independent from `roles.code-review.<scope>.reviewer`.
   An operator escalating the reviewer mid-task (e.g. to `opushigh`) can silently leave the
   fixer on the default `haiku`, defeating the point of the escalation — a strong reviewer
   finds issues a weak fixer can't reliably resolve, burning review rounds.
2. **#640** — `_cleanliness.revert_out_of_scope_drift`'s internal `git checkout HEAD --
   <path>` silently fails in nested-hub layouts (`hub_root != git_root`, e.g.
   `src/csharp/NORCE.Models`). Root cause confirmed by reading the code: the porcelain
   status lines it works from are git-root-relative (per `_pygit2_util.status_porcelain`'s
   documented behavior — see `compute_scope_violations`'s docstring in the same file), but
   the function compares them against a hub-relative `task_dir` and runs the checkout with
   `cwd=worktree` (hub root). The path is effectively double-prefixed and the checkout
   fails, so the file stays dirty and blocks the batch instead of being auto-reverted.
   `compute_scope_violations` in the same file already solves this correctly via a
   `hub_prefix`-rebasing step; `revert_out_of_scope_drift` never got the equivalent fix.
3. **#658** — `golang-build/SKILL.md`'s Tool Installation section tells the agent to run a
   bare `which`/`command -v` check for `goimports`/`golangci-lint` and report "not found"
   if it fails. Tools installed via `go install` (the method the skill itself recommends)
   land in `$(go env GOPATH)/bin`, which is not guaranteed to be on `$PATH` for every shell
   session — producing a false negative even though the tools are present.
4. **#632** — `plugins/mill/templates/plan-overview.md`'s "All Files Touched" section
   comment claims "mill-go reads this to warn if two parallel batches touch the same file".
   Confirmed by grep: the only consumer of that section is `_plan_validate.py`'s
   `all-files-touched-mismatch` check (a cross-check of the derived union against the
   overview's declared list); parallel-overlap warnings come from a separate check,
   `parallel-modifies-overlap`, which reads the cards' `Edits:`/`Creates:`/`Moves:` fields
   directly and has nothing to do with this section. The comment describes behavior that
   does not exist.
5. **#623** — `mill-plan/SKILL.md`'s Phase: Plan Review steps 4b/4c/4d ("apply fixes to
   plan files" / "editing the plan files directly") never explicitly warn against the
   specific failure mode where a reviewer finding names an exact source-code location that
   needs reconciling with a plan card — it's easy to reflexively edit the real source file
   instead of the plan card describing that future edit. A near-miss of exactly this
   happened once already (caught via `git status`, reverted, no lasting damage), but the
   guardrail that would have prevented the reflex was never added.

## Scope

**In:**
- #651: a non-blocking stderr warning in `millpy-fix.py` comparing the resolved fixer tier
  against the resolved `roles.code-review.<scope>.reviewer` tier (see Decisions), plus a
  short comment in the config template documenting the `fixer.model` / `code-review.*.reviewer`
  relationship.
- #640: `git_root`-aware rebasing fix to `_cleanliness.revert_out_of_scope_drift`, mirroring
  the pattern already used by `compute_scope_violations` in the same file; updates the sole
  production call site in `mill-go/SKILL.md` step 2b.
- #658: `golang-build/SKILL.md` Tool Installation section gains a `$(go env GOPATH)/bin`
  fallback check before declaring a tool missing.
- #632: rewrite of the "All Files Touched" section comment in `plan-overview.md` to describe
  its actual role (validator cross-check), removing the false mill-go-parallel-warning claim.
- #623: one explicit guardrail line added to `mill-plan/SKILL.md` Phase: Plan Review, applying
  to the fix-application steps (4b/4c/4d) uniformly.

**Out:**
- #651: no per-role/per-scope fixer key (fixer.model stays a single global key); no
  comparison against discussion-review or plan-review reviewers — `roles.fixer.model` is
  only ever consumed by the code-review fixer dispatch path (confirmed: `millpy-fix.py` is
  the only caller of `roles.fixer.model`; plan-review and discussion-review fixes are
  applied inline by the orchestrating session, with no separate "fixer" role or model key).
  No cross-provider (e.g. Claude vs Gemini) strength comparison — undefined, skipped
  entirely when providers differ.
- #640: no change to `compute_scope_violations` or `clean_ephemeral_scope_violations`
  (already correct); no change to the cleanliness gate's blocking behavior itself, only to
  why the revert step was failing to run.
- #658: no change to `golang-build`'s build/test/lint command list, failure-handling
  section, or any other skill; no new automated test infra for skill markdown content.
- #632: no change to mill-go's actual behavior — the fix does not implement the previously
  (falsely) claimed parallel-overlap read of this section; `parallel-modifies-overlap`
  remains the sole source of that warning.
- #623: no mechanical enforcement (e.g. a post-fix `git diff --name-only` assertion) —
  textual guardrail only, matching the issue's own suggested fix.

## Decisions

### fixer-tier-warning-scope-and-callsite (#651)

- Decision: Add a non-blocking stderr warning, emitted from `millpy-fix.py` right after
  `fixer_spec` is resolved (existing code around the `fixer_spec = _reviewers.resolve(...)`
  call). Compare the fixer's resolved `(model, effort)` against the resolved
  `(model, effort)` of `roles.code-review.<scope>.reviewer`, where `<scope>` is the value of
  `--scope batch|holistic` for this fix invocation. Only compare when both sides resolve to
  `provider: claude` and `type: single` — skip silently (no warning either way) when either
  side is a cluster type or a non-Claude provider (e.g. Gemini), since cross-provider or
  cross-cluster "strength" has no defined ordering. Tier order for comparison: model family
  `haiku(0) < sonnet(1) < opus(2)` (primary key), then `effort` `low(0) < medium(1) <
  high(2) < max(3)` as a tiebreaker within the same family. Warn (to stderr, non-fatal) when
  the reviewer's tier tuple is strictly greater than the fixer's tier tuple. Additionally,
  add a short comment next to the `fixer:` block in `plugins/mill/templates/mill-config.yaml`
  noting that `roles.fixer.model` and `roles.code-review.<scope>.reviewer` should generally
  be escalated together.
- Rationale: `millpy-fix.py` is the only place `roles.fixer.model` is read, and the only
  reviewer role whose findings actually get routed to that fixer is code-review (batch and
  holistic) — plan-review and discussion-review fixes are applied inline by the
  orchestrating Claude session directly, with no separate fixer-role dispatch, so comparing
  against those reviewers would produce meaningless warnings for a code path that doesn't
  exist. Firing the check at fix-dispatch time (rather than at every review invocation) means
  the warning only appears when the asymmetry is actually about to matter — a fix run is
  about to happen with a weaker model than the reviewer that found the issues.
- Rejected: comparing against every configured reviewer role/scope regardless of whether
  that scope actually uses `roles.fixer.model` (wrong — most scopes don't; would produce
  false-positive noise). Documentation-only fix with no code check (relies on the operator
  remembering to read the comment — the whole reported problem is that this doesn't happen
  reliably). Blocking/hard-error validation instead of a warning (too aggressive for a
  heuristic quality signal, not a correctness violation — `validate_role_refs` in the same
  file already reserves hard `ReviewerError` for genuinely broken references, not
  quality-tier mismatches).

### cleanliness-revert-hub-prefix-fix (#640)

- Decision: Add a `git_root: Path` parameter to
  `_cleanliness.revert_out_of_scope_drift(worktree, task_dir, parent_branch)` (becoming
  `revert_out_of_scope_drift(worktree, task_dir, parent_branch, git_root)` or equivalent
  keyword form — mill-plan's discretion on exact parameter order/name during Phase: Plan, as
  long as it doesn't break the two other public functions' signatures). Inside the function,
  compute `hub_prefix` from `worktree` (hub root) relative to `git_root`, exactly as
  `compute_scope_violations` already does (`hub_prefix = worktree.relative_to(git_root).as_posix()`,
  empty string when they're equal — flat layout). Rebase every git-root-relative porcelain
  path onto the hub-relative form before the existing `task_dir_str`/`owned_paths`
  in-scope/out-of-scope comparison runs, and pass the hub-relative form to the
  `git checkout HEAD -- <path>` subprocess call (which continues to run with `cwd=worktree`,
  unchanged). Update the sole production call site — `mill-go/SKILL.md` step 2b's inline
  Python snippet and its `signature:` line — to pass `git_root` (already resolved earlier in
  that skill session, per its Path Setup section). Add a nested-hub-layout regression test to
  `plugins/mill/unit_tests/test-cleanliness.py` mirroring the existing `ROOD-*` test cases
  but with `hub_root != git_root`.
- Rationale: `compute_scope_violations`, in the same file, already documents and solves
  exactly this rebasing problem for a sibling function; using the same technique keeps the
  two path-handling conventions in `_cleanliness.py` consistent instead of introducing a
  second, different one.
- Rejected: running `git checkout` with `cwd=git_root` instead of rebasing paths — would
  work but leaves the file's two "scope" functions using different path conventions
  (git-root-relative subprocess calls in one, hub-relative in the other), which is more
  confusing for future maintenance than mirroring the one correct pattern that already
  exists.

### golang-build-gopath-fallback (#658)

- Decision: In `plugins/golang/skills/golang-build/SKILL.md`'s "Tool Installation" section,
  change the detection step for each tool to first try the existing `command -v`/`which`
  check, then fall back to checking `$(go env GOPATH)/bin/<tool>` directly (e.g.
  `command -v goimports >/dev/null 2>&1 || test -x "$(go env GOPATH)/bin/goimports"`). If the
  tool is found via the fallback, the build workflow should invoke it via that full path (or
  prepend `$(go env GOPATH)/bin` to `PATH` for the remainder of the session) rather than
  relying on the bare command name. Only emit the existing "not found — install with: ..."
  message and stop when both checks fail.
- Rationale: `go install` (the method the skill's own "Install:" instructions recommend)
  places binaries in `$GOPATH/bin`, which is commonly not on `PATH` for a fresh shell/tool
  session — the false negative is a direct consequence of the skill recommending an install
  method its own detection step doesn't account for.
- Rejected: documenting the `$GOPATH/bin` fallback only in the failure message (tells the
  operator to work around it manually every time, rather than fixing the detection).

### plan-overview-comment-accuracy (#632)

- Decision: Rewrite the "All Files Touched" section's descriptive comment in
  `plugins/mill/templates/plan-overview.md` to state its actual role: it is the input to
  `_plan_validate.py`'s `all-files-touched-mismatch` check, which cross-checks this
  hand/agent-maintained list against the derived union of every card's `Edits:`/`Creates:`/
  Move-target paths (cards are the source of truth; this section exists to catch drift
  between the two). Remove the false claim that mill-go reads this section to warn about
  parallel-batch file overlap.
- Rationale: matches the issue's own "Expected" framing exactly — describe the section's
  real role rather than inventing new mill-go behavior nobody asked for or needs (parallel
  overlap detection is already fully covered by the separate `parallel-modifies-overlap`
  check, which reads the cards directly and doesn't depend on this section at all).
- Rejected: implementing the previously-claimed mill-go behavior instead of fixing the
  comment — would create a second, redundant code path duplicating
  `parallel-modifies-overlap` for no benefit.

### mill-plan-source-edit-guardrail (#623)

- Decision: Add one explicit guardrail sentence to `mill-plan/SKILL.md`'s Phase: Plan
  Review, placed once so it applies uniformly to the fix-application steps (4b's "apply each
  NIT fix... by editing the plan files directly", 4c's "Apply NIT fixes...", and 4d's "Apply
  fixes to plan files"): *"NIT/BLOCKING fixes during Plan Review apply ONLY to files under
  `<plan_dir>` — never to the actual source files the plan describes editing, even when a
  finding quotes an exact source location."* Exact placement (e.g. immediately before step
  4's branches, or repeated inline at each of 4b/4c/4d) is mill-plan's discretion during
  Phase: Plan, as long as the guardrail text is present and unambiguous before any
  fix-application step a Builder could reach.
- Rationale: matches the issue's own suggested fix text closely — it already precisely
  names the failure mode (a finding citing an exact pre-existing source passage tempts a
  literal edit of that real file instead of the plan card describing the future edit).
- Rejected: a mechanical post-fix `git diff --name-only` assertion that fails loudly on any
  out-of-`<plan_dir>` modification — stronger, but the single sourced incident was already
  caught and reverted manually with no lasting damage, and there's no evidence the textual
  guardrail alone is insufficient. Adding process/complexity beyond what the issue asks for
  is not justified.

### batch-structure

- Decision: Five separate plan batches, one per issue. File ownership per batch:
  - **#651**: `plugins/mill/scripts/millpy-fix.py`, `plugins/mill/scripts/_reviewers.py`
    (new tier-compare helper + its unit tests in `test-reviewers.py`),
    `plugins/mill/templates/mill-config.yaml` (comment only), plus unit tests in
    `test-millpy-fix.py` for the call-site wiring.
  - **#640**: `plugins/mill/scripts/_cleanliness.py`, `plugins/mill/skills/mill-go/SKILL.md`
    (step 2b's inline snippet + signature line only), `plugins/mill/unit_tests/test-cleanliness.py`.
  - **#658**: `plugins/golang/skills/golang-build/SKILL.md` only.
  - **#632**: `plugins/mill/templates/plan-overview.md` only.
  - **#623**: `plugins/mill/skills/mill-plan/SKILL.md` only.
  - #651 and #640 both touch `plugins/mill/skills/mill-go/SKILL.md`, but in unrelated,
    non-adjacent sections (an escalation-checklist comment vs. step 2b's cleanliness-gate
    snippet). Mark these two batches as sequential with each other (not parallel) to avoid
    a same-file parallel-edit conflict; #658, #632, and #623 touch no files shared with any
    other batch and can run in parallel with everything else.
- Rationale: the five issues are functionally unrelated; per-issue batches keep each code
  review scoped to one problem and maximize safe parallelism given how file-disjoint most of
  the fixes are.
- Rejected: one combined batch — simpler DAG, but forces full serialization for fixes that
  don't need it and loses per-issue review granularity.

## Technical context

- `plugins/mill/scripts/_reviewers.py` already has the registry-resolution machinery this
  task needs: `load(hub_dir)`, `resolve(registry, name)` (returns a flattened spec dict with
  `model`, `effort`, `provider`, `type`), and `validate_role_refs(cfg, registry)` (existing
  pattern for role-ref validation, called from the three review CLIs' prepare stages — but
  NOT the right call site for the new warning; see Decisions above).
- `plugins/mill/scripts/_agent_dispatch.py`'s `MODEL_FAMILIES` dict (`claude-sonnet` →
  `"sonnet"`, `claude-opus` → `"opus"`, `claude-haiku` → `"haiku"`) and `model_to_tier()` are
  available but only map a model id to a family name, not an ordinal rank — the new
  tier-compare helper needs its own explicit rank mapping (see Decisions, #651).
  `plugins/mill/templates/mill-agents.yaml` shows the full reviewer catalogue, including
  non-Claude entries (`g25flash`, `g25pro`, `g3flash_preview` — provider `gemini`) and
  cluster-type entries, both of which the #651 fix must skip rather than attempt to compare.
- `plugins/mill/scripts/_cleanliness.py`'s `compute_scope_violations` (lines ~59-110) is the
  reference implementation for the `hub_prefix` rebasing technique the #640 fix should
  mirror — read its docstring carefully, it documents the exact nested-hub-layout rule.
  `revert_out_of_scope_drift` is defined at the bottom of the same file (~line 324).
- `_cleanliness.revert_out_of_scope_drift`'s only production caller is inline Python in
  `plugins/mill/skills/mill-go/SKILL.md`'s "2b. Cleanliness gate" section — `git_root` is
  already resolved once at the top of that skill (mill-go's Path Setup) and stays in scope
  for the whole session, so no new resolution call is needed there, just threading the
  existing variable into the call.
- `plugins/mill/unit_tests/test-cleanliness.py` already has `ROOD-1` through `ROOD-4` test
  cases for `revert_out_of_scope_drift` (flat-layout only) — the new nested-hub test should
  follow the same tempdir-based fixture pattern.
- `plugins/golang/skills/golang-build/SKILL.md` is pure markdown (agent-followed
  instructions) — there is no Python code backing "Tool Installation"; the fix is a text
  edit only.
- `plugins/mill/scripts/_plan_validate.py`'s `_check_all_files_touched_mismatch` (~line
  1148) is the actual (and only) consumer of `plan-overview.md`'s "All Files Touched"
  section; `parallel-modifies-overlap` (~line 824, a different check) is the actual source
  of parallel-batch-overlap warnings and reads `Edits:`/`Creates:`/`Moves:` from the cards
  directly, confirming the template comment's claim is simply wrong.
- `plugins/mill/skills/mill-plan/SKILL.md`'s Phase: Plan Review steps 4b (line ~185), 4c
  (line ~207), and 4d (line ~209-217) are the three fix-application sites needing the new
  guardrail language.

## Testing

- **#651**: unit tests for the new tier-compare helper in `test-reviewers.py` — same-family
  different-effort ordering, cross-family ordering, cross-provider skip (no warning), cluster
  type skip (no warning), equal-tier no-warning case. Wiring test in `test-millpy-fix.py`
  asserting the warning fires (stderr) when `--scope` selects a code-review scope whose
  reviewer resolves to a strictly higher tier than `fixer.model`, and does not fire when
  tiers are equal or the fixer is stronger.
- **#640**: new nested-hub-layout test in `test-cleanliness.py` (`hub_root` a subdirectory of
  a synthesized `git_root`) verifying the previously-failing revert now succeeds and returns
  the reverted path; existing flat-layout `ROOD-*` tests must continue passing unchanged
  (regression guard — the rebasing must be a no-op when `hub_prefix` is empty).
- **#658**: no automated test — verified by plan/code review reading the bash fallback logic
  for correctness (see Decisions/Rejected).
- **#632**: no automated test — a template comment wording change; `_plan_validate.py`'s
  existing `all-files-touched-mismatch` test coverage (if any) is unaffected since behavior
  doesn't change, only prose.
- **#623**: no automated test — a SKILL.md instructional-text change; verified by plan/code
  review reading the guardrail sentence for clarity and correct placement.

## Q&A log

- **Q:** #651 — what should the fix do about the fixer/reviewer model escalation gap? **A:** [auto-pick] Add a non-blocking stderr warning in `millpy-fix.py` comparing fixer vs. code-review-reviewer tier, plus a config-template comment. **Why:** closes the actual gap instead of relying on operators reading documentation; the repo already has the registry/tier-resolution machinery to build on.
- **Q:** #640 — how should the nested-hub double-prefix bug in `revert_out_of_scope_drift` be fixed? **A:** [auto-pick] Add a `git_root` parameter and mirror `compute_scope_violations`'s existing `hub_prefix` rebasing technique. **Why:** consistency with the already-correct sibling function in the same file; avoids a second divergent path convention.
- **Q:** #658 — how should golang-build's tool-detection false negative be fixed? **A:** [auto-pick] Add a `$(go env GOPATH)/bin` fallback check before declaring a tool missing, and invoke via that path if found there. **Why:** closes the false negative itself, matches the issue's stated expected behavior.
- **Q:** #632 — should the stale "All Files Touched" comment be corrected or should the claimed behavior be implemented? **A:** [auto-pick] Correct the comment to describe the section's real role (validator cross-check). **Why:** matches the issue's own expected framing; implementing the false claim would duplicate `parallel-modifies-overlap` for no benefit.
- **Q:** #623 — textual guardrail or mechanical enforcement for the mill-plan source-edit near-miss? **A:** [auto-pick] One explicit guardrail sentence in Phase: Plan Review, applied before steps 4b/4c/4d. **Why:** matches the issue's own suggested fix; no evidence the textual guardrail alone is insufficient.
- **Q:** should #651's warning compare fixer.model against every configured reviewer role/scope, or only code-review? **A:** [auto-pick] Code-review only (batch and holistic), fired from `millpy-fix.py` at fix-dispatch time. **Why:** `roles.fixer.model` is only ever consumed by the code-review fixer dispatch path — comparing against discussion-review/plan-review reviewers would be comparing against a code path that doesn't use this key at all.
- **Q:** should these 5 fixes be one combined plan batch or five separate batches? **A:** [auto-pick] Five separate batches, with #651 and #640 marked sequential with each other (both touch `mill-go/SKILL.md` in unrelated sections) and the other three parallel with everything. **Why:** maximizes safe parallelism given how file-disjoint most fixes are; keeps review scoped per issue.
