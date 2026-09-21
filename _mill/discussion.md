# Discussion: Misc infra/wiki/PR/self-hosting reliability bugs

```yaml
task: Misc infra/wiki/PR/self-hosting reliability bugs
slug: mill-infra-reliability-misc-r2
status: discussing
parent: main
```

## Problem

Ten independent reliability bugs were filed against mill's own infrastructure (wiki daemon, PR-state
resolution, baseline pre-flight, review-duration recording, the handoff skill, dotnet build hygiene, a
cwd-corrupting cross-reference pattern, and a self-hosting cache-freshness gap) while running real
tasks against other repos and against millhouse itself. Each was closed on GitHub and folded into this
one backlog task (source issues: #1107, #1106, #1105, #1103, #1102, #1097, #1095, #1094, #1092,
#1077). None share a root cause; they are grouped only because they are all small, self-contained
infra fixes discovered incidentally during other work. This discussion covers all ten; each gets its
own Decision below.

This was run in `--auto` mode with no live operator (autonomous mill-start invocation). Every
subsection states its own reasoning inline rather than deferring to a Q&A log, since there was no
operator exchange to log — see Q&A log at the end for the one process note that applies.

## Scope

**In:**
- #1107 — wiki `_client.health_check` / `_ensure_daemon` post-spawn readiness race.
- #1106 — `millpy-merge-in-subagent.py --recompute-baseline` TypeError on a mapping-form `verify:` field.
- #1105 — `_pr_state.resolve_pr_state` missing `--repo` and silent failure-to-`none` coercion.
- #1103 — wiki `commit_push` rebase-conflict message and pre-render pull error visibility.
- #1102 — per-batch eager baseline pre-flight cost (lazy computation, not the "halt on red parent" primary option — see Decision).
- #1097 — `millpy-review-plan.py`/discussion/code finalize `--duration-s` has no derivation or cross-check.
- #1095 — `handoff` skill lacks an explicit ban on session-changelog content.
- #1094 — `csharp-build` skill's documented `dotnet build`/`dotnet test` commands lack node-reuse control.
- #1092 — `mill-plan`/`mill-start` SKILL.md cross-references to `mill-go-base/SKILL.md` invite a cwd-corrupting `cd`.
- #1077 — self-hosting plugin-cache-freshness gap at mill-go/mill-merge entry (documentation fix; the underlying pathspec bug itself is already fixed in this dev tree via commit `ace7dbbf`).

**Out:**
- #1102's "Primary" proposal (drop the parent-branch-red accommodation entirely and halt the task) is
  explicitly NOT adopted here — see that Decision for why. A future task can revisit it.
- No new automated cache-freshness *check* is added for #1077 — this task documents the existing
  `update-plugins.sh` recovery instead of building a diffing mechanism (see that Decision).
- No changes to `_verify_baseline.py`'s module-wide (single-command) baseline computation — only the
  per-batch computation's eagerness changes for #1102.
- No broader sweep for other `sed`-adjacent or cwd-corrupting cross-references beyond the two files
  #1092 names.

## Decisions

### wiki-health-check-post-spawn-race (#1107)

- Decision: In `wiki/_client.py`'s `_ensure_daemon`, replace the post-spawn wait loop's
  `wait_for_socket_reachable(...)` check with an actual `OP_HEALTH` probe (same request shape the
  function already uses for the pre-spawn "is an existing daemon still alive" check:
  `{FIELD_OP: OP_HEALTH, FIELD_TOKEN: state["token"], "payload": {"liveness_only": True}}`, sent via
  `_connect_send_recv`). Keep polling (short sleep, same `deadline`) until the probe returns
  `ok: True`, or raise `WikiStartupError("daemon did not start within timeout")` as today if the
  deadline elapses.
  - Root cause confirmed by reading the code: `wait_for_socket_reachable` only proves the OS-level
    listen socket accepts a TCP connection. It does not prove the daemon's request-handling path is
    ready to answer with `ok: True` — a connection can be accepted into the backlog before the
    server has finished its own startup work. `_dispatch`'s caller-level retry loop only retries on
    `ConnectionRefusedError`/`TimeoutError`/`ConnectionResetError` — a clean-but-unready `ok: False`
    response is not one of those, so it propagates straight through as a false negative.
  - This fixes the race at its single source (`_ensure_daemon`), benefiting every op that dispatches
    right after a fresh spawn, not just `health_check()` specifically.
- Rationale: matches the issue's own reproduction (`health_check` immediately re-run seconds later
  succeeds with no other action) — the daemon *does* become ready almost immediately; the bug is
  purely in what "started" means to the waiter.
- Rejected: adding a retry loop inside `health_check()` itself only patches the one call site that
  happened to be observed failing; the same race is latent in every other op's first post-spawn call.

### merge-in-recompute-baseline-verify-field (#1106)

- Decision: In `millpy-merge-in-subagent.py`'s `_run_recompute_baseline`, stop reading
  `overview_frontmatter.get("verify")` directly. Route it through `_plan_dag.parse_verify_field
  (overview_frontmatter, project_root, git_root)` exactly like every other consumer
  (`millpy-implement.py`, `millpy-fix.py`, `_plan_dag.iter_batch_verifies`, `_plan_validate.py`) —
  `parse_verify_field`'s own docstring already lists "merge-in" among the sites required to route
  through it. Thread the returned `cwd` into `_verify_baseline.compute_baseline(...,
  cwd_override_relative=cwd)`, matching `compute_baseline`'s existing parameter for this exact
  purpose. Wrap the `parse_verify_field` call in the same try/except this function already uses
  around `_parent_branch.resolve` and `compute_baseline` (`parse_verify_field` raises `ValueError` on
  a malformed mapping) so the function's documented "never raises, always emits a JSON status line"
  contract holds.
  - Root cause confirmed by reading the code: when a plan's `verify:` is the newer
    `{cwd: hub|git_root, command: ...}` mapping form (used by nested-hub-layout plans), the raw dict
    flows into `compute_baseline`'s `module_wide_verify_cmd: str` parameter and on into
    `_run_verify_in`, which does something string/path-like with it — producing exactly `expected
    str, bytes or os.PathLike object, not dict`. Every other read site in the codebase already
    normalizes this field via `parse_verify_field`; `_run_recompute_baseline` is the one holdout.
- Rationale: this is the single normalizer function that exists precisely to prevent this class of
  bug; the fix is bringing the one non-conforming call site in line with the rest of the codebase,
  not inventing new handling.
- Rejected: coercing the dict to `str(verify)` or similar — would silently run the wrong (or a
  garbage) command instead of the intended one in nested-layout repos.

### pr-state-repo-flag-and-error-visibility (#1105)

- Decision:
  1. In `_pr_state.resolve_pr_state`, resolve the target repo via the existing `_gh_issues.detect_repo
     (Path(cwd))` helper (already used elsewhere in the codebase for the same "parse `git remote
     get-url origin`" job) and pass it as `--repo <owner/repo>` to the `gh pr list` call whenever
     detection succeeds. When `detect_repo` returns `""` (can't parse the remote), omit `--repo` and
     preserve today's cwd-auto-detection behavior unchanged — this keeps the fix safe for
     non-github.com remotes.
  2. Add an `"error"` key to the returned dict (default `None`). Populate it with the captured stderr
     (or exception message) only for the genuine "the gh call itself failed" branches (subprocess
     exception, non-zero exit code, JSON parse failure) — never for "the call succeeded and legitimately
     found zero/no matching PRs," which stays `error: None`.
  3. In `mill-merge/SKILL.md`'s `### PR-state gate`, `none` route: check `error` before falling back
     to phase-based behavior. If `error` is non-null, halt immediately with a distinct message (e.g.
     `"gh pr list failed to resolve PR state for branch <branch>: <error> -- this is a gh/environment
     failure, not evidence of no PR; investigate gh auth/repo-detection, then re-run /mill-merge."`)
     instead of routing into the misleading "no PR on this branch" phase-based fallback. Only proceed
     with the existing phase-based `none` behavior when `error` is `None`.
  4. In `millpy-cleanup.py`'s `_apply_pr_reap_record`, when `state == "none"` and `error` is present,
     include it in the existing stderr log line (this call site's own next sweep already retries
     naturally, so no behavior change beyond a better log message).
  - Root cause confirmed by reading the code: `resolve_pr_state` never passes `--repo`, relying on
    `gh`'s cwd-based auto-detection, which the issue reproduces failing in a nested hub-worktree
    layout; and it collapses every failure mode (including a genuine `gh` error) into the same
    `state: "none"` used for "no PR found," with no way for a caller to tell them apart.
- Rationale: reuses an existing, already-battle-tested repo-detection helper instead of introducing a
  second implementation of `git remote get-url origin` parsing; separating "no PR" from "gh call
  failed" is the direct fix for the misleading halt message the issue reports.
- Rejected: making every `gh` failure a hard halt at `resolve_pr_state` itself — `millpy-cleanup.py`'s
  sweeper needs to keep retrying transient failures silently rather than halting a background sweep;
  the `error` field lets each caller decide.

### wiki-stale-clone-recovery-visibility (#1103)

- Decision: two narrowly-scoped visibility fixes, not a new auto-recovery mechanism (see Rejected):
  1. In `wiki/_sync.py`'s `commit_push`, when the final rebase-retry path raises
     `WikiPushError(f"git pull --rebase failed: ...")`, extend the message to name the recovery path
     that is already known to work: mention that `millpy-wiki-shutdown.py` releases the daemon's own
     `tasks.json` file handle, which is a precondition for any manual `git reset --hard` recovery on
     Windows (the issue's own incident confirms `_client.shutdown(wiki_path)` followed by `git reset
     --hard` succeeded cleanly). Today's message gives no hint that the daemon itself is a file
     holder, which is exactly what cost the investigation time in the incident.
  2. In `wiki/_server.py`'s `_render_and_commit_all`, the pre-render `pull()` call currently does
     `except WikiPushError: pass` — fully silent. Change this to log the caught error to stderr
     (ASCII-only, per CLAUDE.md's `_log()` convention) before continuing, so a persistently-failing
     fast-forward (a sign of leftover unpushed local state from an earlier failed operation — exactly
     the precursor to the staleness this issue describes) is visible in the daemon's own log instead
     of vanishing. The function's flow (render/commit proceeds regardless) is unchanged; only the
     silence is fixed.
  - Root cause confirmed by reading the code: `_render_and_commit_all` already does the "auto-pull
    with the store closed" gap-1 fix the issue asks for (`self._store.close()` / `pull(...)` /
    `self._store.reload()` runs before every render, specifically to dodge the Windows file-lock
    issue) — that part of the mechanism already exists. What's missing is (a) the pre-render pull's
    own failures are swallowed with no trace, and (b) the actual manual-recovery step that worked in
    the incident (`millpy-wiki-shutdown.py`) isn't referenced from the error a caller actually sees.
- Rationale: the daemon already does the right thing operationally (close-pull-reload,
  close-commit_push-reload); the gap is diagnosability, not mechanism. A human or script hitting the
  rebase-conflict error today has no way to discover the shutdown-first recovery without independently
  rediscovering it, as the incident shows.
- Rejected: building an automatic "detect staleness, shut the daemon down, hard-reset, restart"
  recovery into `commit_push` itself. The local-only commit that fails to rebase IS the just-attempted
  mutation; auto-discarding it via a hard reset would silently lose that write rather than recover
  it. Automatic recovery here trades a loud, diagnosable failure for a silent data-loss risk — not a
  net improvement over pointing the operator at the already-working manual recovery.

### baseline-preflight-lazy-not-eager (#1102)

- Decision: adopt the issue's own **first fallback** ("make it lazy"), not its **primary** proposal
  ("drop the accommodation, halt on red parent"). Scope:
  - Stop eagerly computing every batch's `verify_baseline_failures` before batch 1 dispatches
    (`mill-go-base/SKILL.md`'s "0.5 Baseline pre-flight" speculative-launch path, "0.55 Done-gate
    baseline pre-flight", and "0.6 Per-batch baseline recapture" — all three currently drive
    `_verify_baseline.compute_batch_baselines` across the whole plan's batch set up front).
  - At task start, pin the parent branch's tip SHA once (a new `baseline_parent_sha:` field in
    status.md's top yaml block, following the existing `get_module_verify_baseline` /
    `set_module_verify_baseline` / `clear_module_verify_baseline` accessor pattern in `_status.py`)
    so a later on-demand computation still snapshots the exact commit the task actually started
    against, regardless of how far the parent has moved by the time a batch's verify fails.
  - When a batch's own verify gate fails and that batch has no cached `verify_baseline_failures` yet,
    compute it then — on demand, checking out `baseline_parent_sha` (reusing
    `_checkout_parent_branch`/`_link_dependency_dirs`/`compute_batch_baselines`'s existing machinery
    for a single command) — cache the result in status.md, and apply the existing waiver logic
    unchanged from there.
  - The module-wide (single-command, dependency-manifest) baseline computation is untouched — it is
    not what the issue's cost complaint targets ("the plan's *complete verify command set*"), and
    `#590`'s "before any implementer touches dependency manifests" ordering constraint still applies
    to it specifically.
  - The flaky-test case the issue itself calls out as the one legitimate use of the mechanism
    (`verify_baseline_failures` absorbing non-deterministic pre-existing failures) is unaffected: the
    waiver still applies once computed, just computed later.
- Rationale: the issue's Primary proposal is the architecturally cleaner end state, but it is a full
  reversal of the `#590` decision, touching `mill-go-base/SKILL.md` sections 0.5/0.55/0.6, the
  done-gate, and `millpy-fix.py`'s union-baseline consumption — a change of that size, made as one
  batch inside a ten-item reliability grab-bag, is disproportionate and risks destabilizing machinery
  that three just-landed commits (`a3af2f99`, `9d38e1f4`, `273bcc0e`) specifically hardened (dedup,
  timing, hang-bounding) in direct response to this same mechanism's earlier problems (#1098, #1101).
  The lazy fallback delivers the issue's actual stated cost complaint — 100%-of-tasks eager cost
  before batch 1, "an answer that should be 'no, of course not' every single time" — while keeping the
  waiver semantics and existing plumbing intact.
- Rejected: the Primary "halt on red parent" design — deferred, not implemented, as a scope call for
  this task (see Scope/Out). A future task should own it explicitly, since it also needs its own
  answer for umbrella-branch parents (the issue's own "Related" note: "argues for gating umbrella
  branches properly, not tolerating red ones") which is out of scope for a lazy-computation change.
  Also rejected: the second fallback ("overlap it" — run it in the background concurrent with batch
  1) — it still pays the full eager cost, just hides its latency; lazy is strictly cheaper for the
  common case where no batch's verify ever fails against a baseline it needed.

### review-duration-derived-not-trusted (#1097)

- Decision: applies uniformly to plan, discussion, and code review (all three route through the same
  `_agent_dispatch.write_brief` / `_review_common.py` finalize path).
  - `_agent_dispatch.write_brief` additionally writes a small sibling stamp file next to the brief
    (e.g. `<brief_path>` with suffix swapped to `.prepare_ts`, mirroring `output_path_for`'s existing
    `.out.md` suffix-swap pattern) containing the wall-clock time the brief was written (UTC epoch
    seconds is sufficient; reuse whatever the codebase's existing `_timestamp` helper exposes for a
    raw epoch value, or store the ISO string and diff on read).
  - In the shared finalize path in `_review_common.py` (`apply_cost_metadata` / `finalize`'s
    `duration_s` handling), when a `.prepare_ts` stamp file exists next to the brief for this round,
    compute `derived_duration_s = now - prepare_ts`. Use `derived_duration_s` as the value written to
    `duration_s:`, ignoring or overriding a caller-supplied `--duration-s` whenever the two disagree
    by more than a small tolerance (e.g. the greater of 20% relative or a fixed few-seconds absolute
    floor, to allow for brief-write / process-launch overhead) — log a one-line ASCII warning noting
    the discrepancy and which value won, rather than silently accepting the caller's number. When
    they roughly agree, or no `--duration-s` was passed at all, use the derived value. `--duration-s`
    remains available as a fallback for any dispatch path that doesn't go through `write_brief` (there
    is no other such path today under Agent-mode dispatch, but the flag itself is kept rather than
    removed, so no CLI contract breaks).
  - This is a non-blocking correction (never raises, never halts a review round) — the goal is a
    trustworthy `duration_s:` value for `/mill-review-summary`'s timing table, not a new failure mode
    in the review pipeline.
- Rationale: `write_brief` is the one place already common to plan/discussion/code Agent-mode
  dispatch, so stamping there fixes all three review types with one change instead of three
  parallel ones. A wall-clock stamp (not a monotonic one) is required because prepare and finalize run
  as separate process invocations with real dispatched-agent work happening in between — a
  monotonic clock does not survive across processes.
- Rejected: a hard reject (fail the finalize call) on disagreement — the issue's own fallback phrasing
  ("failing that, finalize should reject...") is the fallback to the primary ask ("derive it itself"),
  and a hard failure would turn a cosmetic timing-accuracy bug into a new way to block a review round
  in agent mode, which is worse than an occasionally-imprecise duration value.

### handoff-no-session-changelog (#1095)

- Decision: rewrite `plugins/mill/skills/handoff/SKILL.md` to add, verbatim, the four elements the
  issue proposes:
  1. An explicit, example-bearing prohibition: the handoff document must not contain a session
     changelog under any heading — naming "Done this session", "Changes made", "Completed work",
     "Recent commits" as anti-pattern headings to reject on sight, and stating plainly that work
     already committed is described by its commit, and work already merged is described by its PR —
     never restated in the handoff.
  2. A one-line positive statement of the document's job — current state and durable facts, not
     history — plus the per-line test to apply while writing it: "would a fresh agent act differently
     if this line were missing? If not, cut it." Call out explicitly that this test removes passing
     test counts, timings, and descriptions of already-finished edits, while keeping open PRs,
     in-flight work, and constraints.
  3. Explicit handling of the overwrite case: when the handoff replaces an existing handoff document,
     the author re-derives every section from this skill's rules and treats the previous file only as
     a source of *facts* (e.g. "PR #183 is still open"), never as a section template or outline to
     inherit — this is what stops one generation's violation from reproducing in every later one, per
     the issue's own root-cause analysis of how the pattern propagated.
  4. A short anti-pattern example list under the prohibition (item 1): a committed refactor, a green
     test run with its duration, a merged PR's contents, a review whose file is already committed at
     a known path — each with a one-line "why not" (already captured elsewhere / not durable state).
- Rationale: this is a documentation-only fix scoped to exactly the file and section the issue names;
  the existing "don't duplicate content already captured in other artifacts" rule already gestures at
  this but reads, per the issue's own analysis, as being about specs/design docs rather than commits —
  naming the anti-pattern with headings an author would actually write is what makes it catchable by
  a fresh session with no memory of this incident.
- Rejected: leaving the fix at "the existing duplication rule already covers this, tighten the
  wording only" — the issue's incident shows the existing wording already failed to fire twice in one
  document; a reworded-but-still-abstract rule doesn't add the overwrite-case handling (item 3), which
  is the structural fix that stops recurrence.

### dotnet-node-reuse-hygiene (#1094)

- Decision: update `plugins/csharp/skills/csharp-build/SKILL.md`'s two documented default commands
  (currently `dotnet build --nologo -clp:ErrorsOnly` / `dotnet test --nologo -clp:ErrorsOnly`) to add
  `-p:UseSharedCompilation=false /nr:false`, matching exactly the flags the issue's own incident
  confirms resolves the stall (`dotnet test ... -p:UseSharedCompilation=false /nr:false` completed in
  32s versus an 11+ minute stall without them). Add a short note next to the commands explaining why:
  a long orchestrated mill session chains many sequential `dotnet build`/`dotnet test` calls (per-batch
  verify, baseline pre-flight, merge-in verify replay, git-pr's final verify), and MSBuild's
  `nodeReuse:true` default lets worker processes accumulate and contend across that whole session
  unless explicitly disabled per invocation.
  - This is the only fix location: every mill call site that runs a `dotnet build`/`dotnet test`
    invocation (per-batch verify, baseline pre-flight, merge-in verify replay, git-pr Step 5) does so
    by executing whatever command string the plan's `verify:` field (or the ad-hoc convention) names —
    none of them hardcode the dotnet invocation themselves — so fixing the one documented source that
    plan authors and ad-hoc callers copy from is sufficient; no `_verify_baseline.py`/
    `_implementer_common.py` changes are needed.
- Rationale: matches the issue's own suggested fix exactly, and the flags are the ones already proven
  in the incident's own before/after comparison.
- Rejected: a periodic "clear stale node-reuse servers" background mechanism (the issue's other
  suggested option) — that's an environment-level workaround for a problem the invocation flags solve
  directly and for free; no new machinery needed.

### skill-cross-reference-no-bare-cd-bait (#1092)

- Decision: in `plugins/mill/skills/mill-plan/SKILL.md` and `plugins/mill/skills/mill-start/SKILL.md`,
  replace every cross-reference to `mill-go-base/SKILL.md`'s "## Agent-mode dispatch" section — both
  the bare `mill-go-base/SKILL.md` form (mill-plan, 9 occurrences) and the repo-relative
  `plugins/mill/skills/mill-go-base/SKILL.md` form (mill-start, 10 occurrences) — with the fully
  qualified `` `${CLAUDE_PLUGIN_ROOT}/skills/mill-go-base/SKILL.md` `` form, matching this repo's own
  established convention (CLAUDE.md: "`${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths ... Write
  `${CLAUDE_PLUGIN_ROOT}` literally in Bash tool calls"). This makes the natural way to actually read
  the cited section (`awk '/^## Agent-mode dispatch/,/^## [^A]/' "${CLAUDE_PLUGIN_ROOT}/skills/
  mill-go-base/SKILL.md"`) require no `cd` at all, closing the exact bait the issue identifies.
  - mill-start's existing repo-relative form is already safer than mill-plan's bare form (no `cd`
    strictly required, since it can be read as `awk ... plugins/mill/skills/mill-go-base/SKILL.md`
    from the worktree root), but it is still not the `${CLAUDE_PLUGIN_ROOT}` convention the rest of
    the codebase uses for intra-plugin references, and it still implicitly assumes cwd is the git
    root — bringing both files to the same `${CLAUDE_PLUGIN_ROOT}`-qualified form removes that
    assumption too.
- Rationale: purely mechanical, low-risk text substitution confined to the two files the issue names;
  it removes the ambiguity that produced the natural-but-wrong `cd <dir> && awk ...` reading without
  changing any behavior these skills describe.
- Rejected: a repo-wide sweep for every other cross-reference to any skill file — out of scope per
  Scope/Out; the issue names exactly these two files and this one target section.

### self-hosting-cache-freshness-note (#1077)

- Decision: the underlying bug (the `git grep` pathspec using `:!<task_dir>` instead of
  `:(exclude)<task_dir>`) is already fixed in this dev tree — confirmed by reading
  `mill-merge/SKILL.md` and `mill-finalize/SKILL.md`, both of which already use `:(exclude)` (commit
  `ace7dbbf`, landed before this task started). What remains from the issue is the self-hosting
  cache-freshness gap itself: add a documentation note, not a new automated check, at the two sites
  most exposed to it:
  1. In this repo's own `CLAUDE.md`, under a self-hosting-relevant section (near the existing
     `CLAUDE_PLUGIN_ROOT` guidance), state plainly: a fix merged to `main` under `plugins/mill/**`
     during the current session does not take effect in any *dispatched* mill-go/mill-merge/mill-plan
     invocation until the plugin cache is refreshed — those dispatches read
     `${CLAUDE_PLUGIN_ROOT}`, a frozen copy, not the dev tree. Point at `./update-plugins.sh` (run
     from the hub root) as the existing, already-working refresh mechanism.
  2. In `mill-merge/SKILL.md`, at the Step 4 citation-scan block (the exact site the issue's incident
     hit), add a one-line pointer back to that CLAUDE.md note, so a future recurrence of *any*
     stale-cache symptom at that call site is one hop from the fix instead of requiring independent
     rediscovery.
- Rationale: a real cache-freshness *check* (diffing the installed `${CLAUDE_PLUGIN_ROOT}` cache
  against this dev tree's `plugins/mill/skills/**`) is meaningful new machinery with real false-positive
  risk (version pinning, non-self-hosting installs where no dev tree exists to compare against) for a
  problem that is rare by construction (it only occurs when millhouse is developing millhouse) and
  already has a working manual fix (`update-plugins.sh`). Documenting the known-working recovery is
  the proportionate fix; building a detector is not justified by one incident.
- Rejected: an automated freshness check at mill-go/mill-merge entry (the issue's own first suggested
  option) — deferred as disproportionate to a single-incident, self-hosting-only failure mode with an
  existing manual fix; a future task can revisit if this recurs.

## Technical context

- Wiki daemon internals: `plugins/mill/scripts/wiki/_client.py` (`health_check`, `_ensure_daemon`,
  `_dispatch`), `plugins/mill/scripts/wiki/_sync.py` (`pull`, `commit_push`), `plugins/mill/scripts/
  wiki/_server.py` (`_render_and_commit_all`, which already closes/reopens the TinyDB store around
  every git operation — reuse this pattern, don't reinvent it).
- PR state: `plugins/mill/scripts/_pr_state.py` (`resolve_pr_state`), consumed by `plugins/mill/
  skills/mill-merge/SKILL.md`'s `### PR-state gate` and `plugins/mill/scripts/millpy-cleanup.py`'s
  `_apply_pr_reap_record`. Repo detection: reuse `plugins/mill/scripts/_gh_issues.py`'s
  `detect_repo(git_root)` — do not reimplement remote-URL parsing.
- Verify-field normalization: `plugins/mill/scripts/_plan_dag.py`'s `parse_verify_field` is the single
  normalizer for every `verify:` frontmatter read site (implementer, fixer, baseline, merge-in,
  plan-validate); `millpy-merge-in-subagent.py`'s `_run_recompute_baseline` is the one holdout that
  needs to route through it.
- Baseline machinery: `plugins/mill/scripts/_verify_baseline.py` (`compute_baseline`,
  `compute_batch_baselines`, `_checkout_parent_branch`, `_link_dependency_dirs`), driven by
  `plugins/mill/scripts/millpy-implement.py`'s `_run_baseline_stage` and consumed by `plugins/mill/
  scripts/millpy-fix.py`'s union-baseline logic. Orchestration lives in `plugins/mill/skills/
  mill-go-base/SKILL.md` sections "0.5 Baseline pre-flight" / "0.55 Done-gate baseline pre-flight" /
  "0.6 Per-batch baseline recapture" (self-hosting only). `plugins/mill/scripts/_status.py` already
  has the `get_module_verify_baseline`/`set_module_verify_baseline`/`clear_module_verify_baseline`
  accessor pattern to mirror for the new `baseline_parent_sha` field.
- Review duration: `plugins/mill/scripts/_agent_dispatch.py` (`write_brief`, `output_path_for`),
  `plugins/mill/scripts/_review_common.py` (`apply_cost_metadata`, `finalize`), invoked identically
  from `millpy-review-plan.py`, `millpy-review-discussion.py`, and `millpy-review-code.py`.
- Skill docs touched: `plugins/mill/skills/handoff/SKILL.md`, `plugins/csharp/skills/csharp-build/
  SKILL.md`, `plugins/mill/skills/mill-plan/SKILL.md`, `plugins/mill/skills/mill-start/SKILL.md`,
  `plugins/mill/skills/mill-merge/SKILL.md`, this repo's own `CLAUDE.md`.
- Unit tests live under `plugins/mill/unit_tests/test-<name>.py`, run via `run-all.py`, using
  in-memory/tempfile fixtures — no real git/LLM. The wiki daemon tests already use
  `WIKI_DAEMON_INPROCESS=1`/`WIKI_DAEMON_SKIP_GIT`/`WIKI_DAEMON_SKIP_PUSH` env-var seams (see
  `wiki/_client.py`'s `_dispatch` and `wiki/_server.py`'s `_render_and_commit_all`) — reuse these for
  #1107/#1103 tests rather than spawning a real daemon subprocess.

## Constraints

No `CONSTRAINTS.md` present at the hub root — none to enumerate beyond this repo's own `CLAUDE.md`
(already reflected in the Decisions above: `${CLAUDE_PLUGIN_ROOT}` usage, ASCII-only `print()`/`_log()`
output, ban on `sed`, no wiki file mutation outside `_client`/`git -C <wiki>`).

## Testing

- **#1107** (wiki-health-check-post-spawn-race): unit test using the existing `WIKI_DAEMON_INPROCESS`/
  `use_inprocess` test seams — simulate a spawned-but-not-yet-ready daemon (e.g. a fake handler that
  returns `ok: False` for the first N health probes, then `ok: True`) and assert `_ensure_daemon`
  retries past the false negatives within its deadline rather than surfacing one immediately. TDD
  candidate: write the failing-then-succeeding probe stub first.
- **#1106** (merge-in-recompute-baseline-verify-field): unit test driving
  `_run_recompute_baseline` (or its constituent call) against an overview frontmatter whose `verify:`
  is the `{cwd: hub, command: ...}` mapping form, asserting no `TypeError` and that
  `compute_baseline` receives a plain string command plus the correct `cwd_override_relative`. A
  second case covers a malformed mapping (missing `command:`), asserting the function still emits a
  `{"status": "success", "baseline": "error", ...}` line rather than raising. TDD candidate.
- **#1105** (pr-state-repo-flag-and-error-visibility): unit test with a fake/stubbed
  `_subprocess_util.run` asserting `--repo <owner/repo>` is present in the constructed `gh pr list`
  argv when `detect_repo` resolves one, and absent when it returns `""`. Separate case: a non-zero
  exit populates `error` while a zero-exit empty-list result leaves `error: None`. TDD candidate for
  both branches.
- **#1103** (wiki-stale-clone-recovery-visibility): unit test asserting the pre-render `pull()`
  failure path in `_render_and_commit_all` now logs (via a captured stderr/log seam) rather than
  passing silently; a string-match assertion on `WikiPushError`'s rebase-failure message confirming
  it references `millpy-wiki-shutdown.py`.
- **#1102** (baseline-preflight-lazy-not-eager): unit tests for the new `baseline_parent_sha`
  get/set/clear accessors (mirror the existing `module_verify_baseline` accessor tests exactly).
  Integration-shaped test (or a carefully stubbed unit test) asserting a batch's verify failure with
  no cached `verify_baseline_failures` triggers on-demand computation against the pinned SHA, and that
  a second failure of the same batch does NOT recompute (cache hit). Assert batch 1 dispatch no longer
  waits on any per-batch baseline computation when no batch has failed yet.
- **#1097** (review-duration-derived-not-trusted): unit test asserting `write_brief` produces a
  `.prepare_ts` stamp file; a finalize-path unit test asserting `duration_s` is derived from the stamp
  when no `--duration-s` is passed, and that a wildly disagreeing passed value is overridden (with the
  derived value winning) rather than recorded verbatim. TDD candidate — this is the exact bug from the
  issue's own observed case (556.0 recorded vs. ~353s actual).
- **#1095** (handoff-no-session-changelog): no automated test (this is a skill-instructions file, not
  code) — instead, self-review: read the fully rewritten `handoff/SKILL.md` and confirm heading
  scaffolding for the four proposed elements, and confirm none of the four example anti-pattern
  headings appear anywhere else in the file as an implied allowed pattern.
- **#1094** (dotnet-node-reuse-hygiene): no automated test (this is a target-repo skill's documented
  command, not mill's own code) — verify the flags are present and correctly placed in the updated
  `csharp-build/SKILL.md`.
- **#1092** (skill-cross-reference-no-bare-cd-bait): grep-based self-check — after editing, `grep -n
  "mill-go-base/SKILL.md" plugins/mill/skills/mill-plan/SKILL.md plugins/mill/skills/mill-start/
  SKILL.md` must show every remaining occurrence already prefixed with `${CLAUDE_PLUGIN_ROOT}/skills/`.
- **#1077** (self-hosting-cache-freshness-note): no automated test — verify the CLAUDE.md note and the
  mill-merge/SKILL.md pointer both exist and cross-reference correctly.

## Q&A log

- **Q:** No human operator is present for this `--auto` mill-start run — how should the ten
  source issues' fixes be scoped when several (#1102, #1097) touch large, actively-evolving
  mechanisms? **A:** [auto-pick] For each, prefer the smallest change that fully resolves the
  reported symptom and stays within the blast radius of files the issue itself names or that direct
  code-reading shows are the actual root cause; where the issue offers its own primary/fallback
  framing (#1102), adopt the fallback and document why the primary is deferred, rather than either
  silently picking the primary or refusing to make the call. **Why:** the task instructions call for
  making the most defensible call and stating it as an assumption rather than halting for an absent
  operator; a full architectural reversal (#1102's primary) inside a ten-item grab-bag risks
  destabilizing machinery three recent commits just hardened, which outweighs the primary option's
  cleaner end state for this task's scope.
