# Batch: bootstrap-posix-test

```yaml
task: "Port mill to POSIX, not just Windows"
batch: "bootstrap-posix-test"
number: 2
cards: 1
verify: PYTHONPATH= bash -n plugins/mill/integration_tests/test-bootstrap.sh
depends-on: []
```

## Batch Scope

Delivers `test-bootstrap.sh`, the POSIX counterpart of the existing
`test-bootstrap.ps1` Layer-01 end-to-end integration test, so the bootstrap
flow (mill-add producing a single commit, sidebar/Home updates, mill-list
readback) is runnable on Linux/macOS — the same treatment `update-plugins.ps1`
received when `update-plugins.sh` was added. Independent of batch 1 (touches a
different file, no shared surface), hence `depends-on: []`. This is a single-card
batch. The batch-local decision that differs from the overview: the per-round
`verify:` is a `bash -n` syntax gate rather than a full behavioral run, because
the authoritative behavioral verification of this integration test is a manual
one-off run (per `discussion.md` Testing: "run manually, not part of
`run-all.py`") — see `## Batch Tests`.

## Cards

### Card 6: Port test-bootstrap.ps1 to POSIX shell

- **Context:**
  - `plugins/mill/integration_tests/test-bootstrap.ps1`
- **Edits:** none
- **Creates:**
  - `plugins/mill/integration_tests/test-bootstrap.sh`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create `plugins/mill/integration_tests/test-bootstrap.sh` as
  a faithful POSIX-shell port of `test-bootstrap.ps1`, reproducing the same
  Layer-01 assertions: mill-add produces a single commit touching `Home.md` +
  `_Sidebar.md`, the sidebar contains the newly added task, and mill-list prints
  it back. Structural requirements: start with `#!/usr/bin/env bash` and
  `set -eu` (fail-loud posture); set `PYTHONIOENCODING=utf-8` before invoking any
  script (cp1252/ASCII-stdout safety); create the throwaway wiki + hub pair under
  `.scratch/` (never `$TMPDIR`, `/tmp`, or `$env:TEMP`, per the overview's
  no-tmp-use-scratch decision); resolve the venv python via the dual-existence
  probe from `mill-setup/SKILL.md:74`
  (`test -f "<root>/.venv/bin/python" && ... || ...`) or use `"$MILL_PYTHON"` if
  the `.ps1` does; keep all script output ASCII-only. Preconditions must fail
  loudly, not silently skip: before doing work, check `command -v uv` and
  `command -v git` and, if either is missing, print a clear message naming the
  missing tool and exit non-zero. If any assertion in the `.ps1` does not match
  current mill behavior (the M1.1-M1.4 scripts, `Home.md`/`_Sidebar.md`
  generation, or mill-list output may have evolved since the `.ps1` was written),
  adapt the assertion to current behavior so the ported script passes against
  the mill in this worktree — do NOT port a stale assertion verbatim. The
  deliverable is a script that both parses (`bash -n`) and, when run manually,
  passes against current mill.
- **Commit:** `test(integration): add POSIX test-bootstrap.sh counterpart`

## Batch Tests

`verify: PYTHONPATH= bash -n plugins/mill/integration_tests/test-bootstrap.sh`
is a shell syntax check — cheap, deterministic, and safe to run after every
implementer/fixer round. It is intentionally NOT a full behavioral run: the
authoritative verification of this integration test is a manual one-off
invocation (`bash plugins/mill/integration_tests/test-bootstrap.sh`), matching
`discussion.md`'s Testing section ("run manually, not part of `run-all.py`") and
the existing `.ps1`, which is likewise not wired into any automated suite. A
full bootstrap run each round would spin up a throwaway git+wiki+hub and is too
heavy for a per-round gate. The implementer MUST perform that manual run once
during implementation and confirm it passes (single commit touching `Home.md` +
`_Sidebar.md`, sidebar contains the task, mill-list readback) before completing
the card; if the underlying M1.1-M1.4 bootstrap flow has changed so
fundamentally that the scenario no longer applies, that is a stuck condition to
surface, not a silently-skipped assertion.
