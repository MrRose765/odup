from __future__ import annotations

# Fallback Python version for versions where release.py lacks MIN_PY_VERSION.
# Keys are normalized version strings (e.g. "14.0", "saas-14.2").
PYTHON_VERSIONS: dict[str, str] = {
    "11.0": "3.6",
    "12.0": "3.6",
    "13.0": "3.8",
    "14.0": "3.8",
    "15.0": "3.8",
    "16.0": "3.9",
    "17.0": "3.10",
    "18.0": "3.10",
}

# Ordered list of (version_selector, install_commands) to run BEFORE requirements.txt.
# Each install_command is the full arg list for `uv pip install`.
# Selectors: "*" | single comparison ">14" | compound ">14,<=18"
# Comparison is done on the major version number (e.g. 18 for "saas-18.3").
PRE_INSTALLS: list[tuple[str, list[list[str]]]] = []

# Same structure as PRE_INSTALLS, but runs AFTER requirements.txt.
POST_INSTALLS: list[tuple[str, list[list[str]]]] = [
    ("*", [["debugpy", "jwt"]]),
    (">=18", [["paramiko"]]),  # Needed for be_payroll
]


# Folders that contains odoo repositories -> Pull + worktree + addons_path
SOURCE_REPOSITORIES = ("odoo", "enterprise", "industry")
# Ugrade repos -> Pull + upgrade path
UPGRADE_REPOSITORIES = ("upgrade-util", "upgrade", "upgrade-specific")
