# Discussion: Fix mill-ghissues-to-tasks to refuse fold-ins into done and deferred tasks

```yaml
task: Fix mill-ghissues-to-tasks to refuse fold-ins into done and deferred tasks
slug: ghissues-skill-fold-guard
status: discussing
parent: main
```

## Problem

Folding a GitHub issue into a wiki task closes the source issue on GitHub with a
pointer comment (`Folded into wiki task: <slug>`). The fold guard today refuses
only the three "plan frozen" phases -- `LOCKED_FOLD_PHASES = ("active",
"ready-to-merge", "pr-pending")`. It does **not** refuse `done`, `abandoned`,
`blocked`, or `deferred` targets. So a triage run can fold an open issue into a
task that will never be worked (done/abandoned) or is postponed (deferred),
close the issue, and silently lose the work. This was self-identified during the
2026-06-15 triage session.

The fix flips the policy from a denylist of frozen phases to an **allowlist**:
an issue may be folded **only into an unclaimed task**. Once a task is claimed
(spawned), or has reached any terminal/blocked/deferred state, folding is
refused -- the issue stays open so it is not forgotten.

## Scope

**In:**
- `millpy-fold.py` -- replace the `LOCKED_FOLD_PHASES` guard with the unclaimed-only allowlist check, AND rewrite the module docstring to match. The docstring lines ~10-17 document the operation order ("phase-guard") and hardcode `LOCKED_FOLD_PHASES = ("active", "ready-to-merge", "pr-pending")` with the "plan frozen" rationale; these must be rewritten to the allowlist rule. The removed constant name must not survive anywhere in the module (docstring or code). The close-comment-string docstring block (lines ~19-21) is unaffected.
- `mill-ghissues-to-tasks/SKILL.md` -- update the fold-target guard in Step 3 (grouping), Step 5 (re-check), and the Rules section to the allowlist rule.
- `mill-fold/SKILL.md` -- update the guard documentation (description frontmatter, "Locked-phase guard" section, error-handling table, example (c)) to the allowlist rule.
- `wiki/__init__.py` -- remove the `LOCKED_FOLD_PHASES` constant (no longer the guard; policy moves into fold code).
- `test-fold.py` -- invert the two tests that currently assert done/abandoned accept folds; add the new refusal/acceptance cases; drop the `LOCKED_FOLD_PHASES`-value assertion and its import.
- `CLAUDE.md` (hub root) -- update the "No fold into ..." constraint line to state the allowlist rule.

**Out:**
- No `--force` / override flag. There is no escape hatch today and none is added.
- The fold **output format** (the `- Sources: #N -- <title>` / `- Folded in: <text>` bullet, the close-comment strings) is unchanged.
- The wiki daemon, parser, renderer, and status vocabulary are unchanged -- this task only reads `status`/`deferred`, it does not add or alter any status value.
- `mill-cleanup`'s separate `_LIVE_PHASES` set is unrelated and untouched.
- No new shared helper module and no policy logic added to the `wiki/` package (the predicate is a one-liner inlined at each call site).

## Decisions

### policy-model

- Decision: Fold is allowed **only into unclaimed tasks**. Concretely: a target is foldable iff `status is None AND not deferred`. Every other state (`active`, `ready-to-merge`, `pr-pending`, `done`, `blocked`, `abandoned`, or any `deferred` task) is refused.
- Rationale: An allowlist is default-deny -- any status added to the vocabulary later is auto-refused, which is the safe direction for a guard whose failure mode is silently closing a GitHub issue. It also matches the operator's mental model exactly ("only unclaimed tasks can be folded into") and subsumes the old `LOCKED_FOLD_PHASES` denylist plus the requested done/deferred additions in one rule.
- Rejected: Extending the `LOCKED_FOLD_PHASES` denylist to add `done`/`abandoned` (and a separate `deferred` branch). Rejected because a denylist must be re-audited every time a status is added, and the policy semantics ("plan frozen") no longer fit terminal states.

### unclaimed-means-status-none

- Decision: "Unclaimed" is defined as `status is None`. No separate spawn-ready check is possible or needed.
- Rationale: `wiki/_parse.py` (line ~62) parses the `[s]` (spawn-ready) marker to `status = None`, identical to a no-marker backlog task. At the storage/`get_task`/`list_tasks_brief` layer there is no distinct "s" value -- backlog and spawn-ready are indistinguishable and both read as `None`. A claimed task always carries a concrete status (`active` onward). So `status is None` is exactly "not yet claimed".
- Rejected: Trying to distinguish spawn-ready from backlog -- impossible at the data layer and not wanted (both are pre-claim and safe to fold into).

### deferred-backlog-refused

- Decision: A backlog task (`status is None`) that is also `deferred = True` is **refused**. The full predicate is `status is None AND not deferred`.
- Rationale: `deferred` is an orthogonal boolean (see `wiki/_render.py` lines 11-17: a task can be `status=None` and `deferred=True`, landing in the `__deferred__` bucket). A deferred task is postponed indefinitely; folding+closing an issue there carries the same forgetting hazard as a done task. The operator explicitly wants deferred refused.
- Rejected: Treating `status is None` alone as sufficient (ignoring `deferred`). Rejected because it would let a deferred backlog task accept folds, contradicting the requirement.

### remove-locked-fold-phases-constant

- Decision: Delete `LOCKED_FOLD_PHASES` from `wiki/__init__.py` and its import + value-assertion from `millpy-fold.py` and `test-fold.py`. The allowlist predicate lives in the fold code, not the wiki package.
- Rationale: With the allowlist, the tuple is dead -- it no longer drives the guard. Keeping a redundant denylist constant invites drift (two sources of truth) and the wiki data layer should not own fold policy (operator's Q2 instinct).
- Rejected: Keeping the constant and layering the allowlist on top -- two overlapping policies, confusing and prone to skew.

### error-message

- Decision: A single, reason-bearing refusal message that names the actual blocking state, e.g. `Cannot fold into '<slug>': task is not unclaimed (status: <status-or-deferred>). Only unclaimed backlog tasks accept fold-ins.` Exit code 1, no Home.md mutation, no GitHub close.
- Rationale: The allowlist makes one uniform message natural; surfacing the actual state (`done`, `active`, `deferred`, etc.) tells the operator why and what to do (route to a new task or skip). Distinct from the old "[active] ... Plan is frozen" wording, which no longer applies to terminal states.
- Rejected: Per-reason bespoke messages (over-engineered for an allowlist); a generic message that hides the blocking state (less actionable).

## Technical context

- **Guard call sites are independent.** `mill-ghissues-to-tasks` does NOT call `millpy-fold.py`; it inlines `_client.get_task` + `_client.upsert_task` with its own status check (SKILL.md Step 5, line ~107: `if task['status'] in {'active', 'ready-to-merge', 'pr-pending'}`). Step 3 (line ~59) describes the same denylist for the grouping decision, and the Rules section (lines ~152) repeats it. Fixing `millpy-fold.py` alone does NOT fix the skill named in the task title -- all of: the script + both SKILL files must change.
- **`millpy-fold.py` guard** is at lines 97-102: `phase = target_task["status"]; if phase in LOCKED_FOLD_PHASES: raise SystemExit(...)`. `target_task` comes from `wiki.list_tasks_brief(wiki_path)` (line 92). The brief dict includes both `status` and `deferred` (verified at runtime; the docstring on `list_tasks_brief` is stale and omits `deferred` but the daemon returns it). `get_task` also returns `deferred`. So the new predicate can read `target_task.get("status")` and `target_task.get("deferred", False)` directly -- no new daemon round-trip. **Use the `.get(...)` form, not subscripting:** `get_task`/`list_tasks_brief` return the raw stored doc, and a doc written without a `deferred` key would lack it (upsert defaults `deferred=False` today, but that is an implicit invariant). The `mill-ghissues-to-tasks` Step-5 inline re-check must therefore use `task.get("status")` and `task.get("deferred", False)`, never subscripting. Note the existing Step-5 snippet (SKILL.md line ~107) currently subscripts `task['status']`; the rewrite must convert that read to `task.get("status")` as well, not only add the new `deferred` read.
- **Status vocabulary** (authoritative: `wiki/_parse.py` line ~40 regex): `s | active | ready-to-merge | pr-pending | done | blocked | abandoned`, plus no-marker. `[s]` -> `None`. `deferred` is a separate boolean field on the task, not a status value.
- **Existing tests that encode the OLD (buggy) contract** (`plugins/mill/unit_tests/test-fold.py`): line 176-184 asserts `LOCKED_FOLD_PHASES == ("active","ready-to-merge","pr-pending")` (remove); line 411-434 "done phase accepts fold" (invert to refused); line 436-459 "abandoned phase accepts fold" (invert to refused). Locked-phase refusal tests (lines 265-352) stay green unchanged -- those phases are still refused under the allowlist, and the tests assert only that `SystemExit` is raised and `post_home == pre_home` (they do NOT inspect message text), so no edit is required for them. The import at line 21 (`from wiki import _client as wiki, LOCKED_FOLD_PHASES, WikiPushError`) must drop `LOCKED_FOLD_PHASES`.
- **Test harness** (`test-fold.py`): in-process wiki via `wiki.use_inprocess(wiki_path)`, tasks seeded by `_setup_tempfile_wiki(home_md, tasks=[...])` passing dicts with `slug/title/brief/status` (add `deferred=True` where needed). `_patch_resolve_paths` swaps `millpy_fold.resolve_git_root`/`resolve_wiki_path`. GH side effects are faked via `_make_fake_fetch_one` / `_make_fake_close_with_comment` injected through `millpy_fold.main(..., _fetch_one=, _close_with_comment=)`. Use `--scope` for guard tests to avoid the GH path entirely (existing pattern).
- **No-mutation invariant:** the guard must run BEFORE any `upsert_task` and before any GH close. The existing tests assert `post_home == pre_home` after a refusal -- keep that invariant for the new refusal cases (and assert no `close_with_comment` call when testing the `--issue` path against a refused target).
- **Run tests with:** `uv run --project plugins/mill plugins/mill/unit_tests/test-fold.py` (unit tests are the documented exception to the cache-invocation rule; they import from the source tree).

## Constraints

- ASCII-only in `print()` / log output (Windows cp1252): use ` -- ` not an em-dash, ` -> ` not an arrow.
- Generated/edited markdown uses fenced ` ```yaml ` for metadata, not `---` frontmatter (except SKILL.md frontmatter, which is `---`).
- Do not run plugin scripts from the source repo for operational use; tests are the only exception (they import the source tree by design).
- `CLAUDE.md` line ~45 currently reads: "No fold into `[active]`/`[ready-to-merge]`/`[pr-pending]` tasks. Phase tuple at `_tasks_md.LOCKED_FOLD_PHASES`." The pointer is doubly stale: the constant lives in `wiki/__init__.py`, not `_tasks_md`, and it is being removed entirely. Replace the line with the allowlist rule and no constant pointer, e.g.: "**Fold only into unclaimed backlog tasks** (`status is None AND not deferred`). Claimed, terminal, blocked, or deferred tasks reject folds -- guard inlined in `millpy-fold.py` and both fold SKILLs." Keep this wording consistent with the error-message decision and the SKILL guard text so all four doc surfaces (CLAUDE.md, the two SKILLs, the script docstring) agree.
- Keep reviewer-facing churn minimal: the fold output format and close-comment strings are byte-identical to today; only the guard predicate, its message, and docs change.

## Testing

TDD candidate: `test-fold.py` is the single test surface. Write the inverted/added cases first, watch them fail against the current guard, then change `millpy-fold.py`.

Cases to cover (all via the `--scope` path unless noted):
- `status=None` (unclaimed backlog) -> fold ACCEPTED, bullet appended, exit 0. (New positive case; the current suite has an "append" round-trip but not a guard-accept assertion keyed on `None`.)
- `status="done"` -> REFUSED, exit 1, Home.md unchanged. (Invert existing line 411 test.)
- `status="abandoned"` -> REFUSED, exit 1, Home.md unchanged. (Invert existing line 436 test.)
- `status="blocked"` -> REFUSED, exit 1, Home.md unchanged. (New -- blocked is claimed, so refused.)
- `status=None, deferred=True` -> REFUSED, exit 1, Home.md unchanged. (New -- the deferred-backlog edge.)
- `status="active" | "ready-to-merge" | "pr-pending"` -> REFUSED. (Existing tests at lines 265-352 already cover these and stay green unchanged -- they assert only `SystemExit` + unchanged Home.md, not message text. Optionally add a deliberate message-text assertion to one case, but it is not required.)
- `--issue` path against a refused target -> no `close_with_comment` call recorded (guard runs before the GH close). (New, uses the fake close capture.)
- Remove the `LOCKED_FOLD_PHASES`-value assertion (lines 176-184) and the constant import.

For the SKILL.md changes there is no automated test (skills are prose); correctness is by review against this discussion. The reviewer should confirm Step 3, Step 5, the Rules section, and the description frontmatter of `mill-ghissues-to-tasks/SKILL.md`, plus the guard section/table/example of `mill-fold/SKILL.md`, all state the allowlist rule consistently and inline no stale `{active, ready-to-merge, pr-pending}` set.

## Q&A log

- **Q:** Which target states should refuse a fold? **A:** Allowlist instead -- fold ONLY into unclaimed tasks. **Why:** Operator: "vi skal ALDRI TILLATE en fold i en aktiv eller done task. Det er kun UNCLAIMED task som kan foldes inn i." Default-deny is safer than enumerating refused states.
- **Q:** What does "unclaimed" mean in stored data? **A:** `status is None`. **Why:** `_parse.py` collapses `[s]`/spawn-ready and no-marker backlog both to `None`; a claimed task always has a concrete status.
- **Q:** A backlog task that is also `deferred=True`? **A:** Refuse it (predicate is `status is None AND not deferred`). **Why:** deferred is postponed; same forgetting hazard as done; operator confirmed refuse.
- **Q:** Keep or remove `LOCKED_FOLD_PHASES`? **A:** Remove it; the allowlist replaces it and fold policy should not live in the `wiki/` package. **Why:** Operator: "Jeg skjonner ikke hvorfor du trenger noe slikt i wikien." Avoids two overlapping policies.
- **Q:** Error-message style? **A:** One reason-bearing message naming the actual blocking state. **Why:** Uniform under an allowlist; surfacing the state is actionable (route to new task or skip).
