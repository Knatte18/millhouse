# Discussion: Fix infrastructure bugs across merge, wiki-daemon, config, plan, and cleanup

```yaml
task: Fix infrastructure bugs across merge, wiki-daemon, config, plan, and cleanup
slug: mill-infra-bug-fixes
status: discussing
parent: main
```

## Problem

A batch of 22 mill infrastructure bugs was filed across mill-merge, the
wiki daemon client, config loading, mill-plan, mill-cleanup, the
implementer, the review backend, and the psmux dispatch path (GitHub
issues #403, #404, #405, #407, #409, #413, #414, #417, #421, #422, #423,
#425, #426, #427, #428, #429, #430, #431, #432, #433, #434). These were
reported across several branches over the past weeks; many surfaced as
hard-stops during real orchestration runs on Windows (connection resets
during Handoff, holistic reviews dying, cleanup refusing to remove
worktrees, false-success merge fixers).

**Why now:** the bugs degrade orchestration reliability on the operator's
day-to-day Windows hub. Several are one-line transient-error gaps that
force a full skill re-run; others (false-success in the merge-in fixer,
ERROR-only review rounds) silently corrupt task state or burn reviewer
dispatches. They are independent and small, which makes them a good
single-sweep task.

**Re-audit result.** During discussion every issue was checked against
the *current* branch (`hanf/mill-infra-bug-fixes`, which already carries
substantial hardening commits). Six issues are already fixed and are
**out of scope** -- see Scope/Out. The remaining **12** are confirmed
present (most verified by reading current code or by live reproduction)
and form the work for this task.

## Scope

**In** -- 12 confirmed-present fixes:

- **#404 + #407 -- wiki client transient-error retry.**
  `wiki/_client._dispatch` retries only `TimeoutError`; add
  `ConnectionResetError` / `ConnectionRefusedError` (WinError 10054 /
  10061) to the same backoff loop. One chokepoint fix covering all
  client ops (`set_phase`, `merge_tasks`, etc.).
- **#431 -- review verdict parser tolerance.**
  `_review_common.parse_verdict` requires a fenced ` ```yaml ` block and
  raises (-> verdict ERROR) when the reviewer emits an unfenced
  `verdict:` line. Add a fallback that accepts an unfenced verdict.
- **#432 -- holistic review crash on directory refs.**
  `_review_common._read_for_bulk` / `bulk_files` call `read_text()` on a
  bare directory path listed in a plan batch's Context/Creates, raising
  `PermissionError` on Windows and killing the holistic review. Skip (or
  expand) directory paths.
- **#427 -- scope-violation false positives on junctions.**
  `_cleanliness.compute_scope_violations` currently reports `.portals`
  and `.wiki` (verified live in this worktree) even though they are
  gitignored junctions. Exclude the junction names.
- **#417 -- stale bash poll-loops lock worktrees.**
  (1) mill-cleanup / `_worktree.remove_safe` have no logic to kill stale
  `bash.exe` poll-loop processes holding handles into a worktree before
  `git worktree remove`; add it. (2) The subprocess/psmux poll loops in
  mill-go SKILL.md have no max-wait; add a self-terminating timeout.
- **#434 -- cleanup misidentifies non-worktree dirs as orphans.**
  `millpy-cleanup.py` enumerates `wts/` with `iterdir()` and treats every
  subdir as a worktree. Use `_worktree.list_worktrees` (already exists;
  runs `git worktree list --porcelain`) as the authoritative source.
- **#425 -- deterministic verify failure misclassified as transient.**
  A missing/unresolvable verify binary (e.g. `go` not in PATH) is
  classified `stuck_type: transient`, triggering a wasteful auto-retry.
  Classify command-not-found / missing-binary failures as
  `verify`/`infrastructure`.
- **#426 -- dirty tree after implementer success.**
  A formatter-induced change (e.g. gofmt) left uncommitted after the
  implementer reports success trips the cleanliness gate. Ensure
  formatter drift is committed before success is reported.
- **#421 -- `PYTHONPATH=` verify rule is language-blind.**
  `_plan_validate.py`'s `verify-not-isolated` check (and the mill-plan
  SKILL.md / CLAUDE.md wording) require `PYTHONPATH= ` on *every* verify
  command; wrong for Go/C# projects. Make it Python-project-aware.
- **#423 -- plan holistic review timeout on large plans.**
  Add a `large_prompt` reviewer/timeout override for plan review,
  mirroring the existing code-review mechanism; fall back to
  `holistic_timeout`.
- **#428 + #433 -- psmux dispatch (dormant but real).**
  `millpy-claude-sub.py` passes the prompt as a command-line arg (fails
  past the ~32767-char Windows limit) and hardcodes a 300s bulk
  response-poll cap that kills holistic reviews below `holistic_timeout`.
  Use stdin redirection and honor the review-layer timeout. Dispatch
  default is `agent`, so these only fire under `dispatch: psmux`; fixed
  now so the fallback path is not a trap.
- **#403 -- missing cache helper produces a cryptic crash.**
  When a helper module (e.g. `_archive_tag.py`) is absent from the
  installed plugin cache (stale install), callers die with
  `ModuleNotFoundError`. Add a preflight self-check that detects missing
  helper modules in the active `CLAUDE_PLUGIN_ROOT` and emits an
  actionable "refresh your cache" message.

**Out** -- already fixed on this branch (verified during discussion; no
work):

- **#414** -- `llm.claude.psmux.shell_path` unknown-key warning: fixed by
  commit 22e2d3f5; config loads cleanly with no warning.
- **#422** -- mill-plan invoking self-report as a Python CLI: SKILL.md
  already invokes the `/mill-self-report` Skill (no `millpy-self-report.py`
  exists or is referenced).
- **#430** -- review-discussion slug detection: `millpy-review-discussion.py`
  now passes `git_root` (task worktree), so slug detects from the branch.
- **#405** -- mill-start not forwarding `--slug`: symptom eliminated by
  #430's fix; no multi-task ERROR. (Belt-and-suspenders `--slug` forward
  intentionally not added.)
- **#413** -- mill-plan not flipping phase to `planned`: all approve paths
  (4a/4b/4c) break to Handoff, which appends `planned` unconditionally
  after its guard (SKILL.md:204).
- **#429** -- worktree `config.local.yaml` ignored: live-verified that a
  worktree override now takes effect (call sites pass the worktree
  `.millhouse`). The `load_config` duplication is a latent code smell but
  not a live bug; intentionally not refactored here.

Also out of scope: any change to the agent-SDK dispatch architecture
itself; the wiki daemon server side (the retry fix is client-only).

## Decisions

### wiki-client-retry (#404, #407)

- Decision: Add `ConnectionResetError` and `ConnectionRefusedError` to
  the existing `except (TimeoutError, ...)` retry loop in
  `wiki/_client._dispatch` (the single chokepoint all public client ops
  funnel through). Keep the existing backoff schedule (`[2, 4, 8]`, 4
  attempts) and the terminal `WikiBusyError`.
- Rationale: One change covers every transient daemon hiccup for every
  caller (`set_phase` during mill-go Handoff and mill-merge done-flip,
  plus `merge_tasks`, `upsert_*`, etc.) without per-call-site retry code.
  Both reported errors are sub-second transients that succeed on retry.
- Rejected: Per-call-site retry in mill-go/mill-merge SKILL.md (scatters
  logic, misses other ops). Catching broad `OSError` (too wide -- would
  swallow genuinely-dead-daemon errors that should fail fast).

### review-parser-tolerance (#431)

- Decision: In `parse_verdict`, when no fenced ` ```yaml ` block is
  found, fall back to scanning for an unfenced `verdict: <VALUE>` line
  (first match wins) before raising. Accept the same four valid values
  (`APPROVE`, `REQUEST_CHANGES`, `GAPS_FOUND`, `NEED_CONTEXT`). The
  fenced-block path stays the primary contract.
- Rationale: An ERROR-only round discards a real review (the verdict and
  findings are present in the raw text) and burns reviewer dispatches /
  hits the two-pass ERROR cap. Tolerant parsing recovers the verdict.
- Rejected: Relaxing only the template (does not fix already-misformatted
  output at parse time). Tolerating arbitrary phrasings (keep it to a
  clear `verdict:` line to avoid false positives).

### bulk-read-directory-skip (#432)

- Decision: In `_read_for_bulk` (or `bulk_files`), detect `p.is_dir()`
  and skip it with a stderr warning rather than `read_text()`. Also
  broaden the `bulk_files` exception guard to catch `PermissionError`
  alongside `FileNotFoundError` as defense-in-depth.
- Rationale: A directory in a plan batch's Context/Creates list is a
  legitimate authoring pattern; it must not crash the holistic review.
- Rejected: Recursively expanding directories into their files (larger
  behavior change, unbounded bulk size); skip is the minimal correct fix.

### scope-violation-junction-skip (#427)

- Decision: Exclude the junction directory names (`.active`, `.portals`,
  `.wiki`, and `.others` if present) in
  `_cleanliness.compute_scope_violations`, regardless of gitignore
  status, since pygit2's `status_porcelain` reports the junction symlinks
  even though `git check-ignore` lists them as ignored.
- Rationale: Verified live -- `compute_scope_violations` returns
  `['.portals', '.wiki']` in a clean task worktree, so every implementer
  invocation reports false violations, masking any real one.
- Rejected: Relying on gitignore (already in place, demonstrably not
  honored for these symlinks by pygit2). A hardcoded skip-set of the
  known junction names is explicit and reliable.

### cleanup-process-kill-and-orphan-detection (#417, #434)

- Decision (#417): Before `_worktree.remove_safe` runs
  `git worktree remove`, find and kill stale processes holding handles
  into the target worktree (Windows: match `bash.exe` / poll-loop command
  lines referencing the worktree path; POSIX: equivalent). Also add a
  bounded max-wait (e.g. ~3600s) to the subprocess/psmux poll-loops
  documented in mill-go SKILL.md so they self-terminate.
- Decision (#434): Replace the `iterdir()`-based orphan-worktree scan in
  `millpy-cleanup.py` with `_worktree.list_worktrees(hub_root)` (parses
  `git worktree list --porcelain`). Only report directories that are
  registered worktrees lacking an active marker; ignore plain
  directories (e.g. an empty `millhouse.worktrees` leftover).
- Rationale: Default dispatch is `agent` (synchronous, no poll loop), so
  the poll-loop timeout is secondary; the dominant failure is
  `WinError 32` from leftover handles, which the process-kill safety net
  addresses for all dispatch modes. The orphan-detection fix removes
  false "orphan worktree" reports.
- Rejected (#417): SKILL.md timeout alone (does not cover already-orphaned
  processes from a crashed session). Rejected (#434): name-pattern
  filtering of `wts/` entries (fragile; the git registry is
  authoritative).

### implementer-stuck-classification (#425)

- Decision: Classify a verify failure caused by a missing/unresolvable
  command (command-not-found / "No such file" / binary absent) as
  `stuck_type: verify` (or `infrastructure`), not `transient`, so mill-go
  does not auto-retry a deterministic failure. The implementer's stuck
  classification path is the locus (see Technical context for the exact
  flow under agent vs subprocess dispatch -- the implementer brief's
  classification guidance and any deterministic detection in the finalize
  path both need to agree).
- Rationale: A `transient` classification triggers mill-go's one-retry
  policy, which re-runs and fails identically, wasting a round.
- Rejected: Treating all verify failures as non-transient (a genuinely
  flaky test should still be retryable); scope the change to the
  missing-binary signal.

### implementer-formatter-cleanliness (#426)

- Decision: Ensure the implementer commits *all* working-tree changes --
  including formatter-induced edits produced by running the verify/format
  step -- before emitting `{"status": "success"}`. Approach: the
  implementer brief instructs running the formatter and committing its
  output before reporting; and/or the finalize/cleanliness path commits
  residual formatter drift rather than failing the gate. Final locus to
  be pinned by mill-plan after reading the implementer brief + finalize
  flow.
- Rationale: A cosmetic formatter whitespace change left uncommitted
  blocks the batch on the cleanliness gate and requires manual recovery.
- Rejected: Loosening the cleanliness gate to ignore modifications (would
  mask real uncommitted work); the change must be committed, not ignored.

### plan-verify-language-aware (#421)

- Decision: Make the `verify-not-isolated` check in `_plan_validate.py`
  fire only for Python projects -- detect a Python project by the
  presence of `pyproject.toml` / mill `scripts/` (or equivalent marker)
  at the project root, and only then require the `PYTHONPATH= ` prefix.
  Reword the mill-plan SKILL.md and the CLAUDE.md "Verify command shape"
  note to say the prefix is required for Python verify commands only.
- Rationale: mill is used for Go and C# projects where `PYTHONPATH=` is
  meaningless and misleading. The prefix's real purpose (stop the test
  subprocess inheriting the cache `PYTHONPATH`) is Python-specific.
- Rejected: SKILL.md reword without the validator change (validator would
  still reject correct Go/C# verify commands). Dropping the rule entirely
  (it is correct and necessary for Python/mill projects).

### plan-review-large-prompt (#423)

- Decision: Add a `large_prompt` override for plan holistic review
  mirroring the code-review mechanism (`maybe_switch_spec_for_large_prompt`
  already runs for plan review; extend it / its config so a large plan can
  select a longer-timeout reviewer spec, and/or honor a
  `roles.plan-review.holistic.large_prompt.timeout`). Fall back to the
  configured `holistic_timeout` when unset. Document the new key in the
  config template.
- Rationale: A 6+ batch plan exceeds the 1800s holistic timeout and dies
  with ERROR; the code-review path already solved this and the pattern
  should be reused, not reinvented.
- Rejected: Bumping the global `holistic_timeout` default (penalizes every
  review; does not scale with plan size). Context truncation (loses review
  fidelity).

### psmux-large-prompt-and-timeout (#428, #433)

- Decision: In `millpy-claude-sub.py`, pass the prompt to `claude` via
  stdin redirection / pipe instead of expanding it on the command line
  (#428), and make the bulk response-poll timeout honor the review-layer
  `holistic_timeout` (pass it through to the wrapper / derive the cap from
  it) instead of the hardcoded 300s (#433).
- Rationale: Although `dispatch: agent` is the default and these are
  dormant, the psmux fallback is silently broken for large prompts and
  long reviews; fixing now prevents a trap if anyone switches dispatch.
- Rejected: Deferring (leaves a broken fallback). Removing psmux (out of
  scope; it is a supported dispatch mode).

### cache-helper-preflight (#403)

- Decision: Add a preflight self-check (a small helper invoked early by
  the affected entrypoints, or a standalone check) that verifies the
  required helper modules are importable from the active
  `CLAUDE_PLUGIN_ROOT/scripts`, and on failure prints an actionable
  message telling the operator the cache is stale and to reinstall/refresh
  the plugin -- instead of a raw `ModuleNotFoundError`.
- Rationale: The cache is a full copy of the plugin dir (a stale install,
  not a packaging-exclusion bug); the only durable repo-side fix is to
  turn the cryptic crash into a clear instruction. mill-merge Step 6
  (`_archive_tag`) is the concrete trigger but the check should be
  general.
- Rejected: A packaging manifest/test (cache build is external to this
  repo; cannot be enforced here). Silent dev-tree `PYTHONPATH` fallback
  (masks the staleness and can load wrong-version code).

## Technical context

- **Dispatch architecture.** `cfg.llm.claude.dispatch` selects
  `subprocess | psmux | agent`; both the hub `mill-config.yaml` and the
  template default to `agent`. `_agent_dispatch.resolve_dispatch_mode`
  validates it. Agent mode runs reviewers/implementers as synchronous
  Agent-tool subagents, then calls the CLI with `--stage finalize
  --agent-output <file>`; the finalize path still runs
  `parse_verdict` / `_forward_output` / `finalize_from_output`, so the
  parser-tolerance (#431) and classification (#425, #426) fixes remain in
  the live path. psmux/subprocess are conditional fallbacks (#428/#433).
- **Wiki client.** `wiki/_client.py`: every public op funnels through
  `_dispatch` (~lines 123-160) -> `_connect_send_recv` (raises `OSError`
  subclasses). Retry loop currently catches only `TimeoutError`.
- **Review backend.** `_review_common.parse_verdict` (~line 1079, strict
  fenced-yaml scan); `_read_for_bulk` (~line 765) + `bulk_files` (~line
  799, catches only `FileNotFoundError`). `_review_plan.py` already calls
  `maybe_switch_spec_for_large_prompt` for the holistic scope but does
  not override the timeout. `holistic_timeout` lives at `cfg.llm`
  (template default 1800).
- **Cleanliness / implementer.** `_cleanliness.compute_scope_violations`
  uses `_pygit2_util.status_porcelain(include_untracked=True)` and filters
  only `_mill/`. `millpy-implement.py` `--stage full` catches
  `_llm_claude.LLMError` and hardcodes `stuck_type: transient` (line
  ~251); the verify-failure classification under agent dispatch is the
  implementer's reported JSON (driven by `templates/implementer-brief.md`)
  finalized via `_implementer_common._forward_output` /
  `finalize_from_output`. The implementer must reconcile both the brief's
  classification guidance and any deterministic finalize detection.
- **Cleanup.** `millpy-cleanup.py` builds its plan with `iterdir()` over
  `<container>/wts/` (~lines 186-209) for orphan detection; no
  process-killing exists in `millpy-cleanup.py` or `_worktree.py`.
  `_worktree.list_worktrees(cwd)` (line ~120) already parses
  `git worktree list --porcelain` and is the ready-made fix helper for
  #434. `_worktree.remove_safe` (line ~178) strips junctions then
  `git worktree remove`.
- **Plan validation.** `_plan_validate.py` `verify-not-isolated` check
  (~line 833) does `verify_stripped.startswith("PYTHONPATH=")`
  unconditionally. The mill-plan SKILL.md "Verify command shape" wording
  and CLAUDE.md both enshrine the universal rule -- update both.
- **psmux wrapper.** `millpy-claude-sub.py` `RESPONSE_POLL_TIMEOUT_S`
  (~line 31, `bulk: 300`); wrapper-script generation (~Step 9, ~line 320)
  passes `$prompt` as an argument.
- **Conventions to honor:** ASCII-only `print`/`_log` output (Windows
  cp1252); never run plugin scripts from the source repo for operational
  calls; all path resolution through `_paths.py`; fix misuse at call sites
  rather than retrofitting runtime guards onto clean helper APIs.

## Constraints

- Windows-first: every fix must behave correctly on Windows (cp1252
  stdout, junction symlinks, `WinError` socket codes, CreateProcess
  command-line limit). No non-ASCII in script stdout.
- No change to the agent-SDK dispatch architecture or the wiki daemon
  server.
- Helpers that take path args must not consult cwd for config; thread
  explicit paths.
- Keep helper APIs clean; correct wrong call sites rather than adding
  kw-only/runtime guards to "catch" misuse.

## Testing

Follow mill test conventions: `plugins/mill/unit_tests/test-<name>.py`
run via `run-all.py`; in-memory / tempfile fixtures; no real git or LLM.
Per fix:

- **#404/#407 (`_dispatch` retry):** unit-test that `_dispatch` retries
  and ultimately returns when `_connect_send_recv` is monkeypatched to
  raise `ConnectionResetError` / `ConnectionRefusedError` once (then
  succeed), and that it raises `WikiBusyError` after the budget. TDD
  candidate.
- **#431 (`parse_verdict`):** pure-function unit tests -- fenced block
  still parses; an unfenced `verdict: GAPS_FOUND` line now parses; junk
  with no verdict still raises. TDD candidate.
- **#432 (`_read_for_bulk` / `bulk_files`):** tempdir with a file and a
  subdirectory in the ref list -> directory skipped with warning, file
  read, no exception. TDD candidate.
- **#427 (`compute_scope_violations`):** assert junction names are
  excluded. Prefer refactoring the filter into a pure helper that takes
  the porcelain lines + skip-set so it is unit-testable without real
  junctions; regression-pin `.portals`/`.wiki` exclusion.
- **#425 (stuck classification):** unit-test the classifier on a
  command-not-found / missing-binary signal -> `verify`/`infrastructure`;
  a flaky/timeout signal -> `transient`. Extract a pure classify function
  if one does not exist.
- **#434 (orphan detection):** unit-test the orphan-selection logic with
  an injected worktree-set (from `list_worktrees`) + on-disk dir set ->
  only registered-but-unmarked worktrees reported; plain dirs ignored.
- **#421 (verify-not-isolated):** unit-test the check against a fake
  Python project root (marker present -> prefix required) and a non-Python
  root (no marker -> prefix not required, native command passes).
- **#423 (large-prompt timeout):** unit-test the timeout-resolution logic
  for plan holistic review -- large_prompt override honored, fallback to
  `holistic_timeout`.
- **#428/#433 (psmux wrapper):** unit-test wrapper generation uses stdin
  redirection (no prompt on the command line) and that the resolved bulk
  poll timeout honors a passed-through `holistic_timeout`.
- **#403 (cache preflight):** unit-test the check reports missing modules
  for a temp `CLAUDE_PLUGIN_ROOT` lacking a helper, and passes when
  present; assert the message is actionable and ASCII-only.
- **#417 (process kill):** unit-test the PID/command-line matching logic
  (which processes reference a given worktree path) with injected process
  records; the actual kill call and the SKILL.md poll-loop timeout are
  validated by inspection / integration, not unit tests.
- **#426 (formatter cleanliness):** integration-leaning; at minimum
  unit-test any extracted "commit residual drift" decision. Document the
  manual repro (verify step that runs a formatter must leave a clean tree
  after success).

## Q&A log

- **Q:** Keep all 22 issues in scope? **A:** No -- drop the 6 already
  fixed on this branch (#405, #413, #414, #422, #429, #430), verified by
  reading current code / live reproduction. 12 confirmed-present fixes
  remain.
- **Q:** Already-fixed issues -- add regression tests for them anyway?
  **A:** No. Drop them entirely; trust the existing fixes (operator
  directive: "drop what's fixed").
- **Q:** #403 (`_archive_tag` missing from cache) -- packaging fix or
  something else? **A:** It is a stale-install artifact, not a repo
  packaging bug (cache is a full copy). Add a preflight self-check that
  turns the `ModuleNotFoundError` into an actionable "refresh cache"
  message.
- **Q:** psmux bugs #428/#433 are dormant (default dispatch is `agent`) --
  fix now or defer? **A:** Fix now (stdin redirection + honor
  `holistic_timeout`); a broken fallback is a trap.
- **Q:** #429 -- worktree config layering: deep-merge worktree-local on
  top of hub and unify the two `load_config` functions? **A:** The acute
  symptom is already fixed (live-verified worktree override takes effect);
  drop the issue. The `load_config` duplication is a latent smell, left
  for a future cleanup, not this task.
- **Q:** #421 (`PYTHONPATH=`) -- validator change or doc-only? **A:** Make
  `_plan_validate.py` Python-project-aware and reword SKILL.md + CLAUDE.md.
- **Q:** #423 -- bump timeout or add an override? **A:** Add a
  `large_prompt` reviewer/timeout override for plan review mirroring
  code-review, falling back to `holistic_timeout`.
- **Q:** #427 -- isn't gitignore supposed to exclude the junctions? **A:**
  It is gitignored, but pygit2's `status_porcelain` still reports the
  `.portals`/`.wiki` symlinks (verified live), so an explicit junction
  skip-set is required.
