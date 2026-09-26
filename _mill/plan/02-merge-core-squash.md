# Batch: merge-core-squash

```yaml
task: 'mill-merge: run the deterministic path as one script'
batch: merge-core-squash
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-merge.py
depends-on: [1]
```

## Batch Scope

Completes `_merge.py` with the teardown side: the child cleanup commit, the Step 5 squash (lock, dirty/ff checks, state-based landed detection, push with non-ff retry and branch-protection fallback, rollback, lock release), the archive tag, the wiki `[done]` flip, and the final notify/report.
After this batch `_merge.run_merge` runs every route end to end;
batch 3 wraps it in a CLI.

Batch-local decisions:

- **Mutation window.** `step_squash` keeps a local `needs_rollback` flag, set to `True` immediately before the first parent mutation (pushing an unpushed local squash, or `merge --squash`) and cleared once the squash is confirmed on origin (push exit 0, retry push exit 0, or the branch-protection `reset --hard` completed).
  The `finally` rolls back only while it is `True`, which keeps the dirty-parent and ff-only halts rollback-free (discussion Decisions `run-budget-and-kill-safety`, `squash-landed-detection`).
- **Exceptions inside the mutation window propagate after rollback.** A non-`Stop` exception (including `Terminated`) is not converted to a halt;
  the rollback and lock release run in `finally`, then it propagates and the CLI exits non-zero with a traceback, matching discussion Decision `script-shape`.
- **Nothing staged after the task-dir restore.** When `git diff --cached --quiet` exits 0 after the restore, the squash is a no-op: skip commit and push, clear `needs_rollback`, and continue to the archive tag (replaces the old "nothing to commit" idempotency note).

## Cards

### Card 4: child cleanup commit with citation scan

- **Context:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Edits:**
  - `plugins/mill/scripts/_merge.py`
  - `plugins/mill/unit_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `step_cleanup_commit(ctx, ops)` and append `("cleanup-commit", step_cleanup_commit, lambda c: c.route in ("direct", "pr-closed", "pr-merged"))` to `STEPS` after `merge-in-check`.
  Spec: old `plugins/mill/skills/mill-merge/SKILL.md` `### 4. Cleanup commit` and the `Cleanup-commit rollback (Step 4)` paragraph.
  - Citation scan (#930), two `ops.run` calls, never halting:
    `["git", "-C", git_root, "grep", "-InE", r"\]\([./]*_mill/discussion\.md\)", "--", ".", f":(exclude){ctx.task_dir_git_rel}", ":(exclude)plugins/**/SKILL.md", ":(exclude)plugins/**/unit_tests/**", ":(exclude)plugins/**/integration_tests/**"]`
    and `["git", "-C", wiki_path, "grep", "-InE", r"\]\([./]*_mill/discussion\.md\)", "--", "."]`.
    Exit 1 with empty stdout is the normal no-hit case.
    Each non-empty stdout line becomes one `ctx.warnings` entry: `permanent-doc citation of _mill/discussion.md is about to go dead: <line>` (prefix wiki hits with `wiki:`).
  - When `ctx.task_dir.exists()`: `_git_ok(["git", "-C", git_root, "rm", "-r", "-q", ctx.task_dir_git_rel], what="git rm task dir")`.
  - `staged = ops.run(["git", "-C", git_root, "diff", "--cached", "--quiet"]).returncode == 1`;
    when staged: `ops.run(["git", "-C", git_root, "commit", "-m", "chore: pre-merge cleanup"])`;
    on non-zero exit run `git -C <git_root> reset --hard HEAD` and raise `halt("cleanup-commit failed: <err>; task branch reset to HEAD. Re-run /mill-merge.")`.
    When nothing is staged, skip the commit (re-entry idempotency).
  The docstring carries the "why cleanup before squash" and archive-recovery notes from the old section.

  Tests: no hits -> no warnings;
  worktree hit and wiki hit -> two warnings, run continues;
  task dir absent -> no `rm` call and, with nothing staged, no `commit` call;
  task dir present -> `rm` then `commit` with message `chore: pre-merge cleanup`;
  commit failure -> `reset --hard HEAD` recorded and halt;
  the wiki grep argv uses `-C <wiki_path>` and no call passes `cwd` equal to the wiki path.
- **Commit:** `feat(mill-merge): cleanup-commit step with citation scan`

### Card 5: squash step with lock, landed detection, push fallback, and rollback

- **Context:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:**
  - `plugins/mill/scripts/_merge.py`
  - `plugins/mill/unit_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add lock helpers, push helpers, and `step_squash(ctx, ops)`;
  append `("squash", step_squash, lambda c: c.route in ("direct", "pr-closed"))` to `STEPS` after `cleanup-commit`.
  Spec: old `plugins/mill/skills/mill-merge/SKILL.md` `### 1. Acquire merge lock on parent`, `### 5. Direct squash`, `### 8. Release merge lock`, `## Rollback (Steps 1-5 only)`, plus discussion Decisions `lock-timing`, `run-budget-and-kill-safety`, `squash-landed-detection`, `step5-in-script`.
  Below, `P` is `ctx.parent_path` and `p` is `ctx.parent_branch`;
  all parent-side git calls are `["git", "-C", P, ...]`.

  Parent path: worktree mode -> the `_parse_worktrees` entry of `git -C <git_root> worktree list --porcelain` whose `branch == f"refs/heads/{p}"`;
  none -> `halt(f"Parent branch {p} is not checked out in any worktree; check it out in its own worktree, then re-run /mill-merge.")`.
  In-place mode -> `P = git_root`.

  Lock (worktree mode only; in-place takes no lock):
  - `_acquire_lock(ctx, ops) -> Path`: lock path `P / ".scratch" / "merge.lock"` (create `.scratch` if missing).
    Existing lock: read its three lines (pid, timestamp, branch);
    stale when the timestamp fails to parse or `ops.now() - ts > 300 s`;
    held by the same branch as `ctx.child_branch` counts as ours.
    Fresh and held by another branch -> raise `halt(f"Merge lock held: {lock} -- pid={pid}, timestamp={ts}, branch={branch}. Wait for it to clear, then re-run /mill-merge.", resume=[], data={"lock_path": str(lock), "pid": pid, "timestamp": ts, "branch": branch}, step="lock")`, so the result reports `step: "lock"` per discussion Decision `lock-timing`.
    Otherwise write `f"{ops.pid()}\n{ops.now():%Y-%m-%dT%H:%M:%SZ}\n{ctx.child_branch}\n"`.
  - `_release_lock(lock)`: unlink, ignoring `FileNotFoundError`.

  `step_squash` sequence:
  1. Worktree mode: acquire lock.
     Everything after runs in `try/finally`;
     the `finally` first rolls back when `needs_rollback` (see batch-local decision), then releases the lock.
     Rollback = `git -C P reset --hard origin/<p>` in worktree mode;
     in in-place mode only when `git -C <git_root> branch --show-current` equals `p`.
     A failing rollback command appends a warning and prints to stderr;
     it never masks the original exception.
  2. Worktree mode: dirty check `git -C P status --porcelain --untracked-files=no`;
     non-empty -> halt with the old dirty-parent text (both (a)/(b) cases), `resume=[]`.
     Then `git -C P fetch origin <p>` and `git -C P merge --ff-only origin/<p>`;
     either failing -> halt with the old diverged-parent text, `resume=[]`.
     In-place mode: `git -C <git_root> fetch origin <p>`;
     failure -> `halt("git fetch origin <p> failed: <err>")`.
  3. Landed detection, in order (discussion Decision `squash-landed-detection`), with `grep = f"^Mill-Task: {slug}$"`:
     (a) `git -C P log origin/<p>..<p> --grep=<grep> --format=%H -n 1` non-empty -> set `needs_rollback = True` and go to the push in step 5 (no new squash);
     (b) `git -C P log origin/<p> --grep=<grep> --format=%H -n 1` non-empty -> landed: append report line `Squash for <slug> already on origin/<p>; skipping squash.` and return;
     (c) `mb = git -C P merge-base origin/<p> <child>`;
     `names = git -C P diff --name-only <mb> <child>` lines not equal to or under `ctx.task_dir_rel + "/"`;
     when `names` is non-empty and `git -C P diff --quiet origin/<p> <child> -- *names` exits 0 -> landed (legacy, same report line) and return;
     empty `names` skips (c).
  4. Fresh squash: `needs_rollback = True`;
     `git -C P merge --squash <child>`;
     non-zero -> collect `git -C P diff --name-only --diff-filter=U` and raise `halt("merge --squash of <child> into <p> failed (conflicts: <files>); parent rolled back to origin/<p>.")`.
     Then `git -C P reset -q HEAD -- <task_dir_rel>` and `git -C P checkout -- <task_dir_rel>` (both results ignored; #497/#648 notes go in the docstring).
     `git -C P diff --cached --quiet` exit 0 -> nothing staged: clear `needs_rollback`, report line, return.
     Else `_git_ok(["git", "-C", P, "commit", "-m", f"{ctx.cached_task}\n\nMill-Task: {slug}"])`.
  5. `_push_parent(ctx, ops) -> str` returns `"pushed"` or `"protected"`:
     `git -C P push`;
     exit 0 -> `"pushed"`.
     Else on combined stdout+stderr: any of `Changes must be made through a pull request`, `repository rule violations`, `protected branch`, `GH006` -> `"protected"`;
     else `! [rejected]` together with `(fetch first)` or `(non-fast-forward)` -> `git -C P fetch origin <p>`, `git -C P rebase origin/<p>`;
     rebase non-zero -> collect `diff --name-only --diff-filter=U`, `git -C P rebase --abort`, raise `halt` naming the conflicting files;
     clean rebase -> retry `git -C P push` once, exit 0 -> `"pushed"`, else raise `halt("git push retry failed: <err>; parent rolled back to origin/<p>.")`;
     neither marker set -> raise `halt("git push failed: <err>; parent rolled back to origin/<p>.")`.
     On `"pushed"` clear `needs_rollback`.
  6. On `"protected"`: `git -C P reset --hard origin/<p>` via `_git_ok`, then clear `needs_rollback`;
     `gh pr list --head <child> --state open --json number,url --jq .[0]` (cwd `git_root`), parse `url` from its JSON stdout when non-empty;
     else `gh pr create --base <p> --head <child> --title <cached_task> --body "Auto-created: direct push was rejected by branch protection.\n\n<cached_task_description>"` (cwd `git_root`) and take the last non-empty stdout line as the URL;
     `git -C <git_root> push origin <child>`;
     `ops.set_phase(wiki_path, slug, "pr-pending")` (exception -> halt with its text);
     set `ctx.route = "branch-protection-pr"`, then raise `Stop("ok", ..., data={"pr_url": url, "slug": slug, "parent_branch": p}, report=["Direct push rejected by branch protection -- switched to PR path. PR: <url>. Consider setting `git.require_pr_to_base: true` in mill-config.yaml."])`.
     The runner treats an `ok` `Stop` like any other stop (ends the run, skips archive tag and `[done]`).

  Tests (lock files in a temp dir used as `P`; `FakeOps.now` fixed):
  lock fresh acquire writes three lines and is gone after the step;
  stale lock (timestamp 6 min old) is overwritten;
  fresh lock from another branch -> halt with `step == "lock"`, holder data, `resume == []`, and no parent git calls;
  lock released on success, on the dirty-parent halt, on a push-failure halt, and when a fake git call raises `RuntimeError`;
  dirty parent and ff-only failure halt with no `reset --hard` call;
  landed (a) -> push, no `merge --squash`;
  landed (b) -> no `merge --squash`, no push;
  landed (c) legacy -> no `merge --squash`;
  fresh squash commit message ends with `Mill-Task: <slug>`;
  nothing staged -> no commit, no push, no reset;
  push success -> no reset;
  non-ff -> rebase -> retry success;
  rebase conflict -> `rebase --abort`, `reset --hard origin/<p>`, halt naming files;
  retry failure and other failure -> `reset --hard origin/<p>` and halt;
  branch-protection -> reset, existing PR reused (no `gh pr create`), `push origin <child>`, one `set_phase(..., "pr-pending")`, result `status == "ok"`, `route == "branch-protection-pr"`, `data.pr_url` set, and `archive_tag` never called;
  branch-protection with no PR -> `gh pr create` called with `--base <p>`;
  a `Terminated` raised by the fake `push` -> `reset --hard origin/<p>` recorded, lock file removed, `Terminated` propagates;
  a `Terminated` raised after a successful push (e.g. from the first post-push call) -> no `reset --hard`;
  in-place mode -> no lock file, no dirty check, `fetch origin <p>` against `git_root`, fetch failure halts.
- **Commit:** `feat(mill-merge): squash step with lock, landed detection, push fallback, rollback`

### Card 6: archive tag, wiki done, notify, and full-route tests

- **Context:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/scripts/_archive_tag.py`
  - `plugins/mill/scripts/_notify.py`
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:**
  - `plugins/mill/scripts/_merge.py`
  - `plugins/mill/unit_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `step_archive_tag`, `step_wiki_done`, `step_notify` and append `("archive-tag", ...)`, `("wiki-done", ...)`, `("notify", ...)` with `applies = lambda c: c.route in ("direct", "pr-closed", "pr-merged")`.
  Spec: old `plugins/mill/skills/mill-merge/SKILL.md` `### 6. Archive tag`, `### 7. Home.md -- mark [done]`, `### 9. Notify + report`.
  - `step_archive_tag`: `r = ops.archive_tag(git_root, slug, ctx.child_branch)` inside `try/except Exception as e` -> `halt(f"Merge landed on {p} but archive-tag failed: {e}. Re-run /mill-merge to retry.", resume=[])` (no rollback: discussion Decision `re-entry-idempotency`).
    Store `ctx.archive = r`;
    report lines `archive-tag action: <action> -- tag: <tag>` and, when set, `prior tag preserved as <moved_aside_to>`;
    `push_failed` -> warning `archive tag push failed -- reconcile <tag> with remote manually: <push_error>`.
  - `step_wiki_done`: `ops.set_phase(wiki_path, slug, "done")`;
    exception -> `halt(f"Merge landed on {p} but wiki-done failed: {e}. Re-run /mill-merge to retry.", resume=[])`.
  - `step_notify`: `ops.notify("mill-merge.done", f"task {slug} merged into {p}", slug=slug, parent=p)`;
    append the old Step 9 report text (`Merge complete for <slug>. Worktree intact -- run /mill-cleanup --apply ...`).
    `run_merge`'s `ok` result `data` holds `slug`, `parent_branch`, `archive_tag`, `archive_action`, `moved_aside_to`.
  - Remove any remaining TODO/placeholder in `_merge.py`;
    the module docstring lists the step names in order and states which routes run which steps.

  Full-route tests through `run_merge` with `FakeOps` (temp status.md, temp parent dir):
  `direct` worktree mode executes exactly `entry, parent, phase-gate, pr-state, merge-in-check, cleanup-commit, squash, archive-tag, wiki-done, notify` (from `timings`);
  `direct` in-place omits `merge-in-check` and takes no lock;
  `pr-merged` omits `merge-in-check` and `squash`;
  `pr-closed` matches `direct`;
  `branch-protection-pr` ends at `squash` with `status == "ok"`;
  exactly one `set_phase` call per route (`done` for the three merge routes, `pr-pending` for branch-protection);
  archive-tag raising and `set_phase` raising -> halt text starts with `Merge landed on`, no `reset --hard` call, lock file already gone;
  `push_failed` -> warning present;
  a sweep test asserting every string in `reason`, `report`, `warnings` of each route's result is ASCII (`s.isascii()`).
- **Commit:** `feat(mill-merge): archive tag, wiki done, notify steps and route tests`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-merge.py`, extended by all three cards.
Card 6's route tests exercise the full `STEPS` list, so this run also re-checks batch 1's steps.
