# Batch: setup-migration

```yaml
task: 57 (A) -- Move config.yaml and agents.yaml from wiki to hub worktree
batch: setup-migration
number: 3
cards: 3
verify: python plugins/mill/integration_tests/test-migration.py
depends-on: [1]
```

## Batch Scope

This batch ships the mill-setup-side migration of existing hubs: a new dedicated script `millpy-migrate-config.py` that the mill-setup skill invokes from a new Phase 3.0b, the SKILL.md edits (Phase 3.1 retargeting, Phase 3.0b insertion, Phase 4.95 deletion, summary cleanup), and a new integration test that exercises the migration end-to-end with a real git wiki fixture.

This batch is independent of batch 2 (loaders refactor): the migration script does NOT call any of the rewritten loaders -- it operates purely at the filesystem + git layer (read YAML, compare, copy bytes, `git rm`, `git add`, push wiki). The batch consumes batch 1's new `mill-config.yaml` template (for Phase 3.1's seed step) and `mill-agents.yaml` template (for the agents-diff branch).

External interface for downstream batches: the new script `millpy-migrate-config.py` exists at the standard scripts path; the SKILL.md's Phase 4.95 is removed; the SKILL.md's summary no longer references machine config. Batch 4 (cleanup) deletes `_machine.py` -- after this batch removes Phase 4.95 and batch 2 removes the two loader callsites, `_machine.py` has no callers.

Batch-local decisions:

- The migration script is invoked from mill-setup Phase 3.0b via the standard cache-form Python venv invocation per CLAUDE.md. The script must run cleanly from a non-hub cwd too (e.g. when invoked from a fresh shell) -- it derives `git_root` via `_paths.resolve_git_root()` and refuses to run if cwd is inside the wiki (the helper enforces this).
- The wiki-side commits are tagged `chore(migrate): remove wiki/config.yaml (moved to hub/mill-config.yaml)` and `chore(migrate): remove wiki/agents.yaml (moved to plugin template)` so the wiki history records the move.
- The script's exit code is 0 for success, 0 for warn-and-skip (agents differ), non-zero only for I/O or git failures. The mill-setup phase narrative explicitly tells the operator to inspect stderr for warn lines and to act on them.
- The integration test uses `.scratch/test-migration/` for fixtures (matches the existing `test-inspect.py` style at `plugins/mill/integration_tests/test-inspect.py`). It creates a bare-remote git wiki via `git init --bare` and clones from it so the push step is verifiable.

## Cards

### Card 19: New script `millpy-migrate-config.py`

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/templates/mill-config.yaml`
  - `plugins/mill/templates/mill-agents.yaml`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/millpy-migrate-config.py`
- **Deletes:** none
- **Requirements:** Create a new CLI script. Top-level structure: shebang, module docstring (one paragraph explaining purpose + invocation), imports (`pathlib.Path`, `sys`, `shutil`, `yaml`, plus local `_paths`, `_wiki`, `_subprocess_util`). Define a `main() -> int` returning the process exit code. `if __name__ == "__main__": sys.exit(main())`.

  `main()` steps:

  1. Resolve `git_root = _paths.resolve_git_root()`. (The helper itself refuses to run when cwd is inside the wiki.) Print `[migrate] hub root: <git_root>` (ASCII).
  2. Resolve `wiki_path = _paths.resolve_wiki_path(git_root)`. If the resolution raises (no wiki configured), print `[migrate] no wiki configured -- nothing to migrate` and return 0.
  3. Resolve plugin-template paths: `plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT") or (Path(__file__).resolve().parent.parent)`. `plugin_config_template = Path(plugin_root) / "templates" / "mill-config.yaml"`. `plugin_agents_template = Path(plugin_root) / "templates" / "mill-agents.yaml"`. (Match the helper logic from `_config._resolve_plugin_template_path` -- prefer importing that helper from `_config` if available; otherwise inline the two-line resolution. Do NOT depend on import order subtleties.)
  4. **Config migration:**
     - `wiki_config = wiki_path / "config.yaml"`. `hub_config = git_root / "mill-config.yaml"`.
     - If `wiki_config` does NOT exist: print `[migrate] no wiki/config.yaml -- config migration skipped` and proceed to agents migration.
     - Elif `wiki_config` exists AND `hub_config` does NOT exist: copy via `shutil.copyfile(wiki_config, hub_config)`. Run `_subprocess_util.run(["git", "-C", str(git_root), "add", "mill-config.yaml"])` (or the project's standard helper). Print `[migrate] mill-config.yaml staged at <hub_config>; commit it on the main branch to land the migration` (ASCII).
     - Elif both exist: print `[migrate] mill-config.yaml already exists at hub root -- skipping copy`.
     - Either way, when `wiki_config` exists, delete it from the wiki. Use a direct commit+push sequence (NOT `_wiki.write_commit_push`, which begins with `git add -- <paths>` and would fail on the now-deleted path). The sequence, inside `with _wiki.wiki_lock(wiki_path, slug="migrate-config"):`, is: (i) `_subprocess_util.run(["git", "-C", str(wiki_path), "rm", "config.yaml"])` -- this stages the deletion; (ii) `_subprocess_util.run(["git", "-C", str(wiki_path), "commit", "-m", "chore(migrate): remove wiki/config.yaml (moved to hub/mill-config.yaml)"])` -- if this returns nonzero AND its combined stdout/stderr contains "nothing to commit", treat it as success and skip the push (the file was already removed in a prior run); otherwise on nonzero raise a clear error; (iii) `_subprocess_util.run(["git", "-C", str(wiki_path), "push"])` -- on nonzero rejection (`"non-fast-forward"` or `"rejected"` in stderr) run `_subprocess_util.run(["git", "-C", str(wiki_path), "pull", "--rebase"])` and retry the push exactly once; if the rebase fails, run `git rebase --abort` and raise an error. The retry policy mirrors `_wiki._write_commit_push_body` lines 408-426 so the rebase-on-reject UX matches the rest of the codebase. Print `[migrate] wiki/config.yaml deleted and pushed`.
  5. **Agents migration:**
     - `wiki_agents = wiki_path / "agents.yaml"`.
     - If `wiki_agents` does NOT exist: print `[migrate] no wiki/agents.yaml -- agents migration skipped` and proceed.
     - Else load both files: `wiki_data = yaml.safe_load(wiki_agents.read_text(encoding="utf-8")) or {}`. `template_data = yaml.safe_load(plugin_agents_template.read_text(encoding="utf-8")) or {}` (handle missing template by treating as empty dict and warning).
     - If `wiki_data == template_data` (deep equality): delete the wiki file using the SAME direct commit+push sequence described in step 4 (git rm; git commit with "nothing to commit" tolerance; git push with one rebase-retry on non-fast-forward). The commit message is `chore(migrate): remove wiki/agents.yaml (moved to plugin template)`. Wrap in the same `with _wiki.wiki_lock(wiki_path, slug="migrate-config"):` block (the lock helper is re-entrant via held-lock counter; nesting OR sequencing under one block is safe). Print `[migrate] wiki/agents.yaml identical to plugin template -- deleted and pushed`.
     - Else: compute the differing entries. For each agent name in `wiki_data` NOT in `template_data`, OR present in both but with different specs, emit one stderr line: `[migrate] WARN: wiki/agents.yaml differs from plugin template -- entry '<name>' is unique or modified` (ASCII). After listing every diff, emit one summary line to stderr: `[migrate] WARN: wiki/agents.yaml NOT deleted -- copy unique entries above into .millhouse/agents.local.yaml and re-run mill-setup` (ASCII). Return 0 (warn, not failure).
  6. **Machine-config-removal notice:** print to stderr (ASCII) `[migrate] note: the per-machine config layer (~/.millhouse/config.machine.yaml) has been removed -- if you previously kept overrides there, move them into this hub's .millhouse/config.local.yaml`. Print unconditionally (cheap operator-friendly reminder).
  7. Return 0.

  Idempotency: a second invocation after a successful migration finds `wiki/config.yaml` absent (step 4 exits early) and `wiki/agents.yaml` absent (step 5 exits early). The machine-config notice still prints; that is acceptable. Exit code stays 0.

  Error handling: wrap step 4's git operations in a try/except that catches `_subprocess_util.SubprocessError` (or whatever the local convention is); on failure, print `[migrate] ERROR: <message>` to stderr and return 1. Do NOT swallow git failures silently. All exceptions bubble up to a top-level catch in `main()` that converts to exit code 1.

  All print statements ASCII only. Use only `_paths`, `_wiki`, `_subprocess_util` for filesystem/git helpers -- do NOT call `subprocess.run` directly (consistency with the rest of `scripts/`).

  Module docstring must mention: (a) what the script does in one sentence, (b) idempotency guarantee, (c) the standard cache-form invocation line per CLAUDE.md conventions (i.e. `PYTHONPATH=... .venv/Scripts/python.exe scripts/millpy-migrate-config.py`).
- **Commit:** `feat(migrate): add millpy-migrate-config.py script`

### Card 20: mill-setup SKILL.md -- retarget Phase 3.1, add Phase 3.0b, remove Phase 4.95, fix summary

- **Context:**
  - `plugins/mill/scripts/millpy-migrate-config.py`
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Four discrete narrative edits in `plugins/mill/skills/mill-setup/SKILL.md`:

  **(a) Phase 3.1 retarget (current lines 157-203, heading `### Phase 3.1 -- Seed wiki/config.yaml from template`):** Rename the heading to `### Phase 3.1 -- Seed mill-config.yaml at hub repo root from template`. Rewrite the body so the target file is `<repo_root>/mill-config.yaml` (NOT `<wiki-dir>/config.yaml`) and the source template is `${CLAUDE_PLUGIN_ROOT}/templates/mill-config.yaml`. The phase still has two cases (case 1: dest missing -- copy + `git add` only; case 2: dest present -- run the block-level upsert that fills any required top-level blocks). For case 1, replace the `_wiki.write_commit_push` call with a `git -C <repo_root> add mill-config.yaml` + a printed reminder to the operator: `mill-config.yaml staged at <repo_root>/mill-config.yaml -- commit it on the main branch to land the migration` (CLAUDE.md hard rule: never auto-commit on the main branch). For case 2, the upsert still uses `yaml.safe_load`/`yaml.dump` on the dest file but the dest is now `<repo_root>/mill-config.yaml`. After upserting, `git add mill-config.yaml` (no commit). The "Why verbatim copy" paragraph at the end of Phase 3.1 stays applicable -- update its file references accordingly. ASCII only.

  **(b) Phase 3.0b insertion (new phase, place IMMEDIATELY BEFORE Phase 3.1 -- not after Phase 3.2).** New heading `### Phase 3.0b -- Migrate wiki config and agents to hub/plugin`. The phase is numbered 3.0b (not 3.2b) to make execution order match SKILL.md reading order: migration MUST run before the new Phase 3.1 (which seeds `mill-config.yaml` from the plugin template). If 3.1 ran first against an existing hub with a custom `wiki/config.yaml`, Phase 3.1 case-1 (dest missing) would seed template defaults to `<repo_root>/mill-config.yaml`, then the migration script would detect both files exist, skip the copy, and delete `wiki/config.yaml` -- silently throwing away the operator's customisations. By running migration first, the script copies `wiki/config.yaml` content to `mill-config.yaml` (user content preserved); then Phase 3.1 case-2 (dest present) runs the block-level upsert against the now-populated hub file, filling only the blocks that were missing from the user's config.

  Body: open with a one-paragraph summary explaining this phase invokes `millpy-migrate-config.py` to (a) copy `wiki/config.yaml` to the hub root if not yet present, (b) delete the wiki copy and push, (c) diff `wiki/agents.yaml` against the plugin template and either delete (identical) or warn-and-skip (different). Then a callout box (or short paragraph) titled "**Ordering constraint:**" stating verbatim: "Phase 3.0b MUST execute before Phase 3.1. If Phase 3.1 ran first against a hub with an existing `wiki/config.yaml`, the operator's custom config would be overwritten by the plugin template's defaults and then silently deleted from the wiki. Do NOT reorder these phases." Then the invocation block in the standard cache-form pattern:

  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-migrate-config.py"
  ```

  After the invocation block, a bulleted summary of what the operator should expect to see in the script output (the three config-migration cases, the two agents-migration cases, the machine-config-removal notice). Close with one paragraph: "Idempotency: re-running mill-setup after a successful migration is a no-op for this phase. If the agents migration warned with diffs, copy the unique entries from the printed list into `.millhouse/agents.local.yaml` and re-run mill-setup to retry the agents step." ASCII only.

  **(c) Phase 4.95 deletion (current lines 420-440):** Delete the entire phase heading and body. Do NOT leave a placeholder. Re-read the surrounding context (Phase 4.9 ends around line 418; Phase 5 begins around line 442) and confirm no incidental references to `_machine.probe`, `_machine.MISSING`, `_machine.PRESENT`, `_machine.MALFORMED`, or `config.machine.yaml` survive elsewhere in the SKILL.md. Search-and-update if any are found outside Phase 4.95.

  **(d) Final summary cleanup (Phase 8 -- current lines 504-553):** Remove the bullet at line 516 ("Machine-level config at `~/.millhouse/config.machine.yaml`..." -- the whole bullet about `_machine.probe()`). Remove the `Machine config:` line from the summary block (currently line 536, inside the triple-backtick block). Remove the explanatory paragraph at line 553 ("`Machine config:` format: when `_machine.probe()` returns..."). The remaining bullets and summary lines are preserved with their relative order. ASCII only.

  At the end of all four edits, grep `_machine` and `config.machine.yaml` in `plugins/mill/skills/mill-setup/SKILL.md` to confirm zero hits.
- **Commit:** `feat(mill-setup): add Phase 3.0b config migration; remove Phase 4.95`

### Card 21: New integration test `test-migration.py`

- **Context:**
  - `plugins/mill/scripts/millpy-migrate-config.py`
  - `plugins/mill/integration_tests/test-inspect.py`
  - `plugins/mill/templates/mill-agents.yaml`
- **Edits:** none
- **Creates:**
  - `plugins/mill/integration_tests/test-migration.py`
- **Deletes:** none
- **Requirements:** Create a new integration test file modeled on `plugins/mill/integration_tests/test-inspect.py`. Top-level structure: module docstring, imports (`os`, `subprocess`, `sys`, `shutil`, `yaml` if helpful, `pathlib.Path`, plus the script-path constants `HUB`, `SCRIPTS`, `PLUGIN_ROOT`, `SCRATCH` -- copy the pattern from `test-inspect.py` lines 1-30). Define `_run`, `_git_init`, and a `_make_hub_with_wiki(slug: str)` fixture helper that:

  - Creates a `<SCRATCH>/test-migration/<slug>/` directory tree with a bare wiki remote, a wiki clone, and a hub repo (real `git init`).
  - Seeds `<wiki>/config.yaml` with a small valid YAML body (e.g. `{key: from_wiki_yaml}`).
  - Seeds `<wiki>/agents.yaml` per-case (identical-to-template OR with-extra-entry).
  - Commits and pushes the wiki to the bare remote.
  - Returns `(hub_path, wiki_path, bare_remote_path)`.

  Test cases (one function per case, `def test_<name>():` that returns 0 on pass, raises AssertionError or returns 1 on fail). A top-level `main()` runs every case and returns the aggregate exit code (0 if all pass, 1 otherwise). Cases:

  - **`test_config_migration_plain_copy`**: hub has no `mill-config.yaml`, wiki has `config.yaml`. Run `millpy-migrate-config.py` as subprocess (set cwd to hub). Assert: `<hub>/mill-config.yaml` exists, its content equals the wiki's original `config.yaml`. Assert `git -C <hub> diff --cached --name-only` includes `mill-config.yaml`. Assert `<wiki>/config.yaml` is deleted from the working tree. Assert the bare remote received the wiki commit (verify via `git -C <bare> log --oneline -- config.yaml` shows a removal commit, or `git -C <wiki> log --oneline` shows the migrate commit and `git -C <wiki> push --dry-run` succeeds).
  - **`test_config_migration_skip_copy_when_hub_already_has`**: hub already has `mill-config.yaml` with distinct content; wiki still has `config.yaml`. Run migration. Assert: hub `mill-config.yaml` unchanged, wiki/config.yaml deleted + pushed.
  - **`test_agents_migration_identical_deletes`**: wiki/agents.yaml byte-equal to the plugin template `plugins/mill/templates/mill-agents.yaml` (resolve via `PLUGIN_ROOT`). Run migration. Assert wiki/agents.yaml deleted, no warning on stderr (only informational lines), exit code 0.
  - **`test_agents_migration_different_warns_and_skips`**: wiki/agents.yaml has an extra entry not in the plugin template. Run migration. Capture stderr. Assert wiki/agents.yaml NOT deleted, stderr contains `WARN` lines naming the extra entry, exit code 0.
  - **`test_idempotency`**: run migration twice in succession on a fresh fixture. Second run prints "nothing to migrate" (or similar -- match what the script actually emits) and is a no-op (no extra commits in wiki, hub `mill-config.yaml` unchanged).

  Test runner pattern: print `PASS test-migration.py: <case_name>` on success and `FAIL test-migration.py: <case_name>` + exception details on failure. Match the success/failure-print pattern of `test-inspect.py`. The `<SCRATCH>/test-migration/` dir is preserved across runs (per existing convention) -- each case creates a fresh `<slug>` subdir to avoid cross-case contamination. ASCII only in all assertions and prints.

  Invocation pattern for the script under test:

  ```python
  env = os.environ.copy()
  env["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
  env["PYTHONPATH"] = str(SCRIPTS)
  result = subprocess.run([sys.executable, str(SCRIPTS / "millpy-migrate-config.py")], cwd=str(hub_path), env=env, capture_output=True, text=True, encoding="utf-8")
  ```

  The test file is runnable directly: `python plugins/mill/integration_tests/test-migration.py`. Exit code 0 on full pass, 1 on any case failure.
- **Commit:** `test(integration): cover config migration phase`

## Batch Tests

The `verify:` runs the new integration test. The migration script's filesystem semantics are tested end-to-end with a real git wiki bare remote. Unit-level coverage of the script's helper functions is intentionally minimal -- the script is a thin CLI orchestrator over already-tested helpers (`_wiki`, `_paths`, `_subprocess_util`); the integration test covers the orchestration. SKILL.md narrative edits in card 20 are reviewed visually -- no runnable surface for SKILL.md per se.
