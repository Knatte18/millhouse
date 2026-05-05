# Discussion: 4 (A) — mill-setup: --from-url for separate wiki repo

```yaml
task: '4 (A) — mill-setup: --from-url for separate wiki repo'
slug: mill-setup-wiki-url
status: discussing
parent: main
```

## Problem

`mill-setup` Phase 1 hardcodes the wiki URL as `<origin>.wiki.git` (the GitHub-wiki convention). That ties every mill installation to a GitHub wiki attached to the same repo as the primary clone. Some users want a dedicated separate repo as the wiki — for example a single shared `HenrikNORCE/all-codeguides-and-wikis` repo with one branch per project (one-repo-many-branches pattern).

`codeguide-setup` already has a `--from-url <url>` flag for the analogous sibling-clone case. mill-setup should match it, plus a `--branch <name>` flag for the multi-branch pattern (which codeguide-setup does not yet support — that's a separate task, out of scope here).

## Scope

**In:**

- New CLI flags `--from-url <url>` and `--branch <name>` for the `mill-setup` skill (parsed from `$ARGUMENTS` in skill prose, mirroring `codeguide-setup`).
- New nested config block in `.millhouse/config.local.yaml`:
  ```yaml
  wiki:
    repo_url: <url>
    branch: <name>
  ```
  Persisted on first successful clone when CLI flag was given. Subsequent re-runs read from config when CLI not given.
- Phase 1 (Derive wiki URL): precedence `CLI flag > config.local.yaml > derived <origin>.wiki.git`.
- Phase 2 (Reachability): conditional error message — GitHub-wiki message only when no `--from-url` (CLI or config) is in effect; generic "URL unreachable" message otherwise.
- Phase 3 (Clone): if `--branch <name>` and branch exists on remote → `git clone -b <branch> --single-branch <url> <dest>`. If `--branch <name>` and branch missing → `git init <dest>`, `git remote add origin <url>`, `git checkout --orphan <branch>`, `git config branch.<branch>.remote origin`, `git config branch.<branch>.merge refs/heads/<branch>` so the first `_wiki.write_commit_push` (Phase 3.1) pushes upstream-cleanly without modifying the helper.
- New Phase 3.2 (Persist wiki overrides): if `--from-url` or `--branch` was given on the CLI, write the `wiki:` block to `.millhouse/config.local.yaml` (creating the file from template if absent — matching the responsibility shift from Phase 5 to Phase 3.2 only when overrides are present).
- Re-run guard: if `<wiki-dir>` already exists as a git repo and its `origin` URL or current branch mismatches the effective `--from-url`/`--branch`, halt with a clear error telling the user to remove the wiki dir or fix the mismatch manually. Never silently switch.
- New helper `_wiki.clone_or_init(url, branch, dest)` that encapsulates the clone-vs-init-orphan logic and returns a status dict. Called from Phase 3.
- Unit test `plugins/mill/unit_tests/test-wiki-clone-or-init.py` covering the four branches: clone-with-branch, clone-without-branch (remote HEAD), init-orphan, pull-existing.
- mill-setup `SKILL.md` updates: `argument-hint:` frontmatter entry, new arg-parsing step at the top of `## Phases`, updated Phase 1/2/3 prose, new Phase 3.2 prose, usage examples in a new `## Usage` section.

**Out:**

- `--branch` for `codeguide-setup` (separate task — task 3 codeguide-improvements).
- Any rename of the existing `paths.wiki:` (wiki-directory override). Stays put.
- Multi-wiki support, wiki-switching commands, mid-flight URL/branch swap (user must rm + re-run).
- Touching `_wiki.sync_pull` or `_wiki.write_commit_push` — the orphan-branch first push is solved entirely by setting `branch.<name>.remote` + `branch.<name>.merge` via `git config` during init, so the helpers stay unchanged.
- Integration test that hits a real remote. Unit test with mocked `_subprocess_util.run` covers the matrix.

## Decisions

### CLI-flag persistence model

- Decision: CLI flags are primary; on first successful clone they are written to `.millhouse/config.local.yaml` under a new nested `wiki:` block. Subsequent re-runs without flags read from config. Precedence: CLI > config > derived default.
- Rationale: `.millhouse/config.local.yaml` is gitignored and per-machine — the right scope for clone-time decisions that vary per developer. CLI primary keeps the first-run UX simple ("paste this command"); config persistence makes re-runs work without remembering flags, which matches the existing idempotency contract of `mill-setup`.
- Rejected: CLI-only (re-runs after wiki-dir wipe would silently fall back to default GitHub wiki, surprising the user). Config-only (impossible on first run before the file exists). Always-persist (clutters config.local.yaml with derivable defaults).

### Config schema — nested `wiki:` block

- Decision: Use nested keys `wiki.repo_url:` and `wiki.branch:` rather than top-level `wiki_repo_url:` / `wiki_branch:`.
- Rationale: Coherent grouping for future wiki-related keys; pairs naturally with the existing `paths.wiki:` (directory override) without colliding with it. Matches the nesting style already used elsewhere (`review.discussion.rounds`, `pipeline.builder`).
- Rejected: Top-level keys (proposal-verbatim but doesn't scale). Reuse of `paths:` block (semantic mismatch — these aren't paths).

### Branch default when `--branch` omitted

- Decision: Use the remote's HEAD / default branch — no `-b` argument to `git clone`.
- Rationale: Matches user intuition for `git clone <url>` of any repo; avoids hardcoding `main` or `master`. The remote decides.
- Rejected: Default to `main` (breaks any wiki on `master`). Halt requiring explicit `--branch` (over-strict; the GitHub-wiki path doesn't pass `--branch` either).

### Mismatch on re-run — halt, never overwrite

- Decision: If `<wiki-dir>` already exists as a git repo and its `origin` URL or current branch differs from the effective CLI/config values, halt with an explicit error.
- Rationale: Same principle as the existing Phase 3 step 3 ("dir exists but is not a git repo → halt"). mill-setup never silently destroys user data; the user must fix the mismatch manually (rm the wiki dir, fix the flag, or fix the config).
- Rejected: Auto-fix (changes remote / checks out new branch — destroys data on a typo). Skip flags silently (silently stale state — confusing).

### Phase 2 reachability message — conditional

- Decision: Without `--from-url` in effect (neither CLI nor config), keep the existing GitHub-wiki guidance ("Open `https://github.com/<owner>/<repo>/wiki`, create the Home page"). With `--from-url` in effect, swap to a generic "URL `<url>` unreachable — check credentials, URL, and network".
- Rationale: The GitHub-wiki message is misleading when the user is targeting a normal repo (no Home page workflow there). Conditional branching keeps both flows clear.
- Rejected: Drop Phase 2 entirely when `--from-url` (loses the early-failure benefit — bad URL would surface as a confusing `git clone` failure later). Same message either way (misleading for non-GitHub URLs).

### Orphan-branch first-push — set upstream during init

- Decision: When `--branch <name>` is given and the branch does not exist on remote, run `git init`, `git remote add origin <url>`, `git checkout --orphan <name>`, then `git config branch.<name>.remote origin` and `git config branch.<name>.merge refs/heads/<name>`. The subsequent `_wiki.write_commit_push` calls (Phase 3.1 config.yaml, Phase 6 Home.md, Phase 6a _Sidebar.md) use plain `git push` because upstream tracking is already configured.
- Rationale: Keeps `_wiki.write_commit_push` unchanged — that helper is depended on across the whole codebase and we do not want to thread "is this the first push?" logic through it. Setting `branch.*.remote`/`merge` is exactly what `git push -u origin <branch>` does internally; we just do it up front.
- Rejected: Modify `_wiki.write_commit_push` to detect "no upstream" failure and retry with `-u` (mutates a stable, widely-used helper for one bootstrap edge case). Make a no-op initial commit during Phase 3 + push (extra commit clutters history).

### Helper extraction — `_wiki.clone_or_init`

- Decision: New helper `_wiki.clone_or_init(url: str, branch: str | None, dest: Path) -> dict` encapsulates the clone-vs-init-orphan-vs-pull logic. SKILL.md Phase 3 calls the helper.
- Rationale: Unit-testable with a mocked `_subprocess_util.run`. Keeps SKILL.md prose short. Centralises the upstream-tracking config so the orphan path is correct.
- Rejected: Inline all logic in SKILL.md prose (untestable, longer prose). New module `_setup_wiki.py` (one logical operation — overkill).

### Argument-parsing pattern

- Decision: Mirror `codeguide-setup`. Add `argument-hint: "[--from-url <url>] [--branch <name>]"` to mill-setup `SKILL.md` frontmatter. New first step at the top of `## Phases`: parse `$ARGUMENTS`, extract `--from-url <url>` and `--branch <name>`. Unknown tokens halt with a usage hint.
- Rationale: Consistent with sibling skill; agent-driven parsing is already idiomatic in this codebase.
- Rejected: Custom positional format (loses agent's existing parsing patterns). Move parsing into a Python helper (overkill — two flags).

### Persistence write — Phase 3.2 location and yaml handling

- Decision: New Phase 3.2 runs immediately after Phase 3 succeeds. If either `--from-url` or `--branch` was supplied on the CLI, write the `wiki:` block into `.millhouse/config.local.yaml`. If the file does not exist yet, copy the template body first then add the block. If it does exist, parse the yaml, set the keys, dump back. Comments in `.millhouse/config.local.yaml` are lost on rewrite — accepted because the file is gitignored and per-machine (low UX cost). Phase 5 then sees the file already exists and skips its template copy (existing behavior); Phase 4.9 still updates `hub_relative_path:` in place (existing behavior — already handles "file exists" case via regex).
- Rationale: Co-locates the persistence with the operation that produces the values. Phase 4.9 / Phase 5 logic for `hub_relative_path:` is unchanged. yaml load+dump is straightforward; the regex-style update used for `hub_relative_path:` would be brittle for nested keys.
- Rejected: Phase 5.5 amendment (puts the write after a phase that's a no-op for the relevant case — confusing ordering). Inline branching in Phase 5 (Phase 5 stays minimal — better to keep concerns separate). `ruamel.yaml` for comment preservation (new dep for marginal UX win on a gitignored file).

## Technical context

### Existing helpers / modules involved

- `plugins/mill/scripts/_wiki.py` — already holds `sync_pull`, `write_commit_push`, `acquire_lock`, `release_lock`, `read_hardlinks`. New `clone_or_init` belongs here.
- `plugins/mill/scripts/_subprocess_util.py` — `_subprocess_util.run(argv)` is the existing wrapper that returns a result with `returncode`, `stdout`, `stderr`. All git calls in `_wiki.py` already use it. Mock target for the unit test.
- `plugins/mill/scripts/_paths.py` — `resolve_wiki_path(git_toplevel)` reads `paths.wiki:` override from `.millhouse/config.local.yaml`. Stays unchanged. (The wiki *directory* override and the new wiki *URL/branch* override are independent: `paths.wiki:` controls where the clone lives, `wiki.repo_url:` / `wiki.branch:` control what's cloned.)
- `plugins/mill/scripts/_setup.py` — `create_hub_links` (Phase 4). Untouched by this task.
- `plugins/mill/scripts/_render.py`, `_vscode.py`, `_shortcuts.py`, `_sidebar.py`, `_gitignore.py`, `_junction.py` — all untouched.

### Skill-level files

- `plugins/mill/skills/mill-setup/SKILL.md` — primary edit target. Frontmatter `argument-hint:`, new arg-parsing step, edits to Phase 1 / Phase 2 / Phase 3, new Phase 3.2, new `## Usage` section near the top with worked examples.
- `plugins/mill/templates/config.local.yaml` — add commented-out `wiki:` block scaffold so users discover the keys (still verbatim-copied by Phase 5 in the no-flag case).

### Argument-parsing reference

`codeguide-setup` SKILL.md (`plugins/codeguide/skills/codeguide-setup/SKILL.md`) line 33-37 is the closest existing pattern. The agent reads `$ARGUMENTS` and extracts flags by token-walking; mill-setup mirrors the same prose pattern (there is no shared parsing helper).

### `_subprocess_util.run` shape

Each call returns an object with `.returncode`, `.stdout`, `.stderr` (strings). Tests mock this by patching `_wiki._subprocess_util.run` with a callable that returns a stub object — no need for `unittest.mock.patch` over the whole subprocess module.

### Branch existence check

Use `git ls-remote --heads <url> <branch>`. Empty stdout (with returncode 0) → branch missing → init+orphan path. Non-empty stdout → branch exists → clone -b. Non-zero returncode → URL unreachable → propagate as the Phase 2 reachability error.

### `.millhouse/config.local.yaml` shape on first-run with `--from-url`

After Phase 3.2 (with `--from-url X --branch B`):

```yaml
hub_relative_path: .          # set by Phase 4.9 in the no-overrides path; in
                              # this path Phase 4.9 still writes it after Phase 3.2
wiki:
  repo_url: X
  branch: B
```

Comments from the template are lost (acceptable — gitignored, per-machine).

### `.millhouse/config.local.yaml` shape with no flags (no behavior change)

Phase 5 verbatim-copies the template, Phase 4.9 sets `hub_relative_path:`. No `wiki:` block is written. Existing behavior preserved.

## Constraints

- **Plugin-cache discipline.** All new code paths follow the existing rule: scripts referenced from SKILL.md use `${CLAUDE_PLUGIN_ROOT}/scripts/...`, not `plugins/mill/scripts/...`. The mill-setup-specific inline `PYTHONPATH=` prefix continues to apply (mill-setup is the bootstrapper that creates the global PYTHONPATH user env var).
- **Idempotency on every phase.** Re-running `mill-setup` after a partial or full setup must remain a no-op when state already matches. Specifically: Phase 3.2's yaml write must be a no-op when the existing `wiki:` block already matches the effective values (load + compare + skip dump if equal).
- **Junctions are never code paths.** No new junction handling needed for this task.
- **Working state never lives in the wiki.** The wiki at the new URL/branch holds only `Home.md`, `_Sidebar.md`, `config.yaml` — same as before. mill-setup's writes to the wiki (Phase 3.1, 6, 6a) are unchanged.
- **No `CONSTRAINTS.md` was found** at hub root; nothing else to enumerate.

## Testing

### Unit test: `plugins/mill/unit_tests/test-wiki-clone-or-init.py`

TDD candidate. Mock `_subprocess_util.run` (the only external surface). Cases:

1. **Clone with explicit branch — branch exists on remote.**
   - `dest` does not exist; `ls-remote --heads <url> <branch>` returns non-empty.
   - Expect: one `git clone -b <branch> --single-branch <url> <dest>` call.
   - Returned dict: `{action: 'cloned', branch_existed_on_remote: True}`.

2. **Init orphan — branch missing from remote.**
   - `dest` does not exist; `ls-remote --heads <url> <branch>` returns empty (rc=0).
   - Expect: `git init <dest>`, `git remote add origin <url>`, `git checkout --orphan <branch>`, `git config branch.<branch>.remote origin`, `git config branch.<branch>.merge refs/heads/<branch>`.
   - Returned dict: `{action: 'initialized', branch_existed_on_remote: False}`.

3. **Clone without branch — remote HEAD.**
   - `dest` does not exist; `branch is None`. Skip `ls-remote --heads` check.
   - Expect: `git clone <url> <dest>`.
   - Returned dict: `{action: 'cloned', branch_existed_on_remote: None}`.

4. **Pull existing.**
   - `dest` exists, `dest/.git` exists, `git -C <dest> remote get-url origin` matches `<url>`, `git -C <dest> branch --show-current` matches `<branch>` (or both `None`/match-remote-HEAD).
   - Expect: `git -C <dest> pull --ff-only`.
   - Returned dict: `{action: 'pulled', branch_existed_on_remote: None}` (or carry over).

5. **Halt — dest exists but not a git repo.** Existing behavior preserved.
   - Expect: raise (existing exception type or new `WikiSetupError`).

6. **Halt — origin URL mismatch.**
   - `dest` exists & is a git repo; `origin` URL ≠ `<url>`.
   - Expect: raise with explicit message naming both URLs.

7. **Halt — branch mismatch.**
   - `dest` exists, origin matches, branch differs from `<branch>`.
   - Expect: raise with explicit message naming both branches.

8. **Reachability failure.**
   - `ls-remote` (or `git clone`) returns non-zero with network-style stderr.
   - Expect: raise (caller — Phase 2 — will translate to user-facing message).

In-memory only: use `tempfile.TemporaryDirectory()` for `dest` paths; never hit a real remote. Match the existing unit-test style under `plugins/mill/unit_tests/`.

### No new integration test

The existing integration-test fixture pattern (`plugins/mill/integration_tests/`) could host an end-to-end test using a local bare repo as `<url>`, but the unit test covers the surface area without the cost. Kept out of scope per Q11.

### Existing tests to re-run

After implementation: `python plugins/mill/unit_tests/run-all.py`. No expected regressions — the existing `_wiki` tests cover `sync_pull` / `write_commit_push` and remain untouched.

## Q&A log

- **Q:** Should `--from-url` / `--branch` be CLI-only, config-only, or both? **A:** Both — CLI primary, persisted to `.millhouse/config.local.yaml` under a nested `wiki:` block on first successful clone. Re-runs without flags read from config. Precedence CLI > config > derived `<origin>.wiki.git`.
- **Q:** Top-level config keys (`wiki_repo_url:` / `wiki_branch:`) or nested (`wiki.repo_url:` / `wiki.branch:`)? **A:** Nested. Coherent grouping; matches existing nested-key idiom (`review.discussion.rounds`, `pipeline.*`).
- **Q:** Default branch when `--branch` is omitted but `--from-url` is given? **A:** Remote HEAD — no `-b` to `git clone`. Whatever the remote default branch is.
- **Q:** Behavior when `<wiki-dir>` already exists with mismatched URL or branch? **A:** Halt. Never silently switch. User fixes manually.
- **Q:** Phase 2 error message — keep the GitHub-wiki guidance always? **A:** Conditional. GitHub-wiki message only when no `--from-url` is in effect; generic message otherwise.
- **Q:** How to make the orphan-branch first push work without modifying `_wiki.write_commit_push`? **A:** During Phase 3 init+orphan, run `git config branch.<branch>.remote origin` and `git config branch.<branch>.merge refs/heads/<branch>` — this is what `git push -u` does internally. Subsequent `_wiki.write_commit_push` calls succeed unchanged.
- **Q:** Inline the clone-or-init logic in SKILL.md prose, or extract to a helper? **A:** Helper `_wiki.clone_or_init(url, branch, dest)`. Unit-testable; SKILL.md stays terse.
- **Q:** Argument parsing — codeguide-setup-style prose, custom format, or Python helper? **A:** codeguide-setup-style prose. Two flags don't justify a helper.
- **Q:** When to write the persistence keys to `.millhouse/config.local.yaml`? **A:** Only when CLI flag was given (not when default GitHub-wiki applies). Avoids polluting the gitignored config with derivable defaults.
- **Q:** Comment preservation when rewriting `.millhouse/config.local.yaml`? **A:** Lose comments on rewrite. yaml load + dump. The file is gitignored and per-machine — low UX cost. No `ruamel.yaml` dependency added.
- **Q:** Test coverage scope? **A:** Unit test of `_wiki.clone_or_init` with mocked `_subprocess_util.run`. No integration test against a real remote.
- **Q:** CLI vs config precedence on re-run? **A:** CLI flag > config.local.yaml > derived default. Standard precedence; CLI overrides.
- **Q:** Where in the phase order does the persistence write happen? **A:** New Phase 3.2 immediately after Phase 3 clone succeeds. When file doesn't exist yet, Phase 3.2 takes over the template seed (only in the override case); Phase 5 then skips. Phase 4.9 (`hub_relative_path:`) still works because it already handles the "file exists" case.
