# Plan: V3 wiki module with daemon and in-process cache

```yaml
task: V3 wiki module with daemon and in-process cache
slug: v3-wiki-module
approved: true
started: 20260522-111104
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: Wiki subpackage foundation
    file: 01-wiki-foundation.md
    depends-on: []
    verify: null
  - number: 2
    name: Git sync layer
    file: 02-wiki-sync.md
    depends-on: [1]
    verify: null
  - number: 3
    name: Generic daemon base
    file: 03-daemon-base.md
    depends-on: []
    verify: null
  - number: 4
    name: Wiki server
    file: 04-wiki-server.md
    depends-on: [1, 2, 3]
    verify: null
  - number: 5
    name: Wiki client
    file: 05-wiki-client.md
    depends-on: [4]
    verify: null
  - number: 6
    name: Unit tests
    file: 06-unit-tests.md
    depends-on: [5]
    verify: "PYTHONPATH=plugins/mill/scripts python plugins/mill/unit_tests/test-wiki-store.py && PYTHONPATH=plugins/mill/scripts python plugins/mill/unit_tests/test-wiki-protocol.py && PYTHONPATH=plugins/mill/scripts python plugins/mill/unit_tests/test-wiki-daemon.py && PYTHONPATH=plugins/mill/scripts python plugins/mill/unit_tests/test-wiki-sync.py"
  - number: 7
    name: Integration test and docs
    file: 07-integration-test.md
    depends-on: [6]
    verify: "PYTHONPATH=plugins/mill/scripts python plugins/mill/integration_tests/test-wiki-e2e.py"
```

## Shared Decisions

### Decision: stdlib-only

- **Decision:** Every file in `wiki/` and `_daemon.py` imports zero mill helpers. Standard library only.
- **Rationale:** The module must be mill-agnostic — parameterized by callers, reusable outside mill, testable in isolation.
- **Applies to:** all batches

### Decision: ascii-log-stdout

- **Decision:** All daemon log lines, `print()` calls, and stdout must be ASCII-only. Use `->` not `→`, `--` not `—`.
- **Rationale:** Windows cp1252 crashes on non-ASCII stdout.
- **Applies to:** all batches

### Decision: windows-compatible-subprocess

- **Decision:** Detached subprocess spawning in `_client.py` must work on Windows 11. Use the two-stage cmd.exe shim pattern (`["cmd", "/c", "start", "", "/B", "/MIN"] + cmd`) with `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB`. `DETACHED_PROCESS` is intentionally omitted — it causes a console flash when combined with `CREATE_NO_WINDOW` (documented in `_subprocess_util.popen_detached`; inlined here because mill imports are forbidden). On POSIX: `start_new_session=True`.
- **Applies to:** batches 5, 7

### Decision: utf8-wire

- **Decision:** All file content and socket payloads encode/decode as UTF-8. Wiki files contain non-ASCII (Norwegian text).
- **Applies to:** all batches

### Decision: no-mill-config

- **Decision:** The module never reads `mill-config.yaml` and never resolves the wiki path itself. All parameters (`wiki_path`, `idle_timeout`, `refresh_interval`) are passed in by the caller.
- **Applies to:** all batches

## All Files Touched

- `CLAUDE.md`
- `plugins/mill/integration_tests/test-wiki-e2e.py`
- `plugins/mill/scripts/_daemon.py`
- `plugins/mill/scripts/wiki/__init__.py`
- `plugins/mill/scripts/wiki/_client.py`
- `plugins/mill/scripts/wiki/_server.py`
- `plugins/mill/scripts/wiki/_store.py`
- `plugins/mill/scripts/wiki/_sync.py`
- `plugins/mill/unit_tests/run-all.py`
- `plugins/mill/unit_tests/test-wiki-daemon.py`
- `plugins/mill/unit_tests/test-wiki-protocol.py`
- `plugins/mill/unit_tests/test-wiki-store.py`
- `plugins/mill/unit_tests/test-wiki-sync.py`
