"""Launch and stop a scan together with any native child processes.

The main Tk thread never reads subprocess output; readers live in a worker.
On POSIX we isolate the CLI and its native scanner in a dedicated session so
SIGTERM reaches both. Windows uses taskkill /T for the process tree.
"""
from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path


def launch_scanner(argv, *, cwd: str | Path, **kwargs) -> subprocess.Popen:
    flags = int(kwargs.pop('creationflags', 0))
    if os.name == 'nt':
        flags |= getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    else:
        kwargs['start_new_session'] = True
    return subprocess.Popen(argv, cwd=cwd, creationflags=flags, **kwargs)


def stop_scanner(process: subprocess.Popen) -> None:
    """Best-effort termination; safe if the CLI or native worker has exited."""
    if process.poll() is not None:
        return
    if os.name == 'nt':
        try:
            subprocess.run(
                ['taskkill', '/PID', str(process.pid), '/T', '/F'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=10, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            if process.poll() is None:
                try:
                    process.terminate()
                except (ProcessLookupError, OSError):
                    pass
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            try:
                process.terminate()
            except (ProcessLookupError, OSError):
                pass
