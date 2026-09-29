# Batch: scribe-release

```yaml
task: Migrate mill's generic skills to the shared scribe plugin
batch: scribe-release
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-agents-defs.py
depends-on: []
```

## Batch Scope

Publishes scribe `1.1.0` with repo-agnostic `python-*` and `csharp-*` skills, declares it as mill's dependency, then removes millhouse's `golang`, `csharp` and `python` plugins.
One batch because the order is the contract: the scribe push (card 1) must land before the deletion (card 2), so the language skills are never published nowhere.
Batch 2 consumes the result: the `scribe:python-*` / `scribe:csharp-*` names it writes into mill resolve against scribe `1.1.0`, and the `SKILLS.md` regeneration it runs no longer sees `plugins/{golang,csharp,python}`.
Batch-local decision: card 1 is the only card in the plan that writes outside this worktree (the scribe clone at `/home/knatte/Code/scribe`), authorised by the discussion's scribe-language-skills decision; every scribe git operation uses `git -C /home/knatte/Code/scribe`, never `cd`.

## Cards

### Card 1: Publish scribe 1.1.0 and declare mill's dependency on it

- **Context:**
  - `plugins/python/skills/python-build/SKILL.md`
  - `plugins/python/skills/python-comments/SKILL.md`
  - `plugins/python/skills/python-testing/SKILL.md`
  - `plugins/csharp/skills/csharp-build/SKILL.md`
  - `plugins/csharp/skills/csharp-comments/SKILL.md`
  - `plugins/csharp/skills/csharp-testing/SKILL.md`
  - `/home/knatte/Code/scribe/plugins/scribe/skills/code-quality/SKILL.md`
  - `/home/knatte/Code/scribe/plugins/scribe/skills/golang-comments/SKILL.md`
  - `/home/knatte/Code/scribe/plugins/scribe/skills/testing/SKILL.md`
- **Edits:**
  - `/home/knatte/Code/scribe/.claude-plugin/marketplace.json`
  - `/home/knatte/Code/scribe/plugins/scribe/.claude-plugin/plugin.json`
  - `/home/knatte/Code/scribe/plugins/scribe/skills/INDEX.md`
  - `/home/knatte/Code/scribe/README.md`
  - `plugins/mill/.claude-plugin/plugin.json`
  - `.claude-plugin/marketplace.json`
- **Creates:**
  - `/home/knatte/Code/scribe/plugins/scribe/skills/python-build/SKILL.md`
  - `/home/knatte/Code/scribe/plugins/scribe/skills/python-comments/SKILL.md`
  - `/home/knatte/Code/scribe/plugins/scribe/skills/python-testing/SKILL.md`
  - `/home/knatte/Code/scribe/plugins/scribe/skills/csharp-build/SKILL.md`
  - `/home/knatte/Code/scribe/plugins/scribe/skills/csharp-comments/SKILL.md`
  - `/home/knatte/Code/scribe/plugins/scribe/skills/csharp-testing/SKILL.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Idempotency check first, because the scribe commit, tag and push are external side effects a re-dispatch cannot see in this worktree's git log.
  Run `git -C /home/knatte/Code/scribe log --oneline -3`, `git -C /home/knatte/Code/scribe tag -l 'scribe--v1.1.0'` and `git -C /home/knatte/Code/scribe ls-remote --tags origin 'scribe--v1.1.0'`.
  If the scribe log already shows the `1.1.0` commit, skip steps A-C and redo only the missing push/tag steps in D;
  if the tag exists locally and on `origin`, skip D entirely.

  **A. Six new scribe skills.**
  Copy each millhouse file to the scribe path of the same skill name (`plugins/python/skills/python-build/SKILL.md` -> `/home/knatte/Code/scribe/plugins/scribe/skills/python-build/SKILL.md`, and likewise for `python-comments`, `python-testing`, `csharp-build`, `csharp-comments`, `csharp-testing`), keeping frontmatter `name:` and `description:` unchanged, then apply these edits:
  - `python-comments` and `csharp-comments`: replace the line "**Load the `code-comments` skill first.**" with "**Load `scribe:code-quality` first — its Comments section is the language-agnostic base.**"
  - `python-comments`: the bullet beginning "See the `code-comments` skill's "many comments needed" corollary" becomes "See `scribe:code-quality`'s Comments section ("Restraint first") for when a function's steps need explaining — decompose into named sub-functions instead of narrating in the docstring." Keep the two continuation lines that follow it.
  - `python-comments` section "## Module docstrings": replace the first bullet ("Every `.py` file **must** have a module-level docstring — it is the file's header comment.") with "See `scribe:code-quality`'s Comments section for the file-header rule and its sole-file exception; in Python the file header is the module-level docstring." Keep the triple-quote placement bullet.
    This mirrors how scribe's `golang-comments` defers the file-header rule to `code-quality` and keeps only the language mechanics.
  - `csharp-comments` section "## File header": replace the sentence "Every `.cs` file must open with a `///` comment block, placed above the `using` statements and the `namespace` declaration." with two lines: "See `scribe:code-quality`'s Comments section for the file-header rule and its sole-file exception." and "In C#, the header is a `///` comment block placed above the `using` statements and the `namespace` declaration." Keep the example.
  - `python-comments` "## Line-wrap style" and `csharp-comments` "## Line-wrap style": replace "See the `prose` skill for the full line-wrap rule." with "See `prose`'s Line-breaks rule for the full rule." (same wording scribe's `golang-comments` uses).
  - `python-testing` and `csharp-testing`: replace "See `@code:testing` for language-agnostic rules" with "See `scribe:testing` for language-agnostic rules", keeping the rest of the sentence.
  - `csharp-build`: in the node-reuse bullet, replace "A long mill-orchestrated" with "A long orchestrated" and the parenthetical "(per-batch verify, baseline pre-flight, merge-in verify replay, git-pr's final verify)" with "(per-change verify, baseline pre-flight, a final pre-merge verify)".
    In the never-pipe bullet replace "(mill-go verify, git-commit lint, any pass/fail check)" with "(a verify step, a pre-commit lint, any pass/fail check)".
  - `python-build` "## Import Organization" example: replace `from solgt.timeseries import convert_date_to_t` with `from mypackage.timeseries import to_period_index`, `import utils_config` with `import project_config`, and `import utils_file_io as fio` with `import file_io as fio`.
    Update the aliased-imports bullet's example to `import file_io as fio`, and "## Configuration"'s "(e.g., `utils_config.py`)" to "(e.g., `project_config.py`)".
  - Keep the domain examples in `python-comments` and `python-build` (CBI, SSB, RSI, LORSI, `grunnkrets_number`, "Extracting CBI into cube form..."): they illustrate domain-reasoning comments and name no repo, package or path.
  - Final check: `grep -nE "mill|millhouse|_mill|plugins/|@code:|solgt|utils_config|utils_file_io|git-pr|merge-in"` over the six new files returns nothing;
    then read each file through for any other identifier naming a specific repo, package or path and genericise it the same way.
    Convert any fixed-column hard-wrapped prose you touch to semantic line breaks (one sentence per line).

  **B. Scribe index, README, version.**
  - `/home/knatte/Code/scribe/plugins/scribe/skills/INDEX.md`: add six table rows after the three `golang-*` rows, ordered `python-comments`, `python-build`, `python-testing`, `csharp-comments`, `csharp-build`, `csharp-testing` (mirroring the golang group's comments/build/testing order), each `| [<name>](<name>/SKILL.md) | <frontmatter description> |`.
  - `/home/knatte/Code/scribe/README.md`: in the opening paragraph change "tests, Go mechanics, handoff documents" to "tests, Go, Python and C# mechanics, handoff documents".
  - `/home/knatte/Code/scribe/plugins/scribe/.claude-plugin/plugin.json` and the `scribe` plugin entry in `/home/knatte/Code/scribe/.claude-plugin/marketplace.json`: `version` `1.0.0` -> `1.1.0`; description "Go mechanics" -> "Go, Python and C# mechanics".
    Also bump the marketplace-level `version` in `/home/knatte/Code/scribe/.claude-plugin/marketplace.json` to `1.1.0`.

  **C. Scribe commit.**
  `git -C /home/knatte/Code/scribe add plugins/scribe/skills README.md plugins/scribe/.claude-plugin/plugin.json .claude-plugin/marketplace.json && git -C /home/knatte/Code/scribe commit -m "scribe 1.1.0: add Python and C# build, comments and testing skills"`.
  End the message with the session's `Co-Authored-By:` trailer.

  **D. Scribe tag and push.**
  `git -C /home/knatte/Code/scribe tag scribe--v1.1.0` (the `<plugin-name>--v<version>` format the dependencies docs require for range resolution), then `git -C /home/knatte/Code/scribe push origin main` and `git -C /home/knatte/Code/scribe push origin scribe--v1.1.0`.
  Never `cd` into the scribe clone.
  A push rejected as non-fast-forward: `git -C /home/knatte/Code/scribe pull --rebase origin main`, re-point the tag at the new HEAD (`git -C /home/knatte/Code/scribe tag -f scribe--v1.1.0`), push again.

  **E. Millhouse manifests.**
  - `plugins/mill/.claude-plugin/plugin.json`: add `"dependencies": [{"name": "scribe", "marketplace": "scribe", "version": "^1.1.0"}]` after `"author"`, before `"agents"`.
    Keep `"version": "2.0.0"`.
  - `.claude-plugin/marketplace.json`: add top-level `"allowCrossMarketplaceDependenciesOn": ["scribe"]` after `"owner"`, before `"plugins"`.
    Keep the `mill` entry's `version` `2.0.0`.
  - Validate: `python3 -c "import json; [json.load(open(p)) for p in ['.claude-plugin/marketplace.json', 'plugins/mill/.claude-plugin/plugin.json', '/home/knatte/Code/scribe/.claude-plugin/marketplace.json', '/home/knatte/Code/scribe/plugins/scribe/.claude-plugin/plugin.json']]"` exits 0;
    then `claude plugin validate plugins/mill`, `claude plugin validate .` and `claude plugin validate /home/knatte/Code/scribe` each report no error (warnings are acceptable; report them).
- **Commit:** `feat(mill): depend on scribe ^1.1.0 (scribe publishes Python and C# skills)`

### Card 2: Remove the golang, csharp and python plugins

- **Context:**
  - `/home/knatte/Code/scribe/plugins/scribe/skills/INDEX.md`
- **Edits:**
  - `.claude-plugin/marketplace.json`
  - `plugins/mill/.claude-plugin/plugin.json`
- **Creates:** none
- **Deletes:**
  - `plugins/golang/settings.json`
  - `plugins/golang/skills/INDEX.md`
  - `plugins/golang/skills/golang-build/SKILL.md`
  - `plugins/golang/skills/golang-comments/SKILL.md`
  - `plugins/golang/skills/golang-testing/SKILL.md`
  - `plugins/csharp/settings.json`
  - `plugins/csharp/skills/INDEX.md`
  - `plugins/csharp/skills/csharp-build/SKILL.md`
  - `plugins/csharp/skills/csharp-comments/SKILL.md`
  - `plugins/csharp/skills/csharp-testing/SKILL.md`
  - `plugins/python/settings.json`
  - `plugins/python/skills/INDEX.md`
  - `plugins/python/skills/python-build/SKILL.md`
  - `plugins/python/skills/python-comments/SKILL.md`
  - `plugins/python/skills/python-testing/SKILL.md`
- **Moves:** none
- **Requirements:**
  Precondition: `git -C /home/knatte/Code/scribe ls-remote --tags origin 'scribe--v1.1.0'` prints a line (card 1's push landed), and the scribe `INDEX.md` lists the six `python-*`/`csharp-*` rows.
  If either fails, stop and report instead of deleting.
  - `git rm -r plugins/golang plugins/csharp plugins/python`, then confirm `ls plugins` no longer lists them (remove any leftover untracked files under those directories too).
  - `.claude-plugin/marketplace.json`: delete the `python`, `csharp` and `golang` objects from `plugins`, leaving `mill`, `codeguide`, `weblens` in their current order.
  - Mill description: in the `mill` entry of `.claude-plugin/marketplace.json` change "Task orchestration, code quality, git workflow, and documentation for Claude Code" to "Task orchestration, git workflow, and documentation for Claude Code";
    in `plugins/mill/.claude-plugin/plugin.json` change the same phrase, keeping its trailing " (v2)".
  - Re-run the card 1 `json.load` check over the two millhouse manifests.
- **Commit:** `chore: remove golang, csharp and python plugins (moved to scribe)`

## Batch Tests

`test-agents-defs.py` parses `plugins/mill/.claude-plugin/plugin.json` (`test_plugin_json_registers_all_agent_files`), so it fails on a malformed manifest after cards 1 and 2.
The scribe-side edits have no runnable surface in this repo;
card 1's own grep check, `json.load` check and `claude plugin validate` runs are their verification.
