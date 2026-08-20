# Discussion: mill-plan Entry step 2: _config.load_config called with hub_root/worktree_root swapped vs its own signature

```yaml
task: mill-plan Entry step 2: _config.load_config called with hub_root/worktree_root swapped vs its own signature
slug: mill-plan-entry-config-load-args-swapped
status: discussing
parent: main
```

## Problem

Three separate GitHub issues (#882, #871, #866) report that `mill-plan/SKILL.md` Entry step 2 calls
`cfg = _config.load_config(worktree_root, git_root)`, while the documented signature quoted two lines
below in the same step reads `_config.load_config(hub_root: Path, worktree_root: Path) -> dict`
(confirmed against the real function at `plugins/mill/scripts/_config.py:221`). Read side by side, the
call's argument names don't textually line up with the signature's parameter names, which reads as a
swapped-argument bug.

A full code trace (see Technical context) shows the **values** passed are already semantically correct —
this is not a runtime behavior bug. The actual defect is that mill-plan's Entry step 1 binds the
hub-root value (`_paths.resolve_hub_path()`) to a local variable literally named `worktree_root`, which
collides by name with `_config.load_config`'s second parameter (also named `worktree_root`) even though
it's passed into the call's first slot. That name collision is what makes the call look wrong next to
the signature line, and is what all three issue reporters (independent automated self-report runs)
flagged.

## Scope

**In:**
- Rename the local variable in `mill-plan/SKILL.md` that is bound to `_paths.resolve_hub_path()` — currently
  named `worktree_root` — to `hub_root`, at every one of its 13 use sites in the file.
- Rewrite Entry step 2's call to `cfg = _config.load_config(hub_root, git_root)`, so it reads correctly
  against the adjacent (unmodified) signature line.
- Update the two parenthetical explanatory notes at the rename's binding site (Entry step 1) and its
  first reuse (Path Setup) to describe the variable as "the hub root" instead of "the task worktree root",
  matching `mill-go-base/SKILL.md`'s existing correct phrasing for the equivalent variable.

**Out:**
- No change to the actual runtime values/roots resolved — `_paths.resolve_hub_path()` and
  `_paths.resolve_git_root()` keep being called exactly as today; this is a pure rename + call-argument
  fix, not a behavior change.
- No change to `_config.py`, `_paths.py`, or any other script — the bug is confined to the SKILL.md prose/call
  site, not the underlying functions.
- No change to `mill-go-base/SKILL.md` — its equivalent variable is already correctly named `hub_root`
  (confirmed at lines 512-514) and its unrelated `_review_common.load_config` call at line 54 uses a
  different function with a different signature (`load_config(hub_root, mill_dir)`), not the pattern
  these issues describe.
- No change to `mill-start/SKILL.md` — it has the identical `worktree_root = _paths.resolve_hub_path()`
  misnaming pattern (confirmed present), but no literal `_config.load_config(...)` call is written inline
  in its SKILL.md (only prose plus a correctly-quoted signature line), so there is no visibly-wrong call
  to fix there. Filed as a follow-up rather than folded into this task — see Decisions.
- Line 42's signature quote itself (`_config.load_config(hub_root: Path, worktree_root: Path) -> dict`)
  is untouched — it documents the real function's actual parameter names and is already correct.
- Lines 53 and 65's generic prose ("no `plan_dir` dir at worktree root") describe the physical directory
  location, not the variable identifier, and stay as-is.

## Decisions

### Root cause: naming defect, not a value swap

- Decision: treat this as a pure naming/legibility defect. The call's argument *values* already match
  `_config.load_config`'s correct semantic roles; only the local variable's *name* is misleading.
- Rationale: traced `_config.load_config` (`_config.py:221`) → `resolve_repo_config_path(hub_root,
  worktree_root)` (`_config.py:178`) → `resolve_main_worktree_root(git_root)` (`_paths.py:234`, whose own
  parameter is explicitly named `git_root`). This confirms `_config.load_config`'s second parameter
  (named `worktree_root` in its own signature) must receive the actual git checkout root — i.e. what
  mill-plan calls `git_root` — not the hub-scoped value from `resolve_hub_path()`. The current call
  already passes `git_root` there. Cross-checking `mill-go-base/SKILL.md` (lines 512-514) confirms the
  same value pairing under the correctly-named variable `hub_root`.
- Rejected: taking the three issue reports at face value and swapping the actual runtime values. Rejected
  because that would change working behavior based on a misreading of a variable name, not a real defect
  in what gets resolved.

### Fix approach: rename throughout, not a local keyword-arg patch

- Decision: rename the local variable `worktree_root` (bound to `_paths.resolve_hub_path()`) to `hub_root`
  at all 13 use sites in `mill-plan/SKILL.md`, and write the Entry step 2 call as
  `cfg = _config.load_config(hub_root, git_root)`.
- Rationale: a keyword-argument-only fix (e.g. `_config.load_config(hub_root=worktree_root,
  worktree_root=git_root)`) would resolve just the one call site but leave the same misleading variable
  name at the other 12 use sites in the file (status_path/plan_dir/reviews_dir derivation, tree-guard
  checkpoints, the self-run-validator call), preserving the same misreading risk that produced three
  duplicate bug reports. `mill-go-base/SKILL.md` already uses `hub_root` as the correct, established
  convention for this exact value — this fix brings mill-plan in line with it.
- Rejected: keyword-args-only patch (smaller diff, but the naming defect at the other 12 sites persists,
  which is the whole reason automated self-report reviewers kept re-flagging this location as a bug).

### mill-start's identical naming pattern: filed as follow-up, not folded in

- Decision: do not modify `mill-start/SKILL.md` in this task, despite it having the identical
  `worktree_root = _paths.resolve_hub_path()` naming pattern (issue #882 explicitly asked for it to be
  checked "for the same pattern").
- Rationale: this task's canonical title/brief names mill-plan Entry step 2 specifically. Unlike
  mill-plan, `mill-start/SKILL.md` never writes a literal `_config.load_config(...)` call inline in its
  Entry step 2 — it only states the merge behavior in prose and quotes the (correct) signature line — so
  there is no visibly-wrong call there to fix, only the same latent variable-naming smell. Fixing it here
  would be scope creep beyond a task whose brief and wiki title are specific to mill-plan.
- Rejected: expanding this task to rename `worktree_root` → `hub_root` throughout `mill-start/SKILL.md` as
  well. Left as an explicit follow-up note instead (see Technical context).

## Technical context

**File to edit:** `plugins/mill/skills/mill-plan/SKILL.md` (this repo's own skill definition — a
self-hosted meta-fix).

**Ground truth confirmed by direct reads during discussion:**
- `plugins/mill/scripts/_config.py:221` — `def load_config(hub_root: Path, worktree_root: Path) -> dict:`.
  Docstring: "hub_root: Absolute path to the hub directory." / "worktree_root: Absolute path to the
  worktree git repository root."
- `plugins/mill/scripts/_config.py:178` — `resolve_repo_config_path(hub_root, worktree_root)` uses
  `hub_root` to look for `mill-config.yaml` directly (candidate 1), and uses `worktree_root` only to seed
  `resolve_main_worktree_root(worktree_root)` for the container-layout fallback (candidate 2).
- `plugins/mill/scripts/_paths.py:234` — `def resolve_main_worktree_root(git_root: Path) -> Path:` — the
  parameter here is explicitly named `git_root`, confirming the value flowing through `worktree_root` in
  `_config.load_config`/`resolve_repo_config_path` must be the actual git checkout root
  (`_paths.resolve_git_root()`'s result), not the hub-scoped value.
- `plugins/mill/skills/mill-go-base/SKILL.md:512-514` — the already-correct reference pattern:
  ```
  git_root = _paths.resolve_git_root()
  hub_root = _paths.resolve_hub_path()
  cfg = _config.load_config(hub_root, git_root)
  ```

**Exact rename sites in `mill-plan/SKILL.md`** (line numbers as of this discussion; mill-plan should
re-grep `\bworktree_root\b` against the live file rather than trust these numbers verbatim, since prior
commits on this branch may shift them):

1. Entry step 1 binding (~line 35): `worktree_root = _paths.resolve_hub_path()` → `hub_root = _paths.resolve_hub_path()`;
   update the trailing parenthetical from "(the task worktree root; used to anchor `_mill/` paths in
   nested layouts)" to "(the hub root; used to anchor `_mill/` paths in nested layouts)" — matching
   mill-go-base's phrasing.
2. Entry step 2 call (~line 39): `cfg = _config.load_config(worktree_root, git_root)` →
   `cfg = _config.load_config(hub_root, git_root)`.
3. Entry step 2 signature quote (~line 42): **leave unchanged** — it documents `_config.load_config`'s own
   real parameter names, not mill-plan's local variable.
4. Path Setup (~line 49): `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])`
   → replace `worktree_root` with `hub_root`; update the parenthetical from "(resolves against the task
   worktree root; `worktree_root` is already bound at Entry step 1 above)" to "(resolves against the hub
   root; `hub_root` is already bound at Entry step 1 above)".
5. Phase: Plan Review's own "Path Setup (Plan Review)" section (~line 117):
   `reviews_dir = _paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])` → replace
   `worktree_root` with `hub_root`; update the trailing parenthetical's `worktree_root` mention to
   `hub_root`.
6. Self-run-validator prose (~line 240): "`worktree_root` at Path Setup, so this needs no new path
   resolution" → "`hub_root` at Path Setup, ...".
7. Self-run-validator call (~line 261): positional arg `worktree_root,` passed to `_plan_validate.run(plan_dir,
   worktree_root, root=..., git_root=git_root, ...)` → `hub_root,`. This is the exact call issue #871 called
   out ("passes `worktree_root` again") — the rename resolves it as a mechanical consequence, no separate
   value change (`_plan_validate.run`'s `project_root` docstring already expects the hub-scoped worktree
   root here, matching what `resolve_hub_path()` returns).
8. Phase: Plan (~line 278): `plan_dir = worktree_root / cfg['paths']['plan_dir']` → `hub_root / cfg['paths']['plan_dir']`.
9. Phase: Plan Review Path Setup (~line 289): `reviews_dir = _paths.resolve_task_path(worktree_root,
   cfg['paths']['reviews_dir'])` → replace `worktree_root` with `hub_root`.
10. Tree-guard safeguard intro (~line 302): `_treeguard.check_and_restore(worktree_root, "_mill",
    git_root=git_root)` → replace `worktree_root` with `hub_root`.
11-13. Three more tree-guard checkpoint call sites (~lines 398, 434, 495, 501 — four occurrences across
    these lines, some lines repeat the call twice in one sentence): same
    `_treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root)` pattern → replace
    `worktree_root` with `hub_root` in each.

**Verification approach:** after editing, `grep -n '\bworktree_root\b' plugins/mill/skills/mill-plan/SKILL.md`
should return exactly one hit — the untouched signature quote at Entry step 2 (item 3 above) — plus any
prose that generically says "worktree root" without underscores (lines ~53, ~65), which are out of scope
per the Scope section. `grep -n '\bhub_root\b'` should return the renamed sites. There is no automated
test suite covering skill-file prose; verification is a full-file read-through confirming every call site
now reads consistently against its adjacent signature/docstring text, plus the grep check above.

**Follow-up filed, not in this task's scope:** `mill-start/SKILL.md` has the identical
`worktree_root = _paths.resolve_hub_path()` naming pattern in its own Entry step 1 / Path Setup. It should
get the same `hub_root` rename in a future task, per issue #882's explicit callout — but since it has no
literal wrong-looking `_config.load_config(...)` call inline (issue #882's proximate trigger), it's left
alone here.

## Testing

This is a documentation/prose-only change to a Markdown skill file (`mill-plan/SKILL.md`) — there is no
code to unit-test. Verification is: (1) the grep check described above under Technical context, confirming
every `worktree_root` use site tied to the `resolve_hub_path()` binding was renamed and the signature-quote
line was left untouched; (2) a full read-through of the edited file confirming no other prose (e.g. the
generic "worktree root" phrases at lines ~53/~65, which describe physical location, not the variable) was
inadvertently changed; (3) confirming the file still parses as valid Markdown (no broken code fences or
inline-code spans introduced by the edits).

## Q&A log

- **Q:** Is the reported argument swap a real runtime behavior bug, or a naming/legibility defect? **A:** [auto-pick] Naming defect only. **Why:** code trace through `_config.load_config` → `resolve_repo_config_path` → `resolve_main_worktree_root(git_root)` confirms the current call already passes semantically-correct values; only the local variable's name is misleading.
- **Q:** Fix by renaming the local variable throughout the file, or by patching just the one call site with keyword arguments? **A:** [auto-pick] Rename throughout (13 sites). **Why:** a keyword-arg-only patch leaves the same misleading name at 12 other use sites, which is what produced three duplicate bug reports in the first place; renaming matches `mill-go-base/SKILL.md`'s already-correct `hub_root` convention.
- **Q:** Should this task also fix the identical naming pattern in `mill-start/SKILL.md`? **A:** [auto-pick] No, stay scoped to mill-plan only. **Why:** the task's canonical title/brief names mill-plan Entry step 2 specifically, and mill-start has no literal wrong-looking call to fix inline — only the same latent smell. Filed as a follow-up instead of folding into this task's diff.
