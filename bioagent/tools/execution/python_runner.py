"""Subprocess-based Python code execution with timeout and output capture."""

from __future__ import annotations

import logging
import subprocess
import tempfile
import uuid
from pathlib import Path

from bioagent.config.settings import settings

logger = logging.getLogger(__name__)

MAX_OUTPUT_BYTES = 10 * 1024  # 10 KB per stream


def execute_python(
    code: str,
    timeout: int | None = None,
) -> dict:
    """Execute Python *code* in a subprocess and return captured output.

    Parameters
    ----------
    code : str
        Python source code to execute.
    timeout : int, optional
        Seconds before killing the subprocess. Defaults to ``settings.code_timeout``.

    Returns
    -------
    dict
        ``{stdout, stderr, exit_code, duration, file_path}``
    """
    if timeout is None:
        timeout = settings.code_timeout

    workspace = settings.workspace_path / "scripts"
    workspace.mkdir(parents=True, exist_ok=True)

    script_path = workspace / f"{uuid.uuid4().hex[:12]}.py"

    # Prepend reproducibility seed so all executions are deterministic
    seed = settings.random_seed
    seed_header = (
        f"import random as _random; _random.seed({seed})\n"
        f"try:\n"
        f"    import numpy as _np; _np.random.seed({seed})\n"
        f"except ImportError:\n"
        f"    pass\n"
        f"try:\n"
        f"    import torch as _torch; _torch.manual_seed({seed})\n"
        f"except ImportError:\n"
        f"    pass\n"
        f"# --- user code below ---\n"
    )
    script_path.write_text(seed_header + code, encoding="utf-8")

    logger.info("Executing script: %s (timeout=%ds)", script_path, timeout)

    try:
        import time

        start = time.monotonic()
        proc = subprocess.run(
            ["python", str(script_path)],
            capture_output=True,
            timeout=timeout,
            cwd=str(settings.workspace_path),
            encoding="utf-8",
            errors="replace",
            text=True,
        )
        duration = time.monotonic() - start
    except subprocess.TimeoutExpired:
        logger.warning("Script timed out after %ds: %s", timeout, script_path)
        return {
            "stdout": "",
            "stderr": f"TimeoutExpired: execution exceeded {timeout}s",
            "exit_code": -1,
            "duration": timeout,
            "file_path": str(script_path),
        }
    except Exception as exc:
        logger.exception("Script execution failed: %s", script_path)
        return {
            "stdout": "",
            "stderr": str(exc),
            "exit_code": -1,
            "duration": 0,
            "file_path": str(script_path),
        }

    stdout = proc.stdout[-MAX_OUTPUT_BYTES:] if len(proc.stdout) > MAX_OUTPUT_BYTES else proc.stdout
    stderr = proc.stderr[-MAX_OUTPUT_BYTES:] if len(proc.stderr) > MAX_OUTPUT_BYTES else proc.stderr

    if proc.returncode != 0:
        logger.warning("Script exited with code %d: %s", proc.returncode, script_path)

    return {
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": proc.returncode,
        "duration": round(duration, 2),
        "file_path": str(script_path),
    }
