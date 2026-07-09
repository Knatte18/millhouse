# Discussion: Fix codeguide-update scope resolution on stacked branches and resolve_scope.py branch-name parsing

```yaml
task: Fix codeguide-update scope resolution on stacked branches and resolve_scope.py branch-name parsing
slug: codeguide-scope-resolution-fixes
status: discussing
parent: main
```

## Problem

Three related bugs share one fix surface: `plugins/codeguide/scripts/resolve_scope.py` and the two mill skills that call it (`git-commit`, `mill-merge-in`).

1. **#617 / #621 — no-arg default picks the wrong base on stacked task branches.** `codeguide-update`'s no-arg scope resolution (used by `git-commit` Step 2 on every commit) detects the base branch purely via git-native signals (`origin/HEAD` → `origin/main` → `origin/master`). On a task branch stacked N levels deep (task → parent task → phase branch → `main`), this always resolves to `main`, not the task's actual immediate parent recorded in `_mill/status.md`'s `parent:` field. A single-file commit on a triple-stacked branch pulled 266 unrelated files into scope (#617); a similar case pulled ~297 files (#621). Implementers have had to manually bypass the tool's default and hand-scope every codeguide-update call, defeating the point of the automatic sync.

2. **#611 — non-hex ref tokens are silently misparsed.** `resolve_scope.py`'s single-token dispatch only recognizes a time-form (`3d`), `HEAD`/`HEAD~N`, or a 7–40 char hex SHA. A checkpoint branch name (`mill-checkpoint-<branch>`) matches none of these and falls through to `_explicit_scope()`, which treats every whitespace-separated token as a literal file path. `mill-merge-in` Step 5 makes this worse by instructing the literal 3-token string `git diff "$CHK"..HEAD` as `$ARGUMENTS` — the words "git" and "diff" get treated as literal (nonexistent) file paths too. The result is a silently wrong/empty scope with no error surfaced; the merge's own doc-sync step quietly does nothing on every real run.

**Why now:** all three bugs were hit in real task-branch workflows this week (2026-07-07 through 2026-07-09) and are blocking correct doc sync on stacked/nested task work, which is the millhouse project's normal mode of operation.

## Scope

**In:**
- `plugins/codeguide/scripts/resolve_scope.py`: broaden single-token dispatch so any git-resolvable ref (not just hex SHAs) routes through the head-rev path; add an optional `--parent <ref>` CLI flag that, when present, is used verbatim as the no-arg mode's base branch (bypassing `_detect_base_branch()`'s origin/HEAD probe).
- `plugins/mill/scripts/_parent_branch.py`: add `resolve_for_codeguide(status_path: Path) -> str | None` — a non-interactive, exception-swallowing wrapper around the existing `resolve()` that returns `None` when there's no recorded parent (missing file, missing `parent:` row), instead of raising or prompting. Signature mirrors `resolve()` exactly — takes an already-resolved `status_path`, never a `hub_root` it would have to resolve internally.
- `plugins/mill/skills/git-commit/SKILL.md` Step 2: before invoking `codeguide-update`, resolve `status_path` via `_paths.resolve_task_path(hub_root, cfg['paths']['status_md'])` (same pattern as mill-start's own Path Setup and mill-merge-in's Entry), then call `resolve_for_codeguide(status_path)`; if it returns a branch name, pass `--parent <branch>`; otherwise invoke exactly as today (no-arg).
- `plugins/mill/skills/mill-merge-in/SKILL.md` Step 5: change the passed argument from the literal string `git diff "$CHK"..HEAD` to the single token `"$CHK..HEAD"`.
- `plugins/codeguide/unit_tests/test-resolve-scope.py`: extend with scenarios for `--parent` override and non-hex ref-token dispatch, plus a regression guard that explicit multi-token path scope is unaffected by the broadened single-token ref check.
- A new/extended unit test for `_parent_branch.resolve_for_codeguide`.

**Out:**
- No change to `resolve.py` (codeguide-root resolution) — unrelated script, unaffected.
- No change to `codeguide-update`'s SKILL.md `$ARGUMENTS` contract (still no-arg / time / `HEAD~N` / explicit paths) — `--parent` is an additive, mill-only flag consumed inside `resolve_scope.py`, not a new documented `$ARGUMENTS` form for standalone (non-mill) users.
- No mill-awareness added to `resolve_scope.py` itself — it never imports `_mill`, `_paths`, or `_marker`, and never reads `_mill/status.md` directly. It only ever sees a branch-name string handed to it by the caller.
- No change to `_parent_branch.resolve()`'s existing interactive/raise behavior used elsewhere (mill-merge, mill-go) — `resolve_for_codeguide` is a new, additional wrapper, not a modification of the existing function.
- No retroactive fix for past codeguide-update runs that silently used the wrong scope — this task only fixes the mechanism going forward.

## Decisions

### resolve_scope.py stays mill-agnostic

- Decision: `resolve_scope.py` gains a generic `--parent <ref>` override flag but never imports mill internals or reads `_mill/status.md`. All mill-specific detection (checking for a task worktree, reading `status.md`'s `parent:` field) lives in the calling skill (`git-commit`).
- Rationale: `plugins/codeguide/scripts/resolve.py` (codeguide-root resolution) already has zero mill coupling — codeguide is designed to be usable in non-mill repos (inline or sibling mode, no `_mill/` anywhere). Coupling `resolve_scope.py` to mill's status format would break that boundary for a mill-only convenience.
- Rejected: teaching `resolve_scope.py` to read `_mill/status.md` directly. Simpler in the short term but permanently couples a codeguide script to mill's internal file format; any future non-mill caller (or mill status.md schema change) breaks it silently.

### Broaden single-token ref dispatch (fixes #611)

- Decision: replace the current hex-only/`HEAD~`/`HEAD` check with a general "does this token resolve to a commit" check: `git rev-parse --verify --quiet <token>^{commit}`. Any token that resolves (branch name, tag, checkpoint branch, hex SHA, `HEAD~N`) routes through `_head_rev_scope()`. Tokens that don't resolve continue to fall through to the existing dispatch chain (time-form check still runs first since `3d`/`1h` are not valid refs; multi-token or non-resolving single tokens still hit `_explicit_scope()`).
- Rationale: fixes the root cause generically — checkpoint branches, parent branches, and arbitrary refs all resolve the same way — instead of special-casing the current `mill-checkpoint-*` naming convention, which could change independently of this fix.
- Rejected: a narrow regex matching only `mill-checkpoint-*`. Brittle — breaks if the checkpoint naming convention changes, and doesn't help a caller who wants to pass a plain branch name (needed for the `--parent` flag below).

### mill-merge-in Step 5 argument fix (fixes #611's second half)

- Decision: change the instructed argument from the literal string `git diff "$CHK"..HEAD` (3 whitespace-separated tokens: `git`, `diff`, `"$CHK"..HEAD`) to the single token `"$CHK..HEAD"`.
- Rationale: `codeguide-update`'s `$ARGUMENTS` was never meant to carry a full git command — only a scope token/range. The "git diff" prefix was always wrong, independent of the ref-dispatch fix above. `resolve_scope.py` does not currently parse a `<ref>..HEAD` range syntax as a single token; the fix passes the checkpoint branch name as `$CHK..HEAD`, which — combined with the broadened ref dispatch — needs `resolve_scope.py` to strip a **literal trailing `..HEAD` suffix only** (not a general `..`-split) from a single token before the ref-resolution check (a token like `mill-checkpoint-foo..HEAD` doesn't resolve as-is via `rev-parse --verify`, but `mill-checkpoint-foo` does, once the `..HEAD` suffix is stripped). See Technical context for the exact parsing rule.
- Rejected: resolving `$CHK` to its hex SHA first in mill-merge-in (the issue's alternative suggestion (a)). Works but pushes an extra `git rev-parse` round-trip into every mill-merge-in run and doesn't fix the general case (any other caller passing a bare branch..HEAD range would still break).

### --parent flag takes unconditional precedence in no-arg mode (fixes #617/#621)

- Decision: when `--parent <branch>` is supplied and `args` is otherwise empty, `_no_arg_scope()` uses `<branch>` directly as `parent`/`base_branch` and skips `_detect_base_branch()`'s `origin/HEAD` → `origin/main` → `origin/master` probe entirely. When `--parent` is absent, behavior is unchanged (today's git-native detection).
- Rationale: issue #621 explicitly asks that the task's declared parent win over the origin/HEAD/main fallback, not merely backstop it — on a stacked branch, origin/HEAD's answer (`main`) is never correct even when it successfully resolves, so precedence must be unconditional, not "fill in when detection fails."
- Rejected: using `--parent` only as a fallback when `_detect_base_branch()` returns `None`. Doesn't fix the actual bug — on a real repo `origin/HEAD` almost always resolves successfully (to `main`), so the fallback path would never trigger.

### Parent-hint computation lives in git-commit only

- Decision: only `git-commit` Step 2 computes and passes `--parent`. `mill-merge-in` needs no parent-hint logic — Step 5 already has an explicit checkpoint-branch ref and passes it as a positional range argument (see the mill-merge-in decision above), which is a different code path (explicit arg, not no-arg mode) from the `--parent` flag.
- Rationale: single source of truth for "how does a mill caller learn its task's parent" avoids duplicating detection logic (and its `ParentBranchError` handling) across two skills and the codeguide-update SKILL.md itself.
- Rejected: duplicating the same status.md-check-and-resolve logic inside `codeguide-update`'s own SKILL.md steps. Would reintroduce mill-awareness into a skill that's meant to work in non-mill repos too (codeguide-update is invoked by contexts other than git-commit).

### New helper: _parent_branch.resolve_for_codeguide

- Decision: add `resolve_for_codeguide(status_path: Path) -> str | None` to `plugins/mill/scripts/_parent_branch.py`. Signature mirrors `resolve()` exactly — it takes an already-resolved `status_path`, never a `hub_root`, and never joins a hardcoded `"_mill/status.md"` literal internally. The caller (`git-commit`) resolves `status_path` via `_paths.resolve_task_path(hub_root, cfg['paths']['status_md'])` before calling this helper, same as every other mill skill that needs status.md's path. Internally: calls `resolve(status_path, interactive=False)` and returns `None` (never raises) on `ParentBranchError`. Returns the branch name string otherwise.
- Rationale: `git-commit`'s SKILL.md is prose instructions for an assistant, not executable code — the "resolve parent, swallow errors" logic needs to live in a unit-testable function, not be re-derived from scratch as inline prose every time the skill runs. Matching `resolve()`'s existing signature (status_path in, not hub_root) also keeps a single path-resolution convention across both functions in this module, and satisfies the CLAUDE.md invariant that all path resolution goes through `_paths.py` rather than an inline hardcoded join inside `_parent_branch.py`.
- Rejected: `resolve_for_codeguide(hub_root: Path)` resolving the sub-path internally via a hardcoded `"_mill/status.md"` literal. Works today but silently ignores `cfg['paths']['status_md']` if a hub ever overrides that config key, and duplicates path-join logic `_paths.py` already owns.
- Rejected: leaving the check as inline SKILL.md prose with no dedicated helper. Untestable, and risks drifting from `_parent_branch.resolve()`'s actual error-handling contract over time.

## Technical context

- **`resolve_scope.py`'s current dispatch** (see module docstring, lines 1–39): no-arg → time-form regex → `HEAD~`/`HEAD`/hex-SHA regex → explicit-paths fallback. The fix changes step 3 from a narrow regex to a live `git rev-parse --verify --quiet <token>^{commit}` check, and needs to handle the `<ref>..HEAD` suffix (used by the mill-merge-in caller) with a **narrow, literal rule**: if the token ends with the exact literal suffix `..HEAD`, strip that suffix and verify the remainder resolves as a ref; any other token containing `..` (e.g. a genuine `<ref>..<other-ref>` range, which no current caller produces) falls through unchanged to the existing dispatch chain rather than being split generically. This mirrors what `_head_rev_scope` already does internally — it builds `f"{token}..HEAD"` from a bare token, so a caller-supplied `<ref>..HEAD` needs the literal `..HEAD` stripped before reaching `_head_rev_scope`, not appended twice, and not generically split at the last `..`.
- **argparse changes**: `_cli()`'s parser currently only has `args: nargs="*"`. Add `--parent` as an `argparse` optional (e.g. `parser.add_argument("--parent", default=None)`), read via `parsed.parent`, threaded into `enumerate_scope(args, cwd=None, parent=None)` as a new optional kwarg — only consulted inside `_no_arg_scope()`, and only meaningful when `args` is empty (positional args already take priority over no-arg mode in the existing `enumerate_scope` control flow, so no new precedence rule is needed there).
- **`_no_arg_scope(toplevel, parent=None)` change**: when `parent` is provided, use it directly (skip the `_detect_base_branch()` call entirely — no need to even attempt origin/HEAD probing). When absent, unchanged.
- **`_parent_branch.py`** already has `_read_parent_from_status()` and `resolve()` — `resolve_for_codeguide` is a thin wrapper, not a rewrite. Existing `ParentBranchError` semantics are untouched; the new function only adds a catch-and-return-`None` layer for the codeguide-update caller, which has no interactive fallback and no reason to halt the commit flow over a missing parent (git-commit should degrade to the existing no-arg default, not block a commit).
- **git-commit's actual invocation mechanics**: `git-commit` currently invokes `@codeguide:codeguide-update` with no arguments via the Skill tool (SKILL.md Step 2, line 19). The fix needs the SKILL.md prose to instruct: (a) resolve `hub_root` via `_paths.resolve_hub_path()` and `status_path` via `_paths.resolve_task_path(hub_root, cfg['paths']['status_md'])` — the same two calls used elsewhere in this session's mill-start Path Setup and in mill-merge-in's Entry, never a hardcoded `_mill/status.md` literal; (b) run `resolve_for_codeguide(status_path)` via the standard `$MILL_PYTHON -c "..."` cache-form invocation (per this repo's CLAUDE.md `## Script invocation` convention); (c) branch on its stdout: empty/`None` → invoke codeguide-update with existing `$ARGUMENTS` (today's behavior, likely still none in the typical case); non-empty → prepend `--parent <branch>` to whatever `$ARGUMENTS` codeguide-update would otherwise receive.
- **Existing test file to extend**: `plugins/codeguide/unit_tests/test-resolve-scope.py` (236 lines, 13 scenarios, no mill coupling in any scenario). It's run via `plugins/codeguide/unit_tests/run-all.py`. No existing scenario exercises a non-hex single-token ref or the `--parent` flag — all 13 current scenarios must keep passing unchanged (broadening the ref check must not flip any of scenario 10's `explicit paths (valid and nonexistent)` behavior, since `a.py`/`nonexistent.py` don't resolve as git refs and must still hit `_explicit_scope()`).
- **git-commit is used outside mill task worktrees too** (e.g. committing directly to `main`/hub repos with `--onmain`) — the parent-hint computation must degrade silently (no error, no prompt) whenever `_mill/status.md` doesn't exist or has no mill-spawn marker, since `git-commit` is a general-purpose skill, not mill-task-only.

## Constraints

- No `CONSTRAINTS.md` present at hub root — none to enumerate beyond this repo's `CLAUDE.md` conventions (already reflected above: `$MILL_PYTHON` cache-form invocation, ASCII-only script output, `_paths.py` for all path resolution).
- `resolve_scope.py` must remain callable with zero mill context present (per its own module docstring's public API contract) — the `--parent` flag is optional and additive, never required.
- All 13 existing `test-resolve-scope.py` scenarios must continue to pass unmodified — this task is additive to that file, not a rewrite of its existing assertions.

## Testing

- **`plugins/codeguide/unit_tests/test-resolve-scope.py`** (extend, TDD candidate):
  - New scenario: single non-hex branch-name token (e.g. checkout a branch named `mill-checkpoint-feature`, commit on it, then run `enumerate_scope(["mill-checkpoint-feature..HEAD"], cwd=...)` from a different branch that has it as an ancestor) → asserts `mode == "head-rev"` and the correct file set, mirroring existing scenario 8's `HEAD~3` shape but with a branch-name-plus-suffix token.
  - New scenario: same branch name without the `..HEAD` suffix, passed bare as a single token → asserts identical `head-rev` routing (covers the case where a caller passes just the ref, not a range).
  - New scenario: `--parent` flag / `parent=` kwarg override on a repo where `origin/HEAD` resolves to `main` but `--parent` names a different branch → asserts `summary["parent"] == "<the --parent value>"` and `summary["base_branch"]` reflects the override, not `main`. Mirrors existing scenario 3's task-branch shape but with an explicit override present.
  - Regression guard alongside the broadened dispatch: re-affirm scenario 10 (`["a.py", "nonexistent.py"]`) still returns `mode == "explicit"` — add an explicit assertion comment noting this guards against the ref-check false-triggering on path-shaped strings that happen to not exist as refs (already true today, since `git rev-parse --verify --quiet` on `a.py` fails cleanly — no other change needed here, but the assertion should be explicit as a regression tripwire).
  - New single-token explicit-path regression scenario: a **single** file path token that does not resolve as a git ref (e.g. `enumerate_scope(["a.py"], cwd=...)` where no branch/tag/commit named `a.py` exists) must still return `mode == "explicit"`, not be misrouted into `_head_rev_scope()` by the broadened single-token dispatch. This is distinct from scenario 10's two-token case — the broadened ref-check only activates on the `len(args) == 1` branch, so a single-token path is exactly the case most likely to be accidentally caught by the new `rev-parse --verify` probe and needs its own explicit assertion.
- **New test for `_parent_branch.resolve_for_codeguide`** (TDD candidate, likely a new `plugins/mill/unit_tests/test-_parent_branch.py` or extension of an existing one if it already exists — check before creating): scenarios for (a) status.md with a `parent:` row → returns the branch name; (b) missing status.md → returns `None`, no raise; (c) status.md present but no `parent:` row → returns `None`, no raise (mirrors `resolve()`'s `ParentBranchError` path but caught).
- **Integration-level** (manual or `plugins/mill/integration_tests/`, lower priority than the unit tests above): a real stacked-branch scenario exercising `git-commit`'s end-to-end Step 2 flow, confirming `--parent` actually reaches `resolve_scope.py` and narrows scope correctly — this is the actual repro shape from #617/#621, so worth at least one integration-level check even though the unit tests above cover the underlying mechanism in isolation.

## Q&A log

- **Q:** Should `resolve_scope.py` stay mill-agnostic with a generic `--parent` override, or read `_mill/status.md` directly? **A:** [auto-pick] Stay mill-agnostic; generic `--parent` flag. **Why:** matches `resolve.py`'s existing zero-mill-coupling precedent — codeguide must remain usable in non-mill repos.
- **Q:** How should checkpoint/branch-name refs be recognized for #611? **A:** [auto-pick] Broaden single-token dispatch to any git-resolvable ref via `rev-parse --verify --quiet`. **Why:** fixes the root cause generically (branch names, tags, checkpoints) instead of a narrow regex that only covers today's naming convention.
- **Q:** How to fix mill-merge-in Step 5's malformed argument string? **A:** [auto-pick] Pass `"$CHK..HEAD"` as a single token. **Why:** simplest fix once broadened ref-dispatch (previous answer) lands; avoids an extra `git rev-parse` round-trip.
- **Q:** Where does `--parent` take precedence in `_no_arg_scope()`? **A:** [auto-pick] Unconditional precedence over origin/HEAD detection when supplied. **Why:** issue #621 explicitly asks that the declared parent win over the origin/HEAD/main fallback, not just backstop it.
- **Q:** Which skill computes and passes `--parent`? **A:** [auto-pick] `git-commit` Step 2 only. **Why:** single source of truth; mill-merge-in already has an explicit ref and needs no parent-hint logic; avoids duplicating detection logic in codeguide-update.
- **Q:** Unit test coverage for the resolve_scope.py changes? **A:** [auto-pick] Extend existing test-resolve-scope.py with `--parent` override, non-hex ref-token, and explicit-paths regression scenarios. **Why:** the file already covers exactly this contract; extending it keeps one source of truth for the scope-resolution behavior spec.
- **Q:** Where should git-commit's mill-detection logic for the parent hint live? **A:** [auto-pick] New helper `_parent_branch.resolve_for_codeguide()`. **Why:** SKILL.md prose can't be unit-tested directly; a small helper function keeps the `ParentBranchError`-swallowing logic testable and out of prose.
