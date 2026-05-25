# Discussion: Finish V3 wiki adoption — complete batch 3 port and test sweep

```yaml
task: Finish V3 wiki adoption — complete batch 3 port and test sweep
slug: wiki-v3-batch3-finish
status: discussing
parent: hanf/wiki-v3-adoption
```

## Problem

The `wiki-v3-adoption` task got batches 1 and 2 to green and committed 31 commits' worth of batch 3, but did not complete batch 3. Four sequential implementer dispatches (haiku via `claude -p` print mode, no auto-compact) landed 9 + 5 + 3 + 4 cards before the fourth timed out at 1800 s with WIP in the worktree. Filed as issue [#371](https://github.com/Knatte18/millhouse/issues/371). The prerequisite task `wiki-v3-verify-isolation` has since landed on this branch (commit `7e10ddb`), so verify subprocesses now load worktree code only — the cache-leakage diagnosis (handoff insight #2) is resolved.

Current state on `hanf/wiki-v3-batch3-finish` under proper isolation (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`): **17 of 77** unit tests fail. Failures cluster in three groups: (a) shipping scripts still importing deleted `_tasks_md` / `_wiki` / `_sidebar` modules — chain-failing tests that import those scripts, (b) test files still calling V2 APIs directly or building `_tasks_md.Task(...)` fixtures, (c) a real V3 product bug where `wiki._client._ensure_daemon` never connects in test fixtures (handoff insight #3, survives PYTHONPATH isolation — `test-millpy-claim.py` is the canonical victim, 11/12 tests timeout).

**Why now:** the V2 modules `_wiki.py`, `_tasks_md.py`, `_sidebar.py` are already deleted (card 30 landed before all callers were ported — handoff insight #2 origin). Shipping scripts in fresh checkouts crash on import. Tests don't pass. The branch can't merge to `main` or even back to `hanf/wiki-v3-adoption` in this state. This task closes the gap and **eliminates every trace of wiki V2 from the mill codebase**.

## Scope

**Primary goal — eliminate V2.** This is not a "port"; it is a **deletion**. When this task completes, the mill codebase contains zero references to wiki V2 — no imports, no fixtures, no docstrings, no error messages, no helpers added as temporary adapters during the port.

**In:**

- **Daemon-startup bug root-cause + fix.** Instrument `wiki._client._spawn_server` to capture stderr from the detached child, identify the real failure mode, fix it in product code. See *Daemon investigation* under Decisions for the diagnostic approach.
- **Shipping-code V2 elimination — cards 25, 26 (finish), 28, 29:**
  - `millpy-spawn.py` — drop `import _tasks_md`, `import _wiki`; drop the `wiki_cfg = resolve_wiki_path(repo_root) / "config.yaml"` fallback branch in `_load_config`; replace `_wiki.sync_pull(...)` + `_tasks_md.parse(home_text)` with `wiki.list_tasks_brief(wiki_path)`; propagate the dict-shape change to all consumers in this file.
  - `_spawn_core.py` — complete the V2 elimination begun by `a1f7aac`: drop `import _tasks_md` (line 73), `import _wiki` (line 74), AND `import _sidebar` (line 70 — the third deleted V2 module, currently still imported); delete the two `_sidebar.regenerate(wiki_path)` calls at lines 515 and 658 outright (V3's daemon regenerates the sidebar internally — these calls have no V3 replacement); replace `_tasks_md.Task` type hints (lines 153, 232, 271, 336–337, 405, 545) with `dict`; replace `_tasks_md.parse`/`remove_entry`/`append_entry`/`claim` (lines 509–513, 534) with `wiki.merge_tasks(...)` atomic op + `wiki.set_phase`/`wiki.get_task`; replace `_wiki.wiki_lock` + `_wiki.write_commit_push` (lines 504, 530, 654, 659) with the V3-equivalent flat sequence; delete `_task_to_dict` (lines 257–268) since no V2 `Task` objects exist after this card; convert every `t.<attr>` to `t["<attr>"]` for the new dict iteration variables; delete the `[s]` (spawn-ready) phase fast-paths — V3 has no `[s]` phase.
  - Small CLIs — `millpy-inspect.py`, `millpy-status.py`, `millpy-terminal.py`, `millpy-vscode.py`: each has one `import _tasks_md` and one `_tasks_md.parse(home_md.read_text(...))` call; both replaced by `wiki.list_tasks_brief(wiki_path)`.
  - `millpy-wikipush.py` sliver — remove `import _wiki` (line 32); unwrap the `with _wiki.wiki_lock(...) as lock_handle:` context manager (line 111); drop the `except _wiki.LockBusy as e:` block (line 113); the push logic itself stays direct (already uses `subprocess` + `git -C <wiki_path>`).
  - Surface-only V2-elimination — `_paths.py` lines 125 / 140 / 407 (drop `_wiki.write_commit_push` mentions in error messages, replace with `git -C <wiki_path>`), `_junction.py:301` (drop `_wiki` mention in docstring), `_worktree.py:207` (drop `_wiki.read_junctions` mention in docstring). No behaviour change; purely text.
  - `_paths.py:318–319` — internal variable name `_wiki = resolve_wiki_path(...)` clashes with the (now-deleted) module name and is misleading; rename the local to `_wiki_path` or `wiki_dir`.
- **Test sweep V2 elimination — cards 36, 37, 38:**
  - **Pass 1 (card 36) — V2 imports and direct calls.** Every test file: delete `import _wiki` / `import _tasks_md` / `import _sidebar`; replace direct calls (`_tasks_md.parse`, `_tasks_md.set_phase`, `_tasks_md.claim`, `_tasks_md.append_to_body`, `_tasks_md.LOCKED_FOLD_PHASES`, `_wiki.write_commit_push`, `_wiki.sync_pull`, `_wiki.wiki_lock`, `_sidebar.regenerate`) with their V3 equivalents (`wiki.list_tasks_brief`, `wiki.get_task`, `wiki.set_phase`, `wiki.upsert_task`, `wiki.upsert_tasks_batch`, `wiki._sync.commit_push`). **Verified current state (planner must re-confirm at plan time):** files with V2 imports/calls are `_test_helpers.py` (line 25 — `import _tasks_md`; line 114 — `_tasks_md.parse`), `test-fold.py` (lines 15–16 — both imports; lines 142–207 — `_tasks_md.append_to_body`/`LOCKED_FOLD_PHASES`; lines 506–511 — `_wiki.write_commit_push`), `test-millpy-spawn.py` (lines 967–970 — `import _tasks_md as real_tasks_md` + `_tasks_md.parse`), `test-spawn-core.py` (line 25 — `import _tasks_md`; lines 88, 190, 198, 206, 216, 231, 244, 260, 275 — `_tasks_md.parse` calls and a `_wiki.write_commit_push` docstring mention). **`test-millpy-claim.py` is NOT a card-36 target** — its 11/12 timeout failures are the batch-A daemon bug, not V2 references (its `sc.claim_in_wiki` calls patch the V3 function `_spawn_core.claim_in_wiki`, not V2). Card 36 expected size: ~4 cards (one per file in the list above).
  - **Pass 2 (card 37) — `mock.patch` retargeting.** Retarget any `mock.patch("...")` strings from V2 module paths to V3: `mill_<cli>.wiki.<fn>`. Delete any `mock.patch("mill_<cli>._sidebar.regenerate")` patches outright (V3's daemon handles sidebar internally). **State note:** a fresh `grep -rn 'mock\.patch.*['\''\"]\(_tasks_md\|_wiki\|_sidebar\)' plugins/mill/unit_tests/` against the current worktree returns **zero matches**. The Pass-2 work appears to have already been done in the test-port commits (`23eabc6`, `8d3b24b`, etc.) on this branch. Card 37 may be empty in practice. **Planner must verify** against `_mill/plan/03-v2-deletion-and-port.md` on parent `hanf/wiki-v3-adoption` (authoritative source) AND a fresh grep at plan time; if both come back clean, fold card 37 into the verify-smoke at the end of batch C with a one-line note "card 37 found empty — V2 mock.patches already removed in prior commits".
  - **Pass 3 (card 38) — fixture conversions and dead-test deletion.** Replace any `_tasks_md.Task(slug=..., title=..., phase=..., has_proposal=..., heading_line_no=...)` fixture builders with `dict` literals carrying `{id, slug, title, group, brief, status, has_proposal}` (V3's `list_tasks_brief` shape — see *Task dict shape* under Technical context). Delete tests that exercised now-removed semantics: `LockBusy` exception handling, `OP_READ` round-trip (V3 has no `OP_READ`), `wiki/config.yaml` fallback. Re-route text-Home.md fixtures (those that write Home.md text and parse it back) through `wiki._client.upsert_tasks_batch`. **State note:** a fresh `grep -rn 'Task(slug=' plugins/mill/unit_tests/` returns **zero matches**; the V2 `Task(...)` builder calls appear already removed in prior commits. Card 38 may also be largely empty. **Planner must verify** against `_mill/plan/03-v2-deletion-and-port.md` on parent and a fresh grep; whatever remains (e.g. residual `LockBusy`/`OP_READ` test cases, text-Home.md fixtures) becomes the actual card-38 work. The authoritative per-file enumeration lives in `_mill/plan/03-v2-deletion-and-port.md` on `hanf/wiki-v3-adoption`.
- **Surfaced fixture bug — test-wiki-noop-commit.** `test_real_change_commits_normally` fails because the test fixture creates a wiki clone with no `origin` remote, but `wiki._sync.commit_push` calls `git push` unconditionally. Fix in-scope: amend the test fixture to add a bare-clone `origin` (the proper testing pattern for `commit_push`). Production code is correct; the fixture is wrong.
- **End-of-task cleanup.** Delete `_mill/handoff.md` (the 122-line diagnostic from `hanf/wiki-v3-adoption`) — it's been consumed by this task.

**Out:**

- **Anything not enumerated above.** Production behaviour changes beyond the V2-elimination scope are out: no UX redesigns, no API renames in `wiki/*`, no daemon protocol changes beyond what's required to fix the startup bug, no migration tooling (V2→V3 migration scripts were already deleted in card 31).
- **Branch base change.** This task stays on `hanf/wiki-v3-batch3-finish` off `hanf/wiki-v3-adoption`, not `main`. The 81 commits ahead of main are real and must be preserved. Squash-merge to `hanf/wiki-v3-adoption` at task end; a separate task or operator decision later opens the eventual `main` PR.
- **Refactors of unrelated mill code.** If a card's diff touches a file outside the enumerated set, the reviewer should push back. Exception: if a real bug surfaces in a V3 module *and* it blocks verify from going green, fix it in-scope (per the surfaced-bug policy under Decisions); file a follow-up issue for anything that doesn't block verify.
- **Migration of older fixture conventions.** Tests that already work and don't reference V2 don't get rewritten just because they could use newer V3 helpers.
- **The new `wiki._client.list_tasks_full` API.** Card 26 uses `list_tasks_brief` only; consumers that need full task fields can switch later if needed.
- **Documentation outside the enumerated docstring/error-text fixes (card 29).** Wiki pages, SKILL.md files, README.md, CLAUDE.md — out of scope unless they contain a `_wiki`/`_tasks_md`/`_sidebar` reference that breaks something. Operator-facing docs were already swept in card 33 (`mill-go: start batch v2-deletion-and-port` and related commits).

## Decisions

### Batch order: daemon first, then shipping, then test sweep

- **Decision:** Plan in four sequential batches in this order: **A** (daemon-bug diagnosis + fix), **B** (shipping-code V2 elimination — cards 25, 26, 28, 29), **C** (test sweep passes 1+2 — cards 36, 37 + noop-commit fixture fix), **D** (test sweep pass 3 — card 38 + final smoke + handoff.md deletion).
- **Rationale:** The daemon-startup bug is in product code that the test sweep depends on. Until it's fixed, every test that calls `wiki.<fn>` without mocking the daemon eats a 10 s timeout. Fixing it first unblocks the test sweep. Shipping code goes next because it's small (4 cards), well-enumerated, and shakes out any product issues before the bulkier test sweep. Test sweep last, because it has the highest card count and is the most repetitive — best done when product code is stable.
- **Rejected:**
  - *Shipping-code first then daemon* — would leave tests broken longer; daemon bug surfaces real risk the V3 server has problems we should know about before relying on it.
  - *Mock the daemon in tests; skip the bug investigation* — ducks insight #3. Production users would still hit the bug. Documents the wrong contract.

### Daemon investigation: root-cause with stderr capture

- **Decision:** Batch A's first card is a diagnostic: temporarily redirect `wiki._client._spawn_server`'s detached child's stderr to a debug log file (or print to stdout via a `--debug` env var) so the real startup failure is captured. Read the captured error, then write one or more fix cards based on what we find. Revert the debug instrumentation in the final fix card so production stays clean.
- **Rationale:** The current symptom — `WikiStartupError: daemon did not start within timeout` — masks the actual failure inside the detached subprocess. The `_spawn_server` function uses `cmd /c start "" /B /MIN` with `creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB`, which deliberately throws away stderr. Two plausible root causes: (1) `wiki._server` crashes on startup (import error, port-bind failure, TinyDB lock contention with handoff insight #2's stale `.wiki-daemon.log` files); (2) Windows-specific `creationflags` combination prevents the child from inheriting the env needed to import `wiki._server`. Without stderr, we're guessing.
- **Rejected:**
  - *Bump SPAWN_TIMEOUT to 30 s and pray* — likely papers over an instant failure with a longer wait; useless.
  - *Add a daemon mock fixture for tests only* — leaves the bug for real users.

### Batch sizing: per-card effort tag + per-batch ceiling

- **Decision:** Each card in the plan carries an **effort tag** in its frontmatter: `effort: S` (≈ 1 unit; small surface change, single function, < 50 LOC diff, single concept), `effort: M` (≈ 2 units; moderate change spanning a function group, 50–200 LOC, one decision), `effort: L` (≈ 4 units; large change, > 200 LOC or cross-file refactor, multiple decisions). **Per-batch ceiling: 4 effort-units.** Plan-review enforces it.
- **Rationale:** Issue #371's root cause was implementer context exhaustion mid-batch, not the raw card count. An effort-weighted ceiling lets the planner split work where it actually costs context (large refactor cards weigh more than trivial deletes). Concrete numbers: a batch of 4× S is fine; a single L card alone is the whole batch; 1 L + 0 others is fine because it likely fills the implementer's window. The 4-unit ceiling is intentionally low — slightly tighter than the proposal's 12–15 card cap, but a sweep card (S) and a port card (L) measure different things.
- **Rejected:**
  - *Per-card LOC estimate* — too brittle; small LOC count can still mean a hard problem.
  - *Soft guideline, no enforcement* — repeats the #371 mistake by relying on planner self-discipline.

### Test-sweep granularity: one card per test file, one commit per file

- **Decision:** In batch C (cards 36 + 37) and batch D (card 38), each test file gets its own card and its own commit on the task branch. Cards are tagged `effort: S` unless the file is exceptional. Commit messages follow `test(<file-basename>): port to V3 wiki API` or similar.
- **Rationale:** Smallest possible review surface; per-file `git -c diff.colorMoved=plain` review is feasible; bisect-friendly. Aligns with proposal's note. Pairs well with the effort-tag ceiling — each batch can fit ~4 S-tagged file ports.
- **Rejected:**
  - *Bundle 2–3 related test files per card* — saves cards at the cost of larger diff per card and harder bisection; not worth it.
  - *One mega-card for all of pass-1, one for all of pass-2* — exactly the #371 anti-pattern.

### Per-batch verify mandatory + zero-failure end criterion

- **Decision:** Every batch frontmatter has a non-null `verify:` command, prefixed with `PYTHONPATH= ` per the verify-isolation invariant. The plan's final card runs the full `run-all.py` smoke and must observe **zero failing tests**.
- **Rationale:** Catches regressions card-by-card instead of post-mortem. Cheap relative to the cost of bisecting a 4-batch regression. The zero-failure end state is the only honest definition of "V2 elimination is done" — pre-existing failures unattributable to the V3 port have a follow-up issue + a `pytest.skip` mark with the issue link.
- **Rejected:**
  - *Verify only at end* — slow feedback; #371's spiritual cousin.
  - *Verify-skip on test-sweep cards* — defeats the purpose of the sweep, since each card's whole point is to make a test green.

### Surfaced-bug policy: in-scope if attributable, follow-up issue otherwise

- **Decision:** Any test failure reasonably attributable to the V2→V3 port (e.g. a fixture that worked under V2 but breaks under V3 because of a different API contract) is fixed in-scope, by adding a card to the appropriate batch. Truly orthogonal bugs (e.g. a wiki._sync push-protocol issue unrelated to V2 elimination) get a GitHub issue and a `pytest.skip` with the issue link; verify still goes green.
- **Rationale:** The handoff explicitly anticipated this (`test-wiki-noop-commit` surfaced as exactly this kind of case). A binary in/out scope policy plus a documented exit ramp keeps the task bounded without paying the cost of leaving the worktree red.
- **Rejected:**
  - *Strict "only enumerated cards"* — would leave verify failing at task end, which violates the zero-failure criterion. Inconsistent.
  - *Fix every failing test no matter the cause* — unbounded scope creep.

### `_task_to_dict` helper: delete in card 26's final step

- **Decision:** The `_task_to_dict` helper added in commit `a1f7aac` is removed as the last step of card 26. Once `millpy-spawn.py` (card 25) and the rest of `_spawn_core.py` consume `wiki.list_tasks_brief` directly, no V2 `Task` objects flow through the system, so no conversion helper is needed.
- **Rationale:** The helper exists only as a transition scaffold for the partial port. Keeping it forever would be dead code. Deleting it is part of the "eliminate V2" goal.
- **Rejected:**
  - *Keep as defensive adapter* — anti-pattern. There's nothing to adapt from.
  - *Promote to public utility* — premature abstraction, no caller needs it.

### `heading_line_no`: drop everywhere

- **Decision:** Remove all references to V2's `heading_line_no` field from `_spawn_core.py` and any test that asserts on it. Error messages that quoted line numbers become slug-based (e.g. `f"task {slug}: ..."`).
- **Rationale:** V3 stores tasks in TinyDB; there are no text positions to track. Synthesising a fake `heading_line_no: 0` carries dead data forever; adding line-number computation to V3 is a pointless re-parse cost.
- **Rejected:**
  - *Synthesise `heading_line_no: 0`* — dead data, anti-pattern.
  - *Re-parse Home.md to compute line numbers* — V3 doesn't store text Home.md at rest; the "text" is rendered on demand from TinyDB.

### Merge strategy: squash to `hanf/wiki-v3-adoption`, defer main PR

- **Decision:** When this task is complete and verified, `/mill-finalize` squash-merges `hanf/wiki-v3-batch3-finish` into its parent `hanf/wiki-v3-adoption`. The parent branch then carries one consolidated `batch3-finish` commit on top of its 81 existing commits. The eventual PR `hanf/wiki-v3-adoption` → `main` is a separate operator decision (not part of this task).
- **Rationale:** Matches mill's standard parent/child flow. Keeps `main`'s eventual V3-adoption PR coherent (one big review) without forcing the batch-3 fix-up to be litigated inside that PR. Allows time to validate the squashed batch-3 work on the parent before the main PR is opened.
- **Rejected:**
  - *PR directly to main, bypass parent* — would dump 81 + N commits into one PR review with no clear seam.
  - *Defer to mill-finalize time* — risks last-minute scramble; the decision is cheap to make now.

### Implementer model: sonnet for all batches

- **Decision:** All four batches target sonnet as the implementer model in plan frontmatter.
- **Rationale:** Sonnet has the context headroom for the gnarlier work (`_spawn_core.py` port in batch B, daemon-bug root-cause in batch A) and avoids the haiku print-mode context-exhaustion pattern that filed issue #371. Cost premium over haiku is acceptable for a one-off finalization task.
- **Rejected:**
  - *Haiku with effort caps* — still risky; #371's diagnosis was that haiku's print-mode lacks auto-compact, so even capped batches can run out.
  - *Opus for daemon batch, sonnet elsewhere* — opus might help on the diagnosis card but adds orchestration complexity and cost; sonnet is sufficient.

### Stuck-handling: pause for human input

- **Decision:** Plan frontmatter sets the orchestrator policy to **pause for human input on stuck** (mill-go's `pipeline.autonomous_mode: false` equivalent, or whatever the current `mill-config.yaml` key is). The implementer pauses for operator decision after N (current default) consecutive same-gate failures on a card.
- **Rationale:** Several cards in this task touch design decisions that the operator may want to weigh in on (e.g. the exact V3 surface for `wiki.merge_tasks` if it turns out the current API doesn't fit cleanly). Pause-and-ask is cheap; wrong-direction auto-fix is expensive.
- **Rejected:**
  - *Autonomous* — risks compounding a wrong fix through subsequent cards.
  - *Defer to ambient config* — implicit, surprising if `config.local.yaml` changes between sessions.

## Technical context

### V3 wiki API (the only surface the plan should use)

`plugins/mill/scripts/wiki/_client.py` exports:

All signatures verified against `plugins/mill/scripts/wiki/_client.py`.

| Function | Returns | Purpose |
|---|---|---|
| `upsert_task(wiki_path, slug, *, title=None, brief=None, body=None, group=None, status=None)` | `dict` (the upserted task) | Add or update a single task. `slug` is positional and required; all other fields are keyword-only and optional. Verified `_client.py:42–95`. |
| `upsert_tasks_batch(wiki_path, tasks: list[dict], *, message: str \| None = None)` | `None` | Atomic batch upsert; replaces text-Home.md fixture pattern. `message` is an optional commit-message tail. Verified `_client.py:98–132`. |
| `set_phase(wiki_path, id_or_slug: int \| str, phase: str \| None)` | `None` | Replaces V2 `_tasks_md.claim`/`set_phase`. Accepts either the TinyDB `id` or the `slug`; `phase=None` clears. Raises `WikiNotFoundError` if the target doesn't exist. Verified `_client.py:135–169`. |
| `remove_task(wiki_path, id_or_slug: int \| str)` | `None` | Replaces `_tasks_md.remove_entry`. Raises `WikiNotFoundError` if missing. Verified `_client.py:172–204`. |
| `get_task(wiki_path, id_or_slug: int \| str)` | `dict \| None` | Returns the task dict or `None` if not found (does NOT raise). Replaces `_tasks_md.parse(text); find by slug`. Verified `_client.py:207–234`. |
| `list_tasks_brief(wiki_path)` | `list[dict]` | Each dict has keys `{id, slug, title, group, brief, status, has_proposal}`. Replaces `_tasks_md.parse(home_md.read_text())`. Verified `_client.py:237–260`. |
| `list_tasks_full(wiki_path)` | `list[dict]` | All TinyDB task fields. Not used in this task. Verified `_client.py:263–286`. |
| `merge_tasks(wiki_path, *, remove_slugs: list[str], upsert: dict, set_phase: tuple[int \| str, str \| None] \| None = None)` | `dict` (the upserted task) | Atomic op replacing `_wiki.wiki_lock` + read-modify-write windows in `_spawn_core.multi_select_groom_then_claim`. All operational args are **keyword-only**. `set_phase` is `(id_or_slug, phase)`. Verified `_client.py:289–331`. |
| `health_check(wiki_path)` | `bool` | Daemon ping. Verified `_client.py:333+`. |

The error hierarchy (`wiki/__init__.py`): `WikiError`, `WikiNotFoundError`, `WikiConflictError`, `WikiPushError`, `WikiProtocolError`, `WikiStartupError`, `WikiPathError`. There is **no** `WikiLockBusy` — the old `_wiki.LockBusy` exception has no V3 equivalent because the daemon serialises writes internally. Code that catches `LockBusy` should drop the except block entirely (no retry needed; V3 calls are synchronous and atomic).

### Task dict shape (V2 → V3 field mapping)

| V2 `Task` field | V3 dict key | Notes |
|---|---|---|
| `slug: str` | `slug: str` | Unchanged. |
| `title: str` | `title: str` | Unchanged. |
| `phase: str \| None` | `status: str \| None` | Renamed. Values still `None`/`"active"`/`"done"`/`"abandoned"`; `"s"` (spawn-ready) is GONE — drop fast-paths. |
| `has_proposal: bool` | `has_proposal: bool` | Unchanged. |
| `heading_line_no: int` | (no equivalent) | Dropped. Error messages adapt to slug-only. |
| (no equivalent) | `id: <opaque>` | TinyDB document id; used by `wiki._client` internals, not by callers. |
| (no equivalent) | `group: str \| None` | The Home.md `## <group>` heading the task lives under. |
| (no equivalent) | `brief: str \| None` | One-line description. |

Iteration variable rewrites in `_spawn_core.py`: every `t.slug` → `t["slug"]`, `t.title` → `t["title"]`, `t.phase` → `t["status"]`, `t.has_proposal` → `t["has_proposal"]`, `t.heading_line_no` → delete the line. Type hints `list[_tasks_md.Task]` → `list[dict]`.

### Modules involved and their current V2 contamination

**Shipping (`plugins/mill/scripts/`):**

- `millpy-spawn.py` lines 44, 46, 49, 68, 128, 130, 178 — V2 imports + `_wiki.sync_pull` + `_tasks_md.parse` + `wiki/config.yaml` fallback.
- `_spawn_core.py` lines 70 (`import _sidebar`), 73–74 (`import _tasks_md`, `import _wiki`), 153, 232, 257–268 (the `_task_to_dict` helper), 271, 336–337, 405, 477–479, 504, 509–513, 515 (`_sidebar.regenerate`), 530, 534, 545, 642, 654, 656, 658 (`_sidebar.regenerate`), 659 — V2 imports + `_wiki.wiki_lock` + `_tasks_md.parse/remove_entry/append_entry/claim` + `_wiki.write_commit_push` + `_sidebar.regenerate` + Task-attribute access + `[s]` fast-paths.
- `millpy-inspect.py` lines 20, 45, 54 — V2 import + `resolve_wiki_path` + `_tasks_md.parse`.
- `millpy-status.py` lines 20, 24, 32 — same pattern.
- `millpy-terminal.py` lines 23, 55, 59 — same pattern.
- `millpy-vscode.py` lines 31, 176, 180 — same pattern.
- `millpy-wikipush.py` lines 32, 102, 104, 111, 113 — `import _wiki`, `_wiki.wiki_lock`, `_wiki.LockBusy`.
- `_paths.py` lines 125, 140, 318–319 (rename `_wiki` local), 407 — docstrings/error text + clashing local var name.
- `_junction.py:301` — docstring.
- `_worktree.py:207` — docstring.

**Tests (`plugins/mill/unit_tests/`):**

- V2 imports/calls (confirmed by grep): `_test_helpers.py`, `test-fold.py`, `test-millpy-spawn.py` (in a small `_tasks_md` fallback block at lines 967–970), `test-spawn-core.py`. (`test-millpy-claim.py` was previously listed here in the handoff but its issue is the batch-A daemon timeout, not V2 references.)
- V2 `Task(...)` fixture builders: **none found in current state** (`grep -rn 'Task(slug=' plugins/mill/unit_tests/` returns zero). Card 38's bulk may already be done.
- V2 `mock.patch("...")` strings: **none found in current state** (`grep` of `mock\.patch.*['\"]_(tasks_md|wiki|sidebar)` returns zero). Card 37's bulk may already be done.
- Other test files currently failing under PYTHONPATH-isolated verify — investigate per-file: `test-cleanup.py`, `test-marker.py`, `test-millpy-color.py` (chain-failure from `_spawn_core.py` import), `test-millpy-terminal.py`, `test-millpy-vscode.py`, `test-review-cli.py`, `test-review-code-flow.py`, `test-review-common.py`, `test-review-discussion-flow.py`, `test-review-plan-flow.py`, `test-setup-hub-links.py`, `test-wiki-noop-commit.py`. Most of these go green automatically once batch B ships (chain-failures from broken imports); the remainder are batch-C/D work. The plan should not assume causation — verify after each batch.

### Daemon startup mechanics (for batch A diagnosis)

`wiki._client._ensure_daemon` (lines 362–421) checks for `<wiki_path>/.wiki-daemon.json`, validates `protocol_version`, attempts a socket connect to the recorded `host:port`. On miss, calls `_spawn_server` (lines 424+) which spawns `python -m wiki._server <wiki_path>` via Windows `cmd /c start "" /B /MIN` with `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB` flags. The child's stderr is silently dropped. After `_spawn_server` returns, the parent polls `state_file.exists() + socket.create_connection` until `SPAWN_TIMEOUT` (10 s) expires. The 10 s deadline is real wall-clock; tests that hit this take 10 s each.

The diagnostic card should:

1. Modify `_spawn_server` to also write child stderr to `<wiki_path>/.wiki-daemon.log` (or capture via a pipe), behind an env var (e.g. `MILL_WIKI_DAEMON_DEBUG=1`) to avoid changing production behaviour.
2. Reproduce the failure in a controlled test (e.g. `python -c "from wiki._client import list_tasks_brief; list_tasks_brief(Path(...))"` against a freshly-created wiki fixture).
3. Read `.wiki-daemon.log` for the real error.
4. File the root cause (likely candidates: TinyDB lock contention, import failure under `creationflags`, port-bind race when fixtures cycle wikis quickly).

The fix card(s) follow from what's found. Revert the debug instrumentation in the final fix card so production output stays unchanged.

### Verify command shape

The mill-config and plan templates already enforce `PYTHONPATH= ` prefix on every `verify:` command (commit `7e10ddb`, validator check `verify-not-isolated`). Plan-batch frontmatter `verify:` values should look like:

```yaml
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-<file>.py
```

For batch-wide smoke verifies:

```yaml
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
```

### Branch base and commit-graph state

- Current branch: `hanf/wiki-v3-batch3-finish` off `hanf/wiki-v3-adoption`.
- Commits on this branch beyond parent: 1 (`715327a spawn: init status for wiki-v3-batch3-finish`).
- Commits on `hanf/wiki-v3-adoption` beyond `main`: 81 — includes 31 batch-3-WIP commits that must be preserved.
- Squash-merge to `hanf/wiki-v3-adoption` at end. The squashed commit absorbs all batch-A through batch-D work into one revision on the parent branch.

## Constraints

- **No PowerShell tool calls.** Use the Bash tool for all shell operations (per CLAUDE.md). PowerShell 7 not installed; PowerShell tool fails.
- **`PYTHONPATH=`-prefix on all verify commands.** Enforced by validator `verify-not-isolated`. Without it, tests load a Frankenstein V2-cache + V3-worktree mix.
- **Cache-form for operational mill scripts.** `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py"`. Tests use `uv run --project plugins/mill`.
- **No `cd .wiki`.** All wiki mutations go through `git -C <wiki_path>` or `_wiki.*` helpers… wait — `_wiki.*` is being deleted in this task. The successor pattern is `git -C <wiki_path>` directly or `wiki._sync.commit_push(wiki_path, files, message)`. SKILL files and code that still document `_wiki.write_commit_push` are the exact card-29 surface fixes.
- **ASCII-only `print()`/`_log()` output.** Windows cp1252 stdout crashes on `—`, `→`, etc.
- **No `[s]` phase code paths.** V3 doesn't recognise the spawn-ready phase. Card 26 deletes them.
- **Junctions stay live during the task.** Don't `rm -rf` the worktree; `_worktree.remove_safe` is the only safe path. (This task doesn't intentionally remove worktrees, but mill-finalize might.)
- **Implementer model: sonnet** (plan frontmatter).
- **Per-batch effort ceiling: 4 units** (S=1, M=2, L=4).
- **Stuck policy: pause for human input** (plan frontmatter, mill-go honours it).
- **End state: zero failing tests under `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`.** Any failure that can't be fixed in-scope gets a follow-up GitHub issue + a `pytest.skip("see #NNN")` mark with the issue link in the test file.

## Testing

**Batch A — daemon-bug diagnosis + fix.** TDD candidate: a small isolated test under `test-wiki-daemon.py` (already exists) or new `test-wiki-daemon-startup.py` that creates a fresh wiki fixture, calls `wiki.health_check(wiki_path)`, and asserts the daemon comes up within 5 s. This test should fail today (baseline) and pass after the fix. Diagnostic card's success criterion is producing a concrete failure message in `.wiki-daemon.log`; the fix-card's success criterion is the new isolated test passing AND `test-millpy-claim.py` going from 11/12 fail → 0 fail.

**Batch B — shipping-code V2 elimination.** Per-card verify runs the test file most directly exercising the changed shipping script:

- Card 25 (`millpy-spawn.py`): `test-millpy-spawn.py` (currently has V2 fixtures; the test sweep in batch C addresses those, so card 25's verify is the import-only smoke `python -c "import millpy_spawn"` plus the `_spawn_core` chain test).
- Card 26 (`_spawn_core.py` finish): `test-spawn-core.py` (currently green for the parts of `_spawn_core` already ported; this card's verify includes the `_task_to_dict` deletion and the remaining attribute-access conversions).
- Card 28 (small CLIs): `test-millpy-terminal.py`, `test-millpy-vscode.py`, and existence-smoke (`python -c "import millpy_inspect; import millpy_status; import millpy_terminal; import millpy_vscode; import millpy_wikipush"`).
- Card 29 (surface fixes): no behavioural test; verify is the docstring grep `grep -r "_wiki\.write_commit_push" plugins/mill/scripts/_paths.py plugins/mill/scripts/_junction.py plugins/mill/scripts/_worktree.py` returning zero matches.

End-of-batch-B verify: `run-all.py` smoke. Expected: the chain-failure cluster (`test-millpy-color.py` etc., which currently fail with `ModuleNotFoundError: _sidebar`) goes green automatically. Any test still failing on a V2 reference is a Batch C target.

**Batch C — test sweep passes 1+2.** Per-card verify runs the individual test file. Each card's success criterion: the file's test count goes from `N failing` → `0 failing` AND no other test starts failing. The noop-commit fixture-fix card's verify runs `test-wiki-noop-commit.py` to green.

**Batch D — test sweep pass 3 + final smoke.** Per-card verify per file (same as C). Final card runs `run-all.py`, asserts zero failures, and deletes `_mill/handoff.md` in the same commit.

Key TDD scenarios (the plan should articulate, not assume the implementer will infer):

- Daemon startup: cold-start (no state file), warm-restart (stale state file), version mismatch (protocol-version mismatch triggers `_kill_daemon`).
- `_spawn_core.multi_select_groom_then_claim` after `wiki.merge_tasks` adoption: source slugs disappear from Home.md, merged slug is `[active]`, atomic (no partial state on push failure).
- `_spawn_core.claim_in_wiki`: V2 used `wiki_lock` + read-modify-write; V3 single `wiki.set_phase(wiki_path, slug, "active")` call. Test that concurrent claims raise `WikiConflictError` (or whatever V3 returns) rather than the old `LockBusy`.
- Fixture pattern: tests that built text Home.md with `_tasks_md.append_entry(...)` switch to `wiki._client.upsert_tasks_batch(wiki_path, [{"slug": ..., "title": ..., "group": ..., "status": ...}, ...])`. The first test rewritten in card-36 establishes the pattern; subsequent rewrites follow it.

**Out of testing scope:** Integration tests under `plugins/mill/integration_tests/`. They invoke real git and real `claude`; not part of `run-all.py`. If they reference V2 they should be cleaned but are out of this task's verify gate. Spot-check during card 36/37 if a `grep` finds V2 references; otherwise defer to a follow-up.

## Q&A log

- **Q:** Implementation order — daemon, shipping, then test sweep? **A:** Yes, daemon-bug first; clarified that "shipping code" = production scripts under `plugins/mill/scripts/` (not test code).
- **Q:** Batch-size constraint — hard card cap or token estimate? **A:** Effort-weighted ceiling (S/M/L per card; ≤ 4 units per batch); user emphasised #371 is really about token budget, not raw count.
- **Q:** Test-sweep granularity per card? **A:** One card per test file, one commit per file (decided in this session given user's "you fix this").
- **Q:** PR strategy? **A:** Squash-merge to `hanf/wiki-v3-adoption`, defer `→ main` PR.
- **Q:** Daemon investigation depth? **A:** Root-cause it with stderr capture from the detached child; no quick hacks.
- **Q:** Implementer model? **A:** Sonnet for all batches.
- **Q:** Out-of-scope failures policy? **A:** Fix in-scope if reasonably attributable to V3 port; follow-up issue + `pytest.skip` for orthogonal bugs.
- **Q:** Should `test-wiki-noop-commit`'s push-destination failure be addressed? **A:** Yes — fix the test fixture (add a bare-clone `origin`); production `commit_push` is correct.
- **Q:** Per-batch verify required? **A:** Yes, every batch's frontmatter has a non-null `PYTHONPATH= ...` verify.
- **Q:** End-of-task verify criterion? **A:** Zero failing tests.
- **Q:** `[s]` (spawn-ready) phase fast-paths in `_spawn_core`? **A:** Delete them — V3 has no `[s]` phase.
- **Q:** `heading_line_no` field in V3? **A:** Drop everywhere; error messages adapt to slug-only.
- **Q:** `_task_to_dict` helper from commit `a1f7aac`? **A:** Delete in card 26's final step; no V2 Task objects survive after card 25/26 land.
- **Q:** Fate of `_mill/handoff.md`? **A:** Delete in the final batch-D card.
- **Q:** Stuck-handling policy? **A:** Pause for human input (`pipeline.autonomous_mode: false` in plan frontmatter).
- **Q:** Overarching scope framing? **A:** This task **eliminates wiki V2** from the mill codebase — not "ports" V2 callers to V3. End state has zero V2 references anywhere (scripts, tests, docstrings, error messages, fixture helpers, dead semantics).
- **Q (review r1 gap-fix):** Card 26's enumerated removals omitted `_sidebar`. Was that an oversight? **A:** Yes — `_spawn_core.py` line 70 has `import _sidebar` and lines 515/658 call `_sidebar.regenerate(wiki_path)`. Card 26's scope now includes the `_sidebar` import deletion plus dropping (not replacing) both `_sidebar.regenerate` call sites; V3's daemon handles sidebar internally. Without this, the post-card-26 `import millpy_spawn` smoke would still raise `ModuleNotFoundError: _sidebar`.
- **Q (review r1 note-fix):** Cards 37 and 38's listed test files appear stale — current grep finds zero matches for V2 `mock.patch` strings and zero V2 `Task(slug=` builders. **A:** Confirmed via fresh grep. Cards 37 and 38 may be largely empty in practice — the test-port commits on this branch (`23eabc6`, `8d3b24b`, `94ef5e2`, `7637f08`, `0c5d1fe`) appear to have already done this work. The discussion now flags this: the planner must verify against `_mill/plan/03-v2-deletion-and-port.md` on parent `hanf/wiki-v3-adoption` (authoritative source) AND a fresh grep at plan time. Whatever residual work remains becomes the actual card-37/38 scope; if both come back clean, those cards fold into the batch-C verify-smoke with a one-line "found empty" note.
- **Q (review r2 gap-fix):** The `merge_tasks` API signature in the Technical-context table was wrong (table said `merge_tasks(wiki_path, source_slugs, merged_slug, merged_fields) -> None`; actual signature is keyword-only `merge_tasks(wiki_path, *, remove_slugs, upsert, set_phase=None) -> dict`). **A:** Fixed. Cross-checked every other row in the table while in there: `set_phase`/`remove_task`/`get_task`/`upsert_task` all had wrong param names (`slug` vs `id_or_slug`) and `get_task` was missing the `dict | None` return type. All rows now correct, each tagged with the verifying line range in `_client.py`. The planner can trust the table for card-26 code generation.
