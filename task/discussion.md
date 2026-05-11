# Discussion: 47 (A) — mill-merge-in: allowlist for known-broken pre-existing test failures

```yaml
task: '47 (A) — mill-merge-in: allowlist for known-broken pre-existing test failures'
slug: verify-skip-known-broken
status: discussing
parent: main
```

## Problem

`mill-merge-in` Step 4 (Verify) replays every batch verify command from the plan. If `main` already has pre-existing test failures unrelated to the task being merged — broken tests that existed before the task branch was created — `mill-merge-in` halts on those failures anyway. Every active task hits the same wall even though the failures are not regressions introduced by the task.

The fix is a per-machine opt-in allowlist: `verify.skip_known_broken: [<test-file>, ...]` in `.millhouse/config.local.yaml`. Before running each verify command, `mill-merge-in` checks whether any allowlisted path appears in the command string; if it does, the command is skipped with a log line `[verify] skipped <file> (allowlisted as known-broken)` and execution continues to the next batch verify.

## Scope

**In:**
- New config key `verify.skip_known_broken` (list of strings), consulted by `mill-merge-in` Step 4.
- Update `mill-merge-in` SKILL.md to describe the allowlist check before each verify command.
- Add `verify.skip_known_broken` schema (commented out, empty list default) to `plugins/mill/templates/wiki-config.yaml` under a new `verify:` section.
- Mirror the comment to the production `wiki/config.yaml` (per CLAUDE.md: template mirrors production).

**Out:**
- `mill-go`'s implementation-time verify loop is not changed.
- No Python helper — the check is a simple config-read + substring-match, LLM-directed inline in the SKILL.
- No glob pattern matching — substring match only.
- No per-runner flag injection (no `--ignore`, `--deselect`) — the entire verify command is skipped when matched.
- No machine-level config (`~/.millhouse/config.machine.yaml`) support — allowlists are worktree-local because known-broken tests are context-dependent.

## Decisions

### Config key placement under `verify:` (not `merge:`)

- Decision: The key lives under `verify.skip_known_broken`, not `merge.skip_known_broken`.
- Rationale: The spec uses this name literally; keeping it separate from `merge:` leaves `merge:` as a namespace for merge-orchestration concerns (locking, rounds) while `verify:` covers verify-gate policy.
- Rejected: `merge.skip_known_broken` — would be consistent with co-locating merge-in config, but contradicts the spec and introduces a namespace that doesn't match any existing key.

### Matching strategy: substring match

- Decision: Skip a verify command if any entry in `verify.skip_known_broken` appears as a substring of the verify command string.
- Rationale: Verify commands are author-controlled strings in the plan. Authors who need to allowlist a specific test file write that file's path literally in the verify command (e.g. `pytest tests/foo/test_bar.py -q`). Substring match is correct for this case and requires zero dependencies.
- Rejected: Argument-level tokenization — adds shell-parsing complexity with no practical benefit given that plan authors control the verify command strings. Glob matching — YAGNI.

### Skip entire verify command (no per-file exclusion)

- Decision: When a match is found, the entire verify command is skipped. No modification of the command to exclude only the matching file.
- Rationale: The spec says "consult before verify-gate is called" — this implies bypassing the call. Per-runner flag injection (e.g. `--ignore` for pytest) would require runner detection logic and per-framework maintenance.
- Rejected: Flag injection — brittle, adds framework coupling.

### Implementation: SKILL.md only, no new Python

- Decision: The allowlist check lives entirely in `mill-merge-in` SKILL.md Step 4, as a pre-check instruction before each `(name, cmd)` is run.
- Rationale: `mill-merge-in` is already LLM-directed. Adding a Python helper for a string-contains check would be premature abstraction (YAGNI). The SKILL.md already instructs reading `iter_batch_verifies` results; adding a pre-loop config read is a natural extension.
- Rejected: New `_verify_allowlist.py` helper — over-engineered for a one-liner check. Modification of `iter_batch_verifies` — mixes DAG structure with config concerns.

### Log format

- Decision: Log exactly `[verify] skipped <allowlisted-path> (allowlisted as known-broken)` where `<allowlisted-path>` is the specific allowlisted string that matched the verify command.
- Rationale: Matches the spec verbatim. Logs the allowlisted path (not the full command) so the operator can see which allowlist entry triggered the skip.
- Rejected: Logging the full command — verbose for long commands. Logging both — more informative but the spec is clear.

### Config layer: local only with template schema

- Decision: Actual values live only in `.millhouse/config.local.yaml` (gitignored, per-machine). The template (`wiki-config.yaml`) gets a new commented `verify:` section documenting the key.
- Rationale: Known-broken test failures are machine-specific — they depend on what's installed, what's been run, and what's broken on that particular dev machine. The wiki config (shared across all clones) is the wrong place for them. The template documents the key schema without forcing any values.
- Rejected: Allowlisting in wiki config — would force the same skip set on all machines, which is wrong for "pre-existing" failures that vary per machine.

## Technical context

**`mill-merge-in` SKILL.md Step 4 (Verify)** — current flow:
```
iter_batch_verifies(plan_dir)  →  [(name, cmd), ...]
for (name, cmd):
  run cmd
  on failure → millpy-merge-in-subagent.py --mode verify-fix
```
New flow:
```
read cfg["verify"]["skip_known_broken"] as skip_list (default [])
for (name, cmd):
  if any(path in cmd for path in skip_list):
    print(f"[verify] skipped {matched_path} (allowlisted as known-broken)")
    continue
  run cmd
  on failure → millpy-merge-in-subagent.py --mode verify-fix
```

**Config loading** — `_config.load_config(wiki_path, worktree_root)` is already called in Entry (step 3 of mill-merge-in). The `cfg` dict is available throughout the skill. Deep-merge order: wiki → machine → worktree-stub → worktree-real. The local `.millhouse/config.local.yaml` wins.

**Files to change:**
- `plugins/mill/skills/mill-merge-in/SKILL.md` — update Step 4, add allowlist pre-check.
- `plugins/mill/templates/wiki-config.yaml` — add commented `verify:` section.
- `C:/Code/millhouse/wiki/config.yaml` (production wiki config) — mirror the template change.

**No Python changes** — `iter_batch_verifies` in `_plan_dag.py` is unchanged.

## Constraints

- The check must be a no-op when `verify.skip_known_broken` is absent or empty (zero behaviour change for existing hubs).
- The allowlist must not mutate the verify command — skip or run, nothing in between.
- Log output must be on stdout so it appears in the mill-merge-in run log.
- Template mirrors production per CLAUDE.md invariant: any change to the template `verify:` section must be mirrored to `wiki/config.yaml`.

## Testing

No unit tests are added because no Python code is changed. The SKILL change is self-documenting and covered by the reviewer.

Manual verification path: set `verify.skip_known_broken: ["tests/foo/test_bar.py"]` in `.millhouse/config.local.yaml`, run `mill-merge-in` against a task whose plan has `verify: pytest tests/foo/test_bar.py -q`, confirm the log shows `[verify] skipped tests/foo/test_bar.py (allowlisted as known-broken)` and the command is not run.

## Q&A log

- **Q:** How should allowlisted entries be matched against verify commands? **A:** [auto-pick] Substring match. **Why:** Verify commands are author-controlled strings; authors write file paths literally. Substring match is correct for the common case and has no dependencies.
- **Q:** Should skipping apply to the entire verify command or filter individual files from it? **A:** [auto-pick] Skip entire verify command. **Why:** The spec says "consult before verify-gate is called" — bypass the call. Per-runner flag injection requires framework coupling.
- **Q:** Where should the allowlist check logic live? **A:** [auto-pick] mill-merge-in SKILL.md Step 4 only. **Why:** The skill is LLM-directed; a config-read + string-contains is a natural inline instruction, not a Python concern.
- **Q:** Where does `verify.skip_known_broken` live in the config hierarchy? **A:** [auto-pick] New `verify:` section in wiki-config.yaml template (commented), values in `.millhouse/config.local.yaml`. **Why:** Matches the spec's key name; template comment pattern established by `merge.verify_fix_rounds`.
- **Q:** What does the log line contain when a verify is skipped? **A:** [auto-pick] `[verify] skipped <allowlisted-path> (allowlisted as known-broken)`. **Why:** Exact spec text; logs the allowlisted path that triggered the skip.
