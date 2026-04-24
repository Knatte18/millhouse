# Batch: integration-test

```yaml
task: mill-cleanup script
batch: integration-test
cards: 1
verify: python plugins/mill/integration_tests/test-cleanup.py
depends-on: [cleanup-core]
```

## Batch Scope

End-to-end integration test for `mill-cleanup.py`. Seeds a full hub+wiki fixture under `.scratch/` with six slug scenarios (done, abandoned, live, orphan-worktree, orphan-active, malformed-status). Asserts dry-run plan output, then asserts `--apply` produces the correct artefact removals and one wiki commit.

## Cards

### Card 5: `plugins/mill/integration_tests/test-cleanup.py`

- **Reads:** `plugins/mill/integration_tests/test-spawn.py` (hub+wiki fixture setup pattern — `_setup_pair` helper), `plugins/mill/integration_tests/test-merge.py` (multi-scenario seeding + assertion pattern), `plugins/mill/scripts/mill-cleanup.py` (expected CLI output format).
- **Modifies:** (none)
- **Creates:** `plugins/mill/integration_tests/test-cleanup.py`
- **Requirements:**
  - **Constants:**
    ```python
    HUB = Path(__file__).resolve().parent.parent.parent.parent
    SCRIPTS = HUB / "plugins" / "mill" / "scripts"
    SCRATCH = HUB / ".scratch"
    ```
  - **`_run(cmd, *, cwd, check=True)`** — same signature and implementation as in `test-spawn.py`.
  - **`_git_init(repo)`** — run `git init -b main` (requires Git ≥ 2.28; see foundation batch note), `git config user.email`, `git config user.name`, create an empty initial commit. Mirrors the helper name in `test-worktree.py`.
  - **`_setup_fixture(container: Path) -> tuple[Path, Path, Path]`** — builds the hub+wiki pair and seeds all six scenarios. Returns `(hub, wiki, worktrees_dir)`.
    - Bare wiki + wiki clone + hub repo (same pattern as `test-spawn._setup_pair`).
    - Create `worktrees_dir = container / "worktrees"`.
    - Create dummy initial commit in hub so `git worktree add` works.
    - **Seed six scenarios in wiki and hub:**
      1. **`done-slug`** — `phase: done` residual case:
         - `wiki/active/done-slug/status.md` with `phase: done`.
         - `git -C hub worktree add -b impl/done-slug <worktrees_dir>/done-slug` — real worktree so `git worktree list --porcelain` registers it.
         - Home.md entry: `## Done task [done-slug] [done]`.
      2. **`abandoned-slug`** — `phase: abandoned` + `[active]` marker:
         - `wiki/active/abandoned-slug/status.md` with `phase: abandoned`.
         - `git -C hub worktree add -b impl/abandoned-slug <worktrees_dir>/abandoned-slug`.
         - Home.md entry: `## Abandoned task [abandoned-slug] [active]`.
      3. **`live-slug`** — `phase: implementing`, leave untouched:
         - `wiki/active/live-slug/status.md` with `phase: implementing`.
         - `git -C hub worktree add -b impl/live-slug <worktrees_dir>/live-slug`.
         - Home.md entry: `## Live task [live-slug] [active]`.
      4. **`orphan-wt-slug`** — worktree exists, no `active/` dir:
         - `git -C hub worktree add -b impl/orphan-wt-slug <worktrees_dir>/orphan-wt-slug`.
         - NO `wiki/active/orphan-wt-slug/` created.
         - No Home.md entry.
      5. **`orphan-active-slug`** — `active/` dir exists, no Home.md `[active]` entry:
         - `wiki/active/orphan-active-slug/status.md` with `phase: implementing`.
         - No worktree created.
         - No Home.md entry (or a `[done]` entry — either way, no `[active]`).
      6. **`malformed-slug`** — `active/` dir exists, `status.md` has invalid YAML:
         - `wiki/active/malformed-slug/status.md` content: `\`\`\`yaml\nphase: [unclosed bracket\n\`\`\`` (triggers yaml.YAMLError).
         - No Home.md entry.
    - Write and commit `wiki/Home.md` with all headings. Commit + push to bare.
    - Commit + push all `wiki/active/` files to bare.
    - Set up `hub/.millhouse/wiki` junction to wiki clone.
    - Write `hub/.millhouse/config.local.yaml` with `paths:\n  wiki: <abs path to wiki clone>` so `_paths.resolve_wiki_path` finds it without sibling-path resolution.
  - **Test 1 — dry-run:**
    - `result = _run(["python", str(SCRIPTS / "mill-cleanup.py")], cwd=hub, check=False)`.
    - Assert `result.returncode == 0`.
    - Assert `"REMOVE (done):      done-slug"` in `result.stdout`.
    - Assert `"REMOVE (abandoned): abandoned-slug"` in `result.stdout`.
    - Assert `"Dry-run" in result.stdout`.
    - Assert `"REPORT:" in result.stdout` and `"orphan-wt-slug"` in `result.stdout`.
    - Assert `"REPORT:" in result.stdout` and `"orphan-active-slug"` in `result.stdout`.
    - Assert `"REPORT:" in result.stdout` and `"malformed-slug"` in `result.stdout`.
    - Assert `"live-slug"` NOT in (line starting with `"REMOVE"` in stdout) — live slug must not appear in REMOVE lines.
    - Assert worktree dirs still exist (dry-run did nothing).
    - PASS: `"PASS dry-run: plan output contains correct REMOVE and REPORT lines"`.
  - **Test 2 — apply:**
    - `result = _run(["python", str(SCRIPTS / "mill-cleanup.py"), "--apply"], cwd=hub, check=False)`.
    - Assert `result.returncode == 0`.
    - **Worktree assertions:**
      - `not (worktrees_dir / "done-slug").exists()` — worktree directory removed.
      - `not (worktrees_dir / "abandoned-slug").exists()` — worktree directory removed.
      - `(worktrees_dir / "live-slug").exists()` — live worktree untouched.
      - `(worktrees_dir / "orphan-wt-slug").exists()` — orphan-wt is report-only, not removed.
    - **Branch assertions:** Run `_run(["git", "branch"], cwd=hub)`. Assert `"impl/done-slug"` not in output. Assert `"impl/abandoned-slug"` not in output. Assert `"impl/live-slug"` in output.
    - **Wiki active-dir assertions** (read from wiki clone):
      - `not (wiki / "active" / "done-slug").exists()`.
      - `not (wiki / "active" / "abandoned-slug").exists()`.
      - `(wiki / "active" / "live-slug").exists()`.
      - `(wiki / "active" / "orphan-active-slug").exists()` — report-only, not removed.
    - **Home.md assertions** (read wiki clone Home.md):
      - `abandoned-slug` heading has no `[active]` marker (cleared to unclaimed).
      - `done-slug` heading still has `[done]` (untouched).
      - `live-slug` heading still has `[active]` (untouched).
    - **Wiki commit assertion:**
      - `log = _run(["git", "log", "--oneline", "-3"], cwd=wiki).stdout`.
      - Assert `"chore: cleanup"` in `log`.
    - PASS: `"PASS --apply: correct worktree removals, wiki commit, Home.md resets"`.
  - **Teardown:** if both tests pass, `shutil.rmtree(container)`. On any failure, print `f"Fixture preserved at {container}"` and exit 1.
  - Exit 0 on all PASS, 1 on first failure.
- **Commit:** `test(cleanup): integration test — dry-run + --apply artefact removals`

## Batch Tests

`python plugins/mill/integration_tests/test-cleanup.py` — exercises the real CLI against a real git repo with real wiki push/pull. Requires `git` in PATH. No network (bare wiki is on-disk).
