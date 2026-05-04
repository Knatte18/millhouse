# Batch: mill-go-skill-rewrite

```yaml
task: 6 — mill-go SKILL.md prose + lock-API + lock-coverage + Builder-oppførsel
batch: mill-go-skill-rewrite
cards: 7
verify: null
depends-on: [wiki-lock-unification, helper-api-additions]
```

## Batch Scope

This batch rewrites `plugins/mill/skills/mill-go/SKILL.md` end-to-end. It depends on B01 (new lock-API) and B02 (`set_phase_at`, `Skill` tool, brief tightening) for the new helper surfaces it references. It is the largest prose batch in the plan and folds in seven distinct issues: #15 (pseudocall), #16 / #19 / #81 (anti-pattern policy belongs in B06's workflow rules — but mill-go SKILL.md still needs explicit signature lines so the Builder doesn't have to read helpers), #25 (holistic carve-out), #28 / #49 / #51 / #61 / #76 / #98 (set_phase via wrapper), #72 (lock release order), #88 (transient row in Stuck table), #99 (path-invariants).

The cards split the SKILL.md by section so each card is reviewable in isolation. Cards 14–20 all modify the same file (`mill-go/SKILL.md`); the implementer commits one per card so the reviewer can read each section's diff against its purpose. No code changes ship in this batch — only SKILL.md prose. There is no `verify:` command because SKILL.md has no automated test surface; behavioural verification happens at the next mill-go integration run.

Batch-local decisions:

- **Explicit signature lines for every helper the Builder calls.** Each section that names a helper (`_active.read_slug`, `_status.append_phase`, `_status.set_batch_field`, `_status.update_field`, `_plan_dag.extract_batch_index`, `_plan_dag.validate`, `_plan_dag.topo_order`, `_implementer_sonnet.run`, `_review_common.parse_verdict`, `_tasks_md.set_phase_at`, `_wiki.write_commit_push`, `_wiki.wiki_lock`, `_builder_lock.acquire`, `_builder_lock.release`, `_notify.notify`, `_timestamp.now_utc_iso`) gets a one-line `signature:` annotation immediately after first reference. The annotation is the canonical signature in pseudo-Python form, with kwargs as `*, kwarg=...`. No prose elaboration; the signature line answers the question "how do I call this?" without the Builder ever needing to open the helper.
- **Pseudocall replacement.** Every `wiki.sync_pull()` / `wiki.<anything>()` in prose is replaced by the concrete invocation `_wiki.sync_pull(wiki_path, slug=<value>)` with `wiki_path` resolved via `_paths.resolve_wiki_path(_paths.resolve_git_root(Path.cwd()))`.
- **Path-invariant fix.** Every reference to `<WIKI_PATH>/active/<slug>/status.md`, `<WIKI_PATH>/active/<slug>/reviews/`, `<WIKI_PATH>/active/<slug>/plan/` is replaced by the worktree-root path (`status.md`, `reviews/`, `plan/`). Every `_wiki.write_commit_push(...)` for these files is replaced by `git -C <worktree> add <path> && git -C <worktree> commit -m "..."` (no push). The only surviving `_wiki.write_commit_push` call in mill-go SKILL.md is the Handoff Home.md flip.

## Cards

### Card 14: Rewrite Entry section — pseudocall replacement, path-invariant, explicit signatures

- **Reads:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_active.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_builder_lock.py`
  - `plugins/mill/scripts/_review_common.py`
- **Modifies:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Requirements:** Rewrite the `## Entry` section (currently lines 10–32). Step 1: read the task slug first — `slug = _active.read_slug(Path(".millhouse"))` — so the real task slug is available before any wiki access. Add `signature: _active.read_slug(mill_dir: Path) -> str` immediately after. Step 2: resolve the wiki path and call `_wiki.sync_pull(wiki_path, slug=slug)` — using the real task slug, NOT the literal `"mill-go"` (two concurrent mill-go sessions running different tasks would both use `"mill-go"` and overwrite each other's lock). Add `signature: _wiki.sync_pull(wiki_path: Path, *, slug: str) -> None`. Step 3: keep config-load instructions; pre-fix the `_review_common.load_config` call shape if mentioned by name. Step 4: keep builder-lock acquisition with explicit signature `_builder_lock.acquire(mill_dir: Path, slug: str) -> LockInfo`. Step 5: rewrite the phase gate's status.md path: `status_path = Path("status.md").resolve()` (worktree root, NOT `<WIKI_PATH>/active/<slug>/status.md`). Add `signature: _status.read_full(status_path: Path) -> dict` next to the read. Step 6: rewrite `<WIKI_PATH>/active/<slug>/plan/00-overview.md` to `Path("plan/00-overview.md").resolve()` (worktree root). Add explicit signatures for `_plan_dag.extract_batch_index`, `_plan_dag.validate`, `_plan_dag.topo_order` immediately after their first mention.
- **Commit:** `docs(mill-go): rewrite Entry — pseudocall + path-invariants + signatures`

### Card 15: Rewrite Prepare + Execute step 1 (Implement) — task-branch git ops for status.md

- **Reads:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_implementer_sonnet.py`
  - `plugins/mill/templates/implementer-brief.md`
- **Modifies:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Requirements:** Rewrite the `## Prepare` section (currently lines 34–40): replace `Commit+push via _wiki.write_commit_push(...)` with `Commit on the task branch: git -C <worktree> add status.md && git -C <worktree> commit -m "mill-go: prepare for {slug}"` (no push). Add explicit signature `_status.init_batches(status_path: Path, names: list[str]) -> None` and `_status.append_phase(status_path: Path, phase: str, timestamp: str) -> None`. Rewrite `## Execute — sequential loop / 1. Implement` (currently lines 42–66): every reference to `<WIKI_PATH>/active/<slug>/status.md` becomes `Path("status.md").resolve()`. Replace `Commit+push status.md` with `git -C <worktree> add status.md && git -C <worktree> commit -m "mill-go: start batch {batch_name}"`. Add explicit signature `_status.set_batch_field(status_path: Path, name: str, key: str, value: str | int | None) -> None`. Add explicit signature `_implementer_sonnet.run(prompt_text: str, *, session_id: str, resume: bool, cwd: Path) -> tuple[str, str]`. Note in passing that `_render.render` (B02) auto-strips the brief's leading HTML comment, so the prompt sent to Sonnet is comment-free.
- **Commit:** `docs(mill-go): rewrite Prepare + Execute step 1 — task-branch commits + signatures`

### Card 16: Rewrite Execute step 2 + step 3 (Code Review loop) — crash-recovery path, task-branch reviews/ commits

- **Reads:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_notify.py`
- **Modifies:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Requirements:** Rewrite `### 2. Parse implementer report` (currently lines 68–82): no path changes; clarify in passing that `commit_sha` is recorded via `_status.set_batch_field`. Rewrite `### 3. Code Review loop` (currently lines 84–113). Crash-recovery scan in step 1: change `<WIKI_PATH>/active/<slug>/reviews/` to `Path("reviews").resolve()`. Add explicit signature `_review_common.parse_verdict(text: str) -> str`. Step 4 APPROVE branch: change `Commit+push` to `git -C <worktree> add status.md && git -C <worktree> commit -m "mill-go: approve batch {batch_name}"`. Step 4 REQUEST_CHANGES branch: change `Commit+push` to `git -C <worktree> add status.md reviews/<file> && git -C <worktree> commit -m "mill-go: review-request batch {batch_name} round {N}"`. Max-rounds exhaustion (step 5): change `commit+push` to `git -C <worktree> add status.md && git -C <worktree> commit -m "mill-go: blocked on {batch_name} after {N} rounds"`. Read `_notify.py` to confirm the signature, then add explicit signature `_notify.notify(event: str, message: str, **fields) -> None`.
- **Commit:** `docs(mill-go): rewrite Code Review loop — task-branch commits + recovery path`

### Card 17: Add `LLMError` row to Stuck escalation table

- **Reads:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/scripts/_llm_claude.py`
- **Modifies:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Requirements:** In `### Stuck escalation` (currently lines 115–119), add a new bullet row above the existing `transient` row: "**`LLMError` from `_llm_claude.run_implementer`** (subprocess crashed before producing a JSON report) → treat as `stuck_type: transient`. Apply the existing one-retry policy: retry once with a fresh session (new UUID, `resume=False`). If the second attempt also raises `LLMError`, escalate to user with the regular `transient` three-option prompt (retry fresh, edit plan and retry, block)." This closes #88 — currently a subprocess crash halts the batch with no recovery. Mention that `_llm_claude.LLMError` is the catch target (not bare `Exception`) so genuine programmer errors still propagate.
- **Commit:** `docs(mill-go): add LLMError row to Stuck escalation table`

### Card 18: Drop holistic-review manual-only carve-out — auto-dispatch like per-batch

- **Reads:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Modifies:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Requirements:** Rewrite `## Holistic code review` (currently lines 127–133). Remove the "Simplification for v2.0" carve-out paragraph that says "do not auto-dispatch — surface the findings to the user with a two-option prompt". Replace with: "On `REQUEST_CHANGES` apply the same review-fix loop as per-batch — track holistic state via `_status.append_phase` with dedicated holistic phase names (`"holistic-reviewing"`, `"holistic-fixing"`, `"holistic-approved"`) rather than `_status.set_batch_field` (which would raise `ValueError: Batch 'holistic' not present` since 'holistic' is never initialized via `init_batches`). Spawn the implementer via `_implementer_sonnet.run(prompt_text, session_id=new_uuid, resume=False, cwd=worktree_path)` with the review file pointer (no resume — holistic review's findings span multiple batches; the implementer receives whole-worktree access). Add `signature: _implementer_sonnet.run(prompt_text: str, *, session_id: str, resume: bool, cwd: Path) -> tuple[str, str]`. Run the same review-fix loop until APPROVE or rounds-exhausted. On rounds-exhausted only, surface to user with the same blocked-batch halt prompt as per-batch flow." This closes #25. Keep the `NEED_CONTEXT` extra-files mechanic unchanged.
- **Commit:** `docs(mill-go): drop holistic-review manual-only carve-out`

### Card 19: Rewrite Handoff section — `set_phase_at`, `wiki_lock`, builder-lock release order

- **Reads:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_builder_lock.py`
- **Modifies:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Requirements:** Rewrite `## Handoff` (currently lines 135–143). Order of operations: (1) `_status.append_phase(status_path, "done", _timestamp.now_utc_iso())` against the worktree-root `status.md`; commit on the task branch via `git -C <worktree> add status.md && git -C <worktree> commit -m "mill-go: done {slug}"` (no push). (2) Flip Home.md's task line to `[done]`: `with _wiki.wiki_lock(wiki_path, slug): _tasks_md.set_phase_at(home_path, slug, "done"); _wiki.write_commit_push(wiki_path, ["Home.md"], f"task: complete {slug}", slug=slug)` — the lock-context wraps the read-modify-write atomically; `set_phase_at` (B02) does the read+transform+write itself; `write_commit_push` (B01) acquires the lock internally but the counter from `wiki_lock` makes that a no-op. Add explicit signatures: `_tasks_md.set_phase_at(path: Path, slug: str, phase: str | None) -> None`, `_wiki.wiki_lock(wiki_path: Path, slug: str) -> ContextManager[None]`, `_wiki.write_commit_push(wiki_path: Path, paths: list[str], msg: str, *, slug: str) -> None`. (3) `_notify.notify("mill-go.done", f"task {slug} complete", slug=slug)`. (4) **Release the builder lock immediately** via `_builder_lock.release(mill_dir)` with explicit signature `_builder_lock.release(mill_dir: Path) -> None`. (5) THEN, if `pipeline.auto_report` → invoke `/mill-self-report` and wait for it. (6) THEN, if `pipeline.auto_merge` → invoke `/mill-merge`; otherwise tell user to run `/mill-merge`. The reordering closes #72 — current SKILL.md holds the lock across both auto-* invocations.
- **Commit:** `docs(mill-go): rewrite Handoff — set_phase_at + wiki_lock + early lock release`

### Card 20: Rewrite Principles + Board discipline sections — accurate paths, signature policy

- **Reads:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Modifies:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Requirements:** Rewrite `## Principles` (currently lines 145–152) — keep the existing six bullets but add a seventh: "**Helper signatures are documented inline.** Every helper this skill names has an explicit one-line signature in the section that calls it. Never Read or Grep the helper source — the signature is here, and any failure surface as an exception. (See `mill:workflow` for the project-wide rule.)" Rewrite `## Board discipline` (currently lines 154–158) entirely: replace the three current bullets with four corrected ones — (1) "Status.md, reviews/<file>, and plan/<file> writes are committed on the **task branch** via `git -C <worktree> add ... && git -C <worktree> commit`. No push from per-card commits — mill-merge pushes the task branch at task end." (2) "Home.md writes (the Handoff `[done]` flip) go through `_wiki.write_commit_push(..., slug=...)` inside a `with _wiki.wiki_lock(wiki_path, slug):` block. The wiki helpers acquire the lock internally; the context manager makes the read-modify-write atomic." (3) "Phase transitions via `_status.append_phase`; batch-state mutations via `_status.set_batch_field`. Hand-editing either yaml block is banned." (4) "The path-invariant rule from CLAUDE.md is load-bearing: working state never goes to the wiki — only Home.md / _Sidebar.md do."
- **Commit:** `docs(mill-go): rewrite Principles + Board discipline`

## Batch Tests

No `verify:` command — this batch is pure SKILL.md prose. Behavioural verification happens at the next mill-go integration run, when a fresh Builder reads the rewritten SKILL.md and executes a real task end-to-end. The expected gain: zero TypeError on Handoff (set_phase_at), zero `Cannot fast-forward to multiple branches` on parallel mill-spawn (B01), zero "Builder reads helper source" tool calls (explicit signatures + B06's anti-pattern rule), correct status.md / reviews/ commits on the task branch (path-invariants), early builder-lock release (no contention with auto-report / auto-merge).
