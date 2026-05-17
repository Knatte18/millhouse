# Batch: millpy-implement-push-branch

```yaml
task: 60 (A) — Branch/slug/claim fixes
batch: millpy-implement-push-branch
number: 3
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Single-file change: in `millpy-implement.py`, source the `branch` value used by both push call sites from `git branch --show-current` instead of from `status.md`'s `branch:` field (D4). The worktree's live branch is the truth; `status.md` is a record. Renaming a branch mid-task is intentional and operator-initiated, so push must follow the rename automatically.

`verify: null` because no automated test is appropriate here — the discussion documents this as a production-smoke change. Branch-rename behavior is exercised end-to-end by the next mill-go run on a renamed branch.

## Cards

### Card 7: `millpy-implement.py` push reads branch from `git branch --show-current` (D4)

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_status.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-implement.py`, replace the call at line 97 — `branch = _status.read_branch(status_path, cfg=cfg, slug=slug)` — with a `_subprocess_util.run` call to `git branch --show-current`:

  ```python
  branch_result = _subprocess_util.run(
      ["git", "-C", str(project_root), "branch", "--show-current"]
  )
  if branch_result.returncode != 0:
      print(json.dumps({"status": "stuck", "stuck_type": "transient", "reason": f"git branch --show-current failed: {branch_result.stderr.strip()}"}))
      print(branch_result.stderr, file=sys.stderr)
      return 1
  branch = branch_result.stdout.strip()
  if not branch:
      print(json.dumps({"status": "stuck", "stuck_type": "transient", "reason": "detached HEAD: no current branch"}))
      print("detached HEAD: no current branch", file=sys.stderr)
      return 1
  ```

  The two existing push call sites at lines 164-170 and 245-251 keep `branch` as their `git push origin <branch>` argument — no change needed at the push sites themselves. Remove the `_status` import if no other reference remains; check with grep — `_status.set_batch_fields`, `_status.read_batches`, `_status.append_phase` are used elsewhere in the file, so `_status` stays imported (just `read_branch` is no longer called). Leave `slug` and the `read_branch` call's other side effects unaffected — no other call site in the file uses `read_branch`. ASCII-only stuck-reason strings (the `--show-current` failure path uses regular text — no em-dash, no Unicode).
- **Commit:** `fix(implement): read branch from git, not status.md, at push time (#301)`

## Batch Tests

`verify: null` — production smoke. The discussion explicitly documents: "D4 (push uses `git branch --show-current`): the next mill-go run on a renamed branch is the natural smoke. Optionally add an integration test under `plugins/mill/integration_tests/` … but the production smoke is sufficient." Implementer should not add a new test file for this card.
