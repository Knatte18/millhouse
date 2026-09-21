"""Discover and run every ``test-*.py`` in this directory.

Exits 0 when all tests pass, 1 when any fails.
Each test runs in its own subprocess, parallelised across CPU cores.
Per-test stdout/stderr is buffered and printed atomically after the test finishes so output from
concurrent runs does not interleave.
Override the worker count with ``--jobs N`` (default: ``os.cpu_count()``).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent

SKIP: frozenset[str] = frozenset({"test-wiki-sync.py"})


def _run_one(test: Path, env: dict) -> tuple[str, int, float, str]:
    t0 = time.monotonic()
    result = subprocess.run(
        [sys.executable, str(test)],
        capture_output=True,
        text=True,
        env=env,
        cwd=HERE,
    )
    elapsed = time.monotonic() - t0
    # Combine stdout and stderr to a single block so interleave is impossible.
    output = (result.stdout or "") + (result.stderr or "")
    return test.name, result.returncode, elapsed, output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--jobs", "-j", type=int, default=os.cpu_count() or 4,
        help="Number of parallel workers (default: %(default)s).",
    )
    parser.add_argument(
        "--sequential", action="store_true",
        help="Run tests one at a time. Equivalent to --jobs 1.",
    )
    parser.add_argument(
        "--only", nargs="+", default=None, metavar="TEST",
        help="Run only the named test files (basenames, e.g. test-fold.py). "
             "Use this in per-batch verify: commands to scope a batch's test "
             "run to only the files its Edits/Creates affect. Unknown names fail.",
    )
    args = parser.parse_args()
    jobs = 1 if args.sequential else max(1, args.jobs)

    all_test_files = sorted(HERE.glob("test-*.py"))
    if not all_test_files:
        print("No test-*.py files found.", file=sys.stderr)
        return 1

    if args.only:
        # --only names a file explicitly, so SKIP (which only trims the unbounded default run) must
        # not make an otherwise-valid name look unknown.
        by_name = {p.name: p for p in all_test_files}
        unknown = [n for n in args.only if n not in by_name]
        if unknown:
            print(f"--only: unknown test file(s): {unknown}", file=sys.stderr)
            return 1
        tests = [by_name[n] for n in args.only]
    else:
        tests = [p for p in all_test_files if p.name not in SKIP]

    # Force UTF-8 I/O so test output containing non-ASCII characters (e.g.
    # the -> arrow in pick_task_single_or_multi output) doesn't crash on Windows consoles that default to cp1252.
    child_env = os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"

    print(f"Running {len(tests)} tests across {jobs} worker(s).", file=sys.stderr)
    t_start = time.monotonic()

    failures: list[str] = []
    timings: list[tuple[str, float, int]] = []

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(_run_one, test, child_env): test for test in tests}
        for fut in as_completed(futures):
            name, rc, elapsed, output = fut.result()
            timings.append((name, elapsed, rc))
            marker = "PASS" if rc == 0 else "FAIL"
            print(f"--- {marker} {name} ({elapsed:.1f}s) ---", file=sys.stderr)
            if output:
                sys.stdout.write(output)
                sys.stdout.flush()
            if rc != 0:
                failures.append(name)

    total = time.monotonic() - t_start
    timings.sort(key=lambda r: -r[1])
    print("", file=sys.stderr)
    print("Slowest 10:", file=sys.stderr)
    for name, elapsed, rc in timings[:10]:
        print(f"  {elapsed:6.1f}s  {name}", file=sys.stderr)

    print("", file=sys.stderr)
    if failures:
        print(f"FAIL -- {len(failures)} of {len(tests)} in {total:.1f}s: {failures}", file=sys.stderr)
        return 1
    print(f"PASS -- all {len(tests)} unit tests in {total:.1f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
