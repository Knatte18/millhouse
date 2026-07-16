# Discussion: mill-finalize/mill-merge corrupt or mishandle _mill/status.md and task_dir on stacked branches

```yaml
task: mill-finalize/mill-merge corrupt or mishandle _mill/status.md and task_dir on stacked branches
slug: mill-merge-stacked-branch-status-corruption
status: discussing
parent: hanf/linux-port-more
```

## Problem

Five consolidated GitHub issues (#648, #653, #656, #659, #662) all surface in the same
scenario: a task branch whose `parent:` is itself another active mill task, with its own
`_mill/status.md` tracked at the identical relative path (`_mill/status.md`). Mill's
finalize/merge machinery never checks whether a `_mill/status.md` it finds actually
belongs to the *current* task — it treats "a file exists at this path" as proof "this
file describes my task." That assumption breaks in the stacked-branch case, with two
independent failure clusters:

1. **Content corruption (#653, #656, #659, #662).** mill-finalize's PR-mode Step 3
   cleanup (`git checkout <parent_branch> -- <task_dir>`, guarded by
   `_finalize_cleanup.base_tracks_task_dir()`) exists to keep PR diffs clean on stacked
   branches by making the child's committed `task_dir` tree bit-identical to the parent's
   tip. When the parent is itself an active task, this both (a) leaves orphaned
   child-only files behind because a bare `git checkout` only adds/updates, never deletes
   (#653), and (b) overwrites the *live worktree's* `_mill/status.md` with the parent's
   unrelated content — the correct outcome for the committed PR diff, but a corruption
   trap for any tool that later reads `_mill/status.md` from that same worktree, since it
   silently now describes the *parent's* task, not the child's (#656/#659). mill-merge's
   Entry Step 5 phase gate and `_parent_branch.resolve()` both then read this corrupted
   file and misroute — worst case, resolving `parent_branch: main` instead of the real
   stacked parent and squash-merging the child directly into `main`, sweeping in
   unrelated/unreviewed parent-branch WIP (#662).
2. **Path bug (#648), orthogonal.** mill-merge's Direct-squash Step 5 restores
   `<task_dir>` on the *parent* worktree (`git -C <parent-path> reset -q HEAD --
   <task_dir>` / `checkout -- <task_dir>`) using a `<task_dir>` value that was resolved
   as an absolute path anchored to the *child* worktree. In worktree mode (separate
   directories under `wts/`) that path is never inside the parent's repo root, so both
   commands fail with "outside repository." Currently harmless in practice (the path is
   usually already excluded from the squash diff by that point) but the commands are
   dead code for worktree-mode merges, silently disabling the #497 bug-2 protection they
   exist to provide.

**Why now:** these were all hit live running mill-finalize/mill-merge on real
stacked-branch tasks (see each issue's Context section for source repo/branch/timestamp)
and consolidated into this one wiki task since they share root cause and code paths.

## Scope

**In:**
- `_finalize_cleanup.base_tracks_task_dir()` / mill-finalize Step 3's restore path: make
  the restore delete-then-checkout so `task_dir` exactly matches base's tree (fixes
  #653's orphaned files).
- A slug-identity check at every downstream site that trusts `_mill/status.md`'s content
  for phase/parent resolution: mill-merge's Entry Step 5 phase gate, and
  `_parent_branch.resolve()` / `_read_parent_from_status()` (used by mill-merge Entry
  Step 4, mill-merge-in Entry Step 2, and mill-finalize's Dispatch step). Mismatch is
  treated identically to "file/field absent" (fixes #656/#659/#662).
- `_parent_branch.resolve_for_codeguide()` also gets the `expected_slug` plumbing for
  consistency, since it shares `_read_parent_from_status()`.
- mill-merge's Direct-squash Step 5: fix the two `git -C <parent-path>` commands to use
  a repo-relative pathspec instead of the child-anchored absolute `<task_dir>` (fixes
  #648).
- Integration test fixture simulating the full stacked-branch scenario (two branches,
  distinct slugs, parent's own `_mill/status.md`), covering all three corrected read
  sites plus the #653 orphan-file case and the #648 path fix.
- Unit tests for the new `expected_slug` kwarg behavior in `_parent_branch.py`.

**Out:**
- No new wiki schema field for parent-branch (would let mismatch cases auto-recover
  without a prompt, but is a much bigger schema change nobody has asked for; the
  existing prompt/`ParentBranchError` fallback already handles this case correctly for
  the non-interactive/interactive split that exists today).
- No identity check added to mill-finalize's own Step 5 `phase == "done"` gate — that
  read always happens before Step 3's corruption within a single invocation; a re-run
  after prior partial corruption is already funneled through mill-merge's PR-state gate,
  not mill-finalize's entry check.
- No transitive/multi-level slug-chain verification — a single slug comparison against
  the immediate `expected_slug` is sufficient; "not mine" is "not mine" regardless of how
  many ancestor tasks exist above the parent.
- No changes to `_status.read_status()` / `read_full()` signatures — the slug check
  stays scoped to the specific call sites that resolve parent/phase for merge routing,
  not the general-purpose status reader used by mill-go and other unrelated callers.

## Decisions

### identity-check-scope

- Decision: implement the slug-identity check as a small, backward-compatible
  `expected_slug: str | None = None` keyword parameter threaded through
  `_parent_branch._read_parent_from_status()`, `resolve()`, and
  `resolve_for_codeguide()`, plus an inline slug comparison in mill-merge's Entry Step 5
  phase-gate logic (using the existing `_status.read_slug()` helper — no `_status.py`
  changes needed there). Do not touch `_status.read_status()`/`read_full()` signatures,
  and do not introduce a new standalone identity module.
- Rationale: minimal blast radius — every existing caller of `_parent_branch.resolve*`
  that doesn't pass `expected_slug` keeps its exact current behavior (default `None`
  skips the check). The two call sites that need protection (mill-merge, mill-merge-in,
  mill-finalize's Dispatch) already have the current slug in scope at the call site, so
  passing it is a one-line change each. `_status.read_status`/`read_full` are used
  broadly (mill-go, etc.) for purposes unrelated to this stacked-branch corruption, so
  forcing every caller to supply an expected slug would be unjustified scope creep.
- Rejected: pushing the check into `_status.py` globally (touches unrelated callers);
  a new dedicated `_task_identity.py` module (adds a module for what is, in practice, a
  one-field comparison already naturally expressed as an optional parameter on the two
  functions that need it).

### mismatch-fallback-behavior

- Decision: on slug mismatch, both `_parent_branch.resolve()` and mill-merge's phase gate
  fall through to their *existing* "field/file absent" recovery path rather than
  inventing a new one. For `_parent_branch`, a mismatched `parent:` row is treated
  exactly as if the row were missing — the existing interactive prompt / `ParentBranchError`
  logic already covers it. For mill-merge's phase gate, a mismatched `_mill/status.md` is
  treated exactly as if `status_path` didn't exist — the existing wiki-lookup fallback
  (`_client.get_task`) already covers it. Both halt messages should additionally name the
  slug mismatch explicitly (e.g. "status.md slug '<found>' does not match task slug
  '<expected>' — treating as absent") so an operator debugging a halt immediately
  understands why, rather than seeing a generic "row missing" message.
- Rationale: mill's existing design philosophy (documented directly in
  `_parent_branch.py`'s module docstring) already rejected a config-level or automatic
  parent-branch override; the only fallback sources that exist today are the interactive
  prompt and the wiki. Reusing them means zero new failure modes to reason about, and the
  fix is symmetric with the pattern mill-merge already uses for `_pr_state` resolution
  (silent-fallback-to-phase-based-behavior).
- Rejected: adding a `parent_branch` field to the wiki task schema so a mismatch could
  silently auto-recover without any prompt — bigger schema change (touches `_client`,
  mill-spawn's initial write, wiki rendering) that nobody has asked for and that the
  existing module docstring already argued against for unrelated reasons (parent-branch
  is per-task, not stable config).

### step3-delete-then-restore

- Decision: mill-finalize's Step 3 restore path becomes
  `git rm -r --ignore-unmatch <task_dir>` immediately followed by
  `git checkout <parent_branch> -- <task_dir>`, then the existing commit. This makes
  `task_dir`'s committed tree an exact copy of `<parent_branch>`'s tree at that path —
  no leftover child-only files (discussion.md, plan/, reviews/, briefs/) survive into the
  PR diff.
- Rationale: matches the #653 reporter's proposed fix directly; a bare `git checkout
  <ref> -- <path>` can only add/update paths present in `<ref>`, never delete paths
  present on the current branch but absent from `<ref>` — exactly the observed leak.
- Rejected: computing a file-list diff and removing only the extra files individually —
  no benefit over delete-then-restore since the whole directory is being reset to base's
  version either way, and the diff-based approach is strictly more code for the same
  outcome.

### step5-relative-pathspec

- Decision: in mill-merge's Direct-squash Step 5, the two commands that operate on the
  *parent* worktree (`git -C <parent-path> reset -q HEAD -- <task_dir>` and
  `git -C <parent-path> checkout -- <task_dir>`) use a repo-relative pathspec derived
  from `cfg['paths']['status_md']`'s parent (in practice the literal `_mill`) instead of
  the absolute, child-worktree-anchored `task_dir` variable. Every other reference to
  `<task_dir>` in mill-merge (e.g. Step 4's `git -C <worktree> rm -r <task_dir>`, run
  against the *child* worktree) is unaffected and keeps the absolute form, since that one
  resolves correctly within the child's own repo root.
- Rationale: `git -C <parent-path> <cmd> -- <pathspec>` resolves a relative pathspec
  against `<parent-path>` (the `-C` target), so a relative form is the only one that can
  ever succeed there; the absolute child-anchored path is guaranteed to be outside the
  parent's repo root in worktree mode, which is exactly the "outside repository" failure
  reported in #648. The surrounding logic already assumes parent and child track
  `task_dir` at the same relative path (that's the entire premise of the #497 bug-2
  restore-protection this step implements), so a relative pathspec is consistent with
  that existing assumption, not a new one.
- Rejected: skipping the restore step when the absolute path isn't `relative_to`-resolvable
  within `<parent-path>` — this is the status quo effectively (the commands fail and,
  per the issue, happen to be harmless in that one observed run), but it silently
  disables the #497 bug-2 protection in the common worktree-mode case rather than fixing
  it.

## Technical context

- `plugins/mill/scripts/_finalize_cleanup.py` — `base_tracks_task_dir(worktree, base_branch,
  task_dir)`; returns `True` iff `base_branch` tracks a `status.md` at `task_dir`'s
  relative path (checked via `git ls-tree`). No slug-comparison today — this function's
  job stays "does base track *any* status.md here," Step 3's restore-vs-rm branch is
  unchanged; only the restore path's git commands change (delete-then-restore).
- `plugins/mill/skills/mill-finalize/SKILL.md` Step 3 ("Cleanup commit (issue #268)") —
  the restore-path commands live here, inline in the skill doc (not in a script).
- `plugins/mill/scripts/_parent_branch.py` — `_read_parent_from_status(status_path)`
  (private, hand-parses the first ```` ```yaml ```` fence for a `parent:` row),
  `resolve(status_path, *, interactive=True) -> str`, `resolve_for_codeguide(status_path)
  -> str | None`. All three need an `expected_slug: str | None = None` kwarg;
  `_read_parent_from_status` gains the actual comparison (reads `slug:` from the same
  yaml block it already scans — no new file read), returning `None` (same as
  "row absent") when `expected_slug` is provided and doesn't match. `resolve()` and
  `resolve_for_codeguide()` just thread the kwarg through.
- `plugins/mill/scripts/_status.py` — `read_slug(status_path) -> str` already exists
  and already falls back to `status_path.parent.name` when the field is absent; reuse
  this directly in mill-merge's phase-gate comparison — no changes needed to this
  module.
- `plugins/mill/skills/mill-merge/SKILL.md`:
  - Entry Step 4 (`_parent_branch.resolve(status_path, interactive=...)`) — add
    `expected_slug=slug` (already resolved in Entry Step 1 as `active_data['slug']`).
  - Entry Step 5 phase gate ("Try `_mill/status.md` first...") — after confirming
    `status_path.exists()`, additionally call `_status.read_slug(status_path)` and
    compare against `slug`; on mismatch, follow the *same* branch already documented for
    "`status_path` is absent" (wiki lookup via `_client.get_task`).
  - Direct-squash Step 5 — the two `git -C <parent-path>` commands switch to the
    relative pathspec per `step5-relative-pathspec` above.
- `plugins/mill/skills/mill-merge-in/SKILL.md` Entry Step 2 — add `expected_slug=slug`
  (slug already resolved in Entry Step 1 via `_marker.slug_from_branch`).
- `plugins/mill/skills/mill-finalize/SKILL.md` Dispatch step — the
  `_parent_branch.resolve(status_path, interactive=False)` call gets `expected_slug=slug`
  too (defense-in-depth; this call always runs before Step 3's corruption in a normal
  single invocation, but costs nothing to protect).
- `plugins/mill/skills/git-commit/SKILL.md` Step 2 (`_parent_branch.resolve_for_codeguide`)
  — out of scope for this task; git-commit's flow doesn't currently resolve/carry a slug
  at that call site, and adding one is a separate concern from the stacked-branch
  finalize/merge corruption this task addresses.
- `plugins/mill/integration_tests/` uses real git (no real LLM) and `.scratch/` fixtures
  — the stacked-branch fixture (two branches, two distinct `_mill/status.md` files) fits
  this harness directly; no new test infrastructure needed.

## Constraints

_No `CONSTRAINTS.md` present at the hub root._

- `print()`/`_log()` output must stay ASCII-only (repo-wide convention) — applies to any
  new halt/warning messages naming the slug mismatch.
- All new git operations against the parent worktree must go through `git -C
  <parent-path> ...` — never `cd`. This is already the pattern in both affected skills;
  the fix must not introduce a new violation.

## Testing

- **Unit (`plugins/mill/unit_tests/`, in-memory/tempfile fixtures, no real git):**
  - `_parent_branch._read_parent_from_status` / `resolve` / `resolve_for_codeguide`:
    TDD candidates — matching slug returns the `parent:` value as today; mismatched slug
    behaves identically to a missing `parent:` row (returns `None` /
    prompts-or-raises depending on `interactive`); no `expected_slug` passed (default
    `None`) preserves today's behavior exactly (regression guard for every existing
    caller that doesn't pass it).
- **Integration (`plugins/mill/integration_tests/`, real git, `.scratch/` fixtures):**
  - Stacked-branch fixture: parent branch with its own `_mill/status.md` (distinct
    slug, `phase: discussing`) and a superset-vs-subset `_mill/` tree relative to the
    child, plus a child branch with a full `_mill/` (discussion.md, plan/, reviews/,
    status.md at `phase: done`/`pr-pending`).
  - Verify mill-finalize's Step 3 restore path leaves `task_dir` exactly matching the
    parent's tree (no orphaned child-only files) — #653.
  - Verify that after Step 3 has run (corrupting the child worktree's live
    `_mill/status.md` with parent content, by design), mill-merge's phase gate correctly
    detects the slug mismatch and falls back to the wiki rather than trusting the
    corrupted phase/parent fields — #656/#659/#662.
  - Worktree-mode Direct-squash: verify the two `git -C <parent-path>` restore commands
    succeed (rather than failing "outside repository") and correctly protect a parent's
    own unrelated `_mill/status.md` from the squash diff — #648, plus re-verification of
    the pre-existing #497 bug-2 protection this step exists for.

## Q&A log

- **Q:** Fix all five sibling issues (#648, #653, #656, #659, #662) in this one task, or
  split #648 out as orthogonal? **A:** [auto-pick] Yes — all five together. **Why:**
  already consolidated into one wiki task; fixes touch the same code paths across
  mill-finalize Step 3 and mill-merge Entry/Direct-squash steps.
- **Q:** What mechanism should downstream readers use to detect a `_mill/status.md` that
  doesn't belong to the current task? **A:** [auto-pick] Minimal/scoped `expected_slug`
  kwarg on `_parent_branch`'s functions plus an inline `_status.read_slug()` comparison
  in mill-merge's phase gate. **Why:** smallest blast radius; every non-opted-in caller
  keeps current behavior; avoids forcing an expected-slug parameter onto
  `_status.read_status`/`read_full`, which unrelated callers (mill-go, etc.) use broadly.
- **Q:** What should mill-merge's phase gate do on slug mismatch? **A:** [auto-pick]
  Treat exactly like `status_path` absent — existing wiki-lookup fallback. **Why:** reuses
  a fallback path that already exists and is already tested/documented, rather than
  inventing new halt semantics.
- **Q:** What should `_parent_branch.resolve()` do on slug mismatch? **A:** [auto-pick]
  Treat exactly like the `parent:` row is missing — existing prompt/`ParentBranchError`
  logic. **Why:** matches the module's own documented philosophy that there is no
  wiki-level parent-branch override; adding one would be a much larger, unrequested
  schema change.
- **Q:** Does mill-finalize's own Step 5 `phase == "done"` check need the same
  defense-in-depth? **A:** [auto-pick] No — out of scope. **Why:** that read always
  precedes Step 3's corruption within a single invocation; a stale re-run is already
  covered by mill-merge's PR-state gate, not mill-finalize's entry check.
- **Q:** How should Step 3's restore path fix #653's orphaned-files leak? **A:**
  [auto-pick] `git rm -r --ignore-unmatch <task_dir>` then `git checkout <parent_branch>
  -- <task_dir>`. **Why:** matches the reporter's proposed fix; a bare checkout can only
  add/update, never delete, which is the exact leak observed.
- **Q:** How should #648's worktree-mode path bug in Direct-squash Step 5 be fixed?
  **A:** [auto-pick] Use a repo-relative pathspec for the two `git -C <parent-path>`
  commands specifically, derived from the config's status_md parent (`_mill`). **Why:**
  relative pathspecs resolve against `-C`'s target; the absolute child-anchored path is
  guaranteed outside the parent's repo root in worktree mode, which is the exact reported
  failure.
- **Q:** Does the non-stacked (common) path change? **A:** [auto-pick] No — confirmed
  unaffected. **Why:** `base_tracks_task_dir()` still returns `False` when base tracks no
  status.md at all, so Step 3 still takes the plain `rm` branch; the identity-check
  additions only ever activate on the restore path, which by construction only exists in
  the stacked-branch case.
- **Q:** Does the slug check need to be transitive across multi-level stacks (parent
  itself stacked on its own parent)? **A:** [auto-pick] No — one level suffices. **Why:**
  "not mine" is "not mine" regardless of how many ancestor tasks exist; the same
  fallback applies at any depth.
- **Q:** What testing strategy covers this fix? **A:** [auto-pick] Integration fixture
  simulating the full stacked-branch scenario (two branches, distinct slugs) across all
  three corrected read sites, plus unit tests for the new `expected_slug` kwarg. **Why:**
  these are cross-skill interaction bugs; unit tests alone would miss the interaction
  that caused them in the first place.
