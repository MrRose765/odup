from __future__ import annotations

import logging
import shlex
import subprocess
from pathlib import Path
from typing import Optional

from .database import clone_database_from_template
from .database import drop_if_exists
from .environment import _get_addons
from .environment import find_odoo_environment
from .error import DatabaseOperationError
from .error import OdooCommandError
from .error import OdooEnvironmentError
from .error import VersionDetectionError
from .versioning import infer_version
from .versioning import _read_master_floor_from_release
from .versioning import parse_version

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


__all__ = [
    "_get_addons",
    "_read_master_floor_from_release",
    "clone_database_from_template",
    "DatabaseOperationError",
    "drop_if_exists",
    "find_odoo_environment",
    "infer_version",
    "OdooCommandError",
    "OdooEnvironmentError",
    "parse_version",
    "run_odoo_command",
    "VersionDetectionError",
]
