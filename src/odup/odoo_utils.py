from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


class OdooEnvironmentError(Exception):
    """Raised when Odoo environment cannot be found or is invalid."""
    pass


def find_odoo_environment(version: str) -> tuple[Path, Path, list[str]]:
    """Find the correct venv, odoo-bin, and addon paths for the given version."""
    home = Path.home()
    odoo_base = home / "src" / "odoo" / version
    
    if not odoo_base.exists():
        raise OdooEnvironmentError(f"Odoo version {version} not found at {odoo_base}")
    
    venv_path = odoo_base / ".venv"
    if not venv_path.exists() or not (venv_path / "bin" / "python").exists():
        raise OdooEnvironmentError(f"Virtual environment not found at {venv_path}")
    
    odoo_bin = odoo_base / "odoo-bin"
    if not odoo_bin.exists():
        raise OdooEnvironmentError(f"odoo-bin not found at {odoo_bin}")
    
    addon_paths = []
    
    odoo_addons = odoo_base / "addons"
    if odoo_addons.exists():
        addon_paths.append(str(odoo_addons))
    
    # Enterprise addons are optional but commonly used
    enterprise_base = home / "src" / "enterprise" / version
    if enterprise_base.exists():
        addon_paths.append(str(enterprise_base))
    
    if not addon_paths:
        raise OdooEnvironmentError(f"No addon paths found for version {version}")
    
    return venv_path, odoo_bin, addon_paths


def run_odoo_command(venv_path: Path, odoo_bin: Path, args: list[str], addon_paths: Optional[list[str]] = None) -> int:
    """Run an odoo-bin command with the appropriate Python environment and addon paths."""
    python_exe = venv_path / "bin" / "python"
    cmd = [str(python_exe), str(odoo_bin)]
    
    if addon_paths:
        cmd.extend(["--addons-path", ",".join(addon_paths)])
    
    cmd.extend(args)
    
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except Exception as e:
        raise OdooEnvironmentError(f"Failed to run odoo-bin: {e}") from e
