# Discussion: mill-finalize/mill-merge-in citation-scan pathspec `:!_mill` fails on git 2.53+

```yaml
task: mill-finalize/mill-merge-in citation-scan pathspec `:!_mill` fails on git 2.53+
slug: mill-finalize-citation-scan-pathspec-magic-bug
status: discussing
parent: main
```

## Problem

On git 2.53.0+, the short-form exclude pathspec magic `:!<pattern>` fails outright when the character immediately following `!` is an underscore: `git grep ... -- . ':!_mill'` raises `fatal: Unimplemented pathspec magic '_' in ':!_mill'` instead of excluding the path. This is confirmed, standalone, independent of mill (`git ls-files -- ':!_foo.txt'` fails the same way; `':!README.md'`, with no leading underscore, works fine; `':(exclude)_foo.txt'` — the long-form spelling — succeeds as a drop-in replacement).

Two skills in this repo build exactly that pathspec to exclude the standard `_mill` task directory from a "citation scan" git-grep step (a non-blocking check for permanent-doc links to `_mill/discussion.md` that a cleanup commit is about to invalidate). Since `_mill` is the default `task_dir` for every mill task, this is not an edge case — the scan errors out on every PR-mode `mill-finalize` run and every `mill-merge` run on an affected git version. 11 duplicate GH issues (#1042, #1038, #1036, #1026, #1025, #1024, #1019, #1017, #1011, #1006, #1004) report this same bug.

## Scope

**In:**
- Convert the citation-scan snippet's four `:!<pattern>` short-form exclusions to the long-form `:(exclude)<pattern>` in:
  - `plugins/mill/skills/mill-finalize/SKILL.md` (Step 3, "Citation scan" — line 87)
  - `plugins/mill/skills/mill-merge/SKILL.md` (Step 4, "Citation scan" — line 287)
- Repo-wide audit for any other `:!<pattern>` short-form pathspec, per issue #1042's own suggested fix ("audit other mill skills for the same pattern"). Confirmed via `grep -rn "':!" plugins/`: no other occurrence exists.

**Out:**
- `plugins/mill/skills/mill-merge-in/SKILL.md` — does not contain any citation-scan snippet or `:!` pathspec in the current worktree, despite several duplicate issues (#1011, #1006, #1004) and this task's own title attributing the bug to it. See Decisions ("Scope correction").
- No Python/script changes — the affected text lives entirely inside fenced bash blocks in markdown `SKILL.md` files.
- No new automated test (see Testing).
- No git-version detection or conditional branch — the long-form syntax is a universal drop-in replacement, valid on every git version that supports pathspec magic at all, so there's nothing to detect.

## Decisions

### Long-form pathspec, not a version guard

- Decision: Replace `:!<pattern>` with `:(exclude)<pattern>` for all four exclusions in each of the two affected snippets.
- Rationale: `:(exclude)` is semantically identical to `:!` on every git version, confirmed as a drop-in replacement by issues #1042 and #1011 — both isolate the trigger to the underscore character right after `!`, not to `_mill` as a whole (`':!README.md'` still works). Switching syntax is strictly simpler and safer than adding version-detection logic to a markdown skill file.
- Rejected: Detecting the installed git version and branching syntax — no benefit, since the long form works unconditionally on every supported version.
- Rejected: Escaping/quoting the underscore — not a documented git pathspec mechanism; every duplicate issue's suggested fix is the long-form keyword, not an escape.

### Scope correction: mill-merge-in is not affected

- Decision: Do not edit `mill-merge-in/SKILL.md`. Treat the task title's and issues #1011/#1006/#1004's attribution of this snippet to `mill-merge-in` as inaccurate.
- Rationale: A full read of the current `plugins/mill/skills/mill-merge-in/SKILL.md` (258 lines: No-op check, Create checkpoint, Merge parent into current, Baseline recompute, Verify, Codeguide update, Commit dispatch briefs, Report) shows no citation-scan step and no `:!` pathspec anywhere. A repo-wide `grep -rn "':!" plugins/` returns exactly two hits, both outside mill-merge-in: `mill-finalize/SKILL.md:87` and `mill-merge/SKILL.md:287` — byte-for-byte the same four-pathspec snippet. The duplicate issues quoting a mill-merge-in citation-scan snippet are quoting text that is actually mill-merge's. Reading the live code takes priority over the task body/issue text when the two disagree.
- Rejected: Editing mill-merge-in anyway "to be safe" — there is nothing there to fix; adding an unrelated snippet to a skill that never had one is scope creep unsupported by the actual code.

### Fix all four pathspecs per snippet, not just `:!<task_dir>`

- Decision: Convert every one of the four `:!` exclusions in each snippet (`:!<task_dir>`, `:!plugins/**/SKILL.md`, `:!plugins/**/unit_tests/**`, `:!plugins/**/integration_tests/**`) to `:(exclude)` form, not only the one (`:!<task_dir>`) that demonstrably fails today.
- Rationale: Issue #1042's reporter did the same in their manual workaround ("swapped `:!_mill` for `:(exclude)_mill` (and the other three `:!` exclusions in the same snippet)"), and issue #1011's suggested fix names the other three exclusions explicitly. Mixing short- and long-form magic in one pathspec list is needless inconsistency, and leaving the other three in short form is latently fragile — any of them starting with an underscore in the future (or a `task_dir` rename to another underscore-prefixed name) would silently reintroduce this exact failure.
- Rejected: Leaving the three `plugins/**/...` exclusions in short form since none currently starts with `_` — true today, but converting all four costs nothing and removes the latent fragility.

## Technical context

Both affected snippets sit inside their skill's `## Steps` section as fenced ` ```bash ` blocks, executed via the Bash tool during `mill-finalize`'s PR Step 3 and `mill-merge`'s Step 4 (Cleanup commit), with `<task_dir>` and `<worktree>` substituted to their real runtime values (`task_dir` is `_mill` for every existing task in this repo, per `cfg['paths']`).

- `plugins/mill/skills/mill-finalize/SKILL.md` lines 83-96 ("Citation scan (non-blocking)"), failing invocation at lines 85-88:
  ```bash
  git -C <worktree> grep -InE '\]\([./]*_mill/discussion\.md\)' -- . \
      ':!<task_dir>' ':!plugins/**/SKILL.md' ':!plugins/**/unit_tests/**' ':!plugins/**/integration_tests/**'
  ```
- `plugins/mill/skills/mill-merge/SKILL.md` lines 283-294 ("Citation scan (non-blocking, #930)"), failing invocation at lines 285-288 — same pathspec list verbatim.
- Both blocks are followed by explanatory prose that describes the pathspec's *purpose* (excluding `task_dir` and this plugin's own tooling docs/tests from the citation grep) without quoting the pathspec syntax itself, so no prose needs to change alongside the bash block — only the fenced snippet's four pathspec tokens.
- The already-documented non-blocking behavior ("`git grep` exits 1 with empty stdout when nothing matches — that is the expected common case, not an error") covers the *no-matches* case only. The bug under fix here is a different failure mode: git refuses to even parse the pathspec (a fatal argument error), which currently aborts the scan rather than falling through to "no citations found" — the long-form fix restores the intended non-blocking behavior for the has-matches and no-matches cases alike.
- No other file in the repo uses `:!` pathspec magic — confirmed via `grep -rn "':!" plugins/`, which returns only the two lines above.
- No unit or integration test asserts on the literal text of either citation-scan snippet (checked `plugins/mill/unit_tests/` and `plugins/mill/integration_tests/` for `citation` and `:!` — no hits tied to this snippet), so no test needs updating alongside the fix.

## Constraints

No `CONSTRAINTS.md` file exists at the hub root. No constraints beyond the general repo conventions in `CLAUDE.md` apply — this fix is a direct `Edit`-tool text substitution inside two markdown files, not a `sed` invocation and not `print()`/`_log()` output.

## Testing

Documentation-only change to two markdown `SKILL.md` files — no application code, no script, no automated suite exercises the literal text of a fenced bash snippet inside a skill doc.

- **Manual verification (this task's `verify:` step):** after editing both snippets, run the corrected invocation directly against this worktree — `PYTHONPATH= git grep -InE '\]\([./]*_mill/discussion\.md\)' -- . ':(exclude)_mill' ':(exclude)plugins/**/SKILL.md' ':(exclude)plugins/**/unit_tests/**' ':(exclude)plugins/**/integration_tests/**'` — and confirm it exits 0 or 1-with-no-output (the documented no-matches case), never the `fatal: Unimplemented pathspec magic` error. Run this once per edited file's snippet (both use the identical pathspec list, so one invocation covers both after the substitution is applied consistently) from the worktree root. The leading `PYTHONPATH=` (literal, empty value) is required by CLAUDE.md's "Verify command shape" rule — this repo's `plugins/mill/pyproject.toml` marks it a Python project, so `_plan_validate.py`'s `verify-not-isolated` check requires the prefix on every plan `verify:` command regardless of whether the command itself invokes Python; mill-plan auto-prepends it on validator failure if the plan omits it.
- No new unit/integration test is warranted: the failure is in the installed git binary's version-specific pathspec parsing, not in any mill script, and no existing test harness parses or executes SKILL.md bash blocks.

## Q&A log

- **Q:** Which files does this task's fix actually touch — `mill-finalize`, `mill-merge`, and `mill-merge-in` as the task title and duplicate issues (#1011/#1006/#1004) suggest, or a narrower set? **A:** [auto-pick] Narrower set: only `mill-finalize/SKILL.md` and `mill-merge/SKILL.md`. A full read of `mill-merge-in/SKILL.md` plus a repo-wide grep confirm it has no citation-scan snippet or `:!` pathspec at all. **Why:** reading the actual current code takes priority over the task body/issue text per this run's governing instructions; several duplicate GH issues appear to misattribute mill-merge's snippet to mill-merge-in, but the live SKILL.md text does not support that attribution.
- **Q:** Convert only the demonstrably-broken `:!<task_dir>` exclusion, or all four `:!` exclusions in each snippet? **A:** [auto-pick] All four, in both snippets. **Why:** matches the reporter's own workaround and issue #1011's suggested fix; avoids leaving a latently fragile short-form pathspec that would silently reintroduce the bug on a future rename or an underscore-prefixed addition.
- **Q:** Add a git-version detection/branch instead of switching syntax unconditionally? **A:** [auto-pick] No — switch unconditionally. **Why:** `:(exclude)` is a universal drop-in replacement per the issue's own repro; a version branch adds complexity with no behavioral benefit.
