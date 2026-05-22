from __future__ import annotations

import re
from pathlib import Path


from .database import query_version
from .error import VersionDetectionError


def _read_release_py(version: str, pattern: str) -> re.Match:
    release_py = Path.home() / "src" / "odoo" / version / "odoo" / "release.py"
    try:
        content = release_py.read_text(encoding="utf-8")
    except OSError:
        raise VersionDetectionError(f"Could not read release.py at {release_py}")
    match = re.search(pattern, content)
    if not match:
        raise VersionDetectionError(f"Pattern {pattern!r} not found in {release_py}")
    return match


def read_min_python_version(version: str) -> str:
    match = _read_release_py(
        version, r"MIN_PY_VERSION\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)"
    )
    return f"{match.group(1)}.{match.group(2)}"


def _read_master_floor_from_release() -> tuple[int, int]:
    match = _read_release_py("master", r"version_info\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*,")
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


def _major_number(version: str) -> int:
    if version == "master":
        major, _ = _read_master_floor_from_release()
        return major
    match = re.search(r"\d+", version)
    if match:
        return int(match.group())
    raise VersionDetectionError(f"Cannot extract major version from: {version}")


def build_upgrade_chain(source_version: str, target_version: str) -> list[str]:
    """Return ordered versions to upgrade through, from source (exclusive) to target (inclusive).

    Only major (.0) versions are used as intermediate steps. If the target is a saas
    version, the corresponding major .0 is included before it. Both X.0 and master are
    treated as distinct checkouts, so the chain for X.0 → master includes X.0 then master.
    Returns an empty list when source and target are identical.
    """
    if source_version == target_version:
        return []

    src_major = _major_number(source_version)
    tgt_major = _major_number(target_version)

    if src_major == tgt_major:
        return [target_version]

    major_steps = [f"{v}.0" for v in range(src_major + 1, tgt_major + 1)]

    if target_version == "master":
        return major_steps + ["master"]

    major_target = f"{tgt_major}.0"
    if target_version == major_target:
        return major_steps

    # saas target: step through the major .0 first, then the saas version
    return major_steps + [target_version]


def infer_version(db_name: str) -> str:
    version = query_version(db_name)

    if not version:
        raise VersionDetectionError(
            f"Database '{db_name}' did not return a base module version."
        )

    return parse_version(version)
