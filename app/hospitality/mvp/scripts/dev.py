#!/usr/bin/env python
"""Cross-OS dev launcher for a Ttest prefab workspace (BDAI-1588 FR-1).

Replaces the POSIX-only `dev.sh`. Reads `run.services` from
`.ttest/config.yaml`, performs first-run bootstrap (env files, backend venv,
frontend node_modules), starts every service as a child process, tees their
combined output to this process's stdout, and tears every child down when this
process exits or is signalled.

Teardown deliberately reuses the SAME primitives Ttest's own `runner.stop_run`
uses -- `taskkill /T /F /PID` on Windows, `os.killpg` on POSIX -- rather than
`CREATE_NEW_PROCESS_GROUP` + `CTRL_BREAK_EVENT`, so there is one teardown
mechanism in the system instead of two that must agree (FR-1a).

[M9, 6-reviewer remediation round] That reuse is only a partial safety net.
Ttest's Stop button (`runner.stop_run`) sends its OWN termination straight to
this launcher process: on Windows `taskkill /T` walks and kills the launcher's
whole descendant tree, so Ttest's Stop button really does reap every child
here. On POSIX, `start_new_session=True` (see `spawn()`) puts each child in
its OWN session, so `os.killpg(os.getpgid(<launcher pid>), ...)` reaches only
the launcher itself -- it can never see into a child's separate session. On
POSIX, reaping every child when the launcher is killed depends entirely on
this file's own SIGTERM/SIGINT handlers running `shutdown()` below; a SIGKILL
of the launcher (which cannot be handled) would orphan the children.
"""

from __future__ import annotations

import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / ".ttest" / "config.yaml"
IS_WINDOWS = sys.platform == "win32"

# [M5/A8] `signal.SIGKILL` is POSIX-only and absent from `signal` on Windows.
# The only place this file reads it is the POSIX branch of shutdown()'s
# escalation, which never runs for real on Windows (guarded by IS_WINDOWS).
# Resolve it once into a module-local so importing this file into a test
# process never mutates the process-global `signal` module.
_SIGKILL = getattr(signal, "SIGKILL", signal.SIGTERM)

DEFAULT_BACKEND_PORT = 8000
DEFAULT_FRONTEND_PORT = 3100

# [M6/A1] ONE shared teardown budget across ALL children, not 5s each.
# `runner.stop_run` gives the WHOLE launcher process 5s total before it
# SIGKILLs it (runner.py:85-89); the launcher's children run in their OWN
# sessions (`start_new_session=True`, see `spawn()`), so runner's `proc.kill()`
# never reaches them -- only this file's `shutdown()` can, and it must finish
# BEFORE runner's 5s elapses. Keep the budget strictly under that 5s.
_SHUTDOWN_TIMEOUT_SECONDS = 4.0

_children: list[subprocess.Popen] = []

# [A2] Guard so `shutdown()` runs its teardown exactly once even though both a
# signal handler and main()'s `finally` call it on the same Stop -- running it
# twice doubles the overrun past runner's 5s.
_shutdown_done = False


# ---------------------------------------------------------------------------
# [C2] Command allowlist -- restated locally, not imported. `dev.py` is a
# prefab template asset (`backend/prefabs/**`), never part of the
# `ttest` package, so it cannot import `routes.py`'s private constants.
# Mirrors `_ALLOWED_RUN_PREFIXES` / `_RUN_METACHAR_RE` (routes.py:298-315)
# exactly: `.ttest/config.yaml` is writable via `PUT …/file` (routes.py:1997),
# which enforces path containment only, not content, so a malicious
# `run.services[*].cmd` written there must still be rejected here, before it
# ever reaches `subprocess.Popen(cmd, shell=True)` in `spawn()`.
# ---------------------------------------------------------------------------

_ALLOWED_CMD_PREFIXES = frozenset(
    {
        "npm",
        "npx",
        "yarn",
        "pnpm",
        "bun",
        "node",
        "next",
        "vite",
        "python",
        "python3",
        "bash",
        "make",
        "sh",
    }
)
_CMD_METACHAR_RE = re.compile(r"[;&|`$<>\n(){}]")
# [A11] This gate is deliberately WIDER than routes.py's exact-token match: it
# accepts the allowlisted bare names above AND an absolute or versioned
# interpreter path matched by its basename (e.g. `/usr/bin/python3.11`,
# `C:/venv/Scripts/python.exe`). `_is_allowed_cmd` runs in `read_services()`,
# BEFORE `spawn()`'s D7 venv rewrite, so it never sees an interpreter path this
# file produced -- the widening exists because `.ttest/config.yaml` is an
# agent-writable sandbox that may legitimately already carry such a path.
_PYTHON_BASENAME_RE = re.compile(r"^python3?(\.\d+)?(\.exe)?$", re.IGNORECASE)


def _is_allowed_cmd(cmd: str) -> bool:
    """Same gate as `routes.py`'s `_validate_run_command`, applied to a
    service read back out of `.ttest/config.yaml` instead of a `/runs`
    request body."""
    if _CMD_METACHAR_RE.search(cmd):
        return False
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return False
    if not tokens:
        return False
    name = Path(tokens[0]).name
    return name in _ALLOWED_CMD_PREFIXES or bool(_PYTHON_BASENAME_RE.match(name))


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def read_services() -> list[dict]:
    """Return `run.services` from .ttest/config.yaml, or a sane default pair."""
    # FR-10 shape: bare allowlisted `cmd`, directory in `cwd`.
    fallback = [
        {
            "name": "backend",
            "cwd": "backend",
            "cmd": f"python -m uvicorn app.main:app --host 0.0.0.0 --port {DEFAULT_BACKEND_PORT} --reload",
            "port": DEFAULT_BACKEND_PORT,
        },
        {
            "name": "frontend",
            "cwd": "frontend",
            "cmd": f"npm run dev -- -p {DEFAULT_FRONTEND_PORT}",
            "port": DEFAULT_FRONTEND_PORT,
        },
    ]
    # [A7] The hardcoded `fallback` is returned ONLY when the config file does
    # not exist. Once it EXISTS, a silent fallback to the default ports
    # (8000/3100) is forbidden -- `_create_ttest_dir` assigns DYNAMIC ports
    # (prefab_resolver.py), so binding the defaults would bind ports Ttest isn't
    # watching (the M7 failure). Any parse failure, or a config that yields zero
    # usable services, fails loudly instead.
    if not CONFIG_PATH.is_file():
        return fallback

    # [M7] `dev.py` runs under whatever `python`/`python3` is first on PATH, not
    # the venv this script bootstraps, so a missing PyYAML is a live path.
    try:
        import yaml
    except ImportError as exc:
        print(f"[dev.py] PyYAML is required to read {CONFIG_PATH.name}: {exc!r}")
        raise SystemExit(1) from exc

    def _abort(reason: str):
        print(
            f"[dev.py] {CONFIG_PATH.name} exists but {reason}; refusing to fall back "
            "to hardcoded default ports Ttest isn't watching"
        )
        raise SystemExit(1)

    try:
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 -- a drifted config must fail loudly, not silently
        _abort(f"could not be parsed as YAML: {exc!r}")
    if not isinstance(config, dict):
        _abort("did not parse to a mapping")
    run = config.get("run")
    if not isinstance(run, dict):
        _abort("has no usable run mapping")
    services = run.get("services")
    if not isinstance(services, list):
        _abort("has no run.services list")
    parsed = [s for s in services if isinstance(s, dict) and isinstance(s.get("cmd"), str)]
    gated = []
    for service in parsed:
        if _is_allowed_cmd(service["cmd"]):
            gated.append(service)
        else:
            print(
                f"[dev.py] dropping service {service.get('name')!r}: "
                "cmd failed the allowlist gate (C2)"
            )
    if not gated:
        _abort("has no service that passed the allowlist gate")
    return gated


# ---------------------------------------------------------------------------
# First-run bootstrap (ported from the retired dev.sh)
# ---------------------------------------------------------------------------


def bootstrap_env_files() -> None:
    """Seed backend/.env and frontend/.env.local from .env.example when missing.

    Next.js only ever reads .env* from its own cwd, so each side needs its own
    copy -- neither reads the workspace-root .env.example.
    """
    example = ROOT / ".env.example"
    if not example.is_file():
        return
    for target in (ROOT / "backend" / ".env", ROOT / "frontend" / ".env.local"):
        if target.parent.is_dir() and not target.is_file():
            target.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"[dev.py] created {target.relative_to(ROOT)} from .env.example")


def backend_python() -> str:
    """Path to the backend venv interpreter, creating and populating the venv once.

    [M8] Raises `SystemExit` when venv creation leaves no interpreter behind,
    instead of degrading to `sys.executable` -- that degrade path skipped
    straight past the `import fastapi` probe and the `pip install -e .` step
    below, so uvicorn would start against a bare interpreter with none of the
    app's dependencies installed. The retired `dev.sh` (:57-60) always reached
    its own install step.
    """
    backend = ROOT / "backend"
    venv = backend / ".venv"
    exe = venv / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")
    if not backend.is_dir():
        return sys.executable
    if not exe.is_file():
        print("[dev.py] creating backend virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=False)
    if not exe.is_file():
        print("[dev.py] failed to create the backend virtual environment; aborting")
        raise SystemExit(1)
    probe = subprocess.run([str(exe), "-c", "import fastapi"], capture_output=True, check=False)
    if probe.returncode != 0:
        print("[dev.py] installing backend dependencies...")
        subprocess.run(
            [str(exe), "-m", "pip", "install", "-e", ".", "--quiet"],
            cwd=str(backend),
            env=_pip_constraint_env(backend),
            check=False,
        )
    return str(exe)


def _pip_constraint_env(backend: Path) -> dict[str, str] | None:
    """The environment that points pip, and its isolated build environment, at
    ``backend/constraints.txt``; ``None`` (pip's own) when the file is not there. A path
    with whitespace or a character outside printable ASCII becomes the relative
    ``constraints.txt`` (pip splits on whitespace)."""
    constraints = backend / "constraints.txt"
    if not constraints.is_file():
        return None
    path = str(constraints.resolve())
    if any(not "!" <= char <= "~" for char in path):
        # pip splits these variables on (Unicode) whitespace; the install runs in backend/.
        # Same rule as the Makefile and dev.sh: anything outside printable ASCII.
        print(
            "[dev.py] WARNING: the path to backend/constraints.txt contains whitespace "
            "or a character outside printable ASCII, so pip gets the relative path "
            "constraints.txt",
            file=sys.stderr,
        )
        path = constraints.name
    return {**os.environ, "PIP_CONSTRAINT": path, "PIP_BUILD_CONSTRAINT": path}


def bootstrap_frontend() -> None:
    """npm install once, mirroring dev.sh's --legacy-peer-deps retry."""
    frontend = ROOT / "frontend"
    if not frontend.is_dir():
        return
    marker = frontend / "node_modules" / ".bin" / ("next.cmd" if IS_WINDOWS else "next")
    if marker.exists():
        return
    print("[dev.py] installing frontend dependencies...")
    if subprocess.run("npm install", cwd=str(frontend), shell=True, check=False).returncode != 0:
        print("[dev.py] npm install failed, retrying with --legacy-peer-deps...")
        subprocess.run("npm install --legacy-peer-deps", cwd=str(frontend), shell=True, check=False)


# ---------------------------------------------------------------------------
# Spawn + tee
# ---------------------------------------------------------------------------


def spawn(service: dict, backend_py: str) -> subprocess.Popen | None:
    name = str(service.get("name") or "service")
    cmd = str(service.get("cmd"))
    # FR-10: the directory is carried in `cwd`, and `cmd` is a bare allowlisted
    # invocation -- there is no `cd <dir> &&` prefix to strip. A declared cwd
    # that is missing or escapes falls back to the workspace root, mirroring
    # what routes._resolve_service_cwd does on the Ttest side (FR-10b).
    cwd = ROOT
    declared = service.get("cwd")
    if isinstance(declared, str) and declared:
        # [A6] the resolve + containment block is inside its own try/except: a
        # malformed `cwd` (e.g. an embedded NUL) makes `.resolve()` raise, and
        # that must NOT abort the spawn loop and orphan already-started
        # siblings. A missing, non-string or escaping value falls back to the
        # workspace root (FR-10b).
        try:
            candidate = (ROOT / declared).resolve()
            if candidate.is_dir() and (candidate == ROOT or ROOT in candidate.parents):
                cwd = candidate
        except (ValueError, OSError):
            cwd = ROOT
    # D7: a bare `python` token resolves to whatever is first on PATH, which is
    # NOT the .venv this script's own bootstrap just populated with
    # `pip install -e .`. Redirect it to the venv interpreter.
    if backend_py:
        parts = cmd.split(maxsplit=1)
        if parts and parts[0] in ("python", "python3"):
            cmd = f'"{backend_py}"' + (f" {parts[1]}" if len(parts) > 1 else "")
    # [M4] `start_new_session=True`, not `preexec_fn=os.setsid` -- by the time
    # the 2nd+ `Popen` runs, a `tee` thread from the 1st child is already
    # live, and CPython's docs call `preexec_fn` unsafe in a multi-threaded
    # process (it runs arbitrary Python between fork and exec).
    kwargs = {} if IS_WINDOWS else {"start_new_session": True}
    print(f"[dev.py] starting {name}: {cmd}")
    try:
        # [A4] `encoding="utf-8", errors="replace"`: without an explicit
        # encoding, `text=True` decodes the child's pipe with the locale
        # codec (cp1252 on Windows), so any UTF-8 multibyte in npm/Next.js
        # output raises UnicodeDecodeError, kills the only drain thread, fills
        # the 64 KiB pipe and hangs the server forever holding its port.
        # `PYTHONUNBUFFERED=1` so a generated FastAPI app's own prints reach the
        # Run log (mirrors the M3 fix one level up).
        return subprocess.Popen(
            cmd,
            cwd=str(cwd),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            **kwargs,
        )
    except Exception as exc:  # noqa: BLE001 -- one bad service must not abort the rest
        print(f"[dev.py] failed to start {name}: {exc!r}")
        return None


def tee(name: str, proc: subprocess.Popen) -> None:
    if proc.stdout is None:
        return
    # [A4] never let a decode/read error kill the only drain thread -- keep
    # draining to EOF so the child's pipe cannot fill and hang the server.
    try:
        for line in proc.stdout:
            sys.stdout.write(f"[{name}] {line}")
            sys.stdout.flush()
    except Exception as exc:  # noqa: BLE001 -- best-effort drain, must not die
        # [A4] self-standing: keep the drain alive no matter what. Emit a
        # best-effort diagnostic -- round-tripped through stdout's own codec with
        # errors="replace" so exc!r's glyphs (e.g. Next.js's ▲) can't raise
        # UnicodeEncodeError even if main()'s reconfigure no-opped -- but NEVER let
        # the diagnostic itself abort the drain: swallow any error from it (a
        # broken/closed stdout could still raise OSError/ValueError) so the pipe
        # drain below always runs.
        try:
            _enc = getattr(sys.stdout, "encoding", None) or "utf-8"
            _msg = f"[dev.py] {name} log stream error: {exc!r}"
            print(_msg.encode(_enc, "replace").decode(_enc, "replace"))
        except Exception:  # noqa: BLE001 -- diagnostic is best-effort, never fatal
            pass
        try:
            for _ in proc.stdout:
                pass
        except Exception:  # noqa: BLE001 -- drained as far as possible
            pass


# ---------------------------------------------------------------------------
# Windows hard-kill safety net
# ---------------------------------------------------------------------------

_windows_job_handle: int | None = None


def _bind_windows_job_object() -> None:
    """Windows only: put this process (and therefore every future child, which
    inherits job membership on creation) in a Job Object with
    KILL_ON_JOB_CLOSE, so children still die even when THIS process is killed
    in a way that gives it zero chance to run any Python code.

    `taskkill /T` (what Ttest's own Stop button uses, see the module
    docstring's M9 note) already walks the process tree without this. This
    covers the harsher case: a bare `TerminateProcess` (what
    `subprocess.Popen.terminate()` calls on Windows) or a crash never invokes
    a signal handler on Windows at all -- Python code in this file simply
    never runs -- so `shutdown()` below cannot be the only safety net.

    Best-effort only: if job creation/assignment fails for any reason (e.g.
    this process is already in a job that forbids nesting on an old Windows),
    this silently no-ops and the graceful SIGINT/SIGTERM handlers remain the
    sole cleanup path, same as before this function existed.
    """
    global _windows_job_handle
    try:
        import ctypes
        from ctypes import wintypes

        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
        JobObjectExtendedLimitInformation = 9

        class _IO_COUNTERS(ctypes.Structure):
            _fields_ = [(f, ctypes.c_uint64) for f in ("Rd", "Wr", "Ot", "RdT", "WrT", "OtT")]

        class _BASIC_LIMIT(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class _EXTENDED_LIMIT(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _BASIC_LIMIT),
                ("IoInfo", _IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        # use_last_error + explicit argtypes/restype are required here: the
        # ctypes default (c_int) truncates the pseudo-handle GetCurrentProcess()
        # returns (0xFFFFFFFFFFFFFFFF on 64-bit), which makes
        # AssignProcessToJobObject fail with ERROR_INVALID_HANDLE even though
        # every argument LOOKS right when printed.
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.GetCurrentProcess.argtypes = []
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            err = ctypes.get_last_error() if hasattr(ctypes, "get_last_error") else "?"
            print(
                f"[dev.py] job-object bind failed (GetLastError={err}); "
                "children may survive a hard kill"
            )
            return
        info = _EXTENDED_LIMIT()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(
            job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)
        ):
            err = ctypes.get_last_error() if hasattr(ctypes, "get_last_error") else "?"
            print(
                f"[dev.py] job-object bind failed (GetLastError={err}); "
                "children may survive a hard kill"
            )
            kernel32.CloseHandle(job)
            return
        if not kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()):
            err = ctypes.get_last_error() if hasattr(ctypes, "get_last_error") else "?"
            print(
                f"[dev.py] job-object bind failed (GetLastError={err}); "
                "children may survive a hard kill"
            )
            kernel32.CloseHandle(job)
            return
        _windows_job_handle = job  # keep alive: closing it would trigger the kill NOW
    except Exception as exc:  # noqa: BLE001 -- best-effort only, see docstring
        print(f"[dev.py] job-object unavailable: {exc!r}")


# ---------------------------------------------------------------------------
# Teardown -- the same primitives runner.stop_run uses (FR-1a)
# ---------------------------------------------------------------------------


def shutdown(*_args) -> None:
    # [A2] run the teardown exactly once -- both a signal handler and main()'s
    # `finally` call this on the same Stop, and a second pass only doubles the
    # overrun past runner.stop_run's 5s budget.
    global _shutdown_done
    if _shutdown_done:
        return
    _shutdown_done = True

    # A second Stop arriving mid-reap must not re-enter a handler and unwind
    # `sys.exit(0)` out of the wait loop below, skipping escalation and orphaning
    # not-yet-reaped children. Ignore further stop signals for the teardown.
    # (Runs in the main thread on both call paths -- signal handler and main()'s
    # `finally` -- so signal.signal is legal here.)
    for _sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(_sig, signal.SIG_IGN)
        except (ValueError, OSError):  # noqa: BLE001 -- off-main-thread / unsupported
            pass

    for proc in _children:
        if proc.poll() is not None:
            continue
        try:
            if IS_WINDOWS:
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                    check=False,
                    capture_output=True,
                )
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:  # noqa: BLE001 -- best-effort reap, then fall back
            try:
                proc.terminate()
            except Exception:  # noqa: BLE001
                pass

    # [M6/A1] ONE monotonic deadline computed once, shared across every child:
    # an instantly-exiting child donates its slice to a slow sibling, and the
    # whole teardown stays inside `_SHUTDOWN_TIMEOUT_SECONDS` (strictly under
    # runner.stop_run's 5s before it SIGKILLs this launcher).
    deadline = time.monotonic() + _SHUTDOWN_TIMEOUT_SECONDS
    for proc in _children:
        try:
            proc.wait(timeout=max(0.0, deadline - time.monotonic()))
        except Exception:  # noqa: BLE001
            # [M5] escalate to the whole process GROUP, not a single PID --
            # `proc.kill()` alone only kills the `shell=True` Popen's own
            # child (the shell), never the real server that
            # `start_new_session` put into its own group, and orphans it
            # still holding the port.
            try:
                if IS_WINDOWS:
                    proc.kill()
                else:
                    os.killpg(os.getpgid(proc.pid), _SIGKILL)
            except Exception:  # noqa: BLE001
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    pass


def main() -> int:
    # [M3] Ttest spawns this launcher with the bare interpreter tokens
    # (constants.py:187-188, no `-u`) into a PIPE, so stdout is block-buffered
    # by default and every print() sits in a buffer instead of reaching the
    # Run log through the entire first-run bootstrap.
    # [BDAI-1588] Also pin the encoding to UTF-8 (errors="replace"), not just
    # line buffering. On Windows sys.stdout defaults to cp1252, which cannot
    # encode the UTF-8 glyphs Next.js prints (e.g. the "▲" logo). tee() writes
    # each child line to THIS process's stdout (:335) and the [A4] drain-error
    # handler reprs the exception (:338) -- both carry that glyph, so a cp1252
    # stdout raises UnicodeEncodeError and kills the drain thread the [A4]
    # guarantee says must never die. The child pipe is already read as UTF-8
    # (spawn(), :317) and Ttest's runner decodes this stream as UTF-8 with
    # errors="replace", so UTF-8 out is the consistent choice.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # noqa: BLE001 -- best-effort only
        pass

    if IS_WINDOWS:
        _bind_windows_job_object()

    # [A12] Install the teardown handlers BEFORE the multi-minute bootstrap
    # (`python -m venv`, `pip install -e .`, `npm install`). A Stop during that
    # window otherwise kills the launcher under the default signal disposition
    # with no cleanup. During bootstrap `_children` is empty, so `shutdown()`
    # is a safe no-op that then exits cleanly.
    signal.signal(signal.SIGINT, lambda *_: (shutdown(), sys.exit(0)))
    signal.signal(signal.SIGTERM, lambda *_: (shutdown(), sys.exit(0)))

    os.chdir(ROOT)
    services = read_services()

    bootstrap_env_files()
    try:
        backend_py = (
            backend_python() if any(s.get("name") == "backend" for s in services) else ""
        )
    except SystemExit as exc:
        # A Stop during bootstrap unwinds the early SIGINT/SIGTERM handler's
        # `sys.exit(0)` through here; that is a clean stop, not a venv failure,
        # so preserve its 0 rather than converting it to 1.
        if exc.code == 0:
            raise
        code = exc.code if isinstance(exc.code, int) else 1
        return code or 1
    if any(s.get("name") == "frontend" for s in services):
        bootstrap_frontend()

    # [A5] declared above the `try` so the `finally` can join the tee threads.
    threads: list[threading.Thread] = []
    started: list[tuple[str, subprocess.Popen]] = []
    try:
        for service in services:
            proc = spawn(service, backend_py)
            if proc is None:
                continue
            _children.append(proc)
            name = str(service.get("name") or "service")
            started.append((name, proc))
            # [item 10] teardown proofs need each child's PID without psutil.
            print(f"[dev.py] started {name} pid={proc.pid}")
            thread = threading.Thread(target=tee, args=(name, proc), daemon=True)
            thread.start()
            threads.append(thread)

        if not _children:
            print("[dev.py] no service started")
            return 1

        print("[dev.py] all services started; press Ctrl+C to stop.")
        # [A3] break as soon as ANY child dies, so one crashed server does not
        # leave its siblings (and this launcher) running silently until every
        # child happens to exit.
        while all(proc.poll() is None for _, proc in started):
            for _, proc in started:
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    continue
        for name, proc in started:
            code = proc.poll()
            if code is not None:
                print(f"[dev.py] {name} exited with {code}")
    finally:
        # [M11] this `finally` must cover the spawn loop too, not just the
        # monitor loop above it -- a later service's malformed `cwd` (before
        # A6, spawn()'s `.resolve()` was outside its own try/except) must not
        # leak an earlier service's already-started child process.
        shutdown()
        # [A5] tee threads are daemons; join within ONE small shared budget so
        # final crash/shutdown output is flushed without pushing total teardown
        # past runner.stop_run's 5s (children are already reaped by shutdown()).
        join_deadline = time.monotonic() + 1.0
        for t in threads:
            t.join(timeout=max(0.0, join_deadline - time.monotonic()))

    # [item 11] report bootstrap/service failures instead of discarding them.
    if any(proc.poll() not in (0, None) for _, proc in started):
        print("[dev.py] one or more services exited with a non-zero status")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
