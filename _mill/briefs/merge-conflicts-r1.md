# Conflict Resolution Brief

Your sole job is to resolve git conflict markers in the listed files, stage each resolved file, and report success. Do NOT commit. Do NOT run `git merge --continue` — the SKILL does that after receiving `{"status":"success"}`.

## Task intent

These excerpts describe what THIS branch is trying to accomplish. When the merge introduces a parent-side change that conflicts with this branch's intent, the resolution preserves THIS branch's intent. In particular: if a file appears under a batch's `Deletes:` list and the merge introduces a modified version of that file from the parent, the resolution is to delete the file (your branch's intent overrides). Stage the deletion with `git -C /home/knatte/Code/millhouse/wts/mill-go-dispatch-path-gaps rm <file>`.

### From discussion.md

# Discussion: mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps

```yaml
task: mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps
slug: mill-go-dispatch-path-gaps
status: discussing
parent: hanf/linux-port-more
```

## Problem

Seven independently-filed GitHub issues (#672, #680, #665, #683, #693, #691, #675) all trace back to four bugs in mill's dispatch and path-resolution layer. Operators and autonomous sessions repeatedly hit multi-minute hangs or silent misrouting when running `millpy-implement.py`, the review-prepare CLIs, or `mill-go`'s Resume path — several of these were filed as separate incidents before the shared root cause was identified. Fixing them now, together, closes all seven issues and removes a source of confusing, hard-to-diagnose stalls in day-to-day mill usage.

## Scope

**In:**
- `millpy-implement.py`: add a fail-fast guard so a `full`-stage run (default or explicit) under `dispatch: agent` config errors immediately instead of hanging to the implementer timeout (#672).
- Review CLI slug/title resolution (`find_active_slug`, `load_task_title` in `_review_common.py`): make each function try on-disk resolution (`status.md` / `*.active` markers) internally before falling through to the wiki daemon round-trip, so every call site — including `_review_plan.py`'s `run()`, which calls `load_task_title` independently of `prepare()` — gets the fast path uniformly (#665, #683, #693, #691).
- `project_root`/`hub_dir` binding: fix all 8 affected call sites found in the current code (6 files) by rebinding `project_root`/`hub_dir` itself (not just `briefs_dir`) at its point of definition, replacing `resolve_hub_path()`'s main-worktree-escaping fallback (or raw `Path.cwd()`) with `_paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root, skip_slug_validation=True)` — the new `skip_slug_validation` parameter avoids reintroducing a daemon round-trip for callers that already hold a validated `slug` (#675).
- `mill-go` Resume, `state=running`: for the subprocess/psmux dispatch path only, change the bare `millpy-implement.py <batch_name>` re-invocation to `millpy-implement.py <batch_name> --resume-incomplete`, which preserves the original `start_sha`/`implementer_session` instead of minting fresh ones. Agent-mode Resume already preserves `start_sha` correctly via the existing `_prepare_reuse_entry` branch and needs no change (#680).

**Out:**
- No change to the wiki daemon's retry/backoff constants or its single-threaded accept-loop architecture — the fix removes the *need* for most callers to hit the daemon at all in the common case, rather than making the daemon itself faster or concurrent.
- No change to `millpy-implement.py`'s `implementer_timeout` value or overall stage model (`prepare`/`full`/`finalize`) — only a guard on which stage is reachable under which dispatch mode.
- No redesign of mill-go's batch/DAG execution model or its `state` machine beyond the `running`-resume fix described above.
- No change to how `resolve_hub_path()` itself walks for `.millhouse/config.local.yaml` — call sites are redirected to a different, already-existing resolver (`resolve_active_hub`) rather than changing `resolve_hub_path`'s own fallback behavior, since other callers may depend on the current fallback intentionally.
- `#691`'s "stale lock" hypothesis is not investigated further — exploration confirmed the actual cause is daemon round-trip latency, not a lock; no lock-related code changes are in scope.

## Decisions

### Fail-fast guard for full-stage under agent-mode dispatch

- Decision: In `millpy-implement.py`, after config load and before stage dispatch, add a guard: if the resolved `--stage` is `"full"` (whether defaulted or passed explicitly) and `_agent_dispatch.resolve_dispatch_mode(cfg) == "agent"`, exit immediately with a clear error directing the caller to use `--stage prepare` + `--stage finalize` instead.
- Rationale: `full` stage runs the implementer synchronously in-process with up to a 1800s timeout — a shape that is fundamentally incompatible with agent-mode dispatch, which expects async prepare/finalize. Failing fast surfaces the misconfiguration in seconds instead of after a Bash-tool timeout (or worse, the full 30-minute implementer timeout).
- Rejected: Guarding only bare/omitted `--stage` invocations — an explicit `--stage full` under agent-mode config is just as broken, since `full` stage's synchronous shape doesn't change based on how the caller invoked it.

### On-disk-first slug/title resolution

- Decision: `find_active_slug` and `load_task_title` are each modified **internally** to try on-disk resolution first (`status.md` YAML frontmatter / `*.active` markers under `_mill/`) and only fall through to the wiki daemon's `_dispatch()` retry loop if the on-disk read fails or is ambiguous (e.g. multiple active markers). The fix lives inside the two shared functions themselves, not in caller-side threading — this matters because `load_task_title` has more call sites than any single caller-side threading fix can reliably cover (see the correction below).
- Rationale: `millpy-implement.py` already reads `task_title` straight from `status.md` with zero daemon calls — this is proven, existing precedent. The daemon round-trip costs up to ~134s per call (4×30s + backoff). This is the confirmed single root cause behind #665, #683, #693, and #691 — #691's "stale lock" theory was a misdiagnosis of the same latency.
- Rejected: Shortening the daemon's retry/backoff constants (treats the symptom, not the cause — still pays a real round-trip on every call). Caching daemon responses (adds staleness/invalidation complexity for a problem the on-disk fast path already solves cleanly, since `status.md`/`*.active` are the same source of truth the daemon itself derives from).
- **Correction (discussion-review round 2 GAP, supersedes round 1's threading approach):** Round 1's fix ("thread the resolved title from `main()` into `prepare()`") does not cover every call site. `_review_code.py`'s `run()` and `_review_discussion.py`'s `run()` both call `prepare()` internally, so caller-side threading into `prepare()` would have reached them — but `_review_plan.py`'s `run()` (line 609, the code path for `--stage full`, which is `millpy-review-plan.py`'s CLI default) does **not** call `prepare()`: it duplicates plan-loading logic and calls `load_task_title(project_root, wiki_root, cfg, slug)` directly at line 692, a second, independent call after `main()`'s `find_active_slug` (`millpy-review-plan.py:131`). A `prepare()`-only threading fix would leave subprocess/psmux-mode plan review paying the un-merged double round-trip the fix is meant to eliminate. Making `find_active_slug`/`load_task_title` on-disk-first **internally** (this Decision's actual text, above) sidesteps the problem entirely: every call site — `prepare()`, `_review_plan.py run()`, or any future caller — gets the fast path automatically, with no per-caller threading to get right or miss. The "merge into one call to guarantee a single round-trip" idea from round 1 is dropped as unnecessary complexity: once each function is on-disk-first, the daemon-fallback case (where a real double round-trip could still occur) is rare enough that caller-side merging isn't worth the API change.

### project_root/hub_dir binding fixed at definition site (not a briefs_dir-only patch)

- Decision: Fix all 8 affected call sites currently found in the code (not the 5 the original brief estimated): `millpy-review-code.py:161`, `millpy-review-plan.py:169`, `millpy-fix.py:637`, `millpy-implement.py:618`, `millpy-merge-in-subagent.py:347/393/428`, `millpy-review-discussion.py:117`. **Corrected scope (discussion-review round 2 GAP):** the bug is not specific to `briefs_dir` — in each file, `project_root`/`hub_dir` is bound *once*, at definition (e.g. `millpy-implement.py:229`: `project_root = _paths.resolve_hub_path()`), then reused for `status_path`, `plan_base`, cleanliness-snapshot paths, git subprocess `cwd=`, the `PROJECT_ROOT` template token, and `briefs_dir` alike. Every one of these breaks identically whenever `resolve_hub_path()`'s cwd-walk fails and falls back to the main worktree (or, in `millpy-merge-in-subagent.py`'s case, raw `Path.cwd()` with no `.millhouse` walk at all). The fix therefore **rebinds `project_root`/`hub_dir` itself at its point of definition** in each of the 6 files — not a parallel, `briefs_dir`-only binding — so every downstream consumer is corrected together.
- Replacement resolver (avoiding a reintroduced daemon round-trip — **also a discussion-review round 2 GAP**): `_paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)` as originally proposed calls `resolve_active_worktree`, which unconditionally calls `_marker.slug_from_branch` (`_paths.py:399`) to check in-place mode — even when the caller already holds a validated `slug` — hitting the same `_dispatch()` daemon retry path (worst case ~134s) the "On-disk-first slug/title resolution" Decision removes, on every `--stage prepare` call in the hot per-batch dispatch path. `resolve_active_worktree`'s exception handling (`except (MarkerError, SystemExit)`, `_paths.py:400`) also doesn't catch `WikiBusyError`/`WikiStartupError`, so a busy/cold daemon can crash resolution uncaught. Fix: add an opt-in `skip_slug_validation: bool = False` parameter to `resolve_active_worktree`, threaded through `resolve_active_hub`. When `True`, skip the `_marker.slug_from_branch` daemon call and determine in-place mode with a cheap, git-only check instead — `_inplace.is_inplace(slug, git_root, cfg) and _pygit2_util.current_branch(git_root) == cfg.get("spawn", {}).get("branch_prefix", "") + slug` — the same branch-derivation `slug_from_branch` performs, minus its Home.md daemon validation, which is redundant once the caller already trusts `slug`. All 6 files pass `skip_slug_validation=True`. Existing callers of `resolve_active_hub`/`resolve_active_worktree` (`millpy-abandon.py:53`, `_review_common.py:374`) keep the default `False`, unaffected.
- Groundwork required (none of the 6 files have this today): **(a)** none compute a `container_path` binding — each needs a new `container_path = _paths.resolve_container_path(git_root)` call before the `resolve_active_hub` call. **(b)** `millpy-merge-in-subagent.py` specifically has no `slug` variable in scope at its 3 call sites (347/393/428) — it calls `_marker.slug_from_branch(git_root, wiki_path, cfg)` at line 264 but discards the return value; the fix must capture it (`slug = _marker.slug_from_branch(git_root, wiki_path, cfg)`). The other 5 files already resolve `slug` in scope by the time `project_root`/`hub_dir` is bound.
- Rationale: A fresh code read at discussion time found more affected sites than the filing brief described. Trusting the current code over a stale count avoids leaving 3 known-bad sites unfixed. Escaping to the main worktree causes briefs written by agent-mode `--stage prepare` to land where the dispatched Agent can't find them — a symptom easily mistaken for the #672 hang. Rebinding at definition (not a `briefs_dir`-only patch) is required because every other consumer of `project_root`/`hub_dir` shares the identical escaping-fallback bug — a narrower patch would leave `status_path`, `plan_base`, snapshot paths, git `cwd=`, and the `PROJECT_ROOT` template token silently broken in the exact scenario this task fixes. The `skip_slug_validation` fast path is required because reusing `resolve_active_hub` unmodified would silently reintroduce the exact daemon dependency the on-disk-first Decision removes, on the hottest call path in the system.
- Rejected: Fixing only the 5 sites the brief named. A `briefs_dir`-only parallel binding, leaving `status_path`/`plan_base`/`PROJECT_ROOT`/git-`cwd` unfixed. Using `resolve_active_hub` unmodified and accepting the reintroduced daemon dependency plus adding `WikiBusyError`/`WikiStartupError` handling at each site — treats a symptom while leaving the actual regression (undoing the on-disk-first fix) in place.

### mill-go Resume (subprocess/psmux only): preserve start_sha via --resume-incomplete

- Decision: Scope corrected after re-verifying against current source (discussion-review round 1 flagged the original framing as factually wrong). `mill-go/SKILL.md`'s **agent-mode** Resume path (`Resume` section, `state=running`, line 514) already re-runs the standard Agent-mode dispatch pattern (`--stage prepare` → Agent → `--stage finalize`), and `millpy-implement.py`'s existing `_prepare_reuse_entry` branch (lines 439-450) already reuses the original `start_sha`/`implementer_session` from `status.md` whenever `--stage prepare` targets a batch already in `running` state. Agent-mode Resume does not discard partial-commit evidence today — there was nothing to fix there. The actual bug is scoped to the **subprocess/psmux** dispatch path only (`SKILL.md` lines 520-524): its Resume `running`-case bare-invokes `millpy-implement.py <batch_name>` with no `--stage` flag (defaults to `full`), which always takes the "Normal (first-pass) dispatch" branch (`millpy-implement.py:495-516`) and mints a fresh `start_sha`/`session_id`, discarding any partial-commit evidence. Fix: change that one invocation to `millpy-implement.py <batch_name> --resume-incomplete` — an already-existing CLI flag that reads the original `start_sha`/`implementer_session` from `status.md` and skips the cleanliness snapshot + `mill-go: start batch` housekeeping commit, reusing the same recovery plumbing the `incomplete`-classification path already relies on.
- Rationale: The original decision assumed agent-mode Resume performed a hardcoded bare/full-stage call — it doesn't; that shape only exists on the subprocess/psmux path. An existing flag (`--resume-incomplete`) already provides exactly the preserve-start_sha behavior needed, so the fix is a one-line invocation change in `SKILL.md`'s Resume section, not new partial-commit-detection logic or dispatch-mode routing.
- Rejected: Building new partial-commit detection (`git rev-list --count`) and dispatch-mode routing logic into Resume — unnecessary; `--resume-incomplete` already does this. Logging partial commits for audit only, or blocking resume for operator decision — both are moot once the existing flag is used correctly, since the accounting problem goes away entirely.

### No #672/#680 interdependency (correction, discussion-review round 1)

- Decision: There is no interdependency between the #672 guard and the #680 fix. #672's fail-fast guard fires when the resolved `--stage` is `full` **and** `dispatch == agent`. #680's fix only changes the subprocess/psmux Resume invocation, which never runs under `dispatch == agent` — agent-mode Resume uses `--stage prepare` (`SKILL.md` line 514) and never reaches `--stage full`. The guard added for #672 can therefore never fire on a Resume-issued call, on either dispatch mode. The two fixes are independent and can be implemented, tested, and landed in any order or batch grouping the plan finds convenient.
- Rationale: The original "must land together" constraint was based on an inaccurate premise (see previous Decision) formed before `mill-go/SKILL.md`'s current Resume section text was directly consulted; re-reading lines 508-525 disproves the claimed hazard.
- Rejected: Retaining the original "single interdependent unit" sequencing constraint — no longer applicable; it would add unneeded coupling to the plan's batch DAG for a hazard that doesn't exist.

## Technical context

- **Dispatch mode resolution:** `_agent_dispatch.resolve_dispatch_mode(cfg)` is the existing, single source of truth for agent vs. subprocess/psmux dispatch mode — used elsewhere in `mill-go`/`mill-start`/`mill-plan`'s Agent-mode dispatch pattern (see `mill-go/SKILL.md` "## Agent-mode dispatch"). Both the new `millpy-implement.py` guard and the Resume fix should call this helper rather than reading `cfg["llm"]["claude"]["dispatch"]` directly, for consistency with existing call sites.
- **Existing on-disk precedent:** `millpy-implement.py:270-271` already reads `task_title` from `status.md`'s YAML frontmatter (`full["yaml"].get("task", slug)`) with zero daemon calls — the on-disk-first fix for `find_active_slug`/`load_task_title` should follow this same pattern, not invent a new one.
- **`load_task_title`'s misleading parameter name (discussion-review round 3 NOTE):** `_review_common.py:329`'s first parameter is named `git_root`, but every call site (`_review_plan.py:359/692`, `_review_code.py:361`, `_review_discussion.py:108`) actually passes the already hub-resolved `project_root`, not a raw git checkout root. The new on-disk fast path must read `status.md` relative to the value actually passed in (hub-resolved), not assume it's a raw git root — this matters for M2+sub configs where hub and git checkout root diverge. No functional change is implied by this, just plan-writer awareness of the existing (misleading) parameter name when locating where to add the on-disk read.
- **Wiki daemon retry shape:** confirmed at `wiki/_client.py:160-189` — 4 attempts, `backoff_sleeps = [2,4,8]`, `_CONNECT_TIMEOUT_SECONDS=5.0`, `_READ_TIMEOUT_SECONDS=30.0` (`_client.py:53-54`). Worst case ≈134s per round-trip. This code is not being changed; callers are being routed around it in the common case.
- **`find_active_slug`'s existing on-disk fallback:** `_review_common.py:312-317` already has an on-disk fallback (`_mill/*.active` glob), but today it only fires *after* `slug_from_branch` has already burned the full daemon-retry budget and raised `MarkerError`. The fix reorders this — try on-disk first, daemon second — rather than adding a new mechanism.
- **`resolve_hub_path` fallback:** `_paths.py:155-221` walks cwd upward for `.millhouse/config.local.yaml`; on failure, falls through to `return main_root` (line 219) — the main worktree. This function itself is not being changed (other callers may rely on its current fallback intentionally); the 6 affected files' `project_root`/`hub_dir` binding is redirected to `resolve_active_hub` (with `skip_slug_validation=True`, see below) instead, since they already have (or will have) `slug` in scope and don't need cwd-based discovery.
- **`resolve_active_worktree`'s daemon call and the `skip_slug_validation` fast path:** `_paths.py:374-419`. Its in-place-mode check unconditionally calls `_marker.slug_from_branch(git_root, wiki_path, cfg)` (line 399), which itself unconditionally calls `_list_tasks_brief_with_retry` (`_marker.py:81`) — the same daemon retry path the on-disk-first Decision removes. The new `skip_slug_validation` parameter bypasses this by checking `_inplace.is_inplace(...)` plus a direct branch-string comparison instead (no daemon call). Existing callers `millpy-abandon.py:53` and `_review_common.py:374` are unaffected since the new parameter defaults to `False`.
- **Completeness/commit-count machinery:** `millpy-implement.py:644-650` already computes `commits_made` via `git rev-list --count <start_sha>..HEAD` for the normal (first-pass) dispatch path, and `finalize_from_output` uses a card-count recount for completeness classification. The Resume fix reuses this existing machinery rather than building new accounting.
- **Cross-cutting interactions to keep in mind while planning:**
  - Every Resume re-dispatch also calls `_marker.slug_from_branch` (via `millpy-implement.py:256`), so it currently pays the cluster-2 daemon tax on top of an already-interrupted run — the on-disk-first fix benefits Resume too, though it isn't strictly required for #680's own fix to be correct.
  - `millpy-implement.py:618`'s `briefs_dir` bug (cluster 3) affects agent-mode `--stage prepare` specifically — a mis-resolved `project_root` writes the brief to the wrong worktree, producing a symptom easily mistaken for the #672 hang. Fixing cluster 3 removes a confound when verifying cluster 1's fix.

## Constraints

No `CONSTRAINTS.md` present at the hub root.

## Testing

- **`millpy-implement.py` fail-fast guard:** unit test with a mocked/stubbed `_agent_dispatch.resolve_dispatch_mode` returning `"agent"`, asserting the process exits promptly (non-zero, clear stderr message) for both a bare invocation and an explicit `--stage full` invocation, without reaching the synchronous implementer-run code path. TDD candidate — write the failing test first, the guard is a small, well-isolated change.
- **On-disk-first slug/title resolution:** unit tests with tempfile-based `status.md`/`*.active` fixtures (no real daemon, no real git) asserting: (a) `find_active_slug` and `load_task_title` each succeed from disk alone when a valid marker/status file is present, with zero daemon calls (mock the daemon client and assert it's never invoked); (b) each falls through to the (mocked) daemon path when the on-disk data is missing, corrupt, or ambiguous (multiple `*.active` markers); (c) `_review_plan.py`'s `run()` (the `--stage full` / subprocess-mode path, distinct from `prepare()`) also hits the on-disk fast path for its independent `load_task_title` call at line 692, not just `prepare()`'s call.
- **`project_root`/`hub_dir` binding + `skip_slug_validation`:** unit tests using tmp git-worktree fixtures (tempfile-created, not real shared git state) for each of the 6 affected files, asserting **all** downstream consumers of the rebound `project_root`/`hub_dir` — not just `briefs_dir` — land under the local task worktree, not a simulated "main worktree" sibling: `status_path`, `plan_base`, snapshot paths, git subprocess `cwd=`, the `PROJECT_ROOT` template token, and `briefs_dir` itself. Cover both the `resolve_hub_path`-fallback cases and `millpy-merge-in-subagent.py`'s raw-cwd case. Separately, unit test `resolve_active_worktree`'s new `skip_slug_validation=True` path in isolation: assert it never calls the (mocked) daemon client, correctly distinguishes in-place vs. worktree mode via the git-only check, and that `skip_slug_validation=False` (the default, used by `millpy-abandon.py`/`_review_common.py`) is behaviorally unchanged.
- **`mill-go` Resume, `state=running`:** unit test simulating a `status.md` with a recorded `start_sha` and a tempfile git repo with commits ahead of it (partial progress), asserting Resume preserves the original `start_sha` rather than re-capturing HEAD, and dispatches via the mocked `resolve_dispatch_mode` path (assert the agent-mode envelope path is taken when config says `agent`, and that the previous hardcoded bare/full-stage call is no longer reachable). A second case with zero commits ahead of `start_sha` should confirm the reset-to-fresh path is unaffected when there truly is no partial progress.
- All of the above follow the existing `unit_tests/` convention (in-memory/tempfile fixtures, no real git/LLM/daemon) rather than `integration_tests/` — these are ordering/routing/guard bugs, not behavior requiring a real daemon or real Claude session to validate.

## Q&A log

- **Q:** The filing brief says 5 remaining `briefs_dir` call sites through `resolve_hub_path`'s escaping fallback; a fresh code read found 8 across 6 files, including one (`millpy-merge-in-subagent.py`) using raw `Path.cwd()` with no `.millhouse` walk at all. Fix all 8, or only the 5 the brief named? **A:** [auto-pick] Fix all 8 sites found in the current code, trusting the fresh read over the brief's stale count. **Why:** the brief predates this exploration pass; leaving 3 known-bad sites unfixed (one of them worse than the others) defeats the purpose of the task. **Correction (discussion-review round 1 GAP):** the original decision assumed `container_path`/`slug` were already in scope at all 8 sites — false for `container_path` everywhere and for `slug` in `millpy-merge-in-subagent.py`; the Decision section now spells out the required new bindings.
- **Q:** Should `millpy-implement.py`'s new fail-fast guard fire only for a bare (`--stage` omitted) invocation, or for any resolved `--stage full` under agent-mode config? **A:** [auto-pick] Fire whenever the resolved stage is `full`, regardless of whether it was defaulted or passed explicitly. **Why:** `full` stage's synchronous, long-timeout shape is incompatible with agent-mode dispatch no matter how the caller reached it — restricting the guard to only the bare case would leave an identical hang reachable via `--stage full` explicitly.
- **Q:** For the daemon-round-trip fix (#665/#683/#693/#691), reorder to try on-disk resolution first only, or also merge `find_active_slug`+`load_task_title` to avoid the double round-trip? **A:** [auto-pick] Do both — reorder to on-disk-first, and merge the two functions' resolution so at most one daemon round-trip is paid when the on-disk path fails. **Why:** exploration confirmed `prepare()` currently calls both functions and each independently triggers its own `slug_from_branch` call, so reordering alone still leaves a 2x tax in the fallback case. **Correction (discussion-review round 2 GAP):** `_review_plan.py`'s `run()` (the `--stage full` path) calls `load_task_title` independently of `prepare()`, so a `prepare()`-only threading fix misses it. The fix now makes both functions on-disk-first internally (see the "On-disk-first slug/title resolution" Decision) rather than merging via caller-side threading — this covers every call site, including `run()`, uniformly; the caller-side "merge" idea is dropped.
- **Q (discussion-review round 2 GAP):** `resolve_active_hub` (proposed for the `project_root`/`briefs_dir` fix) internally calls `resolve_active_worktree`, which unconditionally calls `_marker.slug_from_branch` — reintroducing the exact daemon round-trip the on-disk-first fix removes, on every `--stage prepare` call. Accept the reintroduced dependency (with added `WikiBusyError`/`WikiStartupError` handling), or add a fast path that trusts an already-validated `slug`? **A:** [auto-pick] Add a `skip_slug_validation=True` fast path to `resolve_active_worktree`/`resolve_active_hub` that checks in-place mode via a cheap git-only comparison instead of calling the daemon. **Why:** the 8 (now: 6-file) call sites already hold a validated `slug` by the time they resolve `project_root` — re-validating it via a full daemon round-trip is pure waste, and would silently undermine the on-disk-first fix's whole purpose on the hottest dispatch path in the system.
- **Q (discussion-review round 2 GAP):** Does the `project_root`/`hub_dir` fix rebind the variable at its point of definition (fixing every downstream use: `status_path`, `plan_base`, git `cwd=`, `PROJECT_ROOT` template token, `briefs_dir`) or add a parallel binding scoped to `briefs_dir` only? **A:** [auto-pick] Rebind at definition. **Why:** every other consumer of `project_root`/`hub_dir` shares the identical escaping-fallback bug — a `briefs_dir`-only patch would leave the others silently broken in the exact scenario this task is fixing.
- **Q:** For `mill-go` Resume's `state=running` handling, should partial-commit evidence just be logged, should resume be blocked for operator decision, or should `start_sha` be preserved? **A:** [auto-pick] Preserve `start_sha`. **Why:** logging alone doesn't fix the accounting gap; blocking adds friction for what is normally a safe redo once the accounting is correct. **Corrected during discussion-review round 1:** the fix scope narrowed to the subprocess/psmux Resume path only, via the existing `--resume-incomplete` flag — agent-mode Resume already preserves `start_sha` today through `millpy-implement.py`'s existing `_prepare_reuse_entry` branch, no fix was needed there.
- **Q (superseded, discussion-review round 1):** Given that #672's fail-fast guard would make mill-go Resume hard-fail under agent-mode config unless #680 also fixes Resume's dispatch routing, should these two land as one interdependent unit or ship independently? **A:** This premise was factually wrong — re-reading `mill-go/SKILL.md`'s Resume section (lines 508-525) directly showed agent-mode Resume already uses `--stage prepare` and never reaches `--stage full`, so #672's guard (agent-mode + full-stage only) never fires on a Resume call. **No interdependency exists; #672 and #680 are independent fixes**, see the "No #672/#680 interdependency" Decision above.
- **Q:** If the on-disk fast path for slug/title resolution finds missing, corrupt, or ambiguous data, should it fall back to the existing (slow) daemon path, or fail fast? **A:** [auto-pick] Fall back to the daemon path. **Why:** the fast path is a best-effort optimization for the common case, not a correctness boundary — falling through preserves today's correctness guarantees exactly, only skipping the slow path when the answer is unambiguous.
- **Q:** What testing tier fits these fixes — unit tests with mocked daemon/subprocess and tempfile fixtures, or integration tests with real git/psmux? **A:** [auto-pick] Unit tests, matching the existing `unit_tests/` convention. **Why:** these are ordering/guard/routing bugs, not behavior that requires a real daemon, real git remote, or real Claude session to validate — tempfile-created git worktrees are sufficient for the path-resolution assertions.


### From _mill/plan/00-overview.md


```yaml
task: "mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps"
slug: mill-go-dispatch-path-gaps
approved: true
started: "20260725-134500"
parent: hanf/linux-port-more
root: ""
verify: null
```

### From _mill/plan/01-fail-fast-guard.md


```yaml
task: "mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps"
batch: fail-fast-guard
number: 1
cards: 2
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-implement.py"
depends-on: []
```



- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/02-on-disk-first-resolution.md


```yaml
task: "mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps"
batch: on-disk-first-resolution
number: 2
cards: 3
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-marker.py test-review-plan-flow.py"
depends-on: []
```



- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/03-paths-skip-slug-validation.md


```yaml
task: "mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps"
batch: paths-skip-slug-validation
number: 3
cards: 3
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-paths.py test-paths-sanitize.py test-review-common.py"
depends-on: [2]
```



- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/04-project-root-rebinding-implement-side.md


```yaml
task: "mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps"
batch: project-root-rebinding-implement-side
number: 4
cards: 4
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py test-millpy-fix.py test-millpy-merge-in-subagent.py test-merge-in-subagent.py test-paths.py"
depends-on: [1, 3]
```



- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-fix.py`
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
  - `plugins/mill/unit_tests/test-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/05-project-root-rebinding-review-side.md


```yaml
task: "mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps"
batch: project-root-rebinding-review-side
number: 5
cards: 4
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-code-flow.py test-review-plan-flow.py test-review-plan-finalize-round.py test-review-discussion-flow.py test-paths.py"
depends-on: [3]
```



- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
  - `plugins/mill/unit_tests/test-review-plan-finalize-round.py`
  - `plugins/mill/unit_tests/test-review-cli.py`
  - `plugins/mill/unit_tests/test-review-cli-error-envelope.py`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/06-mill-go-resume-fix.md


```yaml
task: "mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps"
batch: mill-go-resume-fix
number: 6
cards: 1
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-implement.py"
depends-on: []
```



- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none

## Conflicting files

- `plugins/mill/unit_tests/test-review-plan-flow.py`

## Instructions

For each file listed above:

1. Read the file and locate every conflict block (`<<<<<<<`, `=======`, `>>>>>>>`).
2. Understand both sides of the conflict — what each branch intended.
3. Write a resolution that preserves the intent of both sides. When both sides modify **different, non-overlapping parts** of the same conflict region — for example, different columns of one table row, different keys of one object, or disjoint lines of a prose block — **combine both edits** into a single resolved structure. Do NOT pick one side wholesale just because the region overlaps syntactically; picking one side wholesale is correct only when the two changes are genuinely mutually exclusive (e.g. the same key is renamed to two different values). Worked example: if `ours` changes column A and `theirs` changes column B of the same table row, the resolution keeps both column changes in a single row — it does not discard either.
4. Run `git -C /home/knatte/Code/millhouse/wts/mill-go-dispatch-path-gaps add <file>` to stage the resolved file.
5. For modify/delete (DU) conflicts: if Task intent above lists this file under a batch's `Deletes:`, run `git -C /home/knatte/Code/millhouse/wts/mill-go-dispatch-path-gaps rm <file>` instead of editing; that stages the intentional deletion.
6. For UD conflicts — files this branch **modified** that the parent branch **deleted**: do not silently keep the modification. Instead:
   a. Run `git log --diff-filter=D --oneline MERGE_HEAD -- <file>` to find the deletion commit on the parent.
   b. Run `git show <deletion-commit>` to inspect context.
   c. If the deletion commit message mentions a replacement file (e.g. "replaced by", "moved to", "consolidated into"), or the commit also adds a file in the same directory with overlapping content: stage the deletion — `git -C /home/knatte/Code/millhouse/wts/mill-go-dispatch-path-gaps rm <file>`.
   d. If detection is inconclusive: report `{"status":"stuck","stuck_type":"logic","reason":"modify/delete conflict on <file>: cannot determine if parent deletion is a replacement -- operator must decide"}` and halt. Do NOT silently keep the modification.

Never use `git checkout --ours` or `git checkout --theirs` — they silently discard one side of the conflict.

## Report

Your last output line MUST be a bare JSON object (no code fence, no backticks):

On success (nothing discarded):

{"status":"success"}

On success with discarded content — if you had to drop content from one side (e.g. two sides made mutually exclusive changes and only one could survive), list each dropped item:

{"status":"success","discarded":["<short description of what was dropped from which side>"]}

An empty or absent `discarded` field means nothing was lost. If anything was discarded, you MUST list it; an empty list when content was actually dropped is a protocol violation. The `mill-merge-in` frontend reads this field and surfaces any losses to the operator before continuing, rather than silently running `git merge --continue`.

If you cannot resolve one or more conflicts:

{"status":"stuck","stuck_type":"logic","reason":"<one-line description of what you could not resolve>"}

Anything other than this JSON object on the last line is a protocol violation; the merge-in dispatcher treats that as stuck_type: logic with reason "no structured report" — your work is lost. Do not wrap the JSON in a code fence; do not add commentary after it.

## Tools

Available: Read, Edit, Write, Bash, Grep, Glob. Use `git -C /home/knatte/Code/millhouse/wts/mill-go-dispatch-path-gaps` for any git commands; do not `cd`. Worktree cwd is `/home/knatte/Code/millhouse/wts/mill-go-dispatch-path-gaps`.
