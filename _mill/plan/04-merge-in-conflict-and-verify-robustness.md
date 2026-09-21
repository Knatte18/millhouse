# Batch: merge-in-conflict-and-verify-robustness

```yaml
task: mill-go/mill-merge-in orchestration robustness gaps, round 2
batch: merge-in-conflict-and-verify-robustness
number: 4
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-merge-in-subagent.py test-merge-in-subagent.py test-config.py
depends-on: []
```

## Batch Scope

Three fixes to `millpy-merge-in-subagent.py` and its templates/config (`_mill/discussion.md`
Decisions `conflict-brief-rename-chain-intent` #1065, `merge-conflicts-tier-bump-and-roadmap-dedup-check`
#1059/#1047, `verify-subprocess-terminal-geometry` #1068). All three touch this one script and its
sibling template/config files; grouped into one batch. External interface: `mill-config.yaml`'s
`merge:` block gains a new optional `conflicts_model` key that falls back to the existing `model` key
when absent — fully backward-compatible with every hub that has not set it.

## Cards

### Card 8: thread `Moves:` into the conflict brief's task intent

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/templates/merge-in-conflict-brief.md`
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `millpy-merge-in-subagent.py`'s `_collect_task_intent`, widen the plan-file bullet-extraction
  regex from `re.match(r"^-\s*\*\*(Edits|Creates|Deletes):\*\*", line)` to
  `re.match(r"^-\s*\*\*(Edits|Creates|Deletes|Moves):\*\*", line)` so a batch's `Moves:` bullet (and
  its indented rename-pair sub-bullets, already captured by the existing sub-bullet
  `while`/`re.match(r"^\s+-\s*(.+)$", lines[j])` loop directly below) reaches `<TASK_INTENT>` exactly
  like `Deletes:` already does. No other change to this function.
  In `merge-in-conflict-brief.md`, add a new instruction step immediately after the existing step 6
  (the `Deletes:`/DU-conflict special-case): "6a. For a conflict landing on a file's OLD path where
  Task intent above lists that path under a batch's `Moves:` (old path -> new path): before accepting
  a resolution that discards the parent's incoming change to the old path, check whether that
  incoming content is actually a feature addition that belongs on the NEW path instead — the old
  path's identity moved to the new path on this branch, so a parent-side edit to the old path's
  pre-rename identity may need to be re-applied to the new path rather than silently dropped. When
  uncertain, keep the parent's addition (do not discard it) and report the ambiguity via `discarded`
  with a description naming both the old and new paths, rather than asserting nothing was lost."
  Renumber no other existing step; insert this as `6a` between steps 6 and 7 exactly as named.
- **Commit:** `fix(merge-in-subagent): thread Moves: into the conflict brief's task intent (#1065)`

### Card 9: separate conflicts-mode model tier and roadmap-dedup brief guidance

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/templates/mill-config.yaml`
  - `plugins/mill/templates/merge-in-conflict-brief.md`
  - `plugins/mill/unit_tests/test-config.py`
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/templates/mill-config.yaml`'s `merge:` block, keep `model: haiku` but change its
  comment to `# model: LLM alias for the merge-in verify-fix sub-agent (haiku is sufficient --
  mechanical pass/fail against a test command)`, and add a new key immediately below it:
  `# conflicts_model: LLM alias for the merge-in conflicts-mode sub-agent (semantic judgment call --
  haiku produced repeated correctness failures across three separate incidents, see #1059/#1065/#1047;
  falls back to 'model' when absent)` followed by `conflicts_model: sonnet`.
  In `millpy-merge-in-subagent.py`'s `main()`, where `model_name = cfg.get("merge", {}).get("model")
  or implementer_cfg.get("model", "haiku")` is currently computed once and shared by both modes,
  branch it on `args.mode`:
  ```python
  merge_cfg = cfg.get("merge", {})
  if args.mode == "conflicts":
      model_name = (
          merge_cfg.get("conflicts_model")
          or merge_cfg.get("model")
          or implementer_cfg.get("model", "haiku")
      )
  else:
      model_name = merge_cfg.get("model") or implementer_cfg.get("model", "haiku")
  ```
  `verify-fix` mode's resolution is byte-for-byte unchanged (same fallback chain, same default);
  only `conflicts` mode gains the new `conflicts_model`-first lookup. Everything downstream of
  `model_name` (the `_reviewers.resolve` call, `impl_model`/`impl_effort` extraction, the dispatch
  into `_run_conflicts`/`_run_verify_fix`) is unchanged.
  In `merge-in-conflict-brief.md`, add one sentence to the existing step 3/step 4 combine-guidance
  (immediately after step 4's "Ambiguous case" worked example): "Before accepting a roadmap-shaped
  Planned/Done (or similarly staged/shipped) split as correct, explicitly check the rest of the
  resolved file — not just the immediate conflict hunk — for whether the same item is already
  represented under the other status further down; a losing side's move to a new section may already
  be reflected outside the hunk boundary, and keeping the item under both statuses is a
  self-contradiction (an item cannot be simultaneously upcoming and already shipped)."
- **Commit:** `fix(merge-in-subagent): separate conflicts-mode model tier, add roadmap-dedup brief guidance (#1059, #1047)`

### Card 10: deterministic terminal geometry for verify-fix subprocess replay

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new module-level function `_generous_terminal_env() -> dict` to `millpy-merge-in-subagent.py`,
  placed near `_posix_shell_run_args`'s import or first use:
  ```python
  def _generous_terminal_env() -> dict:
      env = dict(os.environ)
      for var, floor in (("COLUMNS", 220), ("LINES", 50)):
          try:
              current = int(env.get(var, "0"))
          except ValueError:
              current = 0
          if current < floor:
              env[var] = str(floor)
      return env
  ```
  (add `import os` at the top of the file if not already imported). Pass `env=_generous_terminal_env()`
  to all three `verify-fix`-mode `subprocess.run(...)` calls that replay the operator-supplied
  `--cmd` verify command: the `--stage finalize --mode verify-fix` early-exit branch's
  `post_verify_result = subprocess.run(...)` call, and `_run_verify_fix`'s own two calls (the initial
  `result = subprocess.run(...)` check and the post-sub-agent `post_verify_result =
  subprocess.run(...)` re-verification). Do not change the `conflicts`-mode dispatch path, the
  `git`/`_subprocess_util.run` calls elsewhere in this file, or any call outside `verify-fix` mode —
  this mitigates the reporter's own leading theory for the observed tmux "no space for new pane"
  flake (a headless orchestrating process lacking the real terminal geometry a tmux-driven smoke test
  would otherwise inherit), and is a no-op for any verify command that does not touch tmux.
- **Commit:** `fix(merge-in-subagent): deterministic terminal geometry for verify-fix subprocess replay (#1068)`

## Batch Tests

Extends `test-millpy-merge-in-subagent.py` with: (1) a fixture batch file with a `Moves:` bullet,
asserting `_collect_task_intent`'s output includes it exactly like `Deletes:` does today; (2) a case
asserting `conflicts` mode resolves `model_name` from `merge.conflicts_model` when set, falls back to
`merge.model` when `conflicts_model` is absent, and that `verify-fix` mode's resolution is unaffected
by `conflicts_model` being present or absent; (3) a case asserting `_generous_terminal_env()` raises
`COLUMNS`/`LINES` to the floor only when the inherited value is smaller (and leaves a
larger-than-floor inherited value untouched), and that the three named `verify-fix` subprocess calls
pass it as `env=`. Extends `test-config.py` with a case confirming `merge.conflicts_model` loads
correctly and is absent-safe. Runs via `run-all.py --only test-millpy-merge-in-subagent.py
test-merge-in-subagent.py test-config.py` — `test-merge-in-subagent.py` is included since it shares
fixtures with `test-millpy-merge-in-subagent.py` for this module and must stay green.
