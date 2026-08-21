# Batch: mill-merge-in-nested-cwd

```yaml
task: 'mill-merge/merge-in: nested-layout config resolution, stale locks, and rollback-target bugs'
batch: mill-merge-in-nested-cwd
number: 2
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Fixes two nested-hub-layout bugs in `plugins/mill/skills/mill-merge-in/SKILL.md`: (1) `#899` — Step 4 (Verify)'s `cwd is None` default resolves to `hub_root`, but `_implementer_common._run_verify_gate` (confirmed via source read) always resolves a plain-string `verify:` command's cwd to `git_root` during mill-go's own live batch dispatch, so the replay must match; (2) `#880` — Step 5 (Codeguide update) relies on ambient shell cwd with no override, but `codeguide/scripts/resolve.py`'s inline walk only searches upward from cwd to the git toplevel, so it can never find a `_codeguide/` directory nested below cwd in a hub subdirectory. Both fixes are prose-only edits to the same file, independent sections — one batch. Every fenced block below reproduces the source file's own byte-exact indentation (flush left, no extra indent from this card's own list nesting) — copy fence contents literally.

## Cards

### Card 3: verify-cwd-default — match `_run_verify_gate`'s live-dispatch behavior

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `### 4. Verify`, find this exact text (the "Resolve the run cwd" bullet, a single indented bullet under the "For each `(name, cmd, cwd)`:" list):

```
- Resolve the run cwd: `hub_root` when `cwd == hub_root`, `git_root` when `cwd == git_root`, and `hub_root` when `cwd is None` (the string-form default — matching the existing pre-batch-3 behavior, since "the worktree root" this step has always run in resolves to `hub_root`, not `git_root`).
  Run the command from that resolved cwd.
  On success: increment `ran` and continue to the next triple.
```

  Replace it with:

```
- Resolve the run cwd: `hub_root` when `cwd == hub_root`, `git_root` when `cwd == git_root`, and `git_root` when `cwd is None` (the string-form default — matching `_implementer_common._run_verify_gate`'s actual live-dispatch behavior: mill-go's own batch verify calls always pass `git_root=git_root` to `_run_verify_gate`, which resolves a plain-string `verify:` command's cwd to `git_root` whenever `git_root` is not `None`, per that function's own docstring — "When None, falls back to project_root" — so `git_root` is what a plain-string `verify:` command was actually exercised against during implementation, and this replay step must match that, not `hub_root`).
  Run the command from that resolved cwd.
  On success: increment `ran` and continue to the next triple.
```

  Do not modify any other bullet in `### 4. Verify` (the allowlist pre-check, plugin-root substitution, or failure-dispatch bullets are unaffected).
- **Commit:** `fix(mill-merge-in): Step 4 verify cwd=None default now resolves to git_root, matching live batch-dispatch behavior (#899)`

### Card 4: codeguide-cwd-pinning — pin cwd to hub_root before invoking codeguide-update

- **Context:**
  - `plugins/codeguide/settings.json`
  - `plugins/mill/skills/git-commit/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `### 5. Codeguide update`, find this exact text:

```
### 5. Codeguide update

If `_codeguide/Overview.md` exists anywhere in the repo, invoke the `codeguide-update` skill scoped to the checkpoint diff:

- Use the Skill tool with name `codeguide:codeguide-update` (namespace matches `plugins/codeguide/settings.json`).
- Pass argument `"$CHK..HEAD"` so the update sees everything the merge introduced, including your conflict resolutions.

If `_codeguide/Overview.md` is absent → skip silently.
This is the documented convention in `plugins/mill/skills/git-commit/SKILL.md` step 2 and we follow it here for symmetry.
```

  Replace it with:

```
### 5. Codeguide update

If `_codeguide/Overview.md` exists anywhere in the repo, invoke the `codeguide-update` skill scoped to the checkpoint diff:

- Resolve `hub_root = _paths.resolve_hub_path()`.
- Run `cd <hub_root>` via the Bash tool.
- Use the Skill tool with name `codeguide:codeguide-update` (namespace matches `plugins/codeguide/settings.json`).
- Pass argument `"$CHK..HEAD"` so the update sees everything the merge introduced, including your conflict resolutions.
- Immediately after the Skill tool call returns, run `cd <worktree>` via the Bash tool to restore cwd for the remaining steps in this file (Step 5.5, Step 6).

**Why the explicit `cd`:** `codeguide/scripts/resolve.py`'s inline walk only searches from cwd *upward* to the git toplevel — it has no mechanism to find a `_codeguide/` directory that lives in a descendant directory below cwd (i.e. the hub, nested under `git_root`). `codeguide-update/SKILL.md`'s own Step 1 (`resolve.py --json`) and Step 2 (`resolve_scope.py $ARGUMENTS`) take no cwd/root argument at all — the CLI has no `--cwd` flag — so the ambient shell cwd at invocation time is the only lever available. Pinning it to `hub_root` here matches the confirmed repro (running from the hub root resolves correctly; running from git_root in a nested layout does not) without changing `resolve.py`'s shared upward-only walk algorithm, which other flat-layout call sites depend on. This `cd` is intra-worktree (`hub_root` is a subdirectory of the current worktree, not a different worktree), so it does not conflict with the cross-worktree `cd`-to-parent prohibition.

If `_codeguide/Overview.md` is absent → skip silently.
This is the documented convention in `plugins/mill/skills/git-commit/SKILL.md` step 2 and we follow it here for symmetry.
```
- **Commit:** `fix(mill-merge-in): pin cwd to hub_root before invoking codeguide-update, so nested-hub codeguide roots resolve (#880)`

## Batch Tests

`verify: null` — both cards are `SKILL.md` prose edits with no Python code changed. `codeguide/scripts/resolve.py` and `_implementer_common._run_verify_gate` were read to ground the fixes but are not modified by this batch, so there is no new/changed function to unit test. Manual review of the rendered SKILL.md text is the verification for both cards.
