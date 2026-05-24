# Review: Adopt V3 wiki module in V2 scripts

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md (round 2)
date: 2026-05-24
```

## Findings

### [GAP] Migration "single commit" contradicts per-mutation daemon commits
**Section:** Technical Context → Migration script anatomy (steps 5–6)
**Issue:** Step 5 says the daemon renders and commits after every `upsert_task` call (existing `commit_push` flow confirmed in `_sync.py:182–183` and `_server.py:_handle_write`). Step 6 claims the migration produces a "single commit." These are mutually exclusive: N tasks → N commits, each staging `tasks.json` + a growing `Home.md`.
**Fix:** Resolve the design before planning. Options: add a deferred-commit / batch-upsert protocol op, have the migration script write `tasks.json` directly via TinyDB and trigger one render+commit (contradicts "no bypass" in step 4), or drop the "single commit" claim and accept N commits.

### [GAP] `_review_common.py` wiki/config.yaml fallback not in scope
**Section:** Scope → purge-wiki-config-yaml / Constraints
**Issue:** `_review_common.py:1237,1248–1263,1269` contains an identical `wiki/config.yaml` fallback to the one being stripped from `_config.py`. The constraint states "No `wiki/config.yaml` references anywhere in shipping code." Confirmed by reading the file — the fallback is runtime code, not a comment.
**Fix:** Add `_review_common.py` (lines ~1233–1270) to the `purge-wiki-config-yaml` scope alongside `_config.py`.

### [GAP] `millpy-spawn.py:68` wiki/config.yaml reference omitted from call-site table
**Section:** Technical Context → V2 call sites table / Scope → Port every V2 call site
**Issue:** `millpy-spawn.py:68` constructs `wiki_cfg = resolve_wiki_path(repo_root) / "config.yaml"` (same direct-path pattern explicitly fixed in `millpy-claim.py:68`). The call-site table lists only `millpy-spawn.py:128` (`sync_pull`). After the purge this path reference violates the stated constraint.
**Fix:** Add `millpy-spawn.py:68` to the scope; update `_load_config`'s missing-config guard to reference only `mill-config.yaml`.

### [NOTE] `millpy-fold.py:99` uses `_tasks_md.LOCKED_FOLD_PHASES` (module deleted)
**Section:** Scope → Port every V2 call site (millpy-fold.py)
**Issue:** `millpy-fold.py:99` imports `_tasks_md.LOCKED_FOLD_PHASES` at runtime; `_tasks_md.py` is deleted in this task. The call-site entry covers only lines 87 and 144. Also, `millpy-fold.py:15` has a local duplicate of the constant — the plan writer needs to reconcile both.
**Fix:** Add `millpy-fold.py:99` (import) and `:15` (dead local duplicate) to the `millpy-fold.py` migration entry.

## Verdict

GAPS_FOUND
Three blocking issues: migration-commit design contradiction, and two omitted `wiki/config.yaml` call sites.