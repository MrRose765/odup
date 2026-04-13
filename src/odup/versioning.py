from __future__ import annotations

import re
from pathlib import Path

import psycopg2

from .error import DatabaseOperationError
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
    query = "SELECT latest_version FROM ir_module_module WHERE name='base';"
    cursor.execute(query)
    res = cursor.fetchone()
    return res[0] if res else None


def parse_version(version_str: str) -> str:
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


def infer_version(db_name: str) -> str:
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
