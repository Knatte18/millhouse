"""
Integration test for per-batch verify-baseline capture and waiver, end-to-end.

`_mill/discussion.md`'s Testing section calls for real-git coverage of the whole `--stage baseline` / `--stage finalize` per-batch waiver mechanism (batches 3-6 of this plan): a fixture task whose one batch's `verify:` command has a pre-existing failure unrelated to the batch's own work, confirming `--stage baseline` captures that failure's signature and `--stage finalize` waives it on replay while still catching a genuinely new, distinct failure introduced later.

Layout mirrors `test-abandon.py` and `test-verify-baseline.py`:

    <container>/wiki.git bare "remote" for the wiki clone
    <container>/wiki wiki clone;
        task record seeded via `wiki._client.upsert_task` (the TinyDB-backed store, not a hand-written Home.md, is the wiki daemon's actual source of truth)
    <container>/hub hub repo (main branch), also the git-worktree source
    <container>/wts/<slug> the fixture task's linked worktree, on branch impl/<slug>

`millpy-implement.py --stage baseline` and `--stage finalize` are invoked as real subprocesses (mirroring production dispatch) with `PYTHONPATH` set to this repo's own `plugins/mill/scripts` directory (and `CLAUDE_PLUGIN_ROOT` removed from the child environment) so the fixture always exercises the worktree's own module code, never a stale plugin-cache copy.

The fixture batch's `verify:` command is a small tracked Python script (`verify_check.py`) at the worktree root, which starts out printing exactly one `FAILED ...`-shaped line and exiting 1 -- a "pre-existing" failure present on the parent branch (`main`) from the very first commit.

Three steps:

    1. `--stage baseline` against the fixture worktree: confirms the batch's `verify_baseline_failures` field in `status.md` is captured as a non-empty list containing the pre-existing failure's signature.
    2. Mutate `verify_check.py` to ALSO print a second, distinct `FAILED
    ...` line (simulating an implementer-introduced regression) while
    keeping the original failure;
        commit the mutation;
        invoke `--stage
    finalize` with a fabricated success `--agent-output`. Confirms the
    CLI's printed JSON reports `stuck_type: "verify"` (the new failure
    is not a subset of the baseline, so it is not waived).
    3. Revert `verify_check.py` back to producing only the original failure;
        commit the revert;
        re-invoke `--stage finalize` with a fresh success `--agent-output`.
        Confirms the CLI's printed JSON now reports `status: "success"` (the pre-existing-only failure set is a subset of the baseline and is waived).

Exits 0 on PASS, 1 on any failure;
scratch is preserved on failure for inspection.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
SCRATCH = HUB / ".scratch"

sys.path.insert(0, str(SCRIPTS))

import _safe_rmtree  # noqa: E402
import _status  # noqa: E402
from wiki import _client as _wiki_client  # noqa: E402

SLUG = "test-baseline-waiver-task"
BRANCH_PREFIX = "impl/"
BATCH_NAME = "fixture-batch"

_ORIGINAL_SCRIPT = (
    "import sys\n"
    "print('FAILED test_original')\n"
    "sys.exit(1)\n"
)

_REGRESSED_SCRIPT = (
    "import sys\n"
    "print('FAILED test_original')\n"
    "print('FAILED test_new_regression')\n"
    "sys.exit(1)\n"
)


def _run(
    cmd: list[str], *, cwd: Path, check: bool = True, env: dict | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _git_init(repo: Path) -> None:
    _run(["git", "init", "-b", "main", str(repo)], cwd=repo.parent)
    _run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
        cwd=repo,
    )
    _run(["git", "-C", str(repo), "config", "user.name", "Test"], cwd=repo)


def _cli_env() -> dict:
    """
    Env for every `millpy-implement.py` subprocess invocation: `PYTHONPATH` pinned to this worktree's own scripts dir and `CLAUDE_PLUGIN_ROOT` removed, so template/registry resolution falls back to the source tree next to `_config.py` (this worktree) rather than any installed plugin cache -- see CLAUDE.md's "Task-worktree path for source verification" and this module's own docstring.
    """
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(SCRIPTS)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    return env


def _setup_fixture(container: Path) -> tuple[Path, Path, Path, str]:
    """
    Build the wiki + hub + task-worktree fixture.

    Returns `(hub, wiki_clone, worktree, initial_sha)`.
    """
    container.mkdir(parents=True, exist_ok=True)
    bare = container / "wiki.git"
    wiki = container / "wiki"
    hub = container / "hub"

    # Bare wiki + clone.
    # The wiki daemon's actual source of truth is the TinyDB-backed tasks.json, not Home.md -- seed the task record via the real `wiki._client.upsert_task` API (same call production code such as millpy-add.py makes) so `_marker.slug_from_branch`'s `list_tasks_brief` lookup finds it.
    _run(["git", "init", "--bare", str(bare), "-b", "main"], cwd=container)
    _run(["git", "clone", str(bare), str(wiki)], cwd=container)
    _run(["git", "-C", str(wiki), "config", "user.email", "test@example.com"], cwd=container)
    _run(["git", "-C", str(wiki), "config", "user.name", "Test"], cwd=container)
    (wiki / ".keep").write_text("", encoding="utf-8")
    _run(["git", "-C", str(wiki), "add", "."], cwd=wiki)
    _run(["git", "-C", str(wiki), "commit", "-m", "seed"], cwd=wiki)
    _run(["git", "-C", str(wiki), "push", "origin", "main"], cwd=wiki)
    _wiki_client.upsert_task(
        wiki, SLUG, title="Test Baseline Waiver", status="active"
    )

    # Hub repo: main branch tip carries the pre-existing failure from the very first commit, plus the fixture's mill plan/status skeleton.
    hub.mkdir()
    _git_init(hub)

    (hub / "verify_check.py").write_text(_ORIGINAL_SCRIPT, encoding="utf-8")

    plan_dir = hub / "_mill" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    verify_cmd = f'PYTHONPATH= "{sys.executable}" "verify_check.py"'
    overview_text = (
        "# Plan: Test Baseline Waiver\n\n"
        "```yaml\n"
        "task: Test Baseline Waiver\n"
        f"slug: {SLUG}\n"
        "approved: true\n"
        "verify: null\n"
        "```\n\n"
        "## Batch Index\n\n"
        "```yaml\n"
        "batches:\n"
        f"  - name: {BATCH_NAME}\n"
        "    file: 01-fixture-batch.md\n"
        "    depends-on: []\n"
        "```\n"
    )
    (plan_dir / "00-overview.md").write_text(overview_text, encoding="utf-8")
    batch_text = (
        "# Batch: fixture-batch\n\n"
        "```yaml\n"
        f"batch: {BATCH_NAME}\n"
        f"verify: {verify_cmd}\n"
        "```\n\n"
        "## Cards\n\n"
        "No cards -- this fixture batch exists only to exercise the\n"
        "per-batch verify-baseline waiver mechanism end-to-end.\n"
    )
    (plan_dir / "01-fixture-batch.md").write_text(batch_text, encoding="utf-8")

    hub_mill = hub / ".millhouse"
    hub_mill.mkdir(exist_ok=True)
    (hub_mill / "config.local.yaml").write_text(
        f"paths:\n  wiki: {wiki.as_posix()}\nspawn:\n  branch_prefix: '{BRANCH_PREFIX}'\n",
        encoding="utf-8",
    )

    _run(["git", "-C", str(hub), "add", "."], cwd=hub)
    _run(["git", "-C", str(hub), "commit", "-m", "init: fixture task skeleton"], cwd=hub)

    # Task worktree, linked off hub's main tip, on branch impl/<slug>.
    wts_dir = container / "wts"
    wts_dir.mkdir()
    wt_path = wts_dir / SLUG
    _run(
        ["git", "-C", str(hub), "worktree", "add", "-b", f"{BRANCH_PREFIX}{SLUG}", str(wt_path), "main"],
        cwd=hub,
    )

    initial_sha = _run(["git", "rev-parse", "HEAD"], cwd=wt_path).stdout.strip()

    # Worktree-local .millhouse stub, mirroring the hub's config so path resolution succeeds when the CLI runs with cwd=wt_path.
    wt_mill = wt_path / ".millhouse"
    wt_mill.mkdir(exist_ok=True)
    (wt_mill / "config.local.yaml").write_text(
        f"paths:\n  wiki: {wiki.as_posix()}\nspawn:\n  branch_prefix: '{BRANCH_PREFIX}'\n",
        encoding="utf-8",
    )

    status_text = (
        "```yaml\n"
        "phase: implementing\n"
        f"slug: {SLUG}\n"
        "task: Test Baseline Waiver\n"
        f"branch: {BRANCH_PREFIX}{SLUG}\n"
        "parent: main\n"
        "```\n\n"
        "## Timeline\n\n"
        "```text\n"
        "implementing  2026-01-01T00:00:00Z\n"
        "```\n\n"
        "## Batches\n\n"
        "```yaml\n"
        "batches:\n"
        f"  - name: {BATCH_NAME}\n"
        "    state: running\n"
        f'    start_sha: "{initial_sha}"\n'
        "    implementer_session: test-session\n"
        "```\n"
    )
    _mill = wt_path / "_mill"
    (_mill / "status.md").write_text(status_text, encoding="utf-8")
    _run(["git", "-C", str(wt_path), "add", "_mill/status.md"], cwd=wt_path)
    _run(["git", "-C", str(wt_path), "commit", "-m", "seed: status.md"], cwd=wt_path)

    return hub, wiki, wt_path, initial_sha


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    container = SCRATCH / f"test-baseline-waiver-{uuid.uuid4().hex[:8]}"
    failed = False
    env = _cli_env()

    try:
        _hub, _wiki, worktree, _initial_sha = _setup_fixture(container)
        print(f"[test-baseline-waiver] container: {container}", file=sys.stderr)

        script = SCRIPTS / "millpy-implement.py"

        # --- Step 1: --stage baseline captures the pre-existing failure ---
        result = _run(
            [sys.executable, str(script), "--stage", "baseline"],
            cwd=worktree,
            check=False,
            env=env,
        )
        print(f"--- baseline stdout ---\n{result.stdout}", file=sys.stderr)
        print(f"--- baseline stderr ---\n{result.stderr}", file=sys.stderr)
        _assert(
            result.returncode == 0,
            f"--stage baseline: expected exit 0, got {result.returncode}",
        )

        status_path = worktree / "_mill" / "status.md"
        batches = _status.read_batches(status_path)
        entry = next((b for b in batches if b.get("name") == BATCH_NAME), None)
        _assert(entry is not None, f"batch {BATCH_NAME!r} missing from status.md after baseline")
        baseline_failures = entry.get("verify_baseline_failures")
        _assert(
            isinstance(baseline_failures, list) and len(baseline_failures) > 0,
            f"expected non-empty verify_baseline_failures, got {baseline_failures!r}",
        )
        _assert(
            any("FAILED test_original" in line for line in baseline_failures),
            f"expected 'FAILED test_original' in baseline signatures, got {baseline_failures!r}",
        )
        # --stage baseline wrote verify_baseline_failures directly into status.md without committing (production's mill-go commits this as part of its own housekeeping);
        # commit it here so the in-scope dirty-tree gate at finalize time sees a clean tree.
        _run(["git", "-C", str(worktree), "add", "_mill/status.md"], cwd=worktree)
        _run(
            ["git", "-C", str(worktree), "commit", "-m", "chore: record verify baseline"],
            cwd=worktree,
        )

        print(
            "PASS: step 1 -- --stage baseline captures the pre-existing failure's signature"
        )

        # --- Step 2: introduce a distinct second failure -- not waived ---
        (worktree / "verify_check.py").write_text(_REGRESSED_SCRIPT, encoding="utf-8")
        _run(["git", "-C", str(worktree), "add", "verify_check.py"], cwd=worktree)
        _run(
            ["git", "-C", str(worktree), "commit", "-m", "regress: introduce a second failure"],
            cwd=worktree,
        )

        agent_output_regressed = container / "agent-output-regressed.json"
        agent_output_regressed.write_text(
            json.dumps({"status": "success", "session_id": "test"}), encoding="utf-8"
        )

        result = _run(
            [
                sys.executable,
                str(script),
                BATCH_NAME,
                "--stage",
                "finalize",
                "--agent-output",
                str(agent_output_regressed),
            ],
            cwd=worktree,
            check=False,
            env=env,
        )
        print(f"--- finalize (regressed) stdout ---\n{result.stdout}", file=sys.stderr)
        print(f"--- finalize (regressed) stderr ---\n{result.stderr}", file=sys.stderr)
        _assert(
            result.returncode == 0,
            f"--stage finalize (regressed): expected exit 0, got {result.returncode}",
        )
        finalize_json = json.loads(result.stdout.strip().splitlines()[-1])
        _assert(
            finalize_json.get("status") == "stuck"
            and finalize_json.get("stuck_type") == "verify",
            f"expected stuck_type=verify for the new, non-baseline failure, got {finalize_json!r}",
        )
        print(
            "PASS: step 2 -- a genuinely new failure alongside the pre-existing one"
            " is NOT waived (stuck_type: verify)"
        )

        # --- Step 3: revert to only the pre-existing failure -- waived ---
        (worktree / "verify_check.py").write_text(_ORIGINAL_SCRIPT, encoding="utf-8")
        _run(["git", "-C", str(worktree), "add", "verify_check.py"], cwd=worktree)
        _run(
            ["git", "-C", str(worktree), "commit", "-m", "revert: back to pre-existing failure only"],
            cwd=worktree,
        )

        agent_output_clean = container / "agent-output-clean.json"
        agent_output_clean.write_text(
            json.dumps({"status": "success", "session_id": "test"}), encoding="utf-8"
        )

        result = _run(
            [
                sys.executable,
                str(script),
                BATCH_NAME,
                "--stage",
                "finalize",
                "--agent-output",
                str(agent_output_clean),
            ],
            cwd=worktree,
            check=False,
            env=env,
        )
        print(f"--- finalize (clean) stdout ---\n{result.stdout}", file=sys.stderr)
        print(f"--- finalize (clean) stderr ---\n{result.stderr}", file=sys.stderr)
        _assert(
            result.returncode == 0,
            f"--stage finalize (clean): expected exit 0, got {result.returncode}",
        )
        finalize_json = json.loads(result.stdout.strip().splitlines()[-1])
        _assert(
            finalize_json.get("status") == "success",
            f"expected status=success once only the pre-existing failure remains"
            f" (subset-diff waiver), got {finalize_json!r}",
        )
        print(
            "PASS: step 3 -- a pre-existing-only failure set is waived (status: success)"
        )

        print("PASS -- per-batch baseline capture and waiver end-to-end (3/3 steps)")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        failed = True
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL (unexpected): {type(exc).__name__}: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        failed = True
        return 1
    finally:
        if failed:
            print(f"Scratch preserved: {container}", file=sys.stderr)
        else:
            try:
                worktree = container / "wts" / SLUG
                if worktree.exists():
                    _run(
                        ["git", "worktree", "remove", "--force", str(worktree)],
                        cwd=container / "hub",
                        check=False,
                    )
            except Exception:
                pass
            _safe_rmtree.safe_rmtree(container, allowed_root=container, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
