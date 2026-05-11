# Batch: skill-and-schema

```yaml
task: '47 (A) — mill-merge-in: allowlist for known-broken pre-existing test failures'
batch: skill-and-schema
number: 1
cards: 3
verify: null
depends-on: []
```

## Batch Scope

The batch delivers `verify.skip_known_broken` support in `mill-merge-in`: the SKILL is updated to consult the allowlist before each verify command, and the schema is documented in both the template and the production wiki config. Three cards, three sequential commits (two on the task branch, one in the wiki repo). The change is documentation-only with no Python or test surface — `verify: null` is correct.

Batch-local decisions: none beyond the Shared Decisions in `00-overview.md`.

## Cards

### Card 1: Update mill-merge-in SKILL.md (Step 4 cfg load + allowlist pre-check; Step 6 Report skip count)

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In Step 4 (Verify), BEFORE the `for each (name, cmd)` loop, add an explicit instruction to load config and read the allowlist. Use the variables `wiki_path` and `git_root` (the same ones already used in Entry steps 1-2). The instruction must direct the LLM to: call `cfg = _config.load_config(wiki_path, git_root)`, then read `skip_list = (cfg.get("verify") or {}).get("skip_known_broken") or []`. Add a one-line note that `skip_list` is the empty list when the key is absent (which is the default for existing hubs).
  - In the `for each (name, cmd)` loop body, insert a pre-check IMMEDIATELY BEFORE the existing "Run the command from the worktree root." bullet: instruct the LLM to iterate `skip_list`; on the first entry `p` where `p in cmd` is true, print exactly `[verify] skipped {p} (allowlisted as known-broken)` to stdout (where `{p}` is the literal allowlisted path that matched), increment a `skipped` counter, and `continue` to the next `(name, cmd)` pair without running the command and without invoking the verify-fix sub-agent. If no entry in `skip_list` matches, fall through to the existing "Run the command from the worktree root." bullet unchanged.
  - Initialise both `ran = 0` and `skipped = 0` counters at the top of Step 4 (right after loading `skip_list`). The `ran` counter increments after each command that runs without error and after each successful verify-fix recovery — it counts commands that completed, skipped commands are not counted under `ran`.
  - In Step 6 (Report), replace the line `Verify: <M> batch tests ran.` with conditional text. The replacement must direct the LLM to emit `Verify: <ran> batch tests ran.` when `skipped == 0`, and `Verify: <ran> batch tests ran, <skipped> skipped (allowlisted as known-broken).` when `skipped >= 1`. Use the placeholders `<ran>` and `<skipped>` in the SKILL.md prose so the LLM substitutes the counter values when emitting the report.
  - Do NOT change any other step (1, 2, 3, 5, Rollback, No-op guarantee). Do NOT introduce a Python helper. Do NOT alter `iter_batch_verifies` or any other Python module — the change is purely SKILL.md prose.
  - Preserve the existing markdown structure: heading levels, the conflict-policy table at Step 3, code-fence language tags (```bash for shell, no language for plain text).
- **Commit:** `docs(mill-merge-in): consult verify.skip_known_broken allowlist in verify step`

### Card 2: Add commented `verify:` section to template wiki-config.yaml

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/wiki-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Append a new top-level section to the template, placed AFTER the existing `merge:` block at the bottom of the file (which currently ends with `  verify_fix_rounds: 3`). The section must follow the documentation style established by the existing `merge:` block: a header band of `# ---------------------------------------------------------------------------` separators, then a `# mill-merge-in: verify allowlist` title comment, then 2-3 short body comment lines, then the commented YAML example.
  - Header band exactly matches the width of other header bands in the file (count the existing `# ---...` lines — they are 75 dashes).
  - Title comment: `# mill-merge-in: verify allowlist`.
  - Body comment (place between title and example): explain in 2-3 lines that `verify.skip_known_broken` is a list of path substrings; if any entry appears as a substring of a plan batch's `verify:` command, `mill-merge-in` skips that command and logs `[verify] skipped <path> (allowlisted as known-broken)`. Add a final body comment line noting that values are per-machine and belong in `.millhouse/config.local.yaml`, not here in the shared wiki config — this block is for schema documentation only.
  - Commented YAML example (exactly two lines, each prefixed `# `): `# verify:` and `#   skip_known_broken: []  # e.g. ["tests/foo/test_flaky.py"]`.
  - Do NOT modify any existing section of the template. Do NOT un-comment any of the new section — every new line begins with `# `. After the change, a YAML parser must still load the file successfully (the new section is comments only and therefore yields no parsed keys).
- **Commit:** `docs(template): document verify.skip_known_broken schema`

### Card 3: Mirror commented `verify:` section to production wiki config

- **Context:**
  - `plugins/mill/templates/wiki-config.yaml`
- **Edits:**
  - `C:/Code/millhouse/wiki/config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Read the file Card 2 just edited (`plugins/mill/templates/wiki-config.yaml`) and locate the new commented `verify:` section that Card 2 added (header band + title + body comments + commented YAML example). This is the exact byte sequence to copy.
  - Read the production wiki config at the absolute path `C:/Code/millhouse/wiki/config.yaml`. Locate the existing `merge:` block at the bottom (this hub already mirrors the template's `merge:` block — confirm before editing).
  - Append the byte-for-byte identical commented `verify:` section AFTER the production file's `merge:` block, preserving any trailing newline behavior of the existing file (do not introduce extra blank lines beyond what the template uses).
  - Stage and commit in the wiki repo via Bash: `git -C "C:/Code/millhouse/wiki" add config.yaml` then `git -C "C:/Code/millhouse/wiki" commit -m "docs: document verify.skip_known_broken schema"` then `git -C "C:/Code/millhouse/wiki" push`. Use the literal absolute path `C:/Code/millhouse/wiki` — do NOT use `cd` and do NOT use the `.wiki` junction.
  - Do NOT create any commit on the task branch for this card. The card's deliverable is the wiki-repo commit only. Verify after the wiki push that the task branch has no new uncommitted changes (`git status` from the worktree root should show clean).
- **Commit:** `docs: document verify.skip_known_broken schema`

## Batch Tests

`verify: null` — the batch is documentation only. No Python code change, no template-rendering change, no behaviour reachable from existing unit tests. The mill-merge-in SKILL.md is LLM-directed prose; correctness is covered by the reviewer in Phase: Plan Review.
