# Batch: other-skills

```yaml
task: 56 (A) -- Fix mill-go/start/plan/merge runtime behavioral bugs
batch: other-skills
number: 4
cards: 4
verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Four targeted SKILL.md edits across three skills. Cards 8 and 9 both edit `mill-start/SKILL.md` (in that order to avoid conflicts). Card 8 adds the progress-vs-non-progress check to the auto-mode Discussion Review round-cap logic (#279). Card 9 adds the `_mill/status.md` working-tree safeguard before each `_status.append_phase` call in the Discussion Review loop (#289). Card 10 fixes `mill-merge/SKILL.md` to cache `task:` and `task_description:` fields before Step 4 deletes `_mill/` (#285). Card 11 fixes `mill-merge-in/SKILL.md` to rewrite `${PLUGIN_ROOT}` to the task worktree's local plugin path in the verify loop (#292).

## Cards

### Card 8: mill-start auto-mode -- progress-vs-non-progress round-cap check

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `mill-start/SKILL.md`, locate the `## Auto mode` subsection `**Phase: Discussion Review -- \`--auto\` changes:**`. Specifically, find the block that describes the GAPS_FOUND path for auto-mode (step 5 of the Discussion Review loop), and the condition for blocking after `max_review_rounds`.

  The current blocking condition reads (paraphrased): "If unresolved gaps remain after `max_review_rounds`: call `_status.set_blocked(..., "auto: discussion review gaps unresolved after {N} rounds")`, then commit and push, then halt."

  Replace this condition with the following two-variable, one-time-extension logic. Before the review loop, the mill-start session maintains two variables:
  - `prev_gap_titles: set[str]` initialised to the empty set before the loop begins.
  - `extension_used: bool` initialised to `False` before the loop begins.

  At the end of each GAPS_FOUND round, after applying gap fixes:
  1. Parse the current round's gap titles from the review file (the heading text of each `### [GAP]` finding).
  2. Let `current_gap_titles` = the set of those titles.
  3. If `round >= max_review_rounds` (the cap would normally fire):
     - If `current_gap_titles.isdisjoint(prev_gap_titles)` (no overlap with previous round) AND `not extension_used`: set `extension_used = True`, allow one more round (do NOT block), and continue the loop with `round += 1`.
     - In all other cases at or past the cap (overlap exists, OR `extension_used` is already `True`): call `_status.set_blocked(status_path, f"auto: discussion review gaps unresolved after {N} rounds", timestamp=_timestamp.now_utc_iso())`, commit `_mill/status.md` with message `mill-start: blocked (auto: discussion review gaps unresolved) for {slug}`, push, and halt.
  4. Update `prev_gap_titles = current_gap_titles` at the end of each round regardless of whether the extension fires.

  The extension is one-time-ever: once `extension_used` is `True`, subsequent rounds always apply the cap regardless of title disjointness.

  Insert the two variable initialisations (`prev_gap_titles = set()` and `extension_used = False`) into the prose before the loop description. Insert the three-way check (disjoint + not used → extend; otherwise → block) into the prose at the point where the round-cap fires. The prose style should mirror mill-plan Phase: Plan Review step 5 (Non-progress check).
- **Commit:** `fix(mill-start): add progress-vs-non-progress check before auto-mode round-cap (#279)`

### Card 9: mill-start Discussion Review -- status.md working-tree safeguard

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `mill-start/SKILL.md`, locate every place in the `### Phase: Discussion Review` section where `_status.append_phase(status_path, ...)` is called (both in the interactive path and the auto-mode path). Before EACH such call, insert a working-tree existence check for `status_path`:

  ```
  Before calling `_status.append_phase`, verify `status_path` exists in the working tree:
  `git -C <worktree> status --short -- _mill/status.md`
  If the output contains `D` (deleted from working tree), restore via:
  `git -C <worktree> checkout HEAD -- _mill/status.md`
  Then proceed with `_status.append_phase`.
  ```

  Note: blank output from `git status --short` means the file is present and unchanged (clean) — blank is NOT the deletion signal. Only a line beginning with ` D` (working-tree deleted) or `D ` (staged deletion) triggers a restore.

  This safeguard covers: the `discussed` Handoff append (Phase: Handoff), the `discussion-fix-r{N}` append (step 4b), and any GAPS_FOUND round append (step 5). In auto-mode, the set_blocked path also appends to status — add the safeguard there too.

  The exact prose can be condensed into a single note if the skill is long: "Before any `_status.append_phase` call in this phase, run `git -C <worktree> status --short -- _mill/status.md`; if the output contains `D`, restore with `git -C <worktree> checkout HEAD -- _mill/status.md` before proceeding." Place this note at the top of the `### Phase: Discussion Review` section, before the loop description, so it applies to all appends in the phase without repetition.
- **Commit:** `fix(mill-start): add status.md working-tree safeguard in Discussion Review loop (#289)`

### Card 10: mill-merge Entry -- cache task: fields before cleanup commit

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `mill-merge/SKILL.md`, locate the Entry section (the section that reads status.md for the phase gate, calls `_marker.task_data`, etc.). After reading `active_data` and before any other step, add a note that the implementer must cache two fields from `_mill/status.md` into local variables:

  ```
  After reading status.md for the phase gate (and before any step that could delete it), cache:
  - `cached_task = _status.read_full(status_path)["yaml"].get("task", slug)` — the task title used in Step 5's squash commit message and Step 6's PR title.
  - `cached_task_description = _status.read_full(status_path)["yaml"].get("task_description", cached_task)` — the task description used in Step 6's PR body.

  Use `cached_task` and `cached_task_description` in all subsequent references to "task: field from status.md" and "task_description field from status.md". Step 4's `git rm -r _mill/` deletes status.md before Step 5 runs; reading from a cached variable avoids the read-after-delete failure.
  ```

  In Step 5 (Direct squash), replace the text `"<task: field from status.md>"` (in the commit message) with `"<cached_task>"`. In Step 6 (PR path), replace `"<task: field from status.md>"` (PR title) with `"<cached_task>"` and `"<task_description field from status.md>"` (PR body) with `"<cached_task_description>"`.

  These are the only changes. The step numbering and all other prose remain unchanged.
- **Commit:** `fix(mill-merge): cache task: fields in Entry before cleanup commit deletes status.md (#285)`

### Card 11: mill-merge-in verify -- rewrite ${PLUGIN_ROOT} to task worktree path

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `mill-merge-in/SKILL.md`, locate the `### Verify` section (the section that calls `_plan_dag.iter_batch_verifies(plan_dir)`). Before the loop that runs each verify command, add:

  ```
  Before running each verify command, substitute `${PLUGIN_ROOT}` in the command string with the task worktree's local plugin path:

  ```python
  local_plugin_root = str(git_root / "plugins" / "mill")
  if (git_root / "plugins" / "mill").is_dir():
      verify_cmd = verify_cmd.replace("${PLUGIN_ROOT}", local_plugin_root)
  ```

  This substitution applies to every `(batch_name, verify_cmd)` pair yielded by `iter_batch_verifies`. If `plugins/mill` does not exist in the current git root (non-millhouse repos), the substitution is a no-op (`is_dir()` returns False, replace is skipped). After substitution, run the verify command as before.
  ```

  The substitution must happen AFTER extracting `verify_cmd` from `iter_batch_verifies` and BEFORE passing it to the shell (via the `millpy-merge-in-subagent.py` `--mode verify-fix` call or the direct run). The `local_plugin_root` computation uses `git_root` which is already resolved in the verify section's setup. No other changes to the verify section.
- **Commit:** `fix(mill-merge-in): rewrite \${PLUGIN_ROOT} to task worktree path in verify loop (#292)`

## Batch Tests

The verify command `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` serves as a regression check. The SKILL.md edits have no automated test coverage; correctness is verified by code review.
