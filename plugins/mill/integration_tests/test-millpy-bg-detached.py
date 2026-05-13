"""
Integration test: detached millpy-bg worker survives a job-bound parent.

Manufactures the job-bound parent condition via ctypes (CreateJobObjectW +
SetInformationJobObject(JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE) +
AssignProcessToJobObject(job, GetCurrentProcess())), spawns millpy-bg.py
from inside that job, and asserts both the WORKER START sentinel and the
EXIT sentinel land in the log file within budget.

This exercises the end-to-end behaviour of batch 1's two-stage cmd /c
start /B launch: the worker must escape the parent job object and write
both sentinels even when the parent process is kill-on-close enrolled.

Run from hub root:
    python plugins/mill/integration_tests/test-millpy-bg-detached.py

Exits 0 on PASS, 1 on any assertion failure.
Windows-only: exits 0 immediately with a SKIP message on POSIX.
"""
from __future__ import annotations

import os
import sys

if os.name != "nt":
    print("SKIP test-millpy-bg-detached: Windows-only")
    sys.exit(0)

import ctypes
import re
import subprocess
import time
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
# HANDLE is pointer-sized on 64-bit Windows; override the ctypes default (c_int)
# so handle values are not truncated.
kernel32.CreateJobObjectW.restype = ctypes.c_void_p
kernel32.SetInformationJobObject.restype = ctypes.c_int
kernel32.SetInformationJobObject.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32,
]
kernel32.AssignProcessToJobObject.restype = ctypes.c_int
kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
kernel32.CloseHandle.restype = ctypes.c_int
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (0x2000) is an extended flag and
    # must be set via JobObjectExtendedLimitInformation (info-class 9), not
    # via JobObjectBasicLimitInformation (info-class 2).
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> None:
    # os._exit(rc) is used for ALL exit paths so that ExitProcess(rc) runs and
    # records the exit code BEFORE Windows releases the job handle during handle-table
    # cleanup. If we used sys.exit + finally: CloseHandle(job), the finally block
    # would fire CloseHandle, which triggers KILL_ON_JOB_CLOSE on this very process
    # before sys.exit can record exit code 0. os._exit bypasses finally blocks and
    # calls ExitProcess directly; the job handle is released by the OS after the exit
    # code is already set, so the subsequent TerminateJobObject call is a no-op.
    rc = 1
    try:
        job = kernel32.CreateJobObjectW(None, None)
        _assert(job is not None, f"CreateJobObjectW failed: error={ctypes.get_last_error()}")

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = kernel32.SetInformationJobObject(
            job,
            9,  # JobObjectExtendedLimitInformation (required for KILL_ON_JOB_CLOSE)
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        _assert(ok, f"SetInformationJobObject failed: error={ctypes.get_last_error()}")

        # GetCurrentProcess() pseudo-handle is always (HANDLE)-1 on Windows;
        # pass as c_void_p to avoid 32-bit truncation on 64-bit processes.
        ok = kernel32.AssignProcessToJobObject(job, ctypes.c_void_p(-1))
        _assert(ok, f"AssignProcessToJobObject failed: error={ctypes.get_last_error()}")

        # Spawn millpy-bg.py from inside the job-bound test process.
        # PYTHONPATH injection is required: the worker subprocess imports
        # _subprocess_util from scripts/ which is not on sys.path by default.
        env = {**os.environ, "PYTHONPATH": str(SCRIPTS)}
        proc = subprocess.Popen(
            [
                sys.executable,
                str(SCRIPTS / "millpy-bg.py"),
                "--slug", "it-detach",
                "--",
                sys.executable, "-c", "print('hi')",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        out, err = proc.communicate()
        _assert(
            "log=" in out,
            f"millpy-bg.py did not print log=<path>; stdout={out!r} stderr={err!r}",
        )
        log_path = Path(out.strip().split(" log=", 1)[1])

        # Poll for START sentinel (within 5s) and EXIT sentinel (within 10s).
        start_re = re.compile(r"\[mill-bg\] WORKER PID=(\d+) START")
        t0 = time.monotonic()
        deadline_start = t0 + 5.0
        deadline_exit = t0 + 10.0

        worker_pid_str = None
        start_found = False
        exit_found = False

        while time.monotonic() < deadline_exit:
            if log_path.exists():
                text = log_path.read_text(encoding="utf-8", errors="replace")
                if not start_found:
                    m = start_re.search(text)
                    if m:
                        worker_pid_str = m.group(1)
                        start_found = True
                if start_found and "[mill-bg] EXIT" in text:
                    exit_found = True
                    break
            if not start_found and time.monotonic() > deadline_start:
                break
            time.sleep(0.5)

        _assert(start_found, f"START sentinel not found in log within 5s; log_path={log_path}")
        _assert(exit_found, f"EXIT sentinel not found in log within 10s; log_path={log_path}")

        # Worker emitted EXIT so it is done -- confirm via tasklist.
        tasklist = subprocess.run(
            ["tasklist", "/FI", f"PID eq {worker_pid_str}"],
            capture_output=True,
            text=True,
        )
        _assert(
            "No tasks are running which match the specified criteria" in tasklist.stdout,
            f"Worker PID {worker_pid_str} still alive after EXIT sentinel; "
            f"tasklist={tasklist.stdout!r}",
        )

        print("PASS -- millpy-bg detached worker survives job-bound parent", flush=True)
        rc = 0

    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr, flush=True)
    except Exception as exc:
        print(f"FAIL (unexpected): {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)

    os._exit(rc)


if __name__ == "__main__":
    main()
