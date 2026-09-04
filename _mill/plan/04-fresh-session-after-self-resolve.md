# Batch: fresh-session-after-self-resolve

```yaml
task: 'millpy-implement/fix.py: stuck-type false positives and session-hygiene gaps'
batch: fresh-session-after-self-resolve
number: 4
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py test-millpy-implement.py
depends-on: [1]
```

## Batch Scope

Fixes #956: `millpy-implement.py --stage prepare`, re-fired without `--resume-incomplete` after a batch self-resolved from a `verify`/`logic` stuck classification, reuses the stale `session_id`/`start_sha` from the original stuck attempt instead of minting fresh ones — contradicting `mill-go-base/SKILL.md`'s documented "fresh batch start" behavior for this exact case. The root cause: self-resolve (per `SKILL.md:905,924-925`) only appends a `self-resolved-verify-logic` phase entry via `_status.append_phase` and commits a plan edit — it never changes the batch's `state` field away from `"running"`, so a self-resolved re-fire is structurally indistinguishable from a genuine transient-dispatch-failure re-fire to the existing `_prepare_reuse_entry` reuse heuristic (which keys only on `state == "running"` + a set `implementer_session`). This batch narrows that heuristic to also consult the phase timeline, and adds a batch-scoped `self_resolve_remint_at` field (not a phase-timeline append — that would collide with the task-level `phase:` field `mill-go-base/SKILL.md`'s crash-recovery table depends on) so a self-resolve marker's effect on the reuse gate is bounded to exactly one fresh mint, never an unbounded chain of them on later transient retries of the same freshly-minted session. Depends on batch 1 only because both batches edit `plugins/mill/scripts/millpy-implement.py` (different functions — batch 1 edits the `--stage finalize` branch, this batch edits the `--stage prepare`/`full` three-way branch — sequencing avoids a same-file parallel-edit conflict, not a functional dependency).

## Cards

### Card 8: `_status.py` — extend `_BATCH_ALLOWED_KEYS` with `self_resolve_remint_at`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  `_BATCH_ALLOWED_KEYS` is the closed set both `set_batch_field` and `set_batch_fields` validate every key against, raising `ValueError` for anything outside it:
  ```python
_BATCH_ALLOWED_KEYS = {
    "state",
    "implementer_session",
    "commit_sha",
    "start_sha",
    "review_round",
    "review_file",
    "blocked_reason",
    "verify_baseline_failures",
}
  ```
  Add `"self_resolve_remint_at",` as a new entry (any position in the set literal — order is not significant for a `set`). This field will hold an ISO-8601 UTC timestamp string, matching the value shape already used by other timestamp-carrying fields in this codebase; no new type validation is needed since `set_batch_field`/`set_batch_fields` accept `str | int | list[str] | None` for any allowed key uniformly.
- **Commit:** `fix(status): allow self_resolve_remint_at as a batch field`

### Card 9: test — `self_resolve_remint_at` round-trips through `set_batch_fields`

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add one new test case to the existing "--- set_batch_fields tests ---" section (immediately after the existing "Success path: multiple fields written atomically" case, which calls `set_batch_fields(sp, "foundation", {"state": "running", "implementer_session": "sess123", "start_sha": "abc"})` and asserts each field round-trips via `read_batches`): a new case calling `set_batch_fields(sp, "foundation", {"self_resolve_remint_at": "2026-09-04T10:49:08Z"})` on a fresh fixture, then asserting `read_batches` returns that exact string for the `self_resolve_remint_at` key on the `"foundation"` entry. Print a `PASS: set_batch_fields writes and round-trips self_resolve_remint_at` line matching this file's existing print-per-case convention.

  Do not add a new negative (unknown-key-rejected) test — the existing "Unknown key raises ValueError" case (`set_batch_fields(sp, "foundation", {"nope": "x"})`) already exercises a key that remains outside `_BATCH_ALLOWED_KEYS` after Card 8's extension, so it already covers the "genuinely unknown keys still rejected" regression without duplication.
- **Commit:** `test(status): cover self_resolve_remint_at round-trip`

### Card 10: `millpy-implement.py` — narrow the prepare-reuse gate and record the remint marker

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Replace the existing `_prepare_reuse_entry` computation block (the `if args.stage == "prepare" and not args.resume_incomplete:` block that sets `_prepare_reuse_entry = _prepare_candidate` whenever `_prepare_candidate.get("state") == "running"` and `_prepare_candidate.get("implementer_session")` is truthy) with a version that also detects an unreacted self-resolve marker and, when found, withholds reuse. Initialize a new variable `_self_resolve_remint_ts = None` at the same top-level scope as the existing `_prepare_reuse_entry = None` initializer (both must be defined regardless of `args.stage`, since the fresh-mint branch below reads `_self_resolve_remint_ts` even when this block never executes — e.g. for `--stage full`, whose fresh-mint-always contract must not change per this file's own existing comment on that constraint).

  Inside the existing `if (_prepare_candidate is not None and _prepare_candidate.get("state") == "running" and _prepare_candidate.get("implementer_session")):` guard, before setting `_prepare_reuse_entry`, add the timeline check:
  ```python
              _timeline = _status.read_full(status_path)["timeline"]
              if _timeline:
                  _last_parts = _timeline[-1].split(None, 1)
                  if len(_last_parts) > 1 and _last_parts[0] == "self-resolved-verify-logic":
                      _self_resolve_remint_ts = _last_parts[1].strip("'\"")
              _already_reminted = (
                  _self_resolve_remint_ts is not None
                  and _prepare_candidate.get("self_resolve_remint_at") == _self_resolve_remint_ts
              )
              if _self_resolve_remint_ts is None or _already_reminted:
                  _prepare_reuse_entry = _prepare_candidate
  ```
  This replaces the guard's previous unconditional `_prepare_reuse_entry = _prepare_candidate` assignment. `_status.read_full` is `_status.py`'s existing `read_full(status_path) -> {"yaml": dict, "timeline": list[str]}` (already imported via the existing `import _status` in this file); its `timeline` list holds raw `"<phase> <timestamp>"` rows in file order, so `timeline[-1]` is the most recent phase entry and `.split(None, 1)` separates the phase token from the (quoted) timestamp, mirroring the exact parsing `_status.phase_entry_timestamp` already uses internally — the `.strip("'\"")` call strips the surrounding quotes the timestamp is written with. `"self-resolved-verify-logic"` is the literal phase string `mill-go-base/SKILL.md`'s per-batch self-resolve step already appends via `_status.append_phase`; `self-resolved-dead-parent` is deliberately NOT checked here, since it never precedes a "re-fire the implementer fresh" step (it fires mid-flow during a success-report cleanliness gate, not before a re-dispatch).

  In the fresh-mint `else:` branch (the branch that captures a fresh `start_sha`, mints a fresh `session_id`, and calls `_status.set_batch_fields(status_path, args.batch_name, {"state": "running", "start_sha": start_sha, "implementer_session": session_id})`), replace that `_status.set_batch_fields(...)` call with a version that additionally records the remint marker only when `_self_resolve_remint_ts` is set (i.e., only when this fresh mint was actually triggered by an unreacted self-resolve, not an ordinary first-pass dispatch):
  ```python
        _fresh_mint_fields = {
            "state": "running",
            "start_sha": start_sha,
            "implementer_session": session_id,
        }
        if _self_resolve_remint_ts is not None:
            _fresh_mint_fields["self_resolve_remint_at"] = _self_resolve_remint_ts
        _status.set_batch_fields(status_path, args.batch_name, _fresh_mint_fields)
  ```
  This is the same `set_batch_fields` call already present (only rewrites the `## Batches` block, never the task-level `phase:` field), so it folds into the fresh-mint branch's existing single "mill-go: start batch {batch_name}" commit — no new commit is introduced by this card.
- **Commit:** `fix(implement): mint a fresh session after an unreacted self-resolve, bounded to one remint`

### Card 11: tests — fresh-mint-after-self-resolve, bounded to one remint

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add four new test cases to `plugins/mill/unit_tests/test-millpy-implement.py`, following this file's existing `_make_fixture`-based fixture pattern and `main(argv)` in-process invocation style:
  1. Build a status.md fixture where a batch's entry has `state: running`, a set `implementer_session`, no `self_resolve_remint_at` field, and the status.md `## Timeline` block's most recent row is `self-resolved-verify-logic '<some ISO timestamp>'`. Invoke `--stage prepare` for that batch with no `--resume-incomplete` flag. Assert the returned prepare envelope's `session_id` and `start_sha` are **not** equal to the fixture's original recorded values (a fresh `session_id`/current-HEAD `start_sha` were minted), and assert the batch's status entry now has `self_resolve_remint_at` equal to the self-resolve row's own timestamp.
  2. The existing "prepare-reuse" happy path — same fixture shape but with the `## Timeline` block's most recent row being an ordinary phase (not a self-resolve marker) — must still reuse: assert the returned `session_id`/`start_sha` **equal** the fixture's original recorded values. This is a regression guard for #625/#635/#643 (session-id churn on legitimate transient-retry re-dispatch) — confirm this case is not newly broken by Card 10's change.
  3. **Compounding-retry regression:** starting from case 1's post-state (batch's status entry now carries `self_resolve_remint_at` equal to the self-resolve row's timestamp, `## Timeline`'s most recent row unchanged), invoke `--stage prepare` for the same batch a *second* time with no `--resume-incomplete` flag (simulating a transient-retry re-fire of the just-fresh-minted session). Assert this second call reuses — returns the **same** `session_id`/`start_sha` case 1's fresh mint produced, not a third distinct pair — proving the self-resolve marker's effect is bounded to exactly one remint.
  4. **Phase-field isolation:** across case 1's fresh-mint call, assert `status.md`'s top-level `phase:` YAML value (read via `_status.read_full(status_path)["yaml"]["phase"]`) is unchanged by the `--stage prepare` call (still whatever it was before the call — the fresh-mint branch's `set_batch_fields` call must never touch it). This guards against a future edit reintroducing an `_status.append_phase`-based marker, which would collide with `mill-go-base/SKILL.md`'s phase-gate crash-recovery table.
- **Commit:** `test(implement): cover fresh-mint-after-self-resolve and its one-remint bound`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/run-all.py --only test-status.py test-millpy-implement.py`, covering both edited files' full existing regression suites plus every case this batch adds. Scoped to these two files rather than the full suite since this batch touches only `_status.py` and `millpy-implement.py`.
