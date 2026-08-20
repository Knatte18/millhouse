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
- Fix Entry step 2's call site only, using explicit keyword arguments:
  `cfg = _config.load_config(hub_root=worktree_root, worktree_root=git_root)`. The local `worktree_root`
  variable (bound to `_paths.resolve_hub_path()` at Entry step 1) is left in place, unrenamed — see
  Decisions for why a blanket rename was considered and rejected during discussion review.
- Correct a factual overstatement in this discussion's own Root-cause rationale (caught by discussion
  review r1): `resolve_repo_config_path` uses `worktree_root` both to seed `resolve_main_worktree_root`
  *and* directly as a third candidate path — not "only" the former.

**Out:**
- No rename of the `worktree_root` local variable anywhere in `mill-plan/SKILL.md`. A full 13-site rename
  to `hub_root` was the original plan but was rejected during discussion review round 1: `mill-go-base`'s
  actual structural analog (its own Path Setup, not the unrelated lines-512-514 preflight snippet
  originally cited) binds this exact hub-scoped value to a variable named `worktree_root` and feeds it
  into `_paths.resolve_task_path`, whose own parameter is literally named `worktree_root`
  (`_paths.py:583`). `_config.load_config`'s `hub_root` parameter and `_paths.resolve_task_path`'s
  `worktree_root` parameter name the *same* underlying value differently — no single local variable name
  can textually match both call sites. Renaming would only relocate the "argument name doesn't match
  callee's own parameter name" defect from `_config.load_config` onto the `resolve_task_path` /
  `_treeguard.check_and_restore` call sites instead of fixing it.
- No change to the actual runtime values/roots resolved — `_paths.resolve_hub_path()` and
  `_paths.resolve_git_root()` keep being called exactly as today; this is a call-argument-only fix, not a
  behavior change.
- No change to `_config.py`, `_paths.py`, or any other script — the bug is confined to the SKILL.md call
  site, not the underlying functions.
- No change to `mill-go-base/SKILL.md` — its own Path Setup already uses the correct, self-consistent
  naming for its call sites (`worktree_root` matching `resolve_task_path`'s param name); its unrelated
  `_review_common.load_config` call at line 54 uses a different function with a different signature
  (`load_config(hub_root, mill_dir)`), not the pattern these issues describe.
- No change to `mill-start/SKILL.md` — see Decisions; filed as a follow-up, not folded into this task.
- No change to `_plan_validate.run`'s call (Entry step "Self-run the validator gate", ~line 261): its
  second positional parameter is named `project_root` — matching neither `hub_root` nor `worktree_root`
  textually — so there is no name-collision defect to fix there, and it already passes the correct value.
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
  already passes `git_root` there. `resolve_repo_config_path` uses its own `worktree_root` parameter two
  ways: to seed `resolve_main_worktree_root(worktree_root)` for the container-layout fallback (candidate
  2), and directly as a third candidate path, `worktree_root / "mill-config.yaml"` (`_config.py:213`,
  candidate 3) — both git-checkout-root semantics, consistent with the conclusion above.
- Rejected: taking the three issue reports at face value and swapping the actual runtime values. Rejected
  because that would change working behavior based on a misreading of a variable name, not a real defect
  in what gets resolved.

### Fix approach: keyword-args at the one broken call site, not a blanket rename

- Decision: leave the local variable `worktree_root` (bound to `_paths.resolve_hub_path()`) named as-is
  everywhere in `mill-plan/SKILL.md`. Fix only the Entry step 2 call, using explicit keyword arguments:
  `cfg = _config.load_config(hub_root=worktree_root, worktree_root=git_root)`.
- Rationale: the original plan (discussion draft, pre-review) was to rename `worktree_root` → `hub_root`
  at all 13 use sites, citing `mill-go-base/SKILL.md` lines 512-514 as an "established convention" for
  naming this value `hub_root`. Discussion review round 1 caught that this citation was wrong: lines
  512-514 are a standalone bash-embedded preflight check, not mill-go-base's structural analog. Its real
  analog — its own Path Setup (~line 75-80) — binds the identical hub-scoped value (via
  `_paths.resolve_active_hub`, docstring: "Return the hub directory... for the slug") to a variable named
  `worktree_root`, then feeds it directly into `_paths.resolve_task_path(worktree_root, ...)` for
  status_path/plan_dir/reviews_dir — `_paths.resolve_task_path`'s own first parameter is literally named
  `worktree_root` (`_paths.py:583`). This is the exact pattern mill-plan itself already uses at its own
  status_path/reviews_dir/plan_dir derivation sites and its `_treeguard.check_and_restore` calls (9 of the
  original 13 rename sites). So `_config.load_config`'s `hub_root` parameter and
  `_paths.resolve_task_path`'s `worktree_root` parameter name the exact same kind of value two different,
  conflicting ways across the codebase's own modules — no single local variable name in mill-plan can
  textually match both conventions at once. Renaming to `hub_root` throughout would have fixed the
  `_config.load_config` call while silently recreating the identical "local variable name doesn't match
  the callee's own parameter name" defect at every `resolve_task_path`/`_treeguard.check_and_restore`
  call site instead — the same class of bug, just relocated, not fixed.
- Rejected: the blanket 13-site rename (this discussion's own original plan, corrected here after
  discussion review). Also rejected: renaming only the `resolve_task_path`/`_treeguard` sites to something
  else (e.g. keeping them `worktree_root` was already correct — no action needed there, so there was
  nothing to rename in that direction either). The keyword-argument fix at the single actually-broken call
  site is the smallest change that both resolves the reported confusion and introduces no new one.

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
  `hub_root` to look for `mill-config.yaml` directly (candidate 1); uses `worktree_root` to seed
  `resolve_main_worktree_root(worktree_root)` for the container-layout fallback (candidate 2); and uses
  `worktree_root` directly as a third candidate path, `worktree_root / "mill-config.yaml"` (candidate 3,
  `_config.py:213`).
- `plugins/mill/scripts/_paths.py:234` — `def resolve_main_worktree_root(git_root: Path) -> Path:` — the
  parameter here is explicitly named `git_root`, confirming the value flowing through `worktree_root` in
  `_config.load_config`/`resolve_repo_config_path` must be the actual git checkout root
  (`_paths.resolve_git_root()`'s result), not the hub-scoped value.
- `plugins/mill/scripts/_paths.py:583` — `def resolve_task_path(worktree_root: Path, cfg_relative_path: str)`
  — this function's own first parameter is named `worktree_root`, and mill-go-base's Path Setup
  (`plugins/mill/skills/mill-go-base/SKILL.md`, ~lines 73-86) passes its hub-scoped value (from
  `_paths.resolve_active_hub`, docstring: "Return the hub directory... for the slug") into it under a
  variable also named `worktree_root` — the established, self-consistent convention for *this* call site,
  opposite of `_config.load_config`'s `hub_root` naming for the identical kind of value. (The
  lines-512-514 snippet originally cited as "the established convention" during this discussion's first
  draft is a standalone bash-embedded preflight check unrelated to Path Setup — that citation was wrong;
  caught and corrected by discussion review round 1.)

**The one call site to fix, `mill-plan/SKILL.md` Entry step 2 (~line 39):**

```
cfg = _config.load_config(worktree_root, git_root)
```
→
```
cfg = _config.load_config(hub_root=worktree_root, worktree_root=git_root)
```

No variable bindings change — `worktree_root` (bound to `_paths.resolve_hub_path()` at Entry step 1,
~line 35) and `git_root` (bound to `_paths.resolve_git_root()`, ~line 33) keep their existing names and
values everywhere in the file, including at every other use site (status_path/plan_dir/reviews_dir
derivation via `_paths.resolve_task_path`, the `_treeguard.check_and_restore` calls, and the
`_plan_validate.run` self-run-validator call at ~line 261) — none of those need or want a rename, per the
Decisions above. Line 42's signature quote (`_config.load_config(hub_root: Path, worktree_root: Path) ->
dict`) also stays unchanged — it already correctly documents the real function's parameter names, and the
keyword-argument call now reads consistently against it.

**Verification approach:** after editing, `grep -n '_config.load_config' plugins/mill/skills/mill-plan/SKILL.md`
should show the Entry step 2 call using the `hub_root=worktree_root, worktree_root=git_root` keyword form.
`grep -n '\bworktree_root\b' plugins/mill/skills/mill-plan/SKILL.md` should show no change in occurrence
count or wording anywhere else in the file (still bound at Entry step 1, still used unchanged at every
other site). There is no automated test suite covering skill-file prose; verification is a full-file
read-through confirming the edited call reads correctly against the adjacent signature line and that no
other line was touched.

**Follow-up filed, not in this task's scope:** `mill-start/SKILL.md` has the identical
`worktree_root = _paths.resolve_hub_path()` binding in its own Entry step 1 / Path Setup, used the same way
mill-plan's is (feeding `_paths.resolve_task_path` calls, matching that function's own parameter name) — so
unlike mill-plan's `_config.load_config` call, it is not misnamed relative to its own use sites. If
`mill-start` ever grows a literal inline `_config.load_config(...)` call (it currently only states the
merge behavior in prose plus a correctly-quoted signature line), the same keyword-argument fix would apply
there too — noted per issue #882's callout, left for a future task since no such call exists today.

## Testing

This is a documentation/prose-only change to a Markdown skill file (`mill-plan/SKILL.md`) — there is no
code to unit-test. Verification is: (1) the grep check described above under Technical context, confirming
the Entry step 2 call was rewritten to keyword-argument form and no other `worktree_root`/`git_root`/`hub_root`
occurrence in the file changed; (2) a full read-through of the edited file confirming the call now reads
consistently against the adjacent signature line; (3) confirming the file still parses as valid Markdown
(no broken code fences or inline-code spans introduced by the edit).

## Q&A log

- **Q:** Is the reported argument swap a real runtime behavior bug, or a naming/legibility defect? **A:** [auto-pick] Naming defect only. **Why:** code trace through `_config.load_config` → `resolve_repo_config_path` → `resolve_main_worktree_root(git_root)` confirms the current call already passes semantically-correct values; only the local variable's name is misleading.
- **Q:** Fix by renaming the local variable throughout the file, or by patching just the one call site with keyword arguments? **A:** [auto-pick, revised in discussion review r1] Keyword arguments at the single broken call site only. **Why:** the blanket-rename plan's justification cited the wrong mill-go-base snippet as precedent; mill-go-base's actual Path Setup analog uses `worktree_root` (matching `_paths.resolve_task_path`'s own parameter name) for the identical value `_config.load_config` calls `hub_root` — no single variable name matches both call sites' conventions, so renaming would have relocated the defect rather than fixed it (discussion review r1, BLOCKING finding).
- **Q:** Should this task also fix the identical naming pattern in `mill-start/SKILL.md`? **A:** [auto-pick] No, stay scoped to mill-plan only. **Why:** the task's canonical title/brief names mill-plan Entry step 2 specifically, and mill-start has no literal wrong-looking call to fix inline — only the same latent smell. Filed as a follow-up instead of folding into this task's diff.
