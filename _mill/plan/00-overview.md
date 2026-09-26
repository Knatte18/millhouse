# Plan: Unify ask-parent into ask-thread: ask any named session, default parent

```yaml
task: 'Unify ask-parent into ask-thread: ask any named session, default parent'
slug: "ask-thread-skill"
approved: true
started: "20260926-083801"
parent_branch: "main"
root: ""
verify: null
skip_checks: ["wiki-config-mutation"]
discussion_sha: "0b4c227ca08e2aef75e4313020601b6ad7dd6c3f"
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: ask-thread-scripts
    file: 01-ask-thread-scripts.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-ask-thread.py test-millpy-ask-thread.py
  - number: 2
    name: ask-thread-skill-and-callers
    file: 02-ask-thread-skill-and-callers.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-ask-thread.py test-millpy-ask-thread.py
```

## Shared Decisions

### Decision: plain-rename-via-git-mv

- **Decision:** every renamed file (`_ask_parent.py`, `millpy-ask-parent.py`, both tests, the skill's `SKILL.md`) moves with `git mv` first, then gets surgical edits; no `ask-parent` alias of any kind survives.
- **Rationale:** discussion.md "Plain rename, no alias"; keeps git rename history.
- **Applies to:** all batches

### Decision: halt-sites-unchanged

- **Decision:** `SITES`, `ACTIONS`, `parse_actions`, `halt_suffix`, `unreachable_suffix` and the callers' control flow keep their exact behaviour; callers only change the skill name `ask-parent` -> `ask-thread`.
- **Rationale:** automatic mode must stay a drop-in for `ask-parent` (discussion.md Constraints).
- **Applies to:** all batches

### Decision: resolve-subcommand-for-direct-mode-entry

- **Decision:** the CLI gains a small `resolve [--to <name>]` subcommand the skill runs once when direct mode is invoked; it fails (exit 1) outside a mill task worktree and prints `{"target": <name or null>}` otherwise.
- **Rationale:** discussion.md requires direct mode to resolve its target once at invocation from `--to`/`parent_thread` and to stop outside a task worktree; the skill must not run inline Python, and `prepare` runs only per question batch, so the invocation-time check needs its own entry point.
  It adds no new behaviour beyond what the discussion specifies.
- **Applies to:** ask-thread-scripts, ask-thread-skill-and-callers

### Decision: ask-id-line-match-rule

- **Decision:** a reply matches when its first non-empty line, with trailing whitespace stripped and leading whitespace kept, equals `ask-id: <ask_id>`.
  Python (`consume`) and the shell poll (`awk 'NF{print; exit}' ... | grep -qxE "ask-id: <ask_id>[[:space:]]*"`) implement the same rule.
- **Rationale:** one reply-recognition rule for the poll, the message check and `consume`, so a file the poll accepts is never rejected by `consume`.
- **Applies to:** all batches

### Decision: done-gate-no-lint-recommendation

- **Decision:** no `pipeline.done_gate` change is recommended; the effective value stays `null`.
- **Rationale:** `uvx ruff check .` exits 1 on the current worktree tip (pre-existing repo-wide lint debt unrelated to this task), so recommending it would force every future task to fix unrelated debt first; the full `run-all.py` suite is multiple minutes and the batch verifies cover every test this task touches.
- **Applies to:** all batches

## All Files Touched

- `SKILLS.md`
- `mill-config.yaml`
- `plugins/mill/docs/harness-tool-contracts.md`
- `plugins/mill/scripts/_ask_thread.py`
- `plugins/mill/scripts/millpy-ask-thread.py`
- `plugins/mill/skills/ask-thread/SKILL.md`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-go-base/handoff.md`
- `plugins/mill/skills/mill-go-base/holistic-review.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-quick/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-ask-thread.py`
- `plugins/mill/unit_tests/test-millpy-ask-thread.py`
