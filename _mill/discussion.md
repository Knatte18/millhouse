# Discussion: Deactivate codeguide integration in millhouse

```yaml
task: Deactivate codeguide integration in millhouse
slug: deactivate-codeguide
status: discussing
parent: main
```

## Problem

Millhouse's own skills (`git-commit`, `mill-merge-in`) call into the separate `codeguide` plugin on every commit and every merge-in, to keep a generated `_codeguide/` doc tree in sync with source changes.
The user's own benchmarking says this no longer earns its keep: Claude's live repo-grepping has gotten good enough that the static-doc benefit codeguide provided is gone, while every commit still pays the cost of resolving whether codeguide is active and, if so, running the sync.

Why now: the user identified this cost/benefit flip directly and asked to stop paying it.
As a side effect, this closes GitHub issue #1137 as moot — that issue's `err.txt` artifact came from codeguide's `resolve_scope.py` tripping mill-go's untracked-file scope gate, and `resolve_scope.py` stops running once nothing calls into codeguide.

## Scope

**In:**
- Delete the two functional call sites that invoke the codeguide plugin: `git-commit/SKILL.md`'s "Codeguide sync" step, and `mill-merge-in/SKILL.md`'s "Codeguide update" step.
- Delete the resulting dead code: `_parent_branch.resolve_for_codeguide` (its only caller is the git-commit step being deleted) and its dedicated tests.
- Update every other prose mention that currently *describes or depends on* those two call sites running (`mill-go-base/SKILL.md`, `mill-quick/SKILL.md`, `implementer-brief.md`, `fixer-batch-brief.md`, `fixer-holistic-brief.md`, and the two rationale paragraphs inside `mill-merge-in/SKILL.md`'s Step 5.5) so they stop promising a `codeguide-update` that no longer happens.
- Remove the stale `codeguide/ <- codeguide clone` line from CLAUDE.md's container-layout diagram, and fix `git-clone/SKILL.md`'s claim that "mill-setup later adds `<repo>/codeguide/`... as siblings" — `mill-setup/SKILL.md` has zero codeguide-specific setup code today, so that claim already describes automation that doesn't exist.
- Close GitHub issue #1137 with a comment pointing at this task, since deactivating codeguide removes the mechanism that produced the reported artifact.

**Out:**
- The separate `plugins/codeguide/` plugin itself (its `codeguide-generate`/`codeguide-maintain`/`codeguide-setup`/`codeguide-update` skills, its scripts, its templates) is not touched or deleted. Only millhouse's own skills stop *calling into* it.
- `_sibling.py`'s `resolve_path` function and its `"codeguide"` role branch are not touched. `_sibling.py` is general-purpose sibling-path plumbing (`_paths.resolve_wiki_path` depends on it, along with ~30 other call sites for wiki-path resolution), and `plugins/codeguide/scripts/_sibling.py` is a documented byte-for-byte "identical twin" of this file, enforced by `test-sibling.py`. Editing mill's copy to drop the codeguide role would desync the twin and break that test, for a role that's harmless dead weight in mill's own copy.
- `_parent_branch.py`'s `resolve`, `check_liveness`, `resolve_dead_parent`, and `ParentBranchError` are not touched — these are load-bearing across the merge/finalize/plan/implement/go pipeline, entirely independent of codeguide. Only `resolve_for_codeguide` (single caller, one-line wrapper) is deleted.
- Prose-only mentions of `_codeguide/` that are conditional on the directory's existence rather than calls into the plugin are left as-is: `mill-start/SKILL.md`'s Explore-phase navigation guidance ("if `_codeguide/Overview.md` exists, follow the codeguide navigation pattern"), `workflow/SKILL.md`'s and `code-comments/SKILL.md`'s mentions of `_codeguide/` as one of several places durable notes/module docs can live, and `millhouse-issue/SKILL.md`'s example usage string. None of these invoke codeguide; they degrade gracefully if `_codeguide/` never exists and stay correct if a repo still has pre-existing codeguide docs on disk.
- No config toggle is added. Deactivation means deleting the calling code, not gating it behind a flag that still pays the resolve-and-check cost before deciding to skip.
- `test-guards.py` and `test-worktree-sibling-resolution.py` are not touched — they test properties of the codeguide plugin/its `_sibling.py` twin that are unrelated to this deletion (guard-anti-pattern scanning, sibling-path parity).

## Decisions

### Delete call sites outright, no feature flag

- Decision: Remove the codeguide-invoking code from `git-commit/SKILL.md` and `mill-merge-in/SKILL.md` entirely, rather than adding a `mill-config.yaml` toggle that defaults off.
- Rationale: No such toggle exists today — activation is decided dynamically by codeguide's own `resolve.py` (inline vs. sibling vs. not-found) per commit. The user's complaint is specifically that every commit pays a resolve-and-check cost; a flag checked *before* `resolve.py` runs would keep paying a (smaller) cost, and a flag checked *after* keeps the whole cost. Deleting the calling code removes it entirely with no future flag to maintain or forget to flip.
- Rejected: config-flag-gated deactivation (moves the cost, doesn't remove it); leaving the codeguide plugin itself deactivated via some plugin-level switch (no such mechanism exists, and would leave the resolve/dispatch code live and untested-against in mill's own skills).

### git-commit/SKILL.md: delete "### 2. Codeguide sync" (lines 21-58 of the current file) entirely

- Decision: Remove the whole "Codeguide sync (only if codeguide is initialized)" section — the `resolve.py --json` invocation, the `found == false` skip check, the parent-branch-hint resolution block (including its `_parent_branch.resolve_for_codeguide` call and the `try`/`except` guard), the `@codeguide:codeguide-update` invocation, and the inline/sibling-mode explanation bullets at the end. Renumber the remaining "## Rules" section's content is untouched (it isn't numbered), but the file's only numbered step ("### 1. Lint") stays "### 1." — there is no "### 2." left after this deletion, which is fine since nothing else in the file or elsewhere references git-commit's steps by number.
- Rationale: this is the primary per-commit cost the user wants gone. `CODEGUIDE_PLUGIN_ROOT` has no other reference anywhere in `plugins/mill/` (confirmed by repo-wide grep) — deleting this section removes its only use.
- Rejected: neutering it into a one-line no-op stub — that still leaves a documented section that describes dead behavior, which is more confusing than removing the section header entirely for a two-step file.

### mill-merge-in/SKILL.md: delete "### 5. Codeguide update" (current lines 181-194), renumber 5.5 → 5

- Decision: Remove Step 5's content and heading entirely (the `_codeguide/Overview.md` existence check, the `cd <hub_root>` / `codeguide:codeguide-update` Skill-tool invocation, the `cd <worktree>` restore, and the "Why the explicit `cd`" rationale paragraph). Renumber the following heading from `### 5.5. Commit dispatch briefs` to `### 5. Commit dispatch briefs`. `### 6. Report` keeps its number unchanged.
- Also edit three mentions upstream of Step 5 that describe the deleted call site and are otherwise missed by a codeguide grep sweep of this file: the frontmatter `description:` line ("...verify + codeguide-update") — rewrite to "...verify. Safe to call standalone..." (drop the codeguide clause); the intro paragraph's "...and runs codeguide-update when applicable." — delete that clause, leaving "...replays the same batch verifies mill-go ran during implementation."; and Step 1's "No checkpoint, no verify, no codeguide-update." fast-path line — rewrite to "No checkpoint, no verify." These three are as much in scope as the Step 5.5/"## No-op guarantee" occurrences below — all describe the same deleted behavior.
- Rationale: `### 6. Report` is cited by number from `mill-merge/SKILL.md` ("mill-merge-in's Step 6 report... 'Substituted parent branch' line"). Since 5.5 renumbers to 5 and 6 was already numerically after 5.5, this citation stays correct with zero edits needed in `mill-merge/SKILL.md`. Leaving a `5.5`/gap-at-5 numbering instead would work too but is needless asymmetry once step 5 no longer exists.
- Rejected: leaving a numbering gap; turning step 5 into a no-op stub (same reasoning as the git-commit decision above).
- Follow-on edits inside the now-renumbered Step 5 (formerly 5.5), both currently rationale prose that assumes codeguide staged something:
  - The "Why staged-only, not unscoped porcelain" paragraph currently ends "...since briefs (if added above) and codeguide docs (already staged by `codeguide_commit.py --mode inline` in Step 5) are the only two things this step ever stages or expects to find staged." Rewrite to "...since briefs (if added above) are the only thing this step ever stages or expects to find staged."
  - The paragraph "This also now picks up Step 5's inline-mode codeguide docs -- already `git add`-staged by `codeguide_commit.py --mode inline` back in Step 5, before this step runs -- which the prior `_mill/briefs`-scoped guard silently dropped whenever `_mill/briefs/` did not exist (#946)." describes a historical bug (#946) that can no longer occur once nothing stages codeguide docs at this point in the file. Delete this sentence entirely.
  - The following paragraph, "This step runs on the success path only... intentionally outside rollback scope..." mentions "no briefs were written AND no codeguide docs were staged either" — rewrite to "no briefs were written" (drop the codeguide clause), since that's now the only thing this step can no-op on.
- Also update the "## No-op guarantee" section's line "no checkpoint, no verify, no codeguide-update, no output side effects" — drop the "no codeguide-update" clause since there's no longer a codeguide-update step to (not) run.

### Delete `_parent_branch.resolve_for_codeguide` and its tests

- Decision: Remove the `resolve_for_codeguide` function in full — its `def`, docstring, and `try`/`except`/`return` body span current lines 233-248 of `_parent_branch.py` — and remove its entry from the module docstring's public-function list. In `test-parent-branch.py`, remove the `resolve_for_codeguide` import and its five dedicated assert/print pairs (the ones reading parent from status.md, returning `None` for a missing file, returning `None` on missing `parent:` instead of raising, and the two `expected_slug` match/mismatch cases) — leave every `resolve(...)` assertion in that same file untouched, since `resolve` stays.
- Rationale: `resolve_for_codeguide` has exactly one caller today (git-commit's Step 2, which this task deletes) — confirmed by repo-wide grep. Once that caller is gone it's unreferenced dead code; per the repo's code-quality convention, dead code is deleted, not left in case something wants it later.
- Rejected: leaving it in place unused — "might want it later" isn't a reason to keep an unreferenced function per this repo's YAGNI convention.

### Prose-only updates elsewhere that currently describe codeguide-update running from git-commit

These three templates and one skill file each contain a sentence whose entire point is that `git-commit` (or `git-commit`-via-fixer) triggers `codeguide-update` — false once the git-commit step above is deleted:

- `plugins/mill/templates/implementer-brief.md` (current line 75-76): rewrite "The skill runs language-appropriate lint on staged files and, if `_codeguide/Overview.md` exists, triggers `codeguide-update` so the next batch's implementer sees the updated codeguide." to "The skill runs language-appropriate lint on staged files." Delete the following line ("Skipping the skill means the next batch reads a stale map.") entirely — its whole rationale was the codeguide map staying fresh, which no longer applies.
- `plugins/mill/templates/fixer-batch-brief.md` (current line 53) and `plugins/mill/templates/fixer-holistic-brief.md` (current line 58): both read "After each fix, commit using the `git-commit` skill (so lint and `codeguide-update` run per commit)." — rewrite both to "After each fix, commit using the `git-commit` skill (so lint runs per commit)."
- `plugins/mill/skills/mill-go-base/SKILL.md` (current lines 947-948): rewrite "...every per-card commit invokes the `git-commit` skill so lint + `codeguide-update` run per-commit." to "...every per-card commit invokes the `git-commit` skill so lint runs per-commit." Delete the following line ("Batch N+1's implementer then reads a codeguide that already reflects batch N's additions.") entirely — same reasoning as implementer-brief.md above.
- `plugins/mill/skills/mill-quick/SKILL.md` (current line 90): rewrite "The skill runs language-appropriate lint on staged files and triggers `codeguide-update` when `_codeguide/Overview.md` exists." to "The skill runs language-appropriate lint on staged files."

Rationale: these are factually wrong the moment git-commit's codeguide step is deleted (they promise a sync that no longer happens) — this is required correctness upkeep following directly from that deletion, not a separate design choice.

### CLAUDE.md and git-clone/SKILL.md: strip the stale codeguide sibling-clone convention

- Decision: Remove the `codeguide/                     ← codeguide clone` line from CLAUDE.md's `## Project shape` container-layout diagram (current line 28). In `plugins/mill/skills/git-clone/SKILL.md`'s `## Hub Structure` section (current line 28), remove the sentence "mill-setup later adds `<repo>/wiki/`, `<repo>/codeguide/`, and `<repo>/portals/` as siblings of `wts/`." and replace it with "mill-setup later adds `<repo>/wiki/` and `<repo>/portals/` as siblings of `wts/`." (dropping only the `codeguide/` clause, keeping the accurate wiki/portals claim).
- Rationale: confirmed by reading `mill-setup/SKILL.md` in full that it contains zero codeguide-specific setup code — no clone step, no junction, no config wiring for a codeguide sibling. Both files currently assert this happens automatically; it never did as part of mill-setup, or codeguide's deactivation makes it doubly untrue going forward. Leaving the line implies a guarantee that neither reflects past nor future behavior.
- Rejected: reframing as "may be cloned manually, if desired" — since `plugins/codeguide/` is out of scope for this task and mill no longer calls into it at all, documenting a manual convention for a now-unused integration adds a maintenance surface with no current consumer; simplest to just remove the claim.

### Issue #1137: close as moot

- Decision: Comment on and close GitHub issue #1137, pointing at this task/PR, once the codeguide call sites are deleted.
- Rationale: per the task brief, #1137's `err.txt` artifact is produced by codeguide's own `resolve_scope.py`; once nothing calls into codeguide, `resolve_scope.py` never runs and the artifact can't be produced. This is the underlying mechanism being removed, not a workaround.
- Rejected: leaving the issue open with a comment only — the mechanism is gone, so there's nothing left to track.

## Technical context

Confirmed by direct grep across `plugins/mill/` (skills, scripts, templates) and `CLAUDE.md`, cross-checked by reading the actual files:

- Exactly two functional entry points into the codeguide plugin from mill: `git-commit/SKILL.md` Step 2 (invokes `@codeguide:codeguide-update` after a `resolve.py --json` check), and `mill-merge-in/SKILL.md` Step 5 (invokes `codeguide:codeguide-update` directly, gated on `_codeguide/Overview.md` existing anywhere in the repo). Every other mention in the plugin is either prose describing/depending on those two entry points (covered under Decisions above) or a purely conditional doc-reading reference that stays unchanged (covered under Scope > Out).
- `CODEGUIDE_PLUGIN_ROOT` (the env var git-commit's Step 2 reads) has no other reference anywhere in `plugins/mill/` — deleting Step 2 removes its only use in this plugin.
- `_sibling.py`: only public function is `resolve_path(role, repo_root)`. Mill's own code only ever calls it with `role="wiki"` (via `_paths.resolve_wiki_path`, itself used by ~30 files). The `role="codeguide"` branch exists purely so mill's copy stays byte-identical to `plugins/codeguide/scripts/_sibling.py` (asserted by `test-sibling.py`) — do not touch this file.
- `_parent_branch.py`: `resolve`, `check_liveness`, `resolve_dead_parent` are called from `millpy-implement.py`, `millpy-review-plan.py`, `millpy-merge-in-subagent.py`, and skills `mill-merge`, `mill-merge-in`, `mill-go-base`, `mill-finalize`, `mill-plan` — all unrelated to codeguide, do not touch. Only `resolve_for_codeguide` (one caller) is in scope for deletion.
- Other test files that reference codeguide (`test-guards.py`, `test-worktree-sibling-resolution.py`) test plugin-parity/anti-pattern properties unrelated to the deleted call sites — out of scope, do not edit.
- `mill-setup/SKILL.md` was read in full: it has no codeguide references at all. This is direct evidence the CLAUDE.md/git-clone claims are already stale before this task, independent of the deactivation itself.

## Constraints

No `CONSTRAINTS.md` present in this repo.

- ASCII-only in generated `print()`/`_log()` output (existing repo convention) — not directly relevant here since this task edits static doc/skill files, not runtime output, but any new prose added must still avoid non-ASCII per CLAUDE.md.
- Never use `sed` for any edit in this task, per CLAUDE.md and the `mill:conversation`/`mill:cli` skills — use `Edit`/`Read`/`Write` for every file touched.
- Verify commands for this repo's Python unit tests must be prefixed with `PYTHONPATH=` (empty) per CLAUDE.md's "Verify command shape" — applies to the plan's `verify:` command for the `test-parent-branch.py` change.

## Testing

- `test-parent-branch.py` (existing file, edited in this task): after removing the five `resolve_for_codeguide` assert/print pairs and its import, run the file directly (it's a `main()`-based script, not pytest) via the repo's standard unit-test runner (`plugins/mill/unit_tests/run-all.py`, or the file directly with the `PYTHONPATH=` prefix per CLAUDE.md) to confirm the remaining `resolve`/`check_liveness`/`ParentBranchError` assertions still pass unmodified.
- No new tests are needed — this task deletes calling code and dead code, it does not add new branching logic. The existing `test-sibling.py` twin-identity test and `test-guards.py`/`test-worktree-sibling-resolution.py` should be run unmodified as a regression check that untouched files (`_sibling.py`, the codeguide plugin) still pass, since this task's grep confirmed they're unaffected but a plan should verify that empirically rather than trust the grep alone.
- TDD is not applicable here — every change is a deletion/rewrite of existing prose or dead code, not new behavior to drive out with a failing test first.
- After all edits, a repo-wide `grep -rni codeguide plugins/mill/ CLAUDE.md` (excluding `plugins/mill/unit_tests/test-sibling.py`, `test-guards.py`, `test-parent-branch.py`'s remaining `_parent_branch` import line, and `test-worktree-sibling-resolution.py`, which legitimately still reference codeguide per Scope > Out) should return only: `_sibling.py`'s docstring/identical-twin comment, `mill-start/SKILL.md` L183, `workflow/SKILL.md` L41, `code-comments/SKILL.md` L61, `millhouse-issue/SKILL.md`'s example string, and `plugins/codeguide/**` itself. This is a good final-verification scenario for the plan to include as a batch's `verify:` step.

## Q&A log

- **Q:** Should CLAUDE.md's container-layout diagram keep documenting `codeguide/` as a hub sibling, given mill-setup never actually creates it? **A:** [auto-pick] Remove the `codeguide/` line from CLAUDE.md and fix git-clone's matching claim. **Why:** confirmed by reading `mill-setup/SKILL.md` in full that no codeguide-specific setup code exists there — the claim already describes automation that doesn't exist, independent of this task's deactivation.
- **Q:** Should `_parent_branch.resolve_for_codeguide` be deleted once its only caller (git-commit's codeguide step) is removed? **A:** [auto-pick] Delete the function and its five dedicated tests in `test-parent-branch.py`. **Why:** confirmed by repo-wide grep it has exactly one caller; per this repo's code-quality convention, unreferenced functions are deleted, not kept "in case."
- **Q:** How should `mill-merge-in/SKILL.md`'s step numbering be handled after deleting "### 5. Codeguide update"? **A:** [auto-pick] Delete Step 5 and renumber 5.5 → 5; Step 6 keeps its number unchanged. **Why:** `mill-merge/SKILL.md` cites "mill-merge-in's Step 6 report" by number — since 6 was already numerically after 5.5, renumbering 5.5→5 requires no edit to that external citation. Confirmed via grep that no other file cites the old codeguide step 5 by number.
- **Q:** Should the two codeguide-referencing rationale paragraphs inside mill-merge-in's Step 5.5 (soon Step 5) be rewritten or left as historical record? **A:** [auto-pick] Rewrite both to drop the codeguide clause; delete the #946-referencing sentence entirely. **Why:** both describe a staging behavior (`codeguide_commit.py --mode inline`) that can no longer occur once nothing invokes codeguide from this file — leaving them would describe dead behavior as if it still happens.
- **Q:** Should the four purely-conditional `_codeguide/` prose mentions (mill-start Explore guidance, workflow/code-comments general doc-placement mentions, millhouse-issue's example string) be scrubbed too, for full removal? **A:** [auto-pick] Leave all four unchanged. **Why:** none of them invoke codeguide — they're conditional on a directory that may still exist from before deactivation (or, for the example string, purely illustrative) and stay correct either way; scrubbing them would be scope creep beyond "stop calling into codeguide."
