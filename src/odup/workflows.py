from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from .database import (
    clone_database_from_template,
    drop_if_exists,
    list_databases,
)
from .environment import (
    add_version_environment,
    find_odoo_environment,
    pull_existing_sources,
)
from .utils import run_odoo_command, SRC_ROOT
from .versioning import (
    build_upgrade_chain,
    infer_version,
    parse_version,
)

PREPARE_TESTS_TAG = "upgrade.test_prepare"
CHECK_TESTS_TAG = "upgrade.test_check"
logger = logging.getLogger(__name__)

# Matches databases created by `upgrade_workflow`: odup_<name>_<version>
_UPGRADED_DB_RE = re.compile(r"^odup_.+_(master|\d+\.\d+|saas-\d+\.\d+)$")
_ALL_ODUP_DB_RE = re.compile(r"^odup_")


@dataclass
class WorkflowOutcome:
    exit_code: int = 0
    error_message: str | None = None


_UPGRADE_PATH = (
    f"{SRC_ROOT / 'upgrade-util' / 'src'},{SRC_ROOT / 'upgrade' / 'migrations'}"
)


def _log_environment_context(
    venv_path: Path, odoo_bin: Path, addons_path: str | None
) -> None:
    logger.debug("Using odoo-bin: %s", odoo_bin)
    logger.debug("Using virtual environment: %s", venv_path)
    if addons_path:
        logger.debug("Using addons path: %s", addons_path)


def createdb_workflow(
    db_name: str,
    version: str | None,
    init: str | None,
    debug: bool,
    extra_args: list[str] | None = None,
) -> WorkflowOutcome:
    db_name = f"odup_{db_name}"
    logger.info("Creating Odoo database '%s' for version %s", db_name, version)

    drop_if_exists(db_name)
    normalized_version = parse_version(version or "master")
    logger.debug("Normalized Odoo version: %s", normalized_version)
    venv_path, odoo_bin, addons_path = find_odoo_environment(normalized_version)
    _log_environment_context(venv_path, odoo_bin, addons_path)

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
        _UPGRADE_PATH,
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
    extra_args: list[str] | None = None,
) -> WorkflowOutcome:
    normalized_target_version = parse_version(target_version)
    source_version = infer_version(db_name)
    chain = build_upgrade_chain(source_version, normalized_target_version)

    if not chain:
        return WorkflowOutcome(
            exit_code=1,
            error_message=f"Source and target versions are the same: {source_version}",
        )

    upgraded_db_name = f"{db_name}_{normalized_target_version}"
    logger.info("Source database: %s (%s)", db_name, source_version)
    logger.info("Upgraded database: %s", upgraded_db_name)
    logger.info("Upgrade chain: %s", " → ".join([source_version] + chain))

    drop_if_exists(upgraded_db_name)
    clone_database_from_template(upgraded_db_name, db_name)

    for step_version in chain:
        venv_path, odoo_bin, addons_path = find_odoo_environment(
            step_version, add_industry=False
        )
        _log_environment_context(venv_path, odoo_bin, addons_path)

        if tests:
            prepare_exit_code = _run_prepare_tests(upgraded_db_name, debug)
            if prepare_exit_code != 0:
                return WorkflowOutcome(
                    exit_code=prepare_exit_code,
                    error_message=f"Upgrade prepare tests failed before {step_version} upgrade (exit code: {prepare_exit_code})",
                )

        logger.info("Upgrading %s to %s...", upgraded_db_name, step_version)
        args = [
            "-d",
            upgraded_db_name,
            "--upgrade-path",
            _UPGRADE_PATH,
            "-u",
            "all",
            "--stop-after-init",
        ]
        if extra_args:
            args.extend(extra_args)
        exit_code = run_odoo_command(
            venv_path, odoo_bin, args, addons_path, debug=debug
        )
        if exit_code != 0:
            return WorkflowOutcome(
                exit_code=exit_code,
                error_message=f"Failed to upgrade to {step_version} (exit code: {exit_code})",
            )

        if tests:
            check_args = [
                "-d",
                upgraded_db_name,
                "--upgrade-path",
                _UPGRADE_PATH,
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
                    error_message=f"Upgrade check failed after {step_version} upgrade (exit code: {check_exit_code})",
                )

    logger.info("Successfully upgraded database '%s'", upgraded_db_name)
    return WorkflowOutcome()


def start_workflow(
    db_name: str, shell: bool, debug: bool, extra_args: list[str] | None = None
) -> WorkflowOutcome:
    logger.info("Starting Odoo database '%s'", db_name)

    version = infer_version(db_name)
    venv_path, odoo_bin, addons_path = find_odoo_environment(version)

    logger.info("Inferred Odoo version: %s", version)
    _log_environment_context(venv_path, odoo_bin, addons_path)

    args = ["shell", "-d", db_name] if shell else ["-d", db_name]
    if extra_args:
        args.extend(extra_args)
    exit_code = run_odoo_command(venv_path, odoo_bin, args, addons_path, debug=debug)
    return WorkflowOutcome(exit_code=exit_code)


def clean_workflow(all_dbs: bool) -> WorkflowOutcome:
    pattern = _ALL_ODUP_DB_RE if all_dbs else _UPGRADED_DB_RE
    to_delete = sorted(db for db in list_databases() if pattern.match(db))

    if not to_delete:
        logger.info("No matching databases found.")
        return WorkflowOutcome()

    for db in to_delete:
        logger.info("Dropping '%s'", db)
        drop_if_exists(db)

    logger.info("Dropped %d database(s).", len(to_delete))
    return WorkflowOutcome()


def env_add_workflow(version: str) -> WorkflowOutcome:
    normalized_version = parse_version(version)
    logger.info("Setting up environment for Odoo %s", normalized_version)
    add_version_environment(normalized_version)
    return WorkflowOutcome()


def env_pull_workflow(
    version: str | None = None, verbosity: int = 0, upgrade_only: bool = False
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
