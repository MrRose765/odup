from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional

import psycopg2
from psycopg2 import sql

from .error import DatabaseOperationError
from .error import OdooCommandError
from .error import OdooEnvironmentError
from .error import VersionDetectionError


def _read_master_floor_from_release() -> tuple[int, int]:
    release_py = Path.home() / "src" / "odoo" / "master" / "odoo" / "release.py"

    try:
        content = release_py.read_text(encoding="utf-8")
    except OSError:
        raise VersionDetectionError(
            f"Could not read release.py to determine master floor version. Expected at {release_py}"
        )

    match = re.search(r"version_info\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*,", content)
    if not match:
        raise VersionDetectionError(
            f"Could not find version_info in release.py. Expected at {release_py}"
        )

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
    curr = None
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user="odoo",
        )
        conn.autocommit = True
        curr = conn.cursor()

        curr.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname))
        )
    except psycopg2.Error as exc:
        raise DatabaseOperationError(
            f"Could not drop database '{dbname}': {exc}"
        ) from exc
    finally:
        if curr:
            curr.close()
        if conn:
            conn.close()


def clone_database_from_template(dbname: str, template_db: str) -> None:
    """Create a database from a template database."""
    conn = None
    curr = None
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user="odoo",
        )
        conn.autocommit = True
        curr = conn.cursor()
        curr.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(dbname),
                sql.Identifier(template_db),
            )
        )
    except psycopg2.Error as exc:
        raise DatabaseOperationError(
            f"Could not clone database '{template_db}' to '{dbname}': {exc}"
        ) from exc
    finally:
        if curr:
            curr.close()
        if conn:
            conn.close()


def infer_version(db_name: str) -> str:
    """
    Infer the Odoo version of an existing database by connecting to it and querying the base module version.
    """
    conn = None
    curr = None
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user="odoo",
        )
        curr = conn.cursor()
        version = _query_version(curr)
    except psycopg2.Error as exc:
        raise DatabaseOperationError(
            f"Could not query database '{db_name}' for Odoo version: {exc}"
        ) from exc
    finally:
        if curr:
            curr.close()
        if conn:
            conn.close()

    if not version:
        raise VersionDetectionError(
            f"Database '{db_name}' did not return a base module version."
        )

    return parse_version(version)


def parse_version(version_str: str) -> str:
    """
    Normalizes Odoo version strings
    To find the master floor version, it reads the version_info from the master release.py file.

    :param version_str: The version string (from DB or input)
    """
    if not version_str:
        raise VersionDetectionError("Received an empty Odoo version string.")

    master_major, master_minor = _read_master_floor_from_release()
    v = version_str.strip().lower().replace("~", ".").replace("-", ".")

    if "master" in v:
        return "master"

    match_digits = re.findall(r"(\d+)", v)
    if not match_digits:
        raise VersionDetectionError(
            f"Could not parse version from string: {version_str}"
        )

    major = int(match_digits[0])
    minor = int(match_digits[1]) if len(match_digits) > 1 else 0

    if major == master_major and minor >= master_minor:
        return "master"
    if minor > 0:
        return f"saas-{major}.{minor}"
    return f"{major}.0"


def _get_addons(name: str, version: str) -> Optional[str]:
    addons_path = Path.home() / "src" / name
    if not addons_path.exists():
        # TODO: log a warning that the addons does not exist
        return None
    addons_path = addons_path / version
    if addons_path.exists():
        return str(addons_path)
    # TODO: Call git management to add worktree if the version is missing.
    return None


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

    enterprise_addons = _get_addons("enterprise", version)
    if enterprise_addons:
        addon_paths.append(enterprise_addons)

    industry_addons = _get_addons("industry", version)
    if industry_addons:
        addon_paths.append(industry_addons)

    addons_path = ",".join(addon_paths) if addon_paths else None
    return venv_path, odoo_bin, addons_path


def _ensure_odup_metadata_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS odup_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def set_prepare_tests_marker(dbname: str, version: str) -> None:
    conn = None
    curr = None
    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user="odoo",
        )
        conn.autocommit = True
        curr = conn.cursor()
        _ensure_odup_metadata_table(curr)
        curr.execute(
            """
            INSERT INTO odup_metadata (key, value, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (key)
            DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """,
            ("upgrade.test_prepare", version),
        )
    except psycopg2.Error as exc:
        raise DatabaseOperationError(
            f"Could not set prepare-tests marker on database '{dbname}': {exc}"
        ) from exc
    finally:
        if curr:
            curr.close()
        if conn:
            conn.close()


def has_prepare_tests_marker(dbname: str) -> bool:
    conn = None
    curr = None
    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user="odoo",
        )
        curr = conn.cursor()
        _ensure_odup_metadata_table(curr)
        curr.execute(
            "SELECT 1 FROM odup_metadata WHERE key = %s", ("upgrade.test_prepare",)
        )
        return curr.fetchone() is not None
    except psycopg2.Error as exc:
        raise DatabaseOperationError(
            f"Could not read prepare-tests marker from database '{dbname}': {exc}"
        ) from exc
    finally:
        if curr:
            curr.close()
        if conn:
            conn.close()


def run_odoo_command(
    venv_path: Path, odoo_bin: Path, args: list[str], addons_path: Optional[str] = None
) -> int:
    """Run an odoo-bin command with the appropriate Python environment and addon paths."""
    python_exe = venv_path / "bin" / "python"
    cmd = [str(python_exe), str(odoo_bin)]

    if addons_path:
        cmd.extend(["--addons-path", addons_path])

    cmd.extend(args)

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except OSError as exc:
        raise OdooCommandError(f"Failed to run odoo-bin: {exc}") from exc
