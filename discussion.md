# Discussion: 6 — mill-go SKILL.md prose + lock-API + lock-coverage + Builder-oppførsel

```yaml
task: 6 — mill-go SKILL.md prose + lock-API + lock-coverage + Builder-oppførsel
slug: mill-go-fixes
status: discussing
parent: main
```

## Problem

mill-go (the Builder skill that drives per-batch implementation) has accumulated 26 self-reported bugs across six runs since 2026-04-26. The bugs cluster on four surfaces:

1. **mill-go SKILL.md prose** — pseudocall notation (`wiki.sync_pull()`) misled the Builder into searching for a non-existent CLI; `_tasks_md.set_phase(home_path, ...)` documented signature does not match the real text-based one (six independent sightings: #28, #49, #51, #61, #76, #98); `status.md` / `reviews/` / `plan/` paths in the SKILL.md still reference the wiki (`<WIKI_PATH>/active/<slug>/...`) in violation of CLAUDE.md "Path invariants" — task-state lives on the task branch, not in the wiki (#99); the holistic-review carve-out forces a manual halt that is not motivated by any architectural difference from per-batch flow (#25); the Stuck table has no row for `LLMError` (subprocess crashed before JSON), so a transient subprocess failure halts the batch (#88); the builder lock is held across `auto_report` + `auto_merge` instead of being released right after the Home.md flip (#72).

2. **`_wiki.py` lock subsystem** — `acquire_lock(wiki_path, slug)` and `release_lock(wiki_path)` have asymmetric signatures and the acquire's return value is undocumented; six failure sightings ended in stale lockfiles + `LockBusy` cascades (#27). `sync_pull` and `write_commit_push` do not acquire the lock themselves; two parallel `mill-*` invocations on the same machine race on `FETCH_HEAD` and crash with "Cannot fast-forward to multiple branches" (2026-04-28 bug). Stale lock on uncaught exception (#82) is the third symptom of the same root cause: callers manage the lock externally and forget to release on failure.

3. **Helper-API gaps** — `_render.render` does not strip the leading HTML template comment, so the implementer-brief's 22-line documentation block (~600 tokens) is sent to every implementer call (#91). `_llm_claude.run_implementer` allows `Read,Edit,Write,Bash,Grep,Glob` — no `Skill`, so the implementer brief's instruction to invoke `@git-commit` is a dead letter; raw `git commit` falls back, skipping lint + `codeguide-update` (#97). `implementer-brief.md` requires a `session_id` field in the JSON report but the implementer chooses a synthetic string instead of echoing the UUID (#71, #89, #105 — four sightings).

4. **mill-plan / mill-start / mill-resume SKILL.md prose** — same `wiki.sync_pull()` pseudocall on Entry step 1 (#15/#55). mill-plan SKILL.md still refers to the obsolete `wiki/active/<slug>/plan/` path in its validator-fix commit (#102). `millpy-validate-plan.py` standalone CLI is broken with `TypeError: resolve_path() takes 2 positional arguments but 3 were given` (#101).

**Why now.** Every mill-go run since 2026-04-26 has hit at least one of these. The lock cascade in particular blocks parallel-worktree workflow (the whole point of the worktree model). Without a fix, every operator hits the same six bugs the first time they spawn a second worktree while a long-running mill-go is active in the first.

**Already resolved (excluded from scope; verified during exploration):**

- **#65** — `status-discussing.md` template already includes `plan: null`; unit test `test-status.py:344-352` asserts the fix.
- **#69** — mill-plan SKILL.md line 105 already says "via direct Edit" for `approved: true`; the contradictory phrasing is gone.
- **#74** — mill-go SKILL.md already invokes review CLI via `${CLAUDE_PLUGIN_ROOT}` (lines 96, 131).
- **#22** — no current code writes `.scratch/briefs/`; only `conversation/SKILL.md` mentions them. The `mill-go-batch.py` ad-hoc script that produced them no longer exists.

## Scope

**In:**

- Rewrite `_wiki.py` so `sync_pull` and `write_commit_push` acquire the wiki lock themselves; expose a `wiki_lock(wiki_path, slug)` context manager for callers that need a multi-operation locked window (e.g. read Home.md → `set_phase` → write_commit_push). Make the inner acquire re-entrant when the context manager already holds the lock for this PID. Add stale-self-lock detection (lock held by caller's own slug → reclaim instead of waiting).
- Drop `_wiki.acquire_lock` / `release_lock` from the public API; migrate every external call site (`millpy-add.py`, `millpy-cleanup.py`, `millpy-abandon.py`, `_spawn_core.py` ×2, `mill-merge` SKILL.md, `mill-go` SKILL.md, `mill-start` SKILL.md, `workflow` SKILL.md, integration test `test-merge.py`, unit test `test-abandon.py`).
- Add `_tasks_md.set_phase_at(path: Path, slug: str, phase: str | None) -> None` wrapper that does read/transform/write. Keep pure `set_phase(text, ...)` for tests.
- Strip leading HTML comment in `_render.render` (promote the pattern from `_status._strip_leading_comment`).
- Add `Skill` to `_llm_claude.run_implementer`'s `allowed_tools`.
- Tighten `implementer-brief.md` to require literal echo of the UUID in the `session_id` field.
- Rewrite `mill-go` SKILL.md Entry / Prepare / Execute / Code Review / Holistic / Handoff / Board discipline sections to (a) replace the pseudocall, (b) use `set_phase_at`, (c) move status.md / reviews/ writes to task-branch `git -C <worktree> add ... && git commit` (no push; mill-merge handles push at end), (d) reserve `_wiki.write_commit_push` for the Handoff Home.md flip only, (e) drop the holistic-review manual-only carve-out, (f) add a row mapping `LLMError` → `stuck_type: transient` to the Stuck table, (g) release the builder lock immediately after the Home.md flip + `set_phase("done")`, before invoking `/mill-self-report` and `/mill-merge`, (h) explicit signature lines for every helper the Builder calls so the Builder never reads source.
- Rewrite `mill-plan` and `mill-start` and `mill-resume` SKILL.md Entry step 1 to replace `wiki.sync_pull()` with concrete invocation. Fix `mill-plan` SKILL.md step 1.5 to commit the validator-fix on the task branch (`git -C <worktree>`), not via `_wiki.write_commit_push` to a `wiki/active/<slug>/plan/` path that no longer exists.
- Fix `millpy-validate-plan.py:32` so `resolve_path` is called with the correct two-arg signature.
- Add two anti-pattern rules to `mill:workflow` SKILL.md: "do not Read or Grep helper internals — call them; signatures are documented in the calling SKILL.md" and "do not write wrapper scripts for orchestration loops the SKILL.md describes inline — execute X, Y, Z as separate tool calls per round so the user can see and interrupt each round".

**Out:**

- `_status.update_field` upsert (#67) — deferred. Template seeds `plan: null`; no known caller needs upsert.
- Brief-file write removal (#22) — moot; no current code writes them.
- Resume section in mill-go SKILL.md — the existing pointer ("see *Resume*") references a section that does not exist; we leave the gap as-is to avoid scope creep.
- mill-go validation that the implementer's `session_id` in the JSON report matches the UUID we passed (#14 enforcement) — over-engineering; tightening the brief is enough.
- Cluster reviewer, holistic-fix agent, implementer self-spawning reviewer, mill-bg, mill-fold-issues, codeguide-seed — all separate Home.md tasks.
- `mill-setup` SKILL.md inline `_wiki.write_commit_push` examples — unaffected by the lock change because they pass the wiki path from a non-task context. The migration drops the external `acquire_lock`/`release_lock` calls but `_wiki.write_commit_push` keeps the same `(wiki_path, paths, msg, slug)` signature; mill-setup just gets a new required `slug` kwarg with a literal value `"mill-setup"`. (Same pattern as mill-cleanup uses today: `acquire_lock(wiki_path, "mill-cleanup")`.)

## Decisions

### lock-API: helpers own the lock + context manager for multi-op windows

- **Decision:** `_wiki.sync_pull(wiki_path, slug)` and `_wiki.write_commit_push(wiki_path, paths, msg, slug)` acquire and release the lock internally. Both gain a required keyword `slug: str`. A new `_wiki.wiki_lock(wiki_path, slug)` context manager exists for callers that need a read-modify-write window (the Handoff Home.md flip is the canonical case: read text → `_tasks_md.set_phase_at` → `write_commit_push`). When the context manager already holds the lock for this process, the inner acquire in `sync_pull` / `write_commit_push` is a no-op (re-entrancy via a module-level `_held_locks: dict[Path, int]` counter). Stale-self-lock detection: if `acquire` finds a lockfile whose holder slug matches `slug`, it reclaims (overwrites + warns) instead of waiting for the timeout.
- **Rationale:** Subsumes the asymmetric-signature bug (#27) — callers never touch the API again. Subsumes the lock-coverage gap (2026-04-28) — every wiki entry takes the lock. Subsumes the stale-lock-on-exception bug (#82) — the context manager's `__exit__` releases on the exception path; helper-internal acquire/release uses `try/finally`. Stale-self-lock detection turns the existing 30s wait into immediate reclaim when the prior holder is the same task that crashed without releasing.
- **Rejected:** Keep `acquire_lock`/`release_lock` symmetric (return token, accept token) without moving lock acquisition into helpers — fragile because every new caller has to remember to bracket sync_pull/write_commit_push, which is exactly the failure mode we just hit. No public context manager — Handoff would need to do read-set_phase-commit inside `write_commit_push`, which conflates concerns.

### `_tasks_md.set_phase_at` wrapper

- **Decision:** Add `set_phase_at(path: Path, slug: str, phase: str | None) -> None` that does `text = path.read_text(...)` → `set_phase(text, slug, phase)` → `path.write_text(...)`. Keep pure `set_phase(text, ...)` for tests and any caller that already has the text in hand.
- **Rationale:** Six independent TypeError sightings on every successful Handoff. The orchestrator skill is the wrong abstraction level for read/write boilerplate. The path-taking wrapper puts the right abstraction at the right level.
- **Rejected:** Change `set_phase` to accept `Path | str` — overloads obscure the contract; tests would have to pass strings explicitly anyway. Leave SKILL.md with the explicit read/transform/write pattern — three lines instead of one in the orchestrator skill, and the next reader still has to figure out the contract.

### `_render.render` strips leading HTML comment

- **Decision:** `_render.render` strips a leading HTML comment (`<!-- ... -->`) at the very start of the template before token substitution. Mid-template comments are preserved.
- **Rationale:** Every template ships with a documentation comment that is useful in source but pure noise in the rendered output. The pattern already exists in `_status._strip_leading_comment` for status.md; promoting it eliminates per-template duplication and saves ~600 tokens per implementer call (the brief's documentation block is the worst offender).
- **Rejected:** Strip only at mill-go's render call site — leaks template-rendering policy into the orchestrator. Leave alone — wastes tokens on every implementer call indefinitely.

### `_llm_claude.run_implementer` adds `Skill` to allowed tools

- **Decision:** `run_implementer` passes `--allowedTools Read,Edit,Write,Bash,Grep,Glob,Skill`.
- **Rationale:** The implementer brief instructs the implementer to invoke `@git-commit` for every per-card commit, so `git-commit`'s lint + `codeguide-update` runs and the next batch's implementer reads a fresh codeguide. Without `Skill`, that instruction is dead letter; the implementer falls back to raw `git commit`, codeguide drifts, and batch N+1 reads a stale map.
- **Rejected:** Build a `millpy-git-commit.py` CLI wrapper — duplicates a skill that already exists. Move `codeguide-update` to mill-go post-batch — architectural change that defers the codeguide refresh past batch N+1's start.

### mill-go SKILL.md: status.md / reviews/ / plan/ commits go on the task branch

- **Decision:** Every mutation of status.md, reviews/<file>, and plan/<file> in mill-go (and in mill-plan / mill-start) is committed via `git -C <worktree> add <path> && git -C <worktree> commit -m "..."`. No push. mill-merge pushes the task branch at the end. `_wiki.write_commit_push` is reserved for the Handoff Home.md flip only.
- **Rationale:** CLAUDE.md "Path invariants" makes this load-bearing: working state lives on the task branch, never in the wiki. The current SKILL.md violates this in Entry step 5–6, Prepare, Execute step 1, Code Review APPROVE/REQUEST_CHANGES, Max-rounds, and Board discipline lines 156–157. mill-resume on another machine fetches the task branch from origin (`git fetch origin <branch>`) — push from the task-branch git ops only happens at end-of-task via mill-merge, which is acceptable: cross-machine resume is a recovery path, not the steady state.
- **Rejected:** Local commit + push on every mutation — doubles git overhead per batch for a recovery-path benefit. Keep current wiki-write structure but annotate the wrong paths — leaves the bug present.

### Builder lock release order in Handoff

- **Decision:** Release the builder lock right after the Home.md flip + `_status.append_phase("done")`, BEFORE invoking `/mill-self-report` and `/mill-merge`.
- **Rationale:** Both auto-report and auto-merge interact with shared wiki resources. Holding the builder lock across them risks downstream contention with another worktree's mill-go that wants the lock. Releasing earlier matches the lock's intent: "one mill-go per worktree", not "one mill-go per worktree-plus-merge".
- **Rejected:** Keep current order — perpetuates the contention risk.

### Stuck table: transient subprocess crash row

- **Decision:** Add a row mapping `_llm_claude.LLMError` (subprocess crashed before JSON report) to `stuck_type: transient`. The existing one-retry policy applies: retry once with a fresh session; if the second attempt also fails, escalate per the regular `transient` row.
- **Rationale:** Currently a subprocess crash halts the batch with no recovery path. Treating it as transient matches the operator's expectation (network blips, claude-cli flakes recover on retry) and reuses the existing retry machinery.
- **Rejected:** Leave as-is — every subprocess hiccup halts the batch.

### `implementer-brief.md`: tighten `session_id` to literal-echo the UUID

- **Decision:** Update the brief to require: "`session_id` MUST be the exact UUID passed to you via the `--session-id` flag; do not invent or paraphrase." mill-go does not validate; it continues to use the UUID it generated. The fix is the contract, not enforcement.
- **Rationale:** Implementer keeps inventing synthetic strings in the field across every batch (#71, #89, #105 — four sightings spanning multiple repos). Today it is harmless because mill-go ignores the field, but the contract is broken every run; future code that round-trips the UUID would crash. Cheap fix; mill-go enforcement is over-engineering.
- **Rejected:** Drop the field — would break the JSON shape unnecessarily for a field that is fine when correctly populated. mill-go enforces and rejects mismatch — over-engineering for a field mill-go does not depend on.

### `mill:workflow` anti-pattern rules

- **Decision:** Add two rules to `mill:workflow` SKILL.md (workflow, not conversation — these are about HOW to invoke skills/helpers, not response style):

  1. **Don't Read or Grep helper internals.** When a SKILL.md names a helper to call, call it. Signatures are documented in the calling SKILL.md. If a helper fails, handle the exception then.
  2. **Don't write wrapper scripts for orchestration loops the SKILL.md describes inline.** If the SKILL says "for each round N do X, Y, Z", execute X, Y, Z as separate tool calls per round. The user must be able to see and interrupt each round. A script that packages a *transactional* operation (e.g. one implementer-spawn step) is fine; a script that packages a *loop* is not.

- **Rationale:** Three independent failure modes (#16, #19, #81) all point back to the Builder treating prose as code-to-derive instead of skill-to-execute. Memory is not the fix (rejected explicitly by the user during the original incident); skill-level rules survive across sessions.
- **Rejected:** Add to `mill:conversation` — wrong scope; conversation is response style. Inline in `mill-go` only — doesn't catch other orchestrator-style skills.

## Technical context

**Files mill-plan needs to know about:**

- [plugins/mill/scripts/_wiki.py](plugins/mill/scripts/_wiki.py) — the lock subsystem. Current public API: `acquire_lock(wiki_path, slug, timeout_seconds=30)`, `release_lock(wiki_path)`, `sync_pull(wiki_path)`, `write_commit_push(wiki_path, relative_paths, commit_msg)`. Module docstring documents the lock model. Stale threshold: 5 min.
- [plugins/mill/scripts/_tasks_md.py](plugins/mill/scripts/_tasks_md.py) — Home.md parser/renderer. `set_phase(text: str, slug: str, phase: str | None) -> str` is the existing text helper. Add `set_phase_at(path: Path, slug: str, phase: str | None) -> None` alongside.
- [plugins/mill/scripts/_render.py](plugins/mill/scripts/_render.py) — single template-substitution helper. Token grammar is `<UPPERCASE>`; HTML comments at the start need stripping. Pattern reference: `_status._strip_leading_comment` in [_status.py:52-68](plugins/mill/scripts/_status.py#L52-L68).
- [plugins/mill/scripts/_llm_claude.py](plugins/mill/scripts/_llm_claude.py) — `run_implementer` is the function whose `allowed_tools` need `Skill` added. Line ~347.
- [plugins/mill/scripts/millpy-validate-plan.py](plugins/mill/scripts/millpy-validate-plan.py) — line 32 calls `resolve_path(cfg["paths"]["plan_dir"], slug, wiki_root)`. The `_review_common.resolve_path` signature is `(path_tmpl, slug)` — drop the third arg.
- [plugins/mill/templates/implementer-brief.md](plugins/mill/templates/implementer-brief.md) — strip the leading HTML comment (will be auto-stripped by `_render.render` after the strip-promotion). Also tighten the `## Report` section's `session_id` requirement.
- [plugins/mill/skills/mill-go/SKILL.md](plugins/mill/skills/mill-go/SKILL.md) — full prose/path-invariant rewrite. Touches Entry / Prepare / Execute / Code Review / Holistic / Handoff / Board discipline.
- [plugins/mill/skills/mill-plan/SKILL.md](plugins/mill/skills/mill-plan/SKILL.md), [plugins/mill/skills/mill-start/SKILL.md](plugins/mill/skills/mill-start/SKILL.md), [plugins/mill/skills/mill-resume/SKILL.md](plugins/mill/skills/mill-resume/SKILL.md) — Entry step 1 pseudocall sweep.
- [plugins/mill/skills/mill-merge/SKILL.md](plugins/mill/skills/mill-merge/SKILL.md), [plugins/mill/skills/workflow/SKILL.md](plugins/mill/skills/workflow/SKILL.md) — drop external `acquire_lock` / `release_lock` references after the lock-API change.

**Caller migration sites for the lock-API change** (drop external acquire/release, add `slug` kwarg to sync_pull / write_commit_push):

- [millpy-add.py:170,200,204](plugins/mill/scripts/millpy-add.py)
- [millpy-cleanup.py:423,443,463,467](plugins/mill/scripts/millpy-cleanup.py) — uses literal `"mill-cleanup"` as slug; preserve.
- [millpy-abandon.py:94,97,103](plugins/mill/scripts/millpy-abandon.py)
- [millpy-claim.py:179](plugins/mill/scripts/millpy-claim.py) — sync_pull only.
- [millpy-spawn.py:119](plugins/mill/scripts/millpy-spawn.py) — sync_pull only.
- [_spawn_core.py:448,475,477,599,605,609](plugins/mill/scripts/_spawn_core.py) — both write_commit_push and acquire/release.
- Integration tests: [test-merge.py:299,304,310,314](plugins/mill/integration_tests/test-merge.py), [test-bootstrap.ps1:191](plugins/mill/integration_tests/test-bootstrap.ps1) (only mentions API in a comment; verify and update).
- Unit-test mocks: [test-abandon.py:69-71](plugins/mill/unit_tests/test-abandon.py), [test-cleanup.py:350,424,469,520,589](plugins/mill/unit_tests/test-cleanup.py), [test-millpy-claim.py:93](plugins/mill/unit_tests/test-millpy-claim.py), [test-millpy-spawn.py:127,279,372,506](plugins/mill/unit_tests/test-millpy-spawn.py).

**`set_phase_at` callers post-fix:**

- mill-go SKILL.md Handoff (Home.md flip).
- mill-merge SKILL.md (already does Home.md flips; check for the same TypeError pattern in its prose).

**Re-entrant lock implementation note:**

A module-level `_held_locks: dict[Path, int]` counter (keyed by absolute wiki path), guarded by `threading.Lock` if multi-threading is ever a concern (mill scripts are single-threaded today; the guard is cheap insurance). The `wiki_lock` context manager increments on `__enter__` (acquiring the disk lock if counter was 0), decrements on `__exit__` (releasing the disk lock if counter drops to 0). `sync_pull` / `write_commit_push` check the counter: if > 0, they skip both acquire and release.

**`mill-setup` SKILL.md is unaffected by the lock-API change in practice:** its `_wiki.write_commit_push` examples will get a new `slug="mill-setup"` literal argument, but the bootstrap context already has no concurrent callers to race with.

## Constraints

From [CLAUDE.md](CLAUDE.md) "Hard rules" — load-bearing for this task:

- **Junctions and hardlinks are NEVER used by scripts or skills.** Path resolution always goes through `_paths.py`. Any new SKILL.md prose that references a wiki or worktree path must use the resolver, not a junction.
- **`${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths.** Scripts referenced from SKILL.md must use `${CLAUDE_PLUGIN_ROOT}` not `plugins/mill/...`. mill-go SKILL.md already does this for review CLIs (lines 96, 131); the rewrite preserves it.
- **Working state is never written to the wiki.** This is the path-invariant the mill-go SKILL.md rewrite (Decision 5) restores.

From [CLAUDE.md](CLAUDE.md) "Path invariants":

- All path resolution goes through `_paths.py`. New helpers go there.
- Working state (status.md, discussion.md, plan/, reviews/) lives at the worktree root on the task branch.
- Scratch lives at `<cwd>/.scratch/`, not under `.millhouse/`.

From [conversation/SKILL.md](plugins/mill/skills/conversation/SKILL.md):

- Never write to `/tmp/`, `$env:TEMP`, system temp dirs.
- Worktree isolation: a session running from a child worktree may not edit files in the parent worktree, may not `cd <parent-path>`, may not commit/push/stage parent state. mill-go and mill-plan run in child worktrees; the SKILL.md prose must respect this.

No `CONSTRAINTS.md` at the hub root.

## Testing

**Unit tests** (run via `python plugins/mill/unit_tests/run-all.py`):

- **`test-wiki.py`** (new or extended): `wiki_lock` context manager re-entrancy (nested `with wiki_lock(...)` does not deadlock); stale-self-lock detection (when lockfile holder == caller's slug, reclaim immediately); `sync_pull` and `write_commit_push` acquire/release internally (assert `.mill-lock` is gone after each call); inside a `wiki_lock` context, `sync_pull` and `write_commit_push` do NOT acquire/release (re-entrancy via the held-lock counter); release on exception (write_commit_push raises → lockfile is gone).
- **`test-tasks-md.py`**: `set_phase_at` reads file, transforms, writes back; raises on missing slug; preserves trailing newline (delegates to `set_phase`).
- **`test-render.py`** (new or extended): leading HTML comment is stripped before token substitution; mid-template HTML comments are preserved verbatim; an HTML comment that wraps the entire template (no token after `-->`) renders as empty body.
- **`test-millpy-validate-plan.py`** (new): standalone CLI invocation against a fixture plan dir returns exit 0 + JSON envelope; exit 1 + errors envelope when fixture has a known violation.
- **Existing unit tests for caller migration** — update mocked acquire_lock/release_lock signatures to nothing (they're gone from the public API); update mocked write_commit_push / sync_pull mocks to accept the new `slug` kwarg.

**Integration tests** (live `git`, optionally live `claude`):

- **`test-wiki-concurrency.py`** (new): spawn two subprocess `_wiki.sync_pull` calls back-to-back against the same wiki clone; assert both succeed and the second waits for the first instead of crashing on FETCH_HEAD. This is the 2026-04-28 regression test.
- **`test-merge.py`**: update for the new lock-API surface; the existing test calls `_wiki.acquire_lock(wiki, slug)` + `release_lock(wiki)` explicitly — replace with `with _wiki.wiki_lock(wiki, slug):` or drop entirely if write_commit_push now handles it.
- **`test-bootstrap.ps1`**: the comment on line 191 mentions the lock API; update to reflect the new surface. Behavioral test should still pass.

**TDD candidates:**

- `_wiki.wiki_lock` context manager + re-entrancy. Write the test first; the implementation is small enough (a counter and a try/finally) to follow the test.
- `_render._strip_leading_comment` in render. Write the test first against the canonical implementer-brief HTML comment.
- Stale-self-lock detection. Write a test that creates a lockfile with the caller's own slug and asserts immediate reclaim.

**Manual smoke test** after batches B01+B02 land but before B04 (mill-go SKILL.md rewrite):

- Run `mill-spawn` from main while a long mill-go is active in another worktree; the second spawn should succeed without `Cannot fast-forward to multiple branches`.

**No tests for:**

- SKILL.md prose changes (B04, B05, B06) — covered by the next mill-go integration run.

## Q&A log

- **Q:** Lock all real folded issues + the 2026-04-28 wiki-concurrency bug? **A:** Yes — fix every still-real folded issue.
- **Q:** Drop or tighten the `session_id` field in implementer brief (#71/89/105)? **A:** Tighten — require literal echo of the UUID. mill-go keeps ignoring (no validation).
- **Q:** Anti-pattern rules for "don't read helper source" / "don't write wrapper scripts" — `mill:conversation` or `mill:workflow`? **A:** `mill:workflow` — these are about HOW to invoke skills/helpers, not response style.
- **Q:** Lock-API design — context manager, token, or helpers own the lock? **A:** Helpers own the lock + `wiki_lock` context manager for multi-op windows + re-entrant inner acquire + stale-self-lock detection. Subsumes #27/#82/2026-04-28 in one move.
- **Q:** `set_phase` for Home.md — wrapper or change signature? **A:** Add `set_phase_at(path, slug, phase) -> None`; keep pure `set_phase(text, ...)` for tests.
- **Q:** `_render.render` HTML-comment strip — in `_render` or at call site? **A:** In `_render.render`. Pattern already exists in `_status._strip_leading_comment`; promote it.
- **Q:** `_llm_claude.run_implementer` — add `Skill` tool, build a CLI wrapper, or move codeguide post-batch? **A:** Add `Skill` to `allowed_tools`. Smallest change; brief's instruction starts working.
- **Q:** mill-go SKILL.md path-invariant rewrite — full or minimal? **A:** Full rewrite of Entry/Prepare/Execute/Code Review/Holistic/Handoff. status.md and reviews/ commits are task-branch local-only; no push (mill-merge pushes at end). `_wiki.write_commit_push` reserved for the Handoff Home.md flip only.
- **Q:** Builder-lock release order in Handoff (#72)? **A:** Release right after Home.md flip + `set_phase("done")`, BEFORE auto-report and auto-merge.
- **Q:** Stuck table — add `LLMError` (subprocess crash) row (#88)? **A:** Yes — map to `stuck_type: transient`, apply existing one-retry policy.
- **Q:** `_status.update_field` upsert (#67)? **A:** Defer — template seeds `plan: null`; no caller needs upsert.
- **Q:** Batch decomposition? **A:** Six batches (B01 lock unification, B02 helper API additions, B03 validate-plan TypeError, B04 mill-go SKILL.md rewrite, B05 mill-plan/start/resume prose, B06 workflow anti-pattern rules). DAG: B01/B02/B03/B06 parallel-safe; B04 depends on B01+B02; B05 depends on B01.
- **Q:** status.md / reviews/ commits — local-only or push to remote? **A:** Local-only; mill-merge pushes at end. mill-resume on another machine handles the recovery path via `git fetch origin <branch>` if needed.
- **Q:** Brief `session_id` literal-echo enforcement — also validate in mill-go? **A:** No. Tighten the brief; mill-go keeps ignoring.
- **Q:** `_wiki.sync_pull` / `write_commit_push` slug source? **A:** Required keyword arg `slug: str`; callers pass it explicitly. mill-cleanup keeps `"mill-cleanup"`, mill-spawn passes the slug it's about to claim.
- **Q:** `wiki.sync_pull()` pseudocall sweep — also covers mill-resume? **A:** Yes; B05 covers mill-start + mill-plan + mill-resume.
