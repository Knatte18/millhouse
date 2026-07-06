# Discussion: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs

```yaml
task: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs
slug: nested-layout-fixes
status: discussing
parent: main
```

## Problem

Five GitHub issues (#603, #608, #601, #607, #604) all share one root cause: code paths in `plugins/mill/scripts/` that assume the mill project root (`hub_root`, resolved via `_paths.resolve_hub_path()`) is identical to the git repository root (`git_root`). That assumption holds for most repos but breaks for "nested hub layout" repos where the mill hub lives in a subdirectory of the git root (e.g. `src/csharp/NORCE.Models`). In those repos, scope-violation checks false-positive and block every Handoff, review CLIs write briefs to the wrong `_mill/` directory, and the finalize verify step can run from the wrong cwd and fail with MSB1009-style errors. This surfaced on a real nested-layout repo; the fix needs to make all five sites nested-aware without regressing the (more common) flat-layout case where `hub_root == git_root`.

## Scope

**In:**
- `_cleanliness.compute_scope_violations` and `_cleanliness.clean_ephemeral_scope_violations` — fix false-positive scope violations in nested layouts (#603, #608; one underlying bug, two signatures to update).
- The `clean_ephemeral_scope_violations` call site at `plugins/mill/skills/mill-go/SKILL.md:749` — updated to pass both `hub_root` and `git_root` (both already resolvable locals at that point in the SKILL).
- `millpy-review-plan.py` and `millpy-review-code.py` — fix `brief_path` to resolve under the hub root, not git_root (#601, #607).
- Verify-command cwd policy across `_implementer_common.py`, `millpy-implement.py`, plan schema, and `_plan_validate.py` — add an explicit `cwd` field to plan verify steps (both per-batch and module-wide/overview) so nested-layout plans can opt into hub-relative execution without regressing the git-root-relative convention pinned for #554 (#604).
- New nested-layout test fixture(s), reused across the affected test files, including the 9 existing `test-cleanliness.py` CESV cases (updated to pass both roots).
- Updating the mill-plan skill/template so newly authored plans on nested-layout tasks set `cwd: hub` and write hub-relative verify commands.

**Out:**
- Any migration/cleanup of already-existing orphaned `_mill/briefs/` directories left at git_root by the #601/#607 bug — left to `mill-cleanup`'s general sweep, not this task.
- Changing `_pygit2_util.status_porcelain`'s low-level path semantics (it stays git-root-relative; callers rebase).
- Retroactively rewriting existing plans' verify commands — the `cwd` field defaults to `git_root` so existing plans are unaffected.
- Any redesign of the junction system itself (`.active`/`.wiki`/`.portals` continue to live at `hub_root`, unchanged).

## Decisions

### compute_scope_violations rebasing

- Decision: Change `compute_scope_violations(worktree: Path)` to `compute_scope_violations(hub_root: Path, git_root: Path)`. Internally, keep calling `_pygit2_util.status_porcelain(hub_root, include_untracked=True)` (unchanged — pygit2 discovers the repo and reports git-root-relative paths regardless of which path is passed), then compute the hub-relative prefix (`hub_root` relative to `git_root`, POSIX-normalized) and strip it from each reported path before applying the existing `_mill/`-prefix check and junction first-segment (`_JUNCTION_SKIP_SET`) check. When `hub_root == git_root` the prefix is `""`, so stripping is a no-op and flat-layout behavior is byte-identical to today.
- Rationale: `_pygit2_util.status_porcelain` always returns git-root-relative paths no matter what path is passed to it — the four call sites in `_implementer_common.py` already pass `project_root` (the correct hub root) as `worktree`, but that alone doesn't fix anything because the string paths returned are still git-root-relative. The double failure mode (both the `_mill/` check and the junction check misfire) needs the git_root→hub_root prefix, not just a differently-named single path argument.
- Rejected: Changing `status_porcelain` itself to accept a root override (touches a shared low-level helper used elsewhere, higher blast radius); shelling out to `git -C <hub_root> status --porcelain` instead of pygit2 (introduces a second status-reading code path with potentially different quoting/edge-case behavior).

### compute_scope_violations caller signature

- Decision: All four call sites in `_implementer_common.py` (lines ~1077, ~1175, ~1264, ~1408) pass both `project_root` and `git_root` explicitly. `git_root` is already threaded as a parameter through the enclosing functions in this file (used for `_run_verify_gate`'s `git_root=` kwarg), so no new path resolution needs to be added at these call sites — just pass the existing local `git_root` through. `clean_ephemeral_scope_violations` (`_cleanliness.py:210`) also changes its signature from `(worktree: Path)` to `(hub_root: Path, git_root: Path)`, forwarding both straight into `compute_scope_violations`. Its own file-removal join at line 268 (`worktree / violation`) is renamed to `hub_root / violation` with no behavior change, since `compute_scope_violations` now returns hub-relative paths and `hub_root` was already the value this parameter held at every real call site. The one external caller, `plugins/mill/skills/mill-go/SKILL.md:749` (`_cleanliness.clean_ephemeral_scope_violations(worktree_root)`), is updated to `clean_ephemeral_scope_violations(worktree_root, git_root)` — both `worktree_root` (itself resolved via `_paths.resolve_active_hub(..., git_root=git_root)` at SKILL.md:42, i.e. already the hub root) and `git_root` are already local variables in scope at that point in the SKILL, so no new resolution call is needed there either. The 9 existing CESV test cases in `test-cleanliness.py` (lines ~556-778, `clean_ephemeral_scope_violations(tmp_path)`) are updated to pass `(tmp_path, tmp_path)` — same value for both roots, since those fixtures are flat-layout — preserving their existing assertions unchanged.
- Rationale: Matches CLAUDE.md's path invariant — "helpers with path args must not consult cwd for config" — and keeps `compute_scope_violations` unit-testable with synthetic paths, no real `.millhouse/config.local.yaml` needed. Propagating the signature change to `clean_ephemeral_scope_violations` and its one real caller closes the gap where the rebase would otherwise happen inside `compute_scope_violations` but silently break the caller that joins violation paths back to a filesystem location for deletion.
- Rejected: Having `compute_scope_violations` call `_paths.resolve_hub_path()` / `_paths.resolve_git_root()` internally — couples a low-level cleanliness helper to config/cwd resolution and makes it untestable in isolation. Leaving `clean_ephemeral_scope_violations`'s signature at one arg and re-deriving `git_root` inside it — same coupling problem, one level up.

### brief_path fix for review-plan / review-code

- Decision: In `millpy-review-plan.py` (~line 151-153) and `millpy-review-code.py` (~line 150-152), change `briefs_dir = _paths.resolve_task_path(git_root, "_mill/briefs/")` to `briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")` (where `project_root = _paths.resolve_hub_path()`, already computed in both scripts). Delete the incorrect comment ("Write the brief under the task worktree (git_root)…") since it describes the bug, not the intent. No orphaned-directory migration.
- Rationale: This is a straight regression — `millpy-review-discussion.py` already does this correctly (`briefs_dir = _paths.resolve_task_path(hub_dir, "_mill/briefs/")`), and both broken scripts have identical copy-pasted code, introduced by commit `e5e26571`. The fix is copying the already-correct pattern.
- Rejected: Adding cleanup of orphaned git-root `_mill/briefs/` dirs from before the fix — no evidence any real repo currently has such dirs; general orphan cleanup already belongs to `mill-cleanup`.

### Verify-cwd explicit field (#604)

- Decision: Add an explicit `cwd` field to plan verify steps — both per-batch (batch file frontmatter `verify:`) and module-wide (overview file frontmatter `verify:`) — accepted values `hub` or `git_root`, defaulting to `git_root` when absent (preserves every existing plan's behavior and the #554-pinned unit test in `test-implementer-common.py` unchanged). The `verify:` frontmatter value becomes either a plain string (implicit `cwd: git_root`, today's format, unchanged) or a `{cwd: ..., command: ...}` mapping.
  - `millpy-implement.py` is the actual read site: `batch_frontmatter.get("verify")` (lines ~371, ~591) and `overview_frontmatter.get("verify")` (line ~311) both currently assume a bare string. A shared helper (e.g. `_plan_dag.parse_verify_field(frontmatter, hub_root, git_root) -> tuple[str | None, Path | None]`) normalizes both forms, returning the command string and a resolved `cwd` Path (`None` for the string form, meaning "use the existing default"; `hub_root` or `git_root` resolved from the mapping form otherwise). All three call sites use this helper before passing `verify_cmd` onward.
  - `_run_verify_gate` in `_implementer_common.py` gains a `cwd_override: Path | None = None` kwarg (in addition to its existing `git_root` kwarg). When `cwd_override` is not None, it takes precedence over the existing `git_root if git_root is not None else project_root` fallback. `millpy-implement.py` passes the resolved cwd from the helper above as `cwd_override` for both the per-batch and module-wide verify gate calls.
  - `_plan_validate.py`'s `_check_verify_not_isolated` / `_check_verify_full_suite` are updated to accept `verify` as either a plain string or the `{cwd, command}` mapping, extracting `command` either way before applying their existing string checks (PYTHONPATH-prefix check, run-all.py filter check).
  - The mill-plan skill/template is updated so that when authoring a plan for a task where `_paths.resolve_hub_path() != _paths.resolve_git_root()` (nested layout), it sets `cwd: hub` (per-batch and module-wide, as applicable) and writes the verify command hub-relative. CLAUDE.md's PYTHONPATH auto-prepend rule (mill-plan auto-prepends `PYTHONPATH=` on `verify-not-isolated` validator failure) operates on the extracted `command` string, not the raw frontmatter value, so it works unchanged against either form.
- Rationale: #554 and #604 are mirror-image bugs from two different nested-layout repos with opposite verify-command authoring conventions (git-root-relative vs hub-relative) — there is no single default cwd that satisfies both. A heuristic ("nested layout → always cwd=hub_root") would silently reintroduce #554 for any nested-layout plan that intentionally wants git-root-relative commands. An explicit per-plan field is the only option that fixes #604 without regressing #554's pinned test. Extending the field to module-wide verify too (not just per-batch) avoids leaving a partial fix that still reproduces #604 for any repo whose *overview*-level verify command is hub-relative.
- Rejected: Heuristic auto-detect based solely on `hub_root != git_root` (reintroduces #554's failure mode for nested-layout plans authored git-root-relative); leaving `cwd=git_root` permanent and treating #604 as a plan-authoring error only (leaves the filed bug unresolved with no code fix); scoping the field to per-batch verify only (leaves module-wide verify exposed to the same bug class).

### Test coverage

- Decision: Add a shared nested-layout test fixture (a temp repo with `hub_root` nested one level under `git_root`, plus the standard junctions created at `hub_root`) reused across `test-cleanliness.py` (for `compute_scope_violations`), `test-review-plan-flow.py` and `test-review-code-flow.py` (for `brief_path`), and a new case in `test-implementer-common.py` (for the `cwd` field, alongside the existing #554-pinned flat-layout case which must stay green).
- Rationale: Current tests for all four affected files only exercise the flat-layout case (`git_root == project_root`), which is precisely why none of these five bugs were caught before shipping.
- Rejected: Manual verification only — doesn't prevent regression and contradicts `mill:testing` conventions.

## Technical context

- **`_paths.py`**: `resolve_hub_path(cwd=None) -> Path` (~line 155) is the canonical nested-aware root resolver — walks up from cwd for `.millhouse/config.local.yaml`, honors `hub_relative_path:` when set. `resolve_task_path(worktree_root, cfg_relative_path) -> Path` (~line 533) does no root selection itself; correctness is 100% dependent on the caller passing the right root — this is exactly where #601/#607 pass the wrong one.
- **`_cleanliness.py:59-77`** — current buggy `compute_scope_violations`:
  ```python
  def compute_scope_violations(worktree: Path) -> list[str]:
      lines = _pygit2_util.status_porcelain(worktree, include_untracked=True)
      violations = []
      for line in lines:
          if line.startswith("?? "):
              path = line[3:]
              if not path.startswith("_mill/"):
                  first_segment = path.split("/")[0]
                  if first_segment not in _JUNCTION_SKIP_SET:
                      violations.append(path)
      return sorted(violations)
  ```
  `clean_ephemeral_scope_violations` (`_cleanliness.py:210-243`) is the only caller within `_cleanliness.py`; it forwards `worktree` into `compute_scope_violations` and also joins violation strings back to disk at line 268 (`file_path = worktree / violation`) for `os.remove` — both its signature and that join line need to change (see Decision above). Its own external caller is `plugins/mill/skills/mill-go/SKILL.md:749` (`_cleanliness.clean_ephemeral_scope_violations(worktree_root)`), where `worktree_root` is resolved at `SKILL.md:42` via `_paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)` — i.e. already the hub root, with `git_root` already a local in scope at that point too.
- **Callers to update** (all in `_implementer_common.py`, currently `_cleanliness.compute_scope_violations(project_root)`): lines ~1077, ~1175, ~1264, ~1408. `git_root` is already an in-scope local/parameter at each site (used for `_run_verify_gate(..., git_root=git_root)` nearby).
- **`test-cleanliness.py`**: 9 existing CESV cases (lines ~538-778) call `clean_ephemeral_scope_violations(tmp_path)` with a single arg; all update to `clean_ephemeral_scope_violations(tmp_path, tmp_path)` (flat-layout fixtures, same value for both roots — assertions unchanged).
- **`millpy-review-plan.py:151-153`** and **`millpy-review-code.py:150-152`** — identical buggy lines:
  ```python
  # Write the brief under the task worktree (git_root), not the hub root,
  # so the implementer's brief path is relative to the task branch checkout.
  briefs_dir = _paths.resolve_task_path(git_root, "_mill/briefs/")
  ```
  Introduced by commit `e5e26571`. Correct existing pattern to copy: `millpy-review-discussion.py:105` — `briefs_dir = _paths.resolve_task_path(hub_dir, "_mill/briefs/")` where `hub_dir = resolve_hub_path()`.
- **`_implementer_common.py:540-580` (`_run_verify_gate`)** — current cwd selection: `effective_cwd = git_root if git_root is not None else project_root`. `git_root` is threaded from `millpy-implement.py` / `millpy-fix.py` call sites and is always non-None in practice today, so verify always runs at `git_root`. This behavior is pinned by `test-implementer-common.py` (~line 1635, "Test A: git_root kwarg selects cwd for the verify subprocess (#554)") — the fix must keep that test's flat-layout assertion green while adding the new `cwd_override` kwarg's hub-relative branch (see Decision above; `cwd_override` takes precedence over the existing `git_root`/`project_root` fallback when not None, leaving the pinned #554 assertion — which never sets `cwd_override` — untouched).
- **`millpy-implement.py`** — actual `verify` frontmatter read sites: `batch_frontmatter.get("verify")` at lines ~371 and ~591 (per-batch), `overview_frontmatter.get("verify")` at line ~311 (module-wide). All three currently assume a bare string and pass it straight through to `finalize_from_output` / `_forward_output` / `_run_verify_gates` as `verify_cmd`. All three route through the new `_plan_dag.parse_verify_field(...)` helper to extract `(command, resolved_cwd)` and thread `resolved_cwd` onward as `_run_verify_gate`'s new `cwd_override` kwarg.
- **`_plan_validate.py`** — `_check_verify_not_isolated` (~line 1214) and `_check_verify_full_suite` (~line 1266) both currently do `verify = parsed.get("verify"); if verify is None or not isinstance(verify, str): continue`. Both need updating to also accept the `{cwd, command}` mapping form and extract the command string from it before running their existing string checks.
- **Junction config**: `plugins/mill/templates/mill-config.yaml:60-64` — junctions (`.wiki`, `.portals`, `.active`) are physically created at `hub_root`, never `git_root`. This is exactly why the git-root-relative first-segment check in `compute_scope_violations` misses them in nested layouts.
- **Commit history**: `e5e26571` introduced #601/#607 (changed correct `project_root` to incorrect `git_root` for briefs_dir, with a since-stale comment). `00203c20` → `82bc02b0` → `a850eec6` introduced #604 as a side effect of fixing #554 (switched `_run_verify_gate` cwd default from `project_root` to `git_root`).

## Testing

- **`compute_scope_violations`**: TDD candidate. New nested-layout fixture case: untracked file at `<hub>/_mill/foo` and a junction at `<hub>/.active` must both be correctly excluded when `hub_root` is nested one level under `git_root`; existing flat-layout cases must remain green.
- **`clean_ephemeral_scope_violations`**: extend the 9 existing CESV cases in `test-cleanliness.py` to pass `(hub_root, git_root)`; add one new nested-layout CESV case asserting both correct violation detection and correct on-disk removal path (the `hub_root / violation` join) when `hub_root` is nested.
- **`millpy-review-plan.py` / `millpy-review-code.py`**: extend `test-review-plan-flow.py` / `test-review-code-flow.py` with a nested-layout case asserting `briefs_dir` resolves under the nested `project_root`, not `git_root`.
- **`_run_verify_gate` / plan `cwd` field**: extend `test-implementer-common.py` with a case asserting `cwd_override` (when set) takes precedence over the `git_root`/`project_root` fallback, alongside the existing #554 case (`git_root` kwarg / default, `cwd_override` absent) which must stay green unchanged. Cover both the per-batch and module-wide verify paths in `millpy-implement.py`'s own test coverage, asserting `parse_verify_field` correctly extracts `(command, cwd)` from both the plain-string and `{cwd, command}` mapping forms.
- **`_plan_validate.py`**: extend existing verify-command validation tests with a case where `verify` is authored as a `{cwd, command}` mapping, asserting `_check_verify_not_isolated` / `_check_verify_full_suite` still validate the extracted command string correctly.

## Q&A log

- **Q:** How should #603/#608 (`compute_scope_violations`) be fixed? **A:** [auto-pick] Add `hub_root`/`git_root` params; rebase pygit2's git-root-relative paths by stripping the hub-relative prefix before the existing `_mill/`-prefix and junction checks. **Why:** lowest blast radius — doesn't touch the shared `status_porcelain` helper, and is a no-op for flat layouts.
- **Q:** Where should `compute_scope_violations` get `hub_root`/`git_root` from? **A:** [auto-pick] Callers pass both explicitly (already available as locals in `_implementer_common.py`). **Why:** CLAUDE.md path invariant — helpers with path args must not consult cwd for config — and keeps the function unit-testable with synthetic paths.
- **Q:** How to fix #601/#607 brief_path, and do orphaned dirs need cleanup? **A:** [auto-pick] Change `git_root` → `project_root` in both scripts (matching `millpy-review-discussion.py`'s existing correct pattern); no migration for pre-existing orphans. **Why:** straight regression fix; orphan cleanup is YAGNI absent evidence, and belongs to `mill-cleanup` generally.
- **Q:** How to resolve the #604 vs #554 verify-cwd conflict? **A:** [auto-pick] Add an explicit `cwd: hub|git_root` field to plan verify steps, defaulting to `git_root`; mill-plan sets `cwd: hub` for nested-layout tasks at plan-write time. **Why:** #554 and #604 are mirror-image bugs from repos with opposite authoring conventions — no single default cwd satisfies both; a heuristic would silently reintroduce #554, and leaving it as a plan-authoring-only fix leaves #604 uncoded.
- **Q:** Do we need new nested-layout test coverage? **A:** [auto-pick] Yes — a shared nested-layout fixture reused across `test-cleanliness.py`, `test-review-plan-flow.py`, `test-review-code-flow.py`, and a new `test-implementer-common.py` case. **Why:** current tests only exercise the flat-layout case, which is precisely why none of these five bugs were caught before shipping.
