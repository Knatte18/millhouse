# Batch: skill-and-template

```yaml
task: '4 (A) — mill-setup: --from-url for separate wiki repo'
batch: skill-and-template
cards: 2
verify: null
depends-on: [helpers]
```

## Batch Scope

This batch wires the helpers from batch `helpers` into mill-setup's behaviour and surfaces the new flags to the user. After this batch:

- `mill-setup` accepts `--from-url <url>` and `--branch <name>` flags, parsed from `$ARGUMENTS` in skill prose.
- A new Phase 0 (Parse arguments) extracts the flags before any phase runs.
- Phase 1 derives the effective wiki URL via `CLI > config.local.yaml > <origin>.wiki.git` precedence.
- Phase 2's reachability error message is conditional on the URL source.
- Phase 3 calls `_wiki.clone_or_init(url, branch, dest)` instead of inline clone/pull logic.
- New Phase 3.2 persists `wiki.repo_url` / `wiki.branch` to `.millhouse/config.local.yaml` via `_config.set_local_wiki_overrides` whenever a CLI flag was supplied this run.
- The `templates/config.local.yaml` template gains a commented-out `wiki:` block scaffold that documents the keys for users who later edit the file by hand.

`verify: null` — these are documentation/template changes; no runnable batch-level assertion. The implementer should manually re-read the rendered SKILL.md flow end-to-end to confirm the precedence and conditional-message branches read correctly.

Batch-local decision: arg parsing is prose-level (token-walk in skill instructions), not a Python helper. Unknown CLI tokens halt with usage-hint text rendered inline in the skill.

## Cards

### Card 5: Update mill-setup `SKILL.md` for `--from-url` / `--branch`

- **Reads:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
  - `plugins/codeguide/skills/codeguide-setup/SKILL.md`
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_config.py`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Edit `plugins/mill/skills/mill-setup/SKILL.md` so the rendered skill supports the two new flags end-to-end. Every change below is in-place editing of the existing file — do not duplicate sections, do not move existing prose.

  **Frontmatter.** Add an `argument-hint:` line to the existing YAML frontmatter (after `description:` — match the position used by `codeguide-setup`'s SKILL.md):

  ```yaml
  argument-hint: "[--from-url <url>] [--branch <name>]"
  ```

  Keep `name:` and `description:` lines unchanged.

  **New `## Usage` section.** Insert immediately before the existing `## When to invoke` section. Worked examples:

  - `/mill-setup` — default GitHub-wiki path. Behaviour unchanged from pre-flags state.
  - `/mill-setup --from-url https://github.com/Org/shared.git --branch wiki/millhouse` — clone the named branch from a separate repo (one-repo-many-branches pattern). If the branch does not yet exist on remote, mill-setup initialises a local orphan branch and the first commit (Phase 3.1) pushes it.
  - `/mill-setup --from-url https://github.com/Org/shared.git` — clone from a separate repo at its remote HEAD branch (no `-b` passed to `git clone`).
  - `/mill-setup --branch wiki/millhouse` — apply branch override to the default `<origin>.wiki.git` URL. Edge case but supported.

  Each example bullet ends with one short sentence on the resulting state ("clones at remote HEAD", "initialises orphan branch X", etc.).

  **New Phase 0 — Parse arguments.** Insert as the first subsection under `## Phases` (above the existing `### Phase 1`). Spec:

  - Read `$ARGUMENTS`. Token-walk left-to-right.
  - Recognise `--from-url <url>` (next token after the flag is the value) and `--branch <name>` (likewise). Either flag may appear at most once.
  - Any other token: halt with the usage-hint message — quote `$ARGUMENTS` back to the user, then print `usage: /mill-setup [--from-url <url>] [--branch <name>]` and stop.
  - Store `<cli-from-url>` and `<cli-branch>` (each may be empty / unset).
  - Optionally: pre-load any existing `.millhouse/config.local.yaml` and read `wiki.repo_url:` / `wiki.branch:` if present, so Phase 1 can apply precedence without re-reading the file.

  **Update Phase 1 — Derive wiki URL.** Replace the existing step list (currently steps 0/1/2/3) so the URL/branch are derived via precedence. Keep step 0 (the `uv --version` check) verbatim. New steps 1–3:

  - Step 1: `git remote get-url origin` → `<origin-url>` (still computed; needed for the derived fallback and for Phase 7's `<repo-name>` resolution).
  - Step 2: Compute the effective URL and branch using precedence:
    - Effective URL: `<cli-from-url>` if set; else `wiki.repo_url:` from `.millhouse/config.local.yaml` if present; else strip `.git` from `<origin-url>` and append `.wiki.git`.
    - Effective branch: `<cli-branch>` if set; else `wiki.branch:` from config if present; else `None` (use remote HEAD).
    - Compute the source flag `<effective-from-url-source>`: `'cli'` | `'config'` | `'derived'` — used by Phase 2's branching message.
  - Step 3: Store `<wiki-url>`, `<wiki-branch>`, `<effective-from-url-source>`, and `<container>` (unchanged from existing logic).

  **Update Phase 2 — Verify wiki is reachable and non-empty.** Replace the existing single-message error path with a conditional:

  - When `<effective-from-url-source> == 'derived'`: keep the existing GitHub-wiki guidance verbatim (the `https://github.com/<owner>/<repo>/wiki` instruction and the GitHub-doesn't-create-the-wiki-repo-until-first-page note).
  - When `<effective-from-url-source>` is `'cli'` or `'config'`: emit the generic message `> The wiki URL '<wiki-url>' is unreachable. Check the URL, your network, and your credentials, then re-run /mill-setup.`

  Phase 2's `git ls-remote <wiki-url>` call itself stays the same (the conditional is purely on the halt message).

  **Update Phase 3 — Clone or fast-forward the wiki at `<wiki-dir>`.** Replace the existing inline steps 1/2/3 with a single call to the new helper. Keep the `<wiki-dir>` derivation step (the `_sibling.py wiki <hub-path>` invocation) at the top of the phase verbatim. After `<wiki-dir>` is computed, render this Python invocation (mirror the existing inline-PYTHONPATH form):

  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
  from pathlib import Path
  import _wiki, json
  result = _wiki.clone_or_init(
      url=r'<wiki-url>',
      branch=r'<wiki-branch-or-empty-then-None>',
      dest=Path(r'<wiki-dir>').resolve(),
  )
  print(json.dumps(result))
  "
  ```

  Show how to translate empty `<wiki-branch>` to Python `None` (e.g. ternary expression in the rendered command). Document that the helper raises `WikiSetupError` on dest-not-git-repo / URL-mismatch / branch-mismatch — the skill instructs the user (or agent) to halt and surface the message verbatim. Document that `WikiPushError` from the pull path means `git pull --ff-only` failed for any reason — network failure, credentials, non-fast-forward / local divergence — instruct the user to inspect and fix manually.

  Drop the existing prose for "If `<wiki-dir>` exists but is not a git repo" — that case is now handled by the helper's `WikiSetupError` and surfaces through the same agent-level halt.

  **New Phase 3.2 — Persist wiki overrides to config.local.yaml.** Insert immediately after Phase 3.1 (the `wiki/config.yaml` seed) and before Phase 3.7 (container scaffolding). Spec:

  - Run only when `<cli-from-url>` or `<cli-branch>` was explicitly supplied on the CLI in this run (i.e. when at least one of the two has its `cli`-source flag set). When both came from config or derived defaults, this phase is a no-op.
  - Render this Python invocation:

    ```bash
    PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "
    from pathlib import Path
    import _config
    changed = _config.set_local_wiki_overrides(
        cfg_path=Path('.millhouse/config.local.yaml'),
        repo_url=<repo-url-or-None>,
        branch=<branch-or-None>,
    )
    print('config.local.yaml updated' if changed else 'config.local.yaml already correct')
    "
    ```

    The agent fills `<repo-url-or-None>` and `<branch-or-None>` with `r'<value>'` when the CLI flag was given AND `None` when only the other flag was given. (Passing `None` for the omitted side preserves whatever value the file already has — partial-update semantics.)

  - Document: `.millhouse/` does not exist on a fresh install at the time this phase fires (it is created in Phase 4 by `create_hub_links`). No separate `mkdir` is needed in this prose — `_config.set_local_wiki_overrides` from Card 3 calls `cfg_path.parent.mkdir(parents=True, exist_ok=True)` before writing.

  - Document: comments in `.millhouse/config.local.yaml` are lost when this phase rewrites the file. The file is gitignored and per-machine, so the trade-off is acceptable. `ruamel.yaml` is not used.

  - Idempotency note: re-running mill-setup with the same flags (or no flags after a prior persisted run) leaves the file untouched — the helper returns `False` when the on-disk yaml-canonical content matches the desired content.

  **Update `## Idempotency` section.** Add a bullet:

  > - Phase 3.2's persisted `wiki.repo_url` / `wiki.branch` block is rewritten only when the on-disk values differ from the effective CLI values. Re-runs with matching flags (or no flags after a prior persisted run) make no change.

  **Update `## Error conditions` table.** Add two new rows:

  | Condition | Action |
  |---|---|
  | `clone_or_init` raises `WikiSetupError` (dest is not a git repo / URL mismatch / branch mismatch / clone or init failure) | Halt with the exception message verbatim. The helper's message names the offending paths; instruct the user to fix manually. |
  | Unknown CLI argument | Halt with usage hint (Phase 0). |

  **Phase 8 verification list — no change.** The wiki-clone invariant ("`<WIKI_PATH>` is a git repo") already covers the success state of `clone_or_init` regardless of which path it took. No new invariant is added.

  Throughout: keep the existing `${CLAUDE_PLUGIN_ROOT}` references and the inline-`PYTHONPATH=` prefix pattern that mill-setup uses everywhere. Do not switch to globally-installed PYTHONPATH — mill-setup is the bootstrapper.

- **Commit:** `docs(mill-setup): add --from-url and --branch flags`

### Card 6: Add commented `wiki:` block scaffold to `templates/config.local.yaml`

- **Reads:**
  - `plugins/mill/templates/config.local.yaml`
- **Modifies:**
  - `plugins/mill/templates/config.local.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Append a new commented-out scaffold block to the existing template, after the `# review:` example and before EOF (or at whatever position keeps the file readable). All lines start with `# ` (comment marker) so the verbatim-copy in mill-setup Phase 5 still produces a parseable empty-overlay yaml.

  Block content (literal — trailing space-after-`#` for readability is fine):

  ```yaml
  # wiki:
  #   The wiki repo overrides. Default behaviour: derive
  #   <origin>.wiki.git from the primary clone's origin URL and
  #   clone the remote default branch. Set explicitly when using a
  #   separate repo as the wiki, or to track a non-default branch
  #   (one-repo-many-branches pattern).
  #
  #   repo_url: https://github.com/Org/shared.git
  #     URL of the wiki repo. Set by /mill-setup --from-url <url>;
  #     persisted automatically. Default: <origin>.wiki.git.
  #
  #   branch: wiki/millhouse
  #     Branch to clone/track in the wiki repo. Set by
  #     /mill-setup --branch <name>; persisted automatically.
  #     Default: remote HEAD.
  ```

  Match the indentation and `# ` prefix style of the existing examples in this template. Verify by re-running mill-setup Phase 5's verbatim-copy path manually: the file copies cleanly into `.millhouse/config.local.yaml` and `yaml.safe_load(...)` returns either `None` or `{}` (no surprise keys).

- **Commit:** `docs(template): add wiki overrides scaffold to config.local.yaml`

## Batch Tests

`verify: null` for this batch. SKILL.md and template changes are documentation; the helpers they reference are tested in batch `helpers`. The implementer manually re-reads the rendered SKILL.md to confirm:

- Phase 0 / Phase 1 / Phase 2 / Phase 3 / Phase 3.2 read correctly end-to-end.
- All `${CLAUDE_PLUGIN_ROOT}` references are preserved (the inline-PYTHONPATH bootstrapper pattern stays intact).
- The `## Error conditions` table covers the new failure modes from `clone_or_init`.
- The `## Usage` examples reflect all four CLI argument permutations (none, `--from-url` only, `--branch` only, both).

Once batch `helpers` and batch `skill-and-template` are both approved and merged, a manual smoke-test of `/mill-setup --from-url <some-test-repo> --branch test/<slug>` against a throwaway repo is the recommended end-to-end validation step. That smoke-test is out-of-scope for the plan's automated `verify:` but should appear in the user-facing PR description.
