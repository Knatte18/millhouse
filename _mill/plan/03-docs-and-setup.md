# Batch: docs-and-setup

```yaml
task: Prefix session names with repo short name; add MH:orch session
batch: docs-and-setup
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: [1, 2]
```

## Batch Scope

Brings the SKILL.md prose in line with batches 1 and 2 and adds mill-setup's explicit `repo.short_name` step.
mill-setup's new step calls `_setup.set_repo_short_name` and `_setup.SHORT_NAME_RE` from batch 1, and its Phase 7b call passes `session_prefix(...)` and `hub=True`.
This batch is last because its `verify:` is the task's full-suite acceptance run (see Batch Tests).

## Cards

### Card 7: mill-setup short_name prompt and hub orch task

- **Context:**
  - `plugins/mill/scripts/_setup.py`
  - `plugins/mill/scripts/_vscode_tasks.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/skills/mill-setup/SKILL.md`:
  - Add a new `### Phase 3.1b — Make repo.short_name explicit` section directly after Phase 3.1 and before Phase 3.2. Content, in the file's existing numbered-step style:
    1. Read `<cwd>/mill-config.yaml` with `yaml.safe_load` and check `(cfg.get('repo') or {}).get('short_name')`. When it is non-empty, print that it is already set and skip the rest of this phase (silent no-op on re-runs).
    2. Otherwise compute `derived = resolve_short_name(cfg, '<repo-name>')` and test it against `_setup.SHORT_NAME_RE`. Show one command (bootstrapper form `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "<VENV_PYTHON>" -c "..."`) that prints `derived` and whether it matches.
    3. Prompt the operator per `mill:conversation`'s numbered-list rule: when `derived` matches, `1) <derived> (Recommended) — derived from the repo name` and `2) Other — type a 2-4 character alphanumeric short name`; when it does not match, no recommended option — ask only for a typed value. Explain in one sentence that the value becomes the lower-cased prefix of every Claude Code session name (`<short>:<phase>` on the hub, `<short>:<slug>:<phase>` in worktrees) and stays verbatim in the VS Code window title.
    4. Validate the answer against `^[A-Za-z0-9]{2,4}$`; re-prompt on failure.
    5. Write with one command calling `_setup.set_repo_short_name(Path(r'<cwd>/mill-config.yaml').resolve(), '<value>')` and printing its return value; when it returns `True`, stage and commit exactly as Phase 3.1's upsert commit does (`_subprocess_util.run` for `git -C <hub_root> add mill-config.yaml` and `git -C <hub_root> commit -m 'chore: set repo.short_name in mill-config.yaml'`).
    State that the helper edits only the `short_name:` line (or inserts a `repo:` block) and preserves every other line and comment.
  - Phase 7b step 1: change the command so the name argument is `_vscode_tasks.session_prefix(resolve_short_name(cfg, '<repo-name>'))` and the call passes `hub=True`; change "Render the six session launch tasks" to say the hub gets the six session launch tasks plus the hub-only `mill: orch` task (session `<short>:orch`, no initial prompt, model/effort from `spawn.sessions.orch`); change "The hub's session names use the short name because no task slug exists there." to say hub session names are `<short>:<phase>`, lower-cased, while worktree sessions are `<short>:<slug>:<phase>`.
  - Phase 7b step 2 (keybindings): add one sentence that the `orch` task has no keybinding (it would be a dead key in every task-worktree window) and is launched via Run Task.
  - Add `_setup` (Phase 3.1b — `set_repo_short_name`, `SHORT_NAME_RE`) to the "Helpers used by this skill" line, merged into the existing `_setup` entry.
  - Add an Idempotency bullet: `repo.short_name` already set -> Phase 3.1b makes no change and does not prompt.
- **Commit:** `docs(mill-setup): prompt for repo.short_name and render hub orch task`

### Card 8: mill-spawn and mill-session-tasks session-name wording

- **Context:**
  - `plugins/mill/scripts/_vscode_tasks.py`
- **Edits:**
  - `plugins/mill/skills/mill-spawn/SKILL.md`
  - `plugins/mill/skills/mill-session-tasks/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/skills/mill-spawn/SKILL.md`, in the description paragraph, change `session names <slug>:<phase>` to `session names <short_name>:<slug>:<phase>, lower-cased`.
  Do not change the frontmatter `description:`.

  In `plugins/mill/skills/mill-session-tasks/SKILL.md`, add after the first body paragraph: session names are `<short_name>:<slug>:<phase>` in a task worktree and `<short_name>:<phase>` on the hub, lower-cased; on the hub the file also gets the hub-only `mill: orch` task; when `repo.short_name` is unset the script warns on stderr and derives the short name from the main worktree's directory name.
  Also add one sentence that existing worktrees keep their old session names until this skill is re-run there.
  Do not change the frontmatter `description:`, so `SKILLS.md` needs no regeneration.
- **Commit:** `docs(skills): document short-name session prefix and hub orch task`

## Batch Tests

This batch edits only SKILL.md prose, so it has no scoped tests of its own.
Its `verify:` is the unbounded `run-all.py` on purpose: the discussion's Testing section makes the full suite this task's acceptance bar, and batches 1 and 2 change shared helpers (`_vscode_tasks`, `_paths`, `_setup`) that other suites import — for example `test-paths.py`, `test-setup-hub-links.py` and `test-millpy-claim.py`, which batch 1 and 2's scoped `verify:` commands deliberately skip.
Running it once here, in the final batch, catches any regression there without paying the full-suite cost on every earlier round.
