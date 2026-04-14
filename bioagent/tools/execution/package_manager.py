"""Auto-install missing Python packages."""

from __future__ import annotations

import importlib.util
import logging
import subprocess

logger = logging.getLogger(__name__)


def install_package(package_name: str) -> str:
    """Install a pip package if not already available.

    Returns
    -------
    str
        Status message for the LLM.
    """
    # Normalize: take the import name (before any extras/versions)
    base_name = package_name.split("[")[0].split(">")[0].split("=")[0].strip()

    if importlib.util.find_spec(base_name.replace("-", "_")) is not None:
        return f"Package '{base_name}' is already installed."

    logger.info("Installing package: %s", package_name)
    try:
        result = subprocess.run(
            ["pip", "install", package_name],
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            return f"Successfully installed '{package_name}'."
        return f"Failed to install '{package_name}': {result.stderr[:500]}"
    except Exception as exc:
        return f"Error installing '{package_name}': {exc}"
