# Batch: migration-script

```yaml
task: Adopt V3 wiki module in V2 scripts
batch: migration-script
number: 2
cards: 2
verify: uv run --project plugins/mill python plugins/mill/integration_tests/test-wiki-migrate.py
depends-on: [1]
```

## Batch Scope

Deliver the one-shot migration script that seeds `tasks.json` from the current free-form `Home.md` and its `proposal-*.md` siblings, plus the integration test that pins its behaviour. The script is the sole canonical caller of the public `wiki.upsert_tasks_batch` API delivered by batch 1; it uses the same public API as every other caller, with no daemon bypass.

This batch reads (does not modify) the V3 module produced by batch 1. The script lives at `plugins/mill/scripts/millpy-wiki-migrate.py`; the integration test lives at `plugins/mill/integration_tests/test-wiki-migrate.py`. No other files are touched.

External interface delivered: the operator runs `python plugins/mill/scripts/millpy-wiki-migrate.py [--dry-run]` once per wiki to migrate its current state to V3. Net commit count on the wiki: two — `wiki: backup pre-V3 Home.md` followed by `wiki: migrate to V3 (TinyDB-backed)`.

Batch-local decisions:

- **Backup-commit-via-direct-git is intentional.** The daemon is not yet running for the freshly-V3 wiki; bootstrapping the backup commit through `git -C <wiki>` is a single isolated exception to the "daemon owns wiki writes" rule. Justified inline in the script via a docstring at the call site.
- **Idempotent re-run definition:** Running the script twice on an already-migrated wiki produces zero new commits on the second run. TinyDB upsert is idempotent for matching task dicts; daemon's render produces byte-identical files (per batch 1 card 2); `commit_push`'s `git diff --cached --quiet` short-circuits the noop commit. The backup file is overwritten on each run — the first backup is the canonical recovery artifact.

## Cards

### Card 13: `millpy-wiki-migrate.py` — one-shot migration script

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/wiki/_parse.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_timestamp.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/millpy-wiki-migrate.py`
- **Deletes:** none
- **Requirements:** Create a new top-level CLI script following the `millpy-*.py` argparse pattern. Single optional flag `--dry-run` (default: commit). Preconditions (stated in the script's `--help` text and at the top of `main()`):
  - The wiki path must be resolvable via `_paths.resolve_wiki_path` — either sibling discovery finds `<container>/wiki/`, or `paths.wiki:` is set in `<worktree>/.millhouse/config.local.yaml`. The migration script does NOT consult `mill-config.yaml` or `wiki/config.yaml` — `_paths.resolve_wiki_path` reads only `.millhouse/config.local.yaml` and otherwise uses sibling discovery (see `_paths.py:386` `resolve_wiki_path` docstring). The script aborts cleanly via the resolver's own exception on failure; no preflight check is needed.
  - The script is one-shot per wiki. Re-running after a successful first invocation is idempotent (no new daemon commit); see step 6 below for the aborted-prior-run guarantee.

  Behaviour:
  1. Resolve `wiki_path` via `_paths.resolve_wiki_path(_paths.resolve_git_root())`. Abort with a clean error if the resolver raises. Do not add a separate `mill-config.yaml`-exists check — the resolver's contract does not require it.
  2. Read `<wiki_path>/Home.md`. If missing, abort with a clean error.
  3. Parse with `wiki._parse.parse_home_md(home_text)` (the extended parser delivered in batch 1 card 3; pure string-in / list-out per card 3's explicit guarantee — does not initialise `_client` and cannot trigger daemon spawn). For each parsed task with a `[[slug]](proposal-slug.md)` link, read `<wiki_path>/proposal-{slug}.md` if it exists and attach the file's contents as the task's `body` field; missing proposal file -> `body = ""`.
  4. If `--dry-run`: print every parsed task dict (slug, title, group, brief, status, has-body flag) to stdout in ASCII, exit 0. No file writes, no commits, no daemon contact — assert this by not importing `wiki._client` from the module's top-level (lazy-import it only inside the commit-mode branch in step 5d).
  5. Otherwise (commit mode):
     a. Atomic-write `<wiki_path>/Home.md.pre-v3.bak` containing the original `Home.md` text. The file is unconditionally overwritten if it already exists.
     b. Run `git -C <wiki_path> add Home.md.pre-v3.bak`, then `git -C <wiki_path> diff --cached --quiet`. If the diff is empty (returncode 0) — i.e. the backup file content matches what was already committed in a prior successful migration — skip the commit and proceed to step 5c. Otherwise run `git -C <wiki_path> commit -m "wiki: backup pre-V3 Home.md"`. This skip path is the idempotency guarantee for the backup commit on re-run; without it the commit step fails with "nothing to commit" and breaks the `&&` chain. This direct-git step is the one intentional bootstrap-commit exception — document inline in the script's docstring referencing decision `migration-commit-shape`.
     c. Build the full task list as `list[dict]`, each dict containing keys `slug, title, group, brief, body, status` (no `id` — the daemon assigns).
     d. Import `wiki._client` lazily (`from wiki import _client as wiki_client`) and call `wiki_client.upsert_tasks_batch(wiki_path, tasks, message="migrate to V3 (TinyDB-backed)")` (note `wiki_path` is the required first positional argument per batch 1 card 6; the `message` keyword causes the daemon to commit as `wiki: migrate to V3 (TinyDB-backed)` per batch 1 card 5's `_handle_upsert_tasks_batch` payload handling). The daemon's `OP_UPSERT_TASKS_BATCH` handler upserts every task into TinyDB and renders + commits once with that message.
     e. Print a final summary line: `migrated N tasks; M with proposal bodies; backup at <wiki>/Home.md.pre-v3.bak`.

  6. **Aborted-prior-run guarantee.** If a previous run aborted mid-way and left a partial `tasks.json` on disk, re-running is safe: the script always rebuilds the full task list from the current `Home.md` and calls `upsert_tasks_batch` with every task. `Store.upsert_task` is keyed by slug — every entry is brought to its current state regardless of prior partial state. No silent drift is possible because the script never reads from `tasks.json` (it always re-parses `Home.md`), and `upsert_tasks_batch` overwrites each task's fields wholesale. If the operator wants a clean re-migration (e.g. they suspect the partial `tasks.json` is corrupt), they delete `<wiki>/tasks.json` manually before re-running; the script does not auto-delete.

  The script is idempotent: a second invocation after a successful first run produces no new daemon-side commit (TinyDB upsert is no-op for matching dicts; daemon's render is byte-identical; `commit_push` skips the empty commit). The backup file is overwritten and the backup commit may or may not produce a new wiki commit depending on whether the original `Home.md` has drifted — either is acceptable for the first idempotency assertion in card 14.

  Use `_timestamp.now_utc_iso()` only if you print timestamps in stdout summary; do not embed timestamps in commit messages (kept stable per the byte-identical render contract).

  All `print()` output is ASCII only.
- **Commit:** `feat(millpy-wiki-migrate): one-shot V3 migration script`

### Card 14: `test-wiki-migrate.py` — integration test (dry-run, commit, idempotent re-run)

- **Context:**
  - `plugins/mill/scripts/millpy-wiki-migrate.py`
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/integration_tests/test-wiki-e2e.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/integration_tests/test-wiki-migrate.py`
- **Deletes:** none
- **Requirements:** Create a new integration test following the existing `integration_tests/test-wiki-e2e.py` shape (real spawned daemon, real TinyDB, real git repo under `.scratch/`). Fixture is a synthetic wiki under `.scratch/migrate-fixture/` populated with a `Home.md` that mirrors the production shape:
  - Two layer headers: `# Layer D (isolated -- run alone)` (parenthetical preserved) and `# Layer Z`.
  - One ungrouped task before the first layer header.
  - One `## (warn) Wiki/config.yaml ...` info note (no `[slug]` line under it).
  - One task carrying `[active]` marker.
  - One task carrying `[abandoned]` marker.
  - Two tasks with `[[slug]](proposal-slug.md)` links plus matching `proposal-{slug}.md` files containing non-empty bodies.

  Test cases (each runs in a fresh fixture copy):
  - `--dry-run`: assert no `Home.md.pre-v3.bak` written, no new git commits on the wiki, no `<wiki>/tasks.json` file created, no `<wiki>/.wiki-daemon.json` state file created (daemon must not spawn during dry-run per card 13 step 4), parsed task list printed to stdout includes every expected slug.
  - commit mode: assert (1) `Home.md.pre-v3.bak` exists with the original content byte-identical to the input fixture's `Home.md`; (2) `tasks.json` exists with one TinyDB row per migrated task; (3) the newly-rendered `Home.md` is V3-format — `# Layer D` and `# Layer Z` headers (no parenthetical), info-note absent, `[active]`/`[abandoned]` markers present, ungrouped task appears after both layer sections; (4) `proposal-{slug}.md` files for the two body-carrying tasks exist with content matching the fixture inputs; (5) both expected commit messages — `wiki: backup pre-V3 Home.md` AND `wiki: migrate to V3 (TinyDB-backed)` — appear somewhere in the new commit range produced by the migration. Do NOT assert "exactly two new commits": the daemon's `on_start` runs `_ensure_gitignore`, which produces an additional `chore(wiki): gitignore daemon artifacts` commit on a fresh wiki before the migration commit fires. The assertion must tolerate that interleaved commit (allow N >= 2 new commits, with both expected messages present in any order).
  - re-run idempotency: invoke the script a second time on the just-migrated fixture. Assert (a) the script exits 0 (no "nothing to commit" failure — the backup-commit skip path in card 13 step 5b must engage when `Home.md.pre-v3.bak` matches the already-committed backup); (b) `git log` head SHA is unchanged after the second invocation (no new daemon-side commit because TinyDB upsert is no-op and `commit_push` short-circuits the empty diff); (c) no additional backup commit is produced (the skip path in step 5b prevents it).

  Drive the script via `subprocess.run([sys.executable, "plugins/mill/scripts/millpy-wiki-migrate.py", ...], cwd=<task-worktree>)` so the path resolution exercises the real production path.
- **Commit:** `test(wiki-migrate): integration coverage for dry-run, commit, idempotent re-run`

## Batch Tests

The batch verify command is `uv run --project plugins/mill python plugins/mill/integration_tests/test-wiki-migrate.py`. The test fixture lives under `.scratch/migrate-fixture/` (gitignored). After this batch, the migration script can be invoked manually against the real wiki by the operator, but the operator action is out of scope for mill-go — mill-go finishes when the integration test passes.
