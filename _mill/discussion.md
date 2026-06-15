# Discussion: Fix millpy-review-plan validator gaps and resolve_ref_paths path-doubling

```yaml
task: Fix millpy-review-plan validator gaps and resolve_ref_paths path-doubling
slug: review-plan-and-ref-paths
status: discussing
parent: main
```

## Problem

Three closed bug issues (#465, #466, #471) were folded into this task because
they share one underlying theme — the plan-review and code-review CLIs resolve
filesystem paths against the wrong base, and the plan-review validator gate does
not run in agent dispatch mode. The issues were filed against the NORCE Models
repo (`src/csharp/NORCE.Models` layout), which is an **M2+sub** repo: the mill hub
(where `_mill/` and `mill-config.yaml` live) is a *subfolder* of the git worktree
root, and the task-terminal cwd sits at that subfolder.

- **#465** — During `/mill-plan` Phase: Plan Review with `dispatch: agent`, the
  pre-review validator gate (`_plan_validate`) never runs. It is wired only into
  the `--stage full` branch; agent mode calls `--stage prepare` then
  `--stage finalize`, neither of which validates. The mill-plan SKILL falsely
  claims (SKILL.md:133) the validator "runs unchanged in BOTH modes."
- **#466** — The `--stage full` validator originally mis-resolved the plan dir,
  emitting `<slug>._mill\plan` (slug concatenated with the path template) and
  then reporting a spurious `missing-overview`. The slug-concatenation symptom is
  **already gone** (the `resolve_path` rewrite + revert chain below), but a
  residual base-consistency defect remains: the validator finds the plan via one
  base but resolves the cards' source-ref paths against another.
- **#471** — `_review_common.resolve_ref_paths` doubles the `root:` sub-path when
  cwd is itself that sub-path: `candidate = project_root / root / raw` becomes
  `git_root/root/root/raw`. A workaround (additive `git_root/root/raw` fallback)
  is already in the code; the issue explicitly asks for a maintainer decision on
  the canonical fix.

**Why now:** these blocked real review runs in the NORCE repo (the holistic code
review for `cuttings-2-1-data-model` hard-failed; the plan validator was bypassed
for `clone-means-independent-copy`). All three are closed-with-workaround and
need a proper, tested fix in the plugin source.

## Scope

**In:**

- `plugins/mill/scripts/millpy-review-plan.py` — run `_plan_validate` in
  `--stage prepare` (emit the errors envelope + exit 1 on findings); thread
  `git_root` + overview `root:` into the `_plan_validate.run` call in
  `--stage full`.
- `plugins/mill/scripts/_plan_validate.py` — accept and forward `git_root` to its
  `resolve_existing_paths` calls so source-ref checks are robust to subfolder cwd.
- `plugins/mill/scripts/_review_common.py` — make `git_root/root/raw` the
  **primary** source-ref resolution (when `root` is set) in both
  `resolve_ref_paths` and `resolve_existing_paths`. NOTE the asymmetry:
  `resolve_ref_paths` already *has* a `git_root/root/raw` candidate
  (lines ~656) and only needs **reordering**; `resolve_existing_paths` has
  only `git_root/raw` today (lines ~721-726) and needs a `git_root/root/raw`
  candidate **added** (not reordered). Demote `project_root/root/raw` to
  fallback in both.
- `plugins/mill/skills/mill-plan/SKILL.md` — update the agent-mode branch to
  handle a validator-failure envelope from `--stage prepare`; correct/keep the
  SKILL.md:133 "BOTH modes" claim true.
- Unit tests: `test-review-common.py`, `test-plan-validate.py`,
  `test-review-plan-flow.py` (and `test-paths.py` if base resolution is touched).

**Out:**

- Changing `resolve_path` (`_review_common.py:319`) back to worktree-root
  resolution. The Jun-13 revert (`88c08793`) is **correct and stays**: `_mill/`
  lives at the hub subfolder, not the worktree root. Do not re-apply `b62ca5e7`.
- The `millpy-review-code.py` CLI's own `project_root = Path.cwd()` assignment —
  the fix lives in the shared `resolve_ref_paths`/`resolve_existing_paths`
  helpers, so code review inherits it without touching the code CLI's wiring.
- Any change to how cwd is established for review runs, or to mill-spawn /
  mill-claim hub layout (`c2780ec3`, `d16807e6` are settled).
- New validator checks or review semantics. This task is path-resolution +
  gate-invocation correctness only.

## Decisions

### three-roots model (the unifying principle)

- Decision: Treat three filesystem bases as distinct and never conflate them.
  1. **hub** = where `_mill/` lives = `git_root / hub_relative_path`. Base for
     `_mill/plan`, `_mill/reviews`, `_mill/briefs`, `discussion.md`, `status.md`.
     Resolved via `resolve_path(...)` (container-aware; also handles the
     `--slug`-from-main cross-worktree case) or `resolve_task_path(hub, ...)`.
  2. **git_root** = repo top. Base for source `root:`/raw ref resolution →
     `git_root / root / raw`.
  3. **cwd** = incidental. In the normal pipeline `cwd == hub`, but #471 proves
     cwd can instead be the source `root:` subfolder. cwd must NOT be the base
     for source-ref resolution.
- Rationale: Every one of #466/#471 is a symptom of resolving against `cwd` when
  the correct base is `hub` (for `_mill/`) or `git_root` (for source refs). The
  user confirmed: "`_mill/` does NOT live at the worktree root; it lives at
  `<worktree_root>/<subfolder>` which is cwd" and "resolve [source refs] against
  git_root."
- Rejected: Resolving everything against a single `project_root` (the status quo
  that produced both bugs); switching `_mill/` resolution to worktree-root
  (already tried in `b62ca5e7`, reverted in `88c08793`).

### #471 — git_root is the primary source-ref base

- Decision: In `resolve_ref_paths` and `resolve_existing_paths`, when `root` is
  set, try `git_root / root / raw` **first**, then fall back to
  `project_root / root / raw`, then the bare/`git_root / raw` paths, then
  creates/deletes suppression (resolve_ref_paths only), then hard-fail
  (resolve_ref_paths) / silent-drop (resolve_existing_paths). `root:` is
  repo-relative by definition, so `git_root/root/raw` is correct regardless of
  where cwd sits — it works in both the cwd==git_root layout (mill-plan) and the
  cwd==git_root/root layout (#471). For `resolve_ref_paths` this is a reorder of
  an existing candidate; for `resolve_existing_paths` the `git_root/root/raw`
  candidate must be **newly added** (it does not exist today).
- Rationale: The current additive fallback "works" only because the doubled
  `project_root/root/raw` candidate happens not to exist on disk; that is fragile
  (a stray matching path would mask the bug). Making git_root primary removes the
  dependence on accidental non-existence.
- Rejected: (a) Keep the additive fallback as-is + only add a regression test —
  leaves the fragile ordering. (b) Drop `project_root` from source-ref resolution
  entirely — riskier; some non-`root` layouts legitimately resolve against
  `project_root`, and `git_root` may be `None` in unit contexts, so keep
  `project_root/root/raw` as a fallback rather than deleting it.

### #466 — validator base consistency, not slug-concat

- Decision: Keep `plan_dir = resolve_path(cfg["paths"]["plan_dir"], slug)` in
  `--stage full` (it correctly resolves to `hub/_mill/plan` post-revert and is
  `--slug`-safe). The fix is to thread `git_root` AND the overview `root:` into
  the `_plan_validate.run(...)` call so the validator resolves *card source-ref
  paths* against `git_root/root`, matching the three-roots model. Currently the
  full-stage call (millpy-review-plan.py ~line 186) passes neither `git_root` nor
  `root`, so a subfolder-cwd run would mis-resolve source refs exactly like #471.
- Rationale: The reported slug-concat symptom is already fixed by the
  `resolve_path` rewrite (verified empirically: `resolve_path` and
  `resolve_task_path(cwd,...)` agree in the `hub_rel="."` layout and
  `resolve_path` → `resolve_active_hub` → `resolve_hub_relative_path` handles
  `hub_rel != "."`). The real residual is that the validator's plan-dir base and
  its source-ref base must both be consistent with the three-roots model.
- Rejected: Switching `plan_dir` (CLI + backend `_review_plan.prepare/run`) to
  `resolve_task_path(project_root, ...)`. That trusts raw cwd and breaks the
  documented `--slug`-from-main cross-worktree run (cwd=main → plan looked up in
  main's `_mill/`). `resolve_path`'s container round-trip exists precisely to
  support that; keep it.

### #465 — validator gate runs inside --stage prepare

- Decision: Run `_plan_validate` inside the `--stage prepare` branch of
  millpy-review-plan.py, before writing the brief. On findings, emit the same
  `{"errors": [...], "summary": "<n> finding(s) across <m> batch(es)"}` envelope
  and `return 1` instead of the prepare/brief envelope. Update mill-plan SKILL's
  agent-mode branch to detect this envelope and apply the existing Step 1.5
  mechanical-fix loop + two-pass cap before re-running `--stage prepare`. This
  makes the SKILL.md:133 "runs in BOTH modes" claim true.
- Wiring note: unlike `--stage full`, the `prepare` branch (lines ~124-150) does
  NOT currently compute `plan_dir` or the overview `root` — it only has `cfg`,
  `slug`, `project_root`, `git_root`, `wiki_root`. The gate must construct
  `plan_dir = resolve_path(cfg["paths"]["plan_dir"], slug)`, derive `root` from
  the overview, and pass `git_root` + `root` into `_plan_validate.run(...)` so
  the agent path gets the same #466/#471 base-consistency as the full path. Use
  the `--stage full` call (lines ~181-199) as the template.
- Rationale: Single source of truth in the script (the `--stage full` branch
  already does exactly this). Putting the gate in `prepare` means it cannot be
  silently skipped by orchestrator omission — which is the exact failure #465
  reported. Plan-review `prepare` is holistic-only (one call per round), so the
  validator runs once per round, matching full-stage cadence.
- Rejected: Adding an explicit "run the validator first" step to the SKILL's
  agent-mode branch only (leaving `prepare` pure). Relies on orchestrator
  discipline — the precise thing that failed here — and duplicates the gate's
  logic across script and prose.

## Technical context

- `plugins/mill/scripts/millpy-review-plan.py`
  - `main()` sets `project_root = Path.cwd()` and `git_root = resolve_git_root()`
    (lines ~102-103) and passes both downstream.
  - `--stage prepare` (lines ~124-150): calls `_review_plan.prepare(...)`, writes
    a brief via `_agent_dispatch.write_brief`, prints a prepare envelope. **No
    validator.** Briefs already use `_paths.resolve_task_path(project_root, ...)`
    (line ~131) — the hub-base pattern to mirror.
  - `--stage full` (lines ~181-218): runs `_plan_validate.run(plan_dir,
    project_root, wiki_root=..., skip_checks=..., max_cards_per_batch=...,
    max_batch_context_tokens=...)` — note **no `git_root`, no `root`** — then
    `_review_plan.run(...)`. `plan_dir = resolve_path(cfg["paths"]["plan_dir"],
    slug)` (line ~185).
  - `--stage finalize` (lines ~151-180): `reviews_dir =
    resolve_path(cfg["paths"]["reviews_dir"], slug)`.
- `plugins/mill/scripts/_review_common.py`
  - `resolve_path(path_tmpl, slug)` (line 319): resolves a config path template
    against `active_hub` via `resolve_active_hub` — i.e. `git_root/hub_rel`.
    Container-aware; supports `--slug` from main. **Do not change.**
  - `resolve_ref_paths(...)` (line 582): resolution order currently
    `wiki/` → `project_root/root/raw` → (`git_root/root/raw`, `git_root/raw`)
    fallback → creates/deletes suppression → hard-fail (lines ~636-669). The
    #471 fallback is lines ~650-661. Reorder so `git_root/root/raw` is primary.
  - `resolve_existing_paths(...)` (line 673): silent-drop sibling of
    `resolve_ref_paths`; same routing. Its git-root fallback (lines ~721-726)
    currently tries **only** `git_root / raw` — there is no `git_root/root/raw`
    candidate to reorder. The fix here is to **ADD** a primary
    `git_root / root / raw` candidate (when `root` is set), mirroring
    `resolve_ref_paths` (~line 656). Used by the validator's
    `_check_non_existent_path` and `_check_batch_oversized`, so without this add
    the #471 layout (cwd==git_root/root) still doubles `root` and the validator
    silently drops the referenced files — defeating the threaded `git_root` from
    the #466 fix.
- `plugins/mill/scripts/_plan_validate.py`
  - `run(plan_dir, project_root, *, root=None, wiki_root=None, skip_checks=...,
    max_cards_per_batch=..., max_batch_context_tokens=...)` (line 1007). It loads
    `root` from the overview when not passed. It calls `resolve_existing_paths`
    in `_check_non_existent_path` (lines ~246, ~264) and `_check_batch_oversized`
    (line ~978) **without `git_root`**. Add a `git_root` param to `run` and
    thread it into those `resolve_existing_paths` calls.
- `plugins/mill/scripts/_paths.py`
  - `resolve_active_hub` (406), `resolve_hub_relative_path` (318),
    `resolve_task_path` (517) — the hub-base machinery. Reference only; the
    revert (`88c08793`) made these the source of truth for `_mill/` location.
- `plugins/mill/scripts/_review_plan.py`
  - `prepare` (280) / `run` (528) / `finalize` (472) all receive `project_root`
    and `git_root` and internally call `resolve_path(cfg["paths"]["plan_dir"],
    slug)` (line ~298) and pass `git_root` into `resolve_ref_paths`. They already
    follow the three-roots model for source refs; leave their plan_dir on
    `resolve_path`.
- Git history that matters: `b62ca5e7` (resolve_path → worktree root) **reverted**
  by `88c08793`; `c2780ec3` (spawn creates `_mill/` at hub subdir);
  `d16807e6` (resolve_hub_path walks cwd for M2+sub). These establish that
  `_mill/` lives at the hub subfolder — the premise of the three-roots model.

## Constraints

- No `CONSTRAINTS.md` at the hub root (checked; absent).
- ASCII-only stdout (`_log`/`print`) — Windows cp1252 (CLAUDE.md).
- Unit tests run via `uv run --project plugins/mill` (or the `run-all.py`
  harness); they use in-memory/tempfile fixtures and **no real git/LLM**. So
  `git_root` in tests is a tempdir path; `resolve_ref_paths`/`resolve_existing_paths`
  must tolerate `git_root=None` (keep the `if git_root is not None` guards).
- Backward compatibility: the `--stage full` path is still used by subprocess /
  psmux dispatch and by manual runs; its envelope shapes (`errors`/`summary` on
  validator failure, `to_dict()` ReviewResult on success) must not change.
- The validator-failure envelope emitted from `--stage prepare` must be
  **byte-identical in shape** to the `--stage full` one so the SKILL's existing
  Step 1.5 JSON parser + fix table work unchanged.

## Testing

- `test-review-common.py` (TDD candidate): add cases for `resolve_ref_paths` and
  `resolve_existing_paths` proving the reordered resolution:
  - cwd == `git_root` layout: `root` set, raw path at `git_root/root/raw` resolves
    (regression for normal mill-plan).
  - cwd == `git_root/root` layout (#471): `project_root` ends with `root`;
    assert the result is `git_root/root/raw` (single prefix), NOT the doubled
    `git_root/root/root/raw`, and that no `ReviewError` is raised.
  - `git_root=None`: falls back to `project_root/root/raw` without crashing.
  - wiki-prefixed paths still route through `wiki_root` (unchanged).
- `test-plan-validate.py` (TDD candidate): add a case where `project_root` is the
  `root:` subfolder and `git_root` is the repo top; assert `_check_non_existent_path`
  and `_check_batch_oversized` find the referenced files (no false
  `non-existent-path` / no spurious oversized miscount) once `git_root` is threaded.
- `test-review-plan-flow.py`: add a `--stage prepare` flow case proving the
  validator runs — feed a plan with a known validator error and assert prepare
  exits 1 with the `errors`/`summary` envelope and writes **no** brief; and a
  clean-plan case asserting prepare writes the brief and prints the prepare
  envelope.
- `test-paths.py`: only if base-resolution helpers are touched; otherwise no new
  cases (the revert is already covered).
- Manual/empirical sanity already done in discussion: `resolve_path` vs
  `resolve_task_path(cwd,...)` agree in the live `hub_rel="."` container — keep
  that as the documented baseline, not a new test.

## Q&A log

- **Q:** Why was the `resolve_path`→worktree-root fix (`b62ca5e7`) reverted, and
  which base is canonical for `_mill/`? **A:** `_mill/` does NOT live at the
  worktree root; it lives at `<worktree_root>/<subfolder>` (the hub), which is
  cwd. The revert is correct; `_mill/` resolves against the hub subfolder.
- **Q:** Canonical fix for #471 path-doubling — git_root or cwd? **A:** Resolve
  source `root:`/raw refs against `git_root` (`git_root/root/raw`), since `root:`
  is repo-relative; make it the primary resolution.
- **Q:** Where should the #465 validator gate live — in `--stage prepare` or as a
  SKILL-instructed orchestrator step? **A:** Operator deferred to recommendation;
  chose running `_plan_validate` inside `--stage prepare` (single source of truth,
  cannot be skipped by orchestrator omission).
- **Q:** Is #466's slug-concatenation still present? **A:** No — already fixed by
  the `resolve_path` rewrite; the residual work is validator base-consistency
  (thread `git_root`+`root` into `_plan_validate.run`), not re-resolving plan_dir.
