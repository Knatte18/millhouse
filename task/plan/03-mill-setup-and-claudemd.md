# Batch: mill-setup-and-claudemd

```yaml
task: Replace uv-run-project with direct venv Python in SKILL.md invocations
batch: mill-setup-and-claudemd
number: 3
cards: 4
verify: null
depends-on: []
```

## Batch Scope

This batch converts cache-form invocations in `mill-setup/SKILL.md` (Card 4) and updates two prose paragraphs that document the old invocation pattern by name: the "How to invoke the helpers" section inside mill-setup SKILL.md (Card 5), and the corresponding paragraph in the root `CLAUDE.md` (Card 6). Both prose updates are bundled here because they describe the same convention and would drift if updated separately.

mill-setup has both source-tree forms (e.g. `uv run --project plugins/mill ...`) and cache forms; only cache forms convert. The "How to invoke the helpers" prose at lines ~57–69 explicitly frames the inline-PYTHONPATH-with-`uv run` pattern as "mill-setup's unique inline-prefix form" — that framing becomes incorrect after Batch 1 converts every other skill to the same direct-Python form, and must be revised.

## Cards

### Card 4: Convert cache-form invocations in mill-setup SKILL.md

- **Context:**
  - `task/discussion.md`
  - `task/plan/00-overview.md`
  - `task/plan/01-bulk-skill-conversion.md`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Apply the same four substitution rules as Card 1 (see `task/plan/01-bulk-skill-conversion.md` Card 1 Requirements, Rules 1–4). The rules apply to every cache-form invocation in fenced ```bash blocks inside mill-setup SKILL.md.

  Specifically, every line matching `uv run --project "${CLAUDE_PLUGIN_ROOT}"` or `uv run --project "$CLAUDE_PLUGIN_ROOT"` (with or without a `PYTHONPATH=...` prefix) is rewritten to use `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"` instead, normalising unbraced `"$CLAUDE_PLUGIN_ROOT"` to braced `"${CLAUDE_PLUGIN_ROOT}"` along the way.

  **DO NOT TOUCH in this card:**
  - Lines containing `uv run --project plugins/mill` (source-tree exception — leave unchanged).
  - The prose at lines ~57–69 (handled by Card 5; do not modify prose in this card even if it contains the literal old pattern inside a code fence).
    - Exception: the bash code fence at lines ~61–67 (the "WRONG/RIGHT" example block) is owned by Card 5 — leave it untouched here.

  Every other bash block in mill-setup SKILL.md (e.g. the `PYTHONPATH="$CLAUDE_PLUGIN_ROOT/scripts" uv run --project "$CLAUDE_PLUGIN_ROOT" python -c "..."` lines at lines 131, 139, 164, 174, 199, 224, 262, 280, 350, 368, 392, 431, 441, 451, 468 of the pre-edit file) converts per Rule 3 (or Rule 1 / 4 depending on shape).

  Post-edit invariant: outside the Card 5 prose block (lines ~57–69), `grep -E 'uv run --project "\$\{?CLAUDE_PLUGIN_ROOT\}?"' plugins/mill/skills/mill-setup/SKILL.md` returns zero matches. `grep -c 'uv run --project plugins/mill' plugins/mill/skills/mill-setup/SKILL.md` returns the same count pre- and post-edit (source-tree forms unchanged).

- **Commit:** `refactor(mill-setup): use direct venv Python for cache-form invocations`

### Card 5: Rewrite "How to invoke the helpers" prose and example in mill-setup SKILL.md

- **Context:**
  - `task/discussion.md`
  - `task/plan/00-overview.md`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Locate the section "## How to invoke the helpers" (currently at line 57 pre-edit). The current section comprises:
  - line 59: a paragraph stating mill-setup is the PYTHONPATH bootstrapper and "every Python invocation in this skill uses the inline prefix:"
  - lines 61–67: a bash code fence with WRONG (source-tree) and RIGHT (`PYTHONPATH="$CLAUDE_PLUGIN_ROOT/scripts" uv run --project "$CLAUDE_PLUGIN_ROOT" python -c "..."`) examples, with the RIGHT example annotated as "mill-setup's unique inline-prefix form"
  - line 69: a paragraph stating "This inline `PYTHONPATH=` prefix is required in mill-setup and in any skill invocation within the same CC session…"

  Rewrite the entire section (the heading stays as "## How to invoke the helpers"; the three pieces above are replaced) so that it reads as follows. Use this exact content; do not summarise or restructure:

  ```markdown
  ## How to invoke the helpers

  mill-setup is the bootstrapper that **creates** the global `PYTHONPATH` Windows user environment variable. That variable does not exist in the current process (or in any child process spawned during this session) until Phase 4.7 completes and a new shell is opened. The mill convention is to invoke the venv Python binary directly with an explicit `PYTHONPATH=` shell prefix on every call — this works whether the global env var is set or not:

  ```bash
  # WRONG — invokes from source tree
  PYTHONPATH="plugins/mill/scripts" uv run --project plugins/mill python -c "..."

  # RIGHT — invokes from cache (the canonical mill-script form, shared with every other mill SKILL.md)
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "..."
  ```

  This direct-binary form is used by every mill SKILL.md (mill-go uses an equivalent form with `$MILL_PYTHON`, an alias defined in its Step 0 block). The source-tree form (`uv run --project plugins/mill ...`) remains the documented exception for cases where the cache path is unavailable — for example, running unit tests from the millhouse repo itself.
  ```

  Two structural changes vs the pre-edit text:
  1. The "unique inline-prefix form" framing is removed. The new prose explicitly states the direct-Python form is shared with every other mill SKILL.md.
  2. The example code fence's RIGHT line uses the direct-Python form (matching Card 4's substitution rules), not `uv run --project`.

  The triple-backtick markdown fences MUST be preserved correctly: the outer block is a markdown code fence (rendered as a literal block in this plan), but inside the SKILL.md file the inner ```bash ... ``` fence is the actual code block.

  **DO NOT TOUCH outside this section:** the heading at line 57, the section that follows ("Helpers used by this skill" at line 71), or anything before line 57.

  Post-edit invariant: `grep -c "unique inline-prefix form" plugins/mill/skills/mill-setup/SKILL.md` returns zero. `grep -c "the canonical mill-script form, shared with every other mill SKILL.md" plugins/mill/skills/mill-setup/SKILL.md` returns exactly one.

- **Commit:** `docs(mill-setup): rewrite invoke-the-helpers prose to match direct-venv convention`

### Card 6: Update CLAUDE.md to document the direct-venv Python invocation pattern

- **Context:**
  - `task/discussion.md`
  - `task/plan/00-overview.md`
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Locate the bullet point in `CLAUDE.md` (under `## Conventions worth carrying`) that currently begins:

  > **Mill scripts are invoked via `uv run`, not `python`.** All SKILL.md examples use `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py" [args]`; inline helpers use `uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "..."`.

  This is currently a single long bullet (pre-edit line 104) running to "…never assume the env var resolves at runtime." Replace the ENTIRE bullet with the following text (still as one bullet, same indentation level — i.e. one top-level `- ` item under `## Conventions worth carrying`):

  ```markdown
  - **Mill scripts are invoked via the cache venv's Python binary directly, not via `uv run --project`.** Cache-form SKILL.md blocks use `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py" [args]`; inline helpers use `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "..."`. The `PYTHONPATH=` prefix is required because the Bash subshell does not reliably inherit the global Windows user env var that `mill-setup` Phase 4.7 sets. The venv at `${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe` is created and maintained by `update-plugins.ps1` when the plugin is installed or upgraded. **Exception (source-tree form):** when running from the millhouse repo itself (e.g. unit tests, or when `${CLAUDE_PLUGIN_ROOT}` is unset in some Bash subshells observed in Windows VS Code's integrated terminal), use `uv run --project plugins/mill plugins/mill/scripts/millpy-X.py` or the inline `PYTHONPATH="plugins/mill/scripts" uv run --project plugins/mill python -c "..."` form — `uv run` will create the source-tree venv on demand. **Exception (mill-go):** mill-go's body calls use `"$MILL_PYTHON"` (an alias to `${PLUGIN_ROOT}/.venv/Scripts/python.exe`) defined in its Step 0 block. **Exception (nested calls):** Python invocations that appear after `--` inside a `millpy-bg.py` launcher line MUST NOT carry the `PYTHONPATH=` prefix — tokens after `--` are passed as argv to a subprocess; the outer launcher already set PYTHONPATH in the process environment, which is inherited automatically.
  ```

  Two structural changes vs the pre-edit text:
  1. The "uv run, not python" framing is replaced with "direct venv Python binary, not uv run --project". The leading `**...**` boldface label is updated accordingly.
  2. The three exceptions (source-tree fallback, mill-go's `$MILL_PYTHON`, and nested-call-no-prefix) are listed inline so a reader who lands on this bullet has the full picture without needing to read individual SKILL.md files.

  **DO NOT TOUCH outside this bullet:** the surrounding bullets (the bullet immediately above about source-tree paths at lines 95–103, and the bullets that follow about generated markdown at line 105+, etc.) MUST remain unchanged.

  Post-edit invariant: `grep -c "Mill scripts are invoked via the cache venv" CLAUDE.md` returns exactly one. `grep -c "Mill scripts are invoked via .uv run., not .python." CLAUDE.md` returns zero (the old framing is gone). `grep -c "uv run --project .CLAUDE_PLUGIN_ROOT" CLAUDE.md` returns zero in the modified bullet (other bullets — e.g. the source-tree example at lines 97–103 — may still reference `uv run` and MUST be preserved).

- **Commit:** `docs(claude.md): document direct-venv Python invocation pattern and exceptions`

### Card 7: Update CLAUDE.md cache-vs-source-tree example to use direct-venv form

- **Context:**
  - `task/plan/03-mill-setup-and-claudemd.md`
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Locate the bullet under `## Conventions worth carrying` whose body begins:

  > **In operational Bash commands typed at the agent level, never reference `plugins/mill/...` or `plugins/codeguide/...` source-tree paths. Use `${CLAUDE_PLUGIN_ROOT}` (which resolves to the cache). Tests run as `python plugins/mill/unit_tests/...` are the sole exception, and only when explicitly invoked from a test runner.**

  This bullet is immediately FOLLOWED by an indented fenced ```bash block containing a WRONG/RIGHT example pair. The RIGHT line currently reads:

  ```
  uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-spawn.py"
  ```

  Replace that RIGHT line (and only that line — leave the `# WRONG — invokes from source tree` line and its accompanying `uv run --project plugins/mill plugins/mill/scripts/millpy-spawn.py` line UNCHANGED, since the WRONG example illustrates a source-tree path which remains a valid documented exception) with:

  ```
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-spawn.py"
  ```

  Reason: post-Card-6 the canonical invocation form is direct venv Python. Leaving this RIGHT example as `uv run --project "${CLAUDE_PLUGIN_ROOT}"` would create an adjacent contradiction with the bullet Card 6 rewrites — that bullet labels `uv run --project` cache-form as the OLD pattern, while this example still labels it RIGHT.

  **DO NOT TOUCH outside that single line:** the surrounding bullet's prose, the WRONG/RIGHT comment lines, the source-tree WRONG example, the bullet that follows (rewritten by Card 6), and every other bullet in `## Conventions worth carrying`.

  Post-edit invariant: `grep -c 'uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-spawn.py"' CLAUDE.md` returns zero. `grep -c '${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe.*millpy-spawn.py' CLAUDE.md` returns exactly one (the new RIGHT example).

- **Commit:** `docs(claude.md): update cache-path example to direct-venv form`

## Batch Tests

This is a documentation-only batch; `verify: null`.

Verification is mechanical and performed by the implementer after applying all three cards:

1. `grep -E 'uv run --project "\$\{?CLAUDE_PLUGIN_ROOT\}?"' plugins/mill/skills/mill-setup/SKILL.md` — expected zero matches.
2. `grep -c 'uv run --project plugins/mill' plugins/mill/skills/mill-setup/SKILL.md` — expected to equal the pre-edit count **plus one** (Card 5's rewritten prose adds one new mention of `uv run --project plugins/mill` inside a sentence describing the source-tree exception). The "+1" applies only after Card 5 runs; if Card 4 is verified separately before Card 5, the count for Card 4 alone must equal the pre-edit count.
3. `grep -c 'unique inline-prefix form' plugins/mill/skills/mill-setup/SKILL.md` — expected zero (old framing removed).
4. `grep -c 'the canonical mill-script form, shared with every other mill SKILL.md' plugins/mill/skills/mill-setup/SKILL.md` — expected exactly one (new framing present).
5. `grep -c 'Mill scripts are invoked via the cache venv' CLAUDE.md` — expected exactly one.
6. `grep -c 'Mill scripts are invoked via .uv run., not .python.' CLAUDE.md` — expected zero (old framing removed).
7. `grep -c 'uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-spawn.py"' CLAUDE.md` — expected zero (Card 7 replaced this RIGHT example).
8. `grep -c '${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe.*millpy-spawn.py' CLAUDE.md` — expected exactly one (Card 7's new RIGHT example).
9. Spot-read the rewritten mill-setup section, the rewritten CLAUDE.md bullet (Card 6), and the updated cache-path example (Card 7) to confirm fenced code blocks render correctly (no broken markdown after the edits).
