from __future__ import annotations

import logging
import os
import sys
from typing import Optional

import typer

from .error import OdupError
from .workflows import WorkflowOutcome
from .workflows import clean_workflow
from .workflows import createdb_workflow
from .workflows import env_add_workflow
from .workflows import env_pull_workflow
from .workflows import start_workflow
from .workflows import upgrade_workflow

app = typer.Typer(
    help="Local helpers for prototyping Odoo upgrade workflows.",
    pretty_exceptions_enable=True,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_short=True,
)
env_app = typer.Typer(help="Manage local Odoo checkouts and virtual environments.")
app.add_typer(env_app, name="env")
logger = logging.getLogger(__name__)
ODOO_COMMAND_CONTEXT = {
    "allow_extra_args": True,
    "ignore_unknown_options": True,
}


class LevelColorFormatter(logging.Formatter):
    RESET = "\033[0m"
    COLORS = {
        logging.INFO: "\033[32m",  # green
        logging.WARNING: "\033[38;5;214m",  # orange
        logging.ERROR: "\033[31m",  # red
        logging.CRITICAL: "\033[31m",  # red
    }

    def __init__(self, fmt: str, datefmt: str | None = None, use_colors: bool = True):
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        original_levelname = record.levelname
        if self.use_colors:
            color = self.COLORS.get(record.levelno)
            if color:
                record.levelname = f"{color}{record.levelname}{self.RESET}"
        try:
            return super().format(record)
        finally:
            record.levelname = original_levelname


@app.callback()
def _configure_logging() -> None:
    use_colors = sys.stderr.isatty() and "NO_COLOR" not in os.environ
    formatter = LevelColorFormatter(
        fmt="%(asctime)s %(levelname)s ? [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        use_colors=use_colors,
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


def _exit_from_outcome(outcome: WorkflowOutcome) -> None:
    if outcome.exit_code != 0:
        if outcome.error_message:
            logger.error(outcome.error_message)
        raise typer.Exit(outcome.exit_code)


def _run_workflow(workflow, *args, **kwargs) -> None:
    try:
        outcome = workflow(*args, **kwargs)
    except OdupError as exc:
        logger.error(exc)
        raise typer.Exit(1)
    except Exception:
        raise
    _exit_from_outcome(outcome)


@app.command()
def clean(
    all_dbs: bool = typer.Option(
        False,
        "--all",
        help="Delete all odup-managed databases, including originals.",
    ),
) -> None:
    """Delete odup-managed databases. By default removes only upgraded databases (odup_<name>_<version>)."""
    _run_workflow(clean_workflow, all_dbs=all_dbs)


@env_app.command("add")
def env_add(
    version: str = typer.Argument(
        ..., help="Odoo version to add (e.g. 17.0, saas-16.3, master)."
    ),
) -> None:
    """Add a new Odoo version: create worktrees for odoo and enterprise, set up venv, and install dependencies."""
    _run_workflow(env_add_workflow, version=version)


@env_app.command("pull")
def env_pull(
    version: Optional[str] = typer.Argument(
        None,
        help="Optional version to pull (for example: 16.0, saas-16.3, master). If omitted, pulls every local checkout.",
    ),
    verbosity: int = typer.Option(
        0,
        "-v",
        "--verbose",
        count=True,
        help="Use -v for debug logs and -vv to also show git command output.",
    ),
    upgrade_only: bool = typer.Option(
        False,
        "--upgrade-only",
        help="Pull only upgrade-related repositories (upgrade-util, upgrade, upgrade-specific).",
    ),
) -> None:
    """Pull existing local Odoo source checkouts."""
    if verbosity:
        logging.getLogger().setLevel(logging.DEBUG)
    _run_workflow(
        env_pull_workflow,
        version=version,
        verbosity=verbosity,
        upgrade_only=upgrade_only,
    )


@app.command(context_settings=ODOO_COMMAND_CONTEXT)
def createdb(
    ctx: typer.Context,
    db_name: str = typer.Argument(
        ..., help="Odoo database name to create. (Will be prefixed with 'odup_')"
    ),
    version: Optional[str] = typer.Option(
        "master",
        "-v",
        "--version",
        help="Odoo version to bootstrap (default: master).",
    ),
    init: Optional[str] = typer.Option(
        None,
        "-i",
        "--init",
        help="Comma-separated list of modules to install.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Run odoo-bin with debugpy and wait for debugger attach on localhost:5678.",
    ),
) -> None:
    """Create a fresh Odoo database for the requested version."""
    _run_workflow(
        createdb_workflow,
        extra_args=list(ctx.args),
        db_name=db_name,
        version=version,
        init=init,
        debug=debug,
    )


@app.command(context_settings=ODOO_COMMAND_CONTEXT)
def upgrade(
    ctx: typer.Context,
    db_name: str = typer.Argument(..., help="Source Odoo database name."),
    target_version: str = typer.Argument(..., help="Target version to upgrade to."),
    tests: bool = typer.Option(
        False,
        "--tests",
        help="Run upgrade check tests (upgrade.test_check) after upgrade.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Run odoo-bin with debugpy and wait for debugger attach on localhost:5678.",
    ),
) -> None:
    """Clone and upgrade a database on a target Odoo version."""
    _run_workflow(
        upgrade_workflow,
        extra_args=list(ctx.args),
        db_name=db_name,
        target_version=target_version,
        tests=tests,
        debug=debug,
    )


@app.command(context_settings=ODOO_COMMAND_CONTEXT)
def start(
    ctx: typer.Context,
    db_name: str = typer.Argument(..., help="Odoo database name to start."),
    shell: bool = typer.Option(
        False,
        "--shell",
        help="Start the database in Odoo shell mode.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Run odoo-bin with debugpy and wait for debugger attach on localhost:5678.",
    ),
) -> None:
    """Start an existing Odoo database using its inferred version."""
    _run_workflow(
        start_workflow,
        extra_args=list(ctx.args),
        db_name=db_name,
        shell=shell,
        debug=debug,
    )


def main() -> None:
    """Run the Typer application."""
    app()


if __name__ == "__main__":
    main()
