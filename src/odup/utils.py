from __future__ import annotations

import logging
import shlex
import subprocess
from pathlib import Path
from typing import Optional

from .error import OdooCommandError, OdupError

logger = logging.getLogger(__name__)


def run_odoo_command(
    venv_path: Path,
    odoo_bin: Path,
    args: list[str],
    addons_path: Optional[str] = None,
    debug: bool = False,
) -> int:
    python_exe = venv_path / "bin" / "python"
    cmd = [str(python_exe)]
    if debug:
        logger.info(
            "Running odoo-bin in debug mode, waiting for debugger to attach on localhost:5678..."
        )
        cmd.extend(["-m", "debugpy", "--listen", "localhost:5678", "--wait-for-client"])
    cmd.append(str(odoo_bin))

    if addons_path:
        cmd.extend(["--addons-path=" + addons_path])

    cmd.extend(args)
    logger.info("Running odoo-bin")
    logger.debug("Command: %s", shlex.join(cmd))

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except OSError as exc:
        raise OdooCommandError(f"Failed to run odoo-bin: {exc}") from exc


def src_root() -> Path:
    return Path.home() / "src"


def run_uv(args: list[str], cwd: Path) -> None:
    result = subprocess.run(["uv", *args], cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise OdupError(f"Command failed: uv {' '.join(args)}\n{result.stderr.strip()}")
