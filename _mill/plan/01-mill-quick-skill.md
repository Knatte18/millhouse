# Batch: mill-quick-skill

```yaml
task: 'Add mill-quick: skip-review pipeline for simple tasks'
batch: mill-quick-skill
number: 1
cards: 2
verify: null
depends-on: []
```

## Batch Scope

This batch delivers the entire `mill-quick` feature: one new skill file,
`plugins/mill/skills/mill-quick/SKILL.md`, plus regenerating the repo-root
`SKILLS.md` index so the new skill is listed. There is no other code —
`mill-quick` calls only existing, already-tested helpers (see the
overview's "no new Python script code" Shared Decision). This is one
batch because it is a single indivisible unit: the skill file is one
document describing one linear flow, and the index regeneration is a
trivial mechanical follow-on that only makes sense once the skill file
exists with correct frontmatter.

## Cards

### Card 1: Write `plugins/mill/skills/mill-quick/SKILL.md`

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-cleanup/SKILL.md`
  - `plugins/mill/skills/git-commit/SKILL.md`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_builder_lock.py`
  - `plugins/mill/scripts/millpy-builder-lock.py`
  - `plugins/mill/scripts/_done_gate.py`
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_timestamp.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/skills/mill-quick/SKILL.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  Write the frontmatter exactly as:

  ```yaml
  ---
  name: mill-quick
  description: "single-pass fix+verify+done skill for simple tasks -- invoked immediately after mill-spawn in place of mill-start, with no discussion round, no plan, and no reviewer of any kind"
  ---
  ```

  Follow with an `# mill-quick` H1 and a short intro paragraph paraphrasing
  `_mill/discussion.md`'s `## Problem` and the "In:" bullets of `## Scope`
  — one session reads the task, makes the fix inline, commits, runs
  `pipeline.done_gate`, and marks the task done, with zero discussion/plan/
  review artifacts.

  Write an `## Entry` section implementing the following steps, in this
  exact order. Every check in steps 2-5 is a precondition: if any of them
  fails, halt immediately with the stated message and do not proceed to
  a later step. No file under the worktree may be edited before step 6.

  1. **Resolve paths, config, and slug** — mirror `mill-start`'s own Entry
     step 1 / Path Setup pattern (do not introduce `discussion_path` or
     `reviews_dir` — `mill-quick` writes neither):
     - `git_root = _paths.resolve_git_root()`
     - `wiki_path = _paths.resolve_wiki_path(git_root)`
     - `worktree_root = _paths.resolve_hub_path()`
     - `cfg = _config.load_config(worktree_root, git_root)` (signature:
       `_config.load_config(hub_root: Path, worktree_root: Path) -> dict`;
       use this exact `(hub_root, git_root)` argument shape for consistency
       with the established call pattern used elsewhere in the codebase,
       e.g. `mill-go/SKILL.md`'s "0.55" block)
     - `slug = _marker.slug_from_branch(git_root, wiki_path, cfg)` — on
       `_marker.MarkerError`, halt: "this worktree was not created by
       mill-spawn" (identical wording to `mill-start`'s Entry step 3 halt).
     - `status_path = _paths.resolve_task_path(worktree_root,
       cfg['paths']['status_md'])`

  2. **`done_gate`-null hard precondition** (cheapest check, no wiki
     round-trip — run this first among the precondition checks):
     - `gate_cmd = (cfg.get('pipeline') or {}).get('done_gate')`
     - If `gate_cmd` is falsy (`None` or empty string): halt with
       `"BLOCKED: mill-quick requires pipeline.done_gate to be configured
       in mill-config.yaml before use -- configure a repo-wide test
       command and retry."` Do not touch any file. This is the
       `verify-mechanism` Decision's hard precondition from
       `_mill/discussion.md` — `mill-quick` never proceeds with
       unverified work.

  3. **Entry-phase gate:**
     - `status_data = _status.read(status_path)`
     - If `status_data.get('phase') != 'discussing'`: halt with
       `f"mill-quick only runs immediately after mill-spawn, before
       mill-start. Current phase: {status_data.get('phase')!r}. Run
       /mill-start instead."`
     - If `status_data.get('plan') is not None`: halt with the same
       message shape, substituting a note that `plan:` is already set
       (belt-and-suspenders per the `entry-phase-gate` Decision).

  4. **Wiki task fetch + status precondition.** Use the exact same
     `PYTHONIOENCODING=utf-8`-prefixed invocation shape as `mill-start`'s
     Phase: Select (same reasoning: avoid the cp1252 `UnicodeEncodeError`
     on non-ASCII body/brief content on Windows):

     ```bash
     PYTHONIOENCODING=utf-8 PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
     from pathlib import Path
     from wiki import _client
     import _paths
     wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
     task = _client.get_task(wiki_path, '<slug>')
     if task is None:
         raise SystemExit('[mill-quick] slug not found in wiki -- was this worktree created by mill-spawn?')
     print('STATUS:', task.get('status', ''))
     print('--- BRIEF ---')
     print(task.get('brief', ''))
     print('--- BODY ---')
     print(task.get('body', ''))
     "
     ```

     Unlike `mill-start`, `mill-quick` makes this call only once — there
     is no separate later re-fetch, since the printed `BRIEF`/`BODY`
     output is already in the orchestrating session's context and stays
     valid for the rest of this same linear flow (no long gap like
     `mill-start`'s Select-then-Explore split). If the first output line
     is not `STATUS: active`, halt: `f"task status is {status!r},
     expected 'active'."` (same gate `mill-start` Phase: Select uses).

  5. **Acquire the builder lock** — only after every check in steps 2-4
     has passed:

     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" acquire <slug>
     ```

     On exit 1 (a *different* slug holds a non-stale lock in this
     worktree — see `_builder_lock.py`'s `LockBusy`), surface stderr and
     halt. Document inline, near this step, the `concurrency-guard`
     Decision's corrected scope: this only guards cross-slug contention
     and self-heals across a crash/resume of the *same* slug (idempotent
     re-acquire) — it does not exclude two concurrent `mill-quick`
     invocations against the same slug; that risk is accepted under the
     operator-trust model.

  6. **Write the intermediate phase** (first point any file may be
     touched):
     - `_status.append_phase(status_path, "implementing",
       _timestamp.now_utc_iso())`
     - Commit via raw git (not the `git-commit` skill — this is state
       bookkeeping, not a code change): `git -C <worktree> add
       <status_path> && git -C <worktree> commit -m "mill-quick: start
       implementing {slug}"`. Do **not** push — deferred, mirroring
       `mill-go`'s Builder-role state commits (see Board discipline
       below).

  Write a `## Fix` section (the single-inline-agent phase):
  - State plainly, quoting the `single-inline-agent` Decision's core
    point: the invoking session itself performs the entire fix —
    exploration, editing, committing — with no `Agent`/`Task` tool call
    and no `mill-implementer-*` dispatch. Whatever model the operator
    started this session with is the model that does the work.
  - Explore and edit using whatever tool calls the fix requires (Read,
    Grep, Glob, Edit, Write, Bash) — no fixed algorithm; the task body/
    brief already read in Entry step 4 is the scope.
  - Commit the fix by invoking the `git-commit` skill with a summary of
    the change as the argument — do **not** call raw `git commit`.
    Quote `implementer-brief.md`'s own phrasing for why: the skill runs
    language-appropriate lint on staged files and triggers
    `codeguide-update` when `_codeguide/Overview.md` exists. This commit
    pushes immediately as part of `git-commit`'s own unconditional-push
    contract — state explicitly that this is harmless here because
    nothing downstream (`mill-merge`, `mill-finalize`) acts on a task
    before `phase: done`.

  Write a `## Verify & Complete` section:

  1. **Run the done gate.** `gate_cmd` was already resolved and validated
     non-null in Entry step 2 — reuse that same value here (do not
     re-read config). Invoke:

     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
     import json
     import _paths, _config, _done_gate
     git_root = _paths.resolve_git_root()
     hub_root = _paths.resolve_hub_path()
     cfg = _config.load_config(hub_root, git_root)
     gate_cmd = (cfg.get('pipeline') or {}).get('done_gate')
     result = _done_gate.run_preflight(gate_cmd, git_root)
     print(json.dumps(result))
     "
     ```

     State that this re-derives `gate_cmd` inside the subprocess rather
     than trying to pass Entry's in-session value across a fresh `Bash`
     subprocess boundary — this is safe because Entry step 2 already
     proved it is non-null and it cannot have changed mid-flow. Give
     this Bash-tool call an extended 600000ms (10-minute) timeout, same
     justification as `mill-go`'s "0.55" step: `gate_cmd` is an
     arbitrary, potentially slow project command with no bound on
     runtime.

  2. **Parse the JSON result** and branch on `result["result"]`:
     - `"ok"` → success path (below).
     - `"blocked"` → failure path (below), using `result["reason"]`.
     - `"skipped"` → treat identically to `"blocked"` with reason
       `"done_gate unexpectedly empty at verify time"` — this branch
       should be unreachable given Entry step 2's precondition; document
       it as a defensive-only fallback, not an expected path.

  3. **Success path:**
     - `_status.append_phase(status_path, "done",
       _timestamp.now_utc_iso())`. Commit via raw git (deferred push,
       same as step 6 above): `git -C <worktree> add <status_path> &&
       git -C <worktree> commit -m "mill-quick: done {slug}"`.
     - Flip the wiki phase — required, not optional (mirrors `mill-go`
       Handoff step 2 exactly):

       ```bash
       PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
       from pathlib import Path; import _paths
       from wiki import _client
       wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
       _client.set_phase(wiki_path, '<slug>', 'ready-to-merge')
       "
       ```
     - Release the builder lock:
       ```bash
       PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
       ```
     - Report to the user: `"Task complete via mill-quick. Run
       /mill-finalize to finalize the task (creates a PR or squashes
       directly, depending on config)."` Do **not** auto-invoke
       `/mill-finalize` — state explicitly that `pipeline.auto_merge`/
       `auto_report` auto-continuation (which `mill-go`'s own Handoff
       steps 5-6 perform) is intentionally out of scope here: it is not
       decided anywhere in `_mill/discussion.md`, and `mill-quick`
       matches `mill-start`'s own Handoff precedent of a plain
       informational report with no auto-invocation of the next skill.

  4. **Failure path:**
     - `_status.set_blocked(status_path, f"done gate failed:
       {result['reason']}", timestamp=_timestamp.now_utc_iso())`.
     - Commit via raw git **and push immediately** — the one exception
       to the deferred-push rule, mirroring `mill-start`'s `--auto`-mode
       blocked-halt precedent (a blocked task never reaches
       `mill-merge` and would otherwise be invisible remotely):
       `git -C <worktree> add <status_path> && git -C <worktree> commit
       -m "mill-quick: blocked (done gate failed) for {slug}" && git -C
       <worktree> push`.
     - Release the builder lock (same command as the success path).
     - Halt, reporting to the user:
       `f"BLOCKED: done gate failed for {slug} -- {result['reason']}"`.

  Write a `## Known limitations` section quoting
  `_mill/discussion.md`'s "Known limitation — orphaned `phase:
  implementing`" note near-verbatim: if the invoking session crashes or
  is interrupted between writing `phase: implementing` and reaching the
  done-gate check, the task is left stuck at `implementing` with no
  automatic recovery — no fixer/retry loop exists by design.
  `mill-quick`'s own entry gate cannot resume it (requires `phase:
  discussing`), and `mill-go`'s resume path assumes a `plan.md` file with
  a `## Batches` section, a structure `mill-quick` never creates. The
  escape hatch is manual: `mill-cleanup`/`mill-abandon`, or a manual
  `_status.set_blocked` call.

  Write a `## Board discipline` section (mirroring `mill-go`'s section of
  the same name) summarizing the three commit kinds and their push rules:
  the fix commit (via `git-commit` skill, pushes immediately, harmless);
  the `implementing`/`done` phase commits (raw git, deferred — pushed
  later by `mill-finalize`/`mill-merge`); the `blocked` phase commit (raw
  git, pushed immediately — the one exception). Add a bullet noting the
  wiki phase mutation on the success path —
  `_client.set_phase(wiki_path, slug, "ready-to-merge")` — mirroring
  `mill-go`'s Board discipline bullet for its own Handoff `[ready-to-merge]`
  flip. State that hand-editing `status.md`'s yaml block is banned outside
  the documented `_status.py`
  calls above, matching every other mill skill's Board discipline
  section.

- **Commit:** `feat(mill-quick): add mill-quick skill for skip-review single-pass tasks`

### Card 2: Regenerate `SKILLS.md`

- **Context:**
  - `plugins/mill/skills/mill-skills-index/SKILL.md`
  - `plugins/mill/scripts/millpy-skills-index.py`
  - `plugins/mill/skills/mill-quick/SKILL.md`
- **Edits:**
  - `SKILLS.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Run the scanner exactly as `mill-skills-index/SKILL.md`
  documents: `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON"
  "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-skills-index.py"` from the repo
  root, then confirm the regenerated `SKILLS.md` contains a `mill-quick`
  row sourced from Card 1's frontmatter (`name: mill-quick`,
  `description:` as written in Card 1). Do not hand-edit `SKILLS.md` —
  the frontmatter in `plugins/mill/skills/mill-quick/SKILL.md` is the
  source of truth; this card only runs the regenerator and commits its
  output.
- **Commit:** `chore: regenerate SKILLS.md`

## Batch Tests

`verify: null` — this batch is pure documentation (one new `SKILL.md`
prose file plus a regenerated index file); there is no runnable code to
test. See the overview's "no dedicated unit/integration test file for
mill-quick" Shared Decision for the full justification: every helper
`mill-quick` calls already has existing unit-test coverage
(`test-status.py`, `test-builder-lock.py`, `test-marker.py`,
`test-paths.py`, `test-done-gate.py`), and the orchestration prose itself
has no function boundary to unit-test, matching every other prose-only
mill skill in this codebase.
