# Discussion: Handle pre-closed and pre-merged PRs gracefully in mill-merge

```yaml
task: Handle pre-closed and pre-merged PRs gracefully in mill-merge
slug: mill-merge-pr-state-awareness
status: discussing
parent: main
```

## Problem

`mill-merge` performs the final squash-merge of a completed task branch back to
its parent. Today it has two entry paths, gated on `phase:` in `_mill/status.md`:

- **`phase: done` (direct mode)** — does a local `git merge --squash` with **no
  awareness of any GitHub PR** for the branch. It blindly re-applies the branch
  diff to the parent.
- **`phase: pr-pending` (PR mode)** — a re-entry path that *does* query the PR
  (`gh pr list --state all`) and routes: `MERGED` -> cleanup only; `OPEN` ->
  "wait, re-run later"; `CLOSED`-without-merge -> "orphaned, run `/mill-abandon`".

Two real workflows break against this:

1. **Collaborative repos.** A teammate squash-merges the branch's PR on GitHub
   while `phase` is still `done`. The direct path is PR-blind, so the local
   `git merge --squash` re-applies an already-landed diff. Because a GitHub
   squash creates a *new* commit with no shared ancestry, the local squash does
   **not** report "Already up to date" — it produces duplicate or divergent
   history (the brief's "key risk in case 3"), and may conflict.
2. **Visibility-PR workflow.** A user opens a PR purely for review, reviews it,
   **closes it manually without merging**, and expects `mill-merge` to then
   squash-merge locally. Today the `pr-pending` path treats a closed-no-merge PR
   as *orphaned* and tells the operator to `/mill-abandon` — the exact opposite
   of what is wanted.

**Why now:** the task is being adopted in collaborative repos and in a
review-via-PR workflow where the brief's three PR states (open / closed-no-merge
/ merged-remotely) each need distinct, correct handling. The brief's claim that
mill-merge currently "closes an open PR before squash-merging" is a mental-model
error — mill-merge never closes PRs and the direct path never queries one. This
task makes mill-merge **PR-state aware at startup** so it routes correctly
instead of producing bad history or abandoning good work.

## Scope

**In:**

- A single **PR-state lookup at mill-merge startup** that runs for **both**
  entry phases (`done` and `pr-pending`), replacing the divergent ad-hoc PR
  handling currently embedded only in the `pr-pending` re-entry path.
- A new shared helper (`_pr_state.py`). It runs
  `gh pr list --head <branch> --state all --json state,mergeCommit,number,url`
  **without** `--jq '.[0]'` — it returns the **full PR array** and computes
  precedence in Python (see Decisions/normalized-state-precedence). The
  `--jq '.[0]'` form currently used inline by
  `millpy-cleanup.py:_apply_pr_reap_record` is intentionally dropped, because
  trusting gh's recency ordering would let a stale CLOSED PR mask a real MERGED
  one. The helper returns a normalized, testable result.
- Routing on the normalized state:
  - **MERGED (remote)** -> skip the local squash entirely; run cleanup-only
    teardown (cleanup commit so the archive tag reflects a clean tip, archive
    tag, Home.md `[done]`, lock release, notify).
  - **OPEN** -> **halt and report** ("PR #N is still open — close or merge it
    on GitHub, then re-run `/mill-merge`"). Never auto-close a PR.
  - **CLOSED without merge** -> **proceed with the normal local squash** path
    (the same Steps 1–9 the direct path runs today). This is the
    visibility-PR workflow.
  - **No PR found / `gh` unavailable / no GitHub remote** -> **silent fallback**
    to the existing direct-squash behavior. PR-awareness is purely additive and
    must never break the common no-PR / local-only case.
- Refactor `millpy-cleanup.py:_apply_pr_reap_record` to consume the same
  `_pr_state.py` helper (de-duplicate the query). Its single-PR behavior is
  unchanged; its **multi-PR** behavior intentionally changes — see
  Decisions/cleanup-adopts-precedence.
- Update the `mill-merge` SKILL.md: fold the old `## PR-path re-entry` table into
  the new unified startup gate; update the `pr-pending` CLOSED semantics from
  "abandon" to "proceed with local squash".
- Unit tests for `_pr_state.py` (mocked `gh` output for each state, plus the
  multi-PR precedence and the `gh`-missing / non-zero-exit fallbacks).

**Out:**

- `mill-finalize` routing (`require_pr_to_base`) is **unchanged** — it still
  decides PR-vs-direct mode and creates the PR in PR mode. This task only changes
  what `mill-merge` does once it runs.
- `mill-merge` never **creates** or **closes** a PR. (The brief's "close the PR"
  wording is explicitly rejected — see Decisions.)
- `git-pr` SKILL.md is unchanged.
- No new config keys. PR-awareness is automatic and self-gating on remote/`gh`
  availability (see Decisions: no-toggle).
- The branch-protection fallback in mill-merge Step 5 (which *creates* a PR when
  a direct push is rejected) is untouched — it is a separate concern.

## Decisions

### unified-startup-pr-gate

- Decision: Add one PR-state check that runs at mill-merge startup **regardless
  of phase** (`done` or `pr-pending`), and route open/closed/merged/none from a
  single place. The existing `## PR-path re-entry` table is subsumed by this gate.
- Rationale: The direct (`done`) path is currently PR-blind, which is the source
  of the duplicate-history risk; the `pr-pending` path has its own divergent
  logic. One gate fixes both and prevents the two paths from drifting further.
- Rejected: *Direct-path-only* (leaves `pr-pending` CLOSED semantics wrong and
  keeps two regimes); *pr-pending-path-only* (leaves the duplicate-history risk
  in the direct path — the brief's primary danger).

### open-pr-halt

- Decision: When the lookup finds an **OPEN** PR, **halt and report** — never
  auto-close. Message: "PR #N is still open — close or merge it on GitHub, then
  re-run `/mill-merge`." This matches the current `pr-pending` OPEN behavior.
- Rationale: Closing a PR is an outward-facing, possibly-surprising action (the
  PR may still be under review). The brief's literal "close the PR" was written
  against an incorrect mental model. Halting is safe and reversible; the operator
  closes or merges the PR explicitly and re-runs.
- Rejected: *Auto-close then squash* (silently closes an under-review PR);
  *interactive prompt to close* (mill-merge runs non-interactively in the
  mill-finalize chain and from background dispatch — a blocking prompt is
  undesirable; halt-with-instructions is the deterministic choice).

### closed-no-merge-proceeds

- Decision: A PR that is **CLOSED without merging** means "approved to merge
  locally" — `mill-merge` proceeds with the normal local squash (Steps 1–9). This
  changes the current `pr-pending` semantics, which abandon the work.
- Rationale: Directly enables the visibility-PR workflow (open PR for review ->
  close manually -> mill-merge squashes locally). The old "orphaned -> abandon"
  reading blocks a legitimate, intended workflow.
- Rejected: *Keep abandon* (rejects the workflow the brief asks for);
  *prompt operator* (ambiguity "rejected vs. just-for-visibility" exists, but a
  closed-no-merge branch that reached `mill-merge` has already passed plan +
  code review and `phase: done`, so "proceed" is the safe, non-destructive
  default; a wrong proceed is recoverable via the archive tag, whereas a wrong
  abandon discards reviewed work).

### no-pr-silent-fallback

- Decision: If no PR exists for the head branch, `gh` is unavailable, the repo
  has no GitHub remote, or the query errors/returns empty, **silently fall back**
  to today's direct-squash behavior.
- Rationale: PR-awareness must be purely additive. The overwhelmingly common case
  (local-only repos, no PR) must behave exactly as before, with no new noise or
  failure mode. The `gh`-missing path mirrors `_apply_pr_reap_record`'s existing
  tolerant handling (non-zero exit / empty stdout -> skip).
- Rejected: *Warn-then-fall-back* (noisy on every local-only merge);
  *hard-fail when gh missing* (breaks offline/local-only merges — unacceptable).

### merged-remote-cleanup-only

- Decision: On **MERGED** (remote squash already landed on the parent), skip
  Steps 1–2 (merge lock + `mill-merge-in`) and Step 5 (local squash). Still run
  Step 4 (cleanup commit) so the archive tag reflects a clean branch tip, then
  Steps 6 (archive tag), 7 (Home.md `[done]`), 8 (lock release — no-op if never
  acquired), 9 (notify/report).
- Rationale: The parent already has the change via the external squash; a local
  squash would duplicate/diverge. The archive tag still wants a clean tip. This
  generalizes the existing `pr-pending` MERGED branch to the `done` phase too.
- Rejected: *Run local squash anyway and rely on "Already up to date"* — invalid,
  because a GitHub squash shares no ancestry, so the local squash is **not** a
  no-op and reapplies the diff.
- Local-parent staleness: because Steps 1–2 and 5 are skipped, the **local**
  parent branch is intentionally **not** fast-forwarded to the remote squash in
  cleanup-only mode — it stays one commit behind `origin/<parent>` until the next
  parent-side `fetch`/`pull` (e.g. the next `mill-merge-in` or `mill-spawn`, both
  of which fetch origin) resyncs it. This is benign and deliberate: cleanup-only
  mode must not touch the parent worktree (no merge lock was acquired), and
  fast-forwarding it here would re-introduce the very parent-worktree coupling
  the MERGED route exists to avoid. The plan must not add a parent ff-sync step.

### cleanup-adopts-precedence

- Decision: When `_apply_pr_reap_record` is refactored onto `_pr_state.py`, its
  **multi-PR** behavior intentionally changes: it now resolves the PR state via
  the MERGED > OPEN > CLOSED precedence rather than gh's `.[0]` recency ordering.
  Single-PR behavior is unchanged; it still finalizes only on `MERGED`.
- Rationale: This is a strict correctness improvement. Today, an older MERGED PR
  sitting behind a more-recent CLOSED PR would make `.[0]` report CLOSED, so
  cleanup would skip a task whose work demonstrably landed. Precedence makes it
  finalize correctly. There is no case where the old `.[0]` answer is *more*
  correct than precedence for "did this branch's work merge?".
- Rejected: *Preserve `.[0]` semantics in cleanup* (would force two query
  variants — defeating the single-source-of-truth goal — and would keep the
  stale-CLOSED-masks-MERGED bug in the reaper).

### cleanup-tag-target-unchanged

- Decision: The two MERGED routes deliberately tag **different** commits, and the
  plan must NOT unify them. `mill-merge`'s cleanup-only route tags the local
  cleanup-commit tip of the task branch via
  `_archive_tag.create_or_resolve(...)`. `millpy-cleanup.py`'s PR-reaper continues
  to tag whatever it tags today (the remote merge / fetched SHA). Only the PR
  *query* is unified, not the teardown or the tag target.
- Rationale: The archive tag in each context preserves a different, locally
  meaningful tip — the task branch's cleaned tip in mill-merge, the reaped record's
  merge point in cleanup. Conflating them would change cleanup's archive semantics,
  which is out of this task's scope.
- Rejected: *Unify the tag target too* (scope creep; would alter cleanup's
  existing archive behavior with no benefit).

### normalized-state-precedence

- Decision: `_pr_state.py` queries `gh pr list --head <branch> --state all` and,
  if multiple PRs exist for the same head branch, applies deterministic
  precedence: **MERGED > OPEN > CLOSED**. Return a small normalized object
  (e.g. `state` in `{"merged","open","closed","none"}`, plus `number`, `url`,
  `merge_commit`) so callers branch on one field. `none` covers no-PR /
  `gh`-missing / query-error.
- Rationale: A branch can accumulate several PRs over its life; "is it merged?"
  must win over a stale CLOSED entry, and an OPEN PR must be visible over a
  superseded CLOSED one. `none` collapses all "can't determine / no PR" cases to
  the single silent-fallback branch.
- Rejected: *Trust `gh ... --jq '.[0]'` ordering blindly* (gh returns by
  recency, which can surface a stale CLOSED over a real MERGED — wrong route).

### no-config-toggle

- Decision: Do **not** add a config key to enable/disable PR-awareness.
- Rationale: The query is a single cheap `gh` call, self-gated on remote/`gh`
  presence, and the `none` fallback makes it invisible when unused. A toggle is
  YAGNI.
- Rejected: *`git.pr_state_aware` flag* — unnecessary surface for behavior that
  is already inert when no PR/remote exists.

## Technical context

What mill-plan needs to know:

- **`mill-merge` SKILL.md** — `plugins/mill/skills/mill-merge/SKILL.md`. The
  Entry "phase gate" (Step 5) and the `## PR-path re-entry` section are the edit
  sites. `CHILD_BRANCH` is currently captured at Step 3 via
  `git branch --show-current`; the new startup gate needs the branch name
  earlier (capture it at entry for the PR query). The teardown Steps 4–9 are the
  building blocks the MERGED (cleanup-only) and CLOSED (full squash) routes
  reuse — do **not** duplicate their logic; reference/route into them.
- **Existing PR-query pattern to factor out** —
  `plugins/mill/scripts/millpy-cleanup.py`, function `_apply_pr_reap_record`
  (~line 573). It already runs
  `_subprocess_util.run(["gh","pr","list","--head",<branch>,"--state","all",
  "--json","state,mergeCommit,number","--jq",".[0]"], cwd=hub_root)` and tolerates
  non-zero exit / empty stdout. New `_pr_state.py` should host this query
  (adding `url` to `--json`, dropping `--jq '.[0]'` so precedence is computed in
  Python), and `_apply_pr_reap_record` should be refactored to call it so there is
  one query implementation. `_apply_pr_reap_record` still acts only on `MERGED`,
  but now resolves that state via the precedence helper rather than gh's `.[0]`
  recency ordering — an intentional, strictly-safer change (see
  Decisions/cleanup-adopts-precedence). Its archive-tag target is **not** unified
  with mill-merge's (see Decisions/cleanup-tag-target-unchanged).
- **`_subprocess_util.run`** — `plugins/mill/scripts/_subprocess_util.py`. The
  standard subprocess wrapper (returns an object with `returncode`, `stdout`,
  `stderr`). `_pr_state.py` must run `gh` with `cwd=<hub_root/git_root>` like the
  cleanup helper does, never `cwd=<wiki>`.
- **`_archive_tag.create_or_resolve(worktree, slug, child_branch)`** —
  idempotent archive tagging used by Step 6; the MERGED route still calls it.
- **`_parent_branch.resolve(status_path, interactive=...)`** and
  **`_status` / `_timestamp`** helpers — unchanged; used by the existing teardown.
- **gh JSON shape** — `state` is one of `OPEN` / `CLOSED` / `MERGED` (uppercase);
  `mergeCommit` is an object/null; `number` int; `url` string. Normalize `state`
  to lowercase in the helper.
- **Naming/style** — new file is a `_*.py` helper (flat in `scripts/`), ASCII-only
  stdout (` -- `, ` -> `), follows the existing helper docstring conventions.
- **Cross-worktree invariant** — mill-merge runs from the child worktree; the
  `gh` query runs with `cwd` = the child git root (`_paths.resolve_git_root()`),
  which is where the branch and remote live. Never `cd` to parent or wiki.

## Constraints

- No `CONSTRAINTS.md` at the hub root was found; constraints below are those
  discovered during discussion.
- **Backward compatibility:** the no-PR / local-only path must be byte-for-byte
  behaviorally identical to today (silent fallback). This is the dominant case.
- **Non-interactive safety:** mill-merge is invoked from the mill-finalize chain
  and from background dispatch — the new gate must not introduce a blocking
  interactive prompt. OPEN -> halt-with-message (deterministic), not a prompt.
- **Non-destructive:** never auto-close a PR; never roll back a squash that has
  already landed on the parent; the MERGED route must not attempt a local merge.
- **Single source of truth for the PR query:** after this task there must be
  exactly one implementation of the `gh pr list` query (in `_pr_state.py`), shared
  by `mill-merge` (via SKILL.md invoking it) and `millpy-cleanup.py`.
- **Wiki/path invariants:** `gh` runs with `cwd` = child git root; all path
  resolution via `_paths.py`; ASCII-only stdout.

## Testing

TDD candidate: **`_pr_state.py`** — pure logic over mocked `gh` output, no real
git/gh, fits the `unit_tests/test-<name>.py` + `run-all.py` harness.

- **`_pr_state.py` unit tests** (`unit_tests/test-pr-state.py`), mocking
  `_subprocess_util.run`:
  - `state: MERGED` JSON -> normalized `merged` (with `number`, `url`,
    `merge_commit` populated).
  - `state: OPEN` -> `open`.
  - `state: CLOSED` (no merge) -> `closed`.
  - Empty `gh` result (no PR) -> `none`.
  - Non-zero exit / `gh` not found -> `none` (silent fallback), no exception.
  - Multiple PRs for one head branch -> precedence MERGED > OPEN > CLOSED
    (assert a stale CLOSED does not mask a MERGED, and a superseded CLOSED does
    not mask an OPEN).
  - Malformed/partial JSON -> `none` (defensive), no crash.
- **`millpy-cleanup.py` regression** — extend/keep `test-cleanup.py` so
  `_apply_pr_reap_record` still finalizes only on `MERGED` after being refactored
  onto `_pr_state.py` (mocked `gh`); confirm no behavior change.
- **mill-merge routing** — SKILL.md behavior is documented, not unit-tested
  directly (no real gh in unit tests). The route table (merged/open/closed/none ->
  action) is specified in the SKILL.md gate and exercised manually / via the
  existing integration harness if extended; the testable core is `_pr_state.py`.
- Run the suite via `plugins/mill/unit_tests/run-all.py`
  (`uv run --project plugins/mill`). Verify command must start with
  `PYTHONPATH=` (empty) per the Python verify-shape rule.

## Q&A log

- **Q:** Where should the new PR-state check live (direct `done` path, `pr-pending`
  path, or both)? **A:** [auto-pick] Both paths, unified check at startup.
  **Why:** the direct path's PR-blindness is the brief's primary risk and the two
  paths otherwise keep diverging; one gate fixes both. See
  Decisions/unified-startup-pr-gate.
- **Q:** When an OPEN PR is found, should mill-merge auto-close it, prompt, or
  halt? **A:** [auto-pick] Halt and report; never auto-close. **Why:** closing a
  possibly-under-review PR is outward-facing and surprising; the brief's "close
  the PR" was based on an incorrect mental model. See Decisions/open-pr-halt.
- **Q:** A PR is CLOSED without merging — proceed with local squash, prompt, or
  keep the current abandon behavior? **A:** [auto-pick] Proceed with local squash.
  **Why:** enables the visibility-PR workflow (review -> close -> mill-merge
  squashes); abandoning reviewed `phase: done` work is the wrong default. See
  Decisions/closed-no-merge-proceeds.
- **Q:** If `gh` is unavailable / no remote / no PR — fall back silently or warn?
  **A:** [auto-pick] Silent fallback to direct squash. **Why:** PR-awareness must
  be additive and invisible in the common local-only case. See
  Decisions/no-pr-silent-fallback.
- **Q:** On a remote-MERGED PR, can we just run the local squash and rely on
  "Already up to date"? **A:** [auto-pick] No — skip the local squash and do
  cleanup-only teardown. **Why:** a GitHub squash shares no ancestry, so the local
  squash is not a no-op and would duplicate/diverge. See
  Decisions/merged-remote-cleanup-only.
- **Q:** Add a config toggle to enable/disable PR-awareness? **A:** [auto-pick]
  No toggle. **Why:** the query is cheap and self-gating; the `none` fallback makes
  it inert when unused — a flag is YAGNI. See Decisions/no-config-toggle.
