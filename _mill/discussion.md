# Discussion: status.md: rename parent to parent_branch, add parent_thread

```yaml
task: 'status.md: rename parent to parent_branch, add parent_thread'
slug: status-parent-fields
status: discussing
parent_branch: main
```

## Problem

`millpy-spawn` seeds every task's `_mill/status.md` with `parent: main`.
The value is a branch name, but the key does not say so, and a second kind of parent is coming: the session (thread) that spawned the task.
The follow-up task `parent-thread-escalation` needs that session name recorded so a worker can later escalate to its orchestrator.

Two changes, nothing more:

1. Rename the status.md key `parent:` to `parent_branch:`, keeping the legacy `parent:` readable.
2. Add an optional `parent_thread:` key, written by `millpy-spawn --parent <name>`.

Why now: the dependency `session-name-short-prefix` has landed (commit `c1acaa03`), so session names like `mh:orch` exist to record.

## Scope

**In:**

- `plugins/mill/scripts/_status.py`: template-driven `parent_branch:` in `render_initial`, new optional `parent_thread` argument, `read_parent_branch` legacy fallback, new `set_parent_branch` writer, insertion anchor in `set_module_verify_baseline` / `set_module_verify_baseline_signatures`.
- `plugins/mill/scripts/_parent_branch.py`: `_parse_parent_from_yaml_text` reads `parent_branch:` with `parent:` fallback; docstrings and error messages name `parent_branch:`.
- `plugins/mill/scripts/_spawn_core.py`: `write_initial_status` gains `parent_thread: str | None = None` and forwards it.
- `plugins/mill/scripts/millpy-spawn.py`: new `--parent <name>` option, forwarded as `parent_thread`.
- Templates: `status-discussing.md`, `discussion.md`, `plan-overview.md` rename their yaml `parent:` row to `parent_branch:`.
  `implementer-brief.md` needs no change (it uses the `<PARENT_BRANCH>` token, not the key) — verify only.
- Skills whose prose names the `parent:` row or calls `_status.update_field(status_path, "parent", ...)`: `mill-merge`, `mill-merge-in`, `mill-finalize`, `mill-start`, `mill-go-base/SKILL.md`, `mill-go-base/handoff.md`, and `mill-spawn` (documents `--parent`).
  `mill-resume` was listed in the proposal but only mentions "parent" in an unrelated sense (the parent worktree's wiki clone) — no edit.
- Unit and integration tests that build or assert status.md content (full list under Technical context).

**Out:**

- Any caller passing `--parent` (mill-pool, orchestrator skills, `orch-review`).
  Wiring callers and reading `parent_thread` belong to `parent-thread-escalation`.
- `millpy-claim.py` (in-place claim) gets no `--parent` option; it keeps calling `write_initial_status` without `parent_thread`.
- A reader function for `parent_thread` — no consumer exists yet (YAGNI); tests use `_status.read()`.
- A migration script rewriting existing status.md files, and any removal date for the legacy fallback.
- Historical docs (`doc/turn-reduction-audit.md`) and archived review files.
- The `<PARENT_BRANCH>` template token name and the Python variable/param name `parent_branch` — already correct.

## Decisions

### Legacy `parent:` fallback is permanent

- Decision: every reader accepts `parent_branch:` first, then `parent:`.
  The fallback is never removed.
- Rationale: `_parent_branch.resolve_dead_parent` reads ancestors' status.md from `archive/<slug>` tags via `git show`; those archived files keep `parent:` forever.
  In-flight worktrees (including this task's own `_mill/status.md`, which has `parent: main`) must still merge.
- Rejected: remove after a migration — archive tags cannot be migrated, so the fallback would be needed anyway.

### Precedence when both keys exist

- Decision: `parent_branch:` wins; `parent:` is consulted only when `parent_branch:` is absent or empty.
- Rationale: a file holding both can only arise from a hand edit or a partial rewrite; the new key is authoritative.
- Rejected: error on both — needless halt in merge paths.

### Writing the parent branch: new `_status.set_parent_branch`

- Decision: add `_status.set_parent_branch(status_path, value)`.
  If a `parent_branch:` row exists it is rewritten in place;
  else if a legacy `parent:` row exists it is replaced in place by `parent_branch: <value>` (migrate-on-write);
  else `ValueError` (same strictness as `update_field`).
  Value goes through `quote_scalar`.
  Every skill site that today calls `_status.update_field(status_path, "parent", resolved_branch)` switches to `_status.set_parent_branch(status_path, resolved_branch)`.
- Rationale: `update_field` requires the key to exist; after the rename, skills calling `update_field(..., "parent_branch", ...)` would raise on legacy files, and calling it with `"parent"` would raise on new files.
  One helper hides the dual-key logic from four skill sites.
- Rejected: have skills call `update_field` with a key chosen by reading the file first — duplicates logic in prose at every site.
  Rejected: make `update_field` alias keys — a generic helper should not know about one field's history.

### Insertion anchor for baseline rows

- Decision: `set_module_verify_baseline` and `set_module_verify_baseline_signatures` insert after the `parent_branch:` row, falling back to the `parent:` row; `ValueError` only when neither exists.
  Match with anchored regexes (`^parent_branch:\s*` / `^parent:\s*`) so neither matches the other or `parent_thread:`.
- Rationale: these functions run on in-flight legacy files and new files alike.

### `parent_thread` rendering

- Decision: `render_initial` and `_spawn_core.write_initial_status` take a keyword argument `parent_thread: str | None = None`.
  When it is a non-empty string (after strip), `render_initial` inserts `parent_thread: <quote_scalar(value)>` on the line immediately after `parent_branch:` in the rendered yaml block.
  When `None` or empty, no row is written.
  The template `status-discussing.md` gets no `<PARENT_THREAD>` token (it cannot express an optional line, and `render_initial` rejects unresolved tokens); its header comment documents that `render_initial` inserts the optional row.
- Rationale: brief requires the field be absent when `--parent` is omitted.
  `quote_scalar` handles the `:` in names like `mh:orch`.
- Rejected: always write `parent_thread: null` — contradicts the brief.

### `millpy-spawn --parent`

- Decision: `--parent NAME` (`default=None`, help text: name of the session spawning this task, recorded as status.md `parent_thread:`).
  Value passed through unchanged except for `strip()`; empty string equals omitted.
  No format validation — session names are free-form strings produced by `_vscode_tasks` / config.
  `--dry-run` output mentions the value when given.
- Rationale: scripts cannot read their own session name; the caller supplies it.
- Rejected: validating against `<short_name>:<...>` — couples spawn to session-naming config for no gain.

### Skill prose

- Decision: skills refer to "`status.md`'s `parent_branch:` row" where they previously said "`parent:` row".
  mill-merge's missing-row BLOCKED message and commit text say `parent_branch:`.
  `mill-spawn/SKILL.md` documents `--parent <name>` in its Run line and one sentence on `parent_thread:`.
  `mill-start/SKILL.md` Phase: Active says "`parent_branch:` (or legacy `parent:`)"; Phase: Discussion File's `<PARENT_BRANCH>` substitution reads the branch via `_status.read_parent_branch`.
- Rationale: prose must match the key the scripts write, and legacy mentions only where a reader of the skill could meet an old file.

## Technical context

- `_status.render_initial` (`plugins/mill/scripts/_status.py`) reads `plugins/mill/templates/status-discussing.md`, replaces `<TOKEN>`s, and raises on unresolved tokens.
  Insert the optional `parent_thread` row after substitution by locating the `parent_branch:` line.
- `_status.read_parent_branch` uses `read_full(...)["yaml"].get("parent")` — change to `get("parent_branch")` then `get("parent")`, same None-on-failure contract.
  Consumer: `millpy-cleanup.py` (~line 484).
- `_parent_branch._parse_parent_from_yaml_text` hand-parses with `line.strip().startswith("parent:")`.
  `parent_branch:` and `parent_thread:` do not start with `parent:`, so the existing check is safe, but the rewrite should track both values separately and return `parent_branch` value or else `parent` value.
  The `expected_slug` guard is unchanged.
  Used by `_read_parent_from_status` (→ `resolve`) and `resolve_dead_parent` (archive-tag `git show` content — the reason the fallback is permanent).
  Module docstring, `resolve` docstring and `ParentBranchError` messages ("No parent: in ...", "set status.md's parent: row") become `parent_branch:`.
- `_status.update_field(status_path, "parent", ...)` call sites to replace with `set_parent_branch`:
  `plugins/mill/skills/mill-merge/SKILL.md` (~line 127, python snippet), `plugins/mill/skills/mill-merge-in/SKILL.md` (~lines 17, 31), `plugins/mill/skills/mill-go-base/SKILL.md` (~line 692), `plugins/mill/skills/mill-go-base/handoff.md` (~line 58).
  Other prose mentions of the `parent:` row: `mill-merge/SKILL.md` (~lines 77, 117, 137), `mill-merge-in/SKILL.md` (~line 20), `mill-finalize/SKILL.md` (~line 46), `mill-start/SKILL.md` (~line 153).
  Lines in those files that use "parent:" in ordinary English ("undo ... on the parent:", "treat child and parent as branches") are not the key — leave them.
- `_spawn_core.write_initial_status` callers: `millpy-spawn.py` (~line 298) and `millpy-claim.py` (~line 275, unchanged).
- `quote_scalar` lives in `_yaml_writer`, already imported by `_status`.
- The `_status.py` module docstring's public-API list gains `set_parent_branch` and the updated `render_initial` signature.
- Tests referencing the `parent` key (from grep of `"parent"`, `'parent'`, `parent:`):
  unit — `test-status.py`, `test-parent-branch.py`, `test-spawn-core.py`, `test-cleanup.py`, `test-abandon.py`, `test-millpy-implement.py`, `test-millpy-fix.py`, `test-millpy-merge-in-subagent.py`, `test-agent-mode-dispatch.py`, `test-cleanliness.py`, `test-plan-validate.py`, `test-millpy-spawn.py`;
  integration — `test-spawn.py`, `test-merge.py`, `test-plan-assets.py`, `test-go-assets.py`, `test-baseline-waiver.py`, `test-agent-mode-commit-target.py`, `test-status.py`, `test-abandon.py`, `test-inspect.py`.
  mill-plan must re-grep rather than trust this list; many hits are fixtures that only need to be parseable and keep working unchanged thanks to the fallback.
- Fixtures that assert the rendered output of `render_initial` / spawn (e.g. `integration_tests/test-spawn.py`'s `"parent: main" in status_text`, `test-plan-assets.py`'s `"parent: main" in rendered`) must change to `parent_branch:`.
  Fixtures that hand-write status.md for other tests may stay on `parent:` (legacy path) or move; prefer moving them to `parent_branch:` except where a test exercises the legacy fallback.

## Constraints

- `print()` / log output ASCII only (CLAUDE.md).
- Verify commands in the plan start with `PYTHONPATH=` (CLAUDE.md "Verify command shape").
- Every status.md yaml field stays one physical line; readers assume it.
- No behaviour change beyond the two fields: no skill reads `parent_thread` and no caller passes `--parent`.

## Testing

- TDD candidates: `_status.set_parent_branch`, `_status.read_parent_branch`, `_parent_branch._parse_parent_from_yaml_text`, `render_initial` with/without `parent_thread`.
- `test-status.py`:
  `render_initial` output has `parent_branch:` and no bare `parent:`;
  with `parent_thread="mh:orch"` the row appears right after `parent_branch:` and round-trips through `_status.read()` as `"mh:orch"`;
  with `None` and `""` no `parent_thread` row;
  `read_parent_branch` on new key, legacy key, both keys (new wins), neither (None);
  `set_parent_branch` rewrites new key, migrates legacy key in place (no `parent:` row left, order preserved), raises when neither;
  `set_module_verify_baseline(_signatures)` insert after `parent_branch:` and after legacy `parent:`.
- `test-parent-branch.py`: `resolve` and `resolve_dead_parent` with archived status.md content using `parent_branch:` and legacy `parent:`; `expected_slug` mismatch still yields None for both keys; `parent_thread:` row never mistaken for the branch.
- `test-spawn-core.py`: `write_initial_status` forwards `parent_thread`; default omits the row.
- `test-millpy-spawn.py`: `--parent mh:orch` reaches `write_initial_status` as `parent_thread`; omitted flag passes `None`.
- `integration_tests/test-spawn.py`: spawned status.md contains `parent_branch: main`; with `--parent`, contains `parent_thread:`.
- Existing merge/cleanup/merge-in tests keep passing; at least one merge path test keeps a legacy `parent:` fixture to prove in-flight worktrees still merge.

## Q&A log

- **Q:** Is the legacy `parent:` fallback permanent or removed after a migration? **A:** [auto-pick] Permanent. **Why:** `resolve_dead_parent` reads archived status.md from `archive/<slug>` tags, which cannot be migrated.
- **Q:** How do skills rebind the parent branch when the file may carry either key? **A:** [auto-pick] New `_status.set_parent_branch` that rewrites `parent_branch:` or migrates a legacy `parent:` row in place. **Why:** `update_field` is strict on key presence; one helper replaces dual-key prose at four sites.
- **Q:** Which key wins when both are present? **A:** [auto-pick] `parent_branch:`. **Why:** new key is authoritative; halting would block merges for no benefit.
- **Q:** How is the optional `parent_thread` row rendered? **A:** [auto-pick] `render_initial(..., parent_thread=None)` inserts a quoted row after `parent_branch:` when non-empty; template has no token. **Why:** templates cannot express an optional line and unresolved tokens raise.
- **Q:** Does `millpy-claim` also get `--parent`? **A:** [auto-pick] No. **Why:** brief scopes the flag to `millpy-spawn`; in-place claim has no orchestrator dispatch path today.
- **Q:** Should any caller (mill-pool, orch skills) start passing `--parent` now? **A:** [auto-pick] No; only document the flag in `mill-spawn/SKILL.md`. **Why:** brief says no behaviour change; wiring belongs to `parent-thread-escalation`.
- **Q:** Rename `parent:` in the `discussion.md` and `plan-overview.md` template yaml too? **A:** [auto-pick] Yes, both. **Why:** same value, same meaning; keeps one key name across generated files. No code parses these rows.
- **Q:** Validate the `--parent` value format? **A:** [auto-pick] No; strip only, empty equals omitted. **Why:** session names are config-driven free-form strings.
