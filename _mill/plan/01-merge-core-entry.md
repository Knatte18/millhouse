# Batch: merge-core-entry

```yaml
task: 'mill-merge: run the deterministic path as one script'
batch: merge-core-entry
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-merge.py
depends-on: []
```

## Batch Scope

Creates `plugins/mill/scripts/_merge.py` with the framework (result contract, `Stop`, `Ops`, timing, runner, signal handling) and the four entry-side steps that decide whether and how a merge runs: `entry`, `parent`, `phase-gate`, `pr-state`, plus the `merge-in-check` callback step.
Creates `plugins/mill/unit_tests/test-merge.py` covering them.
Batch 2 consumes `Ctx`, `Stop`, `Ops`, `_ascii`, `_git_ok`, `_parse_worktrees`, and the `STEPS` list, appending the squash-side steps.

Batch-local decisions:

- **Stale-worktree edge trigger.** The old skill's stale-worktree edge exists for the ambiguity "branch matches cwd AND `<worktrees-dir>/<slug>/` exists".
  `step_entry` evaluates the edge only when the directory `ops.resolve_worktrees_dir(cfg, git_root) / slug` exists on disk;
  when it does not exist, the edge is skipped and `mode` stays as `is_inplace` returned.
  Without this guard every in-place run (no worktree directory at all) would take the "entry absent" branch and write a spurious `self-resolved-stale-worktree` timeline row.
- **Missing parent worktree.** The old skill never said what happens when no `git worktree list --porcelain` entry carries `branch refs/heads/<parent_branch>` in worktree mode.
  The runner halts with a named message (batch 2, `step_squash`) rather than guessing a path.

## Cards

### Card 1: _merge.py framework: result contract, Ops boundary, timing, runner

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_inplace.py`
  - `plugins/mill/scripts/_parent_branch.py`
  - `plugins/mill/scripts/_pr_state.py`
  - `plugins/mill/scripts/_archive_tag.py`
  - `plugins/mill/scripts/_notify.py`
  - `plugins/mill/scripts/_timestamp.py`
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/unit_tests/test-inplace.py`
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_merge.py`
  - `plugins/mill/unit_tests/test-merge.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Create `plugins/mill/scripts/_merge.py` with a module docstring stating it implements the deterministic path of the `mill-merge` skill, called by `millpy-merge.py`.
  Top-level imports (no lazy imports, no `_preflight`): stdlib (`dataclasses`, `datetime`, `os`, `signal`, `threading`, `time`, `pathlib.Path`), and `_archive_tag`, `_config`, `_inplace`, `_marker`, `_notify`, `_parent_branch`, `_paths`, `_pr_state`, `_status`, `_subprocess_util`, `_timestamp`, `from wiki import _client`.
  No `cwd=` keyword argument whose value names the wiki path may appear anywhere (test-guards `subprocess-cwd-wiki` pattern);
  wiki git reads use `["git", "-C", str(wiki_path), ...]`.

  Define:

  1. `_ascii(text: str) -> str` per the overview's `ascii-output` Decision.
  2. `class Terminated(BaseException)` — raised by the SIGTERM handler.
  3. `class Stop(Exception)` with constructor `Stop(status: str, reason: str, *, action: str | None = None, resume: list[str] | None = None, data: dict | None = None, report: list[str] | None = None, step: str | None = None)`.
     A non-`None` `step` overrides the executing step's name in the result's `step` field (batch 2 uses it for the `lock` halt).
     `status` is `"halt"`, `"callback"`, or `"ok"`.
     Module helpers `halt(reason, *, resume=[], data=None, step=None) -> Stop` and `callback(action, reason, *, resume, data, report) -> Stop` build instances (callers `raise` them).
     A `halt` with `resume=None` means "re-running is not the fix";
     `resume=[]` means "fix the cause, then plain re-run".
  4. `@dataclass class MergeOptions`: `merged_in: bool = False`, `confirm_parent: str | None = None`, `parent: str | None = None`.
  5. `@dataclass class Ctx` holding run state, all fields defaulting to `None`/empty: `opts`, `git_root`, `wiki_path`, `container_path`, `cfg`, `slug`, `active_branch`, `mode` (`"worktree"`/`"inplace"`), `worktree_root`, `status_path`, `task_dir`, `task_dir_rel` (relative to `worktree_root`, posix, for parent-side pathspecs), `task_dir_git_rel` (relative to `git_root`, posix, for child-side pathspecs), `parent_branch`, `phase`, `cached_task`, `cached_task_description`, `child_branch`, `route`, `parent_path`, `archive` (dict), plus `warnings: list[str]`, `report: list[str]`, `timings: list[dict]`.
  6. `class Ops` — the real effect boundary.
     Attribute `subproc_s: float = 0.0`.
     Method `_timed(self, fn, *args, **kwargs)` calls `fn`, adds `time.monotonic()` elapsed to `self.subproc_s` in a `finally`, returns the result.
     Timed methods (each a one-line `return self._timed(<helper>, ...)`):
     `run(argv: list[str], cwd: Path | None = None)` -> `_subprocess_util.run(argv, cwd=cwd, quiet_nonzero=True)`;
     `task_data(git_root, wiki_path, cfg)` -> `_marker.task_data`;
     `check_liveness(branch, git_root)`, `resolve_dead_parent(branch, git_root, cfg)` -> `_parent_branch`;
     `pr_state(branch, cwd)` -> `_pr_state.resolve_pr_state`;
     `get_task(wiki_path, slug)`, `set_phase(wiki_path, slug, phase)` -> `_client`;
     `archive_tag(worktree, slug, child_branch)` -> `_archive_tag.create_or_resolve`.
     Untimed methods: `resolve_git_root()`, `resolve_wiki_path(git_root)`, `resolve_container_path(git_root)`, `resolve_hub_path()`, `load_config(hub_root, git_root)` (-> `_config.load_config`), `resolve_active_hub(container_path, slug, cfg, git_root)` (-> `_paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)`), `resolve_worktrees_dir(cfg, git_root)`, `is_inplace(slug, git_root, cfg)`, `resolve_parent(status_path, slug)` (-> `_parent_branch.resolve(status_path, interactive=False, expected_slug=slug)`), `notify(event, detail, **context)`, `now() -> datetime` (UTC-aware), `now_iso() -> str` (-> `_timestamp.now_utc_iso()`), `pid() -> int`.
  7. `_git_ok(ctx, ops, argv, *, cwd=None, what: str) -> CompletedProcess` — runs `ops.run(argv, cwd)`;
     on non-zero exit raises `halt(f"{what} failed: {<last non-empty stderr/stdout line>}")` with `resume=[]`.
  8. `_commit_status(ctx, ops, message)` — `git -C <git_root> add <status_path>`, `git -C <git_root> commit -m <message>`, `git -C <git_root> push`, each through `_git_ok`.
  9. `_parse_worktrees(porcelain: str) -> list[dict]` — splits `git worktree list --porcelain` output on blank lines into dicts with keys `path` (Path), `branch` (the `refs/heads/...` value or `None`), `detached` (bool), `prunable` (bool).
     The first entry is the main worktree.
  10. `STEPS: list[tuple[str, Callable[[Ctx, Ops], None], Callable[[Ctx], bool]]]` — ordered `(name, fn, applies)` triples.
      This card registers nothing;
      cards 2-3 and batch 2 append their steps in order.
  11. `_install_sigterm() -> object` installs a SIGTERM handler that raises `Terminated`, only when `threading.current_thread() is threading.main_thread()`, and returns the previous handler (or `None` when not installed);
      `_restore_sigterm(prev)` restores it.
  12. `run_merge(opts: MergeOptions, ops: Ops | None = None) -> dict` — the runner.
      Builds `Ctx(opts=opts)`;
      installs the SIGTERM handler;
      for each `(name, fn, applies)` in `STEPS`: skip (no timing entry) when `applies(ctx)` is false;
      else set `ops.subproc_s = 0.0`, record `time.monotonic()`, call `fn(ctx, ops)` inside `try/finally` that appends `{"step": name, "wall_s": round(wall, 3), "subproc_s": round(ops.subproc_s, 3)}` to `ctx.timings` (so a stopping step is also timed).
      A raised `Stop` ends the loop and becomes the result;
      completing every step yields `status: "ok"` with `step` = the last executed step name.
      Restores the SIGTERM handler in an outer `finally`.
  13. `_result(ctx, stop: Stop | None, step: str) -> dict` — builds the JSON-able dict with exactly the keys `status`, `route`, `step`, `reason`, `action`, `resume`, `data`, `warnings`, `timings`, `report` (discussion Decision `json-result-contract`).
      `report` = `ctx.report` lines, then the stop's own `report` lines (for a halt with no explicit report, the reason), then one line per timing entry `[mill-merge] <step>: <wall_s:.2f>s (git/net <subproc_s:.2f>s)`, then `[mill-merge] total: <sum:.2f>s`.
      Every string in `reason`, `report`, `warnings` goes through `_ascii`.

  Create `plugins/mill/unit_tests/test-merge.py` in the plain-function style of `plugins/mill/unit_tests/test-inplace.py`: insert `plugins/mill/scripts` on `sys.path`, `import _merge`, define `test_*` functions, and a `main()` that runs every test, prints `PASS`/`FAIL` lines, and returns non-zero on any failure (same harness shape as the tail of `plugins/mill/unit_tests/test-millpy-spawn.py`).
  Add a `FakeOps(_merge.Ops)` helper class in the test file: constructor takes keyword overrides for the untimed/timed methods' return values and a list of `(tokens, CompletedProcess-or-callable)` git rules;
  `run` records `argv` into `self.calls`, returns the first rule whose tokens are all present in `argv` (a callable rule is invoked with `argv`, so it can raise), defaulting to returncode 0 with empty output.
  Also record `set_phase`/`notify`/`archive_tag` calls.
  Tests for this card: `_ascii` mapping;
  `_parse_worktrees` on a three-entry porcelain sample (main, branch entry, detached entry);
  runner with a temporary `STEPS` list (patch `_merge.STEPS` for the test) — skipped steps get no timing entry, a step raising `halt(...)` ends the run with its name in `step` and later steps not called, a step raising a plain `RuntimeError` propagates, `ok` result carries the last step name;
  `_result` report ends with the per-step timing lines and the total line;
  `Ops._timed` accumulates elapsed time into `subproc_s`;
  `_install_sigterm` handler raises `Terminated` when invoked directly and `_restore_sigterm` restores the previous handler.
- **Commit:** `feat(mill-merge): add _merge.py framework (result contract, Ops, runner)`

### Card 2: entry and parent steps

- **Context:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_parent_branch.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_marker.py`
- **Edits:**
  - `plugins/mill/scripts/_merge.py`
  - `plugins/mill/unit_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `step_entry(ctx, ops)` and `step_parent(ctx, ops)` to `_merge.py` and append `("entry", step_entry, always)` and `("parent", step_parent, always)` to `STEPS` (`always = lambda ctx: True`).
  The old `plugins/mill/skills/mill-merge/SKILL.md` `## Entry` steps 1, 1.5, and 4 are the spec;
  copy every operator-facing string from there (ASCII-converted).
  Each step function carries a docstring holding the rationale prose that applies (e.g. #817 liveness, #977, why the raw `slug:` read), replacing the SKILL.md paragraphs.

  `step_entry`:
  - `git_root = ops.resolve_git_root()`, `wiki_path = ops.resolve_wiki_path(git_root)`, `container_path = ops.resolve_container_path(git_root)`, `cfg = ops.load_config(ops.resolve_hub_path(), git_root)`.
  - `active = ops.task_data(git_root, wiki_path, cfg)`;
    on `_marker.MarkerError` raise `halt(<old Entry step 1 "no registered task branch" text>, resume=None)`.
    Bind `ctx.slug`, `ctx.active_branch = active["branch"]`, `ctx.mode = "inplace" if ops.is_inplace(slug, git_root, cfg) else "worktree"`.
  - `wt = _parse_worktrees(_git_ok(... ["git", "-C", git_root, "worktree", "list", "--porcelain"], what="git worktree list").stdout)`.
  - Derive `ctx.worktree_root = ops.resolve_active_hub(container_path, slug, cfg, git_root)`, `ctx.status_path = _paths.resolve_task_path(ctx.worktree_root, cfg["paths"]["status_md"])`, `ctx.task_dir = ctx.status_path.parent`, `ctx.task_dir_rel = ctx.task_dir.relative_to(ctx.worktree_root).as_posix()`, `ctx.task_dir_git_rel = ctx.task_dir.relative_to(git_root).as_posix()`.
  - Stale-worktree edge, only when `(ops.resolve_worktrees_dir(cfg, git_root) / slug).is_dir()` (batch-local decision above): find the `wt` entry whose `path` resolves to that directory.
    Present with `branch == f"refs/heads/{ctx.active_branch}"` and not `prunable`: no action.
    Absent, or present with a different non-`None` branch, or `prunable`: set `ctx.mode = "inplace"`;
    when `ctx.status_path.exists()`, capture `original_phase = _status.read_full(status_path)["yaml"].get("phase")`, call `_status.append_phase(status_path, f"self-resolved-stale-worktree-{mode}", ops.now_iso())` then `_status.append_phase(status_path, original_phase, ops.now_iso())`, and `_commit_status(ctx, ops, f"mill-merge: self-resolved stale-worktree ambiguity ({mode})")`.
    Present but detached (`branch is None`, not prunable): inconclusive — raise `halt` with the old skill's inconclusive text (branch matches cwd AND `<worktree_path>` exists, porcelain inconclusive, stopping rather than guessing), `resume=None`.
  - If `ctx.mode == "worktree"` and `wt[0]["path"]` resolves to `git_root`: raise `halt` with the old "mill-merge from the main worktree requires in-place mode" text naming `slug` and `ctx.active_branch`, `resume=None`.

  `step_parent`:
  - `opts.parent` set: `ctx.parent_branch = opts.parent`;
    no status read, no liveness check, no status write (discussion Decision `stops-that-remain-with-the-model`, `--parent` semantics).
  - Else when `not ctx.status_path.exists()`: `ctx.parent_branch = cfg.get("git", {}).get("base_branch", "main")` and append the old "status.md absent; assuming parent branch is `<base_branch>` ..." notice to `ctx.report`;
    no liveness check.
  - Else: `ctx.parent_branch = ops.resolve_parent(status_path, slug)`;
    on `_parent_branch.ParentBranchError`: `_status.set_blocked(status_path, f"missing parent_branch: row for {slug}", timestamp=ops.now_iso())`, `_commit_status(ctx, ops, f"mill-merge: blocked (missing parent_branch: row) for {slug}")`, raise `halt` with the old `BLOCKED: status.md is missing the parent_branch: row ...` text (`resume=[]`).
    Then when `not ops.check_liveness(parent, git_root)`:
    - `opts.confirm_parent` set: `_status.set_parent_branch(status_path, opts.confirm_parent)`, `_commit_status(ctx, ops, f"mill-merge: rebind dead parent branch for {slug}")`, `ctx.parent_branch = opts.confirm_parent`, append a report line `Rebound dead parent branch <old> -> <new>.`.
    - Else `r = ops.resolve_dead_parent(parent, git_root, cfg)`;
      `outcome == "cycle"`: raise `halt(<old cycle text with hops joined by ' -> '>, resume=None)`;
      `resolved` / `fallback`: raise `callback("confirm-parent", <old resolved/fallback text>, resume=["--confirm-parent", r["branch"]], data={"parent_branch": parent, "outcome": r["outcome"], "candidate": r["branch"], "hops": r["hops"], "reason": r.get("reason")}, report=[<same text>])`.

  Tests in `test-merge.py` (status.md files in a temp dir, written via `_status.render_initial` or a literal fenced-yaml fixture; `FakeOps` for everything else): MarkerError halt with `resume` null;
  in-place mode with no worktree dir skips the stale edge (no timeline row, no git commit calls);
  stale edge with entry absent writes both timeline rows, restores `phase:`, commits, sets mode `inplace`;
  detached entry halts;
  main-worktree halt in worktree mode;
  status absent -> base_branch and notice line;
  `ParentBranchError` -> `blocked_reason` set, commit calls recorded, halt;
  dead parent `resolved` and `fallback` -> `confirm-parent` callback with `resume == ["--confirm-parent", candidate]`;
  `cycle` -> halt with `resume` null;
  `--confirm-parent X` with dead parent -> `parent_branch: X` in status.md, commit recorded, run continues;
  `--parent X` -> `parent_branch == X`, `check_liveness` never called, status.md bytes unchanged.
- **Commit:** `feat(mill-merge): entry and parent-resolution steps in _merge.py`

### Card 3: phase gate, PR-state gate, and merge-in check

- **Context:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_pr_state.py`
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:**
  - `plugins/mill/scripts/_merge.py`
  - `plugins/mill/unit_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `step_phase_gate`, `step_pr_state`, `step_merge_in_check` to `_merge.py` and append, in this order after `parent`: `("phase-gate", step_phase_gate, always)`, `("pr-state", step_pr_state, always)`, `("merge-in-check", step_merge_in_check, lambda c: c.route in ("direct", "pr-closed") and c.mode == "worktree" and not c.opts.merged_in)`.
  The old `plugins/mill/skills/mill-merge/SKILL.md` `## Entry` step 5 and `### PR-state gate` are the spec for every branch and string.

  `step_phase_gate`:
  - When `status_path.exists()`: read `yaml = _status.read_full(status_path)["yaml"]` inside `try/except Exception` (parse failure -> treat as unusable, fall through to the wiki branch).
    Raw `yaml.get("slug")` is compared to `ctx.slug` only when not `None`;
    a mismatch falls through to the wiki branch with `mismatch = True`.
    Otherwise `ctx.phase = yaml.get("phase")`, `ctx.cached_task = yaml.get("task") or slug`, `ctx.cached_task_description = yaml.get("task_description") or ctx.cached_task`.
  - Wiki branch: `task = ops.get_task(wiki_path, slug)`;
    `None` -> `halt("_mill/status.md absent and slug '<slug>' not found in wiki; cannot determine merge state.", resume=None)`;
    `task["status"] == "pr-pending"` -> `ctx.phase = "pr-pending"`;
    `"ready-to-merge"` -> `ctx.phase = "done"`;
    other -> halt with the old "does not show pr-pending or ready-to-merge" text, appending the `(status.md slug did not match task slug '<slug>')` parenthetical only when `mismatch`, `resume=None`.
    Cache `ctx.cached_task = ctx.cached_task_description = task["title"]` (discussion Decision `cached-task-source`;
    no `HEAD~1` recovery).
  - `ctx.phase` not in (`"done"`, `"pr-pending"`) -> halt with the old "status.md phase is `<value>`; mill-merge expects `done`..." text, `resume=None`.

  `step_pr_state`:
  - `ctx.child_branch = _git_ok(ops.run ["git", "-C", git_root, "branch", "--show-current"]).stdout.strip()`;
    empty -> `halt("Detached HEAD in <git_root>; mill-merge needs the task branch checked out.", resume=None)`.
  - `pr = ops.pr_state(ctx.child_branch, git_root)`, then route: `merged` -> `ctx.route = "pr-merged"`;
    `open` -> halt with the old `PR #<number> is still open -- close or merge it on GitHub, then re-run /mill-merge.` text (`resume=[]`);
    `closed` -> `ctx.route = "pr-closed"`;
    `none` with `pr.get("error")` -> halt with the old "Could not determine PR state for branch ..." text (`resume=[]`);
    `none` without error: `phase == "done"` -> `ctx.route = "direct"`, `phase == "pr-pending"` -> halt "status.md says pr-pending but no PR on this branch; inspect manually." (`resume=None`).
    The docstring carries the `merged`-route "local parent is intentionally not fast-forwarded" note and the `closed`-route branch-protection caution.

  `step_merge_in_check` (mirrors `plugins/mill/skills/mill-merge-in/SKILL.md` `### 1. No-op check`, run against the child `git_root`):
  `git -C <git_root> fetch origin <parent>` (result ignored);
  `MERGE_REF = f"origin/{parent}"` when `rev-parse --verify --quiet refs/remotes/origin/<parent>` exits 0 AND `merge-base --is-ancestor <parent> origin/<parent>` exits 0, else `parent`;
  `git -C <git_root> log HEAD..<MERGE_REF> --oneline`;
  non-empty stdout -> raise `callback("merge-in", f"Parent branch {parent} has commits this branch lacks; run mill-merge-in first.", resume=["--merged-in"], data={"parent_branch": parent, "merge_ref": MERGE_REF}, report=[<reason>])`.
  Empty -> continue.

  Tests: status present+slug match (`done`, `pr-pending`, `complete` -> halt);
  status slug mismatch -> wiki fallback with parenthetical on the failure halt;
  status absent + wiki `pr-pending` / `ready-to-merge` / `active` / `None`;
  cached task from status (`task:` present, absent -> slug) and from wiki title;
  PR-state table: `merged` -> `pr-merged`, `open` -> halt naming the number, `closed` -> `pr-closed`, `none`+error -> halt with error text, `none`+`done` -> `direct`, `none`+`pr-pending` -> halt;
  merge-in: parent ahead -> `merge-in` callback with `resume == ["--merged-in"]` and `data.parent_branch`;
  up to date -> continue;
  `opts.merged_in` -> step not executed (no timing entry, no `log` call);
  in-place mode -> step not executed;
  `pr-merged` route -> step not executed.
- **Commit:** `feat(mill-merge): phase gate, PR-state gate, merge-in check in _merge.py`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-merge.py`, the new test file for `_merge.py` created in card 1 and extended by cards 2-3.
No real git, gh, or wiki daemon: `FakeOps` scripts every external call, and status.md fixtures live in temp dirs.
