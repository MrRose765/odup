from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from .error import OdupError
from .odoo_utils import clone_database_from_template
from .odoo_utils import drop_if_exists
from .odoo_utils import find_odoo_environment
from .odoo_utils import infer_version
from .odoo_utils import parse_version
from .odoo_utils import run_odoo_command

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
        typer.echo(
            f"[odup] Failed to create Odoo database '{db_name}' (exit code: {exit_code})",
            err=True,
        )
        raise typer.Exit(exit_code)


@app.command()
def upgrade(
    db_name: str = typer.Argument(..., help="Source Odoo database name."),
    target_version: str = typer.Argument(..., help="Target version to upgrade to."),
) -> None:
    """Clone and upgrade a database on a target Odoo version."""
    try:
        target_version = parse_version(target_version)
        upgraded_db_name = f"{db_name}_{target_version}"
        venv_path, odoo_bin, addons_path = find_odoo_environment(target_version)
    except Exception as exc:
        _handle_error(exc)

    typer.echo(f"[odup] Source database: {db_name}")
    typer.echo(f"[odup] Upgraded database: {upgraded_db_name}")
    typer.echo(f"[odup] Target Odoo version: {target_version}")
    typer.echo(f"[odup] Using odoo-bin: {odoo_bin}")
    typer.echo(f"[odup] Using virtual environment: {venv_path}")
    if addons_path:
        typer.echo(f"[odup] Using addons path: {addons_path}")

    try:
        drop_if_exists(upgraded_db_name)
        clone_database_from_template(upgraded_db_name, db_name)
    except Exception as exc:
        _handle_error(exc)

    args = [
        "-d",
        upgraded_db_name,
        "--upgrade-path",
        f"{(Path.home() / 'src' / 'upgrade-util' / 'src')},{(Path.home() / 'src' / 'upgrade' / 'migrations')}",
        "-u",
        "all",
        "--stop",
    ]

    typer.echo(f"[odup] Running: {venv_path}/bin/python {odoo_bin} {' '.join(args)}")

    try:
        exit_code = run_odoo_command(venv_path, odoo_bin, args, addons_path)
    except Exception as exc:
        _handle_error(exc)

    if exit_code == 0:
        typer.echo(f"[odup] Successfully upgraded database '{upgraded_db_name}'")
    else:
        typer.echo(
            f"[odup] Failed to upgrade database '{upgraded_db_name}' (exit code: {exit_code})",
            err=True,
        )
        raise typer.Exit(exit_code)


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
