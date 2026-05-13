from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .database import clone_database_from_template
from .database import drop_if_exists
from .env_manager import pull_existing_sources
from .environment import find_odoo_environment
from .odoo_utils import run_odoo_command
from .versioning import infer_version
from .versioning import parse_version

PREPARE_TESTS_TAG = "upgrade.test_prepare"
CHECK_TESTS_TAG = "upgrade.test_check"
logger = logging.getLogger(__name__)


@dataclass
class WorkflowOutcome:
    exit_code: int = 0
    error_message: Optional[str] = None


def _upgrade_path_value() -> str:
    home = Path.home()
    return f"{(home / 'src' / 'upgrade-util' / 'src')},{(home / 'src' / 'upgrade' / 'migrations')}"


def _log_environment_context(
    odoo_bin: Path, venv_path: Path, addons_path: Optional[str]
) -> None:
    logger.debug("Using odoo-bin: %s", odoo_bin)
    logger.debug("Using virtual environment: %s", venv_path)
    if addons_path:
        logger.debug("Using addons path: %s", addons_path)


def createdb_workflow(
    db_name: str,
    version: Optional[str],
    init: Optional[str],
    debug: bool,
    extra_args: Optional[list[str]] = None,
) -> WorkflowOutcome:
    db_name = f"odup_{db_name}"
    logger.info("Creating Odoo database '%s' for version %s", db_name, version)

    drop_if_exists(db_name)
    normalized_version = parse_version(version or "master")
    logger.debug("Normalized Odoo version: %s", normalized_version)
    venv_path, odoo_bin, addons_path = find_odoo_environment(normalized_version)
    _log_environment_context(odoo_bin, venv_path, addons_path)

    args = ["-d", db_name]
    if init:
        args.extend(["-i", init])
        logger.info("Installing modules: %s", init)
    args.extend(["--stop-after-init"])
    if extra_args:
        args.extend(extra_args)

    exit_code = run_odoo_command(venv_path, odoo_bin, args, addons_path, debug=debug)
    if exit_code != 0:
        return WorkflowOutcome(
            exit_code=exit_code,
            error_message=f"Failed to create Odoo database '{db_name}' (exit code: {exit_code})",
        )

    logger.info("Successfully created Odoo database '%s'", db_name)
    return WorkflowOutcome()


def _run_prepare_tests(db_name: str, debug: bool) -> int:
    source_version = infer_version(db_name)
    venv_path, odoo_bin, addons_path = find_odoo_environment(source_version)
    args = [
        "-d",
        db_name,
        "--upgrade-path",
        _upgrade_path_value(),
        "--test-enable",
        "--test-tags",
        PREPARE_TESTS_TAG,
        "--stop-after-init",
    ]
    logger.info("Running upgrade prepare tests: %s", PREPARE_TESTS_TAG)
    return run_odoo_command(venv_path, odoo_bin, args, addons_path, debug=debug)


def upgrade_workflow(
    db_name: str,
    target_version: str,
    tests: bool,
    debug: bool,
    extra_args: Optional[list[str]] = None,
) -> WorkflowOutcome:
    normalized_target_version = parse_version(target_version)
    upgraded_db_name = f"{db_name}_{normalized_target_version}"
    logger.info("Source database: %s", db_name)
    logger.info("Upgraded database: %s", upgraded_db_name)
    logger.info("Target Odoo version: %s", normalized_target_version)
    venv_path, odoo_bin, addons_path = find_odoo_environment(
        normalized_target_version, add_industry=False
    )

    _log_environment_context(odoo_bin, venv_path, addons_path)

    drop_if_exists(upgraded_db_name)
    clone_database_from_template(upgraded_db_name, db_name)

    if tests:
        prepare_exit_code = _run_prepare_tests(upgraded_db_name, debug)
        if prepare_exit_code != 0:
            return WorkflowOutcome(
                exit_code=prepare_exit_code,
                error_message=f"Upgrade prepare tests failed for '{upgraded_db_name}' (exit code: {prepare_exit_code})",
            )

    args = [
        "-d",
        upgraded_db_name,
        "--upgrade-path",
        _upgrade_path_value(),
        "-u",
        "all",
        "--stop-after-init",
    ]
    if extra_args:
        args.extend(extra_args)
    exit_code = run_odoo_command(venv_path, odoo_bin, args, addons_path, debug=debug)
    if exit_code != 0:
        return WorkflowOutcome(
            exit_code=exit_code,
            error_message=f"Failed to upgrade database '{upgraded_db_name}' (exit code: {exit_code})",
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
        if extra_args:
            check_args.extend(extra_args)
        logger.info("Running upgrade check tests: %s", CHECK_TESTS_TAG)
        check_exit_code = run_odoo_command(
            venv_path, odoo_bin, check_args, addons_path, debug=debug
        )
        if check_exit_code != 0:
            return WorkflowOutcome(
                exit_code=check_exit_code,
                error_message=f"Upgrade check failed for database '{upgraded_db_name}' (exit code: {check_exit_code})",
            )

    logger.info("Successfully upgraded database '%s'", upgraded_db_name)
    return WorkflowOutcome()


def start_workflow(
    db_name: str, shell: bool, debug: bool, extra_args: Optional[list[str]] = None
) -> WorkflowOutcome:
    logger.info("Starting Odoo database '%s'", db_name)

    version = infer_version(db_name)
    venv_path, odoo_bin, addons_path = find_odoo_environment(version)

    logger.info("Inferred Odoo version: %s", version)
    _log_environment_context(odoo_bin, venv_path, addons_path)

    args = ["shell", "-d", db_name] if shell else ["-d", db_name]
    if extra_args:
        args.extend(extra_args)
    exit_code = run_odoo_command(venv_path, odoo_bin, args, addons_path, debug=debug)
    return WorkflowOutcome(exit_code=exit_code)


def env_pull_workflow(
    version: Optional[str] = None, verbosity: int = 0, upgrade_only: bool = False
) -> WorkflowOutcome:
    normalized_version = parse_version(version) if version else None
    failures = pull_existing_sources(
        version=normalized_version, verbosity=verbosity, upgrade_only=upgrade_only
    )
    if failures:
        report = "\n".join(f"- {failure}" for failure in failures)
        logger.error("Pull report:\n%s", report)
        return WorkflowOutcome(exit_code=1)
    return WorkflowOutcome()
