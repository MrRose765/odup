from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional
import psycopg2
from psycopg2 import sql


class OdooEnvironmentError(Exception):
    """Raised when Odoo environment cannot be found or is invalid."""
    pass


def drop_if_exists(dbname: str) -> None:
    """Drop the specified database if it exists."""
    conn = None
    try:
        conn = psycopg2.connect(
            dbname='postgres',
            user='odoo',
        )
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname)))
        print(f"Successfully dropped database: {dbname}")

    except Exception as e:
        print(f"Error: Could not drop database {dbname}. {e}")
    
    finally:
        if conn:
            cur.close()
            conn.close()


def infer_odoo_version(db_name: str) -> str:
    """Infer the Odoo version from a database by inspecting the base module."""

    query = "SELECT latest_version FROM ir_module_module WHERE name='base';"

    try:
        with psycopg2.connect(dbname=db_name) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                row = cursor.fetchone()
    except psycopg2.Error as exc:
        message = f"Failed to query database '{db_name}' for version."
        detail = str(exc).strip()
        if detail:
            message = f"{message} {detail}"
        raise OdooEnvironmentError(message) from exc

    if not row or not row[0]:
        raise OdooEnvironmentError(f"Database '{db_name}' did not return a base module version.")

    raw_version = str(row[0]).strip()
    try:
        return parse_odoo_version(raw_version)
    except OdooEnvironmentError as exc:
        raise OdooEnvironmentError(f"Failed to parse Odoo version from database '{db_name}': {exc}") from exc


def parse_odoo_version(version: str) -> str:
    """
    Parse and normalize an Odoo version string.

    Converts inputs like:
    - "14.0" -> "14.0"
    - "14" -> "14.0"
    - "19.1" -> "saas-19.1"
    - "saas~19.1.1.3" -> "saas-19.1"
    - "19.3.1.3" -> "master"
    """
    version = version.strip().lower()
    if version in {"master", "saas-master", "19.3.1.3"}:
        return "master"

    saas_match = re.search(r"saas[~-]?(\d+)(?:\.(\d+))?", version)
    if saas_match:
        major, minor = saas_match.groups()
        return f"saas-{major}.{minor or '0'}"

    match = re.search(r"(\d+)(?:\.(\d+))?", version)
    if match:
        major, minor = match.groups()
        return f"{major}.{minor or '0'}"

    raise OdooEnvironmentError(f"Invalid Odoo version format: '{version}'.")


def find_odoo_environment(version: str) -> tuple[Path, Path, Optional[str]]:
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

    addons_path = ",".join(addon_paths) if addon_paths else None
    return venv_path, odoo_bin, addons_path


def run_odoo_command(venv_path: Path, odoo_bin: Path, args: list[str], addons_path: Optional[str] = None) -> int:
    """Run an odoo-bin command with the appropriate Python environment and addon paths."""
    python_exe = venv_path / "bin" / "python"
    cmd = [str(python_exe), str(odoo_bin)]
    
    if addons_path:
        cmd.extend(["--addons-path", addons_path])
    
    cmd.extend(args)
    
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except Exception as e:
        raise OdooEnvironmentError(f"Failed to run odoo-bin: {e}") from e
