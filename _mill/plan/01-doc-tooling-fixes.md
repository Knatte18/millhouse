# Batch: doc-tooling-fixes

```yaml
task: "Skill doc/table accuracy gaps across mill-groom, mill-start/mill-plan, and implementer-brief"
batch: doc-tooling-fixes
number: 1
cards: 4
verify: null
depends-on: []
```

## Batch Scope

This batch delivers all four consolidated doc/tooling accuracy fixes from `discussion.md` in one pass: a stale wiki-junction check in `mill-groom`, a missing required CLI flag in `mill-start`'s Agent-mode dispatch text, a resume-safety gap in `mill-start`'s discussion-fix flow, and a missing ad-hoc-tooling convention in `CLAUDE.md`. It is one batch because the four fixes are small, independent, single-file (or single-section) prose edits with no shared interface — splitting them across batches would add DAG/dependency bookkeeping with zero benefit. There is no external interface for a later batch to consume; this is the only batch in the plan.

## Cards

### Card 1: mill-groom Entry checks — drop stale `.millhouse/wiki/` junction check

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-groom/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace the current two-step `## Entry checks` section (step 1: hardcoded `.millhouse/wiki/` existence test with the message `` `.millhouse/wiki/` junction missing. Run `/mill-setup` first. ``; step 2: a separate `_paths.resolve_wiki_path()` call storing the result as `<WIKI_PATH>`) with a single step that calls `_paths.resolve_wiki_path(_paths.resolve_git_root())` directly. On failure (the call raises or exits non-zero), stop and report exactly: "wiki path could not be resolved. Run `/mill-setup` first." On success, store the returned path as `<WIKI_PATH>`, matching the existing downstream usage of `<WIKI_PATH>` later in the file (`## Step 4 — Per-task action menu` and `## Step 6 — Apply (on approve)`). Remove every reference to the literal path `.millhouse/wiki/` from the `## Entry checks` section — no junction path is checked anymore.
- **Commit:** `docs(mill-groom): drop stale .millhouse/wiki/ junction check, resolve via _paths.resolve_wiki_path`

### Card 2: mill-start — name required `--agent-output` flag in finalize dispatch text

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Two edit sites, both in `### Phase: Discussion Review`:
  1. In step 2 (the "**Dispatch mode:**" paragraph), the sentence "Thread `--round <round>` from the prepare envelope into the finalize invocation unchanged (finalize has no round-cap check and never needs `--max-rounds`)." must be extended to also require `--agent-output <output_path>`, where `<output_path>` is the prepare envelope's `output_path` field (the same field already extracted per the general Agent-mode dispatch pattern's step 2 in `mill-go/SKILL.md`).
  2. In the "Step 3.5: ERROR-only-aggregate retry" subsection's Agent-mode paragraph, the matching sentence "Thread `--round <round>` from the prepare envelope into the finalize invocation unchanged." must receive the identical extension.

  Both sentences must end up naming `--agent-output <output_path>` explicitly, not just `--round <round>` — `millpy-review-discussion.py --stage finalize` exits 1 with `"ERROR: --agent-output required for finalize stage"` when the flag is omitted, so the doc text must match the CLI's actual required-argument contract.
- **Commit:** `docs(mill-start): name required --agent-output flag in finalize dispatch text`

### Card 3: mill-start — close discussion-fix-rN resume gap

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Two edit sites:
  1. **Interactive step 4b** (in `### Phase: Discussion Review`, the "On APPROVE with one or more `[NOTE]` findings" paragraph): immediately after the existing `Call \`_status.append_phase(status_path, f"discussion-fix-r{N}", _timestamp.now_utc_iso())\`.` sentence, add a second call: `_status.append_phase(status_path, "discussed", _timestamp.now_utc_iso())`. Both calls must land before the single git commit this paragraph already describes; the commit's pathspecs (`<discussion_path>`, `<reviews_dir>/`, `<status_path>`, `_mill/briefs/`) and commit message (`mill-start: discussion-fix round {N} for {slug}`) stay unchanged. Additionally, change the paragraph's closing "Push. Break loop → Handoff." to make clear that breaking out of the loop here does NOT re-invoke `### Phase: Handoff`'s own `_status.append_phase(status_path, "discussed", ...)` + commit steps (those would now be redundant — `phase:` is already `discussed` and both commits would otherwise duplicate the Timeline row and produce a second, near-empty commit). Instead, after 4b's push, go straight to Phase: Handoff's final report line: **"Discussion complete. Run `/mill-plan` next to start autonomous plan writing."** — e.g. reword to "Push. Report the Handoff completion message directly (do not re-run Phase: Handoff's status-append/commit — this path already reached `phase: discussed` above); do not invoke `/mill-plan` yourself." `### Phase: Handoff` itself stays unconditional and unchanged for the 4a (plain-APPROVE, no NOTEs) path, which never appends `discussed` on its own and still needs Handoff's append+commit to reach that phase.
  2. **`--auto` mode subsection's restatement** (in `## Auto mode`, the "Phase: Discussion Review — `--auto` changes" bullet list, the bullet beginning "On APPROVE, read the review file..."): the NOTE-handling clause currently re-enumerates the status-append/commit sequence independently ("...append `discussion-fix-r{N}` to the status timeline, single commit covering `<discussion_path>` + `<reviews_dir>/` + `<status_path>` + `_mill/briefs/` with message `mill-start: discussion-fix round {N} for {slug}`, push, break loop → Handoff."). Trim this so it no longer independently lists the status-append/commit mechanics, and instead delegates explicitly to interactive step 4b's full sequence (i.e. its status-append calls — both of them, per edit 1 above — and its commit, unchanged). Do NOT remove or alter this bullet's own NOTE-resolution semantics ("auto-resolve each NOTE by editing `<discussion_path>` using best judgment (per the `mill-receiving-review` decision tree, with PUSH BACK unavailable)") — that guarantee is separate from the status-append/commit mechanics being trimmed and must remain stated in this subsection (it is not duplicated by delegating to 4b, since 4b's own text does not restate the `--auto`-specific "best judgment / PUSH BACK unavailable" framing).
- **Commit:** `docs(mill-start): close discussion-fix-rN resume gap by appending discussed in the same commit`

### Card 4: CLAUDE.md — add ephemeral `uvx` lint convention

- **Context:**
  - `plugins/python/skills/python-build/SKILL.md`
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `## Conventions` section, add a new bullet immediately after the existing "Ad-hoc `dotnet build`/`dotnet test`..." bullet, in the same "Ad-hoc ... (when X isn't Y): ..." phrasing style. The new bullet must state: ad-hoc Python lint/format checks (when a project-specific `python-build` override isn't in place) should use `uvx ruff check .` — an ephemeral, non-project-mutating invocation — and must never use `uv add`/`uv sync` to install a lint tool for a one-off check.
- **Commit:** `docs(claude-md): add ephemeral uvx ruff convention for ad-hoc lint checks`

## Batch Tests

Pure documentation/markdown batch — no runnable code path, no test suite covers skill-doc or `CLAUDE.md` prose, hence `verify: null` at both batch and module-wide scope (per the overview's "verification is manual/inspection-only" Shared Decision). Verification is per-file inspection after implementation:

- **Card 1:** re-read `plugins/mill/skills/mill-groom/SKILL.md`'s `## Entry checks` section; confirm it no longer contains the string `.millhouse/wiki/` anywhere, and that the single `_paths.resolve_wiki_path()` call's failure path reports exactly "wiki path could not be resolved. Run `/mill-setup` first."
- **Card 2:** grep `plugins/mill/skills/mill-start/SKILL.md` for `--agent-output`; confirm both the step-2 and Step-3.5 "Thread `--round`..." sentences now include it, and that the phrasing is consistent with `mill-go/SKILL.md`'s step 6 ("from the prepare envelope's `output_path` field").
- **Card 3:** re-read interactive step 4b; confirm both `_status.append_phase` calls (`discussion-fix-r{N}` then `discussed`) appear before the single commit line, and that the paragraph now routes around `### Phase: Handoff`'s own append+commit instead of re-invoking it (no duplicate `discussed` Timeline row, no second commit on this path). Confirm `### Phase: Handoff` itself is unchanged and still runs normally for the 4a (no-NOTEs) path. Re-read the `--auto` mode subsection's restatement; confirm it delegates to step 4b instead of independently re-listing the status-append/commit sequence, and that its "best judgment / PUSH BACK unavailable" NOTE-handling sentence is still present.
- **Card 4:** re-read `CLAUDE.md`'s `## Conventions` section; confirm the new `uvx` bullet reads consistently with the existing dotnet bullet's style and does not contradict `python-build/SKILL.md`'s generic (non-`uv`-specific) guidance.
