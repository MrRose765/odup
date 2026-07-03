from __future__ import annotations

import re


from .database import query_version
from .error import VersionDetectionError
from .utils import SRC_ROOT
from .version_config import PYTHON_VERSIONS

_component_re = re.compile(r"(\d+ | [a-z]+ | \.| -)", re.VERBOSE)
_replace = {
    "pre": "c",
    "preview": "c",
    "-": "final-",
    "_": "final-",
    "rc": "c",
    "dev": "@",
    "saas": "",
    "~": "",
}.get


def _read_release_py(version: str, pattern: str) -> re.Match:
    release_py = SRC_ROOT / "odoo" / version / "odoo" / "release.py"
    try:
        content = release_py.read_text(encoding="utf-8")
    except OSError:
        raise VersionDetectionError(f"Could not read release.py at {release_py}")
    match = re.search(pattern, content)
    if not match:
        raise VersionDetectionError(f"Pattern {pattern!r} not found in {release_py}")
    return match


def read_min_python_version(version: str) -> str:
    try:
        match = _read_release_py(
            version, r"MIN_PY_VERSION\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)"
        )
        return f"{match.group(1)}.{match.group(2)}"
    except VersionDetectionError:
        fallback = PYTHON_VERSIONS.get(version)
        if fallback:
            return fallback
        raise


def _read_master_version_number() -> tuple[int, int]:
    match = _read_release_py("master", r"version_info\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*,")
    return int(match.group(1)), int(match.group(2))


def __parse_version_parts(s: str):
    for part in _component_re.split(s):
        part = _replace(part, part)
        if not part or part == ".":
            continue
        if part[:1] in "0123456789":
            yield part.zfill(8)
        else:
            yield "*" + part
    yield "*final"


def parse_version(s: str) -> tuple[str, ...]:
    """Convert a version string to a chronologically-sortable key.

    Taken from Odoo's own ``parse_version`` (originally from setuptools 0.6c8).
    Returns a tuple of strings that compares correctly with standard operators,
    so e.g. ``compare_version("16.0") < compare_version("17.0")`` is True.

    Handles Odoo-specific tokens: "saas" and "~" are stripped so that
    "saas-16.3" sorts between "16.0" and "17.0" as expected.
    """
    parts: list[str] = []
    for part in __parse_version_parts((s or "0.1").lower()):
        if part.startswith("*"):
            if part < "*final":
                while parts and parts[-1] == "*final-":
                    parts.pop()
            while parts and parts[-1] == "00000000":
                parts.pop()
        parts.append(part)
    return tuple(parts)


def normalize_version(version_str: str) -> str:
    """Normalize a version string to the corresponding local checkout folder name.

    Accepts any loose version string (e.g. from a database, a CLI argument, or
    a branch name) and maps it to one of three canonical forms:
      - ``"master"``           — for the current development branch
      - ``"saas-<X>.<Y>"``    — for saas/minor releases (minor > 0)
      - ``"<X>.0"``           — for stable major releases

    Raises VersionDetectionError if the string cannot be parsed.
    """
    if not version_str:
        raise VersionDetectionError("Received an empty Odoo version string.")

    master_major, master_minor = _read_master_version_number()
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


def get_major_number(version: str) -> int:
    if version == "master":
        major, _ = _read_master_version_number()
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

    src_major = get_major_number(source_version)
    tgt_major = get_major_number(target_version)

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
    """Return the normalized Odoo version string for a given database"""
    version = query_version(db_name)

    if not version:
        raise VersionDetectionError(
            f"Database '{db_name}' did not return a base module version."
        )

    return normalize_version(version)
