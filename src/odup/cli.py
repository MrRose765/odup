from __future__ import annotations

from typing import Optional

import typer

from .odoo_utils import OdooEnvironmentError, find_odoo_environment, run_odoo_command

app = typer.Typer(help="Local helpers for prototyping Odoo upgrade workflows.")


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
    db_name = f"odup_{db_name}"
    typer.echo(f"[odup] Creating Odoo database '{db_name}' for version {version}")
    
    try:
        venv_path, odoo_bin, addon_paths = find_odoo_environment(version)
    except OdooEnvironmentError as e:
        typer.echo(f"[odup] Error: {e}", err=True)
        raise typer.Exit(1)
    
    typer.echo(f"[odup] Using odoo-bin: {odoo_bin}")
    typer.echo(f"[odup] Using virtual environment: {venv_path}")
    if addon_paths:
        typer.echo(f"[odup] Using addon paths: {', '.join(addon_paths)}")
    
    args = ["-d", db_name]
    
    if init:
        args.extend(["-i", init])
        typer.echo(f"[odup] Installing modules: {init}")
    
    args.extend(["--stop-after-init"])
    
    typer.echo(f"[odup] Running: {venv_path}/bin/python {odoo_bin} {' '.join(args)}")
    
    try:
        exit_code = run_odoo_command(venv_path, odoo_bin, args, addon_paths)
    except OdooEnvironmentError as e:
        typer.echo(f"[odup] Error: {e}", err=True)
        raise typer.Exit(1)
    
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
def test(scenario: str = typer.Argument(..., help="Ad-hoc test scenario to execute.")) -> None:
    """Placeholder command for future testing helpers."""
    typer.echo(f"[odup] Would run scenario '{scenario}'.")


def main() -> None:
    """Run the Typer application."""
    app()


if __name__ == "__main__":
    main()
