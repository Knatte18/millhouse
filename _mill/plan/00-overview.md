# Plan: mill-go-base: orchestration robustness gaps

```yaml
task: "mill-go-base: orchestration robustness gaps"
slug: mill-go-base-orchestration-robustness-gaps
approved: false
started: "20260918-181719"
parent: main
root: ""
verify: null
discussion_sha: "8c07242b7797b163ecc9c181783f6a051a8fbb09"
```

## Batch Index

```yaml
batches:
  - number: 1
    name: status-helpers-core
    file: 01-status-helpers-core.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-status.py
  - number: 2
    name: status-helpers-baseline
    file: 02-status-helpers-baseline.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py test-millpy-implement.py
  - number: 3
    name: entry-gate-parallel-baseline
    file: 03-entry-gate-parallel-baseline.md
    depends-on: [2, 5]
    verify: PYTHONPATH= uv run --project plugins/mill python -c "import pathlib; t = pathlib.Path('plugins/mill/skills/mill-go-base/SKILL.md').read_text(encoding='utf-8'); assert 'baseline_preflight_log' in t, 'missing baseline_preflight_log marker'; assert '--module-wide-only' in t, 'missing --module-wide-only marker'; assert 'Restart/orphan reconciliation' in t, 'missing restart/orphan reconciliation marker'; print('ok')"
  - number: 4
    name: blocked-batch-resume
    file: 04-blocked-batch-resume.md
    depends-on: [1, 6]
    verify: PYTHONPATH= uv run --project plugins/mill python -c "import pathlib; s = pathlib.Path('plugins/mill/skills/mill-go-base/SKILL.md').read_text(encoding='utf-8'); r = pathlib.Path('plugins/mill/skills/mill-go-base/resume.md').read_text(encoding='utf-8'); assert 'resume_batch' in s, 'missing resume_batch marker in SKILL.md'; assert 'resuming a blocked batch after external fix' in s, 'missing new subsection heading in SKILL.md'; assert 'resume_batch' in r or 'resuming a blocked batch after external fix' in r, 'missing cross-reference in resume.md'; print('ok')"
  - number: 5
    name: review-loop-fixes
    file: 05-review-loop-fixes.md
    depends-on: [1, 4]
    verify: null
  - number: 6
    name: agent-dispatch-liveness
    file: 06-agent-dispatch-liveness.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python -c "import pathlib; t = pathlib.Path('plugins/mill/skills/mill-go-base/SKILL.md').read_text(encoding='utf-8'); n = t.count('must never be read, logged, or otherwise acted on'); assert n >= 3, f'expected >=3 write-only warnings, found {n}'; assert 'already confirmed the agent is no longer running' in t, 'missing #1001 fallback-trigger rewording marker'; print('ok')"
  - number: 7
    name: handoff-worktree-guard
    file: 07-handoff-worktree-guard.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python -c "import pathlib; t = pathlib.Path('plugins/mill/skills/mill-go-base/handoff.md').read_text(encoding='utf-8'); assert 'already cleaned up' in t, 'missing existence-check-and-skip marker'; window = t.split('mill-self-report')[0][-800:]; assert 'worktree_root' in window, 'worktree_root existence check not found near self-report step'; print('ok')"
```

## Shared Decisions

### Decision: seven independent robustness fixes, batched by shared-file/shared-dependency locality

- **Decision:** Two foundation batches (1, 2) add pure-Python helpers to `_status.py`/`millpy-implement.py`; five downstream batches (3-7) edit `mill-go-base`'s prose skill files (`SKILL.md`, `holistic-review.md`, `handoff.md`, `resume.md`), each fixing one or two of the seven source issues (#1031, #1013, #1005, #1001, #997, #995, #990 — see `_mill/discussion.md` for full per-issue analysis). Batch 3 depends on batch 2 (needs the new `baseline_preflight_log` helpers and `--module-wide-only` flag); batches 4 and 5 depend on batch 1 (need `resume_batch` and the `latest=True` mode respectively). Batches 6 and 7 have no Python dependency and are root batches.
- **Rationale:** `_status.py` (61,222 bytes) and its own test file `test-status.py` (74,099 bytes) are both large enough that a card citing both in `Edits:` costs ~33,830 estimated context tokens; `SKILL.md` (106,797 bytes) alone costs ~26,700 tokens per citing card. Splitting the Python additions into two smaller batches (rather than one batch with 4+ cards each repeating these large files) and keeping each prose batch to 1-2 cards keeps every batch comfortably under `pipeline.max_batch_context_tokens` (120,000) — see each batch's own Batch Scope for its estimate.
- **Applies to:** all batches.

### Decision: prose-only batches verify via exact-marker grep/python assertions, not a test suite

- **Decision:** Batches 3-7 edit only markdown skill-instruction files with no executable surface of their own. Each such batch's frontmatter `verify:` runs a small `python -c` snippet asserting the presence of specific, code-identifier-like literal strings (flag names, function names, exact mandated headings/phrases) in the edited file(s) — never a prose-similarity or exact-paragraph match. Each card's `Requirements:` mandates the implementer write the exact literal string the batch's `verify:` checks for, so the check is deterministic regardless of surrounding prose phrasing.
- **Rationale:** There is no existing automated content-checker for `mill-go-base`'s skill markdown files (they are LLM-read instructions, not parsed code) and running the full unregisted-to-this-task unit test suite as a stand-in would be a weak, indirect signal. A targeted marker-presence check is cheap, deterministic, and directly verifies "did this specific required edit land," which is the one thing a prose-editing card can meaningfully self-check.
- **Applies to:** batches 3, 4, 5, 6, 7.

### Decision: `pipeline.done_gate` left `null` — two pre-existing, unrelated failures in the full suite

- **Decision:** Per mill-plan's "Done-gate reminder" guidance, the candidate repo-wide check `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` was run against the current worktree tip (before any of this plan's changes) and does NOT exit 0: `FAIL -- 2 of 113 in 12.3s: ['test-mill-go-base-agent-only.py', 'test-millpy-validate-plan.py']`. `test-mill-go-base-agent-only.py` fails because it bans the literal strings `psmux`/`millpy-bg`/`dispatch == subprocess` anywhere in `SKILL.md`, but the current, shipping `SKILL.md` still legitimately documents the subprocess/psmux dispatch branch throughout (this test appears to be scaffolding for a future agent-only variant of `mill-go-base`, not yet applicable to the file as it stands). Both failures are unrelated to this task's seven fixes and pre-exist this plan entirely. `done_gate` is left `null` rather than set to this candidate command, per the guidance's explicit instruction not to make every future task in the hub depend on unrelated pre-existing debt.
- **Rationale:** Setting `done_gate` to a command that already fails for reasons outside this task's scope would spuriously block Handoff on unrelated debt every time this or any future task in the hub runs to completion.
- **Applies to:** all batches (overview-level `verify:`/`done_gate`, not a per-batch field).

## All Files Touched

- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-go-base/handoff.md`
- `plugins/mill/skills/mill-go-base/holistic-review.md`
- `plugins/mill/skills/mill-go-base/resume.md`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-status.py`
