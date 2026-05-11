# Plan: 49 (A) — Defensive guards mot cwd-inni-wiki kjedereaksjoner

```yaml
task: 49 (A) — Defensive guards mot cwd-inni-wiki kjedereaksjoner
slug: fix-wiki-cwd-cascade
approved: true
started: 20260511-120733
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches. Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: defensive-guards
    file: 01-defensive-guards.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 2
    name: anti-pattern-walker-test
    file: 02-anti-pattern-walker-test.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 3
    name: docs-claude-md-and-skills
    file: 03-docs-claude-md-and-skills.md
    depends-on: []
    verify: null
  - number: 4
    name: wiki-log-cleanup
    file: 04-wiki-log-cleanup.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: error-message-text

- **Decision:** All new guards use the literal English error message: `"cwd is inside wiki ({wiki_path}) — scripts must run from a task worktree or the main repo, not the wiki. Wiki mutations go through git -C <wiki_path> or _wiki.write_commit_push."` where `{wiki_path}` is substituted with the detected wiki path (or `git_toplevel` when the wiki path is unresolvable and only the name check fires). `_sibling.resolve_path` uses its own message: `"resolve_path called from wiki repo — wiki cannot resolve its own wiki path"`.
- **Rationale:** Uniform error strings are grep-friendly and the `mill-receiving-review` skill audits anti-patterns by grepping for these. Matches the discussion's `language` and `guard-error-type` decisions.
- **Applies to:** batches 1, 3.

### Decision: identical-twin-rule

- **Decision:** Any code-level change to `plugins/mill/scripts/_sibling.py` is mirrored byte-for-byte (outside the module docstring) to `plugins/codeguide/scripts/_sibling.py`. The existing test in `plugins/mill/unit_tests/test-sibling.py` asserts the two files are byte-equal modulo their module docstrings; new code must keep that test passing.
- **Rationale:** Documented at the top of both files and enforced by the existing identical-twin test. Matches the discussion's `sibling-guard` decision.
- **Applies to:** batch 1.

### Decision: no-allowlist-in-code

- **Decision:** The new anti-pattern walker test allowlists only documentation files that intentionally quote the anti-pattern: `CLAUDE.md` at the repo root, plus the eight SKILL.md files updated by batch 3. No code paths are allowlisted. Adding new allowlist entries in the future requires a documented justification in the test file.
- **Rationale:** The codebase has no legitimate cwd-in-wiki case today; any future match is a regression. Documentation files are the only legitimate place to mention the anti-pattern. Matches the discussion's `test-design` decision.
- **Applies to:** batch 2.

### Decision: documentation-language

- **Decision:** All new prose in `CLAUDE.md` and the eight SKILL.md notes is written in English, matching the surrounding files. The proposal in the wiki is in Norwegian; that language is not propagated.
- **Rationale:** Codebase prose is uniformly English; mixing languages fragments grep results and reading flow. Matches the discussion's `language` decision.
- **Applies to:** batch 3.

## All Files Touched

- `CLAUDE.md`
- `plugins/codeguide/scripts/_sibling.py`
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/_sibling.py`
- `plugins/mill/skills/mill-claim/SKILL.md`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/skills/mill-spawn/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/skills/mill-wiki-push/SKILL.md`
- `plugins/mill/unit_tests/test-no-wiki-cwd.py`
- `plugins/mill/unit_tests/test-paths.py`
- `plugins/mill/unit_tests/test-sibling.py`
