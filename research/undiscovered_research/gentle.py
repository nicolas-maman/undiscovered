"""Keep a long run from getting in the way of whoever owns the computer.

``be_gentle()`` lowers the process priority, so anything the person is doing
comes first, and caps the threads that numeric libraries use, so a run
never takes every core. Call it at the start of a command. Libraries loaded
later read the environment variables; those already loaded (numpy's BLAS)
are capped at run time through threadpoolctl, which scikit-learn installs.
"""

from __future__ import annotations

import os
import sys

# Half the cores, at least one: enough to finish, never the whole machine.
THREADS = max(1, (os.cpu_count() or 2) // 2)


def be_gentle() -> None:
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS", "TOKENIZERS_PARALLELISM"):
        os.environ.setdefault(var, "false" if var == "TOKENIZERS_PARALLELISM" else str(THREADS))
    try:
        from threadpoolctl import threadpool_limits
        threadpool_limits(THREADS)
    except ImportError:
        pass
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            k32 = ctypes.windll.kernel32
            k32.GetCurrentProcess.restype = wintypes.HANDLE      # 64-bit handle, not int
            k32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            k32.SetPriorityClass(k32.GetCurrentProcess(), 0x00004000)   # BELOW_NORMAL
        else:
            os.nice(10)
    except (OSError, AttributeError):
        pass    # not allowed here: run at normal priority rather than fail
