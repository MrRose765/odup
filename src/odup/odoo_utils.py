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


def _read_master_floor_from_release() -> tuple[int, int]:
    release_py = Path.home() / "src" / "odoo" / "master" / "odoo" / "release.py"

    try:
        content = release_py.read_text(encoding="utf-8")
    except OSError:
        raise OdooEnvironmentError(f"Could not read release.py to determine master floor version. Expected at {release_py}")

    match = re.search(r"version_info\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*,", content)
    if not match:
        raise OdooEnvironmentError(f"Could not find version_info in release.py. Expected at {release_py}")

    return int(match.group(1)), int(match.group(2))


def _query_version(cursor):
    """Query Odoo version from the database using the provided cursor."""
    query = "SELECT latest_version FROM ir_module_module WHERE name='base';"
    cursor.execute(query)
    res = cursor.fetchone()
    return res[0] if res else None


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


def infer_version(db_name: str) -> Optional[str]:
    """
    Infer the Odoo version of an existing database by connecting to it and querying the base module version.
    """
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user='odoo',
        )
        cur = conn.cursor()
        version = _query_version(cur)
        return parse_version(version) if version else None
    finally:
        if conn:
            cur.close()
            conn.close()


def parse_version(version_str: str) -> str:
    """
    Normalizes Odoo version strings.
    To find the master floor version, it reads the version_info from the master release.py file.
    
    :param version_str: The version string (from DB or input)
    """
    if not version_str:
        return "master"

    master_major, master_minor = _read_master_floor_from_release()
    v = version_str.strip().lower().replace('~', '.').replace('-', '.')
    
    if "master" in v:
        return "master"

    match_digits = re.findall(r'(\d+)', v)
    if not match_digits:
        raise ValueError(f"Could not parse version from string: {version_str}")

    major = int(match_digits[0])
    minor = int(match_digits[1]) if len(match_digits) > 1 else 0

    if major == master_major and minor >= master_minor:
        return "master"
    if minor > 0:
        return f"saas-{major}.{minor}"
    return f"{major}.0"


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
