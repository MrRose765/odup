from __future__ import annotations

from pathlib import Path
from typing import Optional

from .error import OdooEnvironmentError


def _get_addons(name: str, version: str) -> Optional[str]:
    addons_path = Path.home() / "src" / name
    if not addons_path.exists():
        return None
    addons_path = addons_path / version
    if addons_path.exists():
        return str(addons_path)
    return None


def find_odoo_environment(
    version: str, add_industry: bool = True
) -> tuple[Path, Path, Optional[str]]:
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

    enterprise_addons = _get_addons("enterprise", version)
    if enterprise_addons:
        addon_paths.append(enterprise_addons)

    if add_industry:
        industry_addons = _get_addons("industry", version)
        if industry_addons:
            addon_paths.append(industry_addons)

    addons_path = ",".join(addon_paths) if addon_paths else None
    return venv_path, odoo_bin, addons_path
