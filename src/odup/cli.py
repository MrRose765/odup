from __future__ import annotations

from typing import Optional

import typer

from .error import OdupError
from .odoo_utils import find_odoo_environment 
from .odoo_utils import parse_version 
from .odoo_utils import infer_version
from .odoo_utils import run_odoo_command
from .odoo_utils import drop_if_exists

app = typer.Typer(help="Local helpers for prototyping Odoo upgrade workflows.")


def _handle_error(exc: Exception) -> None:
    """Convert domain exceptions to consistent CLI output and exit code."""
    if isinstance(exc, OdupError):
        typer.echo(f"[odup] Error: {exc}", err=True)
    else:
        typer.echo(f"[odup] Unexpected error: {exc}", err=True)
    raise typer.Exit(1)


@app.command()
def createdb(
    db_name: str = typer.Argument(..., help="Odoo database name to create. (Will be prefixed with 'odup_')"),
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
) -> None:
    """Create a fresh Odoo database for the requested version."""
    try:
        db_name = f"odup_{db_name}"
        typer.echo(f"[odup] Creating Odoo database '{db_name}' for version {version}")

        drop_if_exists(db_name)
        version = parse_version(version)

        venv_path, odoo_bin, addons_path = find_odoo_environment(version)
    except Exception as exc:
        _handle_error(exc)
    
    typer.echo(f"[odup] Using odoo-bin: {odoo_bin}")
    typer.echo(f"[odup] Using virtual environment: {venv_path}")
    if addons_path:
        typer.echo(f"[odup] Using addons path: {addons_path}")
    
    args = ["-d", db_name]
    
    if init:
        args.extend(["-i", init])
        typer.echo(f"[odup] Installing modules: {init}")
    
    args.extend(["--stop-after-init"])
    
    typer.echo(f"[odup] Running: {venv_path}/bin/python {odoo_bin} {' '.join(args)}")
    
    try:
        exit_code = run_odoo_command(venv_path, odoo_bin, args, addons_path)
    except Exception as exc:
        _handle_error(exc)
    
    if exit_code == 0:
        typer.echo(f"[odup] Successfully created Odoo database '{db_name}'")
    else:
        typer.echo(f"[odup] Failed to create Odoo database '{db_name}' (exit code: {exit_code})", err=True)
        raise typer.Exit(exit_code)


@app.command()
def upgrade(
    target_version: str = typer.Argument(..., help="Target version to upgrade to."),
    with_tests: bool = typer.Option(
        False,
        "--tests/--no-tests",
        help="Run upgrade test suites after the upgrade steps.",
    ),
) -> None:
    """Placeholder for orchestrating the upgrade and optional test suite."""
    suffix = " with tests" if with_tests else ""
    typer.echo(f"[odup] Would upgrade database to {target_version}{suffix}.")


@app.command()
def start(
    db_name: str = typer.Argument(..., help="Odoo database name to start."),
    shell: bool = typer.Option(
        False,
        "--shell",
        help="Start the database in Odoo shell mode.",
    ),
) -> None:
    """Start an existing Odoo database using its inferred version."""
    typer.echo(f"[odup] Starting Odoo database '{db_name}'")

    try:
        version = infer_version(db_name)
        venv_path, odoo_bin, addons_path = find_odoo_environment(version)
    except Exception as exc:
        _handle_error(exc)

    typer.echo(f"[odup] Inferred Odoo version: {version}")
    typer.echo(f"[odup] Using odoo-bin: {odoo_bin}")
    typer.echo(f"[odup] Using virtual environment: {venv_path}")
    if addons_path:
        typer.echo(f"[odup] Using addons path: {addons_path}")

    if shell:
        args = ["shell", "-d", db_name]
    else:
        args = ["-d", db_name]

    try:
        exit_code = run_odoo_command(venv_path, odoo_bin, args, addons_path)
    except Exception as exc:
        _handle_error(exc)

    if exit_code != 0:
        raise typer.Exit(exit_code)


@app.command()
def test(scenario: str = typer.Argument(..., help="Ad-hoc test scenario to execute.")) -> None:
    """Placeholder command for future testing helpers."""
    typer.echo(f"[odup] Would run scenario '{scenario}'.")


def main() -> None:
    """Run the Typer application."""
    app()


if __name__ == "__main__":
    main()
