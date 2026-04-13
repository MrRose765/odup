from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .database import clone_database_from_template
from .database import drop_if_exists
from .database import has_prepare_tests_marker
from .database import set_prepare_tests_marker
from .environment import find_odoo_environment
from .error import OdupError
from .odoo_utils import run_odoo_command
from .versioning import infer_version
from .versioning import parse_version

PREPARE_TESTS_TAG = "upgrade.test_prepare"
CHECK_TESTS_TAG = "upgrade.test_check"


@dataclass
class WorkflowOutcome:
    messages: list[str]
    exit_code: int = 0
    error_message: Optional[str] = None


def _upgrade_path_value() -> str:
    home = Path.home()
    return f"{(home / 'src' / 'upgrade-util' / 'src')},{(home / 'src' / 'upgrade' / 'migrations')}"


def _build_environment_messages(
    odoo_bin: Path, venv_path: Path, addons_path: Optional[str]
) -> list[str]:
    messages = [
        f"[odup] Using odoo-bin: {odoo_bin}",
        f"[odup] Using virtual environment: {venv_path}",
    ]
    if addons_path:
        messages.append(f"[odup] Using addons path: {addons_path}")
    return messages


def createdb_workflow(
    db_name: str, version: Optional[str], init: Optional[str], tests: bool, debug: bool
) -> WorkflowOutcome:
    result_messages = []
    db_name = f"odup_{db_name}"
    result_messages.append(
        f"[odup] Creating Odoo database '{db_name}' for version {version}"
    )

    drop_if_exists(db_name)
    normalized_version = parse_version(version or "master")
    venv_path, odoo_bin, addons_path = find_odoo_environment(normalized_version)
    result_messages.extend(
        _build_environment_messages(odoo_bin, venv_path, addons_path)
    )

    args = ["-d", db_name]
    if init:
        args.extend(["-i", init])
        result_messages.append(f"[odup] Installing modules: {init}")
    if tests:
        args.extend(
            [
                "--upgrade-path",
                _upgrade_path_value(),
                "--test-enable",
                "--test-tags",
                PREPARE_TESTS_TAG,
            ]
        )
        result_messages.append(
            f"[odup] Running upgrade prepare tests: {PREPARE_TESTS_TAG}"
        )
    args.extend(["--stop-after-init"])

    exit_code = run_odoo_command(venv_path, odoo_bin, args, addons_path, debug=debug)
    if exit_code != 0:
        return WorkflowOutcome(
            messages=result_messages,
            exit_code=exit_code,
            error_message=f"[odup] Failed to create Odoo database '{db_name}' (exit code: {exit_code})",
        )

    if tests:
        set_prepare_tests_marker(db_name, normalized_version)
        result_messages.append(
            "[odup] Stored prepare-tests marker in DB metadata table (odup_metadata)."
        )

    result_messages.append(f"[odup] Successfully created Odoo database '{db_name}'")
    return WorkflowOutcome(messages=result_messages)


def upgrade_workflow(
    db_name: str, target_version: str, tests: bool, debug: bool
) -> WorkflowOutcome:
    result_messages = []
    normalized_target_version = parse_version(target_version)
    upgraded_db_name = f"{db_name}_{normalized_target_version}"
    venv_path, odoo_bin, addons_path = find_odoo_environment(normalized_target_version)

    result_messages.extend(
        [
            f"[odup] Source database: {db_name}",
            f"[odup] Upgraded database: {upgraded_db_name}",
            f"[odup] Target Odoo version: {normalized_target_version}",
        ]
    )
    result_messages.extend(
        _build_environment_messages(odoo_bin, venv_path, addons_path)
    )

    if tests and not has_prepare_tests_marker(db_name):
        raise OdupError(
            f"Source database '{db_name}' was not marked as prepared. Run 'odup createdb ... --tests' first."
        )

    drop_if_exists(upgraded_db_name)
    clone_database_from_template(upgraded_db_name, db_name)

    args = [
        "-d",
        upgraded_db_name,
        "--upgrade-path",
        _upgrade_path_value(),
        "-u",
        "all",
        "--stop-after-init",
    ]
    exit_code = run_odoo_command(venv_path, odoo_bin, args, addons_path, debug=debug)
    if exit_code != 0:
        return WorkflowOutcome(
            messages=result_messages,
            exit_code=exit_code,
            error_message=f"[odup] Failed to upgrade database '{upgraded_db_name}' (exit code: {exit_code})",
        )

    if tests:
        check_args = [
            "-d",
            upgraded_db_name,
            "--upgrade-path",
            _upgrade_path_value(),
            "--test-enable",
            "--test-tags",
            CHECK_TESTS_TAG,
            "--stop",
        ]
        result_messages.append(f"[odup] Running upgrade check tests: {CHECK_TESTS_TAG}")
        check_exit_code = run_odoo_command(
            venv_path, odoo_bin, check_args, addons_path, debug=debug
        )
        if check_exit_code != 0:
            return WorkflowOutcome(
                messages=result_messages,
                exit_code=check_exit_code,
                error_message=f"[odup] Upgrade check failed for database '{upgraded_db_name}' (exit code: {check_exit_code})",
            )

    result_messages.append(
        f"[odup] Successfully upgraded database '{upgraded_db_name}'"
    )
    return WorkflowOutcome(messages=result_messages)


def start_workflow(db_name: str, shell: bool, debug: bool) -> WorkflowOutcome:
    result_messages = [f"[odup] Starting Odoo database '{db_name}'"]

    version = infer_version(db_name)
    venv_path, odoo_bin, addons_path = find_odoo_environment(version)

    result_messages.append(f"[odup] Inferred Odoo version: {version}")
    result_messages.extend(
        _build_environment_messages(odoo_bin, venv_path, addons_path)
    )

    args = ["shell", "-d", db_name] if shell else ["-d", db_name]
    exit_code = run_odoo_command(venv_path, odoo_bin, args, addons_path, debug=debug)
    return WorkflowOutcome(messages=result_messages, exit_code=exit_code)
