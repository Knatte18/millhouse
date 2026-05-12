---
name: mill-autofix
description: Autonomously fetch open GitHub bug issues, synthesise discussion.md per bug, run mill-plan + mill-go + mill-merge in sequence, close the issue on success, and write a results report.
---

# mill-autofix

You are the autonomous bug-fix orchestrator. Your job: drain the GitHub bug queue. For each open issue labelled `bug`, claim it via mill-claim (in-place on the hub), write `_mill/discussion.md`, run mill-plan → mill-go → mill-merge in sequence, close the issue on success, then move to the next bug. You run entirely in a single CC session in the hub worktree — no sub-LLM spawning.

**The cleanup phase is non-negotiable.** `pipeline.autonomous_mode: true` is a temporary mutation of `.millhouse/config.local.yaml`. It must be restored on every exit path: success, block, killswitch, or unhandled error.

## Arguments

- `--dry-run` — read-only. Fetch issues, print a summary table, exit. **Config is never mutated in dry-run mode.**
- `--max-bugs N` — process at most `N` issues from the fetched list (default: unlimited).

## Phase 0: Init

Record the current branch as `parent_branch`:

```bash
git branch --show-current
```

Record `start_ts` (do not guess — use the clock):

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
import _timestamp; print(_timestamp.now_utc_iso())
"
```

Initialise three result lists (maintained in working context throughout the run):
- `fixed_list` — bugs successfully fixed and merged
- `stuck_list` — bugs that blocked inside mill-plan, mill-go, or mill-merge
- `errored_list` — bugs that could not be set up (dirty tree, claim failure, etc.)

## Phase 1: Fetch

### 1a. Fetch bug issues

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
import _gh_issues, _paths, json, sys
issues = _gh_issues.fetch(label_filter=['bug'], git_root=_paths.resolve_git_root())
json.dump(issues, sys.stdout, indent=2)
"
```

Each issue dict: `number`, `title`, `body` (includes rendered comments), `labels`, `createdAt`.

Store result as `all_issues`. Apply `--max-bugs` cap: `issues = all_issues[:N]` (or all if no cap).

### 1b. Load Home.md and extract existing slugs

Resolve the wiki path:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
from _paths import resolve_git_root, resolve_wiki_path
print(resolve_wiki_path(resolve_git_root()))
"
```

Read `<wiki_path>/Home.md` and extract the set of existing slugs using the `_TASK_HEADING_RE` pattern (same pattern as `millpy-add.py`):

```python
import re
_TASK_HEADING_RE = re.compile(
    r"^##\s+.+?\n\[\[?([a-z][a-z0-9-]*)\]?\](?:\([^)]+\))?[ \t]*$",
    re.MULTILINE,
)
home_text = open("<wiki_path>/Home.md", encoding="utf-8").read()
existing_home_slugs = {m.group(1) for m in _TASK_HEADING_RE.finditer(home_text)}
```

Maintain `existing_home_slugs` in working context throughout the run.

## Phase 1c: Dry-run exit

If `--dry-run` was passed:

1. For each issue in `all_issues` (up to `--max-bugs`):
   - Derive slug using the algorithm below. Add it to `existing_home_slugs` so subsequent entries do not collide.
2. Print a table:
   ```
   #    Issue#  Slug                           Title
   ─────────────────────────────────────────────────────────────────
   1    42      fix-null-deref-in-render       Null dereference in render path
   2    51      broken-wiki-lock               Broken wiki lock on timeout
   ```
3. Exit without mutating any state.

## Phase 2: Pre-flight — enable autonomous mode

Resolve `cfg_path = <git_root>/.millhouse/config.local.yaml`.

Read the original file content (store as `original_cfg_text`, or `None` if the file does not exist):

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
from pathlib import Path
cfg = Path('.millhouse/config.local.yaml')
if cfg.exists():
    print('EXISTS')
    print(cfg.read_text(encoding='utf-8'), end='')
else:
    print('ABSENT')
"
```

If the output starts with `EXISTS`, `original_cfg_text` = the rest. If `ABSENT`, `original_cfg_text = None`.

Set `pipeline.autonomous_mode: true`:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
from pathlib import Path
import yaml
cfg_path = Path('.millhouse/config.local.yaml')
cfg = yaml.safe_load(cfg_path.read_text(encoding='utf-8')) if cfg_path.exists() else {}
if not isinstance(cfg, dict):
    cfg = {}
cfg.setdefault('pipeline', {})['autonomous_mode'] = True
cfg_path.parent.mkdir(parents=True, exist_ok=True)
cfg_path.write_text(yaml.dump(cfg, sort_keys=False, allow_unicode=True), encoding='utf-8')
print('autonomous_mode enabled')
"
```

## Phase 3: Per-bug loop

For each issue in `issues` (in order), execute steps 0–10. After the loop (or after the killswitch fires), proceed to Phase 4.

---

### Step 0: Branch guard + killswitch check

Verify the current branch is `parent_branch`:

```bash
git branch --show-current
```

If the output does not equal `parent_branch`: run the **Stuck cleanup helper**, then continue to the next issue.

Check whether `.scratch/autofix-stop` exists:

```bash
test -f .scratch/autofix-stop && echo STOP || echo GO
```

If `STOP`: halt the loop immediately. Do **not** delete the file. Proceed to Phase 4 (Cleanup) then Phase 5 (Report).

---

### Step 1: Derive slug

Apply the slug algorithm to `issue["title"]` and `existing_home_slugs`:

1. Lowercase the title.
2. Replace every character not in `[a-z0-9]` with `-`.
3. Collapse consecutive `-` runs to a single `-`.
4. Strip leading and trailing `-`.
5. If length > 30: truncate at the last `-` boundary within the first 30 characters (or hard-cut at 30 if no boundary).
6. If the result is in `existing_home_slugs`: append `-<issue_number>`.

This is `_autofix.slug_from_title(title, existing_home_slugs, issue_number)`. You may apply the algorithm mentally or via subprocess:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
import _autofix, json, sys
d = json.loads(sys.stdin.read())
print(_autofix.slug_from_title(d['title'], set(d['existing']), d['num']))
" <<EOF
{"title": "<title>", "existing": [<comma-quoted existing_home_slugs>], "num": <issue_number>}
EOF
```

**Immediately** add the derived slug to `existing_home_slugs` (before processing the next bug) so subsequent derivations treat it as taken.

---

### Step 2: Add to Home.md

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-add.py" \
    <slug> \
    --title "<issue title>" \
    --summary "<issue body first 200 chars>"
```

The `--summary` value is `issue["body"][:200].strip()` (use `""` if body is None or empty).

**Exit 0:** proceed to step 3.

**Exit 1:** inspect the combined stdout + stderr:

- **Contains `"already present"`** (the exact phrase from millpy-add.py's SystemExit): parse the phase of the existing task:

  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
  import _tasks_md, sys
  from pathlib import Path
  home_text = Path(sys.argv[1]).read_text(encoding='utf-8')
  tasks = _tasks_md.parse(home_text)
  t = next((t for t in tasks if t.slug == sys.argv[2]), None)
  if t is None:
      print('not-found')
  else:
      print(t.phase or 'unmarked')
  " "<wiki_path>/Home.md" "<slug>"
  ```

  - Phase `active` or `done` → skip this issue. Do not record in any list. Continue to next issue.
  - Phase `unmarked` (or `not-found`) → the task entry exists but was never claimed. Proceed to step 3 (claim it).

- **Any other exit 1 reason:** record in `errored_list` as `{slug, issue_number, title, error: <stderr>}` and continue to next issue.

---

### Step 3: Pre-claim dirty-tree check

```bash
git status --porcelain
```

If output is non-empty (uncommitted changes in the working tree), run:

```bash
git clean -fd _mill/
```

Re-run `git status --porcelain`. If still non-empty: record in `errored_list` as `{slug, issue_number, title, error: "dirty tree after git clean -fd _mill/"}` and continue to next issue.

---

### Step 4: Claim

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-claim.py" \
    --slug <slug>
```

- **Exit 0:** claimed. millpy-claim.py prints `Branch: <name>` — note the branch name.
- **Exit 1:** record in `errored_list` as `{slug, issue_number, title, error: "millpy-claim.py exited 1: <stderr>"}` and continue to next issue.

---

### Step 5: Synthesise discussion.md

Use Glob, Grep, and Read to explore the codebase for evidence of the bug. Consult `issue["body"]` (includes rendered comments), `issue["title"]`, and `issue["labels"]`.

Read project-level constraints (may be empty):

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
import _constraints; c = _constraints.read_if_exists(); print(c or '')
"
```

Write `_mill/discussion.md` with these required sections:

```
## Problem
<the bug as described in the issue — symptoms, reproduction, relevant code paths
 discovered via codebase exploration; include specific file paths and function names>

## Scope
<which files/functions are affected; what is explicitly out of scope>

## Decisions
<how the fix will be structured — approach and rationale, not implementation details>

## Technical context
<relevant code patterns, invariants, or constraints observed during codebase exploration>

## Constraints
<verbatim contents of CONSTRAINTS.md if present; "None." otherwise>

## Testing
<how the fix will be verified: relevant existing tests, new tests to write, manual steps>

## Q&A log

_None yet._
```

Make each section self-contained. mill-plan consumes `discussion.md` cold with zero conversation history — include the concrete evidence you found (file paths, function names, line numbers) in Problem and Technical context.

---

### Step 6: Commit and push discussion.md

```bash
git add _mill/discussion.md
git commit -m "mill-autofix: write discussion.md for <slug>"
git push
```

On any failure: record in `stuck_list` as `{slug, issue_number, title, phase: "discussion", blocked_reason: "<error>"}`, run **Stuck cleanup helper**, and continue to the next issue.

---

### Step 7: Invoke mill-plan

```
/mill-plan
```

After it returns, read `_mill/status.md`'s `phase:` and `blocked_reason:`:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
import _status
from pathlib import Path
s = _status.read_status(Path('_mill/status.md'))
print(s['phase'])
print(s.get('blocked_reason') or '')
"
```

`signature: _status.read_status(status_path: Path) -> {"phase": str, "task": str|None, "current_batch": str|None, "last_timeline_entry": str|None, "blocked_reason": str|None}`

- `planned` → success. Proceed to step 8.
- `blocked` → record in `stuck_list` as `{slug, issue_number, title, phase: "mill-plan", blocked_reason: <value from status.md>}`. Run **Stuck cleanup helper**. Continue to next issue.
- any other phase → record in `stuck_list` as `{slug, issue_number, title, phase: "mill-plan", blocked_reason: "mill-plan ended in unexpected phase: <actual>"}`. Run **Stuck cleanup helper**. Continue to next issue.

---

### Step 8: Invoke mill-go

```
/mill-go
```

After it returns, read `_mill/status.md`'s `phase:` and `blocked_reason:` (same helper as step 7).

- `done` → success. Proceed to step 9.
- `blocked` → record in `stuck_list` as `{slug, issue_number, title, phase: "mill-go", blocked_reason: <value>}`. Run **Stuck cleanup helper**. Continue to next issue.
- any other phase → record in `stuck_list` as `{..., blocked_reason: "mill-go ended in unexpected phase: <actual>"}`. Run **Stuck cleanup helper**. Continue to next issue.

---

### Step 9: Invoke mill-merge

```
/mill-merge
```

mill-merge auto-detects in-place mode (the task is on a branch of the hub worktree; no separate worktree directory exists). After it returns:

```bash
git branch --show-current
```

- Output equals `parent_branch` → mill-merge succeeded. The squash commit is now on `parent_branch`. Proceed to step 10.
- Output does not equal `parent_branch` → mill-merge did not complete. Record in `stuck_list` as `{slug, issue_number, title, phase: "mill-merge", blocked_reason: "still on task branch after mill-merge"}`. Run **Stuck cleanup helper** (which force-checks out `parent_branch`). Continue to next issue.

---

### Step 10: Record success and close issue

Extract the squash commit SHA (we are now on `parent_branch`):

```bash
git log --oneline -1
```

Parse the first space-delimited token as `sha`.

Close the GitHub issue:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
import _gh_issues, _paths
_gh_issues.close_with_comment(<issue_number>, 'Autonomously fixed by mill-autofix. Squash commit: <sha>', git_root=_paths.resolve_git_root())
"
```

On `GhError`: print the error to stderr but proceed — the fix landed; the GitHub close failed. The operator can close manually.

Record in `fixed_list` as `{slug, issue_number, title, commit_sha: sha}`.

---

### Stuck cleanup helper

Run this whenever a bug gets stuck at any phase (step 6, 7, 8, or 9) to restore the worktree to `parent_branch`.

```bash
git reset --hard HEAD
git clean -fd _mill/
git checkout <parent_branch>
```

**Why `git reset --hard HEAD` before `git checkout`:** the implementer session inside mill-go may have left uncommitted tracked-file changes. Without this reset, `git checkout <parent_branch>` aborts when tracked source files differ between branches.

On any git error in the stuck cleanup helper, print to stderr and continue — the report captures the partial state.

Note: the wiki `active/<slug>/` directory and the `[active]` marker in Home.md are left as-is. They will be detected on the next autofix run (the "already present [active]" path in step 2) and skipped. Use `/mill-cleanup` to sweep stale wiki state after the run.

---

## Phase 4: Cleanup — restore autonomous mode

**Always run — even if an unhandled error escapes the per-bug loop.**

Restore `config.local.yaml` to its original state:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
from pathlib import Path
import sys
cfg_path = Path('.millhouse/config.local.yaml')
# original_cfg_text is passed as stdin
original = sys.stdin.read()
if original == '__ABSENT__':
    cfg_path.unlink(missing_ok=True)
    print('config.local.yaml removed (was absent before)')
else:
    cfg_path.write_text(original, encoding='utf-8')
    print('config.local.yaml restored')
" <<'EOF'
<original_cfg_text or literal __ABSENT__>
EOF
```

If `original_cfg_text` was `None` (file did not exist before): delete `.millhouse/config.local.yaml` (`missing_ok=True` — safe if already gone). Otherwise: write back the exact original text byte-for-byte.

## Phase 5: Report

Record `end_ts`:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
import _timestamp; print(_timestamp.now_utc_iso())
"
```

Write `.scratch/autofix-report.md`:

```markdown
# mill-autofix report

Date/time: <start_ts> – <end_ts>
Issues fetched: <len(all_issues)>
--max-bugs applied: <N or "none">
Killswitch fired: <yes/no>

## Fixed (<len(fixed_list)>)

| # | Issue | Slug | Title | Commit |
|---|---|---|---|---|
| 1 | #42 | fix-null-deref-in-render | Null deref in render | abc1234 |

## Stuck (<len(stuck_list)>)

| # | Issue | Slug | Title | Phase | Reason |
|---|---|---|---|---|---|
| 1 | #51 | broken-wiki-lock | Broken wiki lock | mill-plan | non-progress round 2 |

## Errored (<len(errored_list)>)

| # | Issue | Slug | Title | Error |
|---|---|---|---|---|
| 1 | #63 | some-slug | Some bug | dirty tree after git clean |
```

Print to the user:
- Path: `.scratch/autofix-report.md`
- Summary line: `Fixed: N | Stuck: M | Errored: K`
- If killswitch fired: `Note: .scratch/autofix-stop was set — run stopped early. Remove the file to re-enable.`
- If any stuck or errored items: recommend inspecting the report and running `/mill-cleanup` to sweep stale wiki state.

## Principles

- **Cleanup is non-skippable.** Treat the per-bug loop as a try block with a guaranteed finally (Phase 4). A crashed or manually interrupted run must be re-started from scratch; bugs already fixed will be skipped via the "already present [done]" path in step 2.
- **Dry-run is truly read-only.** No config mutations, no wiki writes, no git state changes.
- **Slug uniqueness across the run.** Add each derived slug to `existing_home_slugs` immediately — `_autofix.slug_from_title` only checks the set you pass in; it does not re-read Home.md.
- **Killswitch is a soft stop.** `.scratch/autofix-stop` halts after the current bug completes (or after stuck cleanup if the current bug was in-flight). Do not delete the file.
- **Each bug is independent.** A stuck or errored bug never blocks the next. The stuck cleanup helper restores invariants between bugs.
- **Discussion.md is the handoff.** Include concrete evidence (file paths, function names, line numbers) in Problem and Technical context. mill-plan reads it cold — if the context is thin, the plan will be thin.
- **Never guess timestamps.** Always call `_timestamp.now_utc_iso()` or `now_utc_compact()` via subprocess. The LLM clock is not reliable.
- **Verify parent_branch after each bug.** Before the killswitch check at the top of the next iteration, confirm `git branch --show-current == parent_branch`. If not, run the stuck cleanup helper immediately — something went wrong in the previous iteration's teardown.
