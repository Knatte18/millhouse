# Discussion: mill-merge: run the deterministic path as one script

```yaml
task: 'mill-merge: run the deterministic path as one script'
slug: mill-merge-script
status: discussing
parent_branch: main
```

## Problem

`mill-merge` is a 591-line `SKILL.md` (`plugins/mill/skills/mill-merge/SKILL.md`) that the model executes step by step.
Each numbered step is a separate tool-call turn,
and the skill re-derives paths and config in inline `python -c` blocks at nearly every step.
The cost is round-trip latency, not Python start-up (empty interpreter 14 ms, `import _paths` 77 ms on Linux).
Almost every step is deterministic and already backed by a helper module,
so the model adds latency without adding judgment.

Move the deterministic path into one script, `millpy-merge.py`, that runs the whole sequence up to the first point needing judgment or dialogue,
and prints one JSON result.
`SKILL.md` shrinks to: run the script, act on the JSON, handle the callbacks.
This is part of the mill turn-reduction initiative (mechanize deterministic steps into script calls).

## Scope

**In:**

- New `plugins/mill/scripts/millpy-merge.py` (thin CLI) and `plugins/mill/scripts/_merge.py` (step logic, testable).
- Every deterministic step of today's `mill-merge`, including Step 5's squash, rebase-retry, and branch-protection PR fallback (see Decision `step5-in-script`).
- Per-step wall-clock timing in the JSON result.
- Rewrite of `plugins/mill/skills/mill-merge/SKILL.md` to about 100 lines.
- Updating cross-references to old mill-merge step numbers in other files (see Technical context, "Cross-references to update").
- Unit tests in `plugins/mill/unit_tests/test-millpy-merge.py` (and `test-merge.py` if the plan splits them) with in-memory fakes, no real git.
- `SKILLS.md` / skill wrapper regeneration only if the plan's edits make them stale (the `mill-merge` description line stays the same, so likely no change).

**Out:**

- `mill-merge-in` itself. It keeps its checkpoint, conflict sub-agent, verify replay, and report. Scripting it is a separate task.
- `mill-finalize`, `git-pr`, `mill-cleanup` behavior. `mill-finalize` still invokes `/mill-merge` unchanged.
- Changing who confirms a dead-parent successor (stays an operator confirmation, same as today).
- Go/Cobra rewrite.
- New integration tests with real git/gh (see Decision `testing-scope`).
- `_pr_state`, `_parent_branch`, `_archive_tag`, `_status`, `_client` internals, except for small additive helpers the plan finds strictly necessary.

## Decisions

### script-shape

- Decision: `_merge.py` holds one function per step plus a runner that executes the step list in order and stops at the first step returning a stop.
  `millpy-merge.py` parses flags, calls the runner, and prints exactly one JSON object as the last stdout line.
  Progress/diagnostic lines go to stderr, ASCII only.
  Exit code 0 whenever a JSON result was printed (including `halt`);
  non-zero only on an unexpected crash (traceback on stderr, no JSON).
- Rationale: matches `workflow/SKILL.md` anti-pattern rule #2 (transactional script, one call per sequence) and the brief.
  A step-list runner makes step ordering directly unit-testable and gives one place to wrap timing.
- Rejected: one monolithic `main()` (untestable ordering);
  separate scripts per step (reintroduces the turns this task removes).

### json-result-contract

- Decision: the result object has these top-level fields:
  - `status`: `"ok"` | `"halt"` | `"callback"`.
  - `route`: which path ran — `"direct"`, `"pr-merged"`, `"pr-closed"`, `"branch-protection-pr"` (Step 5 fallback created/reused a PR and flipped `[pr-pending]`).
  - `step`: the step name that produced the stop (for `halt`/`callback`), or the last step (for `ok`).
  - `reason`: human-readable ASCII message (for `halt`, the exact operator-facing text today's SKILL.md prints for that halt).
  - `action`: for `callback` only — `"merge-in"` or `"confirm-parent"`.
  - `resume`: the exact argument list (JSON array of strings) the skill appends when re-invoking the script after handling the stop;
    `null` when re-running is not the fix (e.g. `open` PR halt says "close or merge it, then re-run `/mill-merge`", which is a plain re-run: `[]`).
  - `data`: action-specific payload (e.g. `parent_branch`, `outcome`, `candidate`, `hops`, `reason` for confirm-parent; `pr_url` for branch-protection; `slug`, `parent_branch`, `archive_tag`, `archive_action`, `moved_aside_to` for ok).
  - `warnings`: list of ASCII strings (citation-scan hits, archive-tag push failure).
    Notify delivery failures are not surfaced: `_notify.notify` swallows them and logs to stderr by design, and this task does not change `_notify`.
  - `timings`: list of `{"step": str, "wall_s": float, "subproc_s": float}`, one per executed step (see Decision `timing`).
  - `report`: list of ASCII lines the skill prints verbatim to the operator.
- Rationale: one shape covers every exit, so `SKILL.md` needs one parse-and-branch block.
  Putting the operator text in the script keeps the skill short and the wording testable.
- Rejected: distinct JSON shapes per exit (skill must know each);
  exit-code-encoded stops (loses the payload).

### stops-that-remain-with-the-model

- Decision: exactly two callbacks and all halts:
  1. `callback`/`merge-in`: the parent has commits the child lacks (`git log HEAD..<MERGE_REF>` non-empty, using the same `origin/<parent>`-vs-local `MERGE_REF` rule as `mill-merge-in` Step 1).
     `data.parent_branch` carries the resolved parent.
     Skill invokes the `mill-merge-in` skill with `<parent_branch>` as its positional argument, then re-runs the script with `resume` = `["--merged-in"]` (plus `--parent <new>` when merge-in's report carries `Substituted parent branch: <old> -> <new>`).
     If `mill-merge-in` fails, the skill halts and reports; no lock is held at that point (see Decision `lock-timing`), so nothing to release.
     `--parent <branch>` semantics: it overrides the resolved parent branch for this run only, skips the script's own liveness check and `confirm-parent` callback (merge-in already had the operator confirm that branch), and is not persisted by the script (`mill-merge-in` persists it to `status.md` when that file exists).
     The skill must pass `--parent <new>` on every later re-run of the script in the same `/mill-merge` invocation after a substitution, so a re-run never re-resolves the old dead parent.
  2. `callback`/`confirm-parent`: parent liveness check failed and `_parent_branch.resolve_dead_parent` returned `resolved` or `fallback`.
     Skill shows the same operator message today's Entry Step 4 prints (script puts it in `report`), asks with a numbered-options list (1) proceed against `<candidate>` (Recommended), 2) halt), and on confirm re-runs with `resume` = `["--confirm-parent", "<candidate>"]`.
     The script then rebinds `status.md` via `_status.set_parent_branch`, commits `mill-merge: rebind dead parent branch for {slug}`, pushes, and continues.
     `cycle` is a plain `halt`, no callback.
  - Every other stop is `halt` with today's message text.
- Rationale: these are the only two places the brief and today's skill need judgment or dialogue.
- Rejected: script invokes `mill-merge-in`'s clean path itself (duplicates a 256-line skill with verify replay; out of scope).

### step5-in-script

- Decision: Step 5 (dirty-parent check, parent ff-only, squash, task-dir restore, commit, push, non-ff fetch+rebase+single retry, and the branch-protection fallback: `reset --hard origin/<parent>`, `gh pr list --head`, `gh pr create` if none, `git push origin <child>`, `_client.set_phase(..., 'pr-pending')`) all run in the script.
  Branch-protection detection uses today's substring list (`Changes must be made through a pull request`, `repository rule violations`, `protected branch`, `GH006`);
  non-ff detection uses `! [rejected]` plus `(fetch first)` or `(non-fast-forward)`.
  The branch-protection route ends `status: "ok"`, `route: "branch-protection-pr"`, with `data.pr_url`, and skips archive tag and `[done]` exactly as today.
- Rationale: every branch of Step 5 is string-matching plus fixed commands; nothing in it needs judgment.
  The brief allowed a callback only "if it cannot be made deterministic".
- Rejected: branch-protection fallback as a callback (adds a turn for a fixed sequence).

### lock-timing

- Decision: acquire `<parent-path>/.scratch/merge.lock` (three lines: pid, ISO-8601 UTC Z timestamp, child branch) after the merge-in check passes, immediately before Step 5, and never hold it across a stop.
  Release it in a `try/finally` right after Step 5 finishes (success, fallback, halt, or rollback), before archive tag / `[done]`, matching today's "Post-Step-5-success sequencing".
  Stale rule unchanged: timestamp older than 5 min is overwritten.
  The script does not block on a busy lock: when a fresh lock is held by another branch, it returns `halt` with `step: "lock"`, the holder's three lines in `reason`, and `resume: []`.
  The skill handles that halt by waiting and re-running (see Decision `run-budget-and-kill-safety`); the 5-min stale rule bounds how long a dead holder blocks.
  In-place mode: no lock (unchanged).
- Rationale: today's order (lock, then merge-in) would force the lock to survive an LLM callback across process boundaries, needing re-entrant ownership logic and a release path when the skill aborts.
  The lock guards parent-worktree mutations, which all happen in Step 5.
  A parent advancing between merge-in and Step 5 is already handled by the pre-squash ff-only and the push rebase-retry.
  Not blocking in-script keeps one call well inside the Bash tool's timeout.
- Rejected: keep today's order with a re-entrant lock keyed on child branch (more code, stale lock on skill abort);
  a 5-min in-script poll (one call could exceed the Bash tool timeout, and a timeout kill skips `finally`).

### run-budget-and-kill-safety

- Decision:
  - The skill invokes the script with the Bash tool `timeout: 600000` (10 min, the maximum), stated in `SKILL.md`.
    With no in-script lock wait, a run is fetch/squash/push/rebase-retry/wiki plus `gh` calls, far below that.
  - On a `lock` halt, the skill waits for the lock to clear with the `Monitor` tool (poll the lock file every 10 s; emit when it is gone or its timestamp is older than 5 min; give up after 5 min) and re-runs the script once;
    a second `lock` halt is reported to the operator with the holder info (today's post-5-min behavior).
  - The runner installs a `SIGTERM` handler (and treats `KeyboardInterrupt`) that raises an exception, so the `finally` path runs on a Bash-tool timeout kill.
  - The Step 5 `finally` path: if the squash has not been confirmed pushed (see Decision `squash-landed-detection`), roll back with `git -C <parent-path> reset --hard origin/<parent_branch>` (worktree mode;
    in-place mode resets the current branch the same way when it is the parent), then release the lock.
    This runs for any exception between `merge --squash` and a successful push, not only for detected push failures.
    The dirty-parent and ff-only-divergence halts stay exempt (they fire before any mutation).
  - A crash that still produces no JSON (e.g. `SIGKILL`) is documented in `SKILL.md`: the lock goes stale after 5 min, and a half-applied squash surfaces on the next run as the existing dirty-parent halt, whose text already tells the operator how to commit or reset it.
    The skill reports a no-JSON exit with the stderr tail and tells the operator to re-run `/mill-merge`.
- Rationale: a timeout kill must not leave the parent mid-squash with a held lock;
  a signal handler plus `finally` covers the `SIGTERM` case, and the existing dirty-parent halt covers the unrecoverable `SIGKILL` case.
- Rejected: no signal handling (timeout kill skips rollback);
  running the script through `millpy-bg` (adds polling turns, which this task removes).

### squash-landed-detection

- Decision: decide whether the squash already landed from repository state, never from `merge --squash` / `commit` output.
  After the dirty-parent check and parent ff-only, in this order:
  1. **Unpushed local squash:** if `git -C <parent-path> rev-list origin/<parent_branch>..<parent_branch>` contains a commit carrying this task's trailer (below), push it (with the same non-ff rebase-retry and branch-protection handling as a fresh push) and skip `merge --squash`.
     Any other local-only commit on the parent is already covered by the ff-only divergence halt or pushed along with it, same as today's `git push`.
  2. **Already landed:** if `git -C <parent-path> log origin/<parent_branch> --grep '^Mill-Task: <slug>$' --format=%H -n 1` finds a commit, the squash is on origin: skip Step 5 entirely and continue to archive tag.
  3. **Legacy landed (no trailer):** otherwise, if every non-task-dir file the child changed since `git merge-base origin/<parent_branch> <child>` has identical content in `origin/<parent_branch>` and the child's tree (`git diff --quiet origin/<parent_branch> <child> -- <those paths>`), treat as landed.
     Covers squashes made by the old prose skill.
  4. Otherwise run the fresh squash.
  - The squash commit message becomes `<cached_task>` followed by a blank line and the trailer `Mill-Task: <slug>`.
  - In-place mode applies the same checks with the current working tree in place of `<parent-path>`.
- Rationale: a run killed between `commit` and `push` leaves a clean parent ahead of origin that output-based detection mistakes for "nothing to commit" and never pushes;
  a parent that advanced after a landed squash makes a re-squash conflict instead of reporting "landed".
  A trailer is a deterministic marker that survives later parent commits;
  the content check handles pre-trailer history.
- Rejected: output-string idempotency (both failure modes above);
  content check alone (a later edit to the same file on the parent defeats it).

### merged-in-flag

- Decision: `--merged-in` skips the merge-in check on the re-run.
  Without it, a parent that advanced again during `mill-merge-in` would return another `merge-in` callback, potentially looping;
  with it, the late commits are handled by Step 5's ff-only and rebase-retry, same as today.
- Rationale: bounds the callback to one per invocation chain and keeps today's race handling.
- Rejected: capping loops in the skill (more skill prose).

### re-entry-idempotency

- Decision: every step stays idempotent so a plain re-run after any `halt` resumes correctly, relying on existing mechanisms:
  - Phase gate: status.md `phase` if present and slug matches;
    else wiki `pr-pending` / `ready-to-merge` fallback (unchanged).
  - Cleanup commit: skip `git rm` if task dir absent;
    skip commit if nothing staged.
  - Squash: state-based landed detection per Decision `squash-landed-detection` (unpushed local squash is pushed; landed squash skips Step 5).
  - Archive tag: `_archive_tag.create_or_resolve` handles same-SHA / ancestor / divergent.
  - `[done]`: `_client.set_phase` is idempotent.
  - Post-squash failures (archive tag, `[done]`) are never rolled back;
    the `halt` reason says "Merge landed on <parent> but <step> failed: <err>. Re-run /mill-merge to retry".
- Rationale: the brief requires resumable re-entry;
  these steps already behave this way in prose, the script just preserves them.

### cached-task-source

- Decision: resolve `cached_task` / `cached_task_description` once at entry:
  from `status.md` `task:` / `task_description:` when it exists (defaults: slug, then `cached_task`);
  otherwise from the wiki task's `title` for both.
  Drop the `git show HEAD~1:_mill/status.md` recovery path.
- Rationale: in one process the values are cached before Step 4 deletes status.md, so the #987 undefined-variable failure cannot happen.
  `mill-spawn` writes `task:` from the wiki title, so the wiki fallback on re-entry yields the same string.
- Rejected: keep HEAD~1 recovery (dead code in a single-process flow).

### drop-preflight-step

- Decision: remove Step 5.5 (`_preflight.check_helpers(['_archive_tag'])`) and the `_parent_branch:check_liveness` preflight.
  `_merge.py` imports those modules directly at top level.
- Rationale: the preflight guarded inline `python -c` imports against a stale cache;
  the script itself lives in the same cache, so a missing helper fails at script import with a clear `ModuleNotFoundError` before any mutation.

### wiki-writes

- Decision: at most one wiki write per run: `_client.set_phase(wiki_path, slug, 'done')` on the direct / pr-merged / pr-closed routes, or `set_phase(..., 'pr-pending')` on the branch-protection route.
  Reads (`_client.get_task`) are fine.
  Citation scan on the wiki uses `git -C <wiki_path> grep` (read-only).
- Rationale: the brief asks for one wiki commit and push per merge;
  `set_phase` goes through the daemon, which commits and pushes once per call.

### timing

- Decision: the runner wraps each step with `time.monotonic()` for `wall_s`.
  One timing helper in `_merge.py` wraps an arbitrary callable (not only `subprocess.run`) and accumulates its elapsed time into the current step's `subproc_s`;
  every git/gh subprocess call and every `_client` call (which goes through the wiki daemon socket, not a subprocess) runs through it, and so do `_pr_state`, `_archive_tag`, and `_parent_branch` calls that shell out or hit the network.
  The `report` ends with one ASCII line per step: `[mill-merge] <step>: <wall>s (git/net <subproc>s)`, and a total.
  `mill-merge-in`'s verify time is outside the script; the skill already reports it.
- Rationale: answers "script time vs git/network vs verify" for the next slow merge without a profiler.

### skill-md-shape

- Decision: new `SKILL.md` (target ~100 lines) contains: role line and cross-worktree invariants;
  the script invocation in cache form (`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-merge.py" [resume args]`) with Bash `timeout: 600000`;
  a branch table on `status` / `action` / halt `step`;
  the two callback procedures, the `lock` halt wait-and-retry-once procedure, and the rule to keep passing `--parent <new>` after a substitution;
  the no-JSON (hard kill) handling from Decision `run-budget-and-kill-safety`;
  a short statement that rollback and lock release happen inside the script (with the rollback target `origin/<parent_branch>` and the post-squash no-rollback boundary stated once for operators);
  the report/no-self-report note;
  board discipline (lock file path stays `<parent-path>/.scratch/merge.lock`).
  All per-step rationale prose moves into `_merge.py` docstrings/comments where it still applies.
- Rationale: the skill's job becomes dispatch plus the two callbacks.

### routing-preserved

- Decision: the script preserves today's routing exactly:
  - Entry: `_marker.task_data` (MarkerError -> halt with today's text);
    `_inplace.is_inplace`;
    stale-worktree edge via `git worktree list --porcelain` (same self-resolve write/commit/push and inconclusive halt);
    main-worktree-in-worktree-mode halt.
  - Parent branch: status.md absent -> `git.base_branch` (default `main`) plus the notice line in `report`;
    present -> `_parent_branch.resolve(status_path, interactive=False, expected_slug=slug)`;
    `ParentBranchError` -> `set_blocked`, commit, push, halt;
    liveness check only on the status-present branch.
  - Phase gate: raw `slug:` field comparison, then `phase` table (`done`, `pr-pending`, other -> halt);
    wiki fallback when absent or slug mismatch.
  - PR-state gate via `_pr_state.resolve_pr_state(child_branch, git_root)`: `merged` -> Steps 4, 6, 7, 9 (no parent ff);
    `open` -> halt;
    `closed` -> full direct flow;
    `none` with `error` -> halt with the `gh` failure text;
    `none` without error -> `done` continues, `pr-pending` halts.
  - In-place mode: no lock, no merge-in check, Step 5 runs without `-C <parent-path>`, no dirty-parent check, no parent ff.
  - Step 4 citation scan: same two `git grep` pathspecs; hits become `warnings`, never a halt.
  - Rollback on any Step 5 failure before the squash lands: `git -C <parent-path> reset --hard origin/<parent_branch>`;
    dirty-parent and ff-only-divergence halts are exempt (no reset).
    Step 4 partial failure: `git reset --hard HEAD` on the child.
  - Step 9: `_notify.notify("mill-merge.done", ...)` (never raises; delivery failures stay on stderr as today), final report text unchanged.
- Rationale: the task is a mechanical move, not a behavior change;
  preserving routing keeps every past bug fix (#497, #648, #817, #930, #977, #987) intact.

### testing-scope

- Decision: unit tests only, per the brief.
  `_merge.py` takes its external effects through an injectable boundary (a small ops object or module-level functions the tests patch) covering git/gh subprocess calls, `_client`, `_status`, `_pr_state`, `_parent_branch`, `_archive_tag`, `_notify`, and lock-file I/O (lock file in a tempfile dir).
- Rationale: the unit-test convention is in-memory fixtures, no real git/LLM (`plugins/mill/unit_tests/`, e.g. `test-millpy-spawn.py` patches `_spawn_core`).
- Rejected: a real-git integration test (needs `gh` for the PR-state gate; a fake `gh` shim is more scaffolding than this task warrants).

## Technical context

- Current skill: `plugins/mill/skills/mill-merge/SKILL.md` — the authoritative spec for every message string and routing branch the script must preserve.
  Read it in full when planning; the plan should cite its sections per step.
- Helpers to reuse (all in `plugins/mill/scripts/`):
  - `_paths`: `resolve_git_root`, `resolve_wiki_path`, `resolve_container_path`, `resolve_hub_path`, `resolve_active_hub`, `resolve_task_path`.
  - `_config.load_config(hub_root, git_root)`.
  - `_marker.task_data`, `_marker.MarkerError`; `_inplace.is_inplace`.
  - `_status`: `read_full`, `append_phase`, `set_blocked`, `set_parent_branch`.
  - `_parent_branch`: `resolve`, `check_liveness`, `resolve_dead_parent`, `ParentBranchError`.
  - `_pr_state.resolve_pr_state(branch, cwd) -> dict` with `state`, `number`, `error`.
  - `_archive_tag.create_or_resolve(worktree, slug, child_branch) -> dict` with `action`, `tag`, `moved_aside_to`, `push_failed`, `push_error`.
  - `wiki._client`: `get_task`, `set_phase`.
  - `_notify.notify(event, detail, **context)`.
  - `_timestamp.now_utc_iso`; `_subprocess_util` (existing subprocess wrapper — reuse it inside the timing helper rather than calling `subprocess` directly, if it fits).
- Precedent for script shape and tests: `millpy-spawn.py` (thin CLI over `_spawn_core.py`) and `unit_tests/test-millpy-spawn.py`.
- `mill-merge-in` Step 1 no-op check defines `MERGE_REF`: `origin/<parent>` if it exists and local `<parent>` is its ancestor, else local `<parent>`; after `git fetch origin <parent>`.
  The script reuses that rule for the merge-in callback decision.
- Task dir relative pathspec for parent-side commands: `_paths.resolve_task_path(worktree_root, cfg['paths']['status_md']).parent.relative_to(worktree_root).as_posix()` (#648: absolute child path fails with "outside repository").
- Parent worktree path: the `git worktree list --porcelain` entry whose branch is `refs/heads/<parent_branch>`.
- Cross-references to update (grep `mill-merge` / `Step 5` / `Step 4` / `Step 7` to find all):
  - `plugins/mill/skills/mill-merge-in/SKILL.md` (Entry step 3 "Card 1" note, liveness paragraph, caller-propagation note, Step 1 fast-path note) — point at the script's `merge-in` callback / `--parent` resume instead of old step numbers.
  - `plugins/mill/skills/mill-status/SKILL.md` table rows citing "mill-merge Step 5/7".
  - `plugins/mill/skills/mill-go-base/SKILL.md` "mirrors mill-merge's own Step 5 fallback".
  - `CLAUDE.md` hard-constraints bullet citing "`mill-merge` Step 4's cleanup commit".
  - `plugins/mill/integration_tests/test-merge.py` comments at lines 405, 589, 1338 naming "mill-merge Step 4/5" — comment-only edits to name the `_merge.py` step functions instead.
- After merge, the plugin cache is frozen until `./update-plugins.sh`; this task's own merge runs the old skill.

## Constraints

- ASCII only in `print()` / stderr output (Windows cp1252).
- Never `sed` in code, skill text, or sub-agent prompts; no `.wiki` junction path on any command line or passed to a helper — resolve via `_paths`.
- Keep imports lean on the hot path (Windows/Cortex AV overhead); do not add heavy third-party imports.
- Wiki mutations only via `_client`; wiki reads via `git -C <wiki_path>`; never change cwd to the wiki or the parent worktree.
- All parent-branch git operations use `git -C <parent-path>`; never `cd` to the parent.
- Recursive deletions (none expected here) would require `_junction.strip_all_in_worktree` first.
- Plan `verify:` commands start with `PYTHONPATH= ` (Python project).

## Testing

- TDD candidates in `_merge.py`:
  - Runner: step ordering per route (`direct` worktree mode, `direct` in-place, `pr-merged`, `pr-closed`, `branch-protection-pr`); stops end the run; timings recorded for executed steps only.
  - PR-state routing table: `merged`, `open`, `closed`, `none`+error, `none`+`done`, `none`+`pr-pending`.
  - Phase gate: status present/absent, slug match/mismatch/absent field, wiki `pr-pending` / `ready-to-merge` / other / missing task.
  - Parent resolution: status absent -> base_branch notice; `ParentBranchError` -> set_blocked + halt; dead parent `resolved`/`fallback` -> `confirm-parent` callback; `cycle` -> halt; `--confirm-parent` rebinds and continues.
  - Merge-in check: parent ahead -> `merge-in` callback with `resume` `["--merged-in"]`; `--merged-in` skips the check; in-place skips it.
  - Lock: fresh acquire, stale overwrite, busy lock -> immediate `lock` halt with holder info and `resume: []`; released on success, on Step 5 halt, and on exception.
  - Kill safety: an exception (and a simulated `SIGTERM`) raised between `merge --squash` and a successful push triggers `reset --hard origin/<parent_branch>` and lock release; one raised after a confirmed push does not roll back.
  - Squash-landed detection: local squash commit with the trailer unpushed -> pushed, no new squash; trailer commit on `origin/<parent>` (parent advanced since) -> Step 5 skipped, no re-squash; legacy content-identical case -> skipped; none -> fresh squash with the `Mill-Task: <slug>` trailer in the message.
  - `--parent <branch>`: overrides the parent, skips liveness/`confirm-parent`, writes nothing to `status.md`.
  - Step 5 push outcomes: success; non-ff -> rebase -> retry success; rebase conflict -> abort + rollback + halt naming files; retry failure -> rollback + halt; branch-protection -> reset + reuse-or-create PR + push child + `pr-pending`; other failure -> rollback + halt; dirty parent and ff-only divergence halt with no reset.
  - Idempotency: task dir absent skips cleanup commit; nothing staged after the task-dir restore skips the commit.
  - Post-squash failure (archive tag / `set_phase` raising) -> halt without rollback, lock already released.
  - Wiki writes: exactly one `set_phase` call per route.
  - Every string emitted to `report`/`warnings`/`reason` is ASCII.
- CLI (`millpy-merge.py`): import smoke test; flag parsing (`--merged-in`, `--confirm-parent`, `--parent`); exactly one JSON line on stdout; exit 0 on halt, non-zero on crash.
- Run via `run-all.py` / `uv run --project plugins/mill`.

## Q&A log

- **Q:** Should Step 5's branch-protection fallback stay a model callback (as the brief tentatively listed) or move into the script? 1) Script (Recommended) 2) Callback. **A:** [auto-pick] Script. **Why:** every branch is fixed commands plus substring matching; the brief only kept it with the model if it could not be made deterministic.
- **Q:** How does the script hand off to `mill-merge-in`? 1) Script runs the merge-in no-op check and returns a `merge-in` callback only when the parent is ahead; skill runs `mill-merge-in`, re-runs with `--merged-in` (Recommended) 2) Always return a merge-in callback 3) Re-implement merge-in's clean path in the script. **A:** [auto-pick] Option 1. **Why:** the common no-op case costs zero extra turns, and merge-in's verify replay stays in one place.
- **Q:** When is the merge lock acquired? 1) After the merge-in check, just before Step 5, never held across a stop (Recommended) 2) Before merge-in as today, with a re-entrant lock. **A:** [auto-pick] Option 1. **Why:** avoids a lock surviving an LLM callback; Step 5's ff-only and rebase-retry already handle a parent that moves meanwhile.
- **Q:** Keep the `HEAD~1:_mill/status.md` recovery for `cached_task`? 1) Drop it; cache at entry, wiki title on re-entry (Recommended) 2) Keep it. **A:** [auto-pick] Drop. **Why:** single-process caching removes the #987 failure mode.
- **Q:** Keep Step 5.5 cache preflight? 1) Drop; direct imports in `_merge.py` (Recommended) 2) Keep. **A:** [auto-pick] Drop. **Why:** the script lives in the same cache, so a missing helper fails at import before any mutation.
- **Q:** Add a real-git integration test? 1) No, unit tests with fakes only (Recommended) 2) Yes, with a fake `gh` shim. **A:** [auto-pick] No. **Why:** brief scopes unit tests; `gh` shim scaffolding outweighs the gain.
- **Q:** (review r1) How does the script handle a busy merge lock? 1) Halt immediately with `step: "lock"`; skill waits via Monitor and re-runs once (Recommended) 2) Poll in-script up to 5 min with a 600000 ms Bash timeout. **A:** [auto-pick] Option 1. **Why:** keeps each call short and kill-safe; the wait moves to a tool built for it.
- **Q:** (review r1) How does a re-run know the squash already landed? 1) `Mill-Task: <slug>` trailer on the squash commit, content check for legacy squashes, push any unpushed trailer commit (Recommended) 2) Content check only. **A:** [auto-pick] Option 1. **Why:** a trailer survives later parent edits to the same files.
- **Q:** Dead-parent confirmation under autonomous runs? 1) Keep operator confirmation as a callback, unchanged (Recommended) 2) Auto-accept. **A:** [auto-pick] Keep. **Why:** behavior change is out of scope; the brief lists it as staying with the model.
