from __future__ import annotations

from typing import Optional

import typer

from .error import OdupError
from .workflows import WorkflowOutcome
from .workflows import createdb_workflow
from .workflows import env_pull_workflow
from .workflows import start_workflow
from .workflows import upgrade_workflow

app = typer.Typer(help="Local helpers for prototyping Odoo upgrade workflows.")
env_app = typer.Typer(help="Manage local Odoo checkouts and virtual environments.")
app.add_typer(env_app, name="env")


def _handle_error(exc: Exception) -> None:
    """Convert domain exceptions to consistent CLI output and exit code."""
    if isinstance(exc, OdupError):
        typer.echo(f"[odup] Error: {exc}", err=True)
    else:
        typer.echo(f"[odup] Unexpected error: {exc}", err=True)
    raise typer.Exit(1)


def _exit_from_outcome(outcome: WorkflowOutcome) -> None:
    for message in outcome.messages:
        typer.echo(message)
    if outcome.exit_code != 0:
        if outcome.error_message:
            typer.echo(outcome.error_message, err=True)
        raise typer.Exit(outcome.exit_code)


def _run_workflow(workflow, *args, **kwargs) -> None:
    try:
        outcome = workflow(*args, **kwargs)
    except Exception as exc:
        _handle_error(exc)
    _exit_from_outcome(outcome)


@env_app.command("pull")
def env_pull(
    version: Optional[str] = typer.Argument(
        None,
        help="Optional version to pull (for example: 16.0, saas-16.3, master). If omitted, pulls every local checkout.",
    ),
) -> None:
    """Pull existing local Odoo source checkouts."""
    _run_workflow(env_pull_workflow, version=version)


@app.command()
def createdb(
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
    tests: bool = typer.Option(
        False,
        "--tests",
        help="Run upgrade preparation tests (upgrade.test_prepare).",
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
        db_name=db_name,
        version=version,
        init=init,
        tests=tests,
        debug=debug,
    )


@app.command()
def upgrade(
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
        db_name=db_name,
        target_version=target_version,
        tests=tests,
        debug=debug,
    )


@app.command()
def start(
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
    _run_workflow(start_workflow, db_name=db_name, shell=shell, debug=debug)


@app.command()
def test(
    scenario: str = typer.Argument(..., help="Ad-hoc test scenario to execute."),
) -> None:
    """Placeholder command for future testing helpers."""
    typer.echo(f"[odup] Would run scenario '{scenario}'.")


def main() -> None:
    """Run the Typer application."""
    app()


if __name__ == "__main__":
    main()
